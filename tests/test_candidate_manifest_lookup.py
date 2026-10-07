"""Stage 3D.3 exact lookup, ownership, lifetime and replay regressions."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch
from game.aircraft_operations import fulfilment, manifest_lookup as lookup
from game.simulation import kernel, shared_candidate
from game.simulation.candidate_ownership import CandidateOwnership
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution, resolve_until
from game.world_state import validate_world, flight_transition_validation as proof
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import canonical_world, save_reload


class CandidateManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = flight_world(3)
        cls.zero = flight_world(1, fare_minor=0)

    def setUp(self):
        initialize_runtime_handlers()
        self.world = deepcopy(self.base)

    def capsule(self):
        event = min(self.world['world_state']['pending_events'].values(), key=kernel._event_key)
        contract = kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(event['event_type'])
        owner = CandidateOwnership(self.world)
        cap = owner.begin(contract.mutation_footprint(self.world, event['event_id']),
                          read_lookup_factory=contract.read_lookup_factory)
        return owner, cap, event, contract

    def assert_manifests_equal(self, world):
        index = lookup.CandidateManifestLookup(world)
        for flight_id in world['world_state']['dated_flights']:
            full = fulfilment._build_confirmed_carriage_manifest(world, flight_id)
            indexed = fulfilment._build_confirmed_carriage_manifest(
                world, flight_id, booking_ids=index.lookup(world, flight_id))
            self.assertEqual(indexed, full)
        index.close()

    def test_all_flight_manifests_match_slow_canonical_oracle(self):
        self.assert_manifests_equal(self.world)

    def test_zero_fare_and_empty_manifests_match_canonical_oracle(self):
        self.assert_manifests_equal(deepcopy(self.zero))
        index = lookup.CandidateManifestLookup(self.world)
        self.assertEqual(index.lookup(self.world, 'no-such-flight'), ())

    def test_order_is_sorted_ids_independent_of_dictionary_order(self):
        first = lookup.CandidateManifestLookup(self.world)
        for name in ('bookings', 'itineraries'):
            self.world['world_state'][name] = dict(reversed(tuple(self.world['world_state'][name].items())))
        second = lookup.CandidateManifestLookup(self.world)
        self.assertEqual(first._groups, second._groups)
        for ids in second._groups.values(): self.assertEqual(ids, tuple(sorted(ids)))
        self.assert_manifests_equal(self.world)

    def test_lookup_exposes_only_immutable_ids(self):
        owner, cap, event, _ = self.capsule()
        ids = cap.read_lookup(cap.envelope, event['owner_id'])
        self.assertIs(type(ids), tuple)
        self.assertTrue(ids)
        self.assertTrue(all(type(key) is str for key in ids))
        index = next(iter(owner._read_lookups.values()))
        with self.assertRaises(TypeError): index._groups[event['owner_id']] = ()
        owner.close()

    def test_corrupt_lineage_and_capacity_keep_identical_manifest_rejections(self):
        for corruption in ('lineage', 'revision', 'sale', 'checkpoint', 'capacity'):
            with self.subTest(corruption=corruption):
                world = deepcopy(self.base); state = world['world_state']
                booking = next(iter(state['bookings'].values()))
                itinerary = state['itineraries'][booking['itinerary_id']]
                flight_id = itinerary['dated_flight_ids'][0]
                if corruption == 'lineage': itinerary['schedule_lineage']['schedule_revision'] += 1
                elif corruption == 'revision': booking['inventory_revision_at_commit'] += 100
                elif corruption == 'sale': booking['finance_transaction_id'] = 'missing'
                elif corruption == 'checkpoint': booking['booking_checkpoint_id'] = 'missing'
                else: state['dated_flights'][flight_id]['capacity'] = 0
                index = lookup.CandidateManifestLookup(world)
                full = fulfilment._build_confirmed_carriage_manifest(world, flight_id)
                indexed = fulfilment._build_confirmed_carriage_manifest(world, flight_id,
                    booking_ids=index.lookup(world, flight_id))
                self.assertFalse(full.succeeded)
                self.assertEqual(indexed, full)
                index.close()

    def test_build_independent_verification_rejects_omission_duplicate_wrong_and_surplus(self):
        groups = lookup._build_groups(self.world['world_state'])
        flight_id = next(k for k, ids in groups.items() if ids)
        booking_id = groups[flight_id][0]
        for corruption in ('omission', 'duplicate', 'wrong', 'surplus'):
            with self.subTest(corruption=corruption):
                bad = dict(groups)
                if corruption == 'omission': bad[flight_id] = bad[flight_id][1:]
                elif corruption == 'duplicate': bad[flight_id] += (booking_id,)
                elif corruption == 'wrong':
                    other = next(k for k in groups if k != flight_id)
                    bad[flight_id] = bad[flight_id][1:]
                    bad[other] = tuple(sorted((*bad[other], booking_id)))
                else: bad[flight_id] = tuple(sorted((*bad[flight_id], 'missing')))
                with patch.object(lookup, '_build_groups', return_value=bad):
                    with self.assertRaises(ValueError): lookup.CandidateManifestLookup(self.world)

    def test_build_failure_replays_strict_first_event_without_lookup(self):
        expected = deepcopy(self.world); self.assertTrue(kernel.process_next_event(expected).succeeded)
        with patch.object(lookup, '_build_groups', side_effect=ValueError('lookup build fault')):
            actual = resolve_until(self.world, window(self.world, 'departure'), shared=True)
        self.assertEqual(actual.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertEqual(canonical_world(self.world), canonical_world(expected))

    def test_current_relevant_authority_is_resolved_and_stale_association_rejected(self):
        owner, cap, event, _ = self.capsule()
        ids = cap.read_lookup(cap.envelope, event['owner_id'])
        booking = self.world['world_state']['bookings'][ids[0]]
        self.world['world_state']['itineraries'][booking['itinerary_id']]['dated_flight_ids'] = ['wrong']
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            cap.read_lookup(cap.envelope, event['owner_id'])
        owner.close()

    def test_missing_booking_and_changed_source_fail_closed(self):
        for mutation in ('missing', 'root'):
            owner, cap, event, _ = self.capsule()
            ids = cap.read_lookup(cap.envelope, event['owner_id'])
            if mutation == 'missing': self.world['world_state']['bookings'].pop(ids[0])
            else: self.world['world_state']['bookings'] = deepcopy(self.world['world_state']['bookings'])
            with self.assertRaisesRegex(ValueError, 'source changed'):
                cap.read_lookup(cap.envelope, event['owner_id'])
            owner.close(); self.world = deepcopy(self.base)

    def test_protected_reads_cannot_modify_booking_or_itinerary(self):
        owner, cap, event, _ = self.capsule()
        ids = cap.read_lookup(cap.envelope, event['owner_id'])
        row = cap.envelope['world_state']['bookings'][ids[0]]
        with self.assertRaises(ValueError): row['itinerary_id'] = 'wrong'
        itinerary = cap.envelope['world_state']['itineraries'][row['itinerary_id']]
        with self.assertRaises(ValueError): itinerary['dated_flight_ids'].append('wrong')
        owner.close()

    def test_foreign_predecessor_and_replaced_capsule_source_rejected(self):
        owner, cap, event, _ = self.capsule()
        with self.assertRaises(ValueError): cap.read_lookup(deepcopy(self.world), event['owner_id'])
        cap.envelope['world_state']['bookings'] = deepcopy(cap.envelope['world_state']['bookings'])
        with self.assertRaisesRegex(ValueError, 'source replaced'):
            cap.read_lookup(cap.envelope, event['owner_id'])
        owner.close()

    def test_lazy_build_and_expiry_on_close(self):
        owner, cap, event, _ = self.capsule()
        self.assertEqual(owner._read_lookups, {})
        read = cap.read_lookup
        read(cap.envelope, event['owner_id'])
        service = next(iter(owner._read_lookups.values()))
        owner.close()
        self.assertEqual(owner._read_lookups, {})
        self.assertIsNone(service._world)
        self.assertEqual(dict(service._groups), {})
        with self.assertRaises(ValueError): read(cap.envelope, event['owner_id'])
        with self.assertRaises(ValueError): service.lookup(self.world, event['owner_id'])

    def test_future_write_footprint_cannot_invalidate_existing_lookup(self):
        owner, cap, event, _ = self.capsule()
        cap.read_lookup(cap.envelope, event['owner_id'])
        for name in ('bookings', 'itineraries'):
            with self.assertRaisesRegex(ValueError, 'source is writable'):
                owner.begin({name: set()})
        owner.close()

    def test_lookup_factory_is_identity_bound_to_flight_certificate(self):
        _, _, _, contract = self.capsule()
        self.assertTrue(proof.is_flight_certificate(contract))
        self.assertFalse(proof.is_flight_certificate(replace(contract, read_lookup_factory=lambda x: None)))

    def test_payment_lookup_metadata_cannot_spoof_none_by_value_equality(self):
        from game.aircraft_market.step5 import _payment_handler
        from game.world_state.payment_validation import payment_execution_contract, is_payment_certificate
        class EqualAnything:
            def __eq__(self, other): return True
        contract = payment_execution_contract(_payment_handler)
        self.assertTrue(is_payment_certificate(contract))
        self.assertFalse(is_payment_certificate(replace(contract, read_lookup_factory=EqualAnything())))

    def test_one_build_per_candidate_not_per_manifest(self):
        builds = []; actual = lookup._build_groups
        def build(world): builds.append(len(world['bookings'])); return actual(world)
        with patch.object(lookup, '_build_groups', build):
            result = resolve_until(self.world, window(self.world, 'round-trip'), shared=True, max_batch_events=64)
        self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(builds, [len(self.base['world_state']['bookings'])])
        self.assertTrue(validate_world(self.world).is_valid)

    def test_new_candidate_after_cooperative_return_builds_its_own_lookup(self):
        services = []; actual = lookup.CandidateManifestLookup.__init__
        def build(service, world): actual(service, world); services.append(service)
        with patch.object(lookup.CandidateManifestLookup, '__init__', build):
            request = begin_resolution(self.world, window(self.world, 'round-trip'), shared=True, max_batch_events=2)
            while not request.finished:
                request.step()
                self.assertTrue(all(service._world is None for service in services))
                self.assertFalse(any(isinstance(v, lookup.CandidateManifestLookup) for v in vars(request).values()))
        self.assertTrue(request.result.succeeded)
        self.assertEqual(len(services), 6)

    def test_payment_only_does_not_build_booking_lookup(self):
        from tests.payment_fixtures import payment_world
        world, target = payment_world()
        with patch.object(lookup, '_build_groups', side_effect=AssertionError('Payment indexed Bookings')):
            result = resolve_until(world, target, shared=True)
        self.assertTrue(result.succeeded, result.failure)

    def test_shadow_retains_full_scan_and_exact_world_oracle(self):
        canonical = indexed = 0; actual = fulfilment._build_confirmed_carriage_manifest
        def manifest(*args, **kwargs):
            nonlocal canonical, indexed
            if kwargs.get('booking_ids') is None: canonical += 1
            else: indexed += 1
            return actual(*args, **kwargs)
        with patch.object(fulfilment, '_build_confirmed_carriage_manifest', manifest):
            result = resolve_until(self.world, window(self.world, 'round-trip'), shared=True, shadow=True)
        self.assertTrue(result.succeeded, result.failure)
        self.assertGreater(canonical, 0); self.assertGreater(indexed, 0)

    def test_lookup_failure_discards_state_before_strict_prefix_replay(self):
        expected = deepcopy(self.world)
        for _ in range(2): self.assertTrue(kernel.process_next_event(expected).succeeded)
        services = []; actual = lookup.CandidateManifestLookup.lookup; count = 0
        def faulty(service, envelope, flight_id):
            nonlocal count
            if service not in services: services.append(service)
            count += 1
            if count == 3: raise ValueError('second-event lookup fault')
            return actual(service, envelope, flight_id)
        replay = shared_candidate.SharedResolutionRequest._recover
        def recover(request, attempts):
            self.assertTrue(all(service._world is None for service in services))
            return replay(request, attempts)
        with patch.object(lookup.CandidateManifestLookup, 'lookup', faulty), patch.object(
                shared_candidate.SharedResolutionRequest, '_recover', recover):
            result = resolve_until(self.world, window(self.world, 'departure'), shared=True)
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertEqual(canonical_world(self.world), canonical_world(expected))

    def test_final_validation_sees_no_live_private_lookup(self):
        services = []; actual = lookup.CandidateManifestLookup.__init__
        def build(service, world): actual(service, world); services.append(service)
        validation = shared_candidate._validate_batch
        def validate(world):
            self.assertTrue(all(service._world is None for service in services))
            return validation(world)
        with patch.object(lookup.CandidateManifestLookup, '__init__', build), patch.object(shared_candidate, '_validate_batch', validate):
            result = resolve_until(self.world, window(self.world, 'round-trip'), shared=True)
        self.assertTrue(result.succeeded, result.failure)

    def test_in_flight_and_completed_save_reload_have_no_lookup_state(self):
        for kind in ('departure', 'round-trip'):
            world = deepcopy(self.base)
            self.assertTrue(resolve_until(world, window(world, kind), shared=True).succeeded)
            restored = save_reload(world)
            self.assertEqual(canonical_world(restored), canonical_world(world))
            self.assertEqual(restored['metadata']['save_schema_version'], 8)
            text = canonical_world(restored)
            for marker in ('read_lookup', 'CandidateManifestLookup', '_read_lookups', '_read_capability'):
                self.assertNotIn(marker, text)
            if kind == 'departure':
                self.assertTrue(resolve_until(restored, window(restored, 'round-trip'), shared=True).succeeded)

    def test_indexed_completion_keeps_frozen_manifest_exact(self):
        target = window(self.world, 'completion')
        expected = deepcopy(self.world)
        self.assertTrue(kernel.process_events_through(expected, target).succeeded)
        self.assertTrue(resolve_until(self.world, target, shared=True).succeeded)
        self.assertEqual(canonical_world(self.world), canonical_world(expected))

    def test_callback_does_not_retain_consumed_capsule_or_event_copies(self):
        import weakref
        owner, cap, event, _ = self.capsule()
        read = cap.read_lookup; envelope = cap.envelope
        read(envelope, event['owner_id'])
        reference = weakref.ref(cap)
        del cap
        self.assertIsNone(reference())
        with self.assertRaisesRegex(ValueError, 'expired'): read(envelope, event['owner_id'])
        owner.close()

    def test_invalid_booking_authority_rejected_at_entry_without_index_or_mutation(self):
        for corruption in ('missing', 'itinerary', 'duplicate-flight', 'type'):
            world = deepcopy(self.base); state = world['world_state']
            key = next(iter(state['bookings'])); booking = state['bookings'][key]
            itinerary = state['itineraries'][booking['itinerary_id']]
            if corruption == 'missing': del state['bookings'][key]
            elif corruption == 'itinerary': booking['itinerary_id'] = 'missing'
            elif corruption == 'duplicate-flight': itinerary['dated_flight_ids'] *= 2
            else: booking['booking_revision'] = True
            before = canonical_world(world)
            with patch.object(lookup, '_build_groups', side_effect=AssertionError('invalid entry indexed')):
                result = resolve_until(world, window(world, 'departure'), shared=True)
            self.assertFalse(result.succeeded)
            self.assertEqual(canonical_world(world), before)

    def test_public_manifest_does_not_accept_unowned_lookup_hint(self):
        flight_id = next(iter(self.world['world_state']['dated_flights']))
        with self.assertRaisesRegex(ValueError, 'owned event reads'):
            fulfilment.build_confirmed_carriage_manifest(self.world, flight_id, _booking_lookup=lambda *_: ())


if __name__ == '__main__': unittest.main()
