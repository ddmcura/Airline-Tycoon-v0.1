"""Stage 3D exact value/type/alias preservation and failure regressions."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch
from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import resolve_until
from game.world_state import flight_transition_validation as proof
from game.world_state.flight_proof_witness import protected_bytes, mutable_alias_error
from game.world_state.serialization import json_compatibility_error
from game.world_state.validation import _container_alias_error
from tests.flight_fixtures import flight_world, window
from tests.test_flight_certification import transition
from tests.resolution_oracle import canonical_world, save_reload


class ValueWitnessTests(unittest.TestCase):
    def test_exact_scalar_types_and_container_types(self):
        values=[None,False,True,0,1,1.0,'1',[],(),{},b'1',{1:[]},{'1':[]}]
        encodings=[protected_bytes(value) for value in values]
        self.assertEqual(len(set(encodings)),len(values))

    def test_equal_values_ignore_immutable_string_sharing(self):
        shared='a sufficiently long non-interned string'
        separate=(' '+shared)[1:]
        self.assertIsNot(shared,separate)
        self.assertEqual(protected_bytes([shared,shared]),protected_bytes([shared,separate]))

    def test_mutable_sharing_requires_separate_global_alias_proof(self):
        row=[]
        self.assertEqual(protected_bytes([row,row]),protected_bytes([[],[]]))
        self.assertIsNotNone(mutable_alias_error([row,row]))
        self.assertIsNone(mutable_alias_error([[],[]]))

    def test_custom_reduction_is_never_invoked(self):
        calls=[]
        class Evil:
            def __reduce__(self): calls.append(True); return dict,()
        with self.assertRaises(ValueError): protected_bytes({'value':Evil()})
        self.assertEqual(calls,[])

    def test_cycle_fails_closed_in_both_witnesses(self):
        cyclic=[]; cyclic.append(cyclic)
        with self.assertRaises(ValueError): protected_bytes(cyclic)
        self.assertIsNotNone(mutable_alias_error(cyclic))

    def test_nonfinite_float_cannot_impersonate_valid_predecessor(self):
        for value in (float('nan'),float('inf'),float('-inf')):
            self.assertNotEqual(protected_bytes({'x':value}),protected_bytes({'x':0.0}))
            self.assertIsNotNone(json_compatibility_error({'x':value}))

    def test_reordering_conservatively_rejects_instead_of_losing_a_check(self):
        self.assertNotEqual(protected_bytes({'a':1,'b':2}),protected_bytes({'b':2,'a':1}))

    def test_alias_predicate_matches_canonical_on_generated_graphs(self):
        rng=random.Random(1937)
        for _ in range(100):
            rows=[{'n':rng.randrange(10),'items':[rng.randrange(10),{'x':[]}]} for _ in range(6)]
            graph={'rows':rows,'other':deepcopy(rows[0])}
            if rng.randrange(2): graph['other']=rows[rng.randrange(6)]
            self.assertEqual(mutable_alias_error(graph) is None,_container_alias_error(graph) is None)
        for value in (None,1,'x',[],{}): self.assertIsNone(mutable_alias_error(value))


class FlightProofOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3)
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def departed(self):
        return transition(self.world,proof.capture_departure,proof.validate_departure)

    def test_detached_protected_witness_is_exact_bytes(self):
        before,event_id,generated=self.departed()
        self.assertIs(type(before['protected']),bytes)
        witness=before['protected']
        self.world['ui_state']['filters']['unrelated']='changed'
        self.assertEqual(before['protected'],witness)
        with self.assertRaisesRegex(ValueError,'protected structure'):
            proof.validate_departure(before,self.world,event_id,generated)

    def test_in_place_protected_type_changes_cannot_hide_behind_equality(self):
        before,event_id,generated=self.departed()
        for value in (True,7.0):
            world=deepcopy(self.world); world['metadata']['save_schema_version']=value
            with self.assertRaises(ValueError): proof.validate_departure(before,world,event_id,generated)

    def test_canonical_check_covers_changed_records_only_on_success(self):
        original=proof.json_compatibility_error
        with patch.object(proof,'json_compatibility_error',wraps=original) as checks:
            self.departed()
        self.assertEqual(checks.call_count,1)
        checked=checks.call_args.args[0]
        self.assertIs(type(checked),list)
        self.assertIn(self.world['simulation'],checked)
        self.assertIn(self.world['deterministic_state']['id_allocator'],checked)
        self.assertNotIn(self.world,checked)

    def test_protected_noncanonical_key_has_failure_only_diagnostic(self):
        before,event_id,generated=self.departed()
        world=deepcopy(self.world)
        revisions=next(iter(world['world_state']['schedule_definitions'].values()))['revisions']
        revisions[1]=revisions.pop('1')
        with self.assertRaisesRegex(ValueError,'non-JSON authority'):
            proof.validate_departure(before,world,event_id,generated)

    def test_cross_changed_protected_alias_remains_rejected(self):
        self.world['ui_state']['filters']['empty']=[]
        before,event_id,generated=self.departed()
        flight_id=before['flight']['dated_flight_id']
        new=self.world['world_state']['active_aircraft_operations'][flight_id]
        # The protected UI list is equal-valued: fingerprints alone cannot see
        # its sharing with the new operation. The global graph predicate must.
        self.world['ui_state']['filters']['empty']=new['zero_fare_booking_ids']
        self.assertEqual(proof._protected_digest(self.world,before['excluded']),before['protected'])
        with self.assertRaisesRegex(ValueError,'mutable-container alias'):
            proof.validate_departure(before,self.world,event_id,generated)

    def test_equal_valued_alias_entirely_inside_protected_state_is_rejected(self):
        self.world['ui_state']['filters'].update(a=[],b=[])
        before,event_id,generated=self.departed()
        filters=self.world['ui_state']['filters']; filters['b']=filters['a']
        self.assertEqual(proof._protected_digest(self.world,before['excluded']),before['protected'])
        with self.assertRaisesRegex(ValueError,'mutable-container alias'):
            proof.validate_departure(before,self.world,event_id,generated)

    def test_shallow_views_cannot_hide_noncanonical_root_or_table_types(self):
        class NonPlain(dict): pass
        before,event_id,generated=self.departed()
        for path in (('world_state',),('deterministic_state',),
                ('world_state','active_aircraft_operations'),('world_state','dated_flights')):
            with self.subTest(path=path):
                world=deepcopy(self.world); parent=world
                for key in path[:-1]: parent=parent[key]
                parent[path[-1]]=NonPlain(parent[path[-1]])
                with self.assertRaisesRegex(ValueError,'non-JSON authority'):
                    proof.validate_departure(before,world,event_id,generated)

    def test_encoding_failure_discards_and_replays_exact_successful_prefix(self):
        target=window(self.world,'departure'); expected=deepcopy(self.world)
        strict=kernel.process_next_event(expected); self.assertTrue(strict.succeeded)
        real=proof.protected_bytes; calls=0
        def fail_after_capture(value):
            nonlocal calls
            calls+=1
            if calls==2: raise ValueError('controlled encoding fault')
            return real(value)
        with patch.object(proof,'protected_bytes',fail_after_capture):
            result=resolve_until(self.world,target,shared=True,shadow=True,max_batch_events=64)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE')
        self.assertEqual(len(result.completed_event_ids),1)
        self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_alias_and_serialization_faults_recover_without_speculative_leakage(self):
        for fault in ('alias','tuple','protected-tuple'):
            with self.subTest(fault=fault):
                world=deepcopy(self.base); world['ui_state']['filters']['empty']=[]
                expected=deepcopy(world); self.assertTrue(kernel.process_next_event(expected).succeeded)
                real=kernel._apply_handler_candidate; calls=0
                def corrupt(original,candidate,event_id,handler,**options):
                    nonlocal calls
                    outcome=real(original,candidate,event_id,handler,**options); calls+=1
                    if calls==1:
                        flight_id=candidate['world_state']['event_history'][event_id]['owner_id']
                        operation=candidate['world_state']['active_aircraft_operations'][flight_id]
                        if fault=='alias': operation['zero_fare_booking_ids']=candidate['ui_state']['filters']['empty']
                        elif fault=='tuple': operation['zero_fare_booking_ids']=()
                        else: candidate['ui_state']['filters']['invalid']=()
                    return outcome
                with patch.object(kernel,'_apply_handler_candidate',corrupt):
                    result=resolve_until(world,window(world,'departure'),shared=True,max_batch_events=64)
                self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE')
                self.assertEqual(calls,2)
                self.assertEqual(canonical_world(world),canonical_world(expected))

    def test_no_witness_bytes_are_saved_and_inflight_restore_is_exact(self):
        self.departed(); restored=save_reload(self.world)
        self.assertEqual(canonical_world(restored),canonical_world(self.world))
        self.assertNotIn('protected',restored)
        self.assertNotIn('flight_proof_witness',restored)

    def test_later_event_cannot_repair_protected_mutation(self):
        target=window(self.world,'departure'); calls=0
        real=kernel._apply_handler_candidate
        def corrupt(original,candidate,event_id,handler,**options):
            nonlocal calls
            outcome=real(original,candidate,event_id,handler,**options)
            calls+=1
            if calls==1: candidate['world_state']['airports'][next(iter(candidate['world_state']['airports']))]['corruption']=True
            return outcome
        with patch.object(kernel,'_apply_handler_candidate',corrupt):
            result=resolve_until(self.world,target,shared=True,max_batch_events=64)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE')
        self.assertEqual(len(result.completed_event_ids),1)
        self.assertEqual(calls,2)  # first bad candidate + successful strict replay
        self.assertNotIn('corruption',next(iter(self.world['world_state']['airports'].values())))

if __name__=='__main__': unittest.main()
