"""Strict Completion after Phase 3G retirement: owned/borrowed exact outcomes."""
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel
from game.simulation.resolver import begin_resolution
from game.aircraft_operations import fulfilment
from game.world_state.flight_proof_witness import protected_bytes
from tests import test_scoped_completion_experiment as fixtures


class StrictCompletionSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ScopedCompletionTests.setUpClass()
        cls.source = fixtures.ScopedCompletionTests.source
        cls.event = fixtures.ScopedCompletionTests.event
        cls.fid = fixtures.ScopedCompletionTests.fid

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def make(self, closed=True, source=None):
        session = Stage1Session(closed_owner=closed, save_root=self.temp.name,
                                runtime_clock=lambda: 0)
        session.world = deepcopy(self.source if source is None else source)
        session.career_id = session._save_store.new_career_id()
        session._reset_autosave_clocks()
        self.addCleanup(session.close)
        return session

    def equal(self, actual, control):
        self.assertEqual(protected_bytes(actual._world), protected_bytes(control._world))
        self.assertEqual(actual.authoritative_bytes(), control.authoritative_bytes())

    def test_next_event_uses_strict_transaction_and_exact_result(self):
        session = self.make()
        control = self.make(False)
        with patch.object(kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones:
            actual = session.advance_next_event()
        self.assertEqual(clones.call_count, 2)
        self.assertEqual(actual, control.advance_next_event())
        self.equal(session, control)
        self.assertEqual(actual.result.completed_event_ids, (self.event['event_id'],))
        world = session._world['world_state']
        operation = self.source['world_state']['active_aircraft_operations'][self.fid]
        result = world['flight_results'][self.fid]
        aircraft = world['aircraft'][operation['actual_aircraft_id']]
        self.assertEqual(aircraft['status'], 'PARKED')
        self.assertEqual(aircraft['current_airport_id'],
                         world['dated_flights'][self.fid]['destination_airport_id'])
        self.assertNotIn(self.fid, world['active_aircraft_operations'])
        self.assertEqual(result['booking_witnesses'], operation['booking_witnesses'])
        self.assertEqual(result['source_booking_ids'], operation['source_booking_ids'])
        self.assertEqual(world['bookings'], self.source['world_state']['bookings'])
        self.assertEqual(session.ownership_counts()['acquisitions'], 1)

    def test_successive_requests_interleaved_strict_events(self):
        s = self.make(); control = self.make(False); binding = s.binding_revision
        self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)
        target = min(control._world['world_state']['pending_events'].values(),key=kernel._event_key)['due_at_utc']
        self.assertEqual(s.advance_to(target),control.advance_to(target)); self.equal(s,control)
        self.assertEqual(s.advance_next_event(),control.advance_next_event()); self.equal(s,control)
        self.assertEqual(s.binding_revision,binding); self.assertEqual(s.ownership_counts()['acquisitions'],1)


    def test_cooperative_budget_counts_completion_once(self):
        source = deepcopy(self.source)
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=source['simulation']['time_utc'],
                              owner_type='airline',owner_id=source['world_state']['player']['primary_airline_id'])
        observations=[]
        for closed in (False,True):
            s=self.make(closed,source); s._ensure_runtime()
            request=begin_resolution(s._world,self.event['due_at_utc'],shared=True,
                max_batch_events=1,max_events=2,max_generated_events=1,
                execution_state=s._runtime.execution_state)
            while not request.finished: request.step()
            observations.append((request.result,protected_bytes(s._world),request._completed,request._generated))
        self.assertEqual(observations[0],observations[1]); self.assertEqual(observations[1][2],2)


    def test_equal_utc_preserves_complete_command_outcome(self):
        source=deepcopy(self.source)
        aircraft=source['world_state']['active_aircraft_operations'][self.fid]['actual_aircraft_id']
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=self.event['due_at_utc'],
            owner_type='aircraft',owner_id=aircraft,operation_revision=0,priority=99,payload={})
        s=self.make(True,source); control=self.make(False,source)
        self.assertEqual(s.advance_to(self.event['due_at_utc']),control.advance_to(self.event['due_at_utc']))
        self.equal(s,control)


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


    def test_custom_registry_retained_reference_stays_detached_on_strict_path(self):
        s=self.make(); retained=[]; registry=kernel.EventHandlerRegistry()
        def custom(context):
            fulfilment._completion_handler(context); retained.append(context.envelope)
        registry.register('STAGE1_FLIGHT_COMPLETION',custom)
        result=kernel.process_next_event(s._world,registry=registry)
        self.assertTrue(result.succeeded,result.failure)
        before=protected_bytes(s._world)
        retained[0]['world_state']['flight_results'][self.fid]['carried_passenger_count']=999
        self.assertEqual(before,protected_bytes(s._world))


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


    def test_quarterly_publication_matches_borrowed_session(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        source=QuarterlyBackendTests.fixture('2027-02-28T23:59:59Z','2027-Q2',published=False)[0]
        s=self.make(True,source); control=self.make(False,source)
        actual=s.advance_to('2027-03-01T00:00:00Z'); expected=control.advance_to('2027-03-01T00:00:00Z')
        self.assertEqual(actual,expected); self.equal(s,control)
        self.assertIn('QUARTERLY_PUBLICATION',{r['event_type'] for r in actual.event_rows})


    def test_unmodified_borrowed_legacy_session_is_exact_control(self):
        legacy=Stage1Session(save_root=self.temp.name,runtime_clock=lambda:0)
        legacy.world=deepcopy(self.source); legacy.career_id=legacy.save_store.new_career_id()
        legacy._reset_autosave_clocks(); s=self.make()
        self.assertEqual(s.advance_next_event(),legacy.advance_next_event()); self.equal(s,legacy)


if __name__ == '__main__': unittest.main()
