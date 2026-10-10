"""Isolated quarterly supply, sold lineage and strict operational regression."""
from copy import deepcopy
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch
import json
from pathlib import Path

from tests import test_quarterly_foundation as foundation
encoded = foundation.encoded
from game.scheduling import quarterly_backend as backend
from game.scheduling.quarterly_backend import enable_quarterly_backend_for_testing
from game.scheduling.quarterly_supply import QuarterlySupply, QuarterlyShoppingIndexes
from game.scheduling.quarterly_occurrences import (
    QuarterlyOccurrenceReference, OccurrenceReadRequest, resolve_quarterly_occurrences)
from game.scheduling.rotation import _connection
from game.world_state.planning_reference import planning_snapshot
from game.world_state import validate_world, create_stage1_new_game
from game.world_state.quarterly_construction import create_weekly_plan, retire_service
from game.world_state.timestamps import parse_canonical_utc, format_utc
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import resolve_until
from game.booking.checkpoint import prepare_daily_booking_checkpoint, process_daily_booking_checkpoint
from game.booking.shopping import allocate_desired_travel_dates
from game.world_state.persistence import SaveStore
from game.scheduling import quarterly_commands as commands
from game.scheduling.quarterly_publication import PublishQuarterlyPlan
from game.simulation import kernel
from app.session import Stage1Session


class QuarterlyBackendTests(unittest.TestCase):
    @classmethod
    def fixture(cls, start="2027-01-01T00:00:00Z", quarter="2027-Q1", *, published=True):
        with tempfile.TemporaryDirectory() as temporary:
            scenario = json.loads(Path('Data/Stage1/philippines_v1.json').read_text(encoding='utf-8'))
            scenario['start_time_utc'] = start
            path = Path(temporary) / 'scenario.json'
            path.write_text(json.dumps(scenario), encoding='utf-8')
            bootstrap = create_stage1_new_game(scenario_id='stage1-philippines-v1',
                ceo_display_name='A', airline_display_name='Dabudhi',
                base_airport_reference_code='MNL', reference_path=path)
        f = foundation.FoundationTests(); f.base = bootstrap; f.setUp()
        legacy = deepcopy(f.world)
        pid, sid, n, row = f.plan(quarter)
        row['weekdays'] = list(range(7))
        # plan constructor detaches input; build exact independent return leg.
        plan = f.state['weekly_plans'][pid]
        plan['revisions']['1']['slots'][0]['weekdays'] = list(range(7))
        plan['revisions']['1']['slots'][0]['departure_local_time'] = '09:00:00'
        back_id, back_n = f.service()
        back = f.slot(back_id, back_n, origin_airport_id=f.dest,
            destination_airport_id=f.origin, departure_local_time='14:00:00',
            connection_id=_connection(f.world, f.owner, f.dest, f.origin),
            planning_timing=planning_snapshot(f.state, f.aircraft, f.dest, f.origin),
            weekdays=list(range(7)))
        plan['revisions']['1']['slots'].append(back)
        if published:
            plan['revisions']['1']['published_at_utc'] = f.world['simulation']['time_utc']
        world = deepcopy(f.world)
        enable_quarterly_backend_for_testing(world)
        initialize_runtime_handlers()
        return world, pid, sid, f.owner, f.aircraft, legacy

    @classmethod
    def setUpClass(cls):
        cls.base, cls.pid, cls.sid, cls.owner, cls.aircraft, cls.legacy = cls.fixture()

    def setUp(self):
        self.world = deepcopy(self.base)

    def valid(self):
        report = validate_world(self.world)
        self.assertTrue(report.is_valid, report.errors[:3])

    def advance(self, target, **kwargs):
        result = resolve_until(self.world, target, **kwargs)
        self.assertIsNone(result.failure, result.failure)
        self.valid()
        return result

    def test_untouched_legacy_new_game_has_no_marker(self):
        self.assertNotIn('operational_authority', self.legacy['simulation'])

    def test_enrollment_does_not_materialize_unsold_quarter(self):
        self.assertFalse(self.world['world_state']['dated_flights'])
        self.assertEqual(sum(e['event_type'] == 'QUARTERLY_DISPATCH'
            for e in self.world['world_state']['pending_events'].values()), 1)

    def test_published_projection_matches_independent_stage3b_resolver(self):
        day = '2027-01-04'
        row = next(r for r in QuarterlySupply(self.world).on_date(day)
                   if r['quarterly_lineage']['service_id'] == self.sid)
        ref = QuarterlyOccurrenceReference(self.pid, 1, self.sid, 1, day)
        resolved = resolve_quarterly_occurrences(self.world, airline_id=self.owner,
            requests=(OccurrenceReadRequest(ref, 1),))
        self.assertTrue(resolved.succeeded, resolved.issues)
        expected = resolved.occurrences[0]
        self.assertEqual(row['occurrence_key'], self.sid + '@2027-01-04#1')
        self.assertEqual(row['scheduled_off_block_utc'], expected.departure_utc)
        self.assertEqual(row['scheduled_in_block_utc'], expected.planning_arrival_utc)
        self.assertEqual(row['capacity'], expected.slot_facts['capacity'])

    def test_draft_exclusion(self):
        state = self.world['world_state']
        slots = deepcopy(state['weekly_plans'][self.pid]['revisions']['1']['slots'])
        create_weekly_plan(self.world, self.owner, '2027-Q2', slots=slots)
        before = encoded(self.world)
        self.assertFalse(QuarterlySupply(self.world).on_date('2027-04-02'))
        self.assertEqual(encoded(self.world), before)

    def test_retirement_excludes_new_sales_preserves_execution(self):
        retire_service(self.world, self.sid)
        self.assertFalse(any(r['quarterly_lineage']['service_id'] == self.sid
            for r in QuarterlySupply(self.world).on_date('2027-01-04')))
        self.assertTrue(any(r['quarterly_lineage']['service_id'] == self.sid
            for r in QuarterlySupply(self.world, sales=False).on_date('2027-01-04')))
        self.valid()

    def test_absolute_lead_distribution_and_horizon(self):
        cfg = self.world['simulation']['configuration']['booking']
        self.assertEqual([(r['minimum_lead_days'], r['maximum_lead_days'], r['weight_bps'])
            for r in cfg['lead_time_buckets']],
            [(0,0,500),(1,6,1500),(7,29,3500),(30,89,3000),(90,365,1500)])
        values = allocate_desired_travel_dates(100000, world_seed=1,
            cohort_date='2027-01-01', market_id='market-000000000001', booking_configuration=cfg)
        self.assertEqual(sum(n for _, n in values), 100000)
        self.assertEqual(values[0], ('2027-01-01', 5000))
        self.assertEqual(values[-1][0], '2028-01-01')

    def test_first_operational_departure_completion_and_finance(self):
        self.advance('2027-01-01T08:00:00Z')
        state = self.world['world_state']
        self.assertGreaterEqual(len(state['flight_results']), 1)
        for result in state['flight_results'].values():
            flight = state['dated_flights'][result['dated_flight_id']]
            self.assertEqual(result['quarterly_lineage'], flight['quarterly_lineage'])
            self.assertIsNone(result['schedule_id'])
            self.assertGreater(result['operating_cost_minor'], 0)
        self.assertGreater(state['aircraft'][self.aircraft]['lifecycle']['lifetime_cycles'], 0)

    def test_daily_booking_sold_lineage_capacity_and_original_date(self):
        self.advance('2027-01-02T00:00:00Z')
        state = self.world['world_state']
        self.assertTrue(state['bookings'])
        consumed = {}
        for booking in state['bookings'].values():
            itinerary = state['itineraries'][booking['itinerary_id']]
            flight = state['dated_flights'][itinerary['dated_flight_ids'][0]]
            self.assertIsNone(itinerary['schedule_lineage'])
            self.assertEqual(itinerary['quarterly_lineage'], flight['quarterly_lineage'])
            self.assertEqual(booking['total_fare_minor'], booking['passenger_count'] *
                itinerary['fare_offer_snapshot']['amount_minor'])
            delta = (parse_canonical_utc(itinerary['scheduled_departure_utc']).date() -
                parse_canonical_utc(booking['desired_travel_date']+'T00:00:00Z').date()).days
            self.assertLessEqual(abs(delta), 3)
            consumed[flight['dated_flight_id']] = consumed.get(flight['dated_flight_id'], 0) + booking['passenger_count']
        for flight_id, count in consumed.items():
            self.assertLessEqual(count, state['dated_flights'][flight_id]['capacity'])
        for checkpoint in state['booking_state']['booking_checkpoints'].values():
            for result in checkpoint['market_results'].values():
                self.assertEqual(result['desired_passenger_count'], sum(result[k] for k in (
                    'booked_passenger_count','outside_option_passenger_count',
                    'insufficient_capacity_passenger_count','no_eligible_service_passenger_count',
                    'no_departure_on_desired_date_passenger_count')))
        before = encoded(self.world)
        prepared = prepare_daily_booking_checkpoint(self.world)
        self.assertTrue(prepared.succeeded, prepared.issues)
        result = process_daily_booking_checkpoint(self.world, **prepared.as_kwargs())
        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(result.reused)
        self.assertEqual(encoded(self.world), before)

    def test_identical_replay(self):
        other = deepcopy(self.world)
        self.advance('2027-01-02T00:00:00Z')
        result = resolve_until(other, '2027-01-02T00:00:00Z')
        self.assertIsNone(result.failure, result.failure)
        self.assertEqual(encoded(other), encoded(self.world))

    def test_mode_cannot_be_removed_from_sold_lineage(self):
        self.advance('2027-01-01T08:00:00Z')
        del self.world['simulation']['operational_authority']
        self.assertFalse(validate_world(self.world).is_valid)

    def test_dispatch_lineage_tamper_rejected(self):
        event = next(e for e in self.world['world_state']['pending_events'].values()
                     if e['event_type'] == 'QUARTERLY_DISPATCH')
        event['payload']['quarterly_lineage']['revision'] = 2
        self.assertFalse(validate_world(self.world).is_valid)

    def manual_publish(self, quarter, *, pid=None, revision=0):
        request = PublishQuarterlyPlan('MANUAL', quarter, pid, revision,
                                      self.world['simulation']['time_utc'])
        prepared = commands.prepare_quarterly_command(self.world, airline_id=self.owner, request=request)
        self.assertTrue(prepared.succeeded, prepared.issues)
        applied = commands.apply_quarterly_command(self.world, airline_id=self.owner, prepared=prepared.prepared)
        self.assertTrue(applied.succeeded, applied.issues)
        return applied

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SaveStore(temporary); career = store.new_career_id()
            store.save(career, 'manual', self.world)
            loaded, _ = store.load(career)
        self.assertEqual(encoded(loaded), encoded(self.world))
        self.assertEqual(loaded['simulation']['clock_state'], 'PAUSED')
        return loaded

    def test_save_load_before_departure(self):
        self.roundtrip()

    def test_save_load_locked_operation_and_exact_replay(self):
        self.advance('2027-01-01T01:00:00Z')
        self.assertTrue(self.world['world_state']['active_aircraft_operations'])
        loaded = self.roundtrip()
        self.advance('2027-01-01T08:00:00Z')
        result = resolve_until(loaded, '2027-01-01T08:00:00Z')
        self.assertIsNone(result.failure, result.failure)
        self.assertEqual(encoded(loaded), encoded(self.world))

    def test_save_load_bookings_and_completed_finance(self):
        self.advance('2027-01-02T08:00:00Z')
        self.roundtrip()

    def test_session_load_rebind_preserves_exclusive_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = Stage1Session(save_root=temporary, runtime_clock=lambda: 0)
            session.world = deepcopy(self.world)
            session.career_id = session.save_store.new_career_id()
            session.save_manual(); session.load_saved(session.career_id)
            self.assertEqual(session.world['simulation']['operational_authority'], 'QUARTERLY_BACKEND_V1')
            self.assertEqual(encoded(session.world), encoded(self.world))

    def test_legacy_save_retains_legacy_authority(self):
        self.world = deepcopy(self.legacy)
        loaded = self.roundtrip()
        self.assertNotIn('operational_authority', loaded['simulation'])

    def test_existing_operational_career_cannot_enroll(self):
        self.advance('2027-01-02T00:00:00Z')
        del self.world['simulation']['operational_authority']
        before = encoded(self.world)
        with self.assertRaises(ValueError):
            enable_quarterly_backend_for_testing(self.world)
        self.assertEqual(encoded(self.world), before)

    def test_legacy_publication_writer_rejects_without_mutation(self):
        from game.scheduling.publication import publish_configured_window
        before = encoded(self.world)
        result = publish_configured_window(self.world)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.conflicts[0].code, 'OPERATIONAL_AUTHORITY')
        self.assertEqual(encoded(self.world), before)

    def test_published_fare_tamper_rejected(self):
        self.advance('2027-01-02T00:00:00Z')
        flight = next(iter(self.world['world_state']['dated_flights'].values()))
        flight['fare_offer']['amount_minor'] += 1
        self.assertFalse(validate_world(self.world).is_valid)

    def test_duplicate_dated_alias_rejected(self):
        self.advance('2027-01-01T01:00:00Z')
        state = self.world['world_state']
        flight = next(iter(state['dated_flights'].values()))
        from game.world_state.ids import allocate_id
        other = allocate_id(self.world, 'dated_flight')
        copied = deepcopy(flight); copied['dated_flight_id'] = other
        state['dated_flights'][other] = copied
        self.world['simulation']['operation_revisions'][other] = copied['operation_revision']
        self.assertFalse(validate_world(self.world).is_valid)

    def test_missing_dispatch_reconstructs_identically(self):
        events = self.world['world_state']['pending_events']
        for identity in tuple(events):
            if events[identity]['event_type'] == 'QUARTERLY_DISPATCH':
                del events[identity]
        before = len(events)
        backend.reconcile(self.world)
        self.assertEqual(len(self.world['world_state']['pending_events']), before + 1)
        committed = encoded(self.world)
        backend.reconcile(self.world)
        self.assertEqual(encoded(self.world), committed)
        self.advance('2027-01-01T08:00:00Z')

    def test_missing_past_operation_is_invalid_not_silently_recovered(self):
        self.world['world_state']['pending_events'] = {}
        self.world['simulation']['time_utc'] = '2027-01-01T08:00:00Z'
        self.assertFalse(validate_world(self.world).is_valid)

    def test_stale_dispatch_reconciliation(self):
        self.world['simulation']['operation_revisions'][self.aircraft] = 1
        self.advance('2027-01-01T08:00:00Z')
        self.assertTrue(any(e['event_type'] == 'QUARTERLY_DISPATCH' and e['status'] == 'STALE'
            for e in self.world['world_state']['event_history'].values()))

    def test_strict_shared_resolver_equivalence(self):
        other = deepcopy(self.world)
        self.advance('2027-01-02T00:00:00Z')
        result = resolve_until(other, '2027-01-02T00:00:00Z', shared=True)
        self.assertIsNone(result.failure, result.failure)
        self.assertEqual(encoded(other), encoded(self.world))

    def test_quarterly_handlers_do_not_inherit_legacy_certificates(self):
        from game.world_state.flight_transition_validation import supports_departure
        row = backend.next_occurrence(self.world, self.aircraft)
        identity = backend.materialize_candidate(self.world, row)
        event = next(e for e in self.world['world_state']['pending_events'].values()
                     if e['event_type'] == 'STAGE1_FLIGHT_DEPARTURE')
        self.assertEqual(event['owner_id'], identity)
        self.assertFalse(supports_departure(self.world, event))

    def test_manual_publication_carry_forward_does_not_materialize_quarter(self):
        result = self.manual_publish('2027-Q2')
        plan = self.world['world_state']['weekly_plans'][result.weekly_plan_id]
        self.assertEqual(len(plan['revisions']['1']['slots']), 2)
        self.assertTrue(QuarterlySupply(self.world).on_date('2027-04-02'))
        self.assertFalse(self.world['world_state']['dated_flights'])
        self.assertEqual(result.planning_quarter_id, '2027-Q3')

    def test_published_supply_beyond365_does_not_extend_booking_horizon(self):
        for quarter in ('2027-Q2', '2027-Q3', '2027-Q4', '2028-Q1'):
            self.manual_publish(quarter)
        self.assertFalse(QuarterlySupply(self.world).on_date('2028-01-02'))
        self.assertTrue(QuarterlySupply(self.world, sales=False).on_date('2028-01-02'))
        self.assertTrue(QuarterlySupply(self.world).on_date('2028-01-01'))
        self.assertFalse(self.world['world_state']['dated_flights'])

    def test_atomic_dispatch_failure_and_deterministic_retry(self):
        self.advance('2027-01-01T00:59:59Z')
        before = encoded(self.world); control = deepcopy(self.world)
        with patch.object(backend, 'materialize_candidate', side_effect=ValueError('injected supply failure')):
            result = resolve_until(self.world, '2027-01-01T01:00:00Z')
        self.assertIsNotNone(result.failure)
        self.assertEqual(encoded(self.world), before)
        self.advance('2027-01-01T01:00:00Z')
        result = resolve_until(control, '2027-01-01T01:00:00Z')
        self.assertIsNone(result.failure)
        self.assertEqual(encoded(control), encoded(self.world))

    def test_booking_failure_preserves_supply_finance_and_ids(self):
        self.advance('2027-01-01T23:59:59Z')
        before = encoded(self.world); control = deepcopy(self.world)
        with patch.object(backend, 'materialize_candidate', side_effect=ValueError('injected sale failure')):
            result = resolve_until(self.world, '2027-01-02T00:00:00Z')
        self.assertIsNotNone(result.failure)
        self.assertEqual(encoded(self.world), before)
        self.advance('2027-01-02T00:00:00Z')
        result = resolve_until(control, '2027-01-02T00:00:00Z')
        self.assertIsNone(result.failure)
        self.assertEqual(encoded(control), encoded(self.world))

    def test_two_day_progress_is_bounded_and_not_a_full_quarter_table(self):
        self.advance('2027-01-03T00:00:00Z')
        state = self.world['world_state']
        self.assertEqual(len(state['flight_results']), 4)
        sold_ids = {fid for booking in state['bookings'].values()
                    for fid in state['itineraries'][booking['itinerary_id']]['dated_flight_ids']}
        self.assertTrue(all(f['status'] == 'COMPLETED' or fid in sold_ids
                            for fid, f in state['dated_flights'].items()))
        self.assertFalse(state['schedule_definitions'])

    def boundary_world(self, *, start='2027-02-28T23:59:59Z', quarter='2027-Q2'):
        self.world, self.pid, self.sid, self.owner, self.aircraft, _ = self.fixture(start, quarter, published=False)

    def test_boundary_publication_precedes_older_booking_and_opens_supply(self):
        self.boundary_world()
        self.advance('2027-03-01T00:00:00Z')
        state = self.world['world_state']
        history = list(state['event_history'].values())
        types = [e['event_type'] for e in history]
        self.assertLess(types.index('QUARTERLY_PUBLICATION'), types.index('DAILY_BOOKING_CHECKPOINT'))
        self.assertTrue(any(f['quarterly_lineage']['weekly_plan_id'] == self.pid
                           for f in state['dated_flights'].values()))
        self.assertTrue(QuarterlySupply(self.world).on_date('2027-04-01'))
        self.roundtrip()

    def test_committed_automatic_skip_preserves_early_publication_stamp(self):
        self.boundary_world()
        result = self.manual_publish('2027-Q2', pid=self.pid, revision=1)
        stamp = self.world['world_state']['weekly_plans'][result.weekly_plan_id]['revisions']['1']['published_at_utc']
        self.advance('2027-03-01T00:00:00Z')
        self.assertEqual(self.world['world_state']['weekly_plans'][result.weekly_plan_id]['revisions']['1']['published_at_utc'], stamp)
        self.assertEqual(self.world['simulation']['quarterly_publication'][self.owner]['next_quarter_id'], '2027-Q3')

    def test_failed_publication_fences_booking_save_correction_and_retry(self):
        from game.scheduling.quarterly_edits import RemoveQuarterlySlots
        self.boundary_world()
        state = self.world['world_state']
        pid = self.pid
        state['weekly_plans'][pid]['revisions']['1']['slots'].pop()
        failed = resolve_until(self.world, '2027-03-01T00:00:00Z')
        self.assertEqual(failed.failure.code, 'QUARTERLY_PUBLICATION_FAILED')
        self.assertFalse(self.world['world_state']['bookings'])
        self.assertIsNotNone(self.world['simulation']['quarterly_publication'][self.owner]['failure'])
        self.roundtrip()
        request = RemoveQuarterlySlots(pid, 1, ((self.sid, 1),))
        prepared = commands.prepare_quarterly_command(self.world, airline_id=self.owner, request=request)
        self.assertTrue(prepared.succeeded, prepared.issues)
        applied = commands.apply_quarterly_command(self.world, airline_id=self.owner, prepared=prepared.prepared)
        self.assertTrue(applied.succeeded, applied.issues)
        self.advance('2027-03-01T00:00:00Z')
        self.assertIsNone(self.world['simulation']['quarterly_publication'][self.owner]['failure'])
        self.assertFalse(QuarterlySupply(self.world).on_date('2027-04-01'))

    def test_year_rollover_publication_and_neighboring_aircraft_chronology(self):
        self.boundary_world(start='2027-12-01T00:00:00Z', quarter='2028-Q1')
        self.advance('2027-12-01T00:00:00Z')
        self.assertTrue(QuarterlySupply(self.world).on_date('2028-01-01'))
        self.assertEqual(self.world['simulation']['quarterly_publication'][self.owner]['next_quarter_id'], '2028-Q2')
        self.roundtrip()

    def test_date_flexibility_crosses_published_boundary_keeps_original_desired_date(self):
        self.manual_publish('2027-Q2')
        from game.booking.shopping import _offer
        indexes = QuarterlyShoppingIndexes(self.world)
        market = self.world['world_state']['connections'][
            self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]['connection_id']]['market_id']
        keys = indexes.by_market_and_departure_date.get((market, '2027-04-01'))
        offer = _offer(indexes.by_dated_flight_id[keys[0]], '2027-03-31')
        self.assertEqual(offer.desired_travel_date, '2027-03-31')
        self.assertEqual(offer.date_deviation_days, 1)
        self.assertIsNone(offer.schedule_lineage)
        self.assertNotEqual(offer.quarterly_lineage.weekly_plan_id, self.pid)

    def test_modified_next_quarter_preserves_identity_and_changes_fixed_fare(self):
        state = self.world['world_state']
        slots = deepcopy(state['weekly_plans'][self.pid]['revisions']['1']['slots'])
        slots[0]['fare_offer']['amount_minor'] = 12345
        pid = create_weekly_plan(self.world, self.owner, '2027-Q2', slots=slots)
        self.manual_publish('2027-Q2', pid=pid, revision=1)
        before = next(r for r in QuarterlySupply(self.world).on_date('2027-03-31') if r['quarterly_lineage']['service_id'] == self.sid)
        after = next(r for r in QuarterlySupply(self.world).on_date('2027-04-01') if r['quarterly_lineage']['service_id'] == self.sid)
        self.assertEqual(before['quarterly_lineage']['service_id'], after['quarterly_lineage']['service_id'])
        self.assertEqual(before['quarterly_lineage']['slot_number'], after['quarterly_lineage']['slot_number'])
        self.assertEqual(before['fare_offer']['amount_minor'], 10000)
        self.assertEqual(after['fare_offer']['amount_minor'], 12345)

    def test_retirement_keeps_sold_obligations_and_exact_revenue(self):
        self.advance('2027-01-02T00:00:00Z')
        state = self.world['world_state']
        booked = deepcopy(state['bookings'])
        for service_id in state['services']:
            retire_service(self.world, service_id)
        self.advance('2027-01-02T08:00:00Z')
        self.assertEqual(self.world['world_state']['bookings'], booked)
        for result in self.world['world_state']['flight_results'].values():
            self.assertEqual(result['recognized_revenue_minor'], sum(booked[key]['total_fare_minor']
                for key in result['source_booking_ids']))
        self.assertFalse(QuarterlySupply(self.world).on_date('2027-01-03'))

    def test_executable_deadhead_has_no_booking_and_moves_aircraft(self):
        state = self.world['world_state']
        slots = state['weekly_plans'][self.pid]['revisions']['1']['slots']
        slots[1].update(service_type='DEADHEAD', connection_id=None, capacity=0,
                        fare_offer={'currency':'USD','amount_minor':0})
        self.valid()
        self.advance('2027-01-01T08:00:00Z')
        results = self.world['world_state']['flight_results'].values()
        result = next(r for r in results if r['quarterly_lineage']['service_id'] == slots[1]['service_id'])
        self.assertFalse(result['source_booking_ids'])
        self.assertEqual(result['recognized_revenue_minor'], 0)
        self.assertEqual(self.world['world_state']['aircraft'][self.aircraft]['current_airport_id'], slots[0]['origin_airport_id'])

    def test_hypothetical_positioning_and_unavailable_aircraft_are_rejected(self):
        state = self.world['world_state']
        state['weekly_plans'][self.pid]['revisions']['1']['slots'].pop()
        before = encoded(self.world)
        self.assertFalse(validate_world(self.world).is_valid)
        result = resolve_until(self.world, '2027-01-01T08:00:00Z')
        self.assertIsNotNone(result.failure)
        self.assertEqual(encoded(self.world), before)

    def test_double_fulfilment_after_reload_does_not_double_finance(self):
        self.advance('2027-01-02T08:00:00Z')
        self.world = self.roundtrip()
        from game.aircraft_operations.fulfilment import process_flight_completion
        state = self.world['world_state']
        flight_id = next(iter(state['flight_results']))
        before = encoded(self.world)
        flight = state['dated_flights'][flight_id]
        cfg = self.world['simulation']['configuration']['flight_fulfilment']
        result = process_flight_completion(self.world, flight_id,
            expected_booking_revision=state['booking_state']['booking_revision'],
            expected_configuration_fingerprint=cfg['configuration_fingerprint'],
            expected_configuration_revision=cfg['current_revision'],
            expected_event_order_cursor=self.world['simulation']['event_order_cursor'],
            expected_finance_revision=state['airlines'][flight['airline_id']]['finance_revision'],
            expected_inventory_revision=flight['inventory_revision'],
            expected_operation_revision=flight['operation_revision'])
        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(result.reused)
        self.assertEqual(encoded(self.world), before)

    def test_more_frequencies_do_not_multiply_directional_demand(self):
        from game.world_state.quarterly_construction import create_service, allocate_service_slot
        control = deepcopy(self.world)
        state = self.world['world_state']
        slots = state['weekly_plans'][self.pid]['revisions']['1']['slots']
        for source, departure in zip(deepcopy(slots), ('19:00:00', '23:00:00')):
            service = create_service(self.world, self.owner, flight_number_prefix='DAB')
            source.update(service_id=service, slot_number=allocate_service_slot(self.world, service),
                          departure_local_time=departure)
            slots.append(source)
        self.valid()
        self.advance('2027-01-02T00:00:00Z')
        other = resolve_until(control, '2027-01-02T00:00:00Z')
        self.assertIsNone(other.failure, other.failure)
        def pools(world):
            checkpoint = next(c for c in world['world_state']['booking_state']['booking_checkpoints'].values()
                              if c['checkpoint_date'] == '2027-01-02')
            return {key: value['desired_passenger_count'] for key, value in checkpoint['market_results'].items()}
        self.assertEqual(pools(self.world), pools(control))
        self.assertTrue(pools(control))

    def test_unavailable_probability_mass_is_terminal_without_renormalization(self):
        self.advance('2027-01-02T00:00:00Z')
        state = self.world['world_state']
        checkpoint = next(c for c in state['booking_state']['booking_checkpoints'].values()
                          if c['checkpoint_date'] == '2027-01-02')
        terminal = 0
        for result in checkpoint['market_results'].values():
            for day, group in result['desired_date_results'].items():
                if day > '2027-04-03':
                    self.assertEqual(group['booked_passenger_count'], 0)
                    self.assertEqual(group['requested_passenger_count'], group['no_departure_on_desired_date_passenger_count'])
                    terminal += group['requested_passenger_count']
        self.assertGreater(terminal, 0)
        retained = deepcopy(checkpoint)
        self.advance('2027-01-03T00:00:00Z')
        self.assertEqual(self.world['world_state']['booking_state']['booking_checkpoints'][checkpoint['booking_checkpoint_id']], retained)

    def test_late_quarterly_source_mutation_rejects_sale_atomically(self):
        import game.booking.checkpoint as checkpoint
        self.advance('2027-01-01T23:59:59Z')
        before = encoded(self.world)
        original = checkpoint.prepare_daily_booking_allocation
        def mutate(candidate, **kwargs):
            result = original(candidate, **kwargs)
            candidate['world_state']['services'][self.sid]['retired_at_utc'] = candidate['simulation']['time_utc']
            return result
        with patch.object(checkpoint, 'prepare_daily_booking_allocation', side_effect=mutate):
            result = resolve_until(self.world, '2027-01-02T00:00:00Z')
        self.assertIsNotNone(result.failure)
        self.assertEqual(encoded(self.world), before)

    def test_derived_supply_snapshots_do_not_alias_authority(self):
        before = encoded(self.world)
        row = QuarterlySupply(self.world).on_date('2027-01-04')[0]
        row['fare_offer']['amount_minor'] = 1
        row['quarterly_lineage']['service_id'] = 'corrupt'
        self.assertEqual(encoded(self.world), before)

    def test_published_capacity_must_match_installed_aircraft(self):
        plan = self.world['world_state']['weekly_plans'][self.pid]
        plan['revisions']['1']['slots'][0]['capacity'] += 1
        self.assertFalse(validate_world(self.world).is_valid)

    def test_dispatch_handler_substitution_is_rejected(self):
        registry = kernel.EventHandlerRegistry()
        registry.register('QUARTERLY_DISPATCH', lambda context: None)
        self.advance('2027-01-01T00:59:59Z')
        before = encoded(self.world)
        result = resolve_until(self.world, '2027-01-01T01:00:00Z', registry=registry)
        self.assertEqual(result.failure.code, 'HANDLER_CONTRACT_VIOLATION')
        self.assertEqual(encoded(self.world), before)

    def test_invalid_mode_and_marker_without_lineage_are_rejected(self):
        self.world['simulation']['operational_authority'] = 'LEGACY_AND_QUARTERLY'
        self.assertFalse(validate_world(self.world).is_valid)
        self.world = deepcopy(self.base)
        del self.world['simulation']['operational_authority']
        self.assertFalse(validate_world(self.world).is_valid)

    def test_unavailable_aircraft_cannot_create_operations_or_bookings(self):
        state = self.world['world_state']
        slot = state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        state['aircraft'][self.aircraft]['current_airport_id'] = slot['destination_airport_id']
        before = encoded(self.world)
        result = resolve_until(self.world, '2027-01-01T08:00:00Z')
        self.assertIsNotNone(result.failure)
        self.assertEqual(encoded(self.world), before)
        self.assertFalse(state['active_aircraft_operations'])

    def test_zero_fare_reserves_capacity_without_ticket_sale_revenue(self):
        for slot in self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots']:
            slot['fare_offer']['amount_minor'] = 0
        self.advance('2027-01-02T08:00:00Z')
        state = self.world['world_state']
        self.assertTrue(state['bookings'])
        self.assertTrue(all(b['total_fare_minor'] == 0 and b['finance_transaction_id'] is None
                            for b in state['bookings'].values()))
        self.assertTrue(all(r['recognized_revenue_minor'] == 0 and r['operating_cost_minor'] > 0
                            for r in state['flight_results'].values()))

    def test_actual_aircraft_continuity_across_operating_quarter_rollover(self):
        from game.demand import revise_demand_model
        revised = revise_demand_model(self.world, configuration_updates={
            'daily_booker_rate_ppm': 0, 'configuration_version': 'stage3e-zero-demand-fixture-v1'})
        self.assertTrue(revised.succeeded, revised.issues)
        self.manual_publish('2027-Q2')
        self.advance('2027-04-01T08:00:00Z')
        state = self.world['world_state']
        march = [r for r in state['flight_results'].values() if r['scheduled_off_block_utc'][:10] == '2027-03-31']
        april = [r for r in state['flight_results'].values() if r['scheduled_off_block_utc'][:10] == '2027-04-01']
        self.assertEqual(len(march), 2)
        self.assertEqual(len(april), 2)
        self.assertNotEqual(march[0]['quarterly_lineage']['weekly_plan_id'], april[0]['quarterly_lineage']['weekly_plan_id'])
        self.assertEqual(state['aircraft'][self.aircraft]['lifecycle']['lifetime_cycles'], 182)
        self.assertFalse(state['bookings'])
        self.roundtrip()
