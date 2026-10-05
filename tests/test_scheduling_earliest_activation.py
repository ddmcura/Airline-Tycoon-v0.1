"""Earliest uses operational authority, not elapsed weekly-pattern movement."""

from copy import deepcopy
import unittest

from game.scheduling import WeeklyDraft
from game.scheduling.local_time import local_departure
from game.scheduling.timing import timing_bounds
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import format_utc


class EarliestActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='CEO', airline_display_name='Earliest',
            base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base)
        state = self.world['world_state']
        self.ports = {row['reference_code']: key for key, row in state['airports'].items()}
        self.draft = WeeklyDraft(self.world, airline_id=state['player']['primary_airline_id'],
                                 aircraft_id=next(iter(state['aircraft'])))

    def prefix(self):
        self.draft.add_weekdays(self.ports['MNL'], self.ports['CEB'], ['2026-09-01'], '06:00')

    def earliest(self, origin='MNL', destination='DVO', floor='2026-09-01T00:00:00Z'):
        return self.draft.earliest(self.ports[origin], self.ports[destination], not_before=floor)

    def test_inert_prefix_cannot_supply_location_single_insert(self):
        self.prefix()
        before = deepcopy(self.world)
        self.assertEqual(self.draft.projected_location, self.ports['MNL'])
        self.assertEqual(self.earliest(), '2026-09-01T00:30:00Z')
        self.draft.add(self.ports['MNL'], self.ports['DVO'], departure_utc=self.earliest())
        self.draft.save_current(self.world)
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertEqual(len(self.world['world_state']['dated_flights']), 1)
        for key in ('aircraft', 'bookings', 'itineraries', 'flight_results', 'transactions', 'event_history'):
            self.assertEqual(self.world['world_state'][key], before['world_state'][key])
        self.assertTrue(all(row['service_type'] == 'PASSENGER'
                            for row in self.world['world_state']['dated_flights'].values()))

    def test_midnight_lower_bound_is_not_an_inert_departure(self):
        self.prefix()
        self.assertEqual(self.earliest(floor='2026-08-31T16:00:00Z'), '2026-09-01T00:30:00Z')

    def test_manual_and_earliest_produce_identical_authority(self):
        self.prefix()
        manual = deepcopy(self.draft)
        earliest_world = deepcopy(self.world)
        self.draft.add_weekdays(self.ports['MNL'], self.ports['DVO'], ['2026-09-01'],
                                '08:00', earliest=True)
        manual.add_weekdays(self.ports['MNL'], self.ports['DVO'], ['2026-09-01'], '08:30')
        self.assertEqual(self.draft.legs, manual.legs)
        self.draft.save_current(earliest_world)
        manual.save_current(self.world)
        self.assertEqual(earliest_world, self.world)

    def test_multi_day_with_returns_uses_actual_position_and_is_atomic(self):
        self.prefix()
        self.assertEqual(self.draft.add_weekdays(self.ports['MNL'], self.ports['DVO'],
                         ['2026-09-01', '2026-09-02'], '00:00', earliest=True,
                         return_flight=True), 4)
        self.assertEqual([leg['departure_utc'] for leg in self.draft.legs[1:]], [
            '2026-09-01T00:30:00Z', '2026-09-01T02:40:00Z',
            '2026-09-01T16:00:00Z', '2026-09-01T18:10:00Z'])
        before = self.draft.legs
        with self.assertRaises(ValueError):
            self.draft.add_weekdays(self.ports['CEB'], self.ports['DVO'],
                                   ['2026-09-01', '2026-09-02'], '08:00', earliest=True)
        self.assertEqual(self.draft.legs, before)
        self.draft.save_current(self.world)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_genuinely_incompatible_origin_is_not_invented_or_skipped(self):
        self.prefix()
        before = self.draft.legs
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            self.earliest('CEB', 'DVO')
        self.assertEqual(self.draft.legs, before)

    def test_insertion_rechecks_activation_of_later_prefix(self):
        self.prefix()
        self.draft.add_weekdays(self.ports['CEB'], self.ports['DVO'], ['2026-09-01'], '08:30')
        self.draft.add_weekdays(self.ports['DVO'], self.ports['MNL'], ['2026-09-01'], '11:00')
        # At equality the new leg activates before the incompatible CEB leg.
        bad = deepcopy(self.draft)
        bad.add(self.ports['MNL'], self.ports['DVO'], departure_utc='2026-09-01T00:30:00Z')
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            bad.save_current(deepcopy(self.world))
        self.assertEqual(self.earliest(), '2026-09-01T00:30:01Z')
        self.draft.add(self.ports['MNL'], self.ports['DVO'], departure_utc=self.earliest())
        self.draft.save_current(self.world)
        self.assertTrue(validate_world(self.world).is_valid)
        flights = self.world['world_state']['dated_flights'].values()
        self.assertEqual(len(flights), 2)
        self.assertTrue(all(row['service_type'] == 'PASSENGER' for row in flights))

    def test_exact_preparation_and_turnaround_boundary(self):
        self.draft.add(self.ports['MNL'], self.ports['DVO'], departure_utc='2026-09-01T00:30:00Z')
        self.assertEqual(timing_bounds(self.draft.legs[0]['planning_timing'])[1], (1800, 6000, 0))
        self.assertEqual(self.earliest('DVO', 'MNL'), '2026-09-01T02:40:00Z')
        self.draft.add(self.ports['DVO'], self.ports['MNL'], departure_utc=self.earliest('DVO', 'MNL'))
        self.draft.save_current(self.world)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_seconds_are_preserved_without_gui_minute_rounding(self):
        self.prefix()
        self.draft.add(self.ports['MNL'], self.ports['DVO'], departure_utc='2026-09-01T00:30:01Z')
        returned = self.earliest('DVO', 'MNL')
        self.assertEqual(returned, '2026-09-01T02:40:01Z')
        exact = format_utc(local_departure(self.world['world_state'], self.ports['DVO'],
                                          '2026-09-01', '10:40:01'))
        self.assertEqual(returned, exact)
        with self.assertRaisesRegex(ValueError, 'overlap|turnaround'):
            self.draft.add(self.ports['DVO'], self.ports['MNL'], departure_utc='2026-09-01T02:40:00Z')
        self.draft.add(self.ports['DVO'], self.ports['MNL'], departure_utc=returned)
        self.draft.save_current(self.world)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_earliest_query_does_not_mutate_draft_world_or_undo(self):
        self.prefix()
        before = deepcopy(self.draft.__dict__)
        self.earliest()
        self.assertEqual(self.draft.__dict__, before)


if __name__ == '__main__':
    unittest.main()
