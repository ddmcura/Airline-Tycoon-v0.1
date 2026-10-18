"""Single-plan event ownership, exact Stage 3A witnesses and failure boundaries."""

from copy import deepcopy
from hashlib import sha256
import json
import tempfile
import unittest
from unittest.mock import patch

from game.booking import checkpoint
from game.simulation import kernel
from game.simulation.resolver import resolve_until
from game.world_state import add_airline, validate_world
from game.world_state.persistence import SaveStore
from tests import test_quarterly_backend as quarterly_fixtures
from tests.test_stage1_booking_shopping import schema3_world


def digest(world):
    return sha256(json.dumps(world, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def public_checkpoint_handler(context):
    """Strict reference: independent detached preview and public recomputation."""
    prepared = checkpoint.prepare_daily_booking_checkpoint(context.envelope)
    if not prepared.succeeded:
        raise ValueError(prepared.issues[0].message)
    result = checkpoint.process_daily_booking_checkpoint(context.envelope, **prepared.as_kwargs())
    if not result.succeeded:
        raise ValueError(result.issues[0].message)


class SinglePassBookingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = quarterly_fixtures.QuarterlyBackendTests.fixture()[0]
        result = resolve_until(cls.first, '2027-01-01T23:59:59Z')
        assert result.failure is None, result.failure
        cls.retained = deepcopy(cls.first)
        result = resolve_until(cls.retained, '2027-01-02T23:59:59Z')
        assert result.failure is None, result.failure

    def process(self, world):
        result = kernel.process_next_event(world)
        self.assertTrue(result.succeeded, result.failure)
        return result

    def assert_public_equivalent(self, source):
        owned, public = deepcopy(source), deepcopy(source)
        actual = self.process(owned)
        with patch.dict(kernel.DEFAULT_EVENT_HANDLERS._handlers,
                        DAILY_BOOKING_CHECKPOINT=public_checkpoint_handler):
            expected = self.process(public)
        self.assertEqual(actual, expected)
        self.assertEqual(owned, public)
        return owned

    def test_stage3a_exact_inputs_outputs_events_and_one_consumed_plan(self):
        # Reconstruct the saved inputs without a machine-specific fixture path.
        cases = (
            (self.first, 'a4889d4ebcc41328207f4ba34cdb0bf27f1632990f15f2dd6b7cb3c85037ad3c',
             'b0f789c528c9e3fb6b58a2f8fb872c35a9b32df1b5a2abbec4fccf551612518e',
             '6acf22db332d94fecb7d76a5916e188596265ca28fbe2da152e99ef625086641', 1176),
            (self.retained, 'c62b5fb10f32b02ee5d40c5461ea27af420939b2491e97625cbc0bf05035ac7d',
             '3e738332829094ba10dea01bbc9e3d99e37cabc7e7789fb0b3f2a9fd35bfb650',
             'fba086326c4a103f3b4e88c96a612c161eddd5dd9a625896c09e505959d64506', 1165),
        )
        for source, input_hash, output_hash, order_hash, created in cases:
            with self.subTest(input_hash=input_hash):
                self.assertEqual(digest(source), input_hash)
                world = deepcopy(source)
                plans = []
                original = checkpoint.prepare_daily_booking_allocation
                def allocate(*args, **kwargs):
                    candidate = args[0]
                    pending = [c for c in candidate['world_state']['booking_state']['booking_checkpoints'].values()
                               if c['status'] == 'PENDING']
                    self.assertEqual(len(pending), 1)
                    number = source['deterministic_state']['id_allocator']['next_by_type']['booking_checkpoint']
                    self.assertEqual(pending[0]['booking_checkpoint_id'], f'booking_checkpoint-{number:012d}')
                    plan = original(*args, **kwargs)
                    plans.append(plan)
                    return plan
                batches = checkpoint._canonical_batches
                def consume(plan, *args):
                    self.assertIs(plan, plans[0])
                    return batches(plan, *args)
                with patch.object(checkpoint, 'prepare_daily_booking_allocation', side_effect=allocate) as allocation, \
                     patch.object(checkpoint, '_canonical_batches', side_effect=consume), \
                     patch.object(checkpoint, 'prepare_daily_booking_checkpoint', side_effect=AssertionError('event probe')), \
                     patch.object(checkpoint, '_clone_runtime_world', side_effect=AssertionError('event probe copy')):
                    result = self.process(world)
                self.assertEqual(allocation.call_count, 1)
                self.assertEqual(len(result.completed_event_ids), 1)
                self.assertEqual(len(world['world_state']['bookings']) - len(source['world_state']['bookings']), created)
                self.assertEqual(digest(world), output_hash)
                events = sorted(world['world_state']['pending_events'].values(),
                                key=lambda e: (e['due_at_utc'], *e['order_key'], e['event_id']))
                ordered = [(e['due_at_utc'], e['order_key'], e['event_id'], e['event_type']) for e in events]
                self.assertEqual(sha256(json.dumps(ordered, separators=(',', ':')).encode()).hexdigest(), order_hash)
                self.assertEqual(len(world['world_state']['demand_state']['processed_cohorts']),
                                 len(source['world_state']['demand_state']['processed_cohorts']) + 2)

    def test_completed_event_reuses_without_allocation_or_mutation(self):
        world = deepcopy(self.first)
        self.process(world)
        completed = next(e for e in world['world_state']['event_history'].values()
                         if e['event_type'] == checkpoint.BOOKING_CHECKPOINT_EVENT_TYPE)
        before = deepcopy(world)
        with patch.object(checkpoint, 'prepare_daily_booking_allocation', side_effect=AssertionError('reallocation')):
            checkpoint._event_handler(kernel.EventContext(world, deepcopy(completed), kernel._EVENT_TRANSACTION_TOKEN))
        self.assertEqual(world, before)

    def test_stage3a_fixtures_match_strict_and_shared_resolvers(self):
        for source, target, expected_hash in (
            (self.first, '2027-01-02T00:00:00Z', 'b0f789c528c9e3fb6b58a2f8fb872c35a9b32df1b5a2abbec4fccf551612518e'),
            (self.retained, '2027-01-03T00:00:00Z', '3e738332829094ba10dea01bbc9e3d99e37cabc7e7789fb0b3f2a9fd35bfb650'),
        ):
            for shared in (False, True):
                with self.subTest(target=target, shared=shared):
                    world = deepcopy(source)
                    result = resolve_until(world, target, shared=shared)
                    self.assertIsNone(result.failure, result.failure)
                    self.assertEqual(digest(world), expected_hash)

    def test_legacy_zero_fare_and_capacity_contention_match_public_boundary(self):
        for fare in (0, 10000):
            with self.subTest(fare=fare):
                world, _market, flight_id = schema3_world()
                flight = world['world_state']['dated_flights'][flight_id]
                revision = world['world_state']['schedule_definitions'][flight['schedule_id']]['revisions'][str(flight['schedule_revision'])]
                flight['capacity'] = revision['capacity'] = 1
                flight['fare_offer']['amount_minor'] = revision['fare_offer']['amount_minor'] = fare
                world['simulation']['time_utc'] = '2026-08-19T23:59:59Z'
                prepared = checkpoint.prepare_daily_booking_checkpoint(world, activation_providers=())
                self.assertTrue(prepared.succeeded, prepared.issues)
                self.assertTrue(checkpoint.process_daily_booking_checkpoint(
                    world, **prepared.as_kwargs(), activation_providers=()).succeeded)
                final = self.assert_public_equivalent(world)
                self.assertTrue(validate_world(final).is_valid)
                sold = [b for b in final['world_state']['bookings'].values() if b.get('booked_at_utc') == '2026-08-20T00:00:00Z']
                self.assertEqual(sum(b['passenger_count'] for b in sold), 1)
                if fare == 0:
                    self.assertTrue(all(b['finance_transaction_id'] is None for b in sold))

    def test_public_preparation_detached_and_apply_recomputes(self):
        world = deepcopy(self.first)
        world['simulation']['time_utc'] = '2027-01-02T00:00:00Z'
        before = deepcopy(world)
        original = checkpoint.prepare_daily_booking_allocation
        with patch.object(checkpoint, 'prepare_daily_booking_allocation', wraps=original) as allocation:
            prepared = checkpoint.prepare_daily_booking_checkpoint(world)
            self.assertTrue(prepared.succeeded, prepared.issues)
            self.assertEqual(world, before)
            detached = prepared.as_kwargs()
            detached['expected_inventory_revisions'].clear()
            self.assertTrue(prepared.arguments['expected_inventory_revisions'])
            result = checkpoint.process_daily_booking_checkpoint(world, **prepared.as_kwargs())
            self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(allocation.call_count, 2)

    def test_existing_current_day_cohorts_are_preserved(self):
        world = deepcopy(self.first)
        world['simulation']['time_utc'] = '2027-01-02T00:00:00Z'
        prepared = checkpoint.prepare_daily_booking_checkpoint(world)
        plan = checkpoint.prepare_daily_booking_allocation(world, **{
            k: v for k, v in prepared.as_kwargs().items()
            if k not in ('expected_booking_revision', 'expected_finance_revisions', 'expected_event_order_cursor')
        })
        self.assertTrue(plan.succeeded, plan.issues)
        markers = deepcopy(world['world_state']['demand_state']['processed_cohorts'])
        self.assertTrue(markers)
        final = self.assert_public_equivalent(world)
        self.assertEqual(final['world_state']['demand_state']['processed_cohorts'], markers)

    def test_finance_membership_and_liability_posting_exclude_unsold_airline(self):
        world = deepcopy(self.first)
        other = add_airline(world, 'No sales')
        before = deepcopy(world['world_state'])
        self.process(world)
        state = world['world_state']
        self.assertEqual(state['airlines'][other], before['airlines'][other])
        for key in state['airlines'][other]['financial_account_ids']:
            self.assertEqual(state['financial_accounts'][key], before['financial_accounts'][key])
        sales = [t for key, t in state['transactions'].items() if key not in before['transactions']]
        self.assertEqual(len(sales), 1)
        sale = sales[0]
        self.assertNotEqual(sale['airline_id'], other)
        self.assertEqual(sum(e['amount_minor'] for e in sale['entries']), 0)
        gross = sum(state['bookings'][key]['total_fare_minor'] for key in sale['source_booking_ids'])
        owner = sale['airline_id']
        accounts = {state['financial_accounts'][key]['code']: key
                    for key in state['airlines'][owner]['financial_account_ids']}
        for code in ('cash', 'unflown_tickets'):
            key = accounts[code]
            self.assertEqual(state['financial_accounts'][key]['balance_minor'],
                             before['financial_accounts'][key]['balance_minor'] + gross)
        self.assertEqual(state['financial_accounts'][accounts['passenger_revenue']],
                         before['financial_accounts'][accounts['passenger_revenue']])

    def test_event_provider_failures_and_retained_values_are_isolated(self):
        from game.scheduling.quarterly_supply import QuarterlyActivationProvider
        original = QuarterlyActivationProvider.active_market_ids
        for action in ('exception', 'mutation', 'mutable_output', 'retained_reference'):
            with self.subTest(action=action):
                world = deepcopy(self.first)
                observed, outputs = [], []
                def provide(provider, envelope, *args, **kwargs):
                    observed.append(envelope)
                    values = list(original(provider, envelope, *args, **kwargs))
                    outputs.append(values)
                    if action == 'exception':
                        envelope['metadata']['isolation_sentinel'] = 'partial'
                        raise RuntimeError('provider interrupted')
                    if action == 'mutation':
                        envelope['metadata']['isolation_sentinel'] = 'mutated'
                    return values
                with patch.object(QuarterlyActivationProvider, 'active_market_ids', provide):
                    result = kernel.process_next_event(world)
                self.assertTrue(observed)
                if action in ('exception', 'mutation'):
                    self.assertFalse(result.succeeded)
                    self.assertEqual(world, self.first)
                    self.process(world)
                else:
                    self.assertTrue(result.succeeded, result.failure)
                after = deepcopy(world)
                for detached in observed:
                    self.assertIsNot(detached, world)
                    detached['metadata']['isolation_sentinel'] = 'after return'
                for values in outputs:
                    values.clear()
                self.assertEqual(world, after)
                self.assertEqual(digest(world), 'b0f789c528c9e3fb6b58a2f8fb872c35a9b32df1b5a2abbec4fccf551612518e')

    def test_late_witness_mutations_roll_back_and_retry_exactly(self):
        for target in ('inventory', 'finance', 'configuration', 'demand', 'pack', 'booking', 'quarterly_source', 'event'):
            with self.subTest(target=target):
                world = deepcopy(self.retained)
                before = deepcopy(world)
                original = checkpoint.prepare_daily_booking_allocation
                mutations = []
                def mutate(candidate, **kwargs):
                    plan = original(candidate, **kwargs)
                    self.assertTrue(plan.succeeded, plan.issues)
                    state = candidate['world_state']
                    if target == 'inventory':
                        key = next(s.dated_flight_id for m in plan.market_results for g in m.desired_date_results
                                   for s in g.selected_offer_allocations)
                        flight = next(f for f in state['dated_flights'].values() if f['occurrence_key'] == key)
                        flight['inventory_revision'] += 1
                    elif target == 'finance':
                        next(iter(state['airlines'].values()))['finance_revision'] += 1
                    elif target == 'configuration':
                        candidate['simulation']['configuration']['booking']['configuration_fingerprint'] = '0' * 64
                    elif target == 'demand':
                        state['demand_state']['demand_model_revision'] += 1
                    elif target == 'pack':
                        candidate['simulation']['configuration']['demand']['market_pack_configuration']['revision'] += 1
                    elif target == 'booking':
                        state['booking_state']['booking_revision'] += 1
                    elif target == 'quarterly_source':
                        next(iter(state['services'].values()))['retired_at_utc'] = candidate['simulation']['time_utc']
                    else:
                        candidate['simulation']['event_order_cursor'] += 1
                    mutations.append(target)
                    return plan
                with patch.object(checkpoint, 'prepare_daily_booking_allocation', side_effect=mutate) as allocation:
                    failed = kernel.process_next_event(world)
                self.assertEqual(allocation.call_count, 1)
                self.assertEqual(mutations, [target])
                self.assertFalse(failed.succeeded)
                self.assertEqual(world, before)
                self.process(world)
                self.assertEqual(digest(world), '3e738332829094ba10dea01bbc9e3d99e37cabc7e7789fb0b3f2a9fd35bfb650')

    def test_late_failure_save_load_retry_preserves_successful_prefix(self):
        world = quarterly_fixtures.QuarterlyBackendTests.fixture()[0]
        control = deepcopy(world)
        expected = resolve_until(control, '2027-01-02T00:00:00Z')
        self.assertIsNone(expected.failure)
        with patch.object(checkpoint, 'schedule_event', side_effect=RuntimeError('late recurrence failure')):
            result = resolve_until(world, '2027-01-02T00:00:00Z')
        self.assertIsNotNone(result.failure)
        self.assertTrue(world['world_state']['event_history'])
        self.assertFalse(world['world_state']['bookings'])
        prefix = quarterly_fixtures.QuarterlyBackendTests.fixture()[0]
        self.assertIsNone(resolve_until(prefix, world['simulation']['time_utc']).failure)
        self.assertEqual(world, prefix)
        with tempfile.TemporaryDirectory() as temporary:
            store = SaveStore(temporary)
            career = store.new_career_id()
            store.save(career, 'manual', world)
            loaded, _ = store.load(career)
        self.assertEqual(loaded, world)
        self.assertEqual(loaded['simulation']['clock_state'], 'PAUSED')
        retried = resolve_until(loaded, '2027-01-02T00:00:00Z')
        self.assertIsNone(retried.failure)
        self.assertEqual(loaded, control)


if __name__ == '__main__':
    unittest.main()
