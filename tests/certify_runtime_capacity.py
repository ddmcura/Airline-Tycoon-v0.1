"""Stage 3F capacity certification. TEMP fixtures, real session/resolver only.

Finite throughput is an optimistic capacity bound, NOT a live certification.
Live pacing charges measured engine uptime plus the unoccupied part of the
normal 200ms callback interval. Setup/diagnostic I/O never earns time.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from statistics import median
import tempfile
import time
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel, shared_candidate
from game.simulation.pacing import NANOSECOND
from game.simulation.speeds import PLAYER_SPEEDS
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.resolution_oracle import world_digest
from tests.profile_ph_runtime import memory_bytes

FENCES = {'DAILY_BOOKING_CHECKPOINT', 'STAGE1_WEEKLY_PUBLICATION', 'AIRCRAFT_CONTRACT_EXPIRY'}


class ServiceClock:
    """Controlled idle; real engine duration; optional exact finite input cap."""
    def __init__(self):
        self.now = 0
        self.started = None
        self.limit = None

    def __call__(self):
        value = self.now + (time.perf_counter_ns() - self.started if self.started is not None else 0)
        return min(value, self.limit) if self.limit is not None else value

    def begin(self):
        assert self.started is None
        self.started = time.perf_counter_ns()

    def finish(self):
        self.now = self()
        self.started = None

    def idle(self, ns):
        assert self.started is None
        self.now += ns
        if self.limit is not None:
            self.now = min(self.now, self.limit)


def audit(world):
    s = world['world_state']; now = parse_canonical_utc(world['simulation']['time_utc'])
    ports = {k:r['reference_code'] for k,r in s['airports'].items()}
    due = {}
    for e in s['pending_events'].values():
        due[e['event_type']] = min(due.get(e['event_type'], e['due_at_utc']), e['due_at_utc'])
    flights = list(s['dated_flights'].values())
    daily = [f for f in flights if now <= parse_canonical_utc(f['scheduled_off_block_utc']) < now + timedelta(days=1)]
    return dict(start_utc=world['simulation']['time_utc'], aircraft=len(s['aircraft']),
        flights_per_next_24h=len(daily), departures_per_next_24h=len(daily),
        completions_per_next_24h=sum(now <= parse_canonical_utc(f['scheduled_in_block_utc']) < now+timedelta(days=1) for f in flights),
        markets=sorted({ports[f['origin_airport_id']]+'-'+ports[f['destination_airport_id']] for f in flights}),
        collection_sizes={k:len(s[k]) for k in ('bookings','itineraries','dated_flights','pending_events','event_history','flight_results','transactions','schedule_definitions','active_aircraft_operations','aircraft_contracts')},
        statuses=dict(Counter(f['status'] for f in flights)), next_events=due,
        pending_types=dict(Counter(e['event_type'] for e in s['pending_events'].values())),
        recurrence=dict(Counter(r['recurrence'].get('publication_policy','manual') for d in s['schedule_definitions'].values() for r in d['revisions'].values())),
        hash=world_digest(world))


def fixture(size):
    """Public purchases/definitions/publication; domain-produced timing/history."""
    from tests.profile_scheduling import fresh, identities
    from game.scheduling import WeeklyDraft
    from game.scheduling.weekly import _connection
    from game.scheduling.publication import create_schedule_definition
    from game.scheduling.recurrence import publish_rolling_window
    from game.scheduling.timing import timing_bounds
    from game.scheduling.local_time import airport_zone
    from game.economy.fare_reference import suggested_economy_fare_minor
    if type(size) is not int or size<1: raise ValueError('positive aircraft count required')
    w = fresh(size); owner, _, ports = identities(w)
    assert len(w['world_state']['aircraft'])==size
    for index, aircraft_id in enumerate(sorted(w['world_state']['aircraft'])):
        draft = WeeklyDraft(w, airline_id=owner, aircraft_id=aircraft_id)
        for cycle in range(2):
            destination = ports[('DVO','CEB','ILO','BCD','PPS')[(index+cycle)%5]]
            depart = parse_canonical_utc('2026-09-01T01:00:00Z') + timedelta(hours=cycle*6, minutes=index*2)
            fare = suggested_economy_fare_minor(w['world_state'], ports['MNL'], destination)
            draft.add(ports['MNL'], destination, departure_utc=format_utc(depart), fare_minor=fare)
            draft.add_return(fare_minor=suggested_economy_fare_minor(w['world_state'], destination, ports['MNL']))
        for leg in draft.legs:
            s=w['world_state']; origin=leg['origin_airport_id']; dest=leg['destination_airport_id']
            dep=parse_canonical_utc(leg['departure_utc'])
            arr=dep+timedelta(seconds=timing_bounds(leg['planning_timing'])[1][1])
            local=dep.astimezone(airport_zone(s, origin)); arrival=arr.astimezone(airport_zone(s,dest))
            r=create_schedule_definition(w, airline_id=owner, connection_id=_connection(w,owner,origin,dest),
                planned_aircraft_id=aircraft_id, origin_airport_id=origin,destination_airport_id=dest,
                effective_from_local_date='2026-09-01',weekdays=list(range(7)),
                departure_local_time=local.strftime('%H:%M:%S'),arrival_local_time=arrival.strftime('%H:%M:%S'),
                arrival_day_offset=(arrival.date()-local.date()).days,
                capacity=s['aircraft'][aircraft_id]['configuration']['economy_capacity'],
                fare_offer={'currency':'USD','amount_minor':leg['fare_minor']},
                passenger_service_classification='ECONOMY',planning_timing=leg['planning_timing'],
                publication_policy='ROLLING_FOUR_WEEKS_V1')
            assert r.succeeded,r
        if (index+1)%10==0: print(json.dumps({'setup_aircraft':index+1,'fleet':size}),flush=True)
    publish_rolling_window(w,owner)
    return warm(w)


def warm(w):
    """Real events through first Booking checkpoint and mixed next-day cycles."""
    size=len(w['world_state']['aircraft'])
    # Natural warmup puts aircraft in mixed operating phases and retains actual
    # Booking/journal/flight history. No invented NO_OP history or pruned records.
    with tempfile.TemporaryDirectory(prefix='at-capacity-warm-') as root:
        s=Stage1Session(runtime_clock=lambda:0,save_root=root);s.world=w
        s._ensure_runtime();s._bind_owned_reads()
        s.begin_advance_to('2026-09-02T03:00:00Z')
        units=0
        while s.advancing:
            report=s.advance_tick(); units+=1
            if units%10==0: print(json.dumps({'setup_warm_units':units,'fleet':size,'utc':w['simulation']['time_utc']}),flush=True)
            if report is not None: assert report.result.succeeded,report.result.failure
    assert validate_world(w).is_valid
    return w


def process_memory():
    """Current and peak working set; never confuse high-water with growth."""
    import os
    if os.name != 'nt': return {'working_bytes':None,'peak_bytes':memory_bytes()}
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ('peak','working','pp','p','pnp','np','pf','ppf')]
    c=Counters();c.cb=ctypes.sizeof(c)
    handle=ctypes.windll.kernel32.GetCurrentProcess;handle.restype=wintypes.HANDLE
    query=ctypes.windll.psapi.GetProcessMemoryInfo;query.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
    assert query(handle(),ctypes.byref(c),c.cb)
    return {'working_bytes':c.working,'peak_bytes':c.peak}


def percentile(values, q):
    return sorted(values)[int(q*(len(values)-1))] if values else None


def running_metrics(rows):
    """Do not let a later commanded drain conceal growing running backlog."""
    active=[row for row in rows if row['state']=='RUNNING']
    if not active: return {'end':None,'slope':None,'service_ratio':None}
    first,last=active[0],active[-1]
    elapsed=last['pacing_input_seconds']-first['pacing_input_seconds']
    backlog=last['backlog_ns']/NANOSECOND
    total=last['resolved_game_seconds']+backlog
    return dict(end=last,slope=(last['backlog_ns']-first['backlog_ns'])/NANOSECOND/elapsed if elapsed>0 else None,
        service_ratio=last['resolved_game_seconds']/total if total else None)


def measure(base, *, speed='Ultra', days=1, seconds=None, mode='live', budget=120, save_reload=False, instrument=False):
    """No dispatch replacement: the actual session chooses all routing/policies.

    A budgeted stop is censored failure evidence, never successful certification.
    Hard pause retains any unfinished credit and does not claim owed work drained.
    """
    from tests.profile_atomic_boundaries import ExclusiveProfile
    clock=ServiceClock(); rows=[]; units=Counter(); fences=[]; autosaves=[]; profile=ExclusiveProfile()
    with tempfile.TemporaryDirectory(prefix='at-capacity-run-') as root, ExitStack() as stack:
        s=Stage1Session(runtime_clock=clock,save_root=root);s.world=deepcopy(base)
        s.career_id=s.save_store.new_career_id();s._reset_autosave_clocks();s._ensure_runtime();s._bind_owned_reads()
        r=s.runtime; assert r.shared and r.max_batch_events==8
        start=parse_canonical_utc(s.world['simulation']['time_utc']); horizon=days*86400 if seconds is None else seconds
        if type(horizon) is not int or horizon<1: raise ValueError('positive integer horizon required')
        target=format_utc(start+timedelta(seconds=horizon))
        initial_credit=0
        initial_history=set(s.world['world_state']['event_history']); initial_hash=world_digest(s.world)
        s.resume(speed)
        selected_ratio=r.ratio
        if mode=='live': clock.limit=(horizon*NANOSECOND+r.ratio-1)//r.ratio; clock.idle(200_000_000)
        elif mode=='finite': r.credit_ns=horizon*NANOSECOND;initial_credit=r.credit_ns
        elif mode=='advance': s.begin_advance_to(target)
        else: raise ValueError(mode)
        commit_fn=kernel._replace_envelope
        def commit(*args,**kw):
            units['detached_commits']+=1
            return commit_fn(*args,**kw)
        stack.enter_context(patch.object(kernel,'_replace_envelope',commit))
        earned_ns=[0]
        sample_fn=r._sample
        def sampled():
            before=r.credit_ns
            result=sample_fn()
            earned_ns[0]+=r.credit_ns-before
            return result
        stack.enter_context(patch.object(r,'_sample',sampled))
        def shared(request):
            units['shared']+=1
            return shared_fn(request)
        shared_fn=shared_candidate.SharedResolutionRequest._shared_batch
        stack.enter_context(patch.object(shared_candidate.SharedResolutionRequest,'_shared_batch',shared))
        def strict(request):
            event=request._world['world_state']['pending_events'][request._heap[0][3]]
            units['strict']+=1; tick=time.perf_counter(); before=r.credit_ns
            try: return strict_fn(request)
            finally:
                fences.append(dict(event_type=event['event_type'],fence=event['event_type'] in FENCES,
                    seconds=time.perf_counter()-tick,backlog_before_ns=before,callback=len(rows)))
        strict_fn=shared_candidate.SharedResolutionRequest._strict_one
        stack.enter_context(patch.object(shared_candidate.SharedResolutionRequest,'_strict_one',strict))
        save_fn=s.save_store.save
        save_phase=['capacity']
        def save(*args,**kw):
            tick=time.perf_counter()
            try: return save_fn(*args,**kw)
            finally: autosaves.append(dict(slot=args[1],seconds=time.perf_counter()-tick,utc=s.world['simulation']['time_utc'],request_active=r.work is not None,phase=save_phase[0]))
        stack.enter_context(patch.object(s.save_store,'save',save))
        if instrument:
            from game.world_state import validation
            hooks=[(validation._Validator,'run','full_validation'),(validation,'_plain_authority_tree','structural_graph'),(validation,'validate_schema3_booking_authority','booking_validation'),(kernel,'_clone_runtime_world','clone'),
                (kernel,'_replace_envelope','commit'),(kernel,'_apply_handler_candidate','handler'),
                (kernel,'_event_contract_witness','event_history_witness'),
                (kernel,'_handler_contract_error','event_history_proof'),
                (s,'_mark_progress','session_notification'),(s,'maybe_autosave','autosave')]
            from game.world_state import flight_transition_validation as proof
            from game.aircraft_operations import fulfilment, manifest_lookup
            from game.simulation import candidate_ownership
            # Certificate entry callables are identity-bound. Wrapping them
            # would silently turn this into a strict-only benchmark. Time
            # internal dependencies instead; unhooked proof work is residual.
            hooks.extend([(proof,'_capture','transition_capture_subphase'),
                (proof,'_kernel_transition','event_topology_proof'),
                (proof,'_exact','transition_equations')])
            hooks.extend([(fulfilment,'_build_confirmed_carriage_manifest','manifest'),
                (manifest_lookup.CandidateManifestLookup,'__init__','manifest_lookup'),
                (candidate_ownership.CandidateOwnership,'__init__','ownership'),
                (candidate_ownership.CandidateOwnership,'begin','capsule'),
                (candidate_ownership.CandidateOwnership,'publish','capsule'),
                (candidate_ownership.CandidateOwnership,'close','ownership')])
            for owner,name,key in hooks: stack.enter_context(patch.object(owner,name,profile.wrap(getattr(owner,name),key)))
        durations=[]; engine=0.; memory_start=process_memory(); saved=False; overloads=0;recoveries=0; prior_state=r.state
        for callback in range(20000):
            before_utc=s.world['simulation']['time_utc']; before_events=len(s.world['world_state']['event_history']); before_commits=units['detached_commits'];before_revision=s.progression_revision
            before_credit=r.credit_ns; before_units=units.copy(); tick=time.perf_counter()
            if mode=='live': clock.begin()
            if mode=='advance': report=s.advance_tick()
            else: s.pump(); report=None
            if mode=='live': clock.finish()
            dt=time.perf_counter()-tick; engine+=dt;durations.append(dt)
            resolved=int((parse_canonical_utc(s.world['simulation']['time_utc'])-start).total_seconds())
            if r.state=='OVERLOAD_DRAIN' and prior_state!='OVERLOAD_DRAIN': overloads+=1
            if r.state=='RECOVERED' and prior_state!='RECOVERED': recoveries+=1
            prior_state=r.state
            rows.append(dict(callback=callback,seconds=dt,cumulative_engine_seconds=engine,pacing_input_seconds=clock.now/NANOSECOND,
                earned_game_seconds=None if mode=='advance' else resolved+r.credit_ns/NANOSECOND,resolved_game_seconds=resolved,
                utc=s.world['simulation']['time_utc'],target_utc=target if mode=='advance' else r.earned_target_utc,backlog_before_ns=(r.last_pump or {}).get('backlog_before_ns',before_credit),backlog_ns=r.credit_ns,
                events=len(s.world['world_state']['event_history'])-before_events,commits=units['detached_commits']-before_commits,notifications=s.progression_revision-before_revision,
                memory=process_memory(),shared_units=units['shared']-before_units['shared'],strict_units=units['strict']-before_units['strict'],state=r.state))
            if callback%10==0: print(json.dumps({'progress':mode,'fleet':len(base['world_state']['aircraft']),'speed':speed,'engine_seconds':engine,'resolved_seconds':resolved,'backlog_seconds':r.credit_ns/NANOSECOND,'state':r.state}),flush=True)
            if r.blocked: break
            if mode=='advance' and report is not None: break
            if mode!='advance' and r.work is None and r.credit_ns<NANOSECOND and (mode=='finite' or clock.now==clock.limit): break
            if mode=='live' and clock.now==clock.limit and r.running: s.pause()
            if not r.processing and mode=='live': break
            if engine>=budget: break
            if mode=='live': clock.idle(max(0,200_000_000-int(dt*NANOSECOND)))
        # Freeze attribution before audit/save/load verification. The hooks stay
        # installed for safe cleanup but those costs are not engine service.
        exclusive=dict(profile.seconds);profile_calls=dict(profile.calls)
        success=(report is not None and report.result.succeeded and report.result.status=='COMPLETED') if mode=='advance' else not r.blocked and r.state!='ERROR'
        complete=(success and s.world['simulation']['time_utc']==target and (mode=='advance' or (r.work is None and r.credit_ns<NANOSECOND)))
        end_state=r.state;end_diagnostic=r.diagnostic
        if s.advancing: s.cancel_advance()
        s.hard_pause()
        end_credit=r.credit_ns;end_target=r.earned_target_utc
        if mode!='advance':
            assert int((parse_canonical_utc(s.world['simulation']['time_utc'])-start).total_seconds())*NANOSECOND+end_credit==initial_credit+earned_ns[0], 'pacing ledger lost credit'
        # Explicit common final speed action; no field excluded from the oracle.
        r.select_speed('Normal Speed')
        assert validate_world(s.world).is_valid
        events=[e for k,e in s.world['world_state']['event_history'].items() if k not in initial_history]
        resolved=int((parse_canonical_utc(s.world['simulation']['time_utc'])-start).total_seconds())
        backlog=[x['backlog_ns']/NANOSECOND for x in rows]
        for f in fences:
            index=f['callback'];f['backlog_after_ns']=rows[index]['backlog_ns']
            baseline=f['backlog_before_ns']; subsequent=next((x for x in rows[index+1:] if x['backlog_ns']<=baseline),None)
            f['recovered_after_engine_seconds']=None if subsequent is None else subsequent['cumulative_engine_seconds']-rows[index]['cumulative_engine_seconds']
            f['recovery_state']=None if subsequent is None else subsequent['state']
            f['recovered_after_pacing_seconds']=None if subsequent is None else subsequent['pacing_input_seconds']-rows[index]['pacing_input_seconds']
        running=running_metrics(rows)
        input_end=running['end']
        result=dict(pacing_window_end=input_end,active_accrual_pacing_seconds=earned_ns[0]/(selected_ratio*NANOSECOND),drain_engine_seconds=sum(x['seconds'] for x in rows if x['state'] in ('PLAYER_DRAIN','OVERLOAD_DRAIN')),fleet=len(base['world_state']['aircraft']),speed=speed,ratio=selected_ratio,mode=mode,days=horizon/86400,requested_game_seconds=horizon,complete=complete,
            engine_wall_seconds=engine,pacing_input_seconds=clock.now/NANOSECOND,earned_game_seconds=None if mode=='advance' else resolved+end_credit/NANOSECOND,measured_accrued_credit_ns=earned_ns[0],initial_credit_ns=initial_credit,
            resolved_game_seconds=resolved,ending_utc=s.world['simulation']['time_utc'],requested_target_utc=target,earned_target_utc=None if mode=='advance' else end_target,
            starting_backlog_seconds=initial_credit/NANOSECOND,ending_backlog_seconds=end_credit/NANOSECOND,
            maximum_backlog_seconds=max([initial_credit/NANOSECOND]+backlog+[x['backlog_before_ns']/NANOSECOND for x in rows]),backlog_slope_game_seconds_per_pacing_second=running['slope'],running_service_ratio=running['service_ratio'],
            service_ratio=None if mode=='advance' else (resolved/(resolved+end_credit/NANOSECOND) if resolved+end_credit/NANOSECOND else 0),
            engine_service_speed=resolved/engine if engine else 0,full_day_service_upper_bound=horizon/engine if not complete and mode=='finite' and horizon==86400 else None,
            state=end_state,diagnostic=end_diagnostic,overload_count=overloads,recovery_count=recoveries,
            callback_count=len(rows),median_callback_seconds=median(durations),p95_callback_seconds=percentile(durations,.95),p99_callback_seconds=percentile(durations,.99) if len(rows)>=100 else None,max_callback_seconds=max(durations),
            max_shared_callback_seconds=max((x['seconds'] for x in rows if x['shared_units']),default=0),
            max_strict_callback_seconds=max((x['seconds'] for x in rows if x['strict_units']),default=0),
            units=dict(units),event_count=len(events),event_types=dict(Counter(e['event_type'] for e in events)),commit_count=sum(x['commits'] for x in rows),
            event_vector=[(e['event_id'],e['event_type'],e['due_at_utc'],tuple(e['order_key'])) for e in events],callbacks=rows,fences=fences,autosaves=autosaves,save_reload_passed=saved,
            memory_start=memory_start,memory_end=process_memory(),initial_hash=initial_hash,world_hash=world_digest(s.world),
            exclusive_seconds=exclusive,profile_calls=profile_calls,ending_sizes=audit(s.world)['collection_sizes'])
        if save_reload and end_credit<NANOSECOND:
            save_phase[0]='verification'
            result['persistence_check']=persistence_check(s,clock)
            result['save_reload_passed']=True
        return result


def persistence_check(session, clock):
    """Checkpoint/continuation verification, outside measured service interval."""
    from game.world_state.timestamps import parse_canonical_utc
    assert not session.runtime.draining and session.runtime.credit_ns<NANOSECOND
    expected=world_digest(session.world);utc=session.world['simulation']['time_utc']
    session.save_manual();career=session.career_id;session.load_saved(career)
    assert world_digest(session.world)==expected
    assert session.runtime.state=='PAUSED' and session.runtime.credit_ns==0
    clock.limit=None;clock.idle(2*NANOSECOND)
    session.pump();assert session.world['simulation']['time_utc']==utc
    session.resume('Normal Speed');clock.idle(2*NANOSECOND);session.pause()
    target=session.runtime.earned_target_utc
    while session.runtime.draining:
        session.pump()
        assert not session.runtime.blocked,session.runtime.diagnostic
    assert session.world['simulation']['time_utc']==target
    session.save_manual();continued=world_digest(session.world);session.load_saved(career)
    assert world_digest(session.world)==continued and session.runtime.credit_ns==0
    clock.idle(900*NANOSECOND)
    auto=session.maybe_autosave();second=session.maybe_autosave()
    assert auto and not second and validate_world(session.world).is_valid
    session.load_saved(career,'autosave')
    assert world_digest(session.world)==continued and session.runtime.state=='PAUSED'
    return dict(exact_save_reload=True,paused_zero_debt=True,no_offline=True,
        resumed_to_utc=target,autosave_first=True,autosave_second=False,hash=continued)


def equivalence(base, seconds=60, budget=120):
    """Complete-world four-speed and independent strict-kernel comparison.

    Finite credit deliberately compares one identical target, not capacity. The
    same explicit final pause/Normal selection is applied to every reference;
    no authoritative field is omitted or ignored.
    """
    from tests.resolution_oracle import strict_until
    from game.simulation.pacing import RuntimeController
    results=[measure(base,speed=speed.name,seconds=seconds,mode='finite',budget=budget)
             for speed in PLAYER_SPEEDS]
    assert all(r['complete'] for r in results), 'censored run cannot prove equivalence'
    reference=deepcopy(base)
    start=time.perf_counter()
    result=strict_until(reference,results[0]['requested_target_utc'])
    assert result.succeeded and result.status=='COMPLETED',result.failure
    controller=RuntimeController(reference,clock=lambda:0)
    controller.hard_pause();controller.select_speed('Normal Speed')
    expected=world_digest(reference)
    assert all(r['world_hash']==expected for r in results)
    histories=reference['world_state']['event_history']
    initial=set(base['world_state']['event_history'])
    vector=[(e['event_id'],e['event_type'],e['due_at_utc'],tuple(e['order_key']))
            for key,e in histories.items() if key not in initial]
    assert all(r['event_vector']==vector for r in results)
    return dict(fleet=len(base['world_state']['aircraft']),seconds=seconds,
        target=results[0]['requested_target_utc'],hash=expected,
        event_vector=vector,strict_seconds=time.perf_counter()-start,
        speeds=[dict(speed=r['speed'],engine_seconds=r['engine_wall_seconds'],
                     callbacks=r['callback_count'],commits=r['commit_count'],
                     hash=r['world_hash']) for r in results])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--build',action='store_true');p.add_argument('--fleets',default='1,10,25,50');p.add_argument('--mode',choices=['finite','live','advance'],default='finite');p.add_argument('--days',type=int,default=1);p.add_argument('--seconds',type=int);p.add_argument('--speeds',default='Ultra');p.add_argument('--pacing-seconds',type=int);p.add_argument('--budget',type=float,default=120);p.add_argument('--instrument',action='store_true');p.add_argument('--save-check',action='store_true');p.add_argument('--equivalence',action='store_true');a=p.parse_args()
    if a.budget<=0 or a.days<1 or (a.pacing_seconds is not None and a.pacing_seconds<1): p.error('positive budget/horizon required')
    a.fixtures.mkdir(parents=True,exist_ok=True)
    for size in map(int,a.fleets.split(',')):
        path=a.fixtures/f'fleet-{size}.json'
        if a.build:
            started=time.perf_counter()
            if path.exists():
                world=json.loads(path.read_text(encoding='utf-8'))
                if world['simulation']['time_utc']<'2026-09-02T03:00:00Z':
                    world=warm(world)
                    path.write_text(json.dumps(world,separators=(',',':'),allow_nan=False),encoding='utf-8')
            else:
                world=fixture(size)
                path.write_text(json.dumps(world,separators=(',',':'),allow_nan=False),encoding='utf-8')
            print(json.dumps({'fixture_audit':audit(world),'setup_seconds':time.perf_counter()-started}),flush=True)
            continue
        world=json.loads(path.read_text(encoding='utf-8'));assert validate_world(world).is_valid
        assert len(world['world_state']['aircraft'])==size, 'fixture fleet label does not match authority'
        if a.equivalence:
            print(json.dumps({'equivalence_result':equivalence(world,a.seconds or 60,a.budget)}),flush=True)
            continue
        for speed in a.speeds.split(','):
            from game.simulation.speeds import player_speed
            seconds=a.seconds if a.pacing_seconds is None else a.pacing_seconds*player_speed(speed).ratio
            report=measure(world,speed=speed,days=a.days,seconds=seconds,mode=a.mode,budget=a.budget,instrument=a.instrument,save_reload=a.save_check)
            print(json.dumps({'capacity_result':report}),flush=True)

if __name__=='__main__': main()
