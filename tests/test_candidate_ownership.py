"""Stage 3D.2 structural ownership, local alias and full-oracle regressions."""
from copy import deepcopy
from dataclasses import replace
import random
import unittest
from unittest.mock import patch

from game.simulation import kernel, shared_candidate
from game.simulation import candidate_ownership as ownership_module
from game.simulation.candidate_ownership import (
    CandidateOwnership, ReadOnlyDict, ReadOnlyList, WriteCapsule, require_capsule,
)
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution, resolve_until
from game.world_state import validate_world
from game.world_state import flight_transition_validation as proof
from game.world_state.validation import _container_alias_error
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import canonical_world, save_reload


class ReadBoundaryTests(unittest.TestCase):
    def test_nested_reads_are_structurally_immutable_and_detached(self):
        source={'a':{'b':[{'c':1}]}}
        read=CandidateOwnership(deepcopy(source))._snapshot
        source['a']['b'][0]['c']=2
        self.assertEqual(read['a']['b'][0]['c'],1)
        with self.assertRaises(ValueError): read['a']['b'][0]['c']=3
        with self.assertRaises(TypeError): dict.__setitem__(read['a'],'bad',1)
        with self.assertRaises(TypeError): list.append(read['a']['b'],1)

    def test_dictionary_mutators_and_reinitialization_are_rejected(self):
        row=ReadOnlyDict({'x':1})
        for action in (lambda: row.update(x=2),lambda: row.clear(),lambda: row.pop('x'),
                       lambda: row.setdefault('y',1),lambda: row.__init__({'x':2}),
                       lambda: setattr(row,'_proxy',{}),lambda: delattr(row,'_access')):
            with self.assertRaises(ValueError): action()
        self.assertEqual(row['x'],1)

    def test_list_mutators_and_reinitialization_are_rejected(self):
        row=ReadOnlyList([1])
        for action in (lambda: row.append(2),lambda: row.extend([2]),lambda: row.clear(),
                       lambda: row.pop(),lambda: row.reverse(),lambda: row.sort(),
                       lambda: row.__init__([2]),lambda: row.__iadd__([2])):
            with self.assertRaises(ValueError): action()
        self.assertEqual(row,[1])

    def test_detached_read_copy_is_plain_and_cannot_mutate_snapshot(self):
        read=CandidateOwnership({'a':[{'b':1}]})._snapshot; copy=deepcopy(read)
        self.assertIs(type(copy),dict); self.assertIs(type(copy['a']),list)
        copy['a'][0]['b']=2
        self.assertEqual(read['a'][0]['b'],1)

    def test_alias_and_cycle_baseline_fail_closed(self):
        shared=[]
        for source in ({'a':shared,'b':shared},):
            with self.assertRaisesRegex(ValueError,'alias baseline'): CandidateOwnership(source)
        source=[]; source.append(source)
        with self.assertRaisesRegex(ValueError,'alias baseline'): CandidateOwnership(source)

    def test_noncanonical_baseline_type_is_not_frozen(self):
        with self.assertRaisesRegex(ValueError,'non-JSON ownership baseline'): CandidateOwnership({'bad':()})

    def test_read_memo_is_bounded_to_candidate_and_released_on_close(self):
        source={'rows':[{'value':i} for i in range(1000)]}
        owner=CandidateOwnership(source); rows=owner._snapshot['rows']
        for row in rows: self.assertIsInstance(row['value'],int)
        del row
        self.assertLessEqual(len(owner._views),1002)
        self.assertEqual(len(source['rows']),1000)
        owner.close()
        self.assertEqual(owner._views,{})

    def test_forged_capsule_or_envelope_cannot_grant_proof(self):
        with self.assertRaises(ValueError): WriteCapsule(ReadOnlyDict({}),{})
        with self.assertRaises(ValueError): require_capsule(object(),{})


class OwnershipTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3)
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def prepared(self, completion=False):
        if completion:
            self.assertTrue(kernel.process_events_through(self.world,window(self.world,'departure')).succeeded)
        event=min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        contract=kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(event['event_type'])
        owner=CandidateOwnership(self.world)
        capsule=owner.begin(contract.mutation_footprint(self.world,event['event_id']))
        before=kernel._event_contract_witness(self.world)
        witness=contract.capture_transition(capsule.envelope,event['event_id'],before,ownership=capsule)
        outcome,failure,generated=kernel._apply_handler_candidate(before,capsule.envelope,event['event_id'],contract.handler)
        self.assertIsNone(failure)
        return owner,capsule,contract,witness,event['event_id'],generated

    def test_selected_outputs_match_full_protected_and_alias_oracles(self):
        for completion in (False,True):
            self.world=deepcopy(self.base)
            if completion: kernel.process_events_through(self.world,window(self.world,'departure'))
            event=min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
            contract=kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(event['event_type'])
            before=kernel._event_contract_witness(self.world)
            oracle=contract.capture_transition(self.world,event['event_id'],before)
            expected=deepcopy(self.world); self.assertTrue(kernel.process_next_event(expected).succeeded)
            owner=CandidateOwnership(self.world); capsule=owner.begin(contract.mutation_footprint(self.world,event['event_id']))
            witness=contract.capture_transition(capsule.envelope,event['event_id'],before,ownership=capsule)
            _,failure,generated=kernel._apply_handler_candidate(before,capsule.envelope,event['event_id'],contract.handler)
            self.assertIsNone(failure)
            contract.validate_transition(witness,capsule.envelope,event['event_id'],generated)
            owner.publish(self.world,capsule)
            contract.validate_transition(oracle,self.world,event['event_id'],generated)
            self.assertIsNone(_container_alias_error(self.world))
            self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_raw_predecessor_capture_is_bound_to_exact_private_candidate(self):
        event=min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        contract=kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(event['event_type'])
        owner=CandidateOwnership(self.world)
        cap=owner.begin(contract.mutation_footprint(self.world,event['event_id']))
        before=kernel._event_contract_witness(self.world)
        original=canonical_world(self.world)
        witness=contract.capture_transition(self.world,event['event_id'],before,ownership=cap)
        self.assertEqual(canonical_world(self.world),original)
        with self.assertRaisesRegex(ValueError,'another predecessor'):
            contract.capture_transition(deepcopy(self.world),event['event_id'],before,ownership=cap)
        _,failure,generated=kernel._apply_handler_candidate(before,cap.envelope,event['event_id'],contract.handler)
        self.assertIsNone(failure)
        contract.validate_transition(witness,cap.envelope,event['event_id'],generated)
        owner.publish(self.world,cap)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_protected_read_write_and_unapproved_table_insertion_are_rejected(self):
        owner,cap,*_=self.prepared()
        port=next(iter(cap.envelope['world_state']['airports'].values()))
        with self.assertRaises(ValueError): port['corrupt']=True
        with self.assertRaises(ValueError): cap.envelope['world_state']['dated_flights']['bad']={}

    def test_root_replacement_is_rejected(self):
        owner,cap,*_=self.prepared()
        cap.envelope['ui_state']=deepcopy(cap.envelope['ui_state'])
        with self.assertRaisesRegex(ValueError,'protected root'): cap.checked_outputs()

    def test_base_table_bypass_is_rejected_by_identity_and_topology_seals(self):
        for attack in ('existing','new'):
            owner,cap,*_=self.prepared()
            table=cap.envelope['world_state']['aircraft']
            if attack=='existing':
                key=next(k for k in table if k not in cap.footprint['aircraft'])
                dict.__setitem__(table,key,deepcopy(table[key]))
            else: dict.__setitem__(table,'illegal',{})
            with self.assertRaises(ValueError): cap.checked_outputs()

    def test_changed_or_new_output_cannot_insert_protected_containers(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        operation=cap.envelope['world_state']['active_aircraft_operations'][witness['flight']['dated_flight_id']]
        operation['zero_fare_booking_ids']=cap.envelope['ui_state']['filters'].get('empty',ReadOnlyList([]))
        with self.assertRaisesRegex(ValueError,'non-JSON'): cap.checked_outputs()

    def test_manifest_equal_value_alias_is_rejected(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        operation=cap.envelope['world_state']['active_aircraft_operations'][witness['flight']['dated_flight_id']]
        self.assertEqual(operation['paid_booking_ids'],operation['source_booking_ids'])
        operation['paid_booking_ids']=operation['source_booking_ids']
        with self.assertRaisesRegex(ValueError,'alias'): cap.checked_outputs()

    def test_generated_event_payload_alias_is_rejected(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        cap.envelope['world_state']['pending_events'][generated[0]]['payload']=cap.envelope['simulation']['fast_forward']
        with self.assertRaisesRegex(ValueError,'alias'): cap.checked_outputs()

    def test_journal_result_equal_value_alias_is_rejected(self):
        owner,cap,contract,witness,event_id,generated=self.prepared(completion=True)
        transaction=witness['expected_transaction']['transaction_id']; flight=witness['flight']['dated_flight_id']
        journal=cap.envelope['world_state']['transactions'][transaction]
        result=cap.envelope['world_state']['flight_results'][flight]
        self.assertEqual(journal['source_booking_ids'],result['paid_booking_ids'])
        result['paid_booking_ids']=journal['source_booking_ids']
        with self.assertRaisesRegex(ValueError,'alias'): cap.checked_outputs()

    def test_nested_journal_entry_alias_is_rejected(self):
        owner,cap,contract,witness,event_id,generated=self.prepared(completion=True)
        journal=cap.envelope['world_state']['transactions'][witness['expected_transaction']['transaction_id']]
        journal['entries'][1]=journal['entries'][0]
        with self.assertRaisesRegex(ValueError,'alias'): cap.checked_outputs()

    def test_result_cannot_alias_another_protected_active_operation(self):
        owner,cap,contract,witness,event_id,generated=self.prepared(completion=True)
        flight=witness['flight']['dated_flight_id']
        others=cap.envelope['world_state']['active_aircraft_operations']
        other=next(row for key,row in others.items() if key!=flight)
        cap.envelope['world_state']['flight_results'][flight]['source_booking_ids']=other['source_booking_ids']
        with self.assertRaisesRegex(ValueError,'non-JSON'): cap.checked_outputs()

    def test_randomized_local_alias_decisions_match_complete_canonical_oracle(self):
        rng=random.Random(42103); owner=CandidateOwnership(self.world)
        event=min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        contract=kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(event['event_type'])
        footprint=contract.mutation_footprint(self.world,event['event_id'])
        for turn in range(24):
            cap=owner.begin(footprint)
            graph={'left':[{'n':rng.randrange(9)}],'right':[{'n':rng.randrange(9)}]}
            if turn%2: graph['right']=graph['left']
            if turn%3: graph=dict(reversed(tuple(graph.items())))
            cap.envelope['simulation']['test_graph']=graph
            complete=deepcopy(self.world); complete['simulation']=cap.envelope['simulation']
            rejected=_container_alias_error(complete) is not None
            if rejected:
                with self.assertRaisesRegex(ValueError,'alias'): cap.checked_outputs()
            else: cap.checked_outputs()

    def test_publication_divergence_cannot_wait_for_later_repair(self):
        real=ownership_module.deepcopy
        def stale(value,*args):
            result=real(value,*args)
            if type(result) is dict and 'records' in result and 'simulation' in result:
                aircraft=next(iter(result['records']['aircraft'].values()))
                aircraft['status']='PARKED'
            return result
        expected=deepcopy(self.world); self.assertTrue(kernel.process_next_event(expected).succeeded)
        with patch.object(ownership_module,'deepcopy',stale):
            result=resolve_until(self.world,window(self.world,'round-trip'),shared=True,max_batch_events=64)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE')
        self.assertEqual(len(result.completed_event_ids),1)
        self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_full_gated_noop_discards_and_restarts_ownership_baseline(self):
        owner_id=self.world['world_state']['player']['primary_airline_id']
        due=min(f['scheduled_off_block_utc'] for f in self.world['world_state']['dated_flights'].values())
        kernel.schedule_event(self.world,event_type='NO_OP',due_at_utc=due,owner_type='airline',owner_id=owner_id,priority=150)
        target=window(self.world,'round-trip'); expected=deepcopy(self.world)
        self.assertTrue(kernel.process_events_through(expected,target).succeeded)
        real=CandidateOwnership.__init__; calls=[]
        def recorded(instance,candidate,**kwargs): calls.append(True); real(instance,candidate,**kwargs)
        with patch.object(CandidateOwnership,'__init__',recorded):
            result=resolve_until(self.world,target,shared=True,max_batch_events=64)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(len(calls),2)
        self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_output_publication_breaks_external_and_retained_references(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        contract.validate_transition(witness,cap.envelope,event_id,generated)
        operation=cap.envelope['world_state']['active_aircraft_operations'][witness['flight']['dated_flight_id']]
        external=[]; operation['zero_fare_booking_ids']=external
        owner.publish(self.world,cap)
        stored=self.world['world_state']['active_aircraft_operations'][witness['flight']['dated_flight_id']]
        self.assertIsNot(stored['zero_fare_booking_ids'],external)
        external.append('bad'); operation['state']='bad'
        self.assertEqual(stored['zero_fare_booking_ids'],[])
        self.assertEqual(stored['state'],'OPERATIONALLY_LOCKED')

    def test_read_view_reflects_publication_and_new_capability_is_detached(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        contract.validate_transition(witness,cap.envelope,event_id,generated); owner.publish(self.world,cap)
        self.assertEqual(deepcopy(owner._snapshot),self.world)
        next_event=min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        next_contract=kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(next_event['event_type'])
        other=owner.begin(next_contract.mutation_footprint(self.world,next_event['event_id']))
        with self.assertRaises(ValueError): require_capsule(cap,other.envelope)

    def test_reference_memo_holds_sources_and_close_revokes_all_capabilities(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        aircraft_id=witness['aircraft']['aircraft_id']
        source=self.world['world_state']['aircraft'][aircraft_id]
        old_read=owner._snapshot['world_state']['aircraft'][aircraft_id]
        contract.validate_transition(witness,cap.envelope,event_id,generated)
        owner.publish(self.world,cap)
        self.assertIs(owner._views[id(source)][0],source)
        self.assertEqual(old_read['aircraft_id'],aircraft_id)
        self.assertIsNot(owner._snapshot['world_state']['aircraft'][aircraft_id],old_read)
        with self.assertRaisesRegex(ValueError,'expired'): owner.publish(self.world,cap)
        owner.close()
        self.assertEqual(owner._views,{})
        self.assertIsNone(owner._candidate)
        with self.assertRaisesRegex(ValueError,'expired'): old_read['status']
        with self.assertRaisesRegex(ValueError,'expired'): owner.begin(cap.footprint)

    def test_foreign_candidate_cannot_use_another_candidates_capsule(self):
        owner,cap,contract,witness,event_id,generated=self.prepared()
        other_world=deepcopy(self.world); other=CandidateOwnership(other_world)
        with self.assertRaisesRegex(ValueError,'another candidate'): other.publish(other_world,cap)

    def test_first_boundary_violation_after_valid_prefix_uses_strict_recovery(self):
        expected=deepcopy(self.world)
        for _ in range(4): self.assertTrue(kernel.process_next_event(expected).succeeded)
        actual=kernel._apply_handler_candidate; calls=0
        def faulty(original,candidate,event_id,handler,**options):
            nonlocal calls
            result=actual(original,candidate,event_id,handler,**options); calls+=1
            if calls==4: candidate['world_state']['airports'][next(iter(candidate['world_state']['airports']))]['bad']=True
            return result
        with patch.object(kernel,'_apply_handler_candidate',faulty):
            result=resolve_until(self.world,window(self.world,'round-trip'),shared=True,max_batch_events=64)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE')
        self.assertEqual(len(result.completed_event_ids),4)
        self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_owned_path_does_not_call_full_protected_encoding(self):
        with patch.object(proof,'protected_bytes',side_effect=AssertionError('full encoding forbidden')):
            result=resolve_until(self.world,window(self.world,'round-trip'),shared=True,max_batch_events=64)
        self.assertTrue(result.succeeded,result.failure)

    def test_full_shadow_protected_oracle_is_retained(self):
        with patch.object(proof,'protected_bytes',wraps=proof.protected_bytes) as full:
            result=resolve_until(self.world,window(self.world,'departure'),shared=True,shadow=True,max_batch_events=64)
        self.assertTrue(result.succeeded,result.failure); self.assertGreater(full.call_count,0)

    def test_footprint_metadata_is_bound_to_exact_certificate(self):
        contract=kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(proof.DEPARTURE)
        self.assertFalse(proof.is_flight_certificate(replace(contract,mutation_footprint=lambda *args:{})))

    def test_no_ownership_state_survives_return_or_save_load(self):
        request=begin_resolution(self.world,window(self.world,'round-trip'),shared=True,max_batch_events=2)
        while not request.finished:
            request.step()
            self.assertTrue(validate_world(self.world).is_valid)
            self.assertFalse(any(isinstance(value,(CandidateOwnership,WriteCapsule)) for value in vars(request).values()))
        self.assertEqual(canonical_world(save_reload(self.world)),canonical_world(self.world))


if __name__=='__main__': unittest.main()
