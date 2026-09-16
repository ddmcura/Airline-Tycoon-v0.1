"""Atomic acquisition, versioned performance and historical compatibility."""

from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
import unittest
from unittest.mock import patch

from app.terminal.main import _Terminal
from app.terminal.session import Stage1Session
from game.aircraft_market.acquisition import preview_purchase, purchase_aircraft
from game.aircraft_market.reference_catalog import load_aircraft_catalog, PH_AIRCRAFT_CATALOG_VERSION as VERSION
from game.aircraft_operations.projections import project_airline_fleet
from game.economy.acquisition import purchase_accounts
from game.scheduling import WeeklyDraft, create_weekly_round_trip_rotation
from game.scheduling.eligibility import check_eligibility
from game.scheduling.timing import timing_bounds
from game.simulation import process_events_through, process_next_event
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.migration import migrate_schema_4_to_5
from game.world_state.timestamps import parse_canonical_utc


def encoded(world):
    return json.dumps(world, sort_keys=True, separators=(',', ':'))


class AcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='A', airline_display_name='B', base_airport_reference_code='MNL')
        catalog = load_aircraft_catalog(catalog_version=VERSION)
        cls.models = [model for m in catalog.manufacturers() for model in catalog.models(m['manufacturer_id'])]

    def setUp(self):
        self.world = deepcopy(self.base)
        state = self.world['world_state']
        self.owner = state['player']['primary_airline_id']
        self.airports = {a['reference_code']: key for key, a in state['airports'].items()}
        self.cash = purchase_accounts(state, self.owner)['cash']
        self.cash['balance_minor'] = 1_000_000_000_000

    def preview(self, model=None, **kwargs):
        return preview_purchase(self.world, airline_id=self.owner,
            catalog_version=VERSION, model_id=model or self.models[0]['model_id'],
            delivery_airport_id=kwargs.pop('delivery_airport_id', self.airports['MNL']), **kwargs)

    def buy(self, model=None):
        return purchase_aircraft(self.world, self.preview(model))

    def assert_valid(self, world=None):
        result = validate_world(world or self.world)
        self.assertTrue(result.is_valid, result.errors)

    def test_all_models_exact_accounting_configuration_and_replay(self):
        registrations = set()
        for model in self.models:
            with self.subTest(model=model['model_id']):
                p = self.preview(model['model_id'])
                before = deepcopy(self.world)
                aircraft_id = purchase_aircraft(self.world, p)
                aircraft = self.world['world_state']['aircraft'][aircraft_id]
                self.assertNotIn(aircraft['display_registration'], registrations)
                registrations.add(aircraft['display_registration'])
                self.assertTrue(aircraft['display_registration'].startswith('RP-C'))
                self.assertEqual(aircraft['configuration']['economy_capacity'], model['max_economy_seats'])
                self.assertEqual(aircraft['status'], 'PARKED')
                self.assertEqual(before['simulation'], self.world['simulation'])
                old = purchase_accounts(before['world_state'], self.owner)
                new = purchase_accounts(self.world['world_state'], self.owner)
                self.assertEqual(old['cash']['balance_minor'] - new['cash']['balance_minor'], p.amount_minor)
                self.assertEqual(new['aircraft_assets']['balance_minor'] - old['aircraft_assets']['balance_minor'], p.amount_minor)
                for code in ('passenger_revenue', 'operating_expenses', 'unflown_tickets'):
                    self.assertEqual(old[code], new[code])
                committed = encoded(self.world)
                self.assertEqual(purchase_aircraft(self.world, p), aircraft_id)
                self.assertEqual(committed, encoded(self.world))
                self.assert_valid()

    def test_exact_balance_and_insufficient_funds(self):
        p = self.preview()
        self.cash['balance_minor'] = p.amount_minor - 1
        before = encoded(self.world)
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            purchase_aircraft(self.world, self.preview())
        self.assertEqual(before, encoded(self.world))
        self.cash['balance_minor'] += 1
        self.buy()
        self.assertEqual(purchase_accounts(self.world['world_state'], self.owner)['cash']['balance_minor'], 0)

    def test_delivery_is_separate_from_existing_home(self):
        self.world['world_state']['airlines'][self.owner]['base_airport_ids'].append(self.airports['CEB'])
        p = self.preview(delivery_airport_id=self.airports['CEB'])
        aircraft_id = purchase_aircraft(self.world, p)
        aircraft = self.world['world_state']['aircraft'][aircraft_id]
        self.assertEqual(aircraft['home_airport_id'], self.airports['MNL'])
        self.assertEqual(aircraft['current_airport_id'], self.airports['CEB'])
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=aircraft_id)
        draft.add(self.airports['CEB'], self.airports['MNL'])
        self.assertTrue(draft.save(self.world).succeeded)

    def test_stale_tampered_invalid_and_reused_commands_are_atomic(self):
        p = self.preview(command_id='one')
        self.world['ui_state']['selected_screen'] = 'unrelated'
        aircraft_id = purchase_aircraft(self.world, p)
        before = encoded(self.world)
        for bad in (replace(p, model_id='unknown'), replace(p, amount_minor=1),
                    self.preview(command_id='one')):
            with self.assertRaises(ValueError):
                purchase_aircraft(self.world, bad)
            self.assertEqual(before, encoded(self.world))
        stale = self.preview()
        self.buy(self.models[1]['model_id'])
        before = encoded(self.world)
        with self.assertRaisesRegex(ValueError, 'stale'):
            purchase_aircraft(self.world, stale)
        with self.assertRaises(ValueError):
            self.preview(delivery_airport_id=self.airports['DVO'])
        with self.assertRaises(ValueError):
            self.preview('unknown')
        self.assertEqual(before, encoded(self.world))
        self.assertIn(aircraft_id, self.world['world_state']['aircraft'])

    def test_failure_after_allocation_preserves_every_byte_and_retry(self):
        p = self.preview()
        before = deepcopy(self.world)
        with patch('game.aircraft_market.acquisition.post_purchase', side_effect=ValueError('injected')):
            with self.assertRaises(ValueError):
                purchase_aircraft(self.world, p)
        self.assertEqual(encoded(before), encoded(self.world))
        left = purchase_aircraft(self.world, p)
        right = purchase_aircraft(before, p)
        self.assertEqual(left, right)
        self.assertEqual(encoded(before), encoded(self.world))

    def test_registration_scales_without_small_pool_and_is_deterministic(self):
        from game.fleet_management.acquisition import enter_purchased_aircraft
        catalog = load_aircraft_catalog(catalog_version=VERSION)
        view = catalog.model(self.models[0]['model_id'])
        # Exercise allocation near 10,000 without manufacturing 10,000 worlds.
        self.world['deterministic_state']['id_allocator']['next_by_type']['aircraft'] = 10000
        other = deepcopy(self.world)
        used = set()
        for _ in range(30):
            a = enter_purchased_aircraft(self.world, self.owner, self.airports['MNL'], view)
            b = enter_purchased_aircraft(other, self.owner, self.airports['MNL'], view)
            self.assertEqual(a, b)
            row = self.world['world_state']['aircraft'][a]
            self.assertEqual(row, other['world_state']['aircraft'][b])
            self.assertNotIn(row['display_registration'], used)
            used.add(row['display_registration'])

    def test_range_exact_ceiling_and_unknown_contract(self):
        aircraft_id = self.buy()
        aircraft = self.world['world_state']['aircraft'][aircraft_id]
        model = self.models[0]
        check_eligibility(aircraft, model['reference_range_km'] * 1000)
        with self.assertRaisesRegex(ValueError, 'RANGE_EXCEEDED'):
            check_eligibility(aircraft, model['reference_range_km'] * 1000 + 1)
        aircraft['configuration']['performance_contract'] = 'future'
        with self.assertRaises(ValueError):
            check_eligibility(aircraft, 1)
        self.assertFalse(validate_world(self.world).is_valid)

    def test_all_categories_capacity_turnaround_and_quick_rotation_guard(self):
        for category in ('NARROWBODY', 'WIDEBODY', 'REGIONAL_JET', 'TURBOPROP'):
            model = next(m for m in self.models if m['aircraft_category'] == category)
            aircraft_id = self.buy(model['model_id'])
            draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=aircraft_id)
            leg = draft.add(self.airports['MNL'], self.airports['CEB'],
                departure_utc='2026-09-07T00:00:00Z', fare_minor=10000)
            returned = draft.add_return()
            pre, block, post = timing_bounds(leg['planning_timing'])[1]
            self.assertEqual(pre, 2700 if category == 'WIDEBODY' else 1800)
            self.assertEqual(post, 0)
            self.assertEqual((parse_canonical_utc(returned['departure_utc']) -
                              parse_canonical_utc(leg['departure_utc'])).total_seconds(), block + pre)
            self.assertTrue(draft.save(self.world).succeeded)
            for flight in self.world['world_state']['dated_flights'].values():
                if flight['planned_aircraft_id'] == aircraft_id:
                    self.assertEqual(flight['capacity'], model['max_economy_seats'])
            before = encoded(self.world)
            result = create_weekly_round_trip_rotation(self.world, airline_id=self.owner,
                aircraft_id=aircraft_id, destination_airport_reference_code='CEB',
                fare_minor=10000, first_operating_date='2026-09-14')
            self.assertFalse(result.succeeded)
            self.assertEqual(before, encoded(self.world))

    def test_booking_fulfilment_mixed_fleet_deadhead_and_replay(self):
        for index, category in enumerate(('WIDEBODY', 'TURBOPROP')):
            model = next(m for m in self.models if m['aircraft_category'] == category)
            aid = self.buy(model['model_id'])
            draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=aid)
            draft.add(self.airports['MNL'], self.airports['CEB'],
                departure_utc='2026-09-07T00:00:00Z', fare_minor=10000)
            draft.add(self.airports['CEB'], self.airports['MNL'], deadhead=True)
            self.assertTrue(draft.save(self.world).succeeded)
        other = json.loads(encoded(self.world))
        target = '2026-09-07T12:00:00Z'
        result = process_events_through(self.world, target)
        self.assertTrue(result.succeeded, result)
        while any(e['due_at_utc'] <= target for e in other['world_state']['pending_events'].values()):
            self.assertTrue(process_next_event(other).succeeded)
        self.assertTrue(process_events_through(other, target).succeeded)
        self.assertEqual(encoded(self.world), encoded(other))
        self.assertTrue(self.world['world_state']['bookings'])
        self.assertEqual(len(self.world['world_state']['flight_results']), 4)
        for flight in self.world['world_state']['dated_flights'].values():
            self.assertEqual(flight['status'], 'COMPLETED')
            if flight['service_type'] == 'DEADHEAD':
                self.assertEqual(flight['capacity'], 0)
        self.assert_valid()

    def test_migration_preserves_exact_starter_and_published_history(self):
        starter = next(iter(self.world['world_state']['aircraft']))
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=starter)
        draft.add(self.airports['MNL'], self.airports['CEB'], departure_utc='2026-09-07T00:00:00Z')
        self.assertTrue(draft.save(self.world).succeeded)
        self.world['metadata']['save_schema_version'] = 4
        original = deepcopy(self.world)
        result = migrate_schema_4_to_5(self.world)
        self.assertTrue(result.succeeded, result)
        self.assertEqual(encoded(self.world), encoded(original))
        expected = deepcopy(original)
        expected['metadata']['save_schema_version'] = 5
        self.assertEqual(encoded(expected), encoded(result.world))
        self.assertNotIn('configuration', result.world['world_state']['aircraft'][starter])

    def test_corrupt_configuration_and_purchase_journals_reject(self):
        aid = self.buy()
        original = deepcopy(self.world)
        mutations = [
            lambda w: w['world_state']['aircraft'][aid]['configuration'].update(economy_capacity=180),
            lambda w: w['world_state']['aircraft'][aid]['configuration'].update(catalog_version='unknown'),
            lambda w: w['world_state']['transactions'].clear(),
            lambda w: w['world_state']['aircraft'][aid].update(display_registration='RP-C0001'),
        ]
        for mutate in mutations:
            candidate = deepcopy(original)
            mutate(candidate)
            self.assertFalse(validate_world(candidate).is_valid)

    def test_terminal_purchase_cancel_and_derived_pagination(self):
        session = Stage1Session()
        session.world = self.world
        for answer in ('cancel\n', '1\nno\n'):
            before = session.authoritative_bytes()
            _Terminal(StringIO(answer), StringIO(), session).purchase_model(self.models[0])
            self.assertEqual(before, session.authoritative_bytes())
            self.assertFalse(session.changed)
        output = StringIO()
        _Terminal(StringIO('bad\n1\nyes\n'), output, session).purchase_model(self.models[0])
        self.assertTrue(session.changed)
        self.assertIn('Purchased RP-C', output.getvalue())
        before = session.authoritative_bytes()
        rows = project_airline_fleet(self.world, self.owner, limit=1, offset=1)
        self.assertEqual(len(rows), 1)
        rows[0]['status'] = 'INVALID'
        self.assertEqual(before, session.authoritative_bytes())

    def test_final_validation_failure_is_atomic(self):
        import game.aircraft_market.acquisition as commands
        preview = self.preview()
        before = encoded(self.world)
        original = commands._validate
        def reject_candidate(candidate):
            original(candidate)
            if len(candidate['world_state']['aircraft']) > 1:
                raise ValueError('injected final validation failure')
        with patch.object(commands, '_validate', side_effect=reject_candidate):
            with self.assertRaisesRegex(ValueError, 'injected'):
                purchase_aircraft(self.world, preview)
        self.assertEqual(before, encoded(self.world))

    def test_purchased_history_does_not_reload_taxi_reference(self):
        aircraft_id = self.buy()
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=aircraft_id)
        draft.add(self.airports['MNL'], self.airports['CEB'], departure_utc='2026-09-07T00:00:00Z')
        self.assertTrue(draft.save(self.world).succeeded)
        before = encoded(self.world)
        with patch('game.world_state.planning_reference._PATH') as path:
            path.read_text.side_effect = OSError('unavailable current timing reference')
            self.assert_valid()
        self.assertEqual(before, encoded(self.world))

    def test_registration_collision_probes_deterministically(self):
        from game.fleet_management.acquisition import enter_purchased_aircraft
        view = load_aircraft_catalog(catalog_version=VERSION).model(self.models[0]['model_id'])
        with patch('game.fleet_management.acquisition.sha256') as digest:
            digest.return_value.digest.return_value = bytes(32)
            first = enter_purchased_aircraft(self.world, self.owner, self.airports['MNL'], view)
            second = enter_purchased_aircraft(self.world, self.owner, self.airports['MNL'], view)
        aircraft = self.world['world_state']['aircraft']
        self.assertEqual(aircraft[first]['display_registration'], 'RP-C000000000000')
        self.assertEqual(aircraft[second]['display_registration'], 'RP-C000000000001')

    def test_second_fleet_page_is_selectable_without_authoritative_summary(self):
        from game.world_state.construction import add_aircraft
        for index in range(25):
            add_aircraft(self.world, self.owner, f'COMPAT-{index}', 'A320-200',
                         home_airport_id=self.airports['MNL'])
        session = Stage1Session()
        session.world = self.world
        before = encoded(self.world)
        terminal = _Terminal(StringIO('next\n1\n'), StringIO(), session)
        selected = terminal.select_aircraft()
        expected = session.fleet(offset=20)[0]
        self.assertEqual(selected, expected)
        self.assertEqual(before, encoded(self.world))

    def test_terminal_catalog_purchase_end_to_end(self):
        session = Stage1Session()
        session.world = self.world
        output = StringIO()
        _Terminal(StringIO('1\n1\n1\nyes\n'), output, session).aircraft_catalogue(purchase=True)
        self.assertIn('Purchased RP-C', output.getvalue())
        self.assertEqual(len(self.world['world_state']['aircraft']), 2)
        _Terminal(StringIO(''), output, session).show_finances()
        self.assertIn('Aircraft assets:', output.getvalue())
        self.assertIn('Aircraft purchase', output.getvalue())

    def test_malformed_migration_and_preview_inputs_reject_without_mutation(self):
        for source in (None, [], {}, {'metadata': None}, {'metadata': []}):
            before = encoded(source)
            self.assertFalse(migrate_schema_4_to_5(source).succeeded)
            self.assertEqual(before, encoded(source))
        before = encoded(self.world)
        with self.assertRaises(ValueError):
            preview_purchase(self.world, airline_id=[], model_id=self.models[0]['model_id'],
                catalog_version=VERSION, delivery_airport_id=self.airports['MNL'])
        with self.assertRaises(ValueError):
            self.preview(delivery_airport_id=[])
        self.assertEqual(before, encoded(self.world))


if __name__ == '__main__':
    unittest.main()
