"""Bounded production-pilot pairs. --retained reuses a supplied existing fixture."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from app import session as sessions
from game.simulation import kernel, owned_event
from game.aircraft_operations import scoped_completion
from game.scheduling import quarterly_backend, quarterly_boundary
from game.world_state.flight_proof_witness import protected_bytes
from tests import test_scoped_completion_experiment as fixtures
from tests.test_simulation_resolver import ph_world, published_pair
from tests.measure_hybrid_completion_boundary import peak_working_set
from tests.benchmark_quarterly_runtime import digest


def run_pair(source, label):
    source_hash=digest(source); reports=[]; outcomes=[]
    with tempfile.TemporaryDirectory() as root:
        for enabled in (False,True):
            session=sessions.Stage1Session(closed_owner=True,scoped_completion=enabled,
                runtime_clock=lambda:0,save_root=root)
            session.world=source; session.fleet()
            counts=dict(candidate_world_clones=0,commit_world_clones=0,other_kernel_world_clones=0,
                backend_world_copies=0,publication_world_copies=0,full_validations=0)
            event_seconds=[0.0]
            def hook(module,name,label,stack):
                original=getattr(module,name)
                def measured(*args,**kwargs):
                    key=label
                    if name=='_clone_runtime_world':
                        caller=sys._getframe(1).f_code.co_name
                        key=('candidate_world_clones' if caller=='_execute_event' else
                             'commit_world_clones' if caller=='_replace_envelope' else 'other_kernel_world_clones')
                    if name!='deepcopy' or (type(args[0]) is dict and 'world_state' in args[0] and 'simulation' in args[0]):
                        if key is not None: counts[key]+=1
                    start=time.perf_counter()
                    try: return original(*args,**kwargs)
                    finally:
                        if name=='_execute_event': event_seconds[0]+=time.perf_counter()-start
                stack.enter_context(patch.object(module,name,measured))
            before=peak_working_set()
            with ExitStack() as stack:
                for module,name,key in (
                    (kernel,'_clone_runtime_world','other_kernel_world_clones'),
                    (kernel,'_execute_event',None),
                    (quarterly_backend,'deepcopy','backend_world_copies'),
                    (quarterly_boundary,'deepcopy','publication_world_copies'),
                    (kernel,'validate_world','full_validations'),
                    (scoped_completion,'validate_world','full_validations'),
                    (owned_event,'validate_world','full_validations'),
                    (quarterly_backend,'validate_world','full_validations'),
                    (quarterly_boundary,'validate_world','full_validations'),
                    (sessions,'validate_world','full_validations')):
                    hook(module,name,key,stack)
                start=time.perf_counter(); result=session.advance_next_event()
                advancement_seconds=time.perf_counter()-start
                session.header(); session.fleet(); session.runtime_view()
                command_seconds=time.perf_counter()-start
            assert result.result.succeeded,result.result.failure
            diagnostics=session.scoped_completion_status()
            ownership=session.ownership_counts()
            reports.append(dict(scoped_completion=enabled,counts=counts,
                advancement_seconds=advancement_seconds,command_with_selected_reads_seconds=command_seconds,
                event_seconds=event_seconds[0],pilot=diagnostics,ownership_before_oracle_exports=ownership,
                lifetime_peak_before=before,lifetime_peak_after=peak_working_set()))
            typed=hashlib.sha256(protected_bytes(session._world)).hexdigest()
            canonical=hashlib.sha256(session.authoritative_bytes()).hexdigest()
            outcomes.append((typed,canonical,result))
            reports[-1]['canonical_world_sha256']=canonical
            session.close(); del session; gc.collect()
    assert outcomes[0]==outcomes[1],label+' complete-world/result mismatch'
    assert digest(source)==source_hash,'input fixture mutated'
    return dict(fixture=label,bookings=len(source['world_state']['bookings']),source_sha256=source_hash,
        modes=reports,complete_typed_world_canonical_bytes_and_reports_equal=True,
        note='One instrumented control-then-pilot pair. Initial owner acquisition/read gate and explicit typed/canonical oracle exports are outside timing. Lifetime memory peaks include setup and both modes; no speedup claim.')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--retained',type=Path)
    args=parser.parse_args()
    if args.retained:
        from game.simulation.handlers import initialize_runtime_handlers
        initialize_runtime_handlers()
        source=json.loads(args.retained.read_text(encoding='utf-8'))
        original_hash=digest(source); prefix=[]; start=time.perf_counter()
        # Keep ONE existing strict request: repeated Next Event commands repeat
        # entry reconciliation on an equal-UTC dispatch/departure frontier.
        # Stop before Completion; the one-day horizon is never drained/benchmarked.
        from datetime import timedelta
        from game.simulation.resolver import begin_resolution
        from game.world_state.timestamps import parse_canonical_utc,format_utc
        horizon=format_utc(parse_canonical_utc(source['simulation']['time_utc'])+timedelta(days=1))
        request=begin_resolution(source,horizon)
        try:
            for step in range(7):
                event=min(source['world_state']['pending_events'].values(),key=kernel._event_key)
                if event['event_type']=='STAGE1_FLIGHT_COMPLETION': break
                if step==6: raise RuntimeError('No Completion within six retained-request setup events: '+str(prefix))
                progress=request.step()
                assert not progress.finished,progress.processing_result
                prefix.append(source['world_state']['event_history'][progress.event_id]['event_type'])
        finally: request.close()
        report=run_pair(source,'retained-existing')
        report.update(original_retained_sha256=original_hash,setup_prefix_types=prefix,
                      retained_setup_and_pair_seconds=time.perf_counter()-start)
        print(json.dumps(report,indent=2))
    else:
        fixtures.ScopedCompletionTests.setUpClass()
        reports=[run_pair(published_pair(ph_world()),'ordinary-unsupported'),
                 run_pair(fixtures.ScopedCompletionTests.source,'quarterly-completion')]
        print(json.dumps(reports,indent=2))


if __name__=='__main__': main()
