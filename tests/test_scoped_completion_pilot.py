"""Production opt-in pilot: differential ownership, faults and request accounting."""
from copy import deepcopy
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel, owned_event
from game.simulation.resolver import begin_resolution
from game.aircraft_operations import scoped_completion, fulfilment
from game.world_state.flight_proof_witness import protected_bytes
from tests import test_scoped_completion_experiment as fixtures
from tests.test_stage1_runtime import Clock


class ScopedPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ScopedCompletionTests.setUpClass()
        cls.source = fixtures.ScopedCompletionTests.source
        cls.event = fixtures.ScopedCompletionTests.event
        cls.fid = fixtures.ScopedCompletionTests.fid

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def make(self, enabled=True, source=None, clock=None):
        s = Stage1Session(closed_owner=True, scoped_completion=enabled,
                          save_root=self.temp.name, runtime_clock=clock or (lambda:0))
        s.world = self.source if source is None else source
        s.career_id = s._save_store.new_career_id(); s._reset_autosave_clocks()
        return s

    def equal(self, actual, control):
        self.assertEqual(protected_bytes(actual._world), protected_bytes(control._world))
        self.assertEqual(actual.authoritative_bytes(), control.authoritative_bytes())

    def test_configuration_default_and_public_interfaces(self):
        with self.assertRaises(ValueError): Stage1Session(scoped_completion=True)
        default = self.make(False); self.assertIsNone(default.scoped_completion_status())
        s = self.make(); s._ensure_runtime()
        for name in ('world','runtime','save_store'):
            with self.assertRaises(AttributeError): getattr(s,name)
        status = s.scoped_completion_status(); status['counts'].clear()
        self.assertTrue(s.scoped_completion_status()['counts'])

    def test_next_event_exact_world_report_and_zero_event_clones(self):
        s = self.make(); control = self.make(False); root = s._world
        with patch.object(kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones:
            actual = s.advance_next_event()
        expected = control.advance_next_event()
        self.assertEqual(clones.call_count, 0)
        self.assertEqual(actual, expected); self.equal(s,control)
        self.assertIs(s._world, root)
        counts = s.scoped_completion_status()['counts']
        self.assertEqual(counts['committed'],1); self.assertEqual(counts['copied_existing_records'],9)
        self.assertEqual(s.ownership_counts()['acquisitions'],1)

    def test_successive_requests_interleaved_strict_events(self):
        s = self.make(); control = self.make(False); binding = s.binding_revision
        self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)
        target = min(control._world['world_state']['pending_events'].values(),key=kernel._event_key)['due_at_utc']
        self.assertEqual(s.advance_to(target),control.advance_to(target)); self.equal(s,control)
        self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)
        self.assertEqual(s.scoped_completion_status()['counts']['committed'],2)
        self.assertEqual(s.binding_revision,binding); self.assertEqual(s.ownership_counts()['acquisitions'],1)

    def test_cooperative_budget_counts_completion_once(self):
        source = deepcopy(self.source)
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=source['simulation']['time_utc'],
                              owner_type='airline',owner_id=source['world_state']['player']['primary_airline_id'])
        observations=[]
        for enabled in (False,True):
            s=self.make(enabled,source); s._ensure_runtime()
            request=begin_resolution(s._world,self.event['due_at_utc'],shared=True,
                max_batch_events=1,max_events=2,max_generated_events=1,
                execution_state=s._runtime.execution_state,**s._event_options())
            while not request.finished: request.step()
            observations.append((request.result,protected_bytes(s._world),request._completed,request._generated))
        self.assertEqual(observations[0],observations[1]); self.assertEqual(observations[1][2],2)

    def test_equal_utc_admission_does_not_add_command_boundary(self):
        source=deepcopy(self.source)
        aircraft=source['world_state']['active_aircraft_operations'][self.fid]['actual_aircraft_id']
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=self.event['due_at_utc'],
            owner_type='aircraft',owner_id=aircraft,operation_revision=0,priority=99,payload={})
        s=self.make(True,source); control=self.make(False,source)
        self.assertEqual(s.advance_to(self.event['due_at_utc']),control.advance_to(self.event['due_at_utc']))
        self.equal(s,control)

    def test_precommit_faults_strict_recover_disable_and_preserve_result(self):
        for stage in ('output_detachment','successor_validation','publication_preparation','before_installation'):
            with self.subTest(stage=stage):
                s=self.make(); control=self.make(False)
                strict=control.advance_next_event()
                reached=[]
                def fail(current):
                    if current==stage: reached.append(stage); raise RuntimeError(stage)
                with patch.object(owned_event,'_fault',fail): report=s.advance_next_event()
                self.assertEqual(reached,[stage]); self.assertEqual(report.result.failure.code,'OPTIMIZER_DIVERGENCE')
                self.assertEqual(report.result.completed_event_ids,strict.result.completed_event_ids)
                self.assertEqual(report.event_rows,strict.event_rows); self.equal(s,control)
                self.assertFalse(s.scoped_completion_status()['enabled'])
                # The latch is reused by the next request, which remains strict.
                self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)

    def test_partial_installation_rolls_back_then_strict_recovery(self):
        s=self.make(); control=self.make(False); control.advance_next_event()
        def partial(world,successor):
            world['simulation']=successor['simulation']; raise RuntimeError('partial')
        with patch.object(owned_event,'_install',partial): report=s.advance_next_event()
        self.assertEqual(report.result.failure.code,'OPTIMIZER_DIVERGENCE'); self.equal(s,control)
        self.assertEqual(s.scoped_completion_status()['counts']['restorations'],1)

    def test_real_handler_failure_keeps_original_error_prefix_allocator_and_retry(self):
        s=self.make(); control=self.make(False)
        allocate=fulfilment.allocate_id
        def fail(*args): allocate(*args); raise RuntimeError('after allocation')
        before=protected_bytes(s._world)
        with patch.object(fulfilment,'allocate_id',fail):
            actual=s.advance_next_event(); expected=control.advance_next_event()
        self.assertEqual(actual,expected); self.equal(s,control)
        self.assertEqual(protected_bytes(s._world),before)
        self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)

    def test_nested_alias_and_retained_writes(self):
        s=self.make(); control=self.make(False); retained=[]
        def hold(stage,capsule):
            if stage=='after_handler': retained.append(capsule.envelope['world_state']['flight_results'][self.fid])
        with patch.object(scoped_completion,'_fault',hold): actual=s.advance_next_event()
        self.assertEqual(actual,control.advance_next_event())
        retained[0]['booking_witnesses'][0]['passenger_count']=999
        self.equal(s,control)
        s=self.make(); control=self.make(False)
        def alias(stage,capsule):
            if stage=='after_handler':
                w=capsule.envelope['world_state']; r=w['flight_results'][self.fid]
                old=protected_bytes(r); r['quarterly_lineage']=w['dated_flights'][self.fid]['quarterly_lineage']
                self.assertEqual(old,protected_bytes(r))
        with patch.object(scoped_completion,'_fault',alias): actual=s.advance_next_event()
        control.advance_next_event(); self.equal(s,control)
        self.assertEqual(actual.result.failure.code,'OPTIMIZER_DIVERGENCE')

    def test_postcommit_faults_and_return_receipt_never_repeat_event(self):
        for stage in ('after_installation_before_marker','after_commit_marker','receipt_return'):
            with self.subTest(stage=stage):
                s=self.make(); control=self.make(False); reached=[]
                def fail(current):
                    if current==stage: reached.append(stage); raise KeyboardInterrupt(stage)
                with patch.object(owned_event,'_fault',fail): actual=s.advance_next_event()
                self.assertEqual(reached,[stage]); self.assertEqual(actual,control.advance_next_event())
                self.equal(s,control); self.assertEqual(s.scoped_completion_status()['counts']['committed'],1)

    def test_authority_return_interruption_recovered_by_event_executor(self):
        s=self.make(); control=self.make(False); reached=[]
        def trace(frame,event,arg):
            if frame.f_code is owned_event._OwnedCompletionAuthority.try_execute.__code__ and event=='return':
                reached.append('return'); raise KeyboardInterrupt('receipt return interrupted')
            return trace
        prior=sys.gettrace()
        try:
            sys.settrace(trace); actual=s.advance_next_event()
        finally: sys.settrace(prior)
        self.assertEqual(reached,['return']); self.assertEqual(actual,control.advance_next_event()); self.equal(s,control)
        self.assertEqual(s.scoped_completion_status()['counts']['committed'],1)

    def test_runtime_retained_request_postcommit_fault_exact_accounting(self):
        from game.simulation.pacing import NANOSECOND
        from game.world_state.timestamps import parse_canonical_utc
        source=deepcopy(self.source)
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=source['simulation']['time_utc'],
            owner_type='airline',owner_id=source['world_state']['player']['primary_airline_id'])
        observations=[]
        for enabled in (False,True):
            clock=Clock(); s=self.make(enabled,source,clock); s.resume(); runtime=s._runtime
            runtime.max_batch_events=1
            seconds=int((parse_canonical_utc(self.event['due_at_utc'])-parse_canonical_utc(s.simulation_time_utc)).total_seconds())
            clock.advance((seconds//30+1)*NANOSECOND); s.pump(); request=runtime.work; base=s._world
            self.assertIsNotNone(request)
            def fail(stage):
                if enabled and stage=='after_installation_before_marker': raise RuntimeError('postcommit')
            with patch.object(owned_event,'_fault',fail):
                for _ in range(30):
                    s.pump()
                    if runtime.work is None: break
            self.assertIs(runtime.world,base); self.assertIs(request._world,base)
            self.assertEqual(request._completed,2); s.pause()
            observations.append((runtime.last_result,protected_bytes(base),runtime.credit_ns))
        self.assertEqual(observations[0],observations[1])

    def test_lifecycle_management_queries_save_load_and_capability_revocation(self):
        s=self.make(); control=self.make(False); old=s._owned_event
        self.assertEqual(s.advance_next_event(),control.advance_next_event())
        self.assertEqual(s.header(),control.header()); self.assertEqual(s.fleet(),control.fleet())
        career=s.save_manual(); s.load_saved(career)
        self.assertFalse(old._alive); self.assertIsNot(s._owned_event,old)
        self.equal(s,control)
        before=s.authoritative_bytes(); token=s._owned_event
        with self.assertRaises(Exception): s.load_saved('missing-career')
        self.assertIs(s._owned_event,token); self.assertEqual(before,s.authoritative_bytes())
        s.close(); self.assertFalse(token._alive)
        s.new_quarterly_development_game('CEO','New Pilot','MNL')
        self.assertTrue(s.scoped_completion_status()['enabled'])

    def test_unsupported_ordinary_registry_and_disabled_latch_remain_strict(self):
        from tests.test_simulation_resolver import ph_world, published_pair
        source=published_pair(ph_world())
        s=self.make(True,source); control=self.make(False,source)
        self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)
        self.assertEqual(s.scoped_completion_status()['counts']['attempts'],0)
        s=self.make(); control=self.make(False)
        s._owned_event.execution_state.disable('test latch')
        with patch.object(kernel,'_clone_runtime_world',wraps=kernel._clone_runtime_world) as clones:
            actual=s.advance_next_event()
        self.assertEqual(clones.call_count,2); self.assertEqual(actual,control.advance_next_event()); self.equal(s,control)

    def test_custom_registry_retained_reference_stays_detached_on_strict_path(self):
        s=self.make(); retained=[]; registry=kernel.EventHandlerRegistry()
        def custom(context):
            fulfilment._completion_handler(context); retained.append(context.envelope)
        registry.register('STAGE1_FLIGHT_COMPLETION',custom)
        result=kernel.process_next_event(s._world,registry=registry,**s._event_options())
        self.assertTrue(result.succeeded,result.failure)
        before=protected_bytes(s._world)
        retained[0]['world_state']['flight_results'][self.fid]['carried_passenger_count']=999
        self.assertEqual(before,protected_bytes(s._world))
        self.assertEqual(s.scoped_completion_status()['counts']['attempts'],0)

    def test_handler_failure_after_successful_prefix_then_explicit_retry(self):
        source=deepcopy(self.source)
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=source['simulation']['time_utc'],
            owner_type='airline',owner_id=source['world_state']['player']['primary_airline_id'])
        s=self.make(True,source); control=self.make(False,source)
        allocate=fulfilment.allocate_id
        def fail(*args): allocate(*args); raise RuntimeError('after allocation with prefix')
        with patch.object(fulfilment,'allocate_id',fail):
            actual=s.advance_to(self.event['due_at_utc']); expected=control.advance_to(self.event['due_at_utc'])
        self.assertEqual(actual,expected); self.assertEqual(len(actual.result.completed_event_ids),1)
        self.equal(s,control)
        self.assertEqual(s.advance_to(self.event['due_at_utc']),control.advance_to(self.event['due_at_utc']))
        self.equal(s,control)

    def test_stale_noop_and_booking_dispatch_completion_sequence(self):
        source=deepcopy(self.source)
        aircraft=source['world_state']['active_aircraft_operations'][self.fid]['actual_aircraft_id']
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=source['simulation']['time_utc'],
            owner_type='aircraft',owner_id=aircraft,operation_revision=0)
        kernel.set_operation_revision(source,aircraft,1)
        s=self.make(True,source); control=self.make(False,source)
        actual=s.advance_to('2027-01-03T08:00:00Z'); expected=control.advance_to('2027-01-03T08:00:00Z')
        self.assertEqual(actual,expected); self.equal(s,control)
        self.assertTrue(actual.result.skipped_event_ids)
        types={row['event_type'] for row in actual.event_rows}
        self.assertTrue({'DAILY_BOOKING_CHECKPOINT','QUARTERLY_DISPATCH','STAGE1_FLIGHT_DEPARTURE','STAGE1_FLIGHT_COMPLETION'}.issubset(types))
        self.assertGreater(s.scoped_completion_status()['counts']['committed'],0)

    def test_quarterly_publication_stays_strict_with_pilot_enabled(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        source=QuarterlyBackendTests.fixture('2027-02-28T23:59:59Z','2027-Q2',published=False)[0]
        s=self.make(True,source); control=self.make(False,source)
        actual=s.advance_to('2027-03-01T00:00:00Z'); expected=control.advance_to('2027-03-01T00:00:00Z')
        self.assertEqual(actual,expected); self.equal(s,control)
        self.assertIn('QUARTERLY_PUBLICATION',{r['event_type'] for r in actual.event_rows})
        self.assertEqual(s.scoped_completion_status()['counts']['attempts'],0)

    def test_legacy_planner_management_and_detached_gui_queries(self):
        from tests.test_simulation_resolver import ph_world
        source=ph_world(); s=self.make(True,source); control=self.make(False,source)
        results=[]
        for session in (s,control):
            aircraft=next(iter(source['world_state']['aircraft']))
            ports={row['reference_code']:row['airport_id'] for row in session.airports()}
            draft=session.begin_scheduling(aircraft)
            draft.add_weekdays(ports['MNL'],ports['DVO'],('2026-08-31',),'08:00',return_flight=True,fare_minor=11600)
            results.append(session.save_scheduling(draft))
        self.assertEqual(results[0],results[1]); self.equal(s,control)
        self.assertEqual(s.fleet(),control.fleet()); self.assertEqual(s.flights(),control.flights())
        self.assertEqual(s.scoped_completion_status()['counts']['attempts'],0)

    def test_real_successor_validation_failure_and_broken_detachment_recover(self):
        for kind in ('invalid_result','borrowed_output'):
            with self.subTest(kind=kind):
                s=self.make(); control=self.make(False); control.advance_next_event()
                if kind=='invalid_result':
                    def corrupt(stage,capsule):
                        if stage=='after_handler':
                            capsule.envelope['world_state']['flight_results'][self.fid]['carried_passenger_count']+=1
                    context=patch.object(scoped_completion,'_fault',corrupt)
                else:
                    context=patch.object(owned_event,'deepcopy',side_effect=lambda value:value)
                with context: actual=s.advance_next_event()
                self.assertEqual(actual.result.failure.code,'OPTIMIZER_DIVERGENCE'); self.equal(s,control)

    def test_unmodified_borrowed_legacy_session_is_exact_control(self):
        legacy=Stage1Session(save_root=self.temp.name,runtime_clock=lambda:0)
        legacy.world=deepcopy(self.source); legacy.career_id=legacy.save_store.new_career_id()
        legacy._reset_autosave_clocks(); s=self.make()
        self.assertEqual(s.advance_next_event(),legacy.advance_next_event()); self.equal(s,legacy)


if __name__=='__main__': unittest.main()
