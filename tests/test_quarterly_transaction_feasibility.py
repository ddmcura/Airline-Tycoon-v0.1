"""B3A isolated architecture proofs; no runtime registration or certificate.

Synthetic handlers illustrate prefix/replay semantics, not shared eligibility.
The actual quarterly Completion probe retains full independent validation and
deliberately does not admit the legacy flight certificate for quarterly mode.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch

import game.world_state  # Keep the pre-existing utility-first import issue separate.
from game.world_state import validate_world, flight_transition_validation as flight_proof
from game.world_state.quarterly_consumers import valid_quarterly_lineage
from game.simulation import kernel
from game.simulation.candidate_ownership import CandidateOwnership, ReadOnlyDict, require_predecessor
from tests import test_quarterly_backend as fixtures

encoded = fixtures.encoded


class QuarterlyTransactionFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, _, _, cls.airline, *_ = fixtures.QuarterlyBackendTests.fixture()
        cls.inflight = deepcopy(cls.base)
        result = kernel.process_events_through(cls.inflight, '2027-01-02T01:00:00Z')
        if not result.succeeded:
            raise AssertionError(result)
        cls.event = min(cls.inflight['world_state']['pending_events'].values(), key=kernel._event_key)
        if cls.event['event_type'] != 'STAGE1_FLIGHT_COMPLETION':
            raise AssertionError('fixture must stop before a real quarterly Completion')

    def setUp(self):
        self.world = deepcopy(self.inflight)
        self.before = encoded(self.world)
        self.assertTrue(validate_world(self.world).is_valid)

    def synthetic_pair(self, effects=None):
        world = deepcopy(self.base)
        ids = [kernel.schedule_event(world, event_type=name,
            due_at_utc=world['simulation']['time_utc'], owner_type='airline',
            owner_id=self.airline, priority=80)
            for name in ('B3A_PROOF_PASS', 'B3A_PROOF_FAIL')]
        registry = kernel.EventHandlerRegistry()
        def first(context):
            if effects is not None:
                effects.append('external effect')
        def fail(context):
            raise RuntimeError('isolated proof failure')
        registry.register('B3A_PROOF_PASS', first)
        registry.register('B3A_PROOF_FAIL', fail)
        self.assertTrue(validate_world(world).is_valid)
        return world, ids, registry

    def test_whole_batch_rollback_loses_the_strict_successful_prefix(self):
        source, ids, registry = self.synthetic_pair()
        reference = deepcopy(source)
        result = kernel.process_events_through(reference, reference['simulation']['time_utc'], registry=registry)
        self.assertEqual(result.completed_event_ids, (ids[0],))
        self.assertEqual(result.failure.event_id, ids[1])
        speculative = deepcopy(source)
        self.assertIsNone(kernel._execute_event(speculative, ids[0], registry)[1])
        self.assertIsNotNone(kernel._execute_event(speculative, ids[1], registry)[1])
        # Discarding the whole candidate leaves an earlier visible boundary.
        self.assertNotEqual(encoded(source), encoded(reference))
        self.assertIn(ids[0], source['world_state']['pending_events'])
        self.assertIn(ids[0], reference['world_state']['event_history'])

    def test_strict_reselection_recovers_a_pure_synthetic_prefix(self):
        source, ids, registry = self.synthetic_pair()
        reference = deepcopy(source)
        expected = kernel.process_events_through(reference, reference['simulation']['time_utc'], registry=registry)
        speculative = deepcopy(source)
        for event_id in ids:
            if kernel._execute_event(speculative, event_id, registry)[1] is not None:
                break
        # Rebuild from committed source, not speculative IDs/cursors/counters.
        actual = kernel.process_events_through(source, source['simulation']['time_utc'], registry=registry)
        self.assertEqual(actual, expected)
        self.assertEqual(encoded(source), encoded(reference))
        self.assertTrue(validate_world(source).is_valid)

    def test_replaying_an_uncertified_external_effect_is_unsafe(self):
        effects = []
        source, ids, registry = self.synthetic_pair(effects)
        speculative = deepcopy(source)
        kernel._execute_event(speculative, ids[0], registry)
        kernel._execute_event(speculative, ids[1], registry)
        kernel.process_events_through(source, source['simulation']['time_utc'], registry=registry)
        self.assertEqual(effects, ['external effect', 'external effect'])
        contract = registry.execution_contract_for('B3A_PROOF_PASS')
        self.assertFalse(contract.permits_shared(registry.handler_for('B3A_PROOF_PASS'), 9, shadow=False))

    def test_shallow_world_copy_does_not_isolate_nested_lineage(self):
        speculative = dict(self.world)
        itinerary = next(iter(speculative['world_state']['itineraries'].values()))
        itinerary['quarterly_lineage']['revision'] = True
        self.assertNotEqual(encoded(self.world), self.before)
        self.assertFalse(validate_world(self.world).is_valid)

    def test_capsule_protects_nested_booking_publication_and_finance_reads(self):
        working = deepcopy(self.world)
        owner = CandidateOwnership(working)
        try:
            cap = owner.begin({})
            state = cap.envelope['world_state']
            itinerary = next(iter(state['itineraries'].values()))
            plan = next(iter(state['weekly_plans'].values()))
            account = next(iter(state['financial_accounts'].values()))
            with self.assertRaises(ValueError):
                itinerary['quarterly_lineage']['revision'] = True
            with self.assertRaises(ValueError):
                plan['revisions'][str(plan['current_revision'])]['slots'].append({})
            with self.assertRaises(ValueError):
                account['currency'] = 'EUR'
            self.assertEqual(encoded(working), self.before)
        finally:
            owner.close()

    def test_read_projection_detaches_without_repairing_lineage_types(self):
        working = deepcopy(self.world)
        owner = CandidateOwnership(working)
        try:
            cap = owner.begin({})
            protected = next(iter(cap.envelope['world_state']['itineraries'].values()))['quarterly_lineage']
            self.assertFalse(valid_quarterly_lineage(protected))
            projection = deepcopy(protected)
            self.assertIs(type(projection), dict)
            self.assertTrue(valid_quarterly_lineage(projection))
            for value in (True, False, 1.0, '1', None, -1, 0):
                altered = deepcopy(projection)
                altered['revision'] = value
                self.assertFalse(valid_quarterly_lineage(altered))
            projection['revision'] = True
            self.assertEqual(encoded(working), self.before)
        finally:
            owner.close()

    def test_json_alias_ownership_checks_do_not_certify_domain_validity(self):
        working = deepcopy(self.world)
        next(iter(working['world_state']['itineraries'].values()))['quarterly_lineage']['revision'] = True
        # Boolean is valid JSON and introduces no mutable alias.
        owner = CandidateOwnership(working)
        try:
            self.assertFalse(validate_world(working).is_valid)
        finally:
            owner.close()

    def test_current_quarterly_completion_rejects_legacy_certificate(self):
        self.assertFalse(flight_proof.supports_completion(self.world, self.event))
        reference = deepcopy(self.world)
        self.assertTrue(kernel.process_next_event(reference).succeeded)
        self.assertTrue(validate_world(reference).is_valid)
        working = deepcopy(self.world)
        owner = CandidateOwnership(working)
        try:
            cap = owner.begin(flight_proof.completion_ownership(working, self.event['event_id']))
            before = kernel._event_contract_witness(working)
            outcome, failure, generated = kernel._apply_handler_candidate(before,
                cap.envelope, self.event['event_id'],
                kernel.DEFAULT_EVENT_HANDLERS.handler_for(self.event['event_type']))
            self.assertIsNone(outcome)
            self.assertEqual(failure.code, 'HANDLER_FAILED')
            self.assertIn('does not match exact flight lineage', failure.message)
            self.assertEqual(generated, ())
            self.assertEqual(encoded(working), self.before)
            self.assertEqual(encoded(self.world), self.before)
        finally:
            owner.close()

    def test_foreign_and_expired_predecessor_cannot_grant_certification(self):
        working = deepcopy(self.world)
        owner = CandidateOwnership(working)
        cap = owner.begin({})
        with self.assertRaises(ValueError):
            require_predecessor(cap, deepcopy(working))
        require_predecessor(cap, working)
        owner.close()
        with self.assertRaises(ValueError):
            require_predecessor(cap, working)
        with self.assertRaises(ValueError):
            cap.checked_outputs()

    def test_test_only_plain_read_bridge_matches_actual_strict_completion(self):
        reference = deepcopy(self.world)
        self.assertTrue(kernel.process_next_event(reference).succeeded)
        working = deepcopy(self.world)
        self.assertTrue(validate_world(working).is_valid)
        owner = CandidateOwnership(working)
        original = ReadOnlyDict.__getitem__
        projections = []
        def project_lineage(view, key):
            value = original(view, key)
            if key == 'quarterly_lineage' and type(value) is ReadOnlyDict:
                value = deepcopy(value)
                projections.append(value)
            return value
        try:
            cap = owner.begin(flight_proof.completion_ownership(working, self.event['event_id']))
            before = kernel._event_contract_witness(working)
            # This lexical mock is NOT a production read API or domain certificate.
            with patch.object(ReadOnlyDict, '__getitem__', project_lineage):
                outcome, failure, generated = kernel._apply_handler_candidate(before,
                    cap.envelope, self.event['event_id'],
                    kernel.DEFAULT_EVENT_HANDLERS.handler_for(self.event['event_type']))
                self.assertIsNone(failure)
                self.assertEqual(outcome, 'COMPLETED')
                self.assertEqual(generated, ())
                owner.publish(working, cap)
            self.assertIs(ReadOnlyDict.__getitem__, original)
            self.assertTrue(projections)
            self.assertTrue(validate_world(working).is_valid)
            self.assertEqual(encoded(working), encoded(reference))
        finally:
            owner.close()
        # Retained projections cannot mutate source, result, manifests or journals.
        for projection in projections:
            projection['revision'] = True
        self.assertEqual(encoded(self.world), self.before)
        self.assertEqual(encoded(working), encoded(reference))
        self.assertTrue(validate_world(working).is_valid)

    def test_plain_projection_preserves_malformed_source_instead_of_repairing_it(self):
        working = deepcopy(self.world)
        itinerary = next(iter(working['world_state']['itineraries'].values()))
        itinerary['quarterly_lineage']['revision'] = True
        self.assertFalse(validate_world(working).is_valid)
        owner = CandidateOwnership(working)
        try:
            cap = owner.begin({})
            protected = cap.envelope['world_state']['itineraries'][itinerary['itinerary_id']]['quarterly_lineage']
            projection = deepcopy(protected)
            self.assertIs(projection['revision'], True)
            self.assertFalse(valid_quarterly_lineage(projection))
        finally:
            owner.close()


if __name__ == '__main__':
    unittest.main()
