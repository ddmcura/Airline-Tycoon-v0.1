"""One bounded legacy/closed pair; copy counts, not a speedup benchmark."""
from contextlib import ExitStack
from copy import deepcopy
import json
import tempfile
import sys
from unittest.mock import patch

from app import session as sessions
from game.simulation import kernel
from game.scheduling import quarterly_backend, quarterly_boundary
from tests.test_simulation_resolver import ph_world, published_pair
from tests.measure_hybrid_completion_boundary import peak_working_set


def main():
    if '--quarterly' in sys.argv:
        from tests.test_quarterly_backend import QuarterlyBackendTests
        source = QuarterlyBackendTests.fixture()[0]
    else:
        source = published_pair(ph_world())
    reports = []
    outcomes = []
    with tempfile.TemporaryDirectory() as root:
        for closed in (False, True):
            session = sessions.Stage1Session(closed_owner=closed, save_root=root, runtime_clock=lambda:0)
            session.world = deepcopy(source) if not closed else source
            session.fleet()
            counts = dict(event_candidate_commit_clones=0, backend_world_copies=0,
                          publication_world_copies=0, full_validations=0)
            def instrument(module, name, label, stack):
                original = getattr(module, name)
                def invoke(*args, **kwargs):
                    if name != 'deepcopy' or (type(args[0]) is dict and 'simulation' in args[0] and 'world_state' in args[0]):
                        counts[label] += 1
                    return original(*args, **kwargs)
                stack.enter_context(patch.object(module, name, invoke))
            before = peak_working_set()
            with ExitStack() as stack:
                for module, name, label in (
                    (kernel, '_clone_runtime_world', 'event_candidate_commit_clones'),
                    (quarterly_backend, 'deepcopy', 'backend_world_copies'),
                    (quarterly_boundary, 'deepcopy', 'publication_world_copies'),
                    (kernel, 'validate_world', 'full_validations'),
                    (sessions, 'validate_world', 'full_validations'),
                    (quarterly_backend, 'validate_world', 'full_validations'),
                    (quarterly_boundary, 'validate_world', 'full_validations')):
                    instrument(module, name, label, stack)
                results = [session.advance_next_event(), session.advance_next_event()]
                session.header(); session.fleet(); session.runtime_view()
            reports.append(dict(closed_owner=closed, counts=counts,
                ownership_before_diagnostic_export=session.ownership_counts(),
                lifetime_peak_before=before, lifetime_peak_after=peak_working_set()))
            outcomes.append((results, session.authoritative_bytes()))
            reports[-1]['ownership_after_diagnostic_export'] = session.ownership_counts()
            session.close()
    assert outcomes[0] == outcomes[1]
    print(json.dumps(dict(pairs=reports, complete_world_and_results_equal=True,
        note='Two real scheduled events and selected reads; lifetime peaks include setup and both modes. No speedup claim.'), indent=2))


if __name__ == '__main__': main()
