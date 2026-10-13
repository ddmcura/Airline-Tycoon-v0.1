"""Opt-in B2.1/B2.4 profiling of the B2 operating fixture and session API.

Use --root with the temporary directory built by benchmark_quarterly_runtime.
Instrumentation is diagnostic; quiet repetitions establish command latency.
"""
import argparse
import ast
from contextlib import ExitStack
from datetime import timedelta
import cProfile
import gc
import json
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

from tests import benchmark_quarterly_runtime as benchmark
from tests.profile_atomic_boundaries import ExclusiveProfile
from game.world_state import validation, serialization, booking_validation
from game.world_state import booking_lineage_validation
from game.simulation import kernel
from game.booking import allocation, shopping
from game.scheduling import quarterly_backend, quarterly_supply


def hooks(profile, stack):
    """Patch existing aliases, never handler registrations or recursive deepcopy."""
    from copy import deepcopy
    from game.booking import indexes as booking_indexes
    from game.aircraft_operations import fulfilment
    from game.world_state import fulfilment_validation, quarterly_consumers
    targets = [
        (validation.validate_world, 'world_validation'),
        (serialization._clone_runtime_world, 'world_clone'),
        (deepcopy, 'deepcopy'),
        (booking_validation._validate_booking_relationships_detailed, 'booking_relationships'),
        (booking_lineage_validation.valid_booking_relationships, 'booking_graph_proof'),
        (booking_lineage_validation._itinerary_graph, 'itinerary_graph'),
        (booking_validation.validate_schema3_booking_authority, 'booking_validation'),
        (booking_indexes.rebuild_booking_indexes, 'booking_indexes'),
        (fulfilment.build_confirmed_carriage_manifest, 'manifest'),
        (fulfilment_validation._validate_schema4_fulfilment_authority, 'fulfilment_validation'),
        (quarterly_consumers.validate_mode, 'quarterly_consumer_validation'),
        (validation._plain_authority_tree, 'authority_graph'),
        (allocation.prepare_daily_booking_allocation, 'booking_allocation'),
        (shopping.prepare_daily_booking_shopping, 'booking_shopping'),
        (quarterly_backend.reconcile, 'dispatch_reconciliation'),
        (kernel._apply_handler_candidate, 'handler_execution'),
        (kernel._replace_envelope, 'detached_commit'),
    ]
    aliases = []
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__name__', '')
        if not name.startswith(('game.', 'app.')):
            continue
        for attribute, value in tuple(vars(module).items()):
            for original, category in targets:
                if value is original:
                    aliases.append((module, attribute, original, category))
                    break
    for module, attribute, original, category in aliases:
        stack.enter_context(patch.object(module, attribute, profile.wrap(original, category)))
    # Scheduling lookups are methods rather than imported aliases.
    for owner, attribute in ((quarterly_supply.QuarterlySupply, 'on_date'),
            (quarterly_supply.QuarterlyActivationProvider, 'active_market_ids')):
        stack.enter_context(patch.object(owner, attribute,
            profile.wrap(getattr(owner, attribute), 'schedule_lookup')))
    gc_start = [None]
    def observe_gc(phase, info):
        if phase == 'start':
            gc_start[0] = perf_counter()
        elif gc_start[0] is not None:
            duration = perf_counter() - gc_start[0]
            profile.seconds['garbage_collection'] = profile.seconds.get('garbage_collection', 0) + duration
            profile.calls['garbage_collection'] = profile.calls.get('garbage_collection', 0) + 1
            if profile.stack:
                profile.stack[-1][1] += duration
            gc_start[0] = None
    gc.callbacks.append(observe_gc)
    stack.callback(gc.callbacks.remove, observe_gc)


def itinerary_reference(revision):
    """Compile only the recorded builder from a trusted repository revision.

    Test-only performance control, not a second production path or save reader.
    Other predicates/types remain current; no handler registration is changed.
    """
    path = 'game/world_state/booking_lineage_validation.py'
    source = subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
    definition = next(node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == '_itinerary_graph')
    namespace = dict(vars(booking_lineage_validation))
    exec(compile(ast.Module(body=[definition], type_ignores=[]),
        f'{revision}:{path}', 'exec'), namespace)
    return namespace['_itinerary_graph']


def measure(base, target, budget, *, instrument=False, cprofile_path=None, reference=False,
            itinerary_builder=None):
    profile = ExclusiveProfile()
    with tempfile.TemporaryDirectory(prefix='at-quarterly-profile-') as temporary:
        session = benchmark.session_for(base, temporary)
        with ExitStack() as stack:
            if itinerary_builder is not None:
                stack.enter_context(patch.object(booking_lineage_validation,
                    '_itinerary_graph', itinerary_builder))
            if reference:
                stack.enter_context(patch.object(booking_lineage_validation,
                    'valid_booking_relationships', return_value=False))
            if instrument:
                hooks(profile, stack)
            profiler = cProfile.Profile() if cprofile_path else None
            if profiler:
                profiler.enable()
            try:
                result = benchmark.advance(session, target, budget)
            finally:
                if profiler:
                    profiler.disable()
            if profiler:
                profiler.dump_stats(str(cprofile_path))
                stats = pstats.Stats(profiler)
                rows = [dict(file=f, line=line, function=name, primitive_calls=cc,
                    calls=nc, exclusive_s=tt, inclusive_s=ct)
                    for (f, line, name), (cc, nc, tt, ct, callers) in stats.stats.items()]
                result['cprofile_top_inclusive'] = sorted(rows,
                    key=lambda row: row['inclusive_s'], reverse=True)[:70]
                result['cprofile_top_exclusive'] = sorted(rows,
                    key=lambda row: row['exclusive_s'], reverse=True)[:70]
                result['profile_total_s'] = stats.total_tt
                result['profile_calls'] = stats.total_calls
            result['exclusive_s'] = profile.seconds
            result['inclusive_s'] = profile.inclusive
            result['calls'] = profile.calls
        # Validation and audit/hash are outside the command/instrumentation region.
        benchmark.valid(session.world)
        result['output_audit'] = benchmark.audit(session.world)
        session.close()
    return result


def validation_study(root, repeats):
    """Vary only coupled Booking/itinerary counts in an unflown synthetic control."""
    from tests import test_quarterly_backend as fixtures
    from tests.profile_booking_validation import split_aggregates
    from game.simulation.resolver import resolve_until
    base = fixtures.QuarterlyBackendTests.fixture(start='2026-12-31T00:00:00Z', quarter='2027-Q1')[0]
    assert resolve_until(base, '2027-01-01T00:00:00Z', shared=False).succeeded
    assert base['world_state']['bookings']
    groups = []
    for factor in (1, 2, 4):
        world = split_aggregates(base, factor)
        before = benchmark.digest(world)
        state = world['world_state']
        group = dict(factor=factor, counts=benchmark.audit(world)['counts'],
            passengers=sum(b['passenger_count'] for b in state['bookings'].values()),
            paid_minor=sum(b['total_fare_minor'] for b in state['bookings'].values()),
            hash=before, samples=[])
        for _ in range(repeats):
            for reference in (True, False):
                with ExitStack() as stack:
                    if reference:
                        stack.enter_context(patch.object(booking_lineage_validation,
                            'valid_booking_relationships', return_value=False))
                    start = perf_counter()
                    result = validation.validate_world(world)
                    elapsed = perf_counter() - start
                assert result.is_valid, result
                group['samples'].append(dict(reference=reference, wall_s=elapsed,
                    peak_bytes=benchmark.memory_bytes()))
        assert benchmark.digest(world) == before
        groups.append(group)
    result = dict(kind='SYNTHETIC_VALIDATION_ONLY', groups=groups,
        note='Aggregate splitting preserves passengers/fare/events/flights/history; not gameplay capacity.')
    (root / 'validation-study.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--label', default='baseline')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--days', type=int, default=1)
    parser.add_argument('--budget', type=float, default=900)
    parser.add_argument('--instrument', action='store_true')
    parser.add_argument('--cprofile', action='store_true')
    parser.add_argument('--reference-booking', action='store_true')
    parser.add_argument('--itinerary-revision', help='trusted Git revision for the test-only itinerary builder control')
    parser.add_argument('--validation-study', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    protected = (Path(__file__).resolve().parents[1] / 'Saves').resolve()
    if root == protected or protected in root.parents:
        parser.error('profiling must not use real Saves')
    if args.repeats < 1 or args.days < 0 or args.budget < 0:
        parser.error('positive repeats and nonnegative days/budget required')
    if Path(args.label).name != args.label or args.label in ('.', '..'):
        parser.error('label must be one filename component')
    if args.validation_study:
        root.mkdir(parents=True, exist_ok=True)
        validation_study(root, args.repeats)
        return
    base = json.loads((root / 'fleet-1.json').read_text(encoding='utf-8'))
    audit = json.loads((root / 'fleet-1-audit.json').read_text(encoding='utf-8'))
    if audit.get('fixture') != 'READY':
        parser.error('requires a ready B2 operating fixture')
    assert benchmark.digest(base) == audit['audit']['hash']
    benchmark.valid(base)
    builder = itinerary_reference(args.itinerary_revision) if args.itinerary_revision else None
    target = benchmark.format_utc(benchmark.parse_canonical_utc(base['simulation']['time_utc'])
        + timedelta(days=args.days))
    result = dict(label=args.label, environment=platform.platform(), python=platform.python_version(),
        source=benchmark.audit(base), days=args.days, instrument=args.instrument,
        cprofile=args.cprofile, reference_booking=args.reference_booking,
        itinerary_revision=args.itinerary_revision, samples=[])
    result['source_file_bytes'] = (root / 'fleet-1.json').stat().st_size
    result['source_record_counts'] = {key: len(value) for key, value in base['world_state'].items()
        if type(value) in (dict, list)}
    result['retained_checkpoints'] = len(base['world_state']['booking_state']['booking_checkpoints'])
    result['processed_cohorts'] = len(base['world_state']['demand_state']['processed_cohorts'])
    for index in range(args.repeats):
        cpath = root / f'{args.label}-{index}.prof' if args.cprofile else None
        sample = measure(base, target, args.budget, instrument=args.instrument,
            cprofile_path=cpath, reference=args.reference_booking, itinerary_builder=builder)
        result['samples'].append(sample)
        print(json.dumps(dict(label=args.label, sample=index, **sample)), flush=True)
    values = [sample['wall_s'] for sample in result['samples']]
    result.update(median_s=statistics.median(values), min_s=min(values), max_s=max(values))
    (root / f'{args.label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(label=args.label, median_s=result['median_s'],
        min_s=result['min_s'], max_s=result['max_s'])), flush=True)


if __name__ == '__main__':
    main()
