"""Patch 1.2B: future allocation is not same-timestamp causal expansion."""
from collections import Counter
from copy import deepcopy
from datetime import timedelta
import json
import unittest
from unittest.mock import patch

from game.simulation import kernel
from game.simulation.resolver import resolve_until
from game.simulation.pacing import RuntimeController
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import parse_canonical_utc, format_utc
from tests.test_shared_candidate import probe_registry, DUE
from tests.test_stage1_event_kernel import make_world, schedule
from tests.resolution_oracle import save_reload


def dense_weekly_fixture(fleet):
    """Real purchases, timing, continuous publication; no fake funds/history."""
    from game.aircraft_market.acquisition import preview_purchase, purchase_aircraft
    from game.aircraft_market.reference_catalog import PH_AIRCRAFT_CATALOG_VERSION
    from game.scheduling import WeeklyDraft
    world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
        ceo_display_name='Audit', airline_display_name='Causal Accounting',
        base_airport_reference_code='MNL')
    assert resolve_until(world, '2026-09-20T00:00:00Z', shared=True).succeeded
    state = world['world_state']
    owner = state['player']['primary_airline_id']
    ports = {row['reference_code']: key for key, row in state['airports'].items()}
    if fleet == 2:
        purchase_aircraft(world, preview_purchase(world, airline_id=owner,
            model_id='airbus-a320neo', catalog_version=PH_AIRCRAFT_CATALOG_VERSION,
            delivery_airport_id=ports['MNL']))
    elif fleet != 1:
        raise ValueError('one or two aircraft')
    destination = ports['CRK' if fleet == 1 else 'CEB']
    for aircraft in list(world['world_state']['aircraft']):
        draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
        for day in range(7):
            cursor = parse_canonical_utc('2026-09-20T16:00:00Z') + timedelta(days=day)
            for _ in range(8 if fleet == 1 else 4):
                draft.add(ports['MNL'], destination, departure_utc=format_utc(cursor), fare_minor=11600)
                draft.add_return(fare_minor=11600)
                cursor = parse_canonical_utc(draft.earliest(ports['MNL'], destination,
                                               not_before=draft.legs[-1]['departure_utc']))
        draft.save_current(world, continuous=True)
    assert resolve_until(world, '2026-09-20T15:59:59Z', shared=True).succeeded
    assert validate_world(world).is_valid
    return world


class FakeClock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now


class CausalAccountingTests(unittest.TestCase):
    def compare(self, world, target, registry, **options):
        expected = deepcopy(world)
        strict = resolve_until(expected, target, registry=registry, **options)
        for cap in (1, 2, 8):
            actual = deepcopy(world)
            shared = resolve_until(actual, target, registry=registry, shared=True,
                                   shadow=True, max_batch_events=cap, **options)
            self.assertEqual(shared, strict)
            self.assertEqual(actual, expected)
            self.assertTrue(validate_world(actual).is_valid)
        return strict, expected

    def test_future_fanout_over_100_is_kept_even_with_other_due_work(self):
        world = make_world()
        future = format_utc(parse_canonical_utc(DUE) + timedelta(hours=1))
        def generate(context):
            for _ in range(113):
                context.schedule_event(event_type='NO_OP', due_at_utc=future,
                    owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(generate)
        schedule(world, DUE, event_type='PROBE'); schedule(world, DUE)
        result, actual = self.compare(world, DUE, registry)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(actual['world_state']['pending_events']), 113)
        self.assertEqual(len(result.completed_event_ids), 2)
        self.assertEqual({e['due_at_utc'] for e in actual['world_state']['pending_events'].values()}, {future})
        result, _ = self.compare(actual, future, registry)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(result.completed_event_ids), 113)

    def test_direct_same_time_runaway_stops_at_100_and_retry_is_exact(self):
        def repeat(context):
            context.schedule_event(event_type='PROBE', due_at_utc=context.event['due_at_utc'],
                owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(repeat)
        world = make_world(); schedule(world, DUE, event_type='PROBE')
        result, actual = self.compare(world, DUE, registry)
        self.assertEqual(result.failure.code, 'EVENT_GENERATION_LIMIT_REACHED')
        self.assertEqual(len(result.completed_event_ids), 100)
        self.assertEqual(len(actual['world_state']['pending_events']), 1)
        retry, resumed = self.compare(actual, DUE, registry)
        self.assertEqual(retry.failure.code, result.failure.code)
        self.assertEqual(len(retry.completed_event_ids), 100)
        self.assertEqual(len(resumed['world_state']['event_history']), 200)

    def test_indirect_same_time_loop_survives_shared_strict_flushes(self):
        def first(context):
            context.schedule_event(event_type='SECOND', due_at_utc=DUE,
                owner_type='airline', owner_id=context.event['owner_id'])
        def second(context):
            context.schedule_event(event_type='PROBE', due_at_utc=DUE,
                owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(first); registry.register('SECOND', second)
        world = make_world(); schedule(world, DUE, event_type='PROBE')
        result, _ = self.compare(world, DUE, registry)
        self.assertEqual(result.failure.code, 'EVENT_GENERATION_LIMIT_REACHED')
        self.assertEqual(len(result.completed_event_ids), 100)

    def test_boundary_resets_only_on_chronological_progress(self):
        later = format_utc(parse_canonical_utc(DUE) + timedelta(seconds=1))
        def generate(context):
            for _ in range(60):
                context.schedule_event(event_type='NO_OP', due_at_utc=context.event['due_at_utc'],
                    owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(generate)
        world = make_world()
        schedule(world, DUE, event_type='PROBE'); schedule(world, later, event_type='PROBE')
        result, actual = self.compare(world, later, registry)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(result.completed_event_ids), 122)
        self.assertEqual(actual['world_state']['pending_events'], {})

    def test_advancing_self_generation_retains_processed_event_limit(self):
        def repeat(context):
            later = format_utc(parse_canonical_utc(context.event['due_at_utc']) + timedelta(seconds=1))
            context.schedule_event(event_type='PROBE', due_at_utc=later,
                owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(repeat)
        world = make_world(); schedule(world, DUE, event_type='PROBE')
        target = format_utc(parse_canonical_utc(DUE) + timedelta(seconds=114))
        limited, _ = self.compare(world, target, registry, max_events=3)
        self.assertEqual(limited.failure.code, 'EVENT_LIMIT_REACHED')
        self.assertEqual(len(limited.completed_event_ids), 3)
        full, _ = self.compare(world, target, registry)
        self.assertTrue(full.succeeded)
        self.assertEqual(len(full.completed_event_ids), 115)


    def test_future_and_same_time_children_have_separate_accounting(self):
        future = format_utc(parse_canonical_utc(DUE) + timedelta(hours=1))
        def generate(context):
            for due in [future] * 113 + [DUE]:
                context.schedule_event(event_type='NO_OP', due_at_utc=due,
                    owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(generate)
        world = make_world(); schedule(world, DUE, event_type='PROBE')
        result, actual = self.compare(world, DUE, registry, max_generated_events=2)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(result.completed_event_ids), 2)
        self.assertEqual(len(actual['world_state']['pending_events']), 113)

    def test_genuine_runtime_stop_retains_pacing_credit(self):
        def repeat(context):
            context.schedule_event(event_type='PROBE', due_at_utc=context.event['due_at_utc'],
                owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(repeat)
        for shared in (False, True):
            world = make_world(); now = world['simulation']['time_utc']
            schedule(world, now, event_type='PROBE')
            clock = FakeClock(); runtime = RuntimeController(world, clock=clock,
                                                              registry=registry, shared=shared)
            runtime.resume(); clock.now = 10**9
            for _ in range(101):
                runtime.pump()
                if runtime.blocked: break
            self.assertTrue(runtime.blocked)
            self.assertEqual(runtime.last_result.failure.code, 'EVENT_GENERATION_LIMIT_REACHED')
            self.assertEqual(runtime.credit_ns, 30 * 10**9)
            self.assertEqual(world['simulation']['time_utc'], now)
            self.assertEqual(len(world['world_state']['pending_events']), 1)
            before = deepcopy(world); runtime.pump(); self.assertEqual(world, before)

    def test_booking_and_market_periodic_successors_are_unchanged(self):
        world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='Period', airline_display_name='Period Air', base_airport_reference_code='MNL')
        result, actual = self.compare(world, '2026-10-01T00:00:00Z', kernel.DEFAULT_EVENT_HANDLERS)
        self.assertTrue(result.succeeded)
        pending = actual['world_state']['pending_events'].values()
        self.assertEqual(Counter(e['event_type'] for e in pending),
                         {'DAILY_BOOKING_CHECKPOINT': 1, 'AIRCRAFT_MARKET_ROTATION': 1})
        self.assertEqual(sorted(e['due_at_utc'] for e in pending),
                         ['2026-10-02T00:00:00Z', '2026-11-01T00:00:00Z'])

    def test_payment_successor_and_exact_settlement_are_unchanged(self):
        from tests.payment_fixtures import payment_world
        world, target = payment_world()
        result, actual = self.compare(world, target, kernel.DEFAULT_EVENT_HANDLERS)
        self.assertTrue(result.succeeded)
        payments = [e for e in actual['world_state']['pending_events'].values()
                    if e['event_type'] == 'AIRCRAFT_CONTRACT_PAYMENT']
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]['due_at_utc'], '2026-11-01T00:00:01Z')


class WeeklyAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {fleet: dense_weekly_fixture(fleet) for fleet in (1, 2)}

    def resolve_publication(self, fleet, *, shared):
        world = deepcopy(self.fixtures[fleet])
        trace = []
        original = kernel._apply_handler_candidate
        def observed(before, candidate, event_id, handler, **kwargs):
            event = deepcopy(candidate['world_state']['pending_events'][event_id])
            out = original(before, candidate, event_id, handler, **kwargs)
            trace.append((event, [deepcopy(candidate['world_state']['pending_events'][i]) for i in out[2]]))
            return out
        with patch.object(kernel, '_apply_handler_candidate', observed):
            result = resolve_until(world, '2026-09-20T16:00:00Z', shared=shared, max_batch_events=8)
        return world, result, trace

    def test_one_and_two_aircraft_publication_and_due_departures_are_exact(self):
        for fleet in (1, 2):
            with self.subTest(fleet=fleet):
                strict, result, trace = self.resolve_publication(fleet, shared=False)
                shared, shared_result, shared_trace = self.resolve_publication(fleet, shared=True)
                self.assertTrue(result.succeeded, result.failure)
                self.assertEqual(shared_result, result)
                self.assertEqual(shared, strict)
                self.assertEqual(trace, shared_trace)
                publication, children = trace[0]
                self.assertEqual(publication['event_type'], 'STAGE1_WEEKLY_PUBLICATION')
                self.assertEqual(Counter(e['event_type'] for e in children),
                    {'STAGE1_FLIGHT_DEPARTURE': 112, 'STAGE1_WEEKLY_PUBLICATION': 1})
                self.assertEqual(len({e['event_id'] for e in children}), 113)
                self.assertTrue(all(e['due_at_utc'] > publication['due_at_utc'] for e in children))
                state = shared['world_state']
                self.assertEqual(len(state['dated_flights']), 560)
                self.assertTrue(all(e['event_id'] in state['pending_events'] for e in children))
                self.assertEqual([e['due_at_utc'] for e in children if e['event_type'] ==
                                  'STAGE1_WEEKLY_PUBLICATION'], ['2026-09-27T16:00:00Z'])
                self.assertEqual(len(state['active_aircraft_operations']), fleet)
                self.assertEqual(Counter(e['event_type'] for e, _ in trace[1:]),
                                 {'STAGE1_FLIGHT_DEPARTURE': fleet})
                self.assertEqual(Counter(e['event_type'] for _, cc in trace[1:] for e in cc),
                                 {'STAGE1_FLIGHT_COMPLETION': fleet})
                self.assertTrue(validate_world(shared).is_valid)
                self.assertEqual(save_reload(shared), shared)
                encoded = json.dumps(shared)
                self.assertNotIn('_generation_boundary', encoded)
                self.assertNotIn('_generated', encoded)

    def test_runtime_speeds_keep_exact_credit_and_cross_boundary(self):
        results = []
        for speed in ('Normal Speed', 'Fast', 'Very Fast'):
            world = deepcopy(self.fixtures[2]); clock = FakeClock()
            runtime = RuntimeController(world, clock=clock); runtime.resume(speed)
            # Exactly one simulated second plus the unavoidable integer-ns remainder.
            elapsed = (10**9 + runtime.ratio - 1) // runtime.ratio
            clock.now = elapsed
            for _ in range(5): runtime.pump()
            self.assertIsNone(runtime.diagnostic)
            self.assertEqual(world['simulation']['time_utc'], '2026-09-20T16:00:00Z')
            self.assertEqual(runtime.credit_ns, elapsed * runtime.ratio - 10**9)
            self.assertEqual(len(world['world_state']['active_aircraft_operations']), 2)
            runtime.select_speed('Normal Speed')
            runtime.close()
            results.append(world)
        self.assertEqual(results[0], results[1]); self.assertEqual(results[1], results[2])
