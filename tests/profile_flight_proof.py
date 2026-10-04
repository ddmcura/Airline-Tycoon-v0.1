"""Exclusive Stage 3D proof profile, frozen TEMP fixtures, no mock argument retention."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import json
import sys
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
    def count_containers(value, private=False):
        from collections.abc import Mapping, Sequence
        pending=[value]; containers=entries=0
        while pending:
            item=pending.pop()
            if isinstance(item,Mapping): values=item.values()
            elif isinstance(item,(list,tuple)): values=item
            elif private and isinstance(item,Sequence) and not isinstance(item,(str,bytes)): values=item
            else: continue
            containers+=1; entries+=len(item)
            pending.extend(v for v in values if isinstance(v,Mapping) or isinstance(v,(list,tuple))
                           or (private and isinstance(v,Sequence) and not isinstance(v,(str,bytes))))
        return containers,entries

    def wrap(fn, category):
        def call(*args, **kwargs):
            name=category(args, stack) if callable(category) else category
            calls[name]=calls.get(name,0)+1
            frame=[perf_counter(),0.0]; stack.append((name,frame))
            try:
                if name=='lookup_close':
                    diagnostic=perf_counter(); lookup=args[0]; groups=lookup._groups
                    ids=sum(len(v) for v in groups.values())
                    own_bytes=sum(map(sys.getsizeof,(lookup,vars(lookup),lookup._sources,lookup._sizes,groups,dict(groups))))+sum(sys.getsizeof(v) for v in groups.values())
                    work['maximum_lookup_bytes']=max(work.get('maximum_lookup_bytes',0),own_bytes)
                    work['maximum_lookup_groups']=max(work.get('maximum_lookup_groups',0),len(groups))
                    work['maximum_lookup_ids']=max(work.get('maximum_lookup_ids',0),ids)
                    elapsed=perf_counter()-diagnostic
                    totals['diagnostic_measurement']=totals.get('diagnostic_measurement',0)+elapsed
                    calls['diagnostic_measurement']=calls.get('diagnostic_measurement',0)+1
                    frame[1]+=elapsed
                if name=='lookup_build':
                    work['booking_build_visits']=work.get('booking_build_visits',0)+len(args[1]['world_state']['bookings'])
                if name=='lookup_verify':
                    work['booking_verification_visits']=work.get('booking_verification_visits',0)+len(args[0]['bookings'])
                if name=='ownership_close':
                    diagnostic=perf_counter(); memo=args[0]._views
                    own_bytes=sys.getsizeof(memo)
                    for marker,(source,view) in memo.items():
                        access=view._access; cells=access.__closure__ or ()
                        own_bytes+=sum(map(sys.getsizeof,(marker,(source,view),view,access,cells)))+sum(map(sys.getsizeof,cells))
                    work['maximum_private_memo_bytes']=max(work.get('maximum_private_memo_bytes',0),own_bytes)
                    work['maximum_private_containers']=max(work.get('maximum_private_containers',0),len(memo))
                    elapsed=perf_counter()-diagnostic
                    totals['diagnostic_measurement']=totals.get('diagnostic_measurement',0)+elapsed
                    calls['diagnostic_measurement']=calls.get('diagnostic_measurement',0)+1
                    frame[1]+=elapsed
                result=fn(*args,**kwargs)
                if name=='protected_encoding':
                    work['protected_bytes']=work.get('protected_bytes',0)+len(result)
                    work['maximum_protected_bytes']=max(work.get('maximum_protected_bytes',0),len(result))
                if name=='manifest':
                    ids=kwargs.get('booking_ids')
                    visits=len(args[0]['world_state']['bookings']) if ids is None else len(ids)
                    work['booking_visits']=work.get('booking_visits',0)+visits
                    key='canonical_booking_visits' if ids is None else 'indexed_booking_visits'
                    work[key]=work.get(key,0)+visits
                    work['manifest_booking_rows']=work.get('manifest_booking_rows',0)+len(result.source_booking_ids)
                if name=='lookup_query':
                    work['lookup_ids_returned']=work.get('lookup_ids_returned',0)+len(result)
                if name=='completion_chronology':
                    work['result_visits']=work.get('result_visits',0)+len(args[0]['world_state']['flight_results'])
                if name=='kernel_witness':
                    work['event_records_copied']=work.get('event_records_copied',0)+sum(len(args[0]['world_state'][n]) for n in ('pending_events','event_history'))
                if name=='ownership_publish' and hasattr(args[0],'_views'):
                    work['maximum_private_containers']=max(work.get('maximum_private_containers',0),len(args[0]._views))
                if name in ('ownership_baseline','mutable_alias'):
                    diagnostic=perf_counter()
                    if name=='ownership_baseline':
                        containers=len(args[0]._views) if hasattr(args[0],'_views') else 0
                        entries=containers
                    else: containers,entries=count_containers(args[0])
                    if name=='ownership_baseline':
                        work['maximum_private_containers']=max(work.get('maximum_private_containers',0),containers)
                        pass  # Entry creates one lazy root; publish/close report actual memo sizes.
                    else:
                        work['alias_container_visits']=work.get('alias_container_visits',0)+containers
                    elapsed=perf_counter()-diagnostic
                    totals['diagnostic_measurement']=totals.get('diagnostic_measurement',0)+elapsed
                    calls['diagnostic_measurement']=calls.get('diagnostic_measurement',0)+1
                    frame[1]+=elapsed
                return result
            finally:
                elapsed=perf_counter()-frame[0]; stack.pop()
                if name in ('capture_departure','capture_completion','validate_departure','validate_completion',
                            'ownership_baseline','ownership_begin','ownership_publish','ownership_close'):
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
    try:
        from game.simulation import candidate_ownership as ownership
    except ImportError:
        ownership=None
    if ownership is not None:
        hooks.extend([(ownership.CandidateOwnership,'__init__','ownership_baseline'),
                      (ownership.CandidateOwnership,'begin','ownership_begin'),
                      (ownership.CandidateOwnership,'publish','ownership_publish'),
                      (ownership.CandidateOwnership,'close','ownership_close'),
                      (ownership.WriteCapsule,'checked_outputs','ownership_boundary'),
                      (ownership,'json_compatibility_error','canonical_json'),
                      (ownership,'mutable_alias_error','mutable_alias')])
    try:
        from game.aircraft_operations import manifest_lookup
    except ImportError:
        manifest_lookup=None
    if manifest_lookup is not None:
        hooks.extend([(manifest_lookup.CandidateManifestLookup,'__init__','lookup_build'),
                      (manifest_lookup,'_verify_groups','lookup_verify'),
                      (manifest_lookup.CandidateManifestLookup,'lookup','lookup_query'),
                      (manifest_lookup.CandidateManifestLookup,'close','lookup_close')])
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
        measured_seconds=measured,nonoverlapping_proof_regions=regions,proof_region_seconds=sum(regions[n] for n in regions if n.startswith(('capture_','validate_'))),
        ownership_plus_proof_seconds=sum(regions.values()),
        diagnostic_adjusted_ownership_proof_seconds=sum(regions.values())-totals.get('diagnostic_measurement',0),
        events=request._completed,batches=batches,max_step_seconds=max(steps),
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
