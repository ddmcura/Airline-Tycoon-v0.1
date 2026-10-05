"""Initial partial week is intent until the first feasible real occurrence."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from game.scheduling import WeeklyDraft
from game.scheduling import publication
from game.scheduling.recurrence import publish_rolling_window
from game.scheduling.activation import initial_week_end
from game.simulation import process_events_through
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import parse_canonical_utc


PATTERN = (('MNL', 'CEB', '06:00'), ('CEB', 'DVO', '08:30'),
           ('DVO', 'MNL', '11:00'), ('MNL', 'DVO', '14:00'),
           ('DVO', 'MNL', '16:30'))


class InitialActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='CEO', airline_display_name='Partial Week',
            base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base)
        state = self.world['world_state']
        self.owner = state['player']['primary_airline_id']
        self.aircraft = next(iter(state['aircraft']))
        self.ports = {row['reference_code']: key for key, row in state['airports'].items()}
        self.draft = self.new_draft()

    def new_draft(self):
        return WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)

    def build(self, day='2026-09-01'):
        for origin, destination, departure in PATTERN:
            self.draft.add_weekdays(self.ports[origin], self.ports[destination],
                                   [day], departure, fare_minor=11600)

    def flights(self, day):
        return sorted((flight for flight in self.world['world_state']['dated_flights'].values()
                       if flight['scheduled_departure_local_date'] == day),
                      key=lambda row: row['scheduled_off_block_utc'])

    def test_inert_prefix_and_future_incompatible_slots_do_not_move_aircraft(self):
        before = deepcopy(self.world)
        self.build()
        self.assertEqual(self.world, before)
        self.draft.save_current(self.world, continuous=True)
        state = self.world['world_state']
        self.assertEqual(len(self.flights('2026-09-01')), 2)
        self.assertEqual(self.flights('2026-09-01')[0]['origin_airport_id'], self.ports['MNL'])
        self.assertEqual(self.flights('2026-09-01')[0]['scheduled_off_block_utc'], '2026-09-01T06:00:00Z')
        for field in ('aircraft', 'bookings', 'itineraries', 'flight_results',
                      'active_aircraft_operations', 'transactions', 'event_history'):
            self.assertEqual(state[field], before['world_state'][field])
        for field in ('world_seed', 'streams'):
            self.assertEqual(self.world['deterministic_state'][field], before['deterministic_state'][field])
        self.assertTrue(all(flight['service_type'] == 'PASSENGER' for flight in state['dated_flights'].values()))
        self.assertTrue(all(event['due_at_utc'] >= self.world['simulation']['time_utc']
                            for event in state['pending_events'].values()))
        self.assertTrue(validate_world(self.world).is_valid)

    def test_full_next_week_and_idempotence_preserve_complete_pattern(self):
        self.build()
        self.draft.save_current(self.world, continuous=True)
        self.assertEqual(len(self.flights('2026-09-08')), 5)
        self.assertEqual([row['origin_airport_id'] for row in self.flights('2026-09-08')],
                         [self.ports[origin] for origin, _, _ in PATTERN])
        before = deepcopy(self.world)
        self.assertEqual(publish_rolling_window(self.world, self.owner).created_dated_flight_ids, ())
        self.assertEqual(self.world, before)
        result = process_events_through(self.world, '2026-09-01T11:00:00Z')
        self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(len(self.world['world_state']['flight_results']), 2)
        self.assertEqual(self.world['world_state']['aircraft'][self.aircraft]['current_airport_id'], self.ports['MNL'])
        result = process_events_through(self.world, '2026-09-08T11:00:00Z')
        self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(len(self.world['world_state']['flight_results']), 7)

    def test_past_slot_still_in_air_does_not_supply_projected_location(self):
        self.draft.add_weekdays(self.ports['MNL'], self.ports['CEB'], ['2026-09-01'], '07:30')
        self.draft.add_weekdays(self.ports['MNL'], self.ports['DVO'], ['2026-09-01'], '09:30', return_flight=True)
        self.draft.save_current(self.world)
        self.assertEqual(len(self.flights('2026-09-01')), 2)
        self.assertEqual(self.flights('2026-09-01')[0]['origin_airport_id'], self.ports['MNL'])

    def test_departure_now_with_elapsed_preparation_terminates_and_stays_inert(self):
        count = [0]
        original = publication._occurrence_record
        def bounded(*args, **kwargs):
            count[0] += 1
            self.assertLess(count[0], 100, 'recurrence cursor failed to advance')
            return original(*args, **kwargs)
        with patch.object(publication, '_occurrence_record', bounded):
            self.draft.add_weekdays(self.ports['MNL'], self.ports['DVO'], ['2026-09-01'],
                                    '08:00', return_flight=True)
            self.draft.save_current(self.world)
        self.assertEqual(self.world['world_state']['dated_flights'], {})
        self.assertLess(count[0], 100)

    def test_location_and_turnaround_strict_after_activation_and_undo_atomic(self):
        self.build()
        before = self.draft.legs
        for origin, destination, departure, message in (
            ('CEB', 'MNL', '19:00', 'REPOSITIONING_INFEASIBLE'),
            ('DVO', 'MNL', '15:45', 'overlap|TURNAROUND')):
            with self.assertRaisesRegex(ValueError, message):
                self.draft.add_weekdays(self.ports[origin], self.ports[destination],
                                       ['2026-09-01'], departure)
            self.assertEqual(self.draft.legs, before)
        self.draft.undo()
        self.assertEqual(len(self.draft.legs), 4)

    def test_first_feasible_movement_does_not_permit_later_prefix_skips(self):
        self.build()
        legs = self.draft.legs
        # Corrupt a later proposed origin while retaining valid timing/schema:
        # publication must reject rather than skipping after initial activation.
        leg = deepcopy(legs[-1])
        leg['origin_airport_id'] = self.ports['CEB']
        leg['planning_timing'] = self.draft._snapshot(self.ports['CEB'], self.ports['MNL'])
        legs[-1] = leg
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            self.draft._candidate(legs)
        self.assertEqual(self.world, self.base)

    def test_no_elapsed_pattern_does_not_allow_impossible_first_future_origin_skip(self):
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_INFEASIBLE'):
            self.draft.add_weekdays(self.ports['CEB'], self.ports['DVO'], ['2026-09-01'], '09:00')
        self.assertEqual(self.draft.legs, [])

    def test_complete_future_week_allows_feasible_planning_but_never_publication_skip(self):
        self.draft.add_weekdays(self.ports['MNL'], self.ports['CEB'], ['2026-09-01'], '06:00')
        self.draft.add_weekdays(self.ports['CEB'], self.ports['DVO'], ['2026-09-07'], '08:30')
        before = deepcopy(self.world)
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            self.draft.save_current(self.world)
        self.assertEqual(self.world, before)

    def test_monday_eight_am_activation_and_next_monday(self):
        result = process_events_through(self.world, '2026-09-07T00:00:00Z')
        self.assertTrue(result.succeeded, result.failure)
        self.draft = self.new_draft()
        self.build('2026-09-07')
        self.draft.save_current(self.world, continuous=True)
        self.assertEqual(len(self.flights('2026-09-07')), 2)
        self.assertEqual(len(self.flights('2026-09-14')), 5)

    def test_materialized_activation_remains_strict_after_time_advances(self):
        self.build()
        self.draft.save_current(self.world, continuous=True)
        self.assertTrue(process_events_through(self.world, '2026-09-02T00:00:00Z').succeeded)
        before = deepcopy(self.world)
        self.assertEqual(publish_rolling_window(self.world, self.owner).created_dated_flight_ids, ())
        self.assertEqual(self.world, before)

    def test_initial_activation_uses_real_airborne_arrival_and_availability(self):
        self.draft.add_weekdays(self.ports['MNL'], self.ports['DVO'], ['2026-09-07'], '08:00')
        self.draft.save_current(self.world)
        # Existing manual operation is not an already-activated rolling pattern.
        # Its actual position/reservation must still govern the new pattern.
        for definition in self.world['world_state']['schedule_definitions'].values():
            definition['revisions']['1']['recurrence'].pop('publication_policy')
        self.assertTrue(process_events_through(self.world, '2026-09-07T00:30:00Z').succeeded)
        self.assertEqual(self.world['world_state']['aircraft'][self.aircraft]['status'], 'IN_FLIGHT')
        self.draft = self.new_draft()
        self.draft.add_weekdays(self.ports['MNL'], self.ports['CEB'], ['2026-09-07'], '06:00')
        # Right projected origin, but preparation overlaps the REAL outbound.
        self.draft.add_weekdays(self.ports['DVO'], self.ports['CEB'], ['2026-09-07'], '10:00')
        self.draft.add_weekdays(self.ports['DVO'], self.ports['CEB'], ['2026-09-07'], '11:00')
        self.draft.save_current(self.world)
        new = [flight for flight in self.flights('2026-09-07')
               if flight['origin_airport_id'] == self.ports['DVO']]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]['scheduled_off_block_utc'], '2026-09-07T03:00:00Z')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_midnight_preparation_before_monday_still_counts_as_current_week(self):
        self.assertTrue(process_events_through(self.world, '2026-09-07T00:00:00Z').succeeded)
        start = parse_canonical_utc('2026-09-06T15:30:00Z')  # Sun 23:30 PH
        departure = parse_canonical_utc('2026-09-06T16:00:00Z')  # Mon 00:00 PH
        end = initial_week_end(self.world, self.aircraft, [(start, departure)])
        self.assertEqual(end.isoformat(), '2026-09-14T00:00:00+08:00')

    def test_realistic_builder_expansion_is_bounded(self):
        calls = [0]
        original = publication._occurrence_record
        def bounded(*args, **kwargs):
            calls[0] += 1
            self.assertLess(calls[0], 300, 'pathological partial-week re-expansion')
            return original(*args, **kwargs)
        with patch.object(publication, '_occurrence_record', bounded):
            self.build()
            self.draft.save_current(self.world, continuous=True)
        self.assertEqual(len(self.world['world_state']['dated_flights']), 22)
        self.assertLess(calls[0], 300)


if __name__ == '__main__':
    unittest.main()
