"""Regression contracts for the approved maximum-allowance weekly planner."""

from copy import deepcopy
from datetime import timedelta
from io import StringIO
import json
import unittest
from unittest.mock import patch

from app.terminal.main import run_terminal
from app.terminal.session import Stage1Session
from game.scheduling.weekly import WeeklyDraft, local_departure, monday
from game.scheduling.timing import timing_bounds, flight_reservation
from game.scheduling.publication import publish_occurrences_through, revise_future_schedule, create_schedule_definition
from game.simulation import process_events_through, process_next_event
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.planning_reference import planning_snapshot
from game.world_state.planning_validation import validate_timing
from game.world_state.timestamps import parse_canonical_utc, format_utc


def encoded(world):
    return json.dumps(world, sort_keys=True, separators=(',', ':'))


class WeeklyPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='A', airline_display_name='B', base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base)
        state = self.world['world_state']
        self.airline = state['player']['primary_airline_id']
        self.aircraft = next(iter(state['aircraft']))
        self.airports = {r['reference_code']: k for k, r in state['airports'].items()}
        self.draft = self.new_draft()

    def new_draft(self):
        return WeeklyDraft(self.world, airline_id=self.airline, aircraft_id=self.aircraft)

    def add(self, origin='MNL', destination='CEB', departure='2026-09-07T00:00:00Z', **kwargs):
        return self.draft.add(self.airports[origin], self.airports[destination],
                              departure_utc=departure, **kwargs)

    def round_trip(self, departure='2026-09-07T00:00:00Z'):
        self.add(departure=departure, fare_minor=10000)
        self.draft.add_return()

    def test_dependency_bounds_use_critical_path_not_sum(self):
        snapshot = planning_snapshot(self.world['world_state'], self.aircraft,
                                     self.airports['MNL'], self.airports['CEB'])
        self.assertEqual(snapshot['cruise_speed_kph'], 840)
        self.assertEqual(snapshot['max_speed_kph'], 890)
        self.assertEqual(snapshot['distance_m'], 566982)
        self.assertEqual(timing_bounds(snapshot), ((2220, 3300, 600), (4200, 4500, 1200)))
        snapshot['activities']['baggage_loading'] = [5000, 6000]
        self.assertEqual(timing_bounds(snapshot)[1][0], 6900)

    def test_snapshot_is_independent_of_decimal_context(self):
        from decimal import localcontext, ROUND_DOWN
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_DOWN
            snapshot = planning_snapshot(self.world['world_state'],self.aircraft,
                                         self.airports['MNL'],self.airports['CEB'])
        self.assertEqual(snapshot['distance_m'],566982)

    def test_draft_one_way_has_no_live_mutation_or_implicit_return(self):
        before = encoded(self.world)
        self.add()
        self.assertEqual(len(self.draft.legs), 1)
        self.assertEqual(encoded(self.world), before)
        self.assertEqual(self.draft.last_stop, self.airports['CEB'])
        detached = self.draft.legs
        detached[0]['fare_minor'] = 999
        self.assertEqual(self.draft.legs[0]['fare_minor'], 0)
        self.draft.save(self.world)
        self.assertEqual(len(self.world['world_state']['dated_flights']), 1)

    def test_earliest_return_counts_post_and_pre_work(self):
        self.round_trip()
        self.assertEqual(self.draft.legs[1]['departure_utc'], '2026-09-07T02:45:00Z')
        self.draft.save(self.world)
        flights = sorted(self.world['world_state']['dated_flights'].values(), key=lambda f: f['scheduled_off_block_utc'])
        self.assertEqual(flight_reservation(self.world['world_state'], flights[0])[1],
                         flight_reservation(self.world['world_state'], flights[1])[0])

    def test_continuous_chain_can_end_away_from_base(self):
        self.add()
        for origin, destination in [('CEB','DVO'), ('DVO','MNL'), ('MNL','DVO'), ('DVO','CEB')]:
            self.draft.add(self.airports[origin], self.airports[destination])
        self.draft.save(self.world)
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertEqual(len(self.world['world_state']['dated_flights']), 5)

    def test_copy_selected_days_and_repeat_two_weeks(self):
        self.round_trip()
        self.draft.copy_day('2026-09-07','2026-09-09')
        self.draft.copy_day('2026-09-07','2026-09-11')
        self.draft.save(self.world, repeat_until='2026-09-20')
        flights = self.world['world_state']['dated_flights']
        self.assertEqual(len(flights), 12)
        self.assertEqual(sorted({f['scheduled_departure_local_date'] for f in flights.values()}),
                         ['2026-09-07','2026-09-09','2026-09-11','2026-09-14','2026-09-16','2026-09-18'])

    def test_repeat_boundary_discontinuity_is_atomic(self):
        self.add()
        before = encoded(self.world)
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            self.draft.save(self.world, repeat_until='2026-09-14')
        self.assertEqual(encoded(self.world), before)
        self.assertEqual(len(self.draft.legs), 1)

    def test_repeat_publication_and_json_roundtrip_preserve_bytes(self):
        self.round_trip()
        self.draft.save(self.world, repeat_until='2026-09-20')
        before = encoded(self.world)
        result = publish_occurrences_through(self.world, '2026-09-20T15:59:59Z')
        self.assertTrue(result.succeeded)
        self.assertFalse(result.created_dated_flight_ids)
        self.assertEqual(encoded(self.world), before)
        self.assertTrue(validate_world(json.loads(before)).is_valid)

    def test_add_second_pattern_reports_global_publication_correctly(self):
        self.round_trip()
        self.draft.save(self.world, repeat_until='2026-09-14')
        self.draft = self.new_draft()
        self.round_trip('2026-09-08T00:00:00Z')
        self.draft.save(self.world)
        self.assertEqual(len(self.world['world_state']['dated_flights']), 6)

    def test_ground_overlap_one_second_below_rejects_without_mutation(self):
        self.add()
        before = self.draft.legs
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.add('CEB','MNL','2026-09-07T02:44:59Z')
        self.assertEqual(self.draft.legs, before)

    def test_past_preparation_invalid_fare_and_same_endpoint_reject(self):
        for kwargs in ({'departure':'2026-09-01T00:00:00Z'}, {'fare_minor':True},
                       {'fare_minor':-1}, {'destination':'MNL'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.add(**kwargs)
        self.assertEqual(self.draft.legs, [])
        self.assertEqual(self.world, self.base)

    def test_week_start_local_midnight_and_overnight_block(self):
        from datetime import date
        self.assertEqual(monday(date(2026,9,9)), date(2026,9,7))
        departure = local_departure(self.world['world_state'], self.airports['MNL'], '2026-09-07','00:10')
        self.assertEqual(format_utc(departure), '2026-09-06T16:10:00Z')
        self.add(departure=format_utc(departure))
        self.assertEqual(len(self.draft.week_rows('2026-08-31')), 1)
        self.assertEqual(len(self.draft.week_rows('2026-09-07')), 1)

    def test_horizon_limit_and_invalid_repeat_end_are_atomic(self):
        with self.assertRaises(ValueError):
            self.add(departure='2026-12-01T00:00:00Z')
        self.round_trip()
        for end in ('2026-09-01','bad','2026-12-31'):
            with self.assertRaises(ValueError):
                self.draft.save(self.world, repeat_until=end)
            self.assertEqual(self.world, self.base)

    def test_stale_draft_rejects(self):
        self.add()
        process_events_through(self.world, '2026-09-01T00:01:00Z')
        before = encoded(self.world)
        with self.assertRaisesRegex(ValueError, 'STALE_DRAFT'):
            self.draft.save(self.world)
        self.assertEqual(encoded(self.world), before)

    def test_allocator_failure_rolls_back_and_retry_matches(self):
        self.round_trip()
        before = encoded(self.world)
        with patch('game.scheduling.publication.allocate_id', side_effect=ValueError('injected')):
            with self.assertRaises(ValueError):
                self.draft.save(self.world)
        self.assertEqual(encoded(self.world), before)
        self.draft.save(self.world)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_snapshot_validation_rejects_bad_ranges_and_duration(self):
        self.round_trip()
        self.draft.save(self.world)
        for value in ([1,0],[True,3],[0,86401],None):
            damaged = deepcopy(self.world)
            revision = next(iter(damaged['world_state']['schedule_definitions'].values()))['revisions']['1']
            revision['planning_timing']['taxi_in_seconds'] = value
            self.assertFalse(validate_world(damaged).is_valid)
        damaged = deepcopy(self.world)
        revision = next(iter(damaged['world_state']['schedule_definitions'].values()))['revisions']['1']
        revision['planning_timing']['cruise_speed_kph'] = 400
        self.assertFalse(validate_world(damaged).is_valid)

    def test_reference_changes_do_not_recalculate_published_history(self):
        self.round_trip()
        self.draft.save(self.world)
        before = encoded(self.world)
        with patch('game.world_state.planning_reference._PATH') as path:
            path.read_text.side_effect = AssertionError('must not load profile')
            self.assertTrue(validate_world(self.world).is_valid)
            self.assertTrue(publish_occurrences_through(self.world, '2026-09-08T00:00:00Z').succeeded)
        self.assertEqual(encoded(self.world), before)

    def test_deadhead_requires_explicit_action_and_operates_without_booking(self):
        with self.assertRaisesRegex(ValueError,'REPOSITIONING_REQUIRED'):
            self.draft.earliest(self.airports['CEB'],self.airports['DVO'])
        self.add(departure='2026-09-01T02:00:00Z',deadhead=True)
        self.draft.save(self.world)
        result = process_events_through(self.world,'2026-09-01T06:00:00Z')
        self.assertTrue(result.succeeded, result.failure)
        flight = next(iter(self.world['world_state']['dated_flights'].values()))
        self.assertEqual(flight['status'],'COMPLETED')
        self.assertEqual(flight['capacity'],0)
        self.assertEqual(self.world['world_state']['bookings'],{})
        self.assertEqual(self.world['world_state']['aircraft'][self.aircraft]['current_airport_id'],self.airports['CEB'])
        from game.aircraft_operations import project_recent_flight_results
        finance = project_recent_flight_results(self.world,self.airline)
        self.assertEqual(finance['cumulative_revenue_minor'],0)
        self.assertGreater(finance['cumulative_cost_minor'],0)
        before = encoded(self.world)
        self.assertTrue(process_events_through(self.world,'2026-09-01T06:00:00Z').succeeded)
        self.assertEqual(encoded(self.world),before)

    def test_stepping_equals_through_target(self):
        self.round_trip('2026-09-01T02:00:00Z')
        self.draft.save(self.world)
        other = deepcopy(self.world)
        target = '2026-09-01T08:00:00Z'
        self.assertTrue(process_events_through(self.world,target).succeeded)
        while min(e['due_at_utc'] for e in other['world_state']['pending_events'].values()) <= target:
            self.assertTrue(process_next_event(other).succeeded)
        self.assertTrue(process_events_through(other,target).succeeded)
        self.assertEqual(encoded(other),encoded(self.world))

    def test_completed_work_reserves_post_arrival_for_new_draft(self):
        self.add(departure='2026-09-01T02:00:00Z')
        self.draft.save(self.world)
        self.assertTrue(process_events_through(self.world,'2026-09-01T03:15:00Z').succeeded)
        draft = self.new_draft()
        self.assertEqual(draft.earliest(self.airports['CEB'],self.airports['MNL']), '2026-09-01T04:45:00Z')

    def test_week_view_and_copy_rejection_are_detached(self):
        self.round_trip()
        before = self.draft.legs
        rows = self.draft.week_rows('2026-09-07')
        rows.clear()
        with self.assertRaises(ValueError):
            self.draft.copy_day('2026-09-07','2026-09-07')
        self.assertEqual(self.draft.legs,before)
        self.assertEqual(self.world,self.base)

    def test_publication_rejects_past_preparation_at_lower_boundary(self):
        self.round_trip('2026-09-01T02:00:00Z')
        self.draft.save(self.world)
        # Retain canonical definitions but reconstruct an unpublished candidate.
        fresh = deepcopy(self.base)
        from game.scheduling.rotation import _connection
        connection = _connection(fresh,self.airline,self.airports['MNL'],self.airports['CEB'])
        snapshot = planning_snapshot(fresh['world_state'],self.aircraft,self.airports['MNL'],self.airports['CEB'])
        created = create_schedule_definition(fresh,airline_id=self.airline,connection_id=connection,
            planned_aircraft_id=self.aircraft,origin_airport_id=self.airports['MNL'],
            destination_airport_id=self.airports['CEB'],weekdays=[1],
            departure_local_time='08:30:00',arrival_local_time='09:45:00',
            effective_from_local_date='2026-09-01',until_local_date='2026-09-01',
            planning_timing=snapshot,capacity=180,fare_offer={'currency':'USD','amount_minor':0})
        self.assertTrue(created.succeeded)
        before = encoded(fresh)
        rejected = publish_occurrences_through(fresh,'2026-09-01T01:00:00Z')
        self.assertFalse(rejected.succeeded)
        self.assertEqual(rejected.conflicts[0].code,'PAST_PREPARATION')
        self.assertEqual(encoded(fresh),before)

    def test_new_draft_suggests_gap_before_existing_service(self):
        self.round_trip()
        self.draft.save(self.world,repeat_until='2026-09-21')
        draft = self.new_draft()
        self.assertEqual(draft.earliest(self.airports['MNL'],self.airports['DVO']),
                         '2026-09-01T01:10:00Z')

    def test_unpublished_recurrence_is_visible_and_blocks_conflicts(self):
        from game.scheduling.rotation import create_weekly_round_trip_rotation
        result = create_weekly_round_trip_rotation(self.world,airline_id=self.airline,
            aircraft_id=self.aircraft,destination_airport_reference_code='CEB',fare_minor=0,
            first_operating_date='2026-09-07')
        self.assertTrue(result.succeeded)
        draft = self.new_draft()
        self.assertEqual(len(draft.week_rows('2026-09-14')),2)
        with self.assertRaisesRegex(ValueError,'overlap'):
            draft.add(self.airports['MNL'],self.airports['DVO'],departure_utc='2026-09-14T00:00:00Z')

    def test_dictionary_order_does_not_change_saved_authority(self):
        other = deepcopy(self.world)
        for name in ('airports','directional_markets','aircraft','airlines'):
            other['world_state'][name] = dict(reversed(list(other['world_state'][name].items())))
        second = WeeklyDraft(other,airline_id=self.airline,aircraft_id=self.aircraft)
        self.round_trip()
        second.add(self.airports['MNL'],self.airports['CEB'],departure_utc='2026-09-07T00:00:00Z',fare_minor=10000)
        second.add_return()
        self.draft.save(self.world)
        second.save(other)
        self.assertEqual(encoded(self.world),encoded(other))

    def test_save_checks_unpublished_future_chain_without_extending_publication(self):
        from game.scheduling.rotation import create_weekly_round_trip_rotation
        result = create_weekly_round_trip_rotation(self.world, airline_id=self.airline,
            aircraft_id=self.aircraft, destination_airport_reference_code='CEB',
            fare_minor=0, first_operating_date='2026-09-07')
        self.assertTrue(result.succeeded)
        self.draft = self.new_draft()
        self.add(destination='DVO', departure='2026-09-08T00:00:00Z')
        before, legs = encoded(self.world), self.draft.legs
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            self.draft.save(self.world)
        self.assertEqual(encoded(self.world), before)
        self.assertEqual(self.draft.legs, legs)
        self.draft.add_return()
        self.draft.save(self.world)
        self.assertEqual(len(self.world['world_state']['dated_flights']), 4)
        self.assertTrue(publish_occurrences_through(
            self.world, '2026-09-14T23:00:00Z').succeeded)

    def test_occurrences_obey_retained_revision_inclusive_end_date(self):
        self.round_trip()
        self.draft.save(self.world, repeat_until='2026-09-14')
        before = encoded(self.world)
        self.assertTrue(validate_world(self.world).is_valid)
        damaged = deepcopy(self.world)
        for schedule in damaged['world_state']['schedule_definitions'].values():
            schedule['revisions']['1']['recurrence']['until_local_date'] = '2026-09-07'
        result = validate_world(damaged)
        self.assertFalse(result.is_valid)
        self.assertTrue(any('recurrence end date' in error.message for error in result.errors))
        self.assertEqual(encoded(self.world), before)

    def test_copy_day_reference_failure_after_first_leg_preserves_draft(self):
        from game.world_state import planning_reference
        self.round_trip()
        before, legs = encoded(self.world), self.draft.legs
        profile = json.loads(planning_reference._PATH.read_text(encoding='utf-8'))
        catalog_id = self.world['world_state']['airports'][self.airports['MNL']]['catalog_airport_id']
        del profile['airports'][catalog_id]['taxi_in_seconds']
        with patch.object(planning_reference, '_PATH') as path:
            path.read_text.return_value = json.dumps(profile)
            with self.assertRaises(KeyError):
                self.draft.copy_day('2026-09-07', '2026-09-10')
            self.assertEqual(path.read_text.call_count, 2)
        self.assertEqual(self.draft.legs, legs)
        self.assertEqual(encoded(self.world), before)
        self.draft.copy_day('2026-09-07', '2026-09-10')
        self.assertEqual(len(self.draft.legs), 4)

    def test_booked_and_completed_history_survives_new_plan(self):
        self.round_trip()
        self.draft.save(self.world,repeat_until='2026-09-20')
        self.assertTrue(process_events_through(self.world,'2026-09-07T00:00:00Z').succeeded)
        world = self.world['world_state']
        self.assertTrue(world['bookings'])
        schedule = list(world['schedule_definitions'].values())[1]
        before = encoded(self.world)
        rejected = revise_future_schedule(self.world,schedule['schedule_id'],
            effective_from_local_date='2026-09-14',expected_revision=1,
            departure_local_time='13:00:00',arrival_local_time='14:15:00')
        self.assertFalse(rejected.succeeded)
        self.assertEqual(rejected.conflicts[0].code,'BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW')
        self.assertEqual(encoded(self.world),before)
        self.assertTrue(process_events_through(self.world,'2026-09-07T08:00:00Z').succeeded)
        # The commit boundary replaces mappings: read retained live history afresh.
        history = deepcopy(self.world['world_state']['bookings'])
        old_flights = deepcopy(self.world['world_state']['dated_flights'])
        self.draft = self.new_draft()
        self.round_trip('2026-09-08T00:00:00Z')
        self.draft.save(self.world)
        self.assertEqual(self.world['world_state']['bookings'],history)
        for key,value in old_flights.items():
            self.assertEqual(self.world['world_state']['dated_flights'][key],value)

    def test_terminal_cancel_keeps_world_and_dirty_state(self):
        session = Stage1Session()
        session.world = deepcopy(self.base)
        session.new_game = lambda *args: None
        session.changed = False
        before = encoded(session.world)
        output = StringIO()
        script = '\n'.join(['1','A','B','26','3','1','1','MNL','CEB','y','100','n','0','0','y',''])
        run_terminal(StringIO(script),output,session_factory=lambda:session)
        self.assertIn('Draft cancelled',output.getvalue())
        self.assertEqual(encoded(session.world),before)
        self.assertFalse(session.changed)

    def test_terminal_planner_script_and_cancel(self):
        session = Stage1Session()
        session.world = deepcopy(self.base)
        # Outer menu starts with New Game; inject a preconstructed session via new_game.
        session.new_game = lambda *args: None
        script = '\n'.join(['1','A','B','26','3','1','2','1','MNL','CEB','y','100','n','6','n','y','0','y',''])
        output = StringIO()
        run_terminal(StringIO(script), output, session_factory=lambda:session)
        self.assertIn('Week of Monday 2026-09-07',output.getvalue())
        self.assertIn('Published 1 flights',output.getvalue())
        self.assertEqual(len(session.world['world_state']['dated_flights']),1)


if __name__ == '__main__':
    unittest.main()
