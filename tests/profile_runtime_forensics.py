"""Stage 3G-A diagnostics only; actual session/resolver, TEMP artifacts.

No handler registration or certificate entry is wrapped. Exclusive timers subtract
nested timed children. Native observation is censored, not capacity certification.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from datetime import timedelta
import gc
import json
import math
from pathlib import Path
import pickle
import tempfile
import time
from unittest.mock import patch

from tests.certify_runtime_capacity import audit, percentile, process_memory
from tests.profile_atomic_boundaries import ExclusiveProfile
from tests.resolution_oracle import world_digest


def structure(value):
    """Diagnostic graph volume, not another authoritative validator."""
    seen=set(); containers=entries=0; stack=[value]
    while stack:
        item=stack.pop()
        if type(item) not in (dict,list) or id(item) in seen: continue
        seen.add(id(item));containers+=1;entries+=len(item)
        stack.extend(item.values() if type(item) is dict else item)
    return dict(containers=containers,entries=entries,
                pickle_bytes=len(pickle.dumps(value,protocol=5)))


def booking_temperature(world):
    s=world['world_state'];counts=Counter()
    for booking in s['bookings'].values():
        itinerary=s['itineraries'].get(booking.get('itinerary_id'),{})
        ids=itinerary.get('dated_flight_ids',[])
        status=s['dated_flights'].get(ids[0],{}).get('status','UNKNOWN') if ids else 'UNKNOWN'
        counts[status]+=1
    return dict(counts)


def changes(before,after):
    """Outside timed engine region; selected unit's exact changed record IDs."""
    result={}
    for name,old in before['world_state'].items():
        new=after['world_state'].get(name)
        if type(old) is dict and type(new) is dict:
            keys=sorted(k for k in old.keys()|new.keys() if old.get(k)!=new.get(k))
            if keys: result[name]=keys
    return result


def instrument(stack,profile,families):
    from app.session import Stage1Session
    from game.simulation import kernel,candidate_ownership
    from game.world_state import validation,flight_transition_validation as proof
    from game.aircraft_operations import fulfilment,manifest_lookup
    from game.booking import checkpoint,allocation,shopping,indexes
    from game.scheduling import publication
    hooks=[(validation._Validator,'run','complete_validation'),
        (validation._Validator,'validate_root','validation_root'),
        (validation,'_plain_authority_tree','validation_graph'),
        (validation._Validator,'validate_collections_and_ids','validation_ids'),
        (validation._Validator,'validate_structure','validation_structure'),
        (validation,'validate_schema3_booking_authority','validation_booking'),
        (validation,'validate_schema4_fulfilment_authority','validation_fulfilment'),
        (kernel,'_clone_runtime_world','whole_world_clone'),
        (kernel,'_replace_envelope','detached_commit'),
        (kernel,'build_event_queue_index','queue_build'),
        (kernel,'schedule_event','queue_insertion'),
        (kernel,'_event_contract_witness','event_witness'),
        (kernel,'_handler_contract_error','handler_kernel_comparison'),
        (proof,'_capture','flight_witness'),(proof,'_kernel_transition','flight_topology'),
        (proof,'_exact','flight_equations'),
        (candidate_ownership.CandidateOwnership,'begin','ownership_begin'),
        (candidate_ownership.CandidateOwnership,'publish','ownership_publish'),
        (candidate_ownership.CandidateOwnership,'close','ownership_close'),
        (candidate_ownership.WriteCapsule,'checked_outputs','ownership_checks'),
        (fulfilment,'_build_confirmed_carriage_manifest','manifest'),
        (fulfilment,'_next_event','handler_queue_min'),
        (fulfilment,'_matching_event','handler_event_lookup'),
        (manifest_lookup.CandidateManifestLookup,'__init__','manifest_index'),
        (checkpoint,'_clone_runtime_world','booking_probe_clone'),
        (checkpoint,'prepare_daily_booking_checkpoint','booking_prepare'),
        (checkpoint,'process_daily_booking_checkpoint','booking_process'),
        (checkpoint,'prepare_daily_booking_allocation','booking_allocation'),
        (allocation,'prepare_daily_booking_allocation','booking_allocation'),
        (allocation,'prepare_daily_booking_shopping','booking_shopping'),
        (shopping,'prepare_daily_booking_shopping','booking_shopping'),
        (shopping,'rebuild_direct_flight_shopping_indexes','shopping_index'),
        (shopping,'resolve_active_daily_cohorts','active_demand'),
        (allocation,'rebuild_booking_indexes','booking_index'),
        (indexes,'rebuild_booking_indexes','booking_index'),
        (publication,'_publish_detached','publication'),
        (publication,'_expand_schedule','publication_expansion'),
        (Stage1Session,'_mark_progress','session_notification'),
        (Stage1Session,'maybe_autosave','autosave')]
    for owner,name,key in hooks:
        stack.enter_context(patch.object(owner,name,profile.wrap(getattr(owner,name),key)))
    original=kernel._apply_handler_candidate
    def dispatch(before,candidate,event_id,handler,**kwargs):
        event=candidate['world_state']['pending_events'][event_id];kind=event['event_type']
        tick=time.perf_counter()
        result=profile.wrap(original,'handler_lifecycle:'+kind)(before,candidate,event_id,handler,**kwargs)
        row=families.setdefault(kind,dict(calls=0,seconds=0.,children=0))
        row['calls']+=1;row['seconds']+=time.perf_counter()-tick;row['children']+=len(result[2])
        return result
    stack.enter_context(patch.object(kernel,'_apply_handler_candidate',dispatch))
    started=[None];profile.gc_details={}
    def gc_time(phase,info):
        if phase=='start':started[0]=time.perf_counter()
        elif started[0] is not None:
            elapsed=time.perf_counter()-started[0];started[0]=None
            profile.seconds['gc']=profile.seconds.get('gc',0)+elapsed
            profile.calls['gc']=profile.calls.get('gc',0)+1
            row=profile.gc_details.setdefault(info['generation'],dict(calls=0,seconds=0.,maximum=0.))
            row['calls']+=1;row['seconds']+=elapsed;row['maximum']=max(row['maximum'],elapsed)
            if profile.stack:profile.stack[-1][1]+=elapsed
    gc.callbacks.append(gc_time);stack.callback(gc.callbacks.remove,gc_time)


def run(base,seconds=60,budget=120,profiled=True,snapshot=None):
    if type(seconds) is not int or seconds<1 or type(budget) not in (int,float) or not math.isfinite(budget) or budget<=0:
        raise ValueError('positive finite diagnostic bounds required')
    from app.session import Stage1Session
    from game.world_state import validate_world
    from game.world_state.timestamps import parse_canonical_utc,format_utc
    profile=ExclusiveProfile();families={};rows=[];memory=process_memory();shape=structure(base)
    first=deepcopy(base);initial=set(base['world_state']['event_history'])
    with tempfile.TemporaryDirectory(prefix='at-forensic-') as root:
        s=Stage1Session(runtime_clock=lambda:0,save_root=root);s.world=deepcopy(base)
        s.career_id=s.save_store.new_career_id();s._reset_autosave_clocks();s._ensure_runtime();s._bind_owned_reads()
        start=parse_canonical_utc(base['simulation']['time_utc']);target=format_utc(start+timedelta(seconds=seconds))
        s.begin_advance_to(target);engine=0.;first_changes=None;report=None
        with ExitStack() as stack:
            if profiled:instrument(stack,profile,families)
            for number in range(20000):
                old=set(s.world['world_state']['event_history']);tick=time.perf_counter()
                report=s.advance_tick();duration=time.perf_counter()-tick;engine+=duration
                events=[s.world['world_state']['event_history'][k] for k in s.world['world_state']['event_history'].keys()-old]
                rows.append(dict(seconds=duration,events=dict(Counter(e['event_type'] for e in events)),
                    utc=s.world['simulation']['time_utc'],memory=process_memory()))
                if first_changes is None and events:
                    first_changes=changes(first,s.world);first=None
                if report is not None or engine>=budget:break
        if s.advancing:s.cancel_advance()
        post_service_memory=process_memory();collected=gc.collect();post_collection_memory=process_memory()
        assert validate_world(s.world).is_valid
        if snapshot:Path(snapshot).write_text(json.dumps(s.world,separators=(',',':'),allow_nan=False),encoding='utf-8')
        durations=[r['seconds'] for r in rows];resolved=(parse_canonical_utc(s.world['simulation']['time_utc'])-start).total_seconds()
        raw_hash=world_digest(s.world)
        s.runtime.select_speed('Normal Speed')  # Same explicit final control as Stage 3F; outside service timing.
        normalized_hash=world_digest(s.world)
        vector=sorted((e['due_at_utc'],e['order_key'],k,e['event_type']) for k,e in s.world['world_state']['event_history'].items() if k not in initial)
        return dict(fleet=len(base['world_state']['aircraft']),profiled=profiled,requested_seconds=seconds,
            engine_seconds=engine,resolved_seconds=resolved,effective_ratio=resolved/engine,
            complete=report is not None and report.result.succeeded and report.result.status=='COMPLETED',
            failure=None if report is None or report.result.failure is None else report.result.failure.as_dict() if hasattr(report.result.failure,'as_dict') else str(report.result.failure),
            callback_count=len(rows),p50=percentile(durations,.5),p95=percentile(durations,.95),p99=percentile(durations,.99) if len(durations)>=100 else None,maximum=max(durations),
            exclusive=profile.seconds,inclusive=profile.inclusive,calls=profile.calls,gc_details=getattr(profile,'gc_details',{}),
            residual=engine-sum(profile.seconds.values()),families=families,callbacks=rows,
            source_audit=audit(base),ending_audit=audit(s.world),first_unit_changed_ids=first_changes,
            source_structure=shape,start_memory=memory,end_memory=process_memory(),
            post_service_memory=post_service_memory,post_collection_memory=post_collection_memory,gc_collected_outside_service=collected,
            booking_temperature_before=booking_temperature(base),booking_temperature_after=booking_temperature(s.world),
            hash=raw_hash,normalized_hash=normalized_hash,
            component_hashes={name:world_digest(s.world['world_state'][name]) for name in ('flight_results','transactions','event_history','bookings','itineraries')},
            deterministic_hash=world_digest(s.world['deterministic_state']),event_vector=vector)


def native(fixture_path,budget,callbacks):
    """Actual SDL2 event loop, continuously running Ultra, no page navigation."""
    from app.gui.app import AirlineTycoonApp
    from app.session import Stage1Session
    from kivy.clock import Clock
    from kivy.uix.button import Button
    from game.world_state import validate_world
    from game.world_state.timestamps import parse_canonical_utc
    base=json.loads(Path(fixture_path).read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='at-forensic-native-') as root:
        prep=Stage1Session(save_root=root);prep.world=deepcopy(base)
        prep.career_id=prep.save_store.new_career_id();prep.save_manual();career=prep.career_id;prep.leave_game()
        class Observation(AirlineTycoonApp):
            def __init__(self):
                super().__init__(session_factory=lambda:Stage1Session(save_root=root))
                self.samples=[];self.heartbeats=[];self.failure=None;self.started=None;self.previous=None
            def _error(self,title,error):self.failure=f'{title}: {error}';self.stop()
            def on_start(self):
                super().on_start();Clock.schedule_once(self.load,.1);self.beat=Clock.schedule_interval(self.heartbeat,.05)
            def on_stop(self):
                if hasattr(self,'beat'):self.beat.cancel()
                super().on_stop()
            def load(self,dt):
                try:
                    next(w for w in self.screens.get_screen('title').walk() if isinstance(w,Button) and w.text=='Load Game').dispatch('on_release')
                    label=self.session.list_careers()[0]['airline_name']+'  |'
                    next(w for w in self._popup.content.walk() if isinstance(w,Button) and w.text.startswith(label)).dispatch('on_release')
                    next(w for w in self._popup.content.walk() if isinstance(w,Button) and w.text=='Current manual save').dispatch('on_release')
                    assert self.session.career_id==career and self.session.runtime.state=='PAUSED'
                    self.started=time.perf_counter();self.previous=self.started;self.resume('Ultra')
                    self.started_unix=time.time();print(json.dumps(dict(native_started_unix=self.started_unix)),flush=True)
                except Exception as exc:self.failure=str(exc);self.stop()
            def heartbeat(self,dt):
                if self.started is None:return
                now=time.perf_counter();self.heartbeats.append(now-self.previous);self.previous=now
            def tick(self,dt):
                if self.started is None:return super().tick(dt)
                s=self.session;old=set(s.world['world_state']['event_history']);parts={};pump=s.pump;refresh=self.refresh
                def timed(fn,key):
                    def call(*args,**kwargs):
                        tick=time.perf_counter()
                        try:return fn(*args,**kwargs)
                        finally:parts[key]=time.perf_counter()-tick
                    return call
                tick=time.perf_counter()
                with patch.object(s,'pump',timed(pump,'engine')),patch.object(self,'refresh',timed(refresh,'presentation')):super().tick(dt)
                elapsed=time.perf_counter()-tick
                kinds=Counter(s.world['world_state']['event_history'][k]['event_type'] for k in s.world['world_state']['event_history'].keys()-old)
                self.samples.append(dict(seconds=elapsed,parts=parts,events=dict(kinds),state=s.runtime.state,credit_ns=s.runtime.credit_ns,utc=s.world['simulation']['time_utc'],memory=process_memory()))
                if len(self.samples)%5==0:print(json.dumps(dict(native_progress=len(self.samples),elapsed=time.perf_counter()-self.started,last=self.samples[-1])),flush=True)
                if s.runtime.blocked:self.failure=s.runtime.diagnostic;self.stop()
                elif len(self.samples)>=callbacks or time.perf_counter()-self.started>=budget:self.stop()
        app=Observation();gc_rows={};gc_start=[None]
        def native_gc(phase,info):
            if app.started is None:return
            if phase=='start':gc_start[0]=time.perf_counter()
            elif gc_start[0] is not None:
                dt=time.perf_counter()-gc_start[0];gc_start[0]=None
                row=gc_rows.setdefault(info['generation'],dict(calls=0,seconds=0.,maximum=0.))
                row['calls']+=1;row['seconds']+=dt;row['maximum']=max(row['maximum'],dt)
        gc.callbacks.append(native_gc)
        try:app.run()
        finally:gc.callbacks.remove(native_gc)
        stopped_unix=time.time()
        if app.failure:raise RuntimeError(app.failure)
        post_observation_memory=process_memory();collected=gc.collect();post_collection_memory=process_memory()
        app.session.hard_pause();assert validate_world(app.session.world).is_valid
        debt=app.session.runtime.credit_ns
        # Censored observation retains debt. Do not claim player Save/drain completed.
        # Diagnostic persistence of the validated committed prefix, outside observation.
        app.session.save_store.save(career,'manual',app.session.world,progression_revision=app.session.progression_revision)
        exact=app.session.authoritative_bytes();app.session.load_saved(career)
        assert app.session.authoritative_bytes()==exact and app.session.runtime.state=='PAUSED'
        durations=[r['seconds'] for r in app.samples]
        return dict(native=True,censored=True,page=app.current_view,speed='Ultra',source=audit(base),ending=audit(app.session.world),
            started_unix=app.started_unix,stopped_unix=stopped_unix,observed_wall_seconds=sum(r['seconds'] for r in app.samples),
            samples=app.samples,callbacks=len(durations),p50=percentile(durations,.5),p95=percentile(durations,.95),p99=percentile(durations,.99) if len(durations)>=100 else None,maximum=max(durations),
            heartbeat_max=max(app.heartbeats,default=0),gc_details=gc_rows,
            post_observation_memory=post_observation_memory,post_collection_memory=post_collection_memory,gc_collected_outside_service=collected,retained_debt_at_stop_ns=debt,
            exact_snapshot_reload=True,player_manual_save_not_claimed=True,hash=world_digest(app.session.world))


def queue_probe(base,repeats=3):
    from game.simulation import kernel
    import heapq
    builds=[];drains=[]
    for _ in range(repeats):
        tick=time.perf_counter();heap=kernel.build_event_queue_index(base);builds.append(time.perf_counter()-tick)
        tick=time.perf_counter()
        while heap:heapq.heappop(heap)
        drains.append(time.perf_counter()-tick)
    return dict(events=len(base['world_state']['pending_events']),build_seconds=builds,all_heap_pop_seconds=drains)


def event_cases():
    from tests.flight_fixtures import flight_world,window
    from tests.payment_fixtures import payment_world
    from tests.test_causal_generation import dense_weekly_fixture
    from game.world_state import create_stage1_new_game
    from game.simulation.resolver import resolve_until
    for kind in ('departure','completion'):
        world=flight_world(1);target=window(world,kind)
        yield kind,world,target
    world,target=payment_world(1);yield 'payment',world,target
    world=create_stage1_new_game(scenario_id='stage1-philippines-v1',ceo_display_name='Audit',airline_display_name='Market audit',base_airport_reference_code='MNL')
    assert resolve_until(world,'2026-09-30T23:59:59Z',shared=True).succeeded
    yield 'market-and-booking',world,'2026-10-01T00:00:00Z'
    world=dense_weekly_fixture(2);yield 'weekly-two-aircraft',world,'2026-09-20T16:00:00Z'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path);p.add_argument('--families',action='store_true')
    p.add_argument('--seconds',type=int,default=60);p.add_argument('--budget',type=float,default=120)
    p.add_argument('--queue',action='store_true');p.add_argument('--next',action='store_true');p.add_argument('--quiet',action='store_true');p.add_argument('--snapshot',type=Path)
    p.add_argument('--native',action='store_true');p.add_argument('--callbacks',type=int,default=20)
    a=p.parse_args()
    if a.seconds<1 or not math.isfinite(a.budget) or a.budget<=0 or a.callbacks<1:p.error('positive bounds required')
    if a.families:
        from game.world_state.timestamps import parse_canonical_utc
        for name,world,target in event_cases():
            seconds=max(1,int((parse_canonical_utc(target)-parse_canonical_utc(world['simulation']['time_utc'])).total_seconds()))
            print(json.dumps(dict(case=name,result=run(world,seconds,a.budget,not a.quiet))),flush=True)
        return
    if a.fixture is None:p.error('--fixture or --families required')
    world=json.loads(a.fixture.read_text(encoding='utf-8'))
    if a.next:
        from game.world_state.timestamps import parse_canonical_utc
        due=min(e['due_at_utc'] for e in world['world_state']['pending_events'].values())
        a.seconds=max(1,int((parse_canonical_utc(due)-parse_canonical_utc(world['simulation']['time_utc'])).total_seconds()))
    result=queue_probe(world) if a.queue else native(a.fixture,a.budget,a.callbacks) if a.native else run(world,a.seconds,a.budget,not a.quiet,a.snapshot)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
