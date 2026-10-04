"""Stage 3E production pacing, debt, boundary and exact-world regressions."""
from copy import deepcopy
from datetime import timedelta
import json
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel, shared_candidate
from game.simulation.pacing import RuntimeController, NANOSECOND
from game.world_state import validate_world
from game.world_state.persistence import SaveError
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.test_stage1_event_kernel import make_world, schedule
from tests.test_stage1_runtime import Clock
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import world_digest


def settle(runtime, limit=2000):
    for _ in range(limit):
        runtime.pump()
        if not runtime.processing or (runtime.work is None and runtime.credit_ns < NANOSECOND): return
    raise AssertionError('runtime did not settle')

class CooperativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.world=make_world(); self.clock=Clock()
        self.runtime=RuntimeController(self.world,clock=self.clock,max_batch_events=2)
    def earn(self,seconds=1):
        self.runtime.resume(); self.clock.advance(seconds*NANOSECOND)
    def events(self,count=5,event_type='NO_OP'):
        due=self.world['simulation']['time_utc']
        return [schedule(self.world,due,event_type=event_type) for _ in range(count)]
    def test_all_speeds_exact_credit_and_authority(self):
        for name,ratio in [('Normal Speed',30),('Fast',210),('Very Fast',900),('Ultra',1800)]:
            world=make_world(); clock=Clock(); r=RuntimeController(world,clock=clock)
            start=parse_canonical_utc(world['simulation']['time_utc']); r.resume(name); clock.advance(NANOSECOND); settle(r)
            self.assertEqual(world['simulation']['time_utc'],format_utc(start+timedelta(seconds=ratio)))
            self.assertEqual(r.credit_ns,0); self.assertEqual(r.state,'RUNNING')
    def test_one_safe_unit_per_callback_and_no_private_candidate(self):
        self.events(); self.earn()
        self.runtime.pump(); request=self.runtime.work
        self.assertEqual(self.runtime.last_pump['events'],2)
        self.assertEqual(len(self.world['world_state']['pending_events']),3)
        self.assertNotIn('candidate',vars(request)); self.assertNotIn('ownership',vars(request))
        self.assertTrue(validate_world(self.world).is_valid)
    def test_player_pause_freezes_accrual_and_drains_exact_target(self):
        self.events(); self.earn(); self.runtime.pump(); work=self.runtime.work
        target=self.runtime.earned_target_utc; self.runtime.pause()
        self.assertEqual(self.runtime.state,'PLAYER_DRAIN'); self.assertIs(self.runtime.work,work)
        credit=self.runtime.credit_ns; self.clock.advance(50*NANOSECOND); self.runtime.pump()
        self.assertEqual(self.runtime.credit_ns,credit); settle(self.runtime)
        self.assertEqual(self.world['simulation']['time_utc'],target)
        self.assertEqual(self.runtime.state,'PAUSED'); self.assertEqual(self.runtime.credit_ns,0)
    def test_temporary_backlog_recovers_without_overload(self):
        self.events(); self.runtime.overload_seconds=.01; self.runtime.grace_ns=30*NANOSECOND
        self.earn(); settle(self.runtime)
        self.assertEqual(self.runtime.state,'RUNNING'); self.assertIsNone(self.runtime.diagnostic)
    def test_persistent_overload_freezes_target_drains_then_requires_resume(self):
        self.events(15); self.runtime.overload_seconds=1; self.runtime.grace_ns=NANOSECOND
        self.earn(2); self.runtime.pump(); self.clock.advance(2*NANOSECOND); self.runtime.pump()
        self.assertEqual(self.runtime.state,'OVERLOAD_DRAIN')
        target=self.runtime.earned_target_utc; debt=self.runtime.credit_ns
        self.clock.advance(100*NANOSECOND); self.runtime.pump()
        self.assertEqual(self.runtime.credit_ns,debt); settle(self.runtime)
        self.assertEqual(self.world['simulation']['time_utc'],target)
        self.assertEqual(self.runtime.state,'RECOVERED'); self.assertFalse(self.runtime.processing)
        before=deepcopy(self.world); self.clock.advance(100*NANOSECOND); self.runtime.pump(); self.assertEqual(before,self.world)
        self.runtime.resume(); self.assertEqual(self.runtime.state,'RUNNING')
    def test_recovered_burst_resets_overload_grace_before_next_elapsed_partition(self):
        self.runtime.resume(); self.clock.advance(130*NANOSECOND); settle(self.runtime)
        self.assertIsNone(self.runtime.overloaded_since)
        self.clock.advance(130*NANOSECOND); settle(self.runtime)
        self.assertEqual(self.runtime.state,'RUNNING'); self.assertEqual(self.runtime.credit_ns,0)
    def test_hard_pause_retains_debt_but_releases_request(self):
        self.events(); self.earn(); self.runtime.pump(); debt=self.runtime.credit_ns
        self.runtime.hard_pause(); self.assertIsNone(self.runtime.work)
        self.assertEqual(self.runtime.credit_ns,debt); self.assertFalse(self.runtime.processing)
        self.clock.advance(100*NANOSECOND); self.runtime.pump(); self.assertEqual(self.runtime.credit_ns,debt)
        self.runtime.resume(); settle(self.runtime); self.assertEqual(self.runtime.credit_ns,0)
    def test_resume_cannot_restart_accrual_during_drain(self):
        self.events(); self.earn(); self.runtime.pause()
        with self.assertRaises(ValueError): self.runtime.resume('Ultra')
        with self.assertRaises(ValueError): self.runtime.select_speed('Ultra')
        self.assertEqual(self.runtime.state,'PLAYER_DRAIN')
    def test_processing_cost_accrues_only_while_running(self):
        registry=kernel.EventHandlerRegistry(); registry.register('SLOW',lambda c:self.clock.advance(2*NANOSECOND))
        self.runtime.registry=registry; self.events(2,'SLOW'); self.earn(); self.runtime.pause()
        settle(self.runtime); self.assertEqual(self.runtime.credit_ns,0)
        self.assertEqual(self.clock.now,5*NANOSECOND)
    def test_fractional_credit_survives_pause_and_resume(self):
        self.runtime.resume(); self.clock.advance(1); self.runtime.pause()
        self.assertEqual(self.runtime.credit_ns,30); self.assertEqual(self.runtime.state,'PAUSED')
        self.clock.advance(100*NANOSECOND); self.runtime.resume(); self.assertEqual(self.runtime.credit_ns,30)
    def test_custom_handler_is_strict_and_equal_time_order_preserved(self):
        registry=kernel.EventHandlerRegistry(); seen=[]
        registry.register('CUSTOM',lambda c:seen.append(c.event['event_id']))
        self.runtime.registry=registry; ids=self.events(3,'CUSTOM'); self.earn()
        self.runtime.pump(); self.assertEqual(seen,ids[:1]); settle(self.runtime); self.assertEqual(seen,ids)
    def test_failing_event_not_retried_and_prefix_preserved(self):
        registry=kernel.EventHandlerRegistry(); registry.register('NO_OP',kernel._no_op); calls=[]
        def fail(c): calls.append(c.event['event_id']); raise ValueError('bad event')
        registry.register('FAIL',fail); self.runtime.registry=registry
        first=self.events(1)[0]; failed=self.events(1,'FAIL')[0]; self.earn(); settle(self.runtime)
        self.assertIn(first,self.world['world_state']['event_history']); self.assertIn(failed,self.world['world_state']['pending_events'])
        self.assertEqual(self.runtime.state,'ERROR'); self.assertEqual(len(calls),1)
        self.clock.advance(100*NANOSECOND); self.runtime.pump(); self.assertEqual(len(calls),1)
    def test_optimizer_divergence_disables_future_shared_without_auto_resume(self):
        self.events(4); self.earn()
        with patch.object(shared_candidate,'_validate_batch',side_effect=ValueError('fault')):
            self.runtime.pump()
        self.assertEqual(self.runtime.state,'ERROR'); self.assertFalse(self.runtime.execution_state.enabled)
        self.assertEqual(len(self.world['world_state']['event_history']),2)
        before=deepcopy(self.world); self.runtime.pump(); self.assertEqual(before,self.world)
        self.runtime.resume(); settle(self.runtime); self.assertFalse(self.runtime.execution_state.enabled)
        self.assertEqual(len(self.world['world_state']['event_history']),4)
    def test_close_replacement_prevents_stale_callbacks(self):
        self.events(); self.earn(); self.runtime.pump(); self.runtime.close()
        before=deepcopy(self.world); self.clock.advance(100*NANOSECOND); self.runtime.pump()
        self.assertEqual(before,self.world); self.assertIsNone(self.runtime.work)
    def test_no_runtime_fields_in_world(self):
        self.events(); self.earn(); self.runtime.pump(); encoded=json.dumps(self.world)
        for field in ('credit_ns','execution_state','OVERLOAD_DRAIN','read_lookup','max_batch_events'):
            self.assertNotIn(field,encoded)
    def test_management_refresh_preserves_request_and_limits(self):
        self.events(); self.earn(); self.runtime.pump(); request=self.runtime.work
        extra=schedule(self.world,self.world['simulation']['time_utc']); self.runtime.management_changed()
        settle(self.runtime); self.assertIn(extra,self.world['world_state']['event_history'])
        self.assertEqual(request._completed,6)
    def test_invalid_budget_is_rejected(self):
        for value in (0,-1,True,1.5):
            with self.assertRaises(ValueError): RuntimeController(make_world(),clock=self.clock,max_batch_events=value)

class ProductionFlightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=flight_world(2,stagger_seconds=60)
    def test_budgets_and_elapsed_partitions_match_complete_strict_world(self):
        target=window(deepcopy(self.base),'round-trip'); start=parse_canonical_utc(self.base['simulation']['time_utc'])
        seconds=int((parse_canonical_utc(target)-start).total_seconds())
        for budget in (1,2,8,64):
            for parts in (1,3):
                world=deepcopy(self.base); clock=Clock(); r=RuntimeController(world,clock=clock,max_batch_events=budget)
                r.resume(); total=(seconds*NANOSECOND+29)//30; allocated=0
                for i in range(parts):
                    end=total*(i+1)//parts; clock.advance(end-allocated); allocated=end; settle(r)
                r.pause()
                expected=deepcopy(self.base); kernel.configure_clock_ratios(expected,normal=30)
                result=kernel.process_events_through(expected,target); self.assertTrue(result.succeeded)
                self.assertEqual(world_digest(world),world_digest(expected))
    def test_booking_fence_separates_candidates(self):
        world=deepcopy(self.base); clock=Clock(); r=RuntimeController(world,clock=clock,max_batch_events=64)
        r.resume(); r.credit_ns=2*86400*NANOSECOND
        seen=[]; original=shared_candidate.SharedResolutionRequest._strict_one
        def strict(request):
            event=request._world['world_state']['pending_events'][request._heap[0][3]]
            seen.append(event['event_type']); return original(request)
        with patch.object(shared_candidate.SharedResolutionRequest,'_strict_one',strict): settle(r)
        self.assertIn('DAILY_BOOKING_CHECKPOINT',seen); self.assertTrue(validate_world(world).is_valid)
    def test_session_epoch_and_save_load_no_offline_debt(self):
        with tempfile.TemporaryDirectory() as root:
            clock=Clock(); s=Stage1Session(runtime_clock=clock,save_root=root); s.world=deepcopy(self.base)
            s.career_id=s.save_store.new_career_id(); s._reset_autosave_clocks(); s._bind_owned_reads()
            s.resume(); old=s._owned_reads(); clock.advance(NANOSECOND); s.pump(); self.assertIsNot(s._owned_reads(),old)
            s.pause();
            for _ in range(100):
                if not s.runtime.draining: break
                s.pump()
            s.save_manual(); encoded=s.authoritative_bytes(); career=s.career_id; oldruntime=s.runtime
            clock.advance(10000*NANOSECOND); s.load_saved(career)
            self.assertEqual(encoded,s.authoritative_bytes()); self.assertEqual(s.runtime.credit_ns,0)
            self.assertEqual(s.runtime.state,'PAUSED'); self.assertTrue(oldruntime.closed)
    def test_manual_save_bookmark_barrier_and_autosave_throttle(self):
        with tempfile.TemporaryDirectory() as root:
            s=Stage1Session(runtime_clock=lambda:0,save_root=root); s.world=deepcopy(self.base)
            s.career_id=s.save_store.new_career_id(); s._reset_autosave_clocks(); s._ensure_runtime()
            s.runtime.credit_ns=200*NANOSECOND; s.resume()
            with self.assertRaises(SaveError) as caught: s.save_manual()
            self.assertEqual(caught.exception.code,'RUNTIME_DRAINING')
            with self.assertRaises(SaveError): s.save_bookmark('pending')
            while s.runtime.draining: s.pump()
            s.save_manual(); s.save_bookmark('safe'); self.assertEqual(len(s.list_bookmarks()),1)
            s._last_auto_sim_time=format_utc(parse_canonical_utc(s.world['simulation']['time_utc'])-timedelta(days=7))
            with patch.object(s.save_store,'save',wraps=s.save_store.save) as save:
                self.assertTrue(s.maybe_autosave()); self.assertFalse(s.maybe_autosave()); self.assertEqual(save.call_count,1)
    def test_mixed_payment_flight_expiry_booking_rotation_production_equivalence(self):
        from tests.payment_fixtures import payment_world
        from tests.profile_scheduling import identities
        from game.scheduling import WeeklyDraft
        world,due=payment_world(2,final=True,lead_seconds=1800)
        owner,aircraft,ports=identities(world)
        draft=WeeklyDraft(world,airline_id=owner,aircraft_id=aircraft)
        draft.add(ports['MNL'],ports['DVO'],departure_utc=due,fare_minor=11600)
        self.assertTrue(draft.save(world).succeeded)
        target=max(f['scheduled_in_block_utc'] for f in world['world_state']['dated_flights'].values())
        expected=deepcopy(world); kernel.configure_clock_ratios(expected,normal=30)
        self.assertTrue(kernel.process_events_through(expected,target).succeeded)
        clock=Clock(); r=RuntimeController(world,clock=clock); r.resume()
        r.credit_ns=int((parse_canonical_utc(target)-parse_canonical_utc(world['simulation']['time_utc'])).total_seconds())*NANOSECOND
        settle(r); r.pause(); self.assertEqual(world_digest(world),world_digest(expected))
        kinds={e['event_type'] for e in world['world_state']['event_history'].values()}
        self.assertTrue({'AIRCRAFT_CONTRACT_PAYMENT','AIRCRAFT_CONTRACT_EXPIRY','AIRCRAFT_MARKET_ROTATION','DAILY_BOOKING_CHECKPOINT','STAGE1_FLIGHT_DEPARTURE','STAGE1_FLIGHT_COMPLETION'} <= kinds)
    def test_production_callbacks_release_manifest_lookup(self):
        from game.aircraft_operations.manifest_lookup import CandidateManifestLookup
        world=deepcopy(self.base); clock=Clock(); r=RuntimeController(world,clock=clock,max_batch_events=1)
        r.resume(); r.credit_ns=2*3600*NANOSECOND
        closed=[]; original=CandidateManifestLookup.close
        def close(lookup):
            original(lookup); closed.append(not lookup._groups and lookup._world is None)
        with patch.object(CandidateManifestLookup,'close',close):
            r.pump(); self.assertTrue(closed); self.assertTrue(all(closed))
            r.pump(); self.assertEqual(len(closed),2)
        self.assertTrue(validate_world(world).is_valid)
    def test_owned_projections_during_private_validation_see_only_commit(self):
        with tempfile.TemporaryDirectory() as root:
            s=Stage1Session(runtime_clock=lambda:0,save_root=root); s.world=deepcopy(self.base)
            s._ensure_runtime(); s._bind_owned_reads(); s.resume(); s.runtime.credit_ns=NANOSECOND
            source=deepcopy(s.world); old=s._read_views; original=shared_candidate._validate_batch
            def inspect(candidate):
                self.assertEqual(s.world,source)
                for read in (s.fleet,s.flights,s.finances): read()
                self.assertIs(s._read_views,old)
                return original(candidate)
            with patch.object(shared_candidate,'_validate_batch',inspect): s.pump()
            self.assertIsNot(s._read_views,old)
            self.assertTrue(s._read_views.matches(s.world,s.progression_revision))
    def test_explicit_advance_uses_shared_facade_and_remains_exact(self):
        with tempfile.TemporaryDirectory() as root:
            s=Stage1Session(runtime_clock=lambda:0,save_root=root); s.world=deepcopy(self.base)
            target=window(deepcopy(self.base),'round-trip'); s.begin_advance_to(target)
            self.assertIsInstance(s._bulk_work,shared_candidate.SharedResolutionRequest)
            while s.advancing: report=s.advance_tick()
            self.assertTrue(report.result.succeeded); self.assertEqual(s.world['simulation']['clock_state'],'PAUSED')
            expected=deepcopy(self.base); kernel.process_events_through(expected,target)
            self.assertEqual(s.world,expected)

if __name__=='__main__': unittest.main()
