"""Stage 3G-D paid first-service integration through the real Session entry."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from app.quarterly_planning import QuarterlyPlanningController
from game.aircraft_operations.fulfilment import process_flight_completion
from game.scheduling.quarterly_supply import QuarterlySupply
from game.world_state import create_stage1_new_game, validate_world


class QuarterlyDevelopmentStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda: 0)
        self.addCleanup(self.session.close)
        self.session.new_quarterly_development_game('CEO', 'Paid start', 'MNL')
        self.controller = QuarterlyPlanningController(self.session)
        self.controller.refresh()
        self.ports = {p['reference_code']: p['airport_id'] for p in self.session.airports()}
        self.aircraft = next(iter(self.state['aircraft']))

    @property
    def state(self):
        return self.session.world['world_state']

    def cash(self):
        return next(a['balance_minor'] for a in self.state['financial_accounts'].values()
                    if a['airline_id'] == self.session.airline_id and a['code'] == 'cash')

    def buy(self):
        quote = self.session.quote_route(self.ports['MNL'], self.ports['MNL'], self.ports['CEB'])
        self.assertEqual(quote.amount_minor, 2_783_491)
        cash = self.cash()
        cid = self.session.apply_route(quote)
        self.assertEqual(self.cash(), cash - quote.amount_minor)
        self.assertEqual(len(self.state['connections']), 2)
        self.assertTrue(all(c['status'] == 'ACTIVE' for c in self.state['connections'].values()))
        journals = [t for t in self.state['transactions'].values() if t['source_type'] == 'ROUTE_ESTABLISHMENT']
        self.assertEqual(len(journals), 1)
        self.assertEqual(journals[0]['source_id'], cid)
        self.assertEqual(journals[0]['amount_minor'], quote.amount_minor)
        self.assertEqual(sum(e['amount_minor'] for e in journals[0]['entries']), 0)
        return cid

    def slot(self, origin='MNL', destination='CEB', time='09:00:00', service_type='PASSENGER'):
        return self.session.quarterly_slot_input(aircraft_id=self.aircraft,
            origin_id=self.ports[origin], destination_id=self.ports[destination],
            weekdays=[4], departure_local_time=time, fare_minor=10_000, service_type=service_type)

    def create(self, **kwargs):
        result = self.controller.create(self.slot(**kwargs), 'PD')
        self.assertTrue(result.succeeded, result.issues)
        return result

    def start_before_publication_boundary(self):
        # Keep the PH scenario intact except creation UTC for bounded lifecycle tests.
        # The unmodified production scenario is checked separately above.
        scenario = json.loads(Path('Data/Stage1/philippines_v1.json').read_text(encoding='utf-8'))
        scenario['start_time_utc'] = '2026-11-30T23:59:59Z'
        path = Path(self.temp.name) / 'scenario.json'
        path.write_text(json.dumps(scenario), encoding='utf-8')
        def dated(**kwargs):
            return create_stage1_new_game(**kwargs, reference_path=path)
        with patch('app.session.create_stage1_new_game', side_effect=dated):
            self.session.new_quarterly_development_game('CEO', 'Boundary', 'MNL')
        self.controller.refresh()

    def advance(self, utc):
        report = self.session.advance_to(utc)
        self.assertIsNone(report.result.failure, report.result.failure)
        self.assertEqual(self.session.world['simulation']['time_utc'], utc)

    def roundtrip(self):
        before = self.session.authoritative_bytes()
        self.session.save_manual()
        self.session.load_saved(self.session.career_id)
        self.assertEqual(self.session.authoritative_bytes(), before)
        self.assertEqual(self.session.world['simulation']['clock_state'], 'PAUSED')
        report = validate_world(self.session.world)
        self.assertTrue(report.is_valid, report.errors[:3])
        self.controller.refresh()

    def test_start_preserves_scenario_capital_starter_and_selected_base(self):
        scenario = json.loads(Path('Data/Stage1/philippines_v1.json').read_text(encoding='utf-8'))
        for base in ('MNL', 'CEB'):
            with self.subTest(base=base):
                self.session.new_quarterly_development_game('CEO', 'Paid start', base)
                legacy = create_stage1_new_game(scenario_id=scenario['scenario_id'],
                    ceo_display_name='CEO', airline_display_name='Paid start', base_airport_reference_code=base)
                self.assertEqual(self.cash(), scenario['starting_cash_minor'])
                for root in ('aircraft', 'airlines', 'financial_accounts', 'airports', 'directional_markets'):
                    self.assertEqual(self.state[root], legacy['world_state'][root], root)
                self.assertFalse(self.state['connections'])
                self.assertFalse(self.state['transactions'])
                self.assertTrue(self.session.quarterly_career)
                self.assertEqual(self.session.world['metadata']['save_schema_version'], 9)
                self.assertEqual(self.session.world['simulation']['clock_state'], 'PAUSED')
                self.assertTrue(validate_world(self.session.world).is_valid)

    def test_failed_creation_preserves_active_session_and_preparations(self):
        quote = self.session.quote_route(self.ports['MNL'], self.ports['MNL'], self.ports['CEB'])
        before = self.session.authoritative_bytes()
        world, runtime, career = self.session.world, self.session.runtime, self.session.career_id
        def fail(candidate):
            candidate['world_state']['connections'].clear()
            candidate['simulation']['time_utc'] = '2099-01-01T00:00:00Z'
            raise ValueError('injected enrollment failure')
        with patch('game.scheduling.quarterly_backend.enable_quarterly_backend_for_testing', side_effect=fail):
            with self.assertRaisesRegex(ValueError, 'injected'):
                self.session.new_quarterly_development_game('Other', 'Other', 'CEB')
        self.assertIs(self.session.world, world)
        self.assertIs(self.session.runtime, runtime)
        self.assertFalse(runtime.closed)
        self.assertEqual(self.session.career_id, career)
        self.assertEqual(self.session.authoritative_bytes(), before)
        self.session.apply_route(quote)

    def test_stale_and_failed_purchase_preserve_authority(self):
        stale = self.session.quote_route(self.ports['MNL'], self.ports['MNL'], self.ports['DVO'])
        self.buy()
        before = self.session.authoritative_bytes()
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.session.apply_route(stale)
        self.assertEqual(self.session.authoritative_bytes(), before)
        quote = self.session.quote_route(self.ports['MNL'], self.ports['MNL'], self.ports['DVO'])
        with patch('game.route_management.establishment.post_route_establishment', side_effect=ValueError('payment failed')):
            with self.assertRaisesRegex(ValueError, 'payment failed'):
                self.session.apply_route(quote)
        self.assertEqual(self.session.authoritative_bytes(), before)

    def test_existing_free_route_save_keeps_rights_without_retroactive_payment(self):
        # Explicit historical fixture; the production development entry no longer seeds it.
        from game.scheduling.rotation import _connection
        for market in sorted(self.state['directional_markets'].values(), key=lambda m: m['market_id']):
            _connection(self.session.world, self.session.airline_id,
                        market['origin_airport_id'], market['destination_airport_id'])
        connections, cash = deepcopy(self.state['connections']), self.cash()
        self.roundtrip()
        self.assertEqual(self.state['connections'], connections)
        self.assertEqual(self.cash(), cash)
        self.assertFalse(self.state['transactions'])

    def test_real_scenario_draft_exclusion_then_publication_opens_sales(self):
        self.buy()
        self.create()
        self.create(origin='CEB', destination='MNL', time='14:00:00')
        self.advance('2026-09-02T00:00:00Z')
        self.assertFalse(self.state['bookings'])
        self.assertFalse(self.state['dated_flights'])
        self.assertFalse(self.state['itineraries'])
        self.assertEqual(len(self.state['transactions']), 1)
        self.roundtrip()
        pid = self.controller.page['plan_id']
        self.assertTrue(self.controller.inspect().execution_ready)
        self.assertTrue(self.controller.prepare_publication().succeeded)
        self.assertTrue(self.controller.confirm_publication().succeeded)
        self.advance('2026-09-03T00:00:00Z')
        self.assertTrue(self.state['bookings'])
        for booking in self.state['bookings'].values():
            itinerary = self.state['itineraries'][booking['itinerary_id']]
            self.assertEqual(itinerary['quarterly_lineage']['weekly_plan_id'], pid)
        self.roundtrip()

    def test_paid_first_service_publication_booking_operation_and_save_replay(self):
        self.start_before_publication_boundary()
        before = self.session.authoritative_bytes()
        with self.assertRaisesRegex(ValueError, 'no active connection'):
            self.slot()
        self.assertEqual(self.session.authoritative_bytes(), before)
        self.buy()
        outbound = self.create()
        # Repeating an outbound leg needs a real return, even if planning can infer a gap.
        readiness = self.controller.inspect()
        self.assertTrue(readiness.planning_feasible)
        self.assertFalse(readiness.execution_ready)
        self.assertTrue(any(i.code == 'UNRESOLVED_POSITIONING' for i in readiness.execution_blockers))
        before = self.session.authoritative_bytes()
        self.assertTrue(self.controller.prepare_publication().succeeded)
        self.assertFalse(self.controller.confirm_publication().succeeded)
        self.assertEqual(self.session.authoritative_bytes(), before)
        # Actual chronology rejects a return before the aircraft can arrive.
        result = self.controller.create(self.slot(origin='CEB', destination='MNL', time='09:01:00'), 'PD')
        self.assertFalse(result.succeeded)
        self.assertEqual(self.session.authoritative_bytes(), before)
        deadhead = self.create(origin='CEB', destination='MNL', time='14:00:00', service_type='DEADHEAD')
        readiness = self.controller.inspect()
        self.assertTrue(readiness.execution_ready, readiness.execution_blockers)
        self.assertFalse(QuarterlySupply(self.session.world).on_date('2027-01-01'))
        self.assertFalse(self.state['bookings'])
        self.roundtrip()  # Draft, paid rights and aircraft remain authoritative.
        pid = self.controller.page['plan_id']
        self.assertTrue(self.controller.prepare_publication().succeeded)
        self.assertTrue(self.controller.confirm_publication().succeeded)
        committed = deepcopy(self.state['weekly_plans'][pid])
        self.controller.select_plan(pid)
        with self.assertRaisesRegex(ValueError, 'locked'):
            self.controller.prepare_publication()
        before = self.session.authoritative_bytes()
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.controller.confirm_publication()
        self.assertEqual(self.session.authoritative_bytes(), before)
        self.advance('2026-12-01T00:00:00Z')
        self.assertTrue(self.state['bookings'])
        for booking in self.state['bookings'].values():
            itinerary = self.state['itineraries'][booking['itinerary_id']]
            self.assertEqual(itinerary['quarterly_lineage']['weekly_plan_id'], pid)
            self.assertEqual(itinerary['quarterly_lineage']['service_id'], outbound.service_id)
            self.assertIsNone(itinerary['schedule_lineage'])
        self.roundtrip()  # Published and sold, before the operating quarter.
        self.advance('2027-01-01T01:00:00Z')
        active = self.state['active_aircraft_operations']
        self.assertEqual(len(active), 1)
        fid = next(iter(active))
        flight = self.state['dated_flights'][fid]
        self.assertEqual(flight['status'], 'OPERATIONALLY_LOCKED')
        arrival = flight['scheduled_in_block_utc']
        self.roundtrip()  # Frozen departure obligations and manifest.
        self.advance(arrival)
        expected = self.session.authoritative_bytes()
        self.assertEqual(self.state['aircraft'][self.aircraft]['current_airport_id'], self.ports['CEB'])
        result = self.state['flight_results'][fid]
        self.assertEqual(result['quarterly_lineage'], self.state['dated_flights'][fid]['quarterly_lineage'])
        self.assertEqual(result['recognized_revenue_minor'], sum(self.state['bookings'][k]['total_fare_minor']
                         for k in result['source_booking_ids']))
        self.session.load_saved(self.session.career_id)
        self.advance(arrival)
        self.assertEqual(self.session.authoritative_bytes(), expected)
        self.advance('2027-01-01T08:00:00Z')
        deadhead_result = next(r for r in self.state['flight_results'].values()
                              if r['quarterly_lineage']['service_id'] == deadhead.service_id)
        self.assertFalse(deadhead_result['source_booking_ids'])
        self.assertEqual(deadhead_result['recognized_revenue_minor'], 0)
        self.assertEqual(self.state['aircraft'][self.aircraft]['current_airport_id'], self.ports['MNL'])
        consumed = {}
        for booking in self.state['bookings'].values():
            itinerary = self.state['itineraries'][booking['itinerary_id']]
            for key in itinerary['dated_flight_ids']:
                consumed[key] = consumed.get(key, 0) + booking['passenger_count']
        for key, count in consumed.items():
            self.assertLessEqual(count, self.state['dated_flights'][key]['capacity'])
        for result in self.state['flight_results'].values():
            transaction = self.state['transactions'][result['settlement_transaction_id']]
            self.assertEqual(transaction['source_id'], result['dated_flight_id'])
        self.assertEqual(len(self.state['flight_results']), 2)
        settlements = {r['settlement_transaction_id'] for r in self.state['flight_results'].values()}
        self.assertEqual(len(settlements), 2)
        self.assertEqual(self.cash(), 30_000_000_000 - 2_783_491
                         + sum(b['total_fare_minor'] for b in self.state['bookings'].values())
                         - sum(r['operating_cost_minor'] for r in self.state['flight_results'].values()))
        for checkpoint in self.state['booking_state']['booking_checkpoints'].values():
            for market in checkpoint['market_results'].values():
                self.assertEqual(market['desired_passenger_count'], sum(market[k] for k in (
                    'booked_passenger_count', 'outside_option_passenger_count',
                    'insufficient_capacity_passenger_count', 'no_eligible_service_passenger_count',
                    'no_departure_on_desired_date_passenger_count')))
        self.assertEqual(self.state['weekly_plans'][pid], committed)
        self.roundtrip()  # Completion, finance and positioning.
        before = self.session.authoritative_bytes()
        for key in self.state['flight_results']:
            flight = self.state['dated_flights'][key]
            cfg = self.session.world['simulation']['configuration']['flight_fulfilment']
            completed = process_flight_completion(self.session.world, key,
                expected_booking_revision=self.state['booking_state']['booking_revision'],
                expected_configuration_fingerprint=cfg['configuration_fingerprint'],
                expected_configuration_revision=cfg['current_revision'],
                expected_event_order_cursor=self.session.world['simulation']['event_order_cursor'],
                expected_finance_revision=self.state['airlines'][flight['airline_id']]['finance_revision'],
                expected_inventory_revision=flight['inventory_revision'],
                expected_operation_revision=flight['operation_revision'])
            self.assertTrue(completed.succeeded, completed.issues)
            self.assertTrue(completed.reused)
        self.assertEqual(self.session.authoritative_bytes(), before)

    def test_failed_boundary_save_correction_retry_from_development_entry(self):
        self.start_before_publication_boundary()
        self.buy()
        self.create()
        report = self.session.advance_to('2026-12-01T00:00:00Z')
        self.assertEqual(report.result.failure.code, 'QUARTERLY_PUBLICATION_FAILED')
        self.assertFalse(self.state['bookings'])
        self.roundtrip()
        before = self.session.authoritative_bytes()
        self.assertIsNotNone(self.controller.retry().result.failure)
        self.assertEqual(self.session.authoritative_bytes(), before)
        self.create(origin='CEB', destination='MNL', time='14:00:00')
        self.roundtrip()  # Correction preserves the fence until explicit retry.
        self.assertTrue(self.controller.page['fence']['failure'])
        self.assertIsNone(self.controller.retry().result.failure)
        expected = self.session.authoritative_bytes()
        self.session.load_saved(self.session.career_id)
        self.controller.refresh()
        self.assertIsNone(self.controller.retry().result.failure)
        self.assertEqual(self.session.authoritative_bytes(), expected)
        self.advance('2026-12-01T00:00:00Z')
        self.assertTrue(self.state['bookings'])
        self.roundtrip()


if __name__ == '__main__':
    unittest.main()
