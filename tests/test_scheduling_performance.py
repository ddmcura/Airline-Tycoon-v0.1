"""Structural performance gates: exact authority and bounded transaction work.

No machine-dependent latency assertions. Run profile_scheduling for timings.
"""
from copy import deepcopy
from datetime import date, timedelta
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.scheduling import WeeklyDraft
from game.scheduling import publication
from game.simulation.kernel import EventContext
from game.world_state import create_stage1_new_game, validate_world
from game.world_state import fulfilment_validation


class SchedulingPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='CEO', airline_display_name='Performance Air',
            base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base)
        state = self.world['world_state']
        self.owner = state['player']['primary_airline_id']
        self.aircraft = next(iter(state['aircraft']))
        self.ports = {row['reference_code']: key for key, row in state['airports'].items()}
        self.draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)

    def dates(self, *offsets):
        return tuple((date(2026, 9, 7) + timedelta(days=i)).isoformat() for i in offsets)

    def add(self, *offsets):
        return self.draft.add_weekdays(self.ports['MNL'], self.ports['DVO'],
            self.dates(*offsets), '08:00', return_flight=True, fare_minor=11600)

    def test_daily_return_uses_constant_complete_validation_boundaries(self):
        for offsets in ((0,), tuple(range(7))):
            with self.subTest(days=len(offsets)):
                self.draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)
                with patch('game.scheduling.weekly.validate_world', wraps=validate_world) as validations, \
                     patch.object(publication, 'validate_world', wraps=validate_world) as nested:
                    self.assertEqual(self.add(*offsets), 2 * len(offsets))
                self.assertEqual(validations.call_count, 0) # Draft proof constructs no world candidate.
                self.assertEqual(nested.call_count, 0)
                self.assertEqual(self.world, self.base)
                self.assertNotIn('_operation_references', self.draft.__dict__)
                self.assertNotIn('_operation_movements', self.draft.__dict__)

    def test_base_projection_and_reference_are_bounded_to_one_add_operation(self):
        calls = []
        original = WeeklyDraft._base_movements
        def counted(draft):
            calls.append(draft.aircraft_id)
            return original(draft)
        with patch.object(WeeklyDraft, '_base_movements', counted):
            self.add(*range(7))
        self.assertEqual(calls, [self.aircraft])
        current = self.draft.validate_current(self.world)
        self.assertEqual(current.legs, self.draft.legs)
        self.assertNotIn('_operation_references', current.__dict__)
        self.assertNotIn('_operation_movements', current.__dict__)

    def test_batch_matches_composed_public_definition_commands_exactly(self):
        self.add(0, 2, 4)
        for options in ({}, {'repeat_until': '2026-10-11'}, {'continuous': True}):
            with self.subTest(options=options):
                actual = self.draft._candidate(self.draft.legs, **options)
                # Reference composition retains the former per-definition public
                # transactions. It uses the SAME modern rules, not legacy state.
                with patch('game.scheduling.weekly._stage_schedule_definition',
                           publication.create_schedule_definition):
                    reference = self.draft._candidate(self.draft.legs, **options)
                self.assertEqual(actual, reference)
                self.assertTrue(validate_world(actual[0]).is_valid)
                self.assertEqual(self.world, self.base)

    def test_last_day_conflict_preserves_whole_draft_and_undo(self):
        self.add(6)
        before, undo = self.draft.legs, deepcopy(self.draft._undo_stack)
        with self.assertRaisesRegex(ValueError, '2026-09-13'):
            self.add(*range(7))
        self.assertEqual(self.draft.legs, before)
        self.assertEqual(self.draft._undo_stack, undo)
        self.assertEqual(self.world, self.base)
        self.assertNotIn('_operation_references', self.draft.__dict__)

    def test_invalid_staged_timing_cannot_cross_save_boundary(self):
        self.add(0)
        self.draft._legs[-1]['planning_timing']['turnaround_seconds'] = 0
        with self.assertRaises(ValueError):
            self.draft.save(self.world)
        self.assertEqual(self.world, self.base)

    def test_public_commands_still_reject_invalid_input_world_atomically(self):
        self.world['world_state']['aircraft'][self.aircraft]['configuration']['economy_capacity'] = -1
        before = deepcopy(self.world)
        result = publication.publish_occurrences_through(self.world, '2026-09-13T15:59:59Z')
        self.assertFalse(result.succeeded)
        self.assertEqual(self.world, before)
        with self.assertRaises(ValueError):
            WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)

    def test_lifecycle_index_scans_events_once_and_preserves_duplicate_rejection(self):
        self.add(*range(7))
        self.draft.save_current(self.world)
        original = fulfilment_validation._all_events
        scans = []
        class Events(dict):
            def values(self):
                scans.append(True)
                return super().values()
        with patch.object(fulfilment_validation, '_all_events',
                          lambda world: Events(original(world))):
            self.assertTrue(validate_world(self.world).is_valid)
        self.assertEqual(len(scans), 1)
        from game.simulation import schedule_event
        event = next(row for row in self.world['world_state']['pending_events'].values()
                     if row['event_type'] == 'STAGE1_FLIGHT_DEPARTURE')
        schedule_event(self.world, event_type=event['event_type'], due_at_utc=event['due_at_utc'],
            owner_type=event['owner_type'], owner_id=event['owner_id'],
            operation_revision=event['operation_revision'], priority=event['order_key'][0],
            payload=deepcopy(event['payload']))
        validation = validate_world(self.world)
        self.assertFalse(validation.is_valid)
        self.assertIn('invalid_lifecycle_event', [issue.code for issue in validation.errors])

    def test_event_publication_requires_kernel_owned_candidate(self):
        context = EventContext(self.world, {})
        with self.assertRaisesRegex(ValueError, 'isolated kernel'):
            publication._publish_event_occurrences(context, '2026-09-13T15:59:59Z', schedule_ids=())
        self.assertEqual(self.world, self.base)

    def test_timeline_uses_retained_bounds_without_rebuilding_timing(self):
        self.add(*range(7))
        with patch.object(self.draft, '_snapshot', side_effect=AssertionError('recalculated timing')):
            rows = self.draft.week_rows('2026-09-07')
        self.assertEqual(len(rows), 14)
        self.assertEqual({row['timeline_departure_local'][:10] for row in rows}, set(self.dates(*range(7))))
        self.assertFalse(any(row['pattern_only'] for row in rows))

    def test_owned_scheduling_aircraft_matches_validated_public_fleet(self):
        from game.aircraft_operations.projections import (
            _project_owned_scheduling_aircraft, project_airline_fleet)
        row = _project_owned_scheduling_aircraft(self.world, self.owner, self.aircraft)
        self.assertEqual(row, project_airline_fleet(self.world, self.owner)[0])
        row['display_registration'] = 'changed presentation copy'
        self.assertEqual(self.world, self.base)
        self.assertIsNone(_project_owned_scheduling_aircraft(self.world, 'missing', self.aircraft))
        self.world['world_state']['aircraft'][self.aircraft]['configuration']['economy_capacity'] = -1
        self.assertIsNone(project_airline_fleet(self.world, self.owner))

    def test_publication_notice_defers_one_atomic_command_and_guards_exit(self):
        from app.gui.app import AirlineTycoonApp
        with tempfile.TemporaryDirectory() as directory:
            session = Stage1Session(save_root=directory, runtime_clock=lambda: 0)
            session.world = deepcopy(self.world)
            app = AirlineTycoonApp(session_factory=lambda: session)
            app.build()
            try:
                self.add(0)
                app._draft = self.draft
                with patch('app.gui.weekly_workspace.Clock.schedule_once') as clock, \
                     patch.object(app, '_dialog'), patch.object(app, '_save_schedule') as save, \
                     patch.object(app, '_dismiss'), patch.object(app.session, 'pump') as pump:
                    app._queue_schedule_publication(None, continuous=True)
                    self.assertEqual(session.world, self.base)
                    save.assert_not_called()
                    self.assertFalse(app._idle())
                    from unittest.mock import Mock
                    leave = Mock()
                    app._guard_unsaved(leave)
                    leave.assert_not_called()
                    app.tick(.2)
                    pump.assert_not_called()
                    callback, delay = clock.call_args.args
                    self.assertEqual(delay, .05)
                    callback(0)
                    save.assert_called_once_with(None, continuous=True)
                    self.assertIsNone(app._schedule_publication_pending)
            finally:
                app.on_stop()

    def test_builder_performs_one_refresh_for_success_and_rejection(self):
        from app.gui.app import AirlineTycoonApp
        with tempfile.TemporaryDirectory() as directory:
            session = Stage1Session(save_root=directory, runtime_clock=lambda: 0)
            session.world = deepcopy(self.world)
            app = AirlineTycoonApp(session_factory=lambda: session)
            app.build()
            try:
                app._enter_game()
                app.show_view('Schedule')
                app.start_schedule(self.aircraft)
                app.change_schedule_week(1)
                app._builder_origin, app._builder_destination = self.ports['MNL'], self.ports['DVO']
                app._builder_time, app._builder_fare = '08:00', '116'
                app._builder_return, app._builder_weekdays = True, set(range(7))
                with patch.object(app, 'refresh', wraps=app.refresh) as refresh:
                    self.assertEqual(app.add_builder_flights(), 14)
                    self.assertEqual(refresh.call_count, 1)
                before = app._draft.legs
                with patch.object(app, 'refresh', wraps=app.refresh) as refresh, patch.object(app, '_error'):
                    self.assertIsNone(app.add_builder_flights())
                    self.assertEqual(refresh.call_count, 1)
                self.assertEqual(app._draft.legs, before)
                self.assertEqual(session.world, self.base)
            finally:
                app.on_stop()
