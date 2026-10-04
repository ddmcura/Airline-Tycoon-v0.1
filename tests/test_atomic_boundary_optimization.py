"""Stage 3E.1 exact graph predicates and retained authoritative gates."""
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
import random
import unittest
from unittest.mock import patch

from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution
from game.world_state import validation as v
from game.world_state.serialization import json_compatibility_error, _clone_runtime_world
from tests import atomic_validation_oracle as old
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import canonical_world, save_reload


def legacy_gates(stack):
    stack.enter_context(patch.object(v, '_plain_authority_tree', lambda _: False))
    for owner, name, fn in (
        (v, 'json_compatibility_error', old.json_compatibility_error),
        (v, '_container_alias_error', old._container_alias_error),
        (v._Validator, 'validate_no_name_references_or_float_money', old.validate_no_name_references_or_float_money),
    ):
        stack.enter_context(patch.object(owner, name, fn))


class ExactGraphPredicateTests(unittest.TestCase):
    def assert_predicates(self, value):
        self.assertEqual(json_compatibility_error(value), old.json_compatibility_error(value))
        self.assertEqual(v._container_alias_error(value), old._container_alias_error(value))

    def test_scalar_types_finite_values_and_key_types(self):
        class String(str): pass
        class Mapping(dict): pass
        class Sequence(list): pass
        for value in (None, True, 17, 1.0, 'text', [], {}, (), set(), Decimal('1'),
                      float('nan'), float('inf'), float('-inf'), String('x'), Mapping(), Sequence(),
                      {1: 3}, {String('key'): [1]}, {'a': [{'bad': ()}]}):
            with self.subTest(value=repr(value)): self.assert_predicates(value)

    def test_random_graphs_match_first_diagnostic_and_alias_paths(self):
        rng=random.Random(32181)
        for _ in range(150):
            rows=[{'n':rng.randrange(100), 'v':[None, False, {'list':[]}]} for _ in range(10)]
            value={'rows':rows,'tail':deepcopy(rows[0])}
            if rng.randrange(2): value['tail']=rows[rng.randrange(10)]
            if rng.randrange(2): rows[rng.randrange(10)]['v'].append((1,))
            if rng.randrange(2): rows[rng.randrange(10)]['bad']=float('inf')
            self.assert_predicates(value)

    def test_aliases_in_different_subtrees_and_cycles(self):
        row=[]
        values=[{'a':row,'b':row},[row,{'b':row}]]
        cycle=[]; cycle.append(cycle); values.append(cycle)
        cycle={}; cycle['self']=cycle; values.append(cycle)
        for value in values: self.assert_predicates(value)

    def test_deep_trees_retain_original_recursion_diagnostics(self):
        for depth in (127,128,129,400,1200):
            value=0
            for _ in range(depth): value=[value]
            self.assert_predicates(value)

    def test_custom_reduction_not_invoked(self):
        calls=[]
        class Evil:
            def __reduce__(self): calls.append(True); return dict,()
        self.assert_predicates({'evil':Evil()})
        self.assertEqual(calls,[])


class ExclusiveMeasurementTests(unittest.TestCase):
    def test_nested_intervals_are_counted_once(self):
        from tests.profile_atomic_boundaries import ExclusiveProfile
        now=[0.0]
        profiler=ExclusiveProfile()
        def child(): now[0]+=2
        child=profiler.wrap(child,'child')
        def parent():
            now[0]+=3; child(); now[0]+=1
        parent=profiler.wrap(parent,'parent')
        with patch('tests.profile_atomic_boundaries.perf_counter',lambda:now[0]): parent()
        self.assertEqual(profiler.seconds,{'child':2,'parent':4})
        self.assertEqual(profiler.inclusive,{'child':2,'parent':6})
        self.assertEqual(profiler.stack,[])
        copy=profiler.wrap(lambda: child(), 'whole_world_clone')
        commit=profiler.wrap(copy, 'detached_commit')
        with patch('tests.profile_atomic_boundaries.perf_counter',lambda:now[0]):
            copy(); commit()
        self.assertEqual(profiler.calls['candidate_clone'],1)
        self.assertEqual(profiler.calls['commit_clone'],1)
        self.assertEqual(profiler.inclusive['candidate_clone'],2)
        self.assertEqual(profiler.inclusive['commit_clone'],2)
        self.assertEqual(profiler.seconds['detached_commit'],0)

    def test_exception_closes_measurement_frame(self):
        from tests.profile_atomic_boundaries import ExclusiveProfile
        profiler=ExclusiveProfile()
        def fail(): raise ValueError('expected')
        with self.assertRaises(ValueError): profiler.wrap(fail,'failure')()
        self.assertEqual(profiler.stack,[])
        self.assertEqual(profiler.calls['failure'],1)


class FullGateOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(2)
    def setUp(self): initialize_runtime_handlers()

    def assert_full_gate(self, world):
        actual=v.validate_world(world).as_dict()
        with ExitStack() as stack:
            legacy_gates(stack)
            expected=v.validate_world(world).as_dict()
        self.assertEqual(actual,expected)
        return actual

    def test_valid_world_and_unknown_nested_fields_match_oracle(self):
        world=deepcopy(self.base)
        world['world_state']['airlines'][next(iter(world['world_state']['airlines']))]['diagnostic']={'rows':[{'ok':1}]}
        self.assert_full_gate(world)
        self.assertTrue(self.assert_full_gate(self.base)['is_valid'])

    def test_unknown_nested_name_money_time_fields_still_checked(self):
        for key,value,code in (('route_id','legacy','name_based_authoritative_reference'),
                               ('unknown_minor',1.0,'invalid_money'),
                               ('unknown_utc','2026-09-01 00:00','invalid_timestamp')):
            world=deepcopy(self.base)
            world['world_state']['airlines'][next(iter(world['world_state']['airlines']))]['diagnostic']={'rows':[{key:value}]}
            result=self.assert_full_gate(world)
            self.assertIn(code,{e['code'] for e in result['errors']})

    def test_ui_values_do_not_acquire_authority_field_rules(self):
        world=deepcopy(self.base)
        world['ui_state']['filters'].update(origin_iata='MNL',display_minor=1.5,display_utc='local label')
        self.assertTrue(self.assert_full_gate(world)['is_valid'])

    def test_combined_proof_requires_plain_timestamp_before_calling_its_methods(self):
        calls=[]
        class Text(str):
            def endswith(self,*args): calls.append('endswith'); return super().endswith(*args)
        graph={'world_state':{'custom_utc':Text('2026-09-01T00:00:00Z')}}
        self.assertFalse(v._plain_authority_tree(graph))
        self.assertEqual(calls,[])

    def test_whole_gate_corruption_categories_retain_identical_errors(self):
        def aircraft_location(w): next(iter(w['world_state']['aircraft'].values()))['current_airport_id']='airport-999999999999'
        def flight_owner(w): next(iter(w['world_state']['dated_flights'].values()))['planned_aircraft_id']='aircraft-999999999999'
        def event_time(w): next(iter(w['world_state']['pending_events'].values()))['due_at_utc']='invalid'
        def revision(w): next(iter(w['world_state']['dated_flights'].values()))['operation_revision']=-1
        def schema(w): w['metadata']['save_schema_version']=999
        def serialization(w): w['ui_state']['filters']['unknown']=Decimal('1')
        def journal(w): next(iter(w['world_state']['transactions'].values()))['entries'][0]['amount_minor']+=1
        def booking(w): next(iter(w['world_state']['bookings'].values()))['passenger_count']=0
        def alias(w): w['ui_state']['filters']['unknown']=w['world_state']['airlines']
        for corrupt in (aircraft_location,flight_owner,event_time,revision,schema,serialization,alias,journal,booking):
            world=deepcopy(self.base); corrupt(world)
            with self.subTest(corrupt=corrupt.__name__):
                self.assertFalse(self.assert_full_gate(world)['is_valid'])

    def test_clock_only_boundary_rechecks_borrowed_world(self):
        world=deepcopy(self.base)
        target=world['simulation']['time_utc']
        request=begin_resolution(world,target,shared=True)
        world['world_state']['airlines'][next(iter(world['world_state']['airlines']))]['unknown_minor']=1.0
        progress=request.step()
        self.assertFalse(progress.processing_result.succeeded)
        self.assertEqual(world['simulation']['time_utc'],target)

    def test_full_transaction_counts_are_retained(self):
        world=deepcopy(self.base); target=window(world,'departure')
        with patch.object(kernel,'validate_world',wraps=v.validate_world) as gate, patch.object(kernel,'_clone_runtime_world',wraps=_clone_runtime_world) as clone:
            request=begin_resolution(world,target,shared=True,max_batch_events=8)
            while not request.finished: request.step()
        self.assertEqual(gate.call_count,3)  # entry, shared flush, final UTC
        self.assertEqual(clone.call_count,2)  # candidate and detached commit
        self.assertTrue(v.validate_world(world).is_valid)

    def test_optimized_and_reference_gates_commit_identical_world_and_save(self):
        target=window(self.base,'round-trip'); outputs=[]
        for reference in (False,True):
            world=deepcopy(self.base)
            with ExitStack() as stack:
                if reference: legacy_gates(stack)
                request=begin_resolution(world,target,shared=True,max_batch_events=2)
                while not request.finished: request.step()
                self.assertTrue(request.result.succeeded)
            self.assertEqual(canonical_world(world),canonical_world(save_reload(world)))
            outputs.append(canonical_world(world))
        self.assertEqual(*outputs)

    def test_validation_retains_no_world_or_per_call_field_validity(self):
        world=deepcopy(self.base)
        self.assertTrue(v.validate_world(world).is_valid)
        record=next(iter(world['world_state']['airlines'].values()))
        record['new_minor']=False
        self.assertFalse(self.assert_full_gate(world)['is_valid'])
        del record['new_minor']
        self.assertTrue(self.assert_full_gate(world)['is_valid'])

if __name__=='__main__': unittest.main()
