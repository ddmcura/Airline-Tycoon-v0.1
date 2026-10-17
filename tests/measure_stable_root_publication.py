"""One small Phase 3F accounting run; no performance/speedup claim."""
from contextlib import ExitStack
from copy import deepcopy
import json
import sys
import tempfile
import time
from unittest.mock import patch

from app import session as session_module
from app.session import Stage1Session
from game.simulation import kernel
from game.scheduling import quarterly_backend, quarterly_boundary
from game.world_state.flight_proof_witness import protected_bytes
from tests import scoped_completion_experiment as scoped
from tests.stable_root_publication_experiment import StableRootBridge
from tests import test_scoped_completion_experiment as fixtures
from tests.measure_hybrid_completion_boundary import peak_working_set


def main():
    fixtures.ScopedCompletionTests.setUpClass()
    source = fixtures.ScopedCompletionTests.source
    expected = deepcopy(source)
    strict = kernel.process_next_event(expected)
    with tempfile.TemporaryDirectory() as root:
        session = Stage1Session(closed_owner=True, save_root=root, runtime_clock=lambda:0)
        session.world = source
        session.fleet()  # Initial read acquisition outside the measured command.
        bridge = StableRootBridge(session)
        identity = id(session._world)
        counts = dict(event_candidate_clones=0, detached_commit_clones=0,
            other_kernel_world_clones=0, experiment_owner_or_export_clones=0,
            backend_world_copies=0, publication_reconciliation_world_copies=0,
            full_validation_calls=0)
        def wrap(module, name, label, stack):
            original = getattr(module, name)
            def counted(*args, **kwargs):
                key = label
                if module is kernel and name == '_clone_runtime_world':
                    caller = sys._getframe(1).f_code.co_name
                    key = ('event_candidate_clones' if caller == '_execute_event' else
                           'detached_commit_clones' if caller == '_replace_envelope' else
                           'other_kernel_world_clones')
                if name != 'deepcopy' or (type(args[0]) is dict and 'world_state' in args[0] and 'simulation' in args[0]):
                    counts[key] += 1
                return original(*args, **kwargs)
            stack.enter_context(patch.object(module, name, counted))
        peak_before = peak_working_set()
        with ExitStack() as stack:
            for module, name, label in (
                (kernel,'_clone_runtime_world','other_kernel_world_clones'),
                (scoped,'_clone_runtime_world','experiment_owner_or_export_clones'),
                (quarterly_backend,'deepcopy','backend_world_copies'),
                (quarterly_boundary,'deepcopy','publication_reconciliation_world_copies'),
                (kernel,'validate_world','full_validation_calls'),
                (scoped,'validate_world','full_validation_calls'),
                (session_module,'validate_world','full_validation_calls'),
                (quarterly_backend,'validate_world','full_validation_calls'),
                (quarterly_boundary,'validate_world','full_validation_calls')):
                wrap(module,name,label,stack)
            start = time.perf_counter()
            prepared = bridge.prepare()
            preparation_seconds = time.perf_counter() - start
            before_installation = dict(counts)
            start = time.perf_counter()
            receipt = bridge.publish(prepared)
            publication_seconds = time.perf_counter() - start
            session.header(); session.fleet(); session.runtime_view()
        assert receipt.committed and receipt.attempt.processing_result == strict
        assert identity == id(session._world)
        assert session.ownership_counts() == dict(acquisitions=1, acquisition_clones=1, full_world_exports=0)
        assert protected_bytes(session._world) == protected_bytes(expected)
        print(json.dumps(dict(bookings=len(source['world_state']['bookings']),
            preparation_seconds=preparation_seconds, publication_seconds=publication_seconds,
            whole_command_counts=counts,
            publication_and_selected_reads_counts={key: counts[key]-before_installation[key] for key in counts},
            bridge_counts=bridge.counts, scoped_counts=bridge._proof_owner.counts,
            session_ownership_counts=session.ownership_counts(),
            lifetime_peak_before=peak_before, lifetime_peak_after=peak_working_set(),
            harness_complete_world_serializations_outside_timer=2,
            exact_world_and_processing_result_equal=True, stable_outer_identity=True,
            note='One small instrumented sample. Constructor acquisition, control clone/execution and complete oracle serializations are outside timing. Lifetime peaks include setup/control; no speedup or memory reduction claim.'),indent=2))


if __name__ == '__main__': main()
