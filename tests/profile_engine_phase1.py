"""Removable Phase 1 diagnostic; no production changes or alternate algorithms.

Run with --source <retained operating JSON> --root <new TEMP directory>.
The supervisor kills each worker at the shared hard wall deadline, including
inside atomic events. Killed worker state is discarded, never saved or resumed.
"""
import argparse
from contextlib import ExitStack
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
from tests.profile_atomic_boundaries import ExclusiveProfile
from tests.profile_quarterly_advancement import hooks
from game.world_state.timestamps import parse_canonical_utc, format_utc
# Preload the lazy reconciliation module so future runs capture its aliases.
# The first recorded shared window predates this preload; its gap is reported.
from game.scheduling import quarterly_boundary


class Profile(ExclusiveProfile):
    def wrap(self, fn, category):
        if category not in ('deepcopy', 'world_clone'):
            return super().wrap(fn, category)
        def call(*args, **kwargs):
            actual = category
            if category == 'deepcopy':
                world = args[0] if args else None
                actual = ('whole_world_deepcopy' if type(world) is dict
                    and 'world_state' in world and 'simulation' in world else 'partial_deepcopy')
            elif self.stack and self.stack[-1][2] == 'detached_commit':
                actual = 'commit_clone'
            return super(Profile, self).wrap(fn, actual)(*args, **kwargs)
        return call


def extra_hooks(profile, stack):
    from game.booking import checkpoint
    from game.demand import activation, model, model4
    from game.simulation import kernel, resolver, shared_candidate
    targets = [
        (checkpoint.prepare_daily_booking_checkpoint, 'booking_preparation'),
        (checkpoint.process_daily_booking_checkpoint, 'booking_processing_persistence'),
        (activation.discover_active_market_ids, 'demand_discovery'),
        (model.resolve_active_daily_cohorts, 'demand_resolution'),
        (model4.resolve_model4_active_daily_cohorts, 'model4_resolution'),
        (kernel._execute_event, 'strict_event'),
        (shared_candidate._shared_transition, 'shared_transition'),
        (quarterly_boundary.reconcile, 'publication_reconciliation'),
    ]
    aliases = [(module, name, original, category)
        for module in tuple(sys.modules.values())
        if getattr(module, '__name__', '').startswith(('game.', 'app.'))
        for name, value in tuple(vars(module).items())
        for original, category in targets if value is original]
    for module, name, original, category in aliases:
        stack.enter_context(patch.object(module, name, profile.wrap(original, category)))
    for owner, name, category in (
        (resolver.ResolutionRequest, 'step', 'strict_resolver_step'),
        (shared_candidate.SharedResolutionRequest, 'step', 'shared_resolver_step'),
        (shared_candidate.SharedResolutionRequest, '_shared_batch', 'shared_batch'),
        (shared_candidate.SharedResolutionRequest, '_strict_one', 'shared_strict_fence')):
        stack.enter_context(patch.object(owner, name, profile.wrap(getattr(owner, name), category)))


def totals(world):
    state = world['world_state']
    return dict(bookings=len(state['bookings']),
        booked_passengers=sum(b['passenger_count'] for b in state['bookings'].values()),
        booking_fares_minor=sum(b['total_fare_minor'] for b in state['bookings'].values()),
        accounts={key: row['balance_minor'] for key, row in state['financial_accounts'].items()},
        events=len(state['event_history']), transactions=len(state['transactions']))


def worker(args):
    root = catchup.safe_root(args.root)
    base = json.loads(args.source.read_text(encoding='utf-8'))
    benchmark.valid(base)
    source_hash = benchmark.digest(base)
    assert source_hash == 'ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0'
    result = dict(mode=args.worker, source_hash=source_hash, initial=totals(base),
        python=platform.python_version(), platform=platform.platform(), windows=[])
    output = root / (args.worker + '.json')
    def persist():
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='at-phase1-saves-') as saves:
        session = benchmark.session_for(base, saves)
        try:
            for day in range(1, 2 if args.worker == 'strict' else 3):
                target = format_utc(parse_canonical_utc(catchup.OPERATING_START) + timedelta(days=day))
                profile = Profile()
                with ExitStack() as stack:
                    if args.worker != 'baseline':
                        hooks(profile, stack)
                        extra_hooks(profile, stack)
                    if args.worker == 'strict':
                        original = catchup.begin_resolution
                        def strict(world, target, **options):
                            options['shared'] = False
                            return original(world, target, **options)
                        stack.enter_context(patch.object(catchup, 'begin_resolution', strict))
                    row = catchup.measure(session, target, 150)
                row.update(day=day, calls=profile.calls, inclusive_s=profile.inclusive,
                    exclusive_s=profile.seconds, totals=totals(session.world),
                    hash=benchmark.digest(session.world))
                result['windows'].append(row)
                persist()
                print(json.dumps(dict(mode=args.worker, day=day, elapsed_s=row['elapsed_s'],
                    status=row['status'], events=row['events'])), flush=True)
                if row['status'] != 'COMPLETED':
                    break
            start = perf_counter()
            result['checks'] = catchup.correctness(session.world)
            result['audit_s'] = perf_counter() - start
            result['source_unchanged'] = benchmark.digest(base) == source_hash
            persist()
            if args.worker == 'instrumented':
                before = benchmark.digest(session.world)
                start = perf_counter()
                session.save_manual()
                save_s = perf_counter() - start
                start = perf_counter()
                session.load_saved(session.career_id)
                load_s = perf_counter() - start
                result['save_load'] = dict(save_s=save_s, load_s=load_s,
                    exact=benchmark.digest(session.world) == before,
                    paused=session.world['simulation']['clock_state'] == 'PAUSED')
                assert result['save_load']['exact'] and result['save_load']['paused']
            result['peak_process_bytes_including_audits'] = benchmark.memory_bytes()
            persist()
        finally:
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--deadline-seconds', type=float, default=600)
    parser.add_argument('--worker', choices=('baseline', 'instrumented', 'strict'))
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    root = catchup.safe_root(args.root)
    root.mkdir(parents=True, exist_ok=False)
    deadline = perf_counter() + args.deadline_seconds
    summary = dict(hard_deadline_s=args.deadline_seconds, workers=[])
    for mode, cap in (('baseline', 180), ('instrumented', 240), ('strict', 180)):
        remaining = deadline - perf_counter()
        if remaining < 30:
            break
        command = [sys.executable, '-B', '-m', 'tests.profile_engine_phase1',
            '--source', str(args.source), '--root', str(root), '--worker', mode]
        start = perf_counter()
        with (root / (mode + '.log')).open('w', encoding='utf-8') as log:
            try:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                    timeout=min(cap, remaining), check=False)
                status = dict(mode=mode, exit_code=process.returncode)
            except subprocess.TimeoutExpired:
                status = dict(mode=mode, hard_timeout=True)
        status['worker_wall_s'] = perf_counter() - start
        summary['workers'].append(status)
        (root / 'supervisor.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(status), flush=True)
        if status.get('hard_timeout') or status.get('exit_code'):
            break


if __name__ == '__main__':
    main()
