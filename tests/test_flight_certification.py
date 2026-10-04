"""Independent Stage 3C Departure/Completion and mixed certification gates."""
from copy import deepcopy
from functools import partial
import tempfile
import unittest
from unittest.mock import patch
from game.simulation import kernel,shared_candidate
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.execution_contracts import ExecutionMode,SharedExecutionState
from game.simulation.resolver import begin_resolution,resolve_until
from game.world_state import validate_world,flight_transition_validation as proof
from tests.flight_fixtures import flight_world,window
from tests.resolution_oracle import assert_equivalent,canonical_world,save_reload


def next_flight_event(world):
    return min(world['world_state']['pending_events'].values(),key=kernel._event_key)['event_id']


def transition(world,capture,validate):
    event_id=next_flight_event(world)
    event=world['world_state']['pending_events'][event_id]
    before=capture(world,event_id,kernel._event_contract_witness(world))
    outcome,failure,generated=kernel._apply_handler_candidate(before['kernel'],world,event_id,
        kernel.DEFAULT_EVENT_HANDLERS.handler_for(event['event_type']))
    assert failure is None,failure
    validate(before,world,event_id,generated)
    return before,event_id,generated


class DepartureProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3)
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def test_each_departure_proves_fully_valid_intermediate(self):
        for _ in range(3):
            transition(self.world,proof.capture_departure,proof.validate_departure)
            self.assertTrue(validate_world(self.world).is_valid)

    def test_changed_and_unchanged_records_are_exact_and_typed(self):
        before,event_id,generated=transition(self.world,proof.capture_departure,proof.validate_departure)
        flight_id=before['flight']['dated_flight_id']; aircraft_id=before['aircraft']['aircraft_id']
        paths=[('world_state','dated_flights',flight_id,'operation_revision'),
            ('world_state','dated_flights',flight_id,'capacity'),
            ('world_state','aircraft',aircraft_id,'current_airport_id'),
            ('world_state','aircraft',aircraft_id,'lifecycle'),
            ('world_state','active_aircraft_operations',flight_id,'booking_witnesses'),
            ('world_state','active_aircraft_operations',flight_id,'maintenance_distance_m'),
            ('world_state','pending_events',generated[0],'order_key'),
            ('world_state','event_history',event_id,'status'),
            ('simulation','operation_revisions',flight_id),('metadata','save_schema_version'),
            ('ui_state','current_focus'),('deterministic_state','id_allocator','next_by_type','transaction')]
        for path in paths:
            with self.subTest(path=path):
                world=deepcopy(self.world); parent=world
                for key in path[:-1]: parent=parent[key]
                parent[path[-1]]='corrupt'
                with self.assertRaises((ValueError,KeyError,TypeError)):
                    proof.validate_departure(before,world,event_id,generated)
        for value in (True,1.0):
            world=deepcopy(self.world); world['world_state']['dated_flights'][flight_id]['operation_revision']=value
            with self.assertRaises(ValueError): proof.validate_departure(before,world,event_id,generated)

    def test_manifest_and_maintenance_freeze_matches_current_domain(self):
        from game.aircraft_operations.fulfilment import _build_confirmed_carriage_manifest
        from game.maintenance.routine import departure_witness
        flight_id=next(iter(self.world['world_state']['dated_flights']))
        expected=_build_confirmed_carriage_manifest(self.world,flight_id)
        before,event_id,_=transition(self.world,proof.capture_departure,proof.validate_departure)
        operation=self.world['world_state']['active_aircraft_operations'][before['flight']['dated_flight_id']]
        self.assertEqual(operation['source_booking_ids'],list(expected.source_booking_ids))
        self.assertTrue(expected.source_booking_ids)
        for key,value in departure_witness(self.world['world_state'],before['flight'],before['aircraft'],
            self.world['simulation']['configuration']['maintenance']).items(): self.assertEqual(operation[key],value)

    def test_equal_json_alias_between_frozen_operations_is_rejected(self):
        first,_,_=transition(self.world,proof.capture_departure,proof.validate_departure)
        second,event_id,generated=transition(self.world,proof.capture_departure,proof.validate_departure)
        operations=self.world['world_state']['active_aircraft_operations']
        operations[second['flight']['dated_flight_id']]['zero_fare_booking_ids']=operations[first['flight']['dated_flight_id']]['zero_fare_booking_ids']
        self.assertFalse(validate_world(self.world).is_valid)
        with self.assertRaisesRegex(ValueError,'mutable-container alias'):
            proof.validate_departure(second,self.world,event_id,generated)

    def test_json_encoding_cannot_hide_noncanonical_container_types(self):
        before,event_id,generated=transition(self.world,proof.capture_departure,proof.validate_departure)
        for invalid in ('tuple','key'):
            with self.subTest(invalid=invalid):
                world=deepcopy(self.world)
                if invalid=='tuple':
                    operation=world['world_state']['active_aircraft_operations'][before['flight']['dated_flight_id']]
                    operation['zero_fare_booking_ids']=tuple(operation['zero_fare_booking_ids'])
                else:
                    revisions=next(iter(world['world_state']['schedule_definitions'].values()))['revisions']
                    revisions[1]=revisions.pop('1')
                self.assertFalse(validate_world(world).is_valid)
                with self.assertRaisesRegex(ValueError,'non-JSON authority'):
                    proof.validate_departure(before,world,event_id,generated)

    def test_unsupported_inputs_keep_strict_fallback(self):
        event=self.world['world_state']['pending_events'][next_flight_event(self.world)]
        self.assertTrue(proof.supports_departure(self.world,event))
        event['payload']['schedule_revision']+=1
        self.assertFalse(proof.supports_departure(self.world,event))

class DepartureSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3); cls.target=window(cls.base,'departure')
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def test_shadow_and_sizes_match_complete_strict_world(self):
        expected=deepcopy(self.world); strict=kernel.process_events_through(expected,self.target)
        for shadow in (True,False):
            for size in (1,2,8,64):
                with self.subTest(shadow=shadow,size=size):
                    world=deepcopy(self.world)
                    actual=resolve_until(world,self.target,shared=True,shadow=shadow,max_batch_events=size)
                    self.assertEqual(actual,strict); self.assertEqual(canonical_world(world),canonical_world(expected))

    def test_one_private_candidate_and_one_detached_commit(self):
        with patch.object(kernel,'validate_world',wraps=kernel.validate_world) as validations,patch.object(
            kernel,'_clone_runtime_world',wraps=kernel._clone_runtime_world) as clones:
            result=resolve_until(self.world,self.target,shared=True)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(validations.call_count,3); self.assertEqual(clones.call_count,2)

    def test_inflight_equal_time_prefix_save_is_exact_and_continues(self):
        expected=deepcopy(self.world); kernel.process_events_through(expected,self.target)
        request=begin_resolution(self.world,self.target,shared=True,max_batch_events=1)
        request.step(); self.assertFalse(request.boundary().current_utc_fully_resolved)
        restored=save_reload(self.world); self.assertEqual(restored,self.world)
        request.close(); self.assertTrue(resolve_until(restored,self.target,shared=True,shadow=True).succeeded)
        self.assertEqual(restored,expected)
        self.assertEqual(len(restored['world_state']['active_aircraft_operations']),3)
        for key in ('protected','expected_operation','capture_departure','candidate_heap'):
            self.assertNotIn(key,canonical_world(restored))

    def test_custom_departure_executes_once_strict(self):
        from game.aircraft_operations.fulfilment import _departure_handler
        calls=[]
        def custom(context): calls.append(context.event['event_id']); _departure_handler(context)
        registry=kernel.EventHandlerRegistry(); registry.register(proof.DEPARTURE,custom)
        actual=resolve_until(self.world,self.target,shared=True,shadow=True,registry=registry)
        self.assertTrue(actual.succeeded,actual.failure); self.assertEqual(calls,list(actual.completed_event_ids))

    def test_first_and_middle_departure_failures_preserve_exact_prefix(self):
        from game.aircraft_operations import fulfilment
        original=fulfilment.departure_operation
        events=sorted(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        for event in events[:3]:
            bad=event['owner_id']
            def fail(envelope,flight,*args):
                if flight['dated_flight_id']==bad: raise ValueError('deliberate departure failure')
                return original(envelope,flight,*args)
            expected=deepcopy(self.world); actual_world=deepcopy(self.world)
            with patch.object(fulfilment,'departure_operation',side_effect=fail):
                strict=kernel.process_events_through(expected,self.target)
                actual=resolve_until(actual_world,self.target,shared=True,shadow=True)
            self.assertEqual(actual,strict); self.assertEqual(actual_world,expected)

    def test_later_departure_cannot_repair_invalid_intermediate_aircraft(self):
        ids=[e['event_id'] for e in sorted(self.world['world_state']['pending_events'].values(),key=kernel._event_key)][:3]
        bad_aircraft=self.world['world_state']['dated_flights'][self.world['world_state']['pending_events'][ids[1]]['owner_id']]['planned_aircraft_id']
        primitive=kernel._apply_handler_candidate; touched=[]
        def faulty(before,candidate,event_id,handler,**options):
            result=primitive(before,candidate,event_id,handler,**options)
            if event_id==ids[1]: candidate['world_state']['aircraft'][bad_aircraft]['current_airport_id']='bad'; touched.append(event_id)
            if event_id==ids[2]: candidate['world_state']['aircraft'][bad_aircraft]['current_airport_id']=None; touched.append(event_id)
            return result
        speculative=deepcopy(self.world)
        for event_id in ids:
            outcome,failure,_=faulty(kernel._event_contract_witness(speculative),speculative,event_id,
                kernel.DEFAULT_EVENT_HANDLERS.handler_for(proof.DEPARTURE))
            self.assertIsNone(failure)
        self.assertTrue(validate_world(speculative).is_valid); touched.clear()
        expected=deepcopy(self.world)
        with patch.object(kernel,'_apply_handler_candidate',side_effect=faulty):
            strict=kernel.process_events_through(expected,self.target)
            actual=resolve_until(self.world,self.target,shared=True)
        self.assertEqual(actual,strict); self.assertEqual(self.world,expected)
        self.assertEqual(actual.completed_event_ids,(ids[0],)); self.assertNotIn(ids[2],touched)

    def test_proof_defect_replays_once_and_disables(self):
        state=SharedExecutionState()
        expected=deepcopy(self.world); kernel.process_next_event(expected)
        with patch.object(proof,'validate_departure',side_effect=ValueError('proof defect')):
            initialize_runtime_handlers()
            result=resolve_until(self.world,self.target,shared=True,execution_state=state)
        initialize_runtime_handlers()
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE'); self.assertFalse(state.enabled)
        self.assertEqual(self.world,expected)

    def test_final_gate_defect_replays_whole_attempt_without_duplicate_effects(self):
        state=SharedExecutionState(); expected=deepcopy(self.world)
        kernel.process_events_through(expected,self.target)
        with patch.object(shared_candidate,'_validate_batch',return_value=validate_world({})):
            result=resolve_until(self.world,self.target,shared=True,execution_state=state)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE'); self.assertFalse(state.enabled)
        self.assertEqual(self.world,expected)

class CompletionProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3); cls.target=window(cls.base,'completion')
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def test_each_completion_proves_fully_valid_intermediate(self):
        for _ in range(3):
            transition(self.world,proof.capture_completion,proof.validate_completion)
            self.assertTrue(validate_world(self.world).is_valid)

    def test_all_financial_and_result_witnesses_are_exact(self):
        before,event_id,generated=transition(self.world,proof.capture_completion,proof.validate_completion)
        flight_id=before['flight']['dated_flight_id']; aid=before['aircraft']['aircraft_id']
        airline=before['airline']['airline_id']; tid=before['expected_transaction']['transaction_id']
        for collection,key,field in [('flight_results',flight_id,'recognized_revenue_minor'),
            ('flight_results',flight_id,'booking_witnesses'),('flight_results',flight_id,'maintenance_expense_minor'),
            ('flight_results',flight_id,'settlement_transaction_id'),('transactions',tid,'entries'),
            ('transactions',tid,'occurred_at_utc'),('transactions',tid,'source_ticket_sale_transaction_ids'),
            ('airlines',airline,'finance_revision'),('aircraft',aid,'lifecycle'),('aircraft',aid,'current_airport_id')]:
            with self.subTest(collection=collection,field=field):
                world=deepcopy(self.world); world['world_state'][collection][key][field]='corrupt'
                with self.assertRaises((ValueError,KeyError,TypeError)):
                    proof.validate_completion(before,world,event_id,generated)
        for key in before['accounts']:
            world=deepcopy(self.world); world['world_state']['financial_accounts'][key]['balance_minor']+=1
            with self.assertRaises(ValueError): proof.validate_completion(before,world,event_id,generated)

    def test_exact_revenue_cost_liability_counters_and_unchanged_bookings(self):
        old=deepcopy(self.world)
        before,event_id,_=transition(self.world,proof.capture_completion,proof.validate_completion)
        result=self.world['world_state']['flight_results'][before['flight']['dated_flight_id']]
        self.assertGreater(result['recognized_revenue_minor'],0)
        self.assertEqual(result['operating_cost_minor'],result['base_operating_cost_minor']+result['maintenance_expense_minor'])
        self.assertEqual(result['operation_revision_after'],result['operation_revision_before']+1)
        for key in ('bookings','itineraries','booking_state'): self.assertEqual(self.world['world_state'][key],old['world_state'][key])
        self.assertEqual(before['cost']['block_seconds'],6000)

    def test_equal_json_alias_between_completed_results_is_rejected(self):
        first,_,_=transition(self.world,proof.capture_completion,proof.validate_completion)
        second,event_id,generated=transition(self.world,proof.capture_completion,proof.validate_completion)
        results=self.world['world_state']['flight_results']
        results[second['flight']['dated_flight_id']]['zero_fare_booking_ids']=results[first['flight']['dated_flight_id']]['zero_fare_booking_ids']
        self.assertFalse(validate_world(self.world).is_valid)
        with self.assertRaisesRegex(ValueError,'mutable-container alias'):
            proof.validate_completion(second,self.world,event_id,generated)

    def test_json_encoding_cannot_hide_tuple_in_completed_result(self):
        before,event_id,generated=transition(self.world,proof.capture_completion,proof.validate_completion)
        result=self.world['world_state']['flight_results'][before['flight']['dated_flight_id']]
        result['zero_fare_booking_ids']=tuple(result['zero_fare_booking_ids'])
        self.assertFalse(validate_world(self.world).is_valid)
        with self.assertRaisesRegex(ValueError,'non-JSON authority'):
            proof.validate_completion(before,self.world,event_id,generated)

    def test_negative_cash_completion_remains_exact(self):
        accounts=self.world['world_state']['financial_accounts']
        cash_id=next(key for key,row in accounts.items() if row['code']=='cash')
        accounts[cash_id]['balance_minor']=0
        self.assertTrue(validate_world(self.world).is_valid)
        expected=deepcopy(self.world)
        strict=kernel.process_events_through(expected,self.target)
        actual=resolve_until(self.world,self.target,shared=True,shadow=True)
        self.assertEqual(actual,strict); self.assertEqual(self.world,expected)
        self.assertLess(self.world['world_state']['financial_accounts'][cash_id]['balance_minor'],0)

    def test_legacy_migrated_v1_inflight_remains_v1(self):
        from game.world_state.fulfilment_validation import MAINTENANCE_WITNESS_FIELDS
        for operation in self.world['world_state']['active_aircraft_operations'].values():
            for key in MAINTENANCE_WITNESS_FIELDS: operation.pop(key)
        self.assertTrue(validate_world(self.world).is_valid)
        before,event_id,_=transition(self.world,proof.capture_completion,proof.validate_completion)
        result=self.world['world_state']['flight_results'][before['flight']['dated_flight_id']]
        self.assertEqual(result['result_version'],1); self.assertNotIn('maintenance_expense_minor',result)

class CompletionSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3); cls.target=window(cls.base,'completion')
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def test_shadow_batch_sizes_and_full_world_equality(self):
        expected=deepcopy(self.world); strict=kernel.process_events_through(expected,self.target)
        for shadow in (False,True):
            for size in (1,2,8,64):
                with self.subTest(shadow=shadow,size=size):
                    world=deepcopy(self.world)
                    actual=resolve_until(world,self.target,shared=True,shadow=shadow,max_batch_events=size)
                    self.assertEqual(actual,strict); self.assertEqual(canonical_world(world),canonical_world(expected))

    def test_one_candidate_two_world_clones_and_three_full_gates(self):
        with patch.object(kernel,'validate_world',wraps=kernel.validate_world) as gates,patch.object(
            kernel,'_clone_runtime_world',wraps=kernel._clone_runtime_world) as clones:
            result=resolve_until(self.world,self.target,shared=True)
        self.assertTrue(result.succeeded,result.failure); self.assertEqual(gates.call_count,3); self.assertEqual(clones.call_count,2)

    def test_completion_prefix_save_preserves_results_pending_events_and_continuation(self):
        expected=deepcopy(self.world); kernel.process_events_through(expected,self.target)
        request=begin_resolution(self.world,self.target,shared=True,max_batch_events=1); request.step()
        self.assertFalse(request.boundary().current_utc_fully_resolved)
        restored=save_reload(self.world); self.assertEqual(restored,self.world)
        self.assertEqual(len(restored['world_state']['flight_results']),1); request.close()
        self.assertTrue(resolve_until(restored,self.target,shared=True,shadow=True).succeeded)
        self.assertEqual(restored,expected)

    def test_first_middle_final_completion_failure_exact_financial_prefix(self):
        from game.aircraft_operations import fulfilment
        original=fulfilment.completion_cost
        events=sorted(self.world['world_state']['pending_events'].values(),key=kernel._event_key)
        for event in events[:3]:
            bad=event['owner_id']
            def fail(envelope,flight,*args):
                if flight['dated_flight_id']==bad: raise ValueError('deliberate completion failure')
                return original(envelope,flight,*args)
            expected=deepcopy(self.world); world=deepcopy(self.world)
            with patch.object(fulfilment,'completion_cost',side_effect=fail):
                strict=kernel.process_events_through(expected,self.target)
                actual=resolve_until(world,self.target,shared=True,shadow=True)
            self.assertFalse(actual.succeeded); self.assertEqual(actual,strict); self.assertEqual(world,expected)

    def test_first_invalid_settlement_cannot_wait_for_later_repair(self):
        ids=[e['event_id'] for e in sorted(self.world['world_state']['pending_events'].values(),key=kernel._event_key)][:3]
        bad_flight=self.world['world_state']['pending_events'][ids[1]]['owner_id']
        primitive=kernel._apply_handler_candidate; touched=[]
        def faulty(before,candidate,event_id,handler,**options):
            outcome=primitive(before,candidate,event_id,handler,**options)
            if event_id==ids[1]: candidate['world_state']['flight_results'][bad_flight]['operating_cost_minor']+=1; touched.append(event_id)
            if event_id==ids[2]: candidate['world_state']['flight_results'][bad_flight]['operating_cost_minor']-=1; touched.append(event_id)
            return outcome
        speculative=deepcopy(self.world)
        for index,event_id in enumerate(ids):
            _,failure,_=faulty(kernel._event_contract_witness(speculative),speculative,event_id,
                kernel.DEFAULT_EVENT_HANDLERS.handler_for(proof.COMPLETION))
            self.assertIsNone(failure)
            if index==1: self.assertFalse(validate_world(speculative).is_valid)
        self.assertTrue(validate_world(speculative).is_valid); touched.clear()
        expected=deepcopy(self.world)
        with patch.object(kernel,'_apply_handler_candidate',side_effect=faulty):
            strict=kernel.process_events_through(expected,self.target)
            actual=resolve_until(self.world,self.target,shared=True)
        self.assertEqual(actual,strict); self.assertEqual(self.world,expected)
        self.assertEqual(actual.completed_event_ids,(ids[0],)); self.assertNotIn(ids[2],touched)

    def test_final_gate_failure_replays_exact_settlement_without_duplicates(self):
        state=SharedExecutionState(); expected=deepcopy(self.world); kernel.process_events_through(expected,self.target)
        with patch.object(shared_candidate,'_validate_batch',return_value=validate_world({})):
            result=resolve_until(self.world,self.target,shared=True,execution_state=state)
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE'); self.assertFalse(state.enabled)
        self.assertEqual(self.world,expected)

    def test_completion_proof_defect_strict_replay_and_continuation(self):
        state=SharedExecutionState(); expected=deepcopy(self.world); kernel.process_events_through(expected,self.target)
        with patch.object(proof,'validate_completion',side_effect=ValueError('completion proof defect')):
            initialize_runtime_handlers()
            result=resolve_until(self.world,self.target,shared=True,execution_state=state)
        initialize_runtime_handlers()
        self.assertEqual(result.failure.code,'OPTIMIZER_DIVERGENCE'); self.assertFalse(state.enabled)
        self.assertTrue(resolve_until(self.world,self.target,shared=True,execution_state=state).succeeded)
        self.assertEqual(self.world,expected)

    def test_custom_completion_handler_has_no_certificate_and_runs_once(self):
        from game.aircraft_operations.fulfilment import _completion_handler
        calls=[]
        def custom(context): calls.append(context.event['event_id']); _completion_handler(context)
        registry=kernel.EventHandlerRegistry(); registry.register(proof.COMPLETION,custom)
        result=resolve_until(self.world,self.target,shared=True,shadow=True,registry=registry)
        self.assertTrue(result.succeeded,result.failure); self.assertEqual(calls,list(result.completed_event_ids))

class MixedFlightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(3,stagger_seconds=3000); cls.target=window(cls.base,'round-trip')
    def setUp(self): initialize_runtime_handlers(); self.world=deepcopy(self.base)

    def test_mixed_order_and_generated_events_all_batch_sizes_shadow(self):
        expected=deepcopy(self.world); strict=kernel.process_events_through(expected,self.target)
        kinds=[expected['world_state']['event_history'][key]['event_type'] for key in strict.completed_event_ids]
        self.assertEqual(set(kinds),{proof.DEPARTURE,proof.COMPLETION})
        self.assertTrue(any(a==proof.COMPLETION and b==proof.DEPARTURE for a,b in zip(kinds,kinds[1:])))
        for shadow in (False,True):
            for size in (1,2,8,64):
                with self.subTest(shadow=shadow,size=size):
                    world=deepcopy(self.world)
                    actual=resolve_until(world,self.target,shared=True,shadow=shadow,max_batch_events=size)
                    self.assertEqual(actual,strict); self.assertEqual(canonical_world(world),canonical_world(expected))

    def test_irregular_boundaries_partitions_inflight_save_full_oracle(self):
        times=sorted({f['scheduled_off_block_utc'] for f in self.world['world_state']['dated_flights'].values()})
        assert_equivalent(self,self.world,self.target,times[:3],save_at=times[0],
            resolver=partial(resolve_until,shared=True,shadow=True),
            request_factory=partial(begin_resolution,shared=True,shadow=True,max_batch_events=2))
        world=deepcopy(self.world); expected=deepcopy(self.world); kernel.process_events_through(expected,self.target)
        request=begin_resolution(world,self.target,shared=True,shadow=True)
        sizes=(1,8,2,1,64); turn=0
        while not request.finished:
            request.max_batch_events=sizes[turn%len(sizes)]; request.step(); turn+=1
            self.assertTrue(validate_world(world).is_valid)
        self.assertEqual(world,expected)

    def test_dictionary_order_does_not_change_ids_manifest_or_results(self):
        expected=deepcopy(self.world); kernel.process_events_through(expected,self.target)
        for collection in ('dated_flights','aircraft','pending_events','bookings','itineraries','transactions','schedule_definitions'):
            self.world['world_state'][collection]=dict(reversed(tuple(self.world['world_state'][collection].items())))
        self.assertTrue(resolve_until(self.world,self.target,shared=True,shadow=True).succeeded)
        self.assertEqual(canonical_world(self.world),canonical_world(expected))

    def test_stage2_fleet_flights_finance_never_see_candidate_and_rebind(self):
        from app.session import Stage1Session
        with tempfile.TemporaryDirectory() as root:
            session=Stage1Session(save_root=root); session.world=deepcopy(self.world)
            for read in (session.fleet,session.flights,session.finances): read()
            old=session._read_views; source=deepcopy(session.world); final=shared_candidate._validate_batch
            def inspect(candidate):
                self.assertEqual(session.world,source)
                for read in (session.fleet,session.flights,session.finances): read()
                self.assertIs(session._read_views,old)
                return final(candidate)
            with patch.object(shared_candidate,'_validate_batch',side_effect=inspect):
                request=begin_resolution(session.world,self.target,shared=True,max_batch_events=64); request.step()
            self.assertFalse(old.matches(session.world,session.progression_revision))
            session._mark_progress()
            for read in (session.fleet,session.flights,session.finances): read()
            self.assertIsNot(session._read_views,old)
            self.assertTrue(session._read_views.matches(session.world,session.progression_revision)); request.close()

    def test_forged_callable_proof_or_version_cannot_inherit_certification(self):
        from dataclasses import replace
        registry=initialize_runtime_handlers()
        class EqualCallable:
            def __eq__(self,other): return True
            def __call__(self,*args): pass
        for kind in (proof.DEPARTURE,proof.COMPLETION):
            contract=registry.execution_contract_for(kind)
            self.assertTrue(proof.is_flight_certificate(contract))
            for forged in (replace(contract,handler=EqualCallable()),replace(contract,version='fake'),
                           replace(contract,validate_transition=lambda *args:None)):
                self.assertFalse(proof.is_flight_certificate(forged))
        self.assertIs(registry.execution_contract_for('AIRCRAFT_CONTRACT_PAYMENT').mode,ExecutionMode.SHARED)
        self.assertIs(registry.execution_contract_for('AIRCRAFT_MARKET_ROTATION').mode,ExecutionMode.STRICT)
        for kind in ('DAILY_BOOKING_CHECKPOINT','STAGE1_WEEKLY_PUBLICATION','AIRCRAFT_CONTRACT_EXPIRY'):
            self.assertIs(registry.execution_contract_for(kind).mode,ExecutionMode.FENCE)

    def test_mixed_middle_completion_failure_matches_strict_successful_prefix(self):
        from game.aircraft_operations import fulfilment
        original=fulfilment.completion_cost
        flight_id=min(self.world['world_state']['dated_flights'].values(),key=lambda f:f['scheduled_off_block_utc'])['dated_flight_id']
        def fail(envelope,flight,operation):
            if flight['dated_flight_id']==flight_id: raise ValueError('mixed completion fault')
            return original(envelope,flight,operation)
        expected=deepcopy(self.world)
        with patch.object(fulfilment,'completion_cost',side_effect=fail):
            strict=kernel.process_events_through(expected,self.target)
            actual=resolve_until(self.world,self.target,shared=True,shadow=True)
        self.assertFalse(actual.succeeded); self.assertEqual(actual,strict); self.assertEqual(self.world,expected)

    def test_final_gate_strict_replay_disagreement_preserves_real_prefix(self):
        execute=kernel._execute_event
        ordered=deepcopy(self.world); events=[]
        while ordered['simulation']['time_utc']<self.target:
            event_id=next_flight_event(ordered); events.append(event_id)
            result=kernel.process_next_event(ordered); self.assertTrue(result.succeeded,result.failure)
        bad=events[3]
        def fail(world,event_id,registry):
            if event_id==bad: return None,kernel.EventFailure('HANDLER_FAILED','replay disagreement',event_id),()
            return execute(world,event_id,registry)
        expected=deepcopy(self.world)
        with patch.object(kernel,'_execute_event',side_effect=fail):
            strict=kernel.process_events_through(expected,self.target)
            with patch.object(shared_candidate,'_validate_batch',return_value=validate_world({})):
                actual=resolve_until(self.world,self.target,shared=True,max_batch_events=64)
        self.assertEqual(actual,strict); self.assertEqual(self.world,expected)
        self.assertEqual(len(actual.completed_event_ids),3)

    def test_shadow_disagreement_discards_speculation_and_disables(self):
        primitive=shared_candidate._shared_transition; state=SharedExecutionState()
        def faulty(candidate,*args,**kwargs):
            result=primitive(candidate,*args,**kwargs)
            candidate['world_state']['airlines'][candidate['world_state']['player']['primary_airline_id']]['display_name']+='?'
            return result
        expected=deepcopy(self.world); kernel.process_next_event(expected)
        with patch.object(shared_candidate,'_shared_transition',side_effect=faulty):
            actual=resolve_until(self.world,self.target,shared=True,shadow=True,execution_state=state)
        self.assertEqual(actual.failure.code,'OPTIMIZER_DIVERGENCE'); self.assertFalse(state.enabled)
        self.assertEqual(self.world,expected)

    def test_schema6_is_valid_strict_fallback_without_divergence(self):
        self.world['metadata']['save_schema_version']=6
        self.world['simulation']['configuration'].pop('maintenance')
        # Schema-6 schedules cannot contain the later rolling-publication options.
        for schedule in self.world['world_state']['schedule_definitions'].values():
            for revision in schedule['revisions'].values():
                revision['recurrence'].pop('publication_policy',None)
                revision['recurrence'].pop('enabled',None)
        self.assertTrue(validate_world(self.world).is_valid)
        expected=deepcopy(self.world); strict=kernel.process_events_through(expected,self.target)
        with patch.object(proof,'capture_departure',side_effect=AssertionError('must stay strict')):
            initialize_runtime_handlers()
            actual=resolve_until(self.world,self.target,shared=True)
        initialize_runtime_handlers()
        self.assertEqual(actual,strict); self.assertEqual(self.world,expected)

    def test_deadhead_round_trip_has_empty_carriage_and_exact_costs(self):
        from game.scheduling import WeeklyDraft
        from tests.profile_scheduling import fresh,identities
        world=fresh(1); owner,aircraft,ports=identities(world)
        draft=WeeklyDraft(world,airline_id=owner,aircraft_id=aircraft)
        draft.add(ports['MNL'],ports['DVO'],departure_utc='2026-09-07T00:01:00Z',deadhead=True)
        draft.add(ports['DVO'],ports['MNL'],departure_utc='2026-09-07T02:11:00Z',deadhead=True)
        self.assertTrue(draft.save(world).succeeded)
        self.assertTrue(kernel.process_events_through(world,'2026-09-07T00:00:59Z').succeeded)
        target=window(world,'round-trip'); expected=deepcopy(world)
        strict=kernel.process_events_through(expected,target)
        self.assertEqual(resolve_until(world,target,shared=True,shadow=True),strict)
        self.assertEqual(world,expected)
        for row in world['world_state']['flight_results'].values():
            self.assertEqual(row['source_booking_ids'],[])
            self.assertEqual(row['carried_passenger_count'],0)
            self.assertEqual(row['recognized_revenue_minor'],0)

    def test_completion_preserves_public_departure_substitution(self):
        from game.aircraft_operations import process_flight_departure
        from game.world_state import add_aircraft
        from tests.test_stage1_terminal_harness import planned_world
        from tests.test_stage1_flight_fulfilment import departure_witnesses
        world,owner,starter,schedule=planned_world()
        flight_id=schedule.dated_flight_ids[1]; flight=world['world_state']['dated_flights'][flight_id]
        substitute=add_aircraft(world,owner,'TEST-SHARED-SUB','boeing-787-9',
            home_airport_id=flight['origin_airport_id'],current_airport_id=flight['origin_airport_id'])
        self.assertTrue(kernel.process_events_through(world,'2026-09-07T03:59:59Z').succeeded)
        world['simulation']['time_utc']=flight['scheduled_off_block_utc']
        self.assertTrue(process_flight_departure(world,flight_id,actual_aircraft_id=substitute,
            **departure_witnesses(world,flight_id)).succeeded)
        expected=deepcopy(world); target=flight['scheduled_in_block_utc']
        strict=kernel.process_events_through(expected,target)
        self.assertEqual(resolve_until(world,target,shared=True,shadow=True),strict)
        self.assertEqual(world,expected)
        result=world['world_state']['flight_results'][flight_id]
        self.assertEqual(result['actual_aircraft_id'],substitute)
        self.assertEqual(result['maintenance_class'],'E')

    def test_zero_fare_round_trip_keeps_zero_revenue_exact(self):
        world=flight_world(1,fare_minor=0); target=window(world,'round-trip')
        expected=deepcopy(world); kernel.process_events_through(expected,target)
        self.assertTrue(resolve_until(world,target,shared=True,shadow=True).succeeded)
        self.assertEqual(world,expected)
        self.assertTrue(all(row['recognized_revenue_minor']==0 for row in world['world_state']['flight_results'].values()))


class FlightFenceTests(unittest.TestCase):
    def test_continuous_weekly_booking_fences_multiple_seeds_and_saved_prefixes(self):
        from tests.test_simulation_resolver import ph_world,published_pair
        for seed in (123,314159):
            base=published_pair(ph_world(seed),continuous=True)
            # Mature genuine history once, then compare all paths across the fences.
            setup=kernel.process_events_through(base,'2026-09-06T15:59:59Z')
            self.assertTrue(setup.succeeded,setup.failure)
            prior=set(base['world_state']['event_history'])
            target='2026-09-07T04:00:00Z'
            expected=assert_equivalent(self,base,target,['2026-09-06T16:00:00Z','2026-09-07T00:00:00Z'],
                save_at='2026-09-07T00:00:01Z',resolver=partial(resolve_until,shared=True,shadow=True),
                request_factory=partial(begin_resolution,shared=True,shadow=True))
            kinds={e['event_type'] for key,e in expected['world_state']['event_history'].items() if key not in prior}
            self.assertTrue({'DAILY_BOOKING_CHECKPOINT','STAGE1_WEEKLY_PUBLICATION',proof.DEPARTURE,proof.COMPLETION}<=kinds)

    def test_real_final_payments_departure_expiry_and_completion_exact_order(self):
        from tests.payment_fixtures import payment_world
        from game.scheduling import WeeklyDraft
        from tests.profile_scheduling import identities
        world,due=payment_world(2,final=True,lead_seconds=1800)
        owner,aircraft,ports=identities(world)
        # Owned starter flies; expiring leased aircraft remain available for return.
        draft=WeeklyDraft(world,airline_id=owner,aircraft_id=aircraft)
        draft.add(ports['MNL'],ports['DVO'],departure_utc=due,fare_minor=11600)
        result=draft.save(world); self.assertTrue(result.succeeded,result)
        target=max(f['scheduled_in_block_utc'] for f in world['world_state']['dated_flights'].values())
        expected=deepcopy(world); strict=kernel.process_events_through(expected,target)
        request=begin_resolution(world,target,shared=True,shadow=True,max_batch_events=64)
        # Keep actual monthly Rotation and Booking inside the tested request;
        # both strict boundaries precede the shared Payment/Departure prefix.
        while any(e['due_at_utc']<due for e in world['world_state']['pending_events'].values()):
            request.step(); self.assertFalse(request.finished)
        preceding=request._completed
        kinds={world['world_state']['event_history'][key]['event_type'] for key in request._completed_ids}
        self.assertTrue({'AIRCRAFT_MARKET_ROTATION','DAILY_BOOKING_CHECKPOINT'}<=kinds)
        prefix=request.step(); self.assertEqual(prefix.completed_event_count,preceding+3)
        self.assertEqual({e['event_type'] for e in world['world_state']['pending_events'].values() if e['due_at_utc']<=due},{'AIRCRAFT_CONTRACT_EXPIRY'})
        restored=save_reload(world); self.assertEqual(restored,world)
        while not request.finished: request.step()
        self.assertEqual(request.result,strict); self.assertEqual(world,expected)
        self.assertTrue(resolve_until(restored,target,shared=True,shadow=True).succeeded); self.assertEqual(restored,expected)

if __name__=='__main__': unittest.main()
