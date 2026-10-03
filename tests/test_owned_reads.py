"""Stage 2 ownership, immutable lookup, invalidation and exact-world gates."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.aircraft_operations import (
    project_airline_fleet, project_airline_flights, project_recent_flight_results,
)
from game.aircraft_operations.projections import _build_operations_lookup
from game.aircraft_operations.fulfilment import (
    build_confirmed_carriage_manifest, _build_confirmed_carriage_manifest,
)
from game.simulation import kernel
from game.world_state import validate_world
from tests.resolution_oracle import canonical_world, strict_until
from tests.test_simulation_resolver import ph_world, published_pair


class OwnedReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = published_pair(ph_world(), continuous=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='at-owned-tests-')
        self.addCleanup(self.temp.cleanup)
        self.session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        self.session.world = deepcopy(self.seed)
        self.session.career_id = self.session.save_store.new_career_id()
        self.session._reset_autosave_clocks()

    def assert_reads(self):
        session = self.session
        before = canonical_world(session.world)
        for read, public in ((session.fleet,project_airline_fleet),
                             (session.flights,project_airline_flights),
                             (session.finances,project_recent_flight_results)):
            self.assertEqual(read(),public(session.world,session.airline_id))
            self.assertEqual(read(),public(session.world,session.airline_id))
        self.assertEqual(before,canonical_world(session.world))

    def test_foreign_binding_validates_once_then_owned_reads_need_no_gate(self):
        with patch('app.session.validate_world', wraps=validate_world) as gate:
            self.session.fleet()
            self.session.flights()
            self.session.finances()
            self.session.flights()
        self.assertEqual(gate.call_count,1)
        self.assert_reads()

    def test_new_game_uses_construction_proof(self):
        self.session.new_game('CEO','Owned Air','MNL')
        with patch('app.session.validate_world',side_effect=AssertionError('repeated read gate')):
            self.session.fleet()
            self.session.flights()
            self.session.finances()
        self.assertTrue(validate_world(self.session.world).is_valid)

    def test_public_invalid_world_never_acquires_read_trust(self):
        invalid = deepcopy(self.seed)
        invalid['metadata']['save_schema_version'] = -1
        self.session.world = invalid
        for public in (project_airline_fleet,project_airline_flights,project_recent_flight_results):
            self.assertIsNone(public(invalid,self.session.airline_id))
        for read in (self.session.fleet,self.session.flights,self.session.finances):
            self.assertIsNone(read())
        self.assertIsNone(self.session._read_views)

    def test_public_validation_remains_on_repeated_arbitrary_reads(self):
        with patch('game.aircraft_operations.projections.validate_world',wraps=validate_world) as gate:
            project_airline_fleet(self.session.world,self.session.airline_id)
            project_airline_fleet(self.session.world,self.session.airline_id)
        self.assertEqual(gate.call_count,2)

    def test_projection_outputs_cannot_poison_next_read_or_authority(self):
        self.assert_reads()
        before = canonical_world(self.session.world)
        fleet = self.session.fleet()
        fleet[0]['status'] = 'POISON'
        flights = self.session.flights()
        flights[0]['next_lifecycle_event']['event_type'] = 'POISON'
        finance = self.session.finances()
        finance['cash_minor'] = -999
        self.assert_reads()
        self.assertEqual(before,canonical_world(self.session.world))

    def test_immutable_source_ids_and_same_manifest_order(self):
        lookup = _build_operations_lookup(self.session.world)
        with self.assertRaises(TypeError):
            lookup.booking_ids_by_flight['bad'] = ('bad',)
        with self.assertRaises(TypeError):
            lookup.next_event_id_by_flight['bad'] = 'bad'
        self.session.advance_to('2026-09-02T00:00:00Z')
        lookup = _build_operations_lookup(self.session.world)
        for flight_id in self.session.world['world_state']['dated_flights']:
            self.assertEqual(build_confirmed_carriage_manifest(self.session.world,flight_id),
                _build_confirmed_carriage_manifest(self.session.world,flight_id,
                    booking_ids=lookup.booking_ids_by_flight.get(flight_id,())))
        self.assert_reads()

    def test_stale_context_from_another_world_rebuilds(self):
        self.session.flights()
        stale = self.session._read_views
        self.session.new_game('Other CEO','Other Air','CEB')
        self.session._read_views = stale  # Deliberate stale/poisoned owner association.
        with patch('app.session.validate_world',wraps=validate_world) as gate:
            self.assert_reads()
        self.assertEqual(gate.call_count,1)
        self.assertIsNot(self.session._read_views,stale)

    def test_subtree_replacement_revalidates_instead_of_reusing_cache(self):
        self.session.flights()
        old = self.session._read_views
        self.session.world['world_state'] = deepcopy(self.session.world['world_state'])
        with patch('app.session.validate_world',wraps=validate_world) as gate:
            self.assert_reads()
        self.assertEqual(gate.call_count,1)
        self.assertIsNot(self.session._read_views,old)

    def test_invalid_subtree_replacement_fails_closed(self):
        self.session.flights()
        state = deepcopy(self.session.world['world_state'])
        state['aircraft'].clear()
        self.session.world['world_state'] = state
        self.assertIsNone(self.session.flights())
        self.assertIsNone(self.session._read_views)

    def test_malformed_foreign_roots_fail_closed(self):
        for root in ('simulation','world_state','metadata'):
            with self.subTest(root=root):
                self.session.world = deepcopy(self.seed)
                self.session.flights()
                self.session.world[root] = None
                self.assertIsNone(self.session.fleet())
                self.assertIsNone(self.session.flights())
                self.assertIsNone(self.session.finances())
                self.assertIsNone(self.session._read_views)

    def test_external_validated_command_replacement_detected(self):
        self.session.flights()
        result = kernel.process_next_event(self.session.world)
        self.assertTrue(result.succeeded)
        with patch('app.session.validate_world',wraps=validate_world) as gate:
            self.assert_reads()
        self.assertEqual(gate.call_count,1)

    def test_revision_change_and_disposal_rebuild_exactly(self):
        self.session.flights()
        old = self.session._read_views
        self.session.progression_revision += 1
        self.assert_reads()
        self.assertIsNot(self.session._read_views,old)
        self.session._read_views = None
        self.assert_reads()

    def test_pages_bounded_and_parameter_validation_cannot_hit_wrong_key(self):
        for offset in range(12):
            self.session.flights(offset=offset,limit=1)
        self.assertEqual(len(self.session._read_views._pages),8)
        for limit in (-1,True,101,1.5):
            for read in (self.session.fleet,self.session.flights):
                with self.assertRaises(ValueError):
                    read(limit=limit)
        self.assert_reads()

    def test_save_load_and_other_career_rebuild_no_derived_state_saved(self):
        self.assert_reads()
        old = self.session._read_views
        self.session.save_manual()
        career = self.session.career_id
        wrapper = json.loads((Path(self.temp.name)/career/'manual.json').read_text())
        self.assertEqual(wrapper['world'],self.session.world)
        text = canonical_world(wrapper['world'])
        for key in ('_read_views','_pages','booking_ids_by_flight','next_event_id_by_flight'):
            self.assertNotIn(key,text)
        self.session.new_game('Second','Second Air','CEB')
        self.session.flights()
        self.session.load_saved(career)
        self.assertIsNot(self.session._read_views,old)
        self.assertEqual(self.session.world['simulation']['clock_state'],'PAUSED')
        with patch('app.session.validate_world',side_effect=AssertionError('load proof lost')):
            self.session.fleet()
            self.session.flights()
            self.session.finances()
        self.assert_reads()

    def test_reads_between_steps_checkpoint_roll_departure_completion_exact_oracle(self):
        expected = deepcopy(self.seed)
        target = '2026-09-07T04:00:00Z'
        self.assertTrue(strict_until(expected,target).succeeded)
        self.session.flights()  # Own the valid input, then force repeated cache churn.
        self.session.begin_advance_to(target)
        boundaries = 0
        while self.session.advancing:
            self.session.advance_tick()
            self.assert_reads()
            self.session._read_views = None
            self.assert_reads()
            boundaries += 1
        self.assertGreater(boundaries,8)
        self.assertEqual(canonical_world(self.session.world),canonical_world(expected))

    def test_payment_and_real_expiry_refresh_finance_and_fleet_exactly(self):
        from datetime import timedelta
        from game.world_state.timestamps import format_utc, parse_canonical_utc
        self.session.new_game('Lease CEO','Lease Air','MNL')
        state = self.session.world['world_state']
        offer = state['aircraft_market_state']['active_lease_offer_ids'][0]
        base = state['airlines'][self.session.airline_id]['base_airport_ids'][0]
        aircraft_id = self.session.accept_lease(self.session.preview_lease(
            offer,'OPERATING_LEASE',1,base))
        contract = next(iter(self.session.world['world_state']['aircraft_contracts'].values()))
        expiry = contract['expires_at_utc']
        self.assert_reads()
        expected = deepcopy(self.session.world)
        target = '2026-10-01T00:00:01Z'
        self.assertTrue(strict_until(expected,target).succeeded)
        self.assertTrue(self.session.advance_to(target).result.succeeded)
        self.assert_reads()
        self.assertEqual(canonical_world(self.session.world),canonical_world(expected))
        before = format_utc(parse_canonical_utc(expiry)-timedelta(seconds=1))
        self.assertTrue(kernel.process_events_through(self.session.world,before,
                                                     max_generated_events=10000).succeeded)
        self.assert_reads()  # Foreign root-preserving event commits must rebind.
        expected = deepcopy(self.session.world)
        target = format_utc(parse_canonical_utc(expiry)+timedelta(seconds=1))
        self.assertTrue(strict_until(expected,target).succeeded)
        old = self.session._read_views
        self.assertTrue(self.session.advance_to(target).result.succeeded)
        self.assert_reads()
        self.assertIsNot(self.session._read_views,old)
        self.assertEqual(canonical_world(self.session.world),canonical_world(expected))
        self.assertNotIn(aircraft_id,[row['aircraft_id'] for row in self.session.fleet()])

    def test_foreign_clock_only_completion_and_same_time_events_rebuild(self):
        self.session.flights()
        before = self.session._read_views
        now = self.session.world['simulation']['time_utc']
        self.assertTrue(kernel.process_events_through(self.session.world,now).succeeded)
        self.assert_reads()
        self.assertIs(self.session._read_views,before)
        self.assertTrue(kernel.process_events_through(self.session.world,
                                                     '2026-09-01T00:00:01Z').succeeded)
        self.assert_reads()
        self.assertIsNot(self.session._read_views,before)

    def test_clock_only_explicit_advance_keeps_valid_session_proof(self):
        self.session.new_game('Clock CEO','Clock Air','MNL')
        self.session.flights()
        self.session.advance_seconds(1)
        with patch('app.session.validate_world',side_effect=AssertionError('lost commit proof')):
            self.session.fleet()
            self.session.flights()
            self.session.finances()
        self.assert_reads()

    def test_session_management_command_and_clock_controls_invalidate(self):
        self.session.new_game('Manager','Manager Air','MNL')
        self.session.fleet()
        old = self.session._read_views
        ports = {row['reference_code']:row['airport_id'] for row in self.session.airports()}
        aircraft = self.session.fleet()[0]['aircraft_id']
        draft = self.session.begin_scheduling(aircraft)
        draft.add_weekdays(ports['MNL'],ports['DVO'],('2026-09-07',),'08:00',
                           return_flight=True,fare_minor=11600)
        self.assertTrue(self.session.save_scheduling(draft,continuous=True).succeeded)
        self.assertIsNot(self.session._read_views,old)
        self.assert_reads()
        self.session.resume()
        self.assert_reads()
        self.session.runtime.credit_ns = 2_000_000_000
        self.session.pump()
        self.assert_reads()
        self.session.pause()
        self.assert_reads()
        self.session.leave_game()
        self.assertIsNone(self.session._read_views)
        self.assertIsNone(self.session.flights())


if __name__ == '__main__':
    unittest.main()
