"""Dormant publication barriers, durable fences and strict/reference recovery."""
from copy import deepcopy
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import resolve_until, begin_resolution
from game.scheduling import quarterly_commands as commands
from game.scheduling.quarterly_publication import PublishQuarterlyPlan
from game.scheduling.quarterly_edits import RemoveQuarterlySlots, ContinueQuarterlySlot
from game.scheduling.quarterly_boundary import enable_quarterly_boundaries_for_testing
from game.world_state.quarterly_boundary import EVENT_TYPE, CONTRACT, boundary, obligations
from game.world_state import validate_world
from game.world_state.timestamps import parse_canonical_utc, format_utc
from game.world_state.quarterly_construction import create_weekly_plan
from tests import test_quarterly_foundation as foundation
from tests import test_quarterly_readiness as readiness


class QuarterlyBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.FoundationTests.setUpClass.__func__(cls)
        initialize_runtime_handlers()

    at = readiness.PublicationReadinessTests.at
    closed_pattern = readiness.PublicationReadinessTests.closed_pattern

    def setUp(self):
        self.owner = self.base['world_state']['player']['primary_airline_id']
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.world, self.pid, self.f = self.at('2027-02-28T23:59:59Z', '2027-Q2')
        self.closed_pattern(self.world, self.pid)
        self.due = '2027-03-01T00:00:00Z'

    def enroll(self, world=None):
        world = self.world if world is None else world
        enable_quarterly_boundaries_for_testing(world, airline_id=self.owner)
        self.assertTrue(validate_world(world).is_valid)
        return world

    def published(self, world=None, pid=None):
        world = self.world if world is None else world
        p = world['world_state']['weekly_plans'][self.pid if pid is None else pid]
        return p['revisions'][str(p['current_revision'])]['published_at_utc']

    def event(self, world=None, quarter='2027-Q2'):
        world = self.world if world is None else world
        return min((e for e in world['world_state']['pending_events'].values()
                    if e['event_type'] == EVENT_TYPE and e['payload']['quarter_id'] == quarter),
                   key=lambda e:e['order_key'][1])

    def run_to(self, target=None, world=None, **kwargs):
        world = self.world if world is None else world
        return resolve_until(world, self.due if target is None else target, **kwargs)

    def fence(self, world=None, **kwargs):
        world = self.world if world is None else world
        # Literal missing return creates a hypothetical weekly positioning gap.
        world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].pop()
        self.enroll(world)
        result = self.run_to(world=world, **kwargs)
        self.assertEqual(result.failure.code, 'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(world['simulation']['time_utc'], self.due)
        self.assertEqual(world['simulation']['clock_state'], 'PAUSED')
        self.assertIsNone(self.published(world))
        return result

    def session(self, world=None):
        s = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        s.world = deepcopy(self.world if world is None else world)
        s.career_id = s.save_store.new_career_id()
        s.save_manual(); s.load_saved(s.career_id)
        self.addCleanup(s.close)
        return s

    def remove(self, session):
        p = session.world['world_state']['weekly_plans'][self.pid]
        rows = p['revisions'][str(p['current_revision'])]['slots']
        request = RemoveQuarterlySlots(self.pid, p['current_revision'],
            tuple((s['service_id'], s['slot_number']) for s in rows))
        prep = session.prepare_quarterly_command(request)
        self.assertTrue(prep.succeeded, prep.issues)
        result = session.apply_quarterly_command(prep.prepared)
        self.assertTrue(result.succeeded, result.issues)
        return result

    def test_four_exact_calendar_boundaries_and_rollover(self):
        pairs = [('2027-Q2','2027-03-01T00:00:00Z'), ('2027-Q3','2027-06-01T00:00:00Z'),
                 ('2027-Q4','2027-09-01T00:00:00Z'), ('2028-Q1','2027-12-01T00:00:00Z')]
        for quarter, due in pairs:
            with self.subTest(quarter=quarter):
                self.assertEqual(boundary(quarter), due)
                before = format_utc(parse_canonical_utc(due)-timedelta(seconds=1))
                # Some pre-existing used-market bootstrap seeds reject late-month
                # start dates. Other boundaries use valid exact-boundary scenarios;
                # the March case also verifies the preceding exact second.
                start = before if quarter == '2027-Q2' else due
                world, pid, _ = self.at(start, quarter)
                self.closed_pattern(world, pid)
                self.enroll(world)
                if start == before:
                    self.assertTrue(self.run_to(before, world).succeeded)
                    self.assertIsNone(self.published(world,pid))
                result = self.run_to(due, world)
                self.assertTrue(result.succeeded, result.failure)
                self.assertEqual(self.published(world,pid),due)

    def test_leap_day_is_not_a_publication_boundary(self):
        world, pid, _ = self.at('2028-02-29T23:59:58Z','2028-Q2')
        self.closed_pattern(world,pid); self.enroll(world)
        result = self.run_to('2028-02-29T23:59:59Z',world)
        self.assertTrue(result.succeeded,result.failure)
        self.assertIsNone(self.published(world,pid))
        result = self.run_to('2028-03-01T00:00:00Z',world)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(self.published(world,pid),'2028-03-01T00:00:00Z')

    def test_booking_enqueued_before_publication_observes_commit(self):
        self.enroll()
        booking = next(e for e in self.world['world_state']['pending_events'].values()
                       if e['event_type']=='DAILY_BOOKING_CHECKPOINT')
        self.assertLess(booking['order_key'][1],self.event()['order_key'][1])
        # Move genuine Booking to the boundary only when the scenario produces
        # that exact checkpoint time; this fixture starts one second before UTC midnight.
        self.assertEqual(booking['due_at_utc'],self.due)
        registry = kernel.EventHandlerRegistry(); observed=[]
        for kind, handler in kernel.DEFAULT_EVENT_HANDLERS._handlers.items():
            if kind == 'DAILY_BOOKING_CHECKPOINT':
                def book(context, original=handler):
                    observed.append(self.published(context.envelope))
                    original(context)
                registry.register(kind,book)
            else:
                registry.register(kind,handler)
        result=self.run_to(registry=registry)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(observed,[self.due])
        self.assertLess(result.completed_event_ids.index(self.event_id_from_history()),
                        result.completed_event_ids.index(booking['event_id']))

    def event_id_from_history(self):
        return next(k for k,e in self.world['world_state']['event_history'].items()
                    if e['event_type']==EVENT_TYPE)

    def test_unrelated_equal_time_priority_and_sequence_are_preserved(self):
        ids=[kernel.schedule_event(self.world,event_type='NO_OP',due_at_utc=self.due,
             owner_type='airline',owner_id=self.owner,priority=p) for p in (4,0,2,0)]
        self.enroll(); pub=self.event()['event_id']
        result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual([k for k in result.completed_event_ids if k in ids], [ids[1],ids[3],ids[2],ids[0]])
        self.assertLess(result.completed_event_ids.index(pub),result.completed_event_ids.index(ids[1]))

    def test_manual_publication_is_immutable_automatic_skip(self):
        request=PublishQuarterlyPlan('MANUAL','2027-Q2',self.pid,1)
        prep=commands.prepare_quarterly_command(self.world,airline_id=self.owner,request=request)
        self.assertTrue(prep.succeeded,prep.issues)
        result=commands.apply_quarterly_command(self.world,airline_id=self.owner,prepared=prep.prepared)
        self.assertTrue(result.succeeded,result.issues)
        stamp=self.published(); plans=deepcopy(self.world['world_state']['weekly_plans'])
        self.enroll(); result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(self.published(),stamp)
        self.assertEqual(self.world['world_state']['weekly_plans'],plans)
        self.assertEqual(obligations(self.world)[self.owner]['next_quarter_id'],'2027-Q3')

    def test_failure_preserves_all_pending_work_and_domain_authority(self):
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].pop()
        self.enroll(); before=deepcopy(self.world)
        result=self.run_to()
        self.assertEqual(result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(self.world['world_state'],before['world_state'])
        self.assertEqual(self.world['deterministic_state'],before['deterministic_state'])
        details=obligations(self.world)[self.owner]['failure']['details']
        self.assertEqual(details[0]['code'],'UNRESOLVED_POSITIONING')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_repeated_failed_retry_is_byte_deterministic_and_cannot_advance(self):
        self.fence(); before=foundation.encoded(self.world)
        for shared in (False,True,False):
            result=self.run_to('2027-03-02T00:00:00Z',shared=shared)
            self.assertEqual(result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
            self.assertEqual(foundation.encoded(self.world),before)

    def test_correction_and_fresh_retry_matches_independent_reference(self):
        self.fence(); session=self.session(); control=deepcopy(session.world)
        result=self.remove(session)
        p=control['world_state']['weekly_plans'][self.pid]
        rows=p['revisions']['1']['slots']
        request=RemoveQuarterlySlots(self.pid,1,tuple((s['service_id'],s['slot_number']) for s in rows))
        prep=commands.prepare_quarterly_command(control,airline_id=self.owner,request=request)
        self.assertTrue(prep.succeeded,prep.issues)
        ref=commands.apply_quarterly_command(control,airline_id=self.owner,prepared=prep.prepared)
        self.assertTrue(ref.succeeded,ref.issues)
        self.assertEqual(result.revision,2)
        outcome=session.advance_to(self.due).result
        refout=self.run_to(world=control,shared=False)
        self.assertTrue(outcome.succeeded,outcome.failure)
        self.assertEqual(outcome,refout)
        self.assertEqual(session.world,control)
        self.assertIsNone(obligations(session.world)[self.owner]['failure'])
        self.assertEqual(self.published(session.world),self.due)

    def test_closed_target_requires_a_real_failed_obligation(self):
        self.enroll()
        # Complete time to boundary via an explicitly failing dispatch, then
        # remove only the diagnostic in a separate adversarial valid world.
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].pop()
        self.run_to(); obligations(self.world)[self.owner]['failure']=None
        s=self.session(); p=s.world['world_state']['weekly_plans'][self.pid]
        row=p['revisions']['1']['slots'][0]
        request=commands.ReviseQuarterlyFare(self.pid,1,row['service_id'],row['slot_number'],
                                            {'currency':'USD','amount_minor':12000})
        result=s.prepare_quarterly_command(request)
        self.assertEqual(result.issues[0].code,'CLOSED_TARGET')

    def test_published_plan_is_locked_even_with_a_fence(self):
        self.fence(); self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['published_at_utc']=self.due
        s=self.session(); row=s.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        result=s.prepare_quarterly_command(commands.ReviseQuarterlyFare(self.pid,1,row['service_id'],1,
                                            {'currency':'USD','amount_minor':12000}))
        self.assertEqual(result.issues[0].code,'PUBLISHED_PLAN')

    def test_fence_cannot_authorize_an_unrelated_quarter(self):
        self.fence()
        old=create_weekly_plan(self.world,self.owner,'2027-Q1',slots=[])
        row=self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        request=commands.ReviseQuarterlyFare(old,1,row['service_id'],1,
                                            {'currency':'USD','amount_minor':12000})
        result=commands.prepare_quarterly_command(self.world,airline_id=self.owner,request=request)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code,'CLOSED_TARGET')

    def test_missing_boundary_event_reconstructs_from_persisted_obligation(self):
        self.enroll(); lost=self.event()['event_id']
        kernel.cancel_event(self.world,lost)
        result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(self.published(),self.due)
        self.assertEqual(self.world['world_state']['event_history'][lost]['status'],'CANCELLED')

    def test_stale_event_cannot_discharge_obligation(self):
        self.enroll(); stale=self.event()['event_id']
        kernel.set_operation_revision(self.world,self.owner,1)
        result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertIn(stale,result.skipped_event_ids)
        self.assertEqual(self.published(),self.due)
        self.assertEqual(len([e for e in self.world['world_state']['event_history'].values()
                              if e['event_type']==EVENT_TYPE and e['status']=='COMPLETED']),1)

    def test_duplicate_events_are_budgeted_lifecycle_only(self):
        self.enroll()
        duplicate=kernel.schedule_event(self.world,event_type=EVENT_TYPE,due_at_utc=self.due,
            owner_type='airline',owner_id=self.owner,payload={'contract':CONTRACT,'quarter_id':'2027-Q2'})
        result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertIn(duplicate,result.completed_event_ids)
        self.assertEqual(obligations(self.world)[self.owner]['next_quarter_id'],'2027-Q3')
        self.assertEqual(len([e for e in self.world['world_state']['pending_events'].values()
                              if e['event_type']==EVENT_TYPE]),1)

    def test_save_load_while_fenced_preserves_bytes_and_pending_work(self):
        self.fence(); s=self.session(); before=foundation.encoded(s.world)
        status=s.quarterly_boundary_status()
        status['failure']['message']='caller mutation'
        self.assertNotEqual(status,s.quarterly_boundary_status())
        s.save_manual(); s.load_saved(s.career_id)
        self.assertEqual(foundation.encoded(s.world),before)
        self.assertEqual(s.world['simulation']['clock_state'],'PAUSED')
        self.remove(s); outcome=s.advance_to(self.due).result
        self.assertTrue(outcome.succeeded,outcome.failure)

    def test_save_load_before_boundary_matches_uninterrupted_world(self):
        self.enroll(); s=self.session(); control=deepcopy(s.world)
        result=s.advance_to(self.due).result; reference=self.run_to(world=control)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(s.world,control)
        self.assertEqual(result,reference)

    def test_rebind_revokes_correction_preparation_and_preserves_fence(self):
        self.fence(); s=self.session(); row=s.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        prep=s.prepare_quarterly_command(commands.ReviseQuarterlyFare(self.pid,1,row['service_id'],1,
                                            {'currency':'USD','amount_minor':12000}))
        self.assertTrue(prep.succeeded,prep.issues)
        s.world=deepcopy(s.world)
        result=s.apply_quarterly_command(prep.prepared)
        self.assertEqual(result.issues[0].code,'STALE_CONTEXT')
        self.assertIsNotNone(s.quarterly_boundary_status()['failure'])

    def test_strict_shared_and_cooperative_caps_have_exact_world_equivalence(self):
        self.enroll(); control=deepcopy(self.world)
        ref=self.run_to(world=control)
        for cap in (1,2,8):
            world=deepcopy(self.world)
            result=self.run_to(world=world,shared=True,shadow=True,max_batch_events=cap)
            self.assertEqual(result,ref)
            self.assertEqual(world,control)

    def test_failure_survives_yield_and_future_advance(self):
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].pop()
        kernel.schedule_event(self.world,event_type='NO_OP',due_at_utc='2027-02-28T23:59:59Z',
            owner_type='airline',owner_id=self.owner)
        self.enroll(); req=begin_resolution(self.world,'2027-03-02T00:00:00Z',shared=True,max_batch_events=1)
        self.addCleanup(req.close)
        first=req.step(); self.assertFalse(first.finished)
        second=req.step(); self.assertTrue(second.finished)
        self.assertEqual(second.processing_result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(self.world['simulation']['time_utc'],self.due)

    def test_processed_event_budget_includes_publication_and_duplicates(self):
        self.enroll(); pub=self.event()['event_id']
        result=self.run_to(max_events=1)
        self.assertEqual(result.failure.code,'EVENT_LIMIT_REACHED')
        self.assertEqual(result.completed_event_ids,(pub,))
        self.assertEqual(self.published(),self.due)
        self.assertTrue(any(e['due_at_utc']==self.due for e in self.world['world_state']['pending_events'].values()))

    def test_custom_publication_handler_cannot_bypass_obligation(self):
        self.enroll(); registry=kernel.EventHandlerRegistry(); registry.register(EVENT_TYPE,kernel._no_op)
        result=self.run_to(registry=registry)
        self.assertEqual(result.failure.code,'HANDLER_CONTRACT_VIOLATION')
        self.assertIsNone(self.published())
        self.assertIsNotNone(obligations(self.world)[self.owner]['failure'])

    def test_missing_handler_fails_safely_at_boundary(self):
        self.enroll(); result=self.run_to(registry=kernel.EventHandlerRegistry())
        self.assertEqual(result.failure.code,'UNKNOWN_EVENT_TYPE')
        self.assertEqual(self.world['simulation']['time_utc'],self.due)
        self.assertIsNotNone(obligations(self.world)[self.owner]['failure'])

    def test_initial_airline_without_a_plan_cannot_be_enrolled(self):
        world=deepcopy(self.world)
        world['world_state']['weekly_plans'].clear()
        before=foundation.encoded(world)
        with self.assertRaisesRegex(ValueError,'upcoming plan or published baseline'):
            self.enroll(world)
        self.assertEqual(foundation.encoded(world),before)

    def test_schema_rejects_past_frontier_and_invalid_failure(self):
        self.enroll()
        bad=deepcopy(self.world); obligations(bad)[self.owner]['next_quarter_id']='2027-Q1'
        self.assertFalse(validate_world(bad).is_valid)
        bad=deepcopy(self.world); obligations(bad)[self.owner]['failure']={'code':'X','message':'X','details':[]}
        self.assertFalse(validate_world(bad).is_valid)

    def test_normal_world_has_no_boundary_policy_and_no_publication(self):
        control=deepcopy(self.world)
        result=self.run_to(); ref=self.run_to(world=control,shared=True)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(result,ref); self.assertEqual(self.world,control)
        self.assertNotIn('quarterly_publication',self.world['simulation'])
        self.assertIsNone(self.published())

    def test_publication_candidate_failure_commits_only_fence(self):
        self.enroll(); before=deepcopy(self.world)
        with patch.object(commands,'commit_weekly_plan_publication',side_effect=ValueError('injected construction failure')):
            result=self.run_to()
        self.assertEqual(result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(self.world['world_state'],before['world_state'])
        self.assertEqual(self.world['deterministic_state'],before['deterministic_state'])
        result=self.run_to(); self.assertTrue(result.succeeded,result.failure)

    def test_loaded_missing_fenced_event_is_reconciled_without_booking_leakage(self):
        self.fence(); kernel.cancel_event(self.world,self.event()['event_id'])
        s=self.session(); result=s.advance_to('2027-03-02T00:00:00Z').result
        self.assertEqual(result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(s.world['simulation']['time_utc'],self.due)
        self.assertFalse(any(e['event_type']=='DAILY_BOOKING_CHECKPOINT'
                             for e in s.world['world_state']['event_history'].values()))

    def test_multi_boundary_advance_carries_forward_without_operational_supply(self):
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].clear()
        self.enroll()
        result=self.run_to('2027-06-01T00:00:00Z',shared=True)
        self.assertTrue(result.succeeded,result.failure)
        plans=self.world['world_state']['weekly_plans']
        committed={p['quarter_id']:p['revisions']['1']['published_at_utc'] for p in plans.values()}
        self.assertEqual(committed,{'2027-Q2':self.due,'2027-Q3':'2027-06-01T00:00:00Z'})
        self.assertEqual(obligations(self.world)[self.owner]['next_quarter_id'],'2027-Q4')
        self.assertEqual(self.world['world_state']['dated_flights'],{})
        self.assertEqual(self.world['world_state']['bookings'],{})
        self.assertEqual(len([e for e in self.world['world_state']['pending_events'].values()
                              if e['event_type']==EVENT_TYPE]),1)

    def test_same_time_budget_survives_publication_and_yields(self):
        self.enroll(); registry=kernel.EventHandlerRegistry()
        for kind,handler in kernel.DEFAULT_EVENT_HANDLERS._handlers.items():
            registry.register(kind,handler)
        def loop(context):
            context.schedule_event(event_type='LOOP',due_at_utc=context.event['due_at_utc'],
                owner_type='airline',owner_id=self.owner)
        registry.register('LOOP',loop)
        kernel.schedule_event(self.world,event_type='LOOP',due_at_utc=self.due,
            owner_type='airline',owner_id=self.owner)
        req=begin_resolution(self.world,self.due,registry=registry,shared=True,max_batch_events=1)
        self.addCleanup(req.close)
        while not req.finished:
            req.step()
        self.assertEqual(req.result.failure.code,'EVENT_GENERATION_LIMIT_REACHED')
        loops=[e for e in self.world['world_state']['event_history'].values() if e['event_type']=='LOOP']
        self.assertEqual(len(loops),100)
        self.assertEqual(self.published(),self.due)
        self.assertEqual(len([e for e in self.world['world_state']['pending_events'].values()
                              if e['event_type']=='LOOP']),1)
        self.assertEqual(self.event(quarter='2027-Q3')['due_at_utc'],'2027-06-01T00:00:00Z')

    def test_unrelated_handler_cannot_advance_or_erase_obligation(self):
        self.enroll(); registry=kernel.EventHandlerRegistry()
        def erase(context):
            context.envelope['simulation']['quarterly_publication'].clear()
        registry.register('ERASE',erase)
        kernel.schedule_event(self.world,event_type='ERASE',due_at_utc=self.world['simulation']['time_utc'],
            owner_type='airline',owner_id=self.owner)
        before=deepcopy(self.world)
        result=self.run_to(registry=registry)
        self.assertEqual(result.failure.code,'HANDLER_CONTRACT_VIOLATION')
        self.assertEqual(self.world,before)

    def test_boundary_publication_retains_four_command_gates_and_two_world_copies(self):
        self.enroll(); gates=[]; copies=[]
        original_entry=commands._entry; original_copy=commands.deepcopy
        def gate(world):
            gates.append(world['simulation']['time_utc']); return original_entry(world)
        def copy(value):
            if type(value) is dict and 'metadata' in value: copies.append(value)
            return original_copy(value)
        with patch.object(commands,'_entry',side_effect=gate),patch.object(commands,'deepcopy',side_effect=copy):
            result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(gates,[self.due]*4)
        self.assertEqual(len(copies),2)

    def test_month_three_initial_target_enrollment_never_invents_incoming_plan(self):
        world,pid,_=self.at(self.due,'2027-Q3')
        self.closed_pattern(world,pid); self.enroll(world)
        self.assertEqual(obligations(world)[self.owner]['next_quarter_id'],'2027-Q3')
        self.assertEqual(self.event(world,'2027-Q3')['due_at_utc'],'2027-06-01T00:00:00Z')
        result=self.run_to(self.due,world)
        self.assertTrue(result.succeeded,result.failure)
        self.assertIsNone(self.published(world,pid))

    def test_failed_missing_carry_target_can_initialize_via_certified_continuation(self):
        world,pid,_=self.at(self.due,'2027-Q1')
        rows=world['world_state']['weekly_plans'][pid]['revisions']['1']['slots']
        rows[0]['departure_local_time']='10:00:00'
        self.closed_pattern(world,pid,departure_local_time='16:00:00')
        world['world_state']['weekly_plans'][pid]['revisions']['1']['published_at_utc']='2027-01-01T00:00:00Z'
        self.enroll(world)
        with patch.object(commands,'commit_weekly_plan_publication',side_effect=ValueError('transient failure')):
            failed=self.run_to(world=world)
        self.assertEqual(failed.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(len(world['world_state']['weekly_plans']),1)
        s=self.session(world); row=rows[0]
        request=ContinueQuarterlySlot(None,0,pid,1,1,row['service_id'],row['slot_number'],{},'2027-Q2')
        prepared=s.prepare_quarterly_command(request)
        self.assertTrue(prepared.succeeded,prepared.issues)
        corrected=s.apply_quarterly_command(prepared.prepared)
        self.assertTrue(corrected.succeeded,corrected.issues)
        self.assertIsNotNone(s.quarterly_boundary_status()['failure'])
        result=s.advance_to(self.due).result
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(s.world['world_state']['weekly_plans'][pid],world['world_state']['weekly_plans'][pid])

    def test_reconciliation_and_failure_at_current_utc_mark_session_dirty(self):
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].pop()
        self.enroll(); self.world['simulation']['time_utc']=self.due
        s=self.session(); self.assertFalse(s.unsaved_progress)
        result=s.advance_to(self.due).result
        self.assertEqual(result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertTrue(s.unsaved_progress)

    def test_false_success_cannot_discharge_a_mandatory_obligation(self):
        self.enroll(); before=deepcopy(self.world)
        fake=commands.QuarterlyCommandResult(succeeded=True,weekly_plan_id=self.pid,revision=1)
        with patch.object(commands,'apply_quarterly_command',return_value=fake):
            result=self.run_to()
        self.assertEqual(result.failure.code,'QUARTERLY_PUBLICATION_FAILED')
        self.assertEqual(result.failure.validation_errors[0]['code'],'INVALID_PUBLICATION_RESULT')
        self.assertEqual(self.world['world_state'],before['world_state'])
        self.assertEqual(obligations(self.world)[self.owner]['next_quarter_id'],'2027-Q2')

    def test_existing_commit_releases_recovered_fence_without_recommit(self):
        self.fence()
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['published_at_utc']=self.due
        plans=deepcopy(self.world['world_state']['weekly_plans'])
        result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(self.world['world_state']['weekly_plans'],plans)
        self.assertIsNone(obligations(self.world)[self.owner]['failure'])

    def test_new_boundary_event_is_strictly_future_and_never_charged_as_same_time(self):
        self.enroll(); result=self.run_to(max_generated_events=1)
        self.assertTrue(result.succeeded,result.failure)
        self.assertEqual(self.event(quarter='2027-Q3')['due_at_utc'],'2027-06-01T00:00:00Z')
        self.assertTrue(all(e['due_at_utc']>self.due for e in self.world['world_state']['pending_events'].values()))

    def test_publication_history_cannot_lose_its_required_enrollment(self):
        self.enroll(); result=self.run_to()
        self.assertTrue(result.succeeded,result.failure)
        kernel.cancel_event(self.world,self.event(quarter='2027-Q3')['event_id'])
        del self.world['simulation']['quarterly_publication']
        self.assertFalse(validate_world(self.world).is_valid)

    def test_missing_owner_entry_is_not_reconstructed_from_historical_guesswork(self):
        self.enroll(); kernel.cancel_event(self.world,self.event()['event_id'])
        obligations(self.world).clear()
        result=validate_world(self.world)
        self.assertFalse(result.is_valid)


if __name__ == '__main__':
    unittest.main()
