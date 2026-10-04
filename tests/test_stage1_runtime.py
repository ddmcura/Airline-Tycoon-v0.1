"""Deterministic continuous runtime and terminal ownership contracts."""
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import unittest

from app.terminal.main import _Terminal, run_terminal
from app.terminal.session import Stage1Session
from game.simulation.pacing import RuntimeController, NANOSECOND
from game.simulation.kernel import (
    EventHandlerRegistry, iter_events_through, process_events_through,
    process_next_event, configure_clock_ratios, set_clock_mode, schedule_event,
)
from game.world_state import validate_world
from tests.test_stage1_event_kernel import make_world, schedule


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, ns):
        self.now += ns


def drain(controller):
    for _ in range(20000):
        controller.pump()
        if not controller.processing or (controller.work is None and controller.credit_ns < NANOSECOND):
            return
    raise AssertionError('runtime did not drain')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.world = make_world()
        self.clock = Clock()
        self.runtime = RuntimeController(self.world, clock=self.clock, max_batch_events=1)

    def test_irregular_fractional_credit_and_repeated_pause(self):
        start = self.world['simulation']['time_utc']
        self.clock.advance(100 * NANOSECOND)
        self.runtime.pump()
        self.assertEqual(self.world['simulation']['time_utc'], start)
        self.runtime.resume()
        for ns in (1, 142857141, 2, 857142856):
            self.clock.advance(ns)
            drain(self.runtime)
        expected = deepcopy(make_world())
        configure_clock_ratios(expected, normal=30)
        from game.world_state.timestamps import parse_canonical_utc, format_utc
        from datetime import timedelta
        target = format_utc(parse_canonical_utc(start) + timedelta(seconds=30))
        process_events_through(expected, target)
        for _ in range(3):
            self.runtime.pause()
            self.clock.advance(50 * NANOSECOND)
            self.runtime.pump()
            self.runtime.resume()
        self.runtime.pause()
        self.assertEqual(self.world, expected)
        self.assertEqual(self.runtime.credit_ns, 0)

    def test_close_and_suspension_do_not_accumulate(self):
        self.runtime.resume()
        # Suspension does not advance the injected active-uptime clock.
        before = deepcopy(self.world)
        for _ in range(10):
            self.runtime.pump()
        self.assertEqual(self.world, before)
        self.runtime.close()
        before = deepcopy(self.world)
        self.clock.advance(10000 * NANOSECOND)
        self.runtime.pump()
        self.assertEqual(self.world, before)
        with self.assertRaises(ValueError):
            self.runtime.resume()

    def test_equal_time_order_and_full_world_equivalence(self):
        due = self.world['simulation']['time_utc']
        for priority in (4, 1, 3):
            schedule(self.world, due, priority=priority)
        expected = deepcopy(self.world)
        self.runtime.resume()
        configure_clock_ratios(expected, normal=30)
        self.clock.advance(NANOSECOND)
        drain(self.runtime)
        self.runtime.pause()
        process_events_through(expected, self.world['simulation']['time_utc'])
        self.assertEqual(self.world, expected)

    def test_pause_between_events_retains_work_and_limits(self):
        due = self.world['simulation']['time_utc']
        for _ in range(4):
            schedule(self.world, due)
        self.runtime.resume()
        self.clock.advance(NANOSECOND)
        self.runtime.pump()
        work = self.runtime.work
        self.runtime.pause()
        self.clock.advance(10 * NANOSECOND)
        self.runtime.pump()
        self.assertIs(self.runtime.work, work)
        self.assertEqual(len(self.world['world_state']['pending_events']), 2)
        self.assertEqual(self.runtime.state, 'PLAYER_DRAIN')
        drain(self.runtime)
        self.assertEqual(len(self.world['world_state']['pending_events']), 0)
        self.assertEqual(self.runtime.state, 'PAUSED')

    def test_incremental_limit_is_not_reset_by_yields(self):
        due = self.world['simulation']['time_utc']
        for _ in range(5):
            schedule(self.world, due)
        work = iter_events_through(self.world, due, max_events=2)
        next(work)
        next(work)
        with self.assertRaises(StopIteration) as caught:
            next(work)
        self.assertEqual(caught.exception.value.failure.code, 'EVENT_LIMIT_REACHED')
        self.assertEqual(len(self.world['world_state']['pending_events']), 3)

    def test_generated_limit_pauses_and_requires_explicit_resume(self):
        registry = EventHandlerRegistry()
        def repeat(context):
            context.schedule_event(event_type='REPEAT', due_at_utc=context.event['due_at_utc'],
                owner_type=context.event['owner_type'], owner_id=context.event['owner_id'])
        registry.register('REPEAT', repeat)
        schedule(self.world, self.world['simulation']['time_utc'], event_type='REPEAT')
        self.runtime.registry = registry
        self.runtime.resume()
        self.clock.advance(NANOSECOND)
        drain(self.runtime)
        self.assertEqual(self.runtime.last_result.failure.code, 'EVENT_GENERATION_LIMIT_REACHED')
        before = deepcopy(self.world)
        self.runtime.pump()
        self.assertEqual(self.world, before)

    def test_failed_transaction_is_not_partial_or_retried(self):
        registry = EventHandlerRegistry()
        def fail(context):
            context.envelope['world_state']['airlines'].clear()
            raise ValueError('injected')
        registry.register('FAIL', fail)
        schedule(self.world, self.world['simulation']['time_utc'], event_type='FAIL')
        self.runtime.registry = registry
        self.runtime.resume()
        before = deepcopy(self.world)
        self.clock.advance(NANOSECOND)
        drain(self.runtime)
        set_clock_mode(before, 'PAUSED')
        self.assertEqual(self.world, before)
        self.assertIn('injected', self.runtime.diagnostic)

    def test_handler_pause_is_reported_before_another_event(self):
        registry = EventHandlerRegistry()
        registry.register('PAUSE', lambda context: context.pause())
        due = self.world['simulation']['time_utc']
        schedule(self.world, due, event_type='PAUSE')
        following = schedule(self.world, due)
        self.runtime.registry = registry
        self.runtime.resume()
        self.clock.advance(NANOSECOND)
        self.runtime.pump()
        self.assertFalse(self.runtime.running)
        self.assertIn(following, self.world['world_state']['pending_events'])
        self.assertEqual(self.runtime.diagnostic, 'Paused by an event')

    def test_processing_delay_credit_is_retained(self):
        registry = EventHandlerRegistry()
        registry.register('SLOW', lambda context: self.clock.advance(2 * NANOSECOND))
        schedule(self.world, self.world['simulation']['time_utc'], event_type='SLOW')
        self.runtime.registry = registry
        self.runtime.resume()
        self.clock.advance(NANOSECOND)
        self.runtime.pump()
        self.assertEqual(self.runtime.credit_ns, 90 * NANOSECOND)
        drain(self.runtime)
        self.assertEqual(self.runtime.credit_ns, 0)

    def test_management_event_insertion_rebuilds_pending_iterator(self):
        due = self.world['simulation']['time_utc']
        schedule(self.world, due)
        self.runtime.resume()
        self.clock.advance(NANOSECOND)
        self.runtime.pump()
        new_id = schedule(self.world, due)
        self.runtime.management_changed()
        drain(self.runtime)
        self.assertIn(new_id, self.world['world_state']['event_history'])

    def test_overload_is_visible_and_retains_credit(self):
        self.runtime = RuntimeController(self.world, clock=self.clock,
                                         overload_seconds=1, overload_grace_seconds=1)
        self.runtime.resume()
        # Seed a backlog as if an expensive transaction had just completed.
        self.runtime.credit_ns = 20 * NANOSECOND
        self.runtime.overloaded_since = 0
        self.clock.advance(2 * NANOSECOND)
        self.runtime.pump()
        self.assertFalse(self.runtime.running)
        self.assertIn('OVERLOAD', self.runtime.diagnostic)
        self.assertEqual(self.runtime.state, 'RECOVERED')
        self.assertEqual(self.runtime.credit_ns, 0)
        self.assertEqual(self.world['simulation']['time_utc'], '2026-08-20T04:31:20Z')

    def test_serialization_contains_no_controller_fields(self):
        self.runtime.resume()
        self.clock.advance(1)
        self.runtime.pump()
        self.assertTrue(validate_world(self.world).is_valid)
        encoded = json.dumps(self.world)
        for name in ('credit_ns', 'last_ns', 'overloaded_since', 'input_source'):
            self.assertNotIn(name, encoded)


class RuntimeGameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.profile_ph_runtime import workload
        cls.base = workload(1, days=1)

    def session(self):
        clock = Clock()
        session = Stage1Session(runtime_clock=clock)
        session.world = deepcopy(self.base)
        session.runtime = RuntimeController(session.world, clock=clock)
        return session, clock

    def test_real_booking_flight_finance_continuation(self):
        continuous, clock = self.session()
        stepped = deepcopy(self.base)
        bulk, _ = self.session()
        for world in (stepped, bulk.world):
            configure_clock_ratios(world, normal=30)
        continuous.resume()
        from game.world_state.timestamps import parse_canonical_utc
        target = '2026-09-08T00:00:00Z'
        seconds = int((parse_canonical_utc(target)-parse_canonical_utc(self.base['simulation']['time_utc'])).total_seconds())
        # Exactly enough credit; draining itself consumes no fake-clock time.
        continuous.runtime.credit_ns = seconds * NANOSECOND
        drain(continuous.runtime)
        continuous.pause()
        while stepped['world_state']['pending_events']:
            next_due = min(e['due_at_utc'] for e in stepped['world_state']['pending_events'].values())
            if next_due > target:
                break
            self.assertTrue(process_next_event(stepped).succeeded)
        process_events_through(stepped, target)
        self.assertTrue(bulk.advance_to(target).result.succeeded)
        self.assertEqual(continuous.world, stepped)
        self.assertEqual(continuous.world, bulk.world)

    def test_navigation_runs_and_manual_pause_persists(self):
        session, clock = self.session()
        class Input:
            calls = 0
            def poll(self, timeout=0):
                self.calls += 1
                if self.calls == 4:
                    return '/pause\n'
                if self.calls == 8:
                    return '0\n'
                clock.advance(NANOSECOND)
                return None
        session.resume()
        start = session.world['simulation']['time_utc']
        terminal = _Terminal(StringIO(), StringIO(), session, input_source=Input())
        self.assertEqual(terminal.prompt('Management selection:'), '0')
        self.assertGreater(session.world['simulation']['time_utc'], start)
        self.assertFalse(session.runtime.running)
        before = deepcopy(session.world)
        clock.advance(100 * NANOSECOND)
        session.pump()
        self.assertEqual(before, session.world)

    def test_bulk_cancellation_stops_at_one_complete_event(self):
        session, _ = self.session()
        session.on_advance_boundary = session.pause
        report = session.advance_to('2026-09-08T00:00:00Z')
        self.assertEqual(report.result.status, 'STOPPED')
        self.assertEqual(len(report.result.completed_event_ids), 1)
        self.assertTrue(session.validate())
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')

    def test_draft_revalidates_current_world_and_stale_purchase_rejects(self):
        session, clock = self.session()
        aircraft = next(iter(session.world['world_state']['aircraft']))
        draft = session.begin_scheduling(aircraft)
        airports = {a['reference_code']: a['airport_id'] for a in session.airports()}
        draft.add(airports['MNL'], airports['CEB'], departure_utc='2026-09-09T00:00:00Z')
        catalog = session.aircraft_catalog()
        model = catalog.models(catalog.manufacturers()[0]['manufacturer_id'])[0]
        preview = session.preview_purchase(model['model_id'], airports['MNL'])
        session.resume()
        clock.advance(NANOSECOND)
        drain(session.runtime)
        before = deepcopy(session.world)
        with self.assertRaisesRegex(ValueError, 'stale'):
            session.purchase(preview)
        self.assertEqual(session.world, before)
        now = session.world['simulation']['time_utc']
        session.save_scheduling(draft)
        self.assertEqual(session.world['simulation']['time_utc'], now)
        self.assertTrue(session.runtime.running)
        self.assertTrue(session.validate())

    def test_input_worker_cannot_access_authority(self):
        source = (Path(__file__).parents[1] / 'app/terminal/input_queue.py').read_text()
        self.assertNotIn('game.', source)
        self.assertNotIn('self.session', source)
        self.assertNotIn('self.world', source)

    def test_live_eof_remains_available_for_exit_confirmation(self):
        from app.terminal.input_queue import TerminalInput
        source = TerminalInput(StringIO(''))
        try:
            self.assertEqual(source.poll(1), '')
            self.assertEqual(source.poll(0), '')
        finally:
            source.close()

    def test_fresh_purchase_while_running_and_replay_after_tick(self):
        session, clock = self.session()
        session.resume()
        catalog = session.aircraft_catalog()
        model = catalog.models(catalog.manufacturers()[0]['manufacturer_id'])[0]
        location = session.delivery_locations()[0]['airport_id']
        preview = session.preview_purchase(model['model_id'], location)
        aircraft = session.purchase(preview)
        clock.advance(NANOSECOND)
        drain(session.runtime)
        before = deepcopy(session.world)
        self.assertEqual(session.purchase(preview), aircraft)
        self.assertEqual(before, session.world)
        self.assertTrue(session.runtime.running)

    def test_invalid_manual_target_preserves_running_world(self):
        session, _ = self.session()
        session.resume()
        before = deepcopy(session.world)
        with self.assertRaises(ValueError):
            session.advance_to('2020-01-01T00:00:00Z')
        self.assertEqual(before, session.world)

    def test_elapsed_current_draft_is_inert_and_does_not_overwrite_history(self):
        session, clock = self.session()
        aircraft = next(iter(session.world['world_state']['aircraft']))
        draft = session.begin_scheduling(aircraft)
        airports = {a['reference_code']: a['airport_id'] for a in session.airports()}
        draft.add(airports['MNL'], airports['CEB'])
        session.advance_seconds(3600)
        before = deepcopy(session.world)
        result = session.save_scheduling(draft)
        self.assertEqual(result.created_dated_flight_ids, ())
        self.assertEqual(session.world['simulation']['time_utc'], before['simulation']['time_utc'])
        for key in ('dated_flights', 'bookings', 'flight_results', 'transactions',
                    'active_aircraft_operations', 'event_history', 'aircraft'):
            self.assertEqual(before['world_state'][key], session.world['world_state'][key])
        self.assertTrue(session.world['world_state']['schedule_definitions'])
        self.assertEqual(draft.legs, [])


if __name__ == '__main__':
    unittest.main()
