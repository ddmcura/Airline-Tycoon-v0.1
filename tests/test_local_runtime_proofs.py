"""Stage 3G-B: local proof induction, sealed selection and exact fallback."""
from copy import deepcopy
import heapq
import unittest
from unittest.mock import patch

from game.simulation import kernel
from game.simulation.candidate_ownership import CandidateOwnership
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import resolve_until
from game.world_state import validate_world
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import canonical_world, save_reload


class LocalProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_runtime_handlers()
        cls.base = flight_world(3)

    def setUp(self): self.world = deepcopy(self.base)

    def prepared(self):
        heap = kernel.build_event_queue_index(self.world)
        event_id = heap[0][3]
        event = self.world['world_state']['pending_events'][event_id]
        contract = kernel.DEFAULT_EVENT_HANDLERS.execution_contract_for(event['event_type'])
        owner = CandidateOwnership(self.world)
        cap = owner.begin(contract.mutation_footprint(self.world,event_id), local=True)
        before = kernel._event_contract_witness(self.world,ownership=cap)
        witness = contract.capture_transition(self.world,event_id,before,ownership=cap)
        ticket = kernel._seal_canonical_selection(cap,heap)
        cap.envelope['simulation']['time_utc'] = event['due_at_utc']
        return owner,cap,contract,before,witness,ticket,heap,event_id

    def test_selector_and_equal_utc_ties_match_original_minimum(self):
        owner,cap,contract,before,witness,ticket,heap,event_id = self.prepared()
        expected = min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        self.assertEqual(ticket.event(cap.envelope),expected)
        self.assertEqual(heap[0],kernel._event_key(expected))

    def test_public_raw_event_and_plain_heap_cannot_grant_selection(self):
        owner,cap,_,_,_,ticket,heap,_ = self.prepared()
        with self.assertRaises(ValueError): kernel._selected_event(ticket.event(cap.envelope),cap.envelope)
        with self.assertRaises(ValueError): kernel._CanonicalSelection(cap,heap)
        with self.assertRaises(ValueError): kernel._seal_canonical_selection(cap,list(heap))
        with self.assertRaises(ValueError): kernel._CanonicalQueue(list(heap))
        with self.assertRaises(ValueError): kernel._seal_canonical_selection(cap,kernel.build_event_queue_index(deepcopy(self.world)))

    def test_selection_rejects_removed_replaced_and_modified_record(self):
        for change in ('remove','replace','modify'):
            _,cap,_,_,_,ticket,_,event_id = self.prepared()
            if change=='remove': del cap.envelope['world_state']['pending_events'][event_id]
            elif change=='replace': cap.envelope['world_state']['pending_events'][event_id]=deepcopy(ticket._event)
            else: cap.envelope['world_state']['pending_events'][event_id]['operation_revision']=True
            with self.assertRaises(ValueError): ticket.event(cap.envelope)

    def test_same_time_earlier_child_invalidates_selection(self):
        _,cap,_,_,_,ticket,_,event_id = self.prepared()
        kernel.schedule_event(cap.envelope,event_type='NO_OP',due_at_utc=ticket._utc,
            owner_type='dated_flight',owner_id=ticket._event['owner_id'],priority=0)
        with self.assertRaises(ValueError): ticket.event(cap.envelope)

    def test_heap_progress_and_clock_progress_invalidate_selection(self):
        for change in ('heap','clock'):
            _,cap,_,_,_,ticket,heap,_ = self.prepared()
            if change=='heap': heapq.heappop(heap)
            else: cap.envelope['simulation']['time_utc']='2026-09-30T00:00:00Z'
            with self.assertRaises(ValueError): ticket.event(cap.envelope)

    def test_explicit_close_candidate_close_and_foreign_envelope_reject(self):
        owner,cap,_,_,_,ticket,_,_ = self.prepared()
        with self.assertRaises(ValueError): ticket.event(deepcopy(self.world))
        ticket.close()
        with self.assertRaises(ValueError): ticket.event(cap.envelope)
        owner,cap,_,_,_,ticket,_,_ = self.prepared(); owner.close()
        with self.assertRaises(ValueError): ticket.event(cap.envelope)

    def test_local_predecessor_contains_only_affected_event_ids(self):
        _,cap,_,before,_,_,_,event_id = self.prepared()
        self.assertEqual(set(before['world_state']['pending_events']),{event_id})
        self.assertEqual(before['world_state']['event_history'],{})
        for name,keys in cap.footprint.items():
            self.assertLessEqual(len(dict.keys(cap.envelope['world_state'][name])),len(keys))

    def test_protected_rows_are_not_reachable_by_base_dict_mutators(self):
        _,cap,_,_,_,_,_,_ = self.prepared()
        table=cap.envelope['world_state']['aircraft']
        other=next(k for k in table if k not in cap.footprint['aircraft'])
        with self.assertRaises(KeyError): dict.__getitem__(table,other)
        with self.assertRaises(ValueError): table[other]['status']='IN_FLIGHT'
        dict.__setitem__(table,other,{})
        with self.assertRaises(ValueError): cap.checked_outputs()

    def test_local_kernel_rejects_unapproved_event_key(self):
        _,cap,_,before,_,_,_,_ = self.prepared()
        dict.__setitem__(cap.envelope['world_state']['pending_events'],'illegal',{})
        with self.assertRaises(ValueError): kernel._event_proof_world(before,cap.envelope)

    def test_alias_and_non_json_output_still_rejected(self):
        for attack in ('alias','non-json'):
            _,cap,_,_,_,_,_,_ = self.prepared()
            if attack=='alias':
                shared=[]; cap.envelope['simulation']['attack']=[shared,shared]
            else: cap.envelope['simulation']['attack']=()
            with self.assertRaises(ValueError): cap.checked_outputs()

    def test_previous_capsules_expire_after_any_publication(self):
        owner,cap,contract,before,witness,ticket,heap,event_id=self.prepared()
        dormant=owner.begin(cap.footprint,local=True)
        outcome,failure,generated=kernel._apply_handler_candidate(before,cap.envelope,event_id,contract.handler,selection=ticket)
        self.assertIsNone(failure)
        contract.validate_transition(witness,cap.envelope,event_id,generated)
        owner.publish(self.world,cap)
        with self.assertRaises(ValueError): dormant.checked_outputs()
        with self.assertRaises(ValueError): ticket.event(cap.envelope)

    def test_failure_revokes_selection_without_consuming_pending_authority(self):
        _,cap,_,before,_,ticket,_,event_id=self.prepared()
        original=canonical_world(self.world)
        def fail(context): raise ValueError('fail before commit')
        _,failure,_=kernel._apply_handler_candidate(before,cap.envelope,event_id,fail,selection=ticket)
        self.assertEqual(failure.code,'HANDLER_FAILED')
        with self.assertRaises(ValueError): ticket.event(cap.envelope)
        self.assertEqual(canonical_world(self.world),original)
        self.assertTrue(kernel.process_next_event(self.world).succeeded)
        self.assertIn(event_id,self.world['world_state']['event_history'])
        self.assertNotIn(event_id,self.world['world_state']['pending_events'])

    def test_optimized_handler_never_re_scans_canonical_queue(self):
        from game.aircraft_operations import fulfilment
        with patch.object(fulfilment,'_next_event',side_effect=AssertionError('queue rescan')):
            result=resolve_until(self.world,window(self.world,'round-trip'),shared=True)
        self.assertTrue(result.succeeded,result.failure)

    def test_local_transition_matches_global_shadow_and_strict(self):
        expected=deepcopy(self.world); target=window(self.world,'round-trip')
        self.assertTrue(kernel.process_events_through(expected,target).succeeded)
        for cap in (1,2,8,64):
            actual=deepcopy(self.world)
            result=resolve_until(actual,target,shared=True,shadow=True,max_batch_events=cap)
            self.assertTrue(result.succeeded,result.failure)
            self.assertEqual(canonical_world(actual),canonical_world(expected))
            self.assertEqual(canonical_world(save_reload(actual)),canonical_world(actual))
            self.assertEqual(actual['metadata']['save_schema_version'],8)

    def test_domain_corruption_cannot_be_repaired_by_later_event(self):
        original_apply=kernel._apply_handler_candidate
        def corrupt(before,candidate,event_id,handler,**kwargs):
            result=original_apply(before,candidate,event_id,handler,**kwargs)
            if before.get('_ownership') is not None:
                flight=candidate['world_state']['dated_flights'][next(iter(before['_ownership'].footprint['dated_flights']))]
                flight['airline_id']='airline:invalid'
            return result
        expected=deepcopy(self.world); self.assertTrue(kernel.process_next_event(expected).succeeded)
        with patch.object(kernel,'_apply_handler_candidate',corrupt):
            result=resolve_until(self.world,window(self.world,'round-trip'),shared=True)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE')
        self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_global_reference_witness_remains_full(self):
        before=kernel._event_contract_witness(self.world)
        self.assertEqual(before['world_state']['pending_events'],self.world['world_state']['pending_events'])
        self.assertEqual(before['world_state']['event_history'],self.world['world_state']['event_history'])
        self.assertNotIn('_ownership',before)

    def test_existing_history_and_pending_records_cannot_be_replaced(self):
        _,cap,_,_,_,_,_,event_id=self.prepared()
        for name in ('pending_events','event_history'):
            table=cap.envelope['world_state'][name]
            key=next(k for k in table if k not in cap.footprint[name])
            with self.assertRaises(ValueError): table[key]={}
            dict.__setitem__(table,key,{})
            with self.assertRaises(ValueError): cap.checked_outputs()

    def test_ownership_mismatch_and_duplicate_result_do_not_gain_certification(self):
        from game.world_state.flight_transition_validation import supports_departure
        event=min(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        flight=self.world['world_state']['dated_flights'][event['owner_id']]
        aircraft=self.world['world_state']['aircraft'][flight['planned_aircraft_id']]
        aircraft['airline_id']='airline:invalid'
        self.assertFalse(supports_departure(self.world,event))
        aircraft['airline_id']=flight['airline_id']
        self.world['world_state']['flight_results'][flight['dated_flight_id']]={}
        self.assertFalse(supports_departure(self.world,event))

    def test_unrelated_source_type_or_output_table_replacement_is_rejected(self):
        _,cap,_,_,_,_,_,_=self.prepared()
        table=cap.envelope['world_state']['aircraft']
        table._base=dict(table._base)
        with self.assertRaises(ValueError): cap.checked_outputs()
        _,cap,_,_,_,_,_,_=self.prepared()
        cap.envelope['world_state']['aircraft']=dict(cap.envelope['world_state']['aircraft'])
        with self.assertRaises(ValueError): cap.checked_outputs()

    def test_limits_remain_100_and_10000(self):
        self.assertEqual(kernel.DEFAULT_MAX_GENERATED_EVENTS_PER_ADVANCE,100)
        self.assertEqual(kernel.DEFAULT_MAX_EVENTS_PER_ADVANCE,10000)


if __name__=='__main__': unittest.main()
