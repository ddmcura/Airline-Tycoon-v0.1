"""Graph-loop optimization retains complete gates and authoritative outcomes."""
from contextlib import ExitStack
from copy import deepcopy
import json
import tempfile
import unittest

from game.simulation import kernel
from game.simulation.resolver import begin_resolution
from game.world_state import validation
from game.world_state.persistence import SaveError, SaveStore, _digest
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import canonical_world
from tests.test_atomic_boundary_optimization import legacy_gates


class RuntimeValidatorOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = flight_world(2)

    def assert_reference_validation(self, world):
        before = canonical_world(world)
        actual = validation.validate_world(world)
        with ExitStack() as stack:
            legacy_gates(stack)
            expected = validation.validate_world(world)
        self.assertEqual(actual, expected)
        self.assertEqual(canonical_world(world), before)
        return actual

    def test_scalar_field_classification_never_proves_a_later_value(self):
        for key, bad in (('ordinary', float('inf')), ('amount_minor', True),
                         ('time_utc', 'local time'), ('ordinary', (1,))):
            with self.subTest(key=key, bad=bad):
                first = 1 if key.endswith('_minor') else (
                    '2026-09-01T00:00:00Z' if key.endswith('_utc') else 'plain')
                rows = [{'ordinary': 'plain', key: first}, {key: first}]
                world = {'world_state': {'rows': rows}}
                self.assertTrue(validation._plain_authority_tree(world))
                rows[1][key] = bad
                self.assertFalse(validation._plain_authority_tree(world))
                rows[1][key] = first
                self.assertTrue(validation._plain_authority_tree(world))

    def test_container_authority_and_global_alias_checks_are_retained(self):
        ui = {'world_state': [{'route_id': 'display', 'amount_minor': 1.5}]}
        world = {'ui_state': ui, 'world_state': {'rows': [{'ordinary': [None, True, 2, 1.5]}]}}
        self.assertTrue(validation._plain_authority_tree(world))
        world['world_state']['rows'][0]['ordinary'].append({'route_id': 'forbidden'})
        self.assertFalse(validation._plain_authority_tree(world))
        world['world_state']['rows'][0]['ordinary'].pop()
        world['world_state']['alias'] = ui
        self.assertFalse(validation._plain_authority_tree(world))

    def test_booking_itinerary_and_flight_mutations_retain_exact_diagnostics(self):
        self.assertTrue(self.assert_reference_validation(self.base).is_valid)
        cases = (
            ('bookings', 'itinerary_id', 'itinerary-999999999999'),
            ('bookings', 'passenger_count', 0),
            ('bookings', 'total_fare_minor', True),
            ('itineraries', 'dated_flight_ids', ['dated_flight-999999999999']),
            ('itineraries', 'scheduled_departure_utc', 'not UTC'),
            ('dated_flights', 'airline_id', 'airline-999999999999'),
        )
        for collection, field, value in cases:
            with self.subTest(collection=collection, field=field):
                world = deepcopy(self.base)
                self.assertTrue(validation.validate_world(world).is_valid)
                next(iter(world['world_state'][collection].values()))[field] = value
                self.assertFalse(self.assert_reference_validation(world).is_valid)

    def test_invalid_event_candidate_preserves_exact_authority(self):
        registry = kernel.EventHandlerRegistry()

        def invalidate(context):
            booking = next(iter(context.envelope['world_state']['bookings'].values()))
            booking['itinerary_id'] = 'itinerary-999999999999'

        registry.register('INVALID_BOOKING', invalidate)
        results = []
        for reference in (False, True):
            world = deepcopy(self.base)
            kernel.schedule_event(world, event_type='INVALID_BOOKING',
                due_at_utc=world['simulation']['time_utc'], owner_type='airline',
                owner_id=world['world_state']['player']['primary_airline_id'])
            before = canonical_world(world)
            with ExitStack() as stack:
                if reference:
                    legacy_gates(stack)
                result = kernel.process_next_event(world, registry=registry)
            self.assertFalse(result.succeeded)
            self.assertEqual(result.failure.code, 'RESULT_VALIDATION_FAILED')
            self.assertEqual(canonical_world(world), before)
            results.append(result)
        self.assertEqual(*results)

    def test_save_rejects_mutation_without_replacing_previous_valid_file(self):
        with tempfile.TemporaryDirectory() as root:
            store = SaveStore(root)
            career = store.new_career_id()
            store.save(career, 'manual', self.base)
            path = store._path(career, 'manual')
            previous = path.read_bytes()
            bad = deepcopy(self.base)
            next(iter(bad['world_state']['itineraries'].values()))['dated_flight_ids'] = ['missing']
            with self.assertRaises(SaveError) as failed_save:
                store.save(career, 'manual', bad)
            self.assertEqual(failed_save.exception.code, 'INVALID_WORLD')
            self.assertEqual(path.read_bytes(), previous)
            restored, _ = store.load(career)
            self.assertEqual(canonical_world(restored), canonical_world(self.base))
            self.assertEqual(restored['simulation']['clock_state'], 'PAUSED')
            # A valid wrapper checksum must not let invalid authority load.
            wrapper = json.loads(previous)
            wrapper['world'] = bad
            wrapper['integrity_sha256'] = _digest({key: value for key, value in wrapper.items()
                                                  if key != 'integrity_sha256'})
            path.write_text(json.dumps(wrapper), encoding='utf-8')
            with self.assertRaises(SaveError) as failed_load:
                store.load(career)
            self.assertEqual(failed_load.exception.code, 'INVALID_WORLD')
            self.assertTrue(validation.validate_world(self.base).is_valid)

    def test_strict_shared_and_reference_have_identical_complete_worlds(self):
        target = window(self.base, 'round-trip')
        outputs = []
        for reference in (False, True):
            for shared in (False, True):
                world = deepcopy(self.base)
                with ExitStack() as stack:
                    if reference:
                        legacy_gates(stack)
                    request = begin_resolution(world, target, shared=shared)
                    while not request.finished:
                        request.step()
                    self.assertTrue(request.result.succeeded, request.result.failure)
                self.assertTrue(validation.validate_world(world).is_valid)
                outputs.append(canonical_world(world))
        self.assertTrue(all(world == outputs[0] for world in outputs))


if __name__ == '__main__':
    unittest.main()
