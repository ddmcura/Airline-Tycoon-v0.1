"""Opt-in ONE small paired command measurement, after correctness tests pass.

No warmup rebuild of large histories, loops, fleet benchmark, or production hook.
Run with python -B -m tests.measure_scoped_completion_experiment.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
import time
from unittest.mock import patch

from game.simulation import kernel
from game.scheduling import quarterly_backend, quarterly_boundary
from tests import scoped_completion_experiment as experiment
from tests.test_scoped_completion_experiment import ScopedCompletionTests
from tests.resolution_oracle import canonical_world
from tests.measure_hybrid_completion_boundary import peak_working_set


def measured(call):
    counts = dict(kernel_world_clones=0, owner_or_export_world_clones=0,
                  backend_world_copies=0, publication_world_copies=0,
                  full_validations=0)
    validation_seconds = [0.0]
    def count(module, name, label, stack):
        original = getattr(module, name)
        def invoke(*args, **kwargs):
            counts[label] += 1
            started = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                if label == 'full_validations':
                    validation_seconds[0] += time.perf_counter() - started
        stack.enter_context(patch.object(module, name, invoke))
    before_peak = peak_working_set()
    with ExitStack() as stack:
        for module, name, label in (
            (kernel, '_clone_runtime_world', 'kernel_world_clones'),
            (experiment, '_clone_runtime_world', 'owner_or_export_world_clones'),
            (quarterly_backend, 'deepcopy', 'backend_world_copies'),
            (quarterly_boundary, 'deepcopy', 'publication_world_copies'),
            (kernel, 'validate_world', 'full_validations'),
            (experiment, 'validate_world', 'full_validations'),
            (quarterly_backend, 'validate_world', 'full_validations'),
            (quarterly_boundary, 'validate_world', 'full_validations')):
            count(module, name, label, stack)
        started = time.perf_counter()
        result = call()
        seconds = time.perf_counter() - started
    return result, dict(seconds=seconds, counts=counts,
        validation_seconds_inclusive=validation_seconds[0],
        process_lifetime_peak_before=before_peak,
        process_lifetime_peak_after=peak_working_set())


def main():
    ScopedCompletionTests.setUpClass()
    source = ScopedCompletionTests.source
    strict = deepcopy(source)  # equivalent harness input setup outside timers
    started = time.perf_counter()
    owner = experiment.ScopedCompletionOwner(source)
    ownership_seconds = time.perf_counter() - started
    try:
        strict_result, strict_report = measured(lambda: kernel.process_next_event(strict))
        attempt, scoped_report = measured(owner.complete)
        assert strict_result.succeeded and attempt.admitted
        assert attempt.processing_result == strict_result
        actual = owner.snapshot()  # explicit complete export, outside command timer
        assert canonical_world(actual) == canonical_world(strict)
        existing = [source['world_state'][name][key] for name,key in attempt.copied_records]
        report = dict(scope='one small instrumented strict-then-scoped pair; NOT a speedup estimate',
            bookings=len(source['world_state']['bookings']),
            ownership_setup_seconds=ownership_seconds,
            strict=strict_report, scoped=scoped_report,
            scoped_owner_counts=owner.counts,
            copied_existing_records=[list(row) for row in attempt.copied_records],
            copied_existing_record_json_bytes=len(json.dumps(existing).encode('utf-8')),
            note='JSON bytes are a payload proxy, not allocated memory; simulation/allocator and read projections are additional copies. Peaks include setup and both paths.',
            complete_world_equivalent=True)
        print(json.dumps(report, indent=2))
    finally:
        owner.close()


if __name__ == '__main__':
    main()
