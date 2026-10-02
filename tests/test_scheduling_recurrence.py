"""Airport-local pattern intent, bounded recurrence, and protected future revisions."""

from copy import deepcopy
from datetime import date, timedelta
import tempfile
import unittest

from app.session import Stage1Session
from game.scheduling import WeeklyDraft
from game.scheduling.local_time import local_departure
from game.scheduling.publication import _expand_schedule
from game.scheduling.recurrence import EVENT_TYPE, POLICY, publish_rolling_window, rolling_horizon
from game.simulation import process_events_through
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc


class RecurringSchedulingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='CEO', airline_display_name='Pattern Air', base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base)
        world = self.world['world_state']
        self.airline = world['player']['primary_airline_id']
        self.aircraft = next(iter(world['aircraft']))
        self.airports = {row['reference_code']: key for key, row in world['airports'].items()}

    def draft(self):
        return WeeklyDraft(self.world, airline_id=self.airline, aircraft_id=self.aircraft)

    def pair(self, draft=None, dates=('2026-08-31',)):
        draft = draft or self.draft()
        draft.add_weekdays(self.airports['MNL'], self.airports['DVO'], dates,
                           '08:00', return_flight=True, fare_minor=11600)
        return draft

    def advance(self, target):
        result = process_events_through(self.world, target)
        self.assertTrue(result.succeeded, result.failure)
        return result

    def dates(self):
        return sorted({row['scheduled_departure_local_date']
                       for row in self.world['world_state']['dated_flights'].values()})

    def test_elapsed_pattern_is_inert_and_future_slots_operate(self):
        draft = self.pair(dates=('2026-08-31', '2026-09-02'))
        self.assertEqual(self.world, self.base)
        rows = draft.week_rows('2026-08-31')
        self.assertEqual(sum(row['pattern_only'] for row in rows), 2)
        result = draft.save_current(self.world)
        self.assertEqual(len(result.created_dated_flight_ids), 2)
        self.assertEqual(self.dates(), ['2026-09-02'])
        state = self.world['world_state']
        for field in ('bookings', 'flight_results', 'active_aircraft_operations', 'transactions', 'event_history'):
            self.assertEqual(state[field], self.base['world_state'][field])
        self.assertEqual(state['aircraft'], self.base['world_state']['aircraft'])
        for key in ('world_seed', 'streams'):
            self.assertEqual(self.world['deterministic_state'][key], self.base['deterministic_state'][key])
        self.assertTrue(all(event['due_at_utc'] >= self.world['simulation']['time_utc']
                            for event in state['pending_events'].values()))
        self.advance('2026-09-02T04:00:00Z')
        self.assertEqual(len(self.world['world_state']['flight_results']), 2)
        self.assertFalse(any(row['scheduled_departure_local_date'] == '2026-08-31'
                             for row in self.world['world_state']['dated_flights'].values()))

    def test_this_week_only_past_pattern_publishes_zero_operations(self):
        result = self.pair().save_current(self.world)
        self.assertEqual(result.created_dated_flight_ids, ())
        state = self.world['world_state']
        for field in ('dated_flights', 'bookings', 'flight_results', 'active_aircraft_operations',
                      'transactions', 'event_history', 'pending_events', 'aircraft'):
            self.assertEqual(state[field], self.base['world_state'][field])
        self.assertTrue(state['schedule_definitions'])
        self.assertFalse(any(row['event_type'] == EVENT_TYPE for row in state['pending_events'].values()))

    def test_continuous_four_future_weeks_and_idempotent_publication(self):
        self.pair().save_current(self.world, continuous=True)
        self.assertEqual(self.dates(), ['2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28'])
        self.assertEqual(rolling_horizon(self.world, self.airline), '2026-10-04T15:59:59Z')
        before = deepcopy(self.world)
        result = publish_rolling_window(self.world, self.airline)
        self.assertEqual(result.created_dated_flight_ids, ())
        self.assertEqual(self.world, before)
        events = [row for row in self.world['world_state']['pending_events'].values()
                  if row['event_type'] == EVENT_TYPE]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['due_at_utc'], '2026-09-06T16:00:00Z')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_week_roll_extends_without_duplicate_occurrences(self):
        self.pair().save_current(self.world, continuous=True)
        self.advance('2026-09-06T16:00:00Z')
        self.assertEqual(self.dates(), ['2026-09-07', '2026-09-14', '2026-09-21', '2026-09-28', '2026-10-05'])
        state = self.world['world_state']
        keys = [row['occurrence_key'] for row in state['dated_flights'].values()]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 10)
        events = [row for row in state['pending_events'].values() if row['event_type'] == EVENT_TYPE]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['due_at_utc'], '2026-09-13T16:00:00Z')
        self.assertEqual(len(state['flight_results']), 0)

    def test_automatic_rollover_does_not_publish_legacy_manual_definitions(self):
        self.pair().save_current(self.world, continuous=True)
        # Convert this isolated fixture to legacy/manual policy, leaving its
        # already-published flights intact, then add a separate rolling pair.
        legacy_ids = set(self.world['world_state']['schedule_definitions'])
        for schedule in self.world['world_state']['schedule_definitions'].values():
            schedule['revisions']['1']['recurrence'].pop('publication_policy')
        for event_id, event in list(self.world['world_state']['pending_events'].items()):
            if event['event_type'] == EVENT_TYPE:
                del self.world['world_state']['pending_events'][event_id]
        self.pair(dates=('2026-09-02',)).save_current(self.world, continuous=True)
        original = {key: deepcopy(row) for key, row in self.world['world_state']['dated_flights'].items()
                    if row['schedule_id'] in legacy_ids}
        self.advance('2026-09-06T16:00:00Z')
        current = {key: deepcopy(row) for key, row in self.world['world_state']['dated_flights'].items()
                   if row['schedule_id'] in legacy_ids}
        # Booking checkpoints legitimately refresh demand allocations. Check
        # protected publication identity/timing rather than runtime projections.
        self.assertEqual(set(current), set(original))
        for key, flight in current.items():
            for field in ('dated_flight_id', 'occurrence_key', 'schedule_id', 'schedule_revision',
                          'origin_airport_id', 'destination_airport_id', 'planned_aircraft_id',
                          'scheduled_departure_local_date', 'scheduled_off_block_utc',
                          'scheduled_in_block_utc', 'capacity', 'fare_offer'):
                self.assertEqual(flight[field], original[key][field])
        self.assertTrue(validate_world(self.world).is_valid)

    def test_repeat_until_is_inclusive_and_bounded_even_for_distant_end(self):
        self.pair().save_current(self.world, repeat_until='2026-09-21')
        self.assertEqual(self.dates(), ['2026-09-07', '2026-09-14', '2026-09-21'])
        for schedule in self.world['world_state']['schedule_definitions'].values():
            recurrence = schedule['revisions']['1']['recurrence']
            self.assertEqual(recurrence['until_local_date'], '2026-09-21')
        self.world = deepcopy(self.base)
        self.pair().save_current(self.world, repeat_until='2028-09-21')
        self.assertEqual(len(self.world['world_state']['dated_flights']), 8)
        self.assertTrue(all(date.fromisoformat(value) <= date(2026, 10, 4) for value in self.dates()))

    def test_revision_first_unpublished_week_preserves_booked_flights(self):
        self.pair().save_current(self.world, continuous=True)
        self.advance('2026-09-02T00:00:00Z')
        self.assertTrue(self.world['world_state']['bookings'])
        before = deepcopy(self.world['world_state']['dated_flights'])
        bookings = deepcopy(self.world['world_state']['bookings'])
        draft = WeeklyDraft.edit_recurring(self.world, airline_id=self.airline, aircraft_id=self.aircraft)
        self.assertEqual(draft.revision_from, '2026-10-05')
        draft.reschedule(0, '2026-10-05', '07:50')
        result = draft.save_current(self.world, continuous=True)
        self.assertEqual(result.created_dated_flight_ids, ())
        self.assertEqual(self.world['world_state']['dated_flights'], before)
        self.assertEqual(self.world['world_state']['bookings'], bookings)
        self.assertTrue(all(schedule['current_revision'] == 2
                            for schedule in self.world['world_state']['schedule_definitions'].values()))
        self.advance('2026-09-06T16:00:00Z')
        flights = [row for row in self.world['world_state']['dated_flights'].values()
                   if row['scheduled_departure_local_date'] == '2026-10-05']
        self.assertEqual(len(flights), 2)
        self.assertTrue(all(row['schedule_revision'] == 2 for row in flights))
        self.assertEqual(min(row['scheduled_off_block_utc'] for row in flights), '2026-10-04T23:50:00Z')

    def test_remove_pattern_movement_stops_future_without_cancellation(self):
        self.pair().save_current(self.world, continuous=True)
        before = deepcopy(self.world['world_state']['dated_flights'])
        draft = WeeklyDraft.edit_recurring(self.world, airline_id=self.airline, aircraft_id=self.aircraft)
        draft.undo()  # Opening a pattern is not an undoable deletion.
        self.assertEqual(len(draft.legs), 2)
        self.assertEqual(draft.delete_selection([0, 1]), 2)
        draft.undo()
        self.assertEqual(len(draft.legs), 2)
        draft.delete_selection([0, 1])
        draft.save_current(self.world, continuous=True)
        self.assertEqual(self.world['world_state']['dated_flights'], before)
        for schedule in self.world['world_state']['schedule_definitions'].values():
            self.assertFalse(schedule['revisions']['2']['recurrence']['enabled'])
            expanded, conflicts = _expand_schedule(self.world, schedule,
                parse_canonical_utc('2026-10-05T00:00:00Z'), parse_canonical_utc('2026-10-20T00:00:00Z'))
            self.assertEqual(expanded, {})
            self.assertEqual(conflicts, [])

    def test_nonparked_future_planning_uses_projected_position_and_turnaround(self):
        draft = self.draft()
        draft.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                           ('2026-09-07',), '08:00', fare_minor=11600)
        draft.save_current(self.world)
        self.advance('2026-09-07T00:30:00Z')
        self.assertEqual(self.world['world_state']['aircraft'][self.aircraft]['status'], 'IN_FLIGHT')
        draft = self.draft()
        before = deepcopy(self.world)
        with self.assertRaisesRegex(ValueError, 'overlap|TURNAROUND'):
            draft.add_weekdays(self.airports['DVO'], self.airports['CEB'],
                               ('2026-09-07',), '09:50')
        self.assertEqual(draft.legs, [])
        self.assertEqual(self.world, before)
        self.assertEqual(draft.earliest(self.airports['DVO'], self.airports['CEB'],
                                       not_before='2026-09-07T01:50:00Z'), '2026-09-07T02:10:00Z')
        draft.add_weekdays(self.airports['DVO'], self.airports['CEB'], ('2026-09-07',), '10:10')
        draft.save_current(self.world)
        wrong = self.draft()
        with self.assertRaisesRegex(ValueError, 'REPOSITIONING_REQUIRED'):
            wrong.add_weekdays(self.airports['MNL'], self.airports['CEB'], ('2026-09-08',), '08:00')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_origin_and_destination_timezones_and_midnight(self):
        world = self.world['world_state']
        # A temporary authoritative timezone fixture; production data is untouched.
        world['airports'][self.airports['DVO']]['timezone'] = 'Asia/Tokyo'
        draft = self.draft()
        departure = local_departure(world, self.airports['MNL'], '2026-09-07', '22:50')
        self.assertEqual(format_utc(departure), '2026-09-07T14:50:00Z')
        draft.add(self.airports['MNL'], self.airports['DVO'], departure_utc=format_utc(departure))
        row = draft.week_rows('2026-09-07')[0]
        self.assertEqual(row['departure_local'], '2026-09-07T22:50:00+08:00')
        self.assertEqual(row['arrival_local'], '2026-09-08T01:30:00+09:00')
        self.assertEqual(row['timeline_arrival_local'], '2026-09-08T00:30:00+08:00')
        draft.save_current(self.world)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_pinned_dst_fold_and_gap_validation(self):
        world = {'airports': {'test': {'timezone': 'America/New_York'}}}
        self.assertEqual(format_utc(local_departure(world, 'test', '2026-11-01', '01:30', fold=0)),
                         '2026-11-01T05:30:00Z')
        self.assertEqual(format_utc(local_departure(world, 'test', '2026-11-01', '01:30', fold=1)),
                         '2026-11-01T06:30:00Z')
        for fold in (0, 1):
            with self.assertRaisesRegex(ValueError, 'does not exist'):
                local_departure(world, 'test', '2026-03-08', '02:30', fold=fold)
        self.assertEqual(format_utc(local_departure(self.world['world_state'], self.airports['MNL'],
                                                    '2026-09-02', '00:00')), '2026-09-01T16:00:00Z')

    def test_continuous_destination_dst_keeps_authoritative_block_duration(self):
        self.world['world_state']['airports'][self.airports['DVO']]['timezone'] = 'America/New_York'
        self.pair(dates=('2026-10-26',)).save_current(self.world, continuous=True)
        outbound = min(self.world['world_state']['schedule_definitions'].values(), key=lambda row: row['schedule_id'])
        flights, issues = _expand_schedule(self.world, outbound,
            parse_canonical_utc('2026-10-26T00:00:00Z'), parse_canonical_utc('2026-11-03T00:00:00Z'))
        self.assertEqual(issues, [])
        self.assertEqual(len(flights), 2)
        self.assertTrue(all(parse_canonical_utc(row['scheduled_in_block_utc'])
                             - parse_canonical_utc(row['scheduled_off_block_utc']) == timedelta(minutes=100)
                            for row in flights.values()))

    def test_cross_zone_revision_dates_and_weekday_rows_share_home_week(self):
        self.world['world_state']['airports'][self.airports['DVO']]['timezone'] = 'America/New_York'
        self.pair(dates=('2026-09-07',)).save_current(self.world, continuous=True)
        before = deepcopy(self.world['world_state']['dated_flights'])
        draft = WeeklyDraft.edit_recurring(self.world, airline_id=self.airline, aircraft_id=self.aircraft)
        self.assertEqual(draft.revision_from, '2026-10-05')
        rows = draft.week_rows('2026-10-05')
        draft_rows = [row for row in rows if row['draft_index'] is not None]
        self.assertEqual(len(draft_rows), 2)
        self.assertTrue(all(row['timeline_departure_local'][:10] == '2026-10-05' for row in draft_rows))
        self.assertEqual(sorted(row['departure_local'][:10] for row in draft_rows), ['2026-10-04', '2026-10-05'])
        draft.save_current(self.world, continuous=True)
        self.assertEqual(before, self.world['world_state']['dated_flights'])
        following = WeeklyDraft.edit_recurring(self.world, airline_id=self.airline, aircraft_id=self.aircraft)
        self.assertEqual(following.revision_from, '2026-10-12')
        self.assertEqual(len(following.legs), 2)

    def test_origin_local_revision_boundary_cannot_split_a_published_date(self):
        self.world['world_state']['airports'][self.airports['DVO']]['timezone'] = 'America/New_York'
        draft = self.draft()
        draft.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                           ('2026-09-06',), '18:00', return_flight=True, fare_minor=11600)
        draft.save_current(self.world, continuous=True)
        before = deepcopy(self.world['world_state']['dated_flights'])
        edited = WeeklyDraft.edit_recurring(self.world, airline_id=self.airline, aircraft_id=self.aircraft)
        # Home Monday Oct 5 is still Sunday Oct 4 at the return origin.
        # That origin-local revision date is already published: advance to the
        # next safe week rather than rewriting the protected Sunday occurrence.
        self.assertEqual(edited.revision_from, '2026-10-12')
        edited.save_current(self.world, continuous=True)
        self.assertEqual(self.world['world_state']['dated_flights'], before)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_save_load_retains_events_pattern_and_deterministic_continuation(self):
        with tempfile.TemporaryDirectory() as root:
            session = Stage1Session(save_root=root, runtime_clock=lambda: 0)
            session.new_game('CEO', 'Pattern Air', 'MNL')
            self.world = session.world
            self.pair().save_current(self.world, continuous=True)
            session.save_manual()
            resumed = Stage1Session(save_root=root, runtime_clock=lambda: 0)
            resumed.load_saved(session.career_id)
            self.assertEqual(resumed.world['simulation']['clock_state'], 'PAUSED')
            self.assertEqual(resumed.authoritative_bytes(), session.authoritative_bytes())
            for target in (session, resumed):
                result = target.advance_to('2026-09-06T16:00:00Z')
                self.assertTrue(result.result.succeeded)
            self.assertEqual(resumed.authoritative_bytes(), session.authoritative_bytes())
            serialized = resumed.authoritative_bytes().decode() if isinstance(resumed.authoritative_bytes(), bytes) else resumed.authoritative_bytes()
            for key in ('clipboard', 'selected_indices', 'builder_weekdays', 'schedule_selected'):
                self.assertNotIn(key, serialized)

    def test_invalid_missing_duplicate_and_wrong_day_publication_events_reject(self):
        self.pair().save_current(self.world, continuous=True)
        event = next(row for row in self.world['world_state']['pending_events'].values()
                     if row['event_type'] == EVENT_TYPE)
        variants = []
        missing = deepcopy(self.world)
        del missing['world_state']['pending_events'][event['event_id']]
        variants.append(missing)
        wrong = deepcopy(self.world)
        wrong['world_state']['pending_events'][event['event_id']]['due_at_utc'] = '2026-09-07T16:00:00Z'
        variants.append(wrong)
        payload = deepcopy(self.world)
        payload['world_state']['pending_events'][event['event_id']]['payload'] = {'contract': 'invalid'}
        variants.append(payload)
        for candidate in variants:
            self.assertFalse(validate_world(candidate).is_valid)


if __name__ == '__main__':
    unittest.main()
