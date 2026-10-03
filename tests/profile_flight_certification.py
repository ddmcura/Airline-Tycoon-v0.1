"""Repeatable Stage 3C fixtures in a caller-supplied TEMP directory only."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch
from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import world_digest
from tests.profile_ph_runtime import memory_bytes


def measure(base, target, repeats, shared):
    initialize_runtime_handlers()
    samples=[]; maximum=[]; digest=None; latency_batches=None
    def run(world):
        request=begin_resolution(world,target,shared=shared,max_batch_events=64,max_generated_events=10000)
        latencies=[]; batches=[]
        while not request.finished:
            before=request._completed
            start=perf_counter(); request.step(); latencies.append(perf_counter()-start)
            if request._completed > before: batches.append(request._completed-before)
        assert request.result.succeeded, request.result.failure
        return request,latencies,batches
    for _ in range(repeats):
        world=deepcopy(base); start=perf_counter()
        request,latencies,batches=run(world)
        samples.append(perf_counter()-start); maximum.append(max(latencies))
        assert latency_batches is None or batches==latency_batches
        latency_batches=batches
        actual=world_digest(world)
        assert digest is None or actual==digest
        digest=actual
    latency_peak=memory_bytes()
    timers={}; calls={}
    def timed(fn,name):
        def call(*args,**kwargs):
            calls[name]=calls.get(name,0)+1
            start=perf_counter()
            try: return fn(*args,**kwargs)
            finally: timers[name]=timers.get(name,0)+perf_counter()-start
        return call
    with ExitStack() as stack:
        validations=stack.enter_context(patch.object(kernel,'validate_world',wraps=kernel.validate_world))
        clones=stack.enter_context(patch.object(kernel,'_clone_runtime_world',wraps=kernel._clone_runtime_world))
        from game.aircraft_operations import fulfilment
        stack.enter_context(patch.object(fulfilment,'_build_confirmed_carriage_manifest',side_effect=timed(fulfilment._build_confirmed_carriage_manifest,'manifest_seconds')))
        stack.enter_context(patch.object(kernel,'_event_contract_witness',side_effect=timed(kernel._event_contract_witness,'kernel_witness_seconds')))
        for name in ('completion_cost','settlement_records'):
            if hasattr(fulfilment,name):
                stack.enter_context(patch.object(fulfilment,name,side_effect=timed(getattr(fulfilment,name),name+'_seconds')))
        try: from game.world_state import flight_transition_validation as proof
        except ImportError: proof=None
        if proof:
            stack.enter_context(patch.object(proof,'json_compatibility_error',side_effect=timed(proof.json_compatibility_error,'json_check_seconds')))
            stack.enter_context(patch.object(proof,'_container_alias_error',side_effect=timed(proof._container_alias_error,'alias_check_seconds')))
            stack.enter_context(patch.object(proof,'_protected_digest',side_effect=timed(proof._protected_digest,'protected_fingerprint_seconds')))
            for name in ('capture_departure','validate_departure','capture_completion','validate_completion'):
                if hasattr(proof,name):
                    stack.enter_context(patch.object(proof,name,side_effect=timed(getattr(proof,name),name+'_seconds')))
        initialize_runtime_handlers()
        world=deepcopy(base); request,latencies,batches=run(world)
    initialize_runtime_handlers()
    assert world_digest(world)==digest
    assert batches==latency_batches, "instrumentation changed execution boundaries"
    return dict(median_seconds=median(samples),samples_seconds=samples,max_step_seconds=max(maximum),
        events=request._completed,events_per_commit=batches,full_validations=validations.call_count,
        world_clones=clones.call_count,world_hash=digest,latency_lifetime_peak_bytes=latency_peak,
        lifetime_peak_bytes=memory_bytes(),instrumented_calls=calls,**timers)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--mode',choices=('strict','shared','both'),default='both')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--case',default='all')
    parser.add_argument('--observed-fixture',type=Path)
    args=parser.parse_args()
    assert args.repeats>0
    args.fixtures.mkdir(parents=True,exist_ok=True)
    cases=[('one-departure',1,'departure',{}),('one-completion',1,'completion',{}),
        ('round-trip',1,'round-trip',{}),('dense-departure',10,'departure',{}),
        ('dense-completion',10,'completion',{}),('mixed-ten',10,'round-trip',{'stagger_seconds':600}),
        ('representative-ten',10,'round-trip',{'stagger_seconds':180,'days':2}),
        ('aged-ten',10,'round-trip',{'history':1000}),('dense-25',25,'round-trip',{})]
    if args.observed_fixture:
        cases.extend([('divine-next-departure',0,'departure',{}),('divine-short',0,'short',{})])
    for name,count,kind,options in cases:
        if args.case not in ('all',name): continue
        path=args.fixtures/(name+'.json')
        if path.exists(): row=json.loads(path.read_text(encoding='utf-8'))
        else:
            if count:
                base=flight_world(count,**options); target=window(base,kind)
            else:
                from datetime import timedelta
                from game.world_state import validate_world
                from game.world_state.timestamps import format_utc,parse_canonical_utc
                base=json.loads(args.observed_fixture.read_text(encoding='utf-8'))
                assert validate_world(base).is_valid
                departure=min(e['due_at_utc'] for e in base['world_state']['pending_events'].values()
                    if e['event_type']=='STAGE1_FLIGHT_DEPARTURE')
                target=departure if kind=='departure' else format_utc(parse_canonical_utc(departure)+timedelta(hours=4))
            row=dict(world=base,target=target)
            path.write_text(json.dumps(row),encoding='utf-8')
            print(json.dumps(dict(built=name,world_hash=world_digest(base))),flush=True)
        modes=(False,True) if args.mode=='both' else (args.mode=='shared',)
        report={}
        for shared in modes:
            report['shared' if shared else 'strict']=measure(row['world'],row['target'],args.repeats,shared)
        if len(modes)==2: assert report['strict']['world_hash']==report['shared']['world_hash']
        print(json.dumps(dict(case=name,input_hash=world_digest(row['world']),**report)),flush=True)

if __name__=='__main__': main()
