"""B3B isolated Completion proof and negative feasibility evidence."""
from copy import deepcopy
import json
import time
import tracemalloc
import unittest
from unittest.mock import patch

import game.world_state
from game.world_state import validate_world, flight_transition_validation as footprint
from game.world_state.flight_proof_witness import protected_bytes, mutable_alias_error
from game.aircraft_operations import fulfilment
from game.simulation import kernel
from game.simulation.candidate_ownership import CandidateOwnership, ReadOnlyDict
from tests import test_quarterly_backend as fixtures
from tests.quarterly_completion_certificate import CompletionCertificate, record_count
from tests.resolution_oracle import canonical_world, save_reload
from tests.test_quarterly_booking_validation import reference_validation


def shadow(source, event_id):
    """B3A lexical bridge only. Always private, detached, and capability-closed."""
    working = deepcopy(source)
    owner = CandidateOwnership(working)
    original = ReadOnlyDict.__getitem__
    projections = []
    def read(view, key):
        value = original(view, key)
        if key == 'quarterly_lineage' and type(value) is ReadOnlyDict:
            value = deepcopy(value)
            projections.append(value)
        return value
    try:
        cap = owner.begin(footprint.completion_ownership(working, event_id))
        with patch.object(ReadOnlyDict, '__getitem__', read):
            outcome, failure, generated = kernel._apply_handler_candidate(
                kernel._event_contract_witness(working), cap.envelope, event_id,
                kernel.DEFAULT_EVENT_HANDLERS.handler_for('STAGE1_FLIGHT_COMPLETION'))
            if failure is None:
                owner.publish(working, cap)
        return working, outcome, failure, generated, projections
    finally:
        owner.close()


class QuarterlyCompletionCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = fixtures.QuarterlyBackendTests.fixture()[0]
        result = kernel.process_events_through(cls.source, '2027-01-02T01:00:00Z')
        assert result.succeeded, result
        cls.event = min(cls.source['world_state']['pending_events'].values(), key=kernel._event_key)
        cls.event_id = cls.event['event_id']
        cls.reference = deepcopy(cls.source)
        assert kernel.process_next_event(cls.reference).succeeded
        cls.candidate, outcome, failure, generated, cls.projections = shadow(cls.source, cls.event_id)
        assert outcome == 'COMPLETED' and failure is None and generated == ()
        assert canonical_world(cls.candidate) == canonical_world(cls.reference)
        cls.binding = CompletionCertificate(cls.source, cls.event_id)
        cls.adversarial_results = []

    @classmethod
    def tearDownClass(cls):
        import os
        if os.environ.get('AT_B3B_MEASURE') == '1':
            print('B3B_ADVERSARIAL ' + json.dumps(cls.adversarial_results))

    def certificate(self):
        # Detached witness bytes are immutable. Each attempt gets its own lifetime.
        # Capture is separately exercised and measured; no reused validity boolean.
        result = object.__new__(CompletionCertificate)
        result.__dict__ = dict(self.binding.__dict__)
        return result

    def test_actual_shadow_matches_independent_strict_complete_world(self):
        self.assertTrue(self.certificate().verify(self.source, self.candidate, self.event_id))
        self.assertEqual(self.candidate, self.reference)
        self.assertEqual(canonical_world(self.candidate), canonical_world(self.reference))
        self.assertTrue(validate_world(self.candidate).is_valid)
        self.assertTrue(reference_validation(self.candidate).is_valid)
        self.assertEqual(validate_world(self.candidate), reference_validation(self.candidate))
        self.assertEqual(self.binding.booking_ids,
                         tuple(self.candidate['world_state']['flight_results'][self.binding.flight_id]['source_booking_ids']))
        self.assertGreater(len(self.binding.booking_ids), 0)

    def test_retained_detached_projections_cannot_change_any_world(self):
        source_bytes = protected_bytes(self.source)
        candidate_bytes = protected_bytes(self.candidate)
        for projection in self.projections:
            projection['revision'] = True
        self.assertEqual(source_bytes, protected_bytes(self.source))
        self.assertEqual(candidate_bytes, protected_bytes(self.candidate))

    def test_source_mutation_and_foreign_equal_world_expire_certificate(self):
        with self.assertRaisesRegex(ValueError, 'different source'):
            self.certificate().verify(deepcopy(self.source), self.candidate, self.event_id)
        changed = deepcopy(self.source)
        cert = CompletionCertificate(changed, self.event_id)
        next(iter(changed['world_state']['itineraries'].values()))['quarterly_lineage']['revision'] = True
        with self.assertRaisesRegex(ValueError, 'source changed'):
            cert.verify(changed, self.candidate, self.event_id)
        with self.assertRaisesRegex(ValueError, 'consumed'):
            cert.verify(changed, self.candidate, self.event_id)

    def test_consumed_event_and_generated_event_mismatch(self):
        cert = self.certificate()
        self.assertTrue(cert.verify(self.source, self.candidate, self.event_id))
        with self.assertRaisesRegex(ValueError, 'consumed'):
            cert.verify(self.source, self.candidate, self.event_id)
        with self.assertRaisesRegex(ValueError, 'different source or event'):
            self.certificate().verify(self.source, self.candidate, 'event-foreign')
        with self.assertRaisesRegex(ValueError, 'generate no events'):
            self.certificate().verify(self.source, self.candidate, self.event_id, ('event-extra',))

    def test_source_and_cross_world_aliases_cannot_hide_behind_equal_bytes(self):
        source = deepcopy(self.source)
        cert = CompletionCertificate(source, self.event_id)
        before = protected_bytes(source)
        state = source['world_state']
        state['active_aircraft_operations'][cert.flight_id]['quarterly_lineage'] = state['dated_flights'][cert.flight_id]['quarterly_lineage']
        self.assertEqual(protected_bytes(source), before)
        self.assertFalse(reference_validation(source).is_valid)
        with self.assertRaisesRegex(ValueError, 'alias'):
            cert.verify(source, self.candidate, self.event_id)
        candidate = deepcopy(self.candidate)
        key = self.binding.itinerary_ids[0]
        candidate['world_state']['itineraries'][key] = self.source['world_state']['itineraries'][key]
        self.assertEqual(protected_bytes(candidate), protected_bytes(self.candidate))
        # Each world is valid alone, but source/result isolation is violated.
        self.assertTrue(reference_validation(candidate).is_valid)
        with self.assertRaisesRegex(ValueError, 'cross-world alias'):
            self.certificate().verify(self.source, candidate, self.event_id)

    def test_save_load_requires_fresh_binding_and_preserves_exact_outcome(self):
        restored = save_reload(self.source)
        self.assertEqual(canonical_world(restored), canonical_world(self.source))
        with self.assertRaises(ValueError):
            self.certificate().verify(restored, self.candidate, self.event_id)
        cert = CompletionCertificate(restored, self.event_id)
        candidate, _, failure, generated, _ = shadow(restored, self.event_id)
        self.assertIsNone(failure)
        self.assertTrue(cert.verify(restored, candidate, self.event_id, generated))
        reference = deepcopy(restored)
        self.assertTrue(kernel.process_next_event(reference).succeeded)
        self.assertEqual(canonical_world(save_reload(candidate)), canonical_world(save_reload(reference)))

    def test_injected_failure_preserves_source_and_retry_matches_strict(self):
        source = deepcopy(self.source)
        before = protected_bytes(source)
        with patch.object(fulfilment, 'settlement_records', side_effect=RuntimeError('B3B settlement interrupted')):
            candidate, outcome, failure, generated, _ = shadow(source, self.event_id)
            strict = deepcopy(source)
            strict_outcome, strict_failure, strict_generated = kernel._execute_event(
                strict, self.event_id, kernel.DEFAULT_EVENT_HANDLERS)
        self.assertIsNone(outcome)
        self.assertEqual(failure, strict_failure)
        self.assertEqual(generated, strict_generated)
        self.assertEqual(protected_bytes(strict), before)
        self.assertEqual(protected_bytes(source), before)
        # No failure candidate may be certified or committed; retry starts fresh.
        with self.assertRaises(ValueError):
            CompletionCertificate(source, self.event_id).verify(source, candidate, self.event_id)
        cert = CompletionCertificate(source, self.event_id)
        retried, _, failure, generated, _ = shadow(source, self.event_id)
        self.assertIsNone(failure)
        self.assertTrue(cert.verify(source, retried, self.event_id, generated))
        self.assertTrue(kernel.process_next_event(strict).succeeded)
        self.assertEqual(canonical_world(retried), canonical_world(strict))

    def test_full_kernel_failure_fence_is_unchanged_not_locally_certified(self):
        first, second = deepcopy(self.source), deepcopy(self.source)
        with patch.object(fulfilment, 'settlement_records', side_effect=RuntimeError('B3B settlement interrupted')):
            a = kernel.process_next_event(first)
            b = kernel.process_next_event(second)
        self.assertFalse(a.succeeded)
        self.assertEqual(a, b)
        self.assertEqual(canonical_world(first), canonical_world(second))
        self.assertEqual(canonical_world(first), canonical_world(self.source))
        self.assertTrue(validate_world(first).is_valid)
        self.assertIn(self.event_id, first['world_state']['pending_events'])
        fresh = CompletionCertificate(first, self.event_id)
        candidate, _, failure, generated, _ = shadow(first, self.event_id)
        self.assertIsNone(failure)
        self.assertTrue(fresh.verify(first, candidate, self.event_id, generated))
        self.assertTrue(kernel.process_next_event(second).succeeded)
        self.assertEqual(canonical_world(candidate), canonical_world(second))

    def test_malformed_source_never_enters_certificate(self):
        for value in (True, False, 1.0, '1', None, 0, -1, 10**9):
            with self.subTest(value=repr(value)):
                source = deepcopy(self.source)
                source['world_state']['itineraries'][self.binding.itinerary_ids[0]]['quarterly_lineage']['revision'] = value
                self.assertFalse(validate_world(source).is_valid)
                self.assertFalse(reference_validation(source).is_valid)
                with self.assertRaises(ValueError):
                    CompletionCertificate(source, self.event_id)

    def test_legacy_flight_remains_outside_quarterly_certificate(self):
        from tests.flight_fixtures import flight_world, window
        legacy = flight_world(1)
        window(legacy, 'completion')
        event = min(legacy['world_state']['pending_events'].values(), key=kernel._event_key)
        self.assertTrue(footprint.supports_completion(legacy, event))
        with self.assertRaises(ValueError):
            CompletionCertificate(legacy, event['event_id'])
        self.assertTrue(kernel.process_next_event(legacy).succeeded)
        self.assertTrue(validate_world(legacy).is_valid)

    def test_opt_in_component_measurements(self):
        # Small real workload, not the expensive retained advancement benchmark.
        import os
        if os.environ.get('AT_B3B_MEASURE') != '1':
            self.skipTest('opt-in diagnostic measurement')
        samples = []
        for _ in range(3):
            start = time.perf_counter()
            cert = CompletionCertificate(self.source, self.event_id)
            construction = time.perf_counter() - start
            start = time.perf_counter()
            cert.verify(self.source, self.candidate, self.event_id)
            verification = time.perf_counter() - start
            start = time.perf_counter()
            validate_world(self.candidate)
            full = time.perf_counter() - start
            samples.append(dict(construction_s=construction, verification_s=verification, full_validation_s=full))
        tracemalloc.start()
        cert = CompletionCertificate(self.source, self.event_id)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print('B3B_MEASUREMENT ' + json.dumps(dict(samples=samples,
              records=record_count(self.source), selected_bookings=len(cert.booking_ids),
              snapshot_bytes=len(cert.source_bytes)+len(cert.expected_bytes),
              retained_bytes=retained, peak_bytes=peak), sort_keys=True))


def mutation_test(name, mutate):
    def test(self):
        candidate = deepcopy(self.candidate)
        mutate(candidate, self.binding)
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.certificate().verify(self.source, candidate, self.event_id)
        result = validate_world(candidate)
        detailed = reference_validation(candidate)
        self.assertEqual(result, detailed)
        if name == 'mutable_alias':
            # Value equality cannot establish ownership: this case deliberately
            # has identical bytes but shares mutable authority between records.
            self.assertEqual(protected_bytes(candidate), protected_bytes(self.reference))
            self.assertIsNotNone(mutable_alias_error(candidate))
        else:
            self.assertNotEqual(protected_bytes(candidate), protected_bytes(self.reference))
        self.adversarial_results.append((name, 'detected', 'reject' if not detailed.is_valid else 'valid different transition'))
    return test


def result_row(w, c):
    return w['world_state']['flight_results'][c.flight_id]


MUTATIONS = {
    'wrong_aircraft': lambda w,c: result_row(w,c).__setitem__('actual_aircraft_id', 'aircraft-foreign'),
    'wrong_flight': lambda w,c: result_row(w,c).__setitem__('dated_flight_id', 'dated_flight-foreign'),
    'wrong_timestamp': lambda w,c: result_row(w,c).__setitem__('completed_at_utc', '2027-01-02T02:40:01Z'),
    'wrong_position': lambda w,c: w['world_state']['aircraft'][c.aircraft_id].__setitem__('current_airport_id', None),
    'missing_result': lambda w,c: w['world_state']['flight_results'].pop(c.flight_id),
    'duplicate_result': lambda w,c: w['world_state']['flight_results'].__setitem__('dated_flight-duplicate', deepcopy(result_row(w,c))),
    'missing_manifest': lambda w,c: result_row(w,c)['source_booking_ids'].pop(),
    'duplicate_manifest': lambda w,c: result_row(w,c)['source_booking_ids'].append(result_row(w,c)['source_booking_ids'][0]),
    'passenger_total': lambda w,c: result_row(w,c).__setitem__('carried_passenger_count', result_row(w,c)['carried_passenger_count']+1),
    'booking_reference': lambda w,c: w['world_state']['bookings'][c.booking_ids[0]].__setitem__('itinerary_id', 'itinerary-missing'),
    'itinerary_lineage': lambda w,c: w['world_state']['itineraries'][c.itinerary_ids[0]]['quarterly_lineage'].__setitem__('revision', -1),
    'boolean_lineage': lambda w,c: w['world_state']['itineraries'][c.itinerary_ids[0]]['quarterly_lineage'].__setitem__('revision', True),
    'false_lineage': lambda w,c: result_row(w,c)['quarterly_lineage'].__setitem__('revision', False),
    'float_lineage': lambda w,c: result_row(w,c)['quarterly_lineage'].__setitem__('slot_number', 1.0),
    'both_side_lineage': lambda w,c: [row['quarterly_lineage'].__setitem__('revision', True) for row in (result_row(w,c), w['world_state']['dated_flights'][c.flight_id], w['world_state']['itineraries'][c.itinerary_ids[0]])],
    'flight_only_lineage': lambda w,c: w['world_state']['dated_flights'][c.flight_id]['quarterly_lineage'].__setitem__('slot_number', True),
    'witness_boolean_lineage': lambda w,c: result_row(w,c)['booking_witnesses'][0]['quarterly_lineage'].__setitem__('revision', True),
    'witness_float_lineage': lambda w,c: result_row(w,c)['booking_witnesses'][0]['quarterly_lineage'].__setitem__('slot_number', 1.0),
    'missing_lineage_key': lambda w,c: result_row(w,c)['quarterly_lineage'].pop('revision'),
    'extra_lineage_key': lambda w,c: result_row(w,c)['quarterly_lineage'].__setitem__('extra', 1),
    'financial_balance': lambda w,c: next(iter(w['world_state']['financial_accounts'].values())).__setitem__('balance_minor', 0),
    'financial_journal_amount': lambda w,c: w['world_state']['transactions'][c.transaction_id]['entries'][0].__setitem__('amount_minor', 1),
    'missing_transaction': lambda w,c: w['world_state']['transactions'].pop(c.transaction_id),
    'duplicate_transaction': lambda w,c: w['world_state']['transactions'].__setitem__('transaction-duplicate', deepcopy(w['world_state']['transactions'][c.transaction_id])),
    'queue_delete': lambda w,c: w['world_state']['pending_events'].pop(next(iter(w['world_state']['pending_events']))),
    'queue_insert': lambda w,c: w['world_state']['pending_events'].__setitem__('event-duplicate', deepcopy(next(iter(w['world_state']['pending_events'].values())))),
    'queue_order_key': lambda w,c: next(iter(w['world_state']['pending_events'].values()))['order_key'].__setitem__(0, 101),
    'queue_dictionary_order': lambda w,c: w['world_state'].__setitem__('pending_events', dict(reversed(list(w['world_state']['pending_events'].items())))),
    'unrelated_nested_list': lambda w,c: next(iter(w['world_state']['weekly_plans'].values()))['revisions']['1']['slots'].append({}),
    'unrelated_ui_value': lambda w,c: w['ui_state'].__setitem__('selected_screen', 'B3B diagnostic'),
    'mutable_alias': lambda w,c: result_row(w,c).__setitem__('quarterly_lineage', w['world_state']['dated_flights'][c.flight_id]['quarterly_lineage']),
}
for _name, _mutation in MUTATIONS.items():
    setattr(QuarterlyCompletionCertificateTests, 'test_mutation_' + _name, mutation_test(_name, _mutation))


if __name__ == '__main__':
    unittest.main()
