"""Opt-in Phase 2B paired measurement on the retained Phase 1 source.

Artifacts require a fresh external TEMP root. The supervisor kills a worker at
the hard deadline, discards its private state and starts no further experiment.
Baseline forces the unchanged public reconciliation transaction at every entry.
"""
import argparse
from contextlib import ExitStack
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

from tests import benchmark_quarterly_catchup as catchup
from tests import benchmark_quarterly_runtime as benchmark
# Preload both lazy reconciliation modules before taking the alias snapshot.
from game.scheduling import quarterly_backend, quarterly_boundary as publication
from game.world_state import serialization, validation
from game.world_state.timestamps import parse_canonical_utc, format_utc

SOURCE_HASH = 'ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0'


def count_operations(stack, mode):
    """Count imported aliases; never patch recursive copy internals or handlers."""
    counts = {}
    seconds = {}
    targets = ((deepcopy, 'deepcopy'),
        (serialization._clone_runtime_world, 'runtime_clone'),
        (validation.validate_world, 'full_validation'))
    def timed(fn, label):
        def call(*args, **kwargs):
            # Partial witness/result copies are deliberately not whole worlds.
            if label.endswith(':deepcopy') and not (args and type(args[0]) is dict
                    and 'world_state' in args[0] and 'simulation' in args[0]):
                return fn(*args, **kwargs)
            counts[label] = counts.get(label, 0) + 1
            started = perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                seconds[label] = seconds.get(label, 0) + perf_counter() - started
        return call
    aliases = [(module, name, original, category)
        for module in tuple(sys.modules.values())
        if getattr(module, '__name__', '').startswith(('game.', 'app.'))
        for name, value in tuple(vars(module).items())
        for original, category in targets if value is original]
    for module, name, original, category in aliases:
        stack.enter_context(patch.object(module, name,
            timed(original, module.__name__ + ':' + category)))
    predicate = (lambda world: True) if mode == 'baseline' else publication._publication_reconciliation_needed
    stack.enter_context(patch.object(publication, '_publication_reconciliation_needed',
        timed(predicate, 'publication_predicate')))
    return counts, seconds


def worker(args):
    root = catchup.safe_root(args.root)
    base = json.loads(args.source.read_text(encoding='utf-8'))
    benchmark.valid(base)
    assert benchmark.digest(base) == SOURCE_HASH
    result = dict(mode=args.worker, source_hash=SOURCE_HASH,
        python=platform.python_version(), platform=platform.platform(), windows=[])
    output = root / (args.worker + '.json')
    def persist():
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='at-publication-noop-save-') as saves:
        session = benchmark.session_for(base, saves)
        try:
            for day in range(1, args.days + 1):
                target = format_utc(parse_canonical_utc(catchup.OPERATING_START) + timedelta(days=day))
                with ExitStack() as stack:
                    counts, seconds = count_operations(stack, args.worker)
                    row = catchup.measure(session, target, 150)
                row.update(calls=counts, inclusive_s=seconds, audit=benchmark.audit(session.world))
                result['windows'].append(row)
                persist()
                print(json.dumps(dict(mode=args.worker, day=day, elapsed_s=row['elapsed_s'],
                    events=row['events'], status=row['status'])), flush=True)
                if row['status'] != 'COMPLETED':
                    return
            result['checks'] = catchup.correctness(session.world)
            before = benchmark.digest(session.world)
            started = perf_counter()
            session.save_manual()
            result['save_s'] = perf_counter() - started
            started = perf_counter()
            session.load_saved(session.career_id)
            result['load_s'] = perf_counter() - started
            result['save_load_exact_paused'] = (benchmark.digest(session.world) == before
                and session.world['simulation']['clock_state'] == 'PAUSED')
            assert result['save_load_exact_paused']
            result['source_unchanged'] = benchmark.digest(base) == SOURCE_HASH
            assert result['source_unchanged']
            result['peak_process_bytes'] = benchmark.memory_bytes()
            persist()
        finally:
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--deadline-seconds', type=float, default=480)
    parser.add_argument('--days', type=int, choices=(1, 2), default=1)
    parser.add_argument('--worker', choices=('baseline', 'candidate'))
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    root = catchup.safe_root(args.root)
    root.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    deadline = started + args.deadline_seconds
    summary = dict(deadline_s=args.deadline_seconds, workers=[])
    for mode in ('baseline', 'candidate'):
        remaining = deadline - perf_counter()
        if remaining <= 0:
            break
        command = [sys.executable, '-B', '-m', 'tests.benchmark_publication_reconciliation',
            '--source', str(args.source), '--root', str(root), '--worker', mode,
            '--days', str(args.days)]
        with (root / (mode + '.log')).open('w', encoding='utf-8') as log:
            worker_start = perf_counter()
            try:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                    timeout=min(220, remaining), check=False)
                status = dict(mode=mode, exit_code=process.returncode)
            except subprocess.TimeoutExpired:
                status = dict(mode=mode, hard_timeout=True)
        status['worker_wall_s'] = perf_counter() - worker_start
        summary['workers'].append(status)
        summary['total_wall_s'] = perf_counter() - started
        (root / 'supervisor.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(status), flush=True)
        if status.get('hard_timeout') or status.get('exit_code'):
            break
    if len(summary['workers']) == 2 and all(w.get('exit_code') == 0 for w in summary['workers']):
        baseline = json.loads((root / 'baseline.json').read_text(encoding='utf-8'))
        candidate = json.loads((root / 'candidate.json').read_text(encoding='utf-8'))
        assert len(baseline['windows']) == len(candidate['windows']) == args.days
        for left, right in zip(baseline['windows'], candidate['windows']):
            assert left['status'] == right['status'] == 'COMPLETED'
            assert left['audit'] == right['audit']
            assert left['event_types'] == right['event_types']
        print('Complete-world paired equality: PASS', flush=True)


if __name__ == '__main__':
    main()
