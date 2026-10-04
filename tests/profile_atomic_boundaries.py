"""Stage 3E.1 exclusive production boundaries on caller-owned frozen TEMP worlds."""
import argparse
import gc
from contextlib import ExitStack
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from statistics import median
import tempfile
from time import perf_counter
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel, shared_candidate, candidate_ownership
from game.simulation.handlers import initialize_runtime_handlers
from game.world_state import validation, flight_transition_validation, payment_validation
from game.aircraft_operations import fulfilment, manifest_lookup
from game.world_state.timestamps import parse_canonical_utc, format_utc
from tests.resolution_oracle import world_digest
from tests.profile_ph_runtime import memory_bytes


class ExclusiveProfile:
    """Subtract complete child intervals; do not retain call arguments/results."""
    def __init__(self):
        self.stack=[]; self.seconds={}; self.calls={}; self.inclusive={}; self.gc_parents={}
    def wrap(self, fn, category):
        def call(*args, **kwargs):
            actual = category
            if category == 'whole_world_clone':
                actual = 'commit_clone' if self.stack and self.stack[-1][2] == 'detached_commit' else 'candidate_clone'
            frame=[None,0.0,actual]; self.stack.append(frame)
            frame[0]=perf_counter()
            self.calls[actual]=self.calls.get(actual,0)+1
            try: return fn(*args, **kwargs)
            finally:
                elapsed=perf_counter()-frame[0]; self.stack.pop()
                self.seconds[actual]=self.seconds.get(actual,0)+elapsed-frame[1]
                self.inclusive[actual]=self.inclusive.get(actual,0)+elapsed
                if self.stack: self.stack[-1][1]+=elapsed
        return call


def measure(base,target,*,instrument=False,shadow=False,reference_graphs=False):
    world=deepcopy(base); profile=ExclusiveProfile(); rows=[]
    initialize_runtime_handlers()
    hooks=[(kernel,'validate_world','complete_validation'),
        (validation._Validator,'validate_root','validation_root'),
        (validation,'_plain_authority_tree','validation_graph'),
        (validation,'json_compatibility_error','validation_json'),
        (validation,'_container_alias_error','validation_alias'),
        (validation._Validator,'validate_collections_and_ids','validation_ids'),
        (validation._Validator,'validate_structure','validation_structure'),
        (validation,'validate_schema3_booking_authority','validation_booking'),
        (validation,'validate_schema4_fulfilment_authority','validation_fulfilment'),
        (validation._Validator,'validate_no_name_references_or_float_money','validation_forbidden_fields'),
        (kernel,'_clone_runtime_world','whole_world_clone'),
        (kernel,'_replace_envelope','detached_commit'),
        (kernel,'build_event_queue_index','queue_selection'),
        (kernel,'_apply_handler_candidate','handler_dispatch'),
        (kernel,'_event_contract_witness','event_history_witness'),
        (kernel,'_handler_contract_error','event_history_proof'),
        (kernel,'_complete_target','clock_only'),
        (shared_candidate.SharedResolutionRequest,'step','resolver_bookkeeping'),
        (shared_candidate.SharedResolutionRequest,'_shared_batch','candidate_bookkeeping'),
        (candidate_ownership.CandidateOwnership,'__init__','ownership_setup'),
        (candidate_ownership.CandidateOwnership,'begin','capsule_setup'),
        (candidate_ownership.CandidateOwnership,'publish','capsule_publish'),
        (candidate_ownership.CandidateOwnership,'close','ownership_close'),
        (candidate_ownership.WriteCapsule,'checked_outputs','capsule_outputs'),
        (fulfilment,'_departure','handler'),(fulfilment,'_completion','handler'),
        (fulfilment,'_build_confirmed_carriage_manifest','manifest'),
        (manifest_lookup.CandidateManifestLookup,'__init__','booking_lookup'),
        (manifest_lookup,'_verify_groups','booking_lookup_verification'),
        (manifest_lookup.CandidateManifestLookup,'lookup','booking_lookup_query'),
        (Stage1Session,'_mark_progress','session_notification'),
        (Stage1Session,'maybe_autosave','autosave_eligibility')]
    for module,names in ((flight_transition_validation,('capture_departure','capture_completion','validate_departure','validate_completion')),
                         (payment_validation,('capture_payment_transition','validate_payment_transition'))):
        hooks.extend((module,name,'transition_capture' if name.startswith('capture') else 'transition_proof') for name in names)
    with tempfile.TemporaryDirectory(prefix='at-atomic-') as root, ExitStack() as stack:
        s=Stage1Session(runtime_clock=lambda:0,save_root=root);s.world=world
        s._ensure_runtime();s._bind_owned_reads();s.resume()
        s.runtime.credit_ns=int((parse_canonical_utc(target)-parse_canonical_utc(world['simulation']['time_utc'])).total_seconds())*1_000_000_000
        if reference_graphs:
            from tests.test_atomic_boundary_optimization import legacy_gates
            legacy_gates(stack)
        if shadow:
            from game.simulation import pacing
            from game.simulation.resolver import begin_resolution
            def dispatch(w,t,**options): return begin_resolution(w,t,shadow=True,**options)
            stack.enter_context(patch.object(pacing,'begin_resolution',dispatch))
        if instrument:
            for module,name,category in hooks:
                stack.enter_context(patch.object(module,name,profile.wrap(getattr(module,name),category)))
            initialize_runtime_handlers()
        if instrument:
            gc_started = [None]
            def gc_time(phase, info):
                if phase == 'start':
                    gc_started[0] = perf_counter()
                elif gc_started[0] is not None:
                    elapsed_gc = perf_counter() - gc_started[0]
                    profile.seconds['garbage_collection'] = profile.seconds.get('garbage_collection', 0) + elapsed_gc
                    profile.calls['garbage_collection'] = profile.calls.get('garbage_collection', 0) + 1
                    parent=profile.stack[-1][2] if profile.stack else 'unattributed'
                    profile.gc_parents[parent]=profile.gc_parents.get(parent,0)+elapsed_gc
                    if profile.stack: profile.stack[-1][1] += elapsed_gc
                    gc_started[0] = None
            gc.callbacks.append(gc_time)
            stack.callback(gc.callbacks.remove, gc_time)
        start=perf_counter()
        for _ in range(20000):
            prior=s.runtime.commit_serial; before=len(world['world_state']['event_history']);tick=perf_counter()
            s.pump()
            rows.append(dict(seconds=perf_counter()-tick,events=len(world['world_state']['event_history'])-before,commits=s.runtime.commit_serial-prior))
            if s.runtime.blocked: raise RuntimeError(s.runtime.diagnostic)
            if s.runtime.work is None and s.runtime.credit_ns<1_000_000_000: break
        else: raise RuntimeError('runtime did not complete')
        elapsed=perf_counter()-start
    s.hard_pause()
    initialize_runtime_handlers()
    assert validation.validate_world(world).is_valid
    sizes={k:len(v) for k,v in base['world_state'].items() if type(v) in (dict,list)}
    return dict(total_seconds=elapsed,max_callback_seconds=max(r['seconds'] for r in rows),
        events=sum(r['events'] for r in rows),units=sum(r['commits'] for r in rows),callbacks=rows,
        gc_parent_seconds=profile.gc_parents,exclusive_seconds=profile.seconds,inclusive_regions=profile.inclusive,calls=profile.calls,
        unattributed_seconds=elapsed-sum(profile.seconds.values()),world_hash=world_digest(world),
        collection_sizes=sizes,peak_process_bytes=memory_bytes(),candidate_json_bytes=len(json.dumps(base,separators=(',',':')).encode()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--cases',default='all')
    p.add_argument('--compare',action='store_true',help='Alternate reference/optimized graphs on identical inputs');p.add_argument('--reference-graphs',action='store_true',help='Frozen Stage 3E graph predicates, same complete engine and fixtures');p.add_argument('--instrument',action='store_true');p.add_argument('--shadow',action='store_true');p.add_argument('--repeats',type=int,default=1)
    a=p.parse_args()
    if a.repeats < 1: p.error('--repeats must be positive')
    names=['one-departure','one-completion','round-trip','representative-ten','aged-ten','dense-25','divine-next-departure','divine-short','clock-small','clock-divine'] if a.cases=='all' else a.cases.split(',')
    for name in names:
        source={'clock-small':'one-completion','clock-divine':'divine-next-departure','history-0':'dense-departure','history-1000':'aged-ten'}.get(name,name)
        fixture=json.loads((a.fixtures/(source+'.json')).read_text(encoding='utf-8'))
        if name.startswith('history-'):
            fixture['target']=json.loads((a.fixtures/'aged-ten.json').read_text(encoding='utf-8'))['target']
        if name.startswith('clock-'):
            current=parse_canonical_utc(fixture['world']['simulation']['time_utc'])
            due=min(parse_canonical_utc(e['due_at_utc']) for e in fixture['world']['world_state']['pending_events'].values())
            target=min(current+timedelta(seconds=30),due-timedelta(seconds=1))
            assert target>current,'fixture needs a nonempty event-free gap'
            fixture['target']=format_utc(target)
        modes=(True,False) if a.compare else (a.reference_graphs,)
        collected={mode:[] for mode in modes}
        for _ in range(a.repeats):
            for mode in modes:
                collected[mode].append(measure(fixture['world'],fixture['target'],instrument=a.instrument,shadow=a.shadow,reference_graphs=mode))
        assert len({r['world_hash'] for reports in collected.values() for r in reports})==1
        assert len({tuple((row['events'],row['commits']) for row in r['callbacks']) for reports in collected.values() for r in reports})==1, 'graph optimization changed transaction boundaries'
        for mode,reports in collected.items():
            print(json.dumps(dict(case=name,reference_graphs=mode,median_seconds=median(r['total_seconds'] for r in reports),reports=reports)),flush=True)

if __name__=='__main__': main()
