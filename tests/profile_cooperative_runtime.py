"""Production pump measurements on frozen TEMP worlds; no production saves."""
import argparse
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
from game.simulation import pacing, kernel, shared_candidate
from game.simulation.resolver import begin_resolution
from game.simulation.speeds import PLAYER_SPEEDS
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.resolution_oracle import world_digest

class Clock:
    def __init__(self, active=False):
        self.now=0; self.active=active; self.start=time.perf_counter_ns()
    def __call__(self):
        return self.now+(time.perf_counter_ns()-self.start if self.active else 0)

def measure(base,target,*,shared=True,batch=8,speed='Normal Speed',service_seconds=None):
    clock=Clock(); rows=[]; counts={'strict_events':0,'shared_batches':0,'commits':0,'clock_boundaries':0}
    def counted(fn,key):
        def call(*a,**k):
            counts[key]+=1
            return fn(*a,**k)
        return call
    def dispatch(world,target,**options):
        options.update(shared=shared,max_batch_events=batch)
        return begin_resolution(world,target,**options)
    with tempfile.TemporaryDirectory(prefix='at-pump-profile-') as root, ExitStack() as stack:
        stack.enter_context(patch.object(pacing,'begin_resolution',dispatch))
        stack.enter_context(patch.object(kernel,'_execute_event',counted(kernel._execute_event,'strict_events')))
        stack.enter_context(patch.object(shared_candidate.SharedResolutionRequest,'_shared_batch',counted(shared_candidate.SharedResolutionRequest._shared_batch,'shared_batches')))
        stack.enter_context(patch.object(kernel,'_replace_envelope',counted(kernel._replace_envelope,'commits')))
        session=Stage1Session(runtime_clock=clock,save_root=root); session.world=deepcopy(base)
        if service_seconds is not None:
            # Resolve the quiet gap through the authoritative kernel, outside
            # timing, so every speed probes the same immediate busy boundary.
            now=parse_canonical_utc(session.world['simulation']['time_utc'])
            due=min(parse_canonical_utc(e['due_at_utc']) for e in session.world['world_state']['pending_events'].values())
            if due>now+timedelta(seconds=1):
                result=kernel.process_events_through(session.world,format_utc(due-timedelta(seconds=1)))
                assert result.succeeded,result.failure
        session._ensure_runtime(); session._bind_owned_reads()
        runtime=session.runtime; session.resume(speed)
        start_utc=parse_canonical_utc(session.world['simulation']['time_utc'])
        if service_seconds is None:
            duration=int((parse_canonical_utc(target)-start_utc).total_seconds())
            # Exactly finite earned work, with fake monotonic timing of zero cost.
            runtime.credit_ns=duration*pacing.NANOSECOND
        else:
            # Force the same immediate busy boundary; subsequent credit is real
            # processing uptime plus an ideal 200-ms idle callback interval.
            next_due=min(e['due_at_utc'] for e in session.world['world_state']['pending_events'].values())
            seconds=max(1,int((parse_canonical_utc(next_due)-start_utc).total_seconds()))
            clock.now=(seconds*pacing.NANOSECOND+runtime.ratio-1)//runtime.ratio
            clock.active=True; clock.start=time.perf_counter_ns()
        initial=len(session.world['world_state']['event_history']); started=time.perf_counter()
        for _ in range(20000):
            before=runtime.credit_ns; events=len(session.world['world_state']['event_history']); commits=counts['commits']; utc=session.world['simulation']['time_utc']; tick=time.perf_counter()
            session.pump()
            counts['clock_boundaries']+=int(utc!=session.world['simulation']['time_utc'] and events==len(session.world['world_state']['event_history']))
            before=(runtime.last_pump or {}).get('backlog_before_ns',before)
            rows.append(dict(seconds=time.perf_counter()-tick,events=len(session.world['world_state']['event_history'])-events,commits=counts['commits']-commits,backlog_before=before/pacing.NANOSECOND,backlog_after=runtime.credit_ns/pacing.NANOSECOND))
            if runtime.blocked: break
            if service_seconds is not None:
                if clock()/pacing.NANOSECOND>=service_seconds or not runtime.running: break
                clock.now+=200_000_000
            elif runtime.work is None and runtime.credit_ns<pacing.NANOSECOND: break
        else: raise RuntimeError('pump did not complete')
        processing=time.perf_counter()-started
        diagnostics=runtime.diagnostic
        state=runtime.state if hasattr(runtime,'state') else 'LEGACY'
        # Snapshot only committed authority, with no debt persisted.
        if hasattr(runtime,'hard_pause'): runtime.hard_pause()
        else: runtime.pause(); runtime.cancel_work()
        active=runtime.last_ns; clock.active=False; clock.now=active
        earned_ns=runtime.credit_ns+int((parse_canonical_utc(session.world['simulation']['time_utc'])-start_utc).total_seconds())*pacing.NANOSECOND
        assert validate_world(session.world).is_valid
        if runtime.last_result and not runtime.last_result.succeeded: raise RuntimeError(runtime.last_result.failure)
        durations=[r['seconds'] for r in rows]; resolved=int((parse_canonical_utc(session.world['simulation']['time_utc'])-start_utc).total_seconds())
        return dict(speed=speed,batch=batch,shared=shared,processing_seconds=processing,requested_game_seconds=earned_ns/pacing.NANOSECOND,resolved_game_seconds=resolved,backlog_game_seconds=runtime.credit_ns/pacing.NANOSECOND,active_seconds=clock()/pacing.NANOSECOND,diagnostic=diagnostics,state=state,median_callback_seconds=median(durations),max_callback_seconds=max(durations),p95_callback_seconds=sorted(durations)[int(.95*(len(durations)-1))] if len(durations)>=20 else None,callbacks=len(rows),events=len(session.world['world_state']['event_history'])-initial,counts=counts,callback_rows=rows,world_hash=world_digest(session.world))

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--fixtures',type=Path,required=True); p.add_argument('--cases',default='one-departure,one-completion,dense-25,divine-next-departure'); p.add_argument('--batches',default='1,8,64'); p.add_argument('--repeats',type=int,default=1); p.add_argument('--mode',choices=['shared','strict','both'],default='both'); p.add_argument('--service-seconds',type=float); a=p.parse_args()
    if a.repeats < 1: p.error('--repeats must be positive')
    if a.service_seconds is not None and a.service_seconds <= 0: p.error('--service-seconds must be positive')
    for name in a.cases.split(','):
        expected_hash=None
        fixture=json.loads((a.fixtures/(name+'.json')).read_text(encoding='utf-8'))
        for shared in ([False,True] if a.mode=='both' else [a.mode=='shared']):
            for batch in (list(map(int,a.batches.split(','))) if shared else [1]):
                for speed in (PLAYER_SPEEDS if a.service_seconds is not None else PLAYER_SPEEDS[:1]):
                    reports=[measure(fixture['world'],fixture['target'],shared=shared,batch=batch,speed=speed.name,service_seconds=a.service_seconds) for _ in range(a.repeats)]
                    if a.service_seconds is None:
                        hashes={r['world_hash'] for r in reports}
                        assert len(hashes)==1
                        current_hash=next(iter(hashes))
                        if expected_hash is None: expected_hash=current_hash
                        assert current_hash==expected_hash, 'strict/shared or budget changed complete authority'
                    print(json.dumps(dict(case=name,median_seconds=median(r['processing_seconds'] for r in reports),reports=reports)),flush=True)
if __name__=='__main__': main()
