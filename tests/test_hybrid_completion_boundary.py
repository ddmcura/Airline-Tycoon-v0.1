"""B3D decisive negative admission proof; never enable a local transaction."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import game.world_state
from game.world_state import validate_world
from game.world_state.flight_proof_witness import protected_bytes
from game.aircraft_operations import fulfilment
from game.simulation import kernel
from tests import test_quarterly_backend as fixtures
from tests.hybrid_completion_boundary import attempt_completion, selected_inputs, plausible_selected_facts
from tests.test_quarterly_booking_validation import reference_validation
from tests.resolution_oracle import canonical_world, save_reload


class HybridCompletionBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = fixtures.QuarterlyBackendTests.fixture()[0]
        assert kernel.process_events_through(cls.source, '2027-01-02T01:00:00Z').succeeded
        event = min(cls.source['world_state']['pending_events'].values(), key=kernel._event_key)
        cls.event_id, cls.flight_id = event['event_id'], event['owner_id']
        cls.operation = cls.source['world_state']['active_aircraft_operations'][cls.flight_id]
        cls.booking = cls.operation['source_booking_ids'][0]
        cls.itinerary = cls.source['world_state']['bookings'][cls.booking]['itinerary_id']
        selected = set(cls.operation['source_booking_ids'])
        cls.foreign_booking = next(key for key in cls.source['world_state']['bookings'] if key not in selected)
        cls.foreign_itinerary = cls.source['world_state']['bookings'][cls.foreign_booking]['itinerary_id']
        cls.frame = selected_inputs(cls.source)[0]
        cls.results = []

    def assert_rejected_world(self, world):
        source_bytes = protected_bytes(world)
        self.assertFalse(reference_validation(world).is_valid)
        expected = deepcopy(world)
        actual = attempt_completion(world)
        reference = kernel.process_next_event(expected)
        self.assertFalse(actual.local_admitted)
        self.assertFalse(actual.processing_result.succeeded)
        self.assertEqual(actual.processing_result, reference)
        self.assertEqual(canonical_world(world), canonical_world(expected))
        self.assertTrue(protected_bytes(world) == source_bytes)

    def test_unselected_invalid_lineage_is_indistinguishable_to_local_inputs(self):
        world = deepcopy(self.source)
        world['world_state']['itineraries'][self.foreign_itinerary]['quarterly_lineage']['revision'] = True
        frame, _ = selected_inputs(world)
        self.assertTrue(protected_bytes(frame) == protected_bytes(self.frame))
        self.assertTrue(plausible_selected_facts(frame))
        self.assert_rejected_world(world)

    def test_outside_scope_alias_is_indistinguishable_even_to_typed_values(self):
        world = deepcopy(self.source)
        state = world['world_state']
        other = next(key for key in state['itineraries']
                     if key not in {state['bookings'][bid]['itinerary_id'] for bid in self.operation['source_booking_ids']}
                     and key != self.foreign_itinerary
                     and state['itineraries'][key]['quarterly_lineage'] == state['itineraries'][self.foreign_itinerary]['quarterly_lineage'])
        before = protected_bytes(world)
        state['itineraries'][other]['quarterly_lineage'] = state['itineraries'][self.foreign_itinerary]['quarterly_lineage']
        self.assertTrue(protected_bytes(world) == before)
        self.assertTrue(protected_bytes(selected_inputs(world)[0]) == protected_bytes(self.frame))
        self.assert_rejected_world(world)

    def test_new_booking_association_cannot_be_proved_from_frozen_ids(self):
        world = deepcopy(self.source)
        world['world_state']['itineraries'][self.foreign_itinerary]['dated_flight_ids'] = [self.flight_id]
        self.assertTrue(protected_bytes(selected_inputs(world)[0]) == protected_bytes(self.frame))
        self.assert_rejected_world(world)

    def test_valid_reconciliation_change_is_not_in_selected_completion_frame(self):
        world = deepcopy(self.source)
        dispatch_id = next(key for key, event in world['world_state']['pending_events'].items()
                           if event['event_type'] == 'QUARTERLY_DISPATCH')
        del world['world_state']['pending_events'][dispatch_id]
        self.assertTrue(reference_validation(world).is_valid)
        self.assertTrue(protected_bytes(selected_inputs(world)[0]) == protected_bytes(self.frame))
        reference = deepcopy(world)
        actual = attempt_completion(world)
        self.assertEqual(actual.processing_result, kernel.process_next_event(reference))
        self.assertEqual(canonical_world(world), canonical_world(reference))
        self.assertFalse(actual.local_admitted)
        self.assertTrue(any(e['event_type'] == 'QUARTERLY_DISPATCH'
                            for e in world['world_state']['pending_events'].values()))
        control = deepcopy(self.source)
        self.assertTrue(kernel.process_next_event(control).succeeded)
        # Both source worlds are valid and have identical selected reads, but
        # reconciliation allocates a fresh event/cursor in only one command.
        self.assertNotEqual(canonical_world(world), canonical_world(control))

    def test_valid_completion_matches_strict_only_through_accounted_fallback(self):
        actual, reference = deepcopy(self.source), deepcopy(self.source)
        outcome = attempt_completion(actual)
        expected = kernel.process_next_event(reference)
        self.assertFalse(outcome.local_admitted)
        self.assertIn('NO_GO', outcome.reason)
        self.assertEqual(outcome.processing_result, expected)
        self.assertEqual(canonical_world(actual), canonical_world(reference))
        self.assertTrue(reference_validation(actual).is_valid)

    def test_selected_projection_is_detached_but_not_source_ownership(self):
        source_bytes = protected_bytes(self.source)
        frame, _ = selected_inputs(self.source)
        frame['itineraries'][self.itinerary]['quarterly_lineage']['revision'] = True
        self.assertTrue(protected_bytes(self.source) == source_bytes)
        source = deepcopy(self.source)
        old = selected_inputs(source)[0]
        source['world_state']['itineraries'][self.foreign_itinerary]['quarterly_lineage']['revision'] = 1.0
        self.assertTrue(protected_bytes(selected_inputs(source)[0]) == protected_bytes(old))
        self.assert_rejected_world(source)

    def test_provider_mutation_exception_and_custom_handler_are_not_invoked(self):
        world = deepcopy(self.source)
        before = protected_bytes(world)
        called = []
        def provider():
            called.append(True)
            world['simulation']['time_utc'] = '2027-01-01T00:00:00Z'
            raise RuntimeError('provider mutation')
        with self.assertRaises(ValueError):
            attempt_completion(world, callbacks=(provider,))
        registry = kernel.EventHandlerRegistry()
        registry.register('STAGE1_FLIGHT_COMPLETION', provider)
        with self.assertRaises(ValueError):
            attempt_completion(world, registry=registry)
        self.assertEqual(called, [])
        self.assertTrue(protected_bytes(world) == before)

    def test_selected_custom_deepcopy_callback_is_rejected_without_invocation(self):
        world = deepcopy(self.source)
        called = []
        class Trap:
            def __deepcopy__(self, memo):
                called.append(True)
                raise RuntimeError('mutating object callback')
        owner = world['world_state']['dated_flights'][self.flight_id]['airline_id']
        world['world_state']['airlines'][owner]['unexpected'] = Trap()
        actual = attempt_completion(world)
        self.assertFalse(actual.local_admitted)
        self.assertFalse(actual.processing_result.succeeded)
        self.assertEqual(actual.processing_result.failure.code, 'INVALID_WORLD')
        self.assertEqual(called, [])

    def test_custom_registry_protocol_is_not_invoked(self):
        called = []
        class Registry:
            def handler_for(self, event_type):
                called.append(event_type)
                raise RuntimeError('registry callback')
        with self.assertRaises(ValueError):
            attempt_completion(deepcopy(self.source), registry=Registry())
        self.assertEqual(called, [])

    def test_other_event_boundaries_and_legacy_marker_are_not_executed(self):
        world = fixtures.QuarterlyBackendTests.fixture()[0]
        before = canonical_world(world)
        with self.assertRaises(ValueError):
            attempt_completion(world)
        self.assertEqual(canonical_world(world), before)
        world = deepcopy(self.source)
        del world['simulation']['operational_authority']
        before = canonical_world(world)
        with self.assertRaises(ValueError):
            attempt_completion(world)
        self.assertEqual(canonical_world(world), before)

    def test_failure_before_and_after_strict_mutation_preserves_source_and_retry(self):
        for target in ('completion_cost', 'settlement_records'):
            with self.subTest(target=target):
                source = deepcopy(self.source)
                before = canonical_world(source)
                reference = deepcopy(source)
                with patch.object(fulfilment, target, side_effect=RuntimeError('B3D injected failure')):
                    actual = attempt_completion(source)
                    expected = kernel.process_next_event(reference)
                self.assertEqual(actual.processing_result, expected)
                self.assertFalse(actual.processing_result.succeeded)
                self.assertEqual(canonical_world(source), before)
                self.assertEqual(canonical_world(reference), before)
                self.assertEqual(attempt_completion(source).processing_result, kernel.process_next_event(reference))
                self.assertEqual(canonical_world(source), canonical_world(reference))
        # Inject a failure after all handler writes but before candidate validation.
        original = fulfilment._completion_handler
        def after(context):
            original(context)
            raise RuntimeError('B3D after mutation')
        source = deepcopy(self.source)
        before = canonical_world(source)
        lookup = kernel.DEFAULT_EVENT_HANDLERS.handler_for
        def injected_lookup(event_type):
            return after if event_type == 'STAGE1_FLIGHT_COMPLETION' else lookup(event_type)
        with patch.object(kernel.DEFAULT_EVENT_HANDLERS, 'handler_for', side_effect=injected_lookup):
            # Invoke the strict reference directly: custom handlers are not in the
            # proposed local boundary. Its detached failure still retains source.
            result = kernel.process_next_event(source)
        self.assertFalse(result.succeeded)
        self.assertEqual(canonical_world(source), before)

    def test_save_load_rebind_and_strict_shared_requests_preserve_authority(self):
        from game.simulation.resolver import resolve_until
        restored = save_reload(self.source)
        actual = attempt_completion(restored)
        reference = deepcopy(self.source)
        self.assertEqual(actual.processing_result, kernel.process_next_event(reference))
        self.assertEqual(canonical_world(save_reload(restored)), canonical_world(save_reload(reference)))
        shared = deepcopy(self.source)
        due = self.source['world_state']['pending_events'][self.event_id]['due_at_utc']
        self.assertTrue(resolve_until(shared, due, shared=True).succeeded)
        self.assertEqual(canonical_world(shared), canonical_world(reference))


def corrupted_input(name, mutation):
    def test(self):
        world = deepcopy(self.source)
        mutation(world, self)
        self.assert_rejected_world(world)
        self.results.append((name, 'local not admitted', 'strict/detailed reject'))
    return test


MUTATIONS = {
    'wrong_aircraft': lambda w,t: w['world_state']['active_aircraft_operations'][t.flight_id].__setitem__('actual_aircraft_id', 'aircraft-foreign'),
    'wrong_flight': lambda w,t: w['world_state']['pending_events'][t.event_id].__setitem__('owner_id', 'dated_flight-foreign'),
    'wrong_utc': lambda w,t: w['world_state']['pending_events'][t.event_id].__setitem__('due_at_utc', '2027-01-02T02:40:01Z'),
    'stale_position': lambda w,t: w['world_state']['aircraft'][t.operation['actual_aircraft_id']].__setitem__('current_airport_id', t.operation['origin_airport_id']),
    'missing_manifest': lambda w,t: w['world_state']['active_aircraft_operations'][t.flight_id]['source_booking_ids'].pop(),
    'duplicate_manifest': lambda w,t: w['world_state']['active_aircraft_operations'][t.flight_id]['source_booking_ids'].append(t.booking),
    'booking_reference': lambda w,t: w['world_state']['bookings'][t.booking].__setitem__('itinerary_id', 'itinerary-foreign'),
    'lineage_boolean': lambda w,t: w['world_state']['itineraries'][t.itinerary]['quarterly_lineage'].__setitem__('revision', True),
    'lineage_float': lambda w,t: w['world_state']['itineraries'][t.itinerary]['quarterly_lineage'].__setitem__('slot_number', 1.0),
    'passenger_count': lambda w,t: w['world_state']['bookings'][t.booking].__setitem__('passenger_count', 999999),
    'missing_settlement': lambda w,t: w['world_state']['transactions'].pop(w['world_state']['bookings'][t.booking]['finance_transaction_id']),
    'duplicate_settlement': lambda w,t: w['world_state']['transactions'].__setitem__('transaction-duplicate', deepcopy(next(iter(w['world_state']['transactions'].values())))),
    'nested_publication': lambda w,t: next(iter(w['world_state']['weekly_plans'].values()))['revisions']['1']['slots'].append({}),
    'queue_corruption': lambda w,t: w['world_state']['pending_events'][t.event_id]['order_key'].__setitem__(1, True),
}
for _name, _mutation in MUTATIONS.items():
    setattr(HybridCompletionBoundaryTests, 'test_corruption_' + _name, corrupted_input(_name, _mutation))


if __name__ == '__main__':
    unittest.main()
