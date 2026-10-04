"""Exclusive Stage 3D proof profile, frozen TEMP fixtures, no mock argument retention."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter
from statistics import median
from unittest.mock import patch
from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution
from game.world_state import flight_transition_validation as proof
from game.aircraft_operations import fulfilment
from tests.resolution_oracle import world_digest
from tests.profile_ph_runtime import memory_bytes


def profile(base, target, shared=True, shadow=False):
    totals={}; calls={}; stack=[]; work={}; regions={}
    def wrap(fn, category):
        def call(*args, **kwargs):
            name=category(args, stack) if callable(category) else category
            calls[name]=calls.get(name,0)+1
            frame=[perf_counter(),0.0]; stack.append((name,frame))
            try:
                result=fn(*args,**kwargs)
                if name=='protected_encoding':
                    work['protected_bytes']=work.get('protected_bytes',0)+len(result)
                    work['maximum_protected_bytes']=max(work.get('maximum_protected_bytes',0),len(result))
                if name=='manifest':
                    work['booking_visits']=work.get('booking_visits',0)+len(args[0]['world_state']['bookings'])
                    work['manifest_booking_rows']=work.get('manifest_booking_rows',0)+len(result.source_booking_ids)
                if name=='completion_chronology':
                    work['result_visits']=work.get('result_visits',0)+len(args[0]['world_state']['flight_results'])
                if name=='kernel_witness':
                    work['event_records_copied']=work.get('event_records_copied',0)+sum(len(args[0]['world_state'][n]) for n in ('pending_events','event_history'))
                return result
            finally:
                elapsed=perf_counter()-frame[0]; stack.pop()
                if name in ('capture_departure','capture_completion','validate_departure','validate_completion'):
                    regions[name]=regions.get(name,0)+elapsed
                totals[name]=totals.get(name,0)+elapsed-frame[1]
                if stack: stack[-1][1][1]+=elapsed
        return call
    def protected(args, frames):
        return 'protected_capture' if any(n.startswith('capture_') for n,_ in frames) else 'protected_compare'
    def exact(args, frames):
        label=args[2]
        if 'allocator' in label or 'simulation' in label: return 'allocator_revision'
        if 'event' in label or 'generated' in label: return 'event_topology'
        if 'aircraft' in label or 'flight' in label: return 'aircraft_reservation'
        if 'journal' in label: return 'journal'
        if 'account' in label or 'finance' in label: return 'finance'
        return 'operation_result'
    def encoding(args, frames):
        return 'protected_encoding' if any(n.startswith('protected_') for n,_ in frames) else 'selected_encoding'
    hooks=[(proof,'_encoded',encoding),(kernel,'_event_contract_witness','kernel_witness'),
        (kernel,'validate_world','full_world_validation'),(kernel,'_clone_runtime_world','clone'),
        (kernel,'_replace_envelope','detached_commit'),
        (proof,'_protected_digest',protected),(proof,'json_compatibility_error','canonical_json'),
        (proof,'_container_alias_error','mutable_alias'),(proof,'_exact',exact),
        (proof,'supports_completion','completion_chronology'),
        (fulfilment,'_build_confirmed_carriage_manifest','manifest'),
        (fulfilment,'completion_cost','cost'),(fulfilment,'settlement_records','settlement')]
    if hasattr(proof,'protected_bytes'):
        hooks.append((proof,'protected_bytes','protected_encoding'))
    hooks += [(proof,n,n) for n in ('capture_departure','capture_completion','validate_departure','validate_completion')]
    world=deepcopy(base)
    with ExitStack() as patches:
        for module,name,category in hooks:
            patches.enter_context(patch.object(module,name,wrap(getattr(module,name),category)))
        initialize_runtime_handlers()
        start=perf_counter()
        request=begin_resolution(world,target,shared=shared,shadow=shadow,max_batch_events=64,max_generated_events=10000)
        steps=[]; batches=[]
        while not request.finished:
            count=request._completed; tick=perf_counter(); request.step(); steps.append(perf_counter()-tick)
            if request._completed>count: batches.append(request._completed-count)
        elapsed=perf_counter()-start
        assert request.result.succeeded,request.result.failure
    initialize_runtime_handlers()
    sizes={k:len(v) for k,v in base['world_state'].items() if type(v) in (dict,list)}
    measured=sum(totals.values())
    return dict(total_seconds=elapsed,exclusive_seconds=totals,calls=calls,unattributed_seconds=elapsed-measured,
        measured_seconds=measured,nonoverlapping_proof_regions=regions,proof_region_seconds=sum(regions.values()),events=request._completed,batches=batches,max_step_seconds=max(steps),
        work=work,collection_sizes=sizes,world_hash=world_digest(world),process_peak_bytes=memory_bytes())


def latency(base, target, mode, repeats):
    initialize_runtime_handlers()
    samples=[]; steps=[]; digest=None; batches=None
    for _ in range(repeats):
        world=deepcopy(base); actual_batches=[]; start=perf_counter()
        request=begin_resolution(world,target,shared=mode!='strict',shadow=mode=='shadow',
            max_batch_events=64,max_generated_events=10000)
        while not request.finished:
            count=request._completed; tick=perf_counter(); request.step(); steps.append(perf_counter()-tick)
            if request._completed>count: actual_batches.append(request._completed-count)
        samples.append(perf_counter()-start)
        assert request.result.succeeded,request.result.failure
        actual=world_digest(world)
        assert digest is None or digest==actual
        assert batches is None or batches==actual_batches
        digest=actual; batches=actual_batches
    return dict(median_seconds=median(samples),samples_seconds=samples,max_step_seconds=max(steps),
        events=request._completed,batches=batches,world_hash=digest,process_peak_bytes=memory_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--case',default='dense-25')
    parser.add_argument('--mode',choices=('strict','shared','shadow'),default='shared')
    parser.add_argument('--latency',action='store_true',help='un-instrumented latency instead of exclusive profiling')
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats<1: parser.error('repeats must be positive')
    names=[args.case] if args.case!='all' else [p.stem for p in sorted(args.fixtures.glob('*.json'))]
    for name in names:
        row=json.loads((args.fixtures/(name+'.json')).read_text(encoding='utf-8'))
        result=(latency(row['world'],row['target'],args.mode,args.repeats) if args.latency
            else profile(row['world'],row['target'],args.mode!='strict',args.mode=='shadow'))
        print(json.dumps(dict(case=name,mode=args.mode,**result)),flush=True)

if __name__=='__main__': main()
