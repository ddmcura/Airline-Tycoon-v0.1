"""Opt-in exact PH advancement measurements, isolated fixtures and save roots.

python -B -m tests.profile_advancement --fixtures <temp-dir> --fleets 1 --days 1,2,7,30
Use identical fixture JSON for before/after. Setup/hashing/final validation excluded.
--case observed-save measures a detached read-only gameplay save supplied separately.
Budgets stop only between complete events; partial runs are labelled, never successes.
"""
import argparse
from collections import Counter
from copy import deepcopy
import cProfile
from contextlib import contextmanager
from datetime import timedelta
import json
from pathlib import Path
import pstats
import tempfile
import time

from app.session import Stage1Session
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.profile_scheduling import seed_publication, identities, fixture, digest, memory, copy_counts, fresh
from game.scheduling.recurrence import publish_rolling_window


def starting_world(fleet):
    world = seed_publication(fleet, rolling=True)
    result = publish_rolling_window(world, identities(world)[0])
    if not result.succeeded:
        raise ValueError(result)
    # Real booking/event history, not a fabricated clock move into flight week.
    with tempfile.TemporaryDirectory() as root:
        session = Stage1Session(runtime_clock=lambda:0, save_root=root)
        session.world = world
        result = session.advance_to('2026-09-06T23:59:59Z').result
        if result.failure:
            raise ValueError(result.failure)
    return world


def advance(world, days, budget):
    with tempfile.TemporaryDirectory() as root:
        session = Stage1Session(runtime_clock=lambda:0, save_root=root)
        session.world = world
        target = format_utc(parse_canonical_utc(world['simulation']['time_utc']) + timedelta(days=days))
        initial = set(world['world_state']['event_history'])
        start = time.perf_counter()
        session.begin_advance_to(target)
        report = None
        limited = False
        while session.advancing:
            report = session.advance_tick()
            if time.perf_counter()-start > budget and session.advancing:
                session.cancel_advance()
                limited = True
        elapsed = time.perf_counter()-start
        if report is not None and report.result.failure:
            status = report.result.failure.code
        else:
            status = 'TIME_BUDGET' if limited else 'COMPLETED'
        records = [e for key,e in world['world_state']['event_history'].items() if key not in initial]
        return {'seconds':elapsed, 'status':status, 'target_utc':target,
                'actual_utc':world['simulation']['time_utc'], 'events':len(records),
                'events_by_type':dict(Counter(e['event_type'] for e in records)),
                'flights_completed':sum(e['event_type']=='STAGE1_FLIGHT_COMPLETION' for e in records)}


@contextmanager
def event_costs():
    from game.simulation import kernel
    original = kernel._execute_event
    times, counts = Counter(), Counter()
    def measured(world, key, registry):
        kind = world['world_state']['pending_events'][key]['event_type']
        started = time.perf_counter()
        try:
            return original(world,key,registry)
        finally:
            times[kind] += time.perf_counter()-started
            counts[kind] += 1
    kernel._execute_event = measured
    try:
        yield times, counts
    finally:
        kernel._execute_event = original


def measure(name, base, days, budget, profile=False, allocations=False):
    world = deepcopy(base)
    row = {'case':name,'days':days, 'input_sha256':digest(base),
           'input_bytes':len(json.dumps(base,separators=(',',':'))),
           'fleet':len(base['world_state']['aircraft']),
           'input_flights':len(base['world_state']['dated_flights']),
           'input_bookings':len(base['world_state']['bookings'])}
    with event_costs() as (times, counts):
        row.update(advance(world,days,budget))
    row['event_seconds_by_type'] = dict(times)
    row['event_dispatch_counts'] = dict(counts)
    assert validate_world(world).is_valid
    row['output_sha256'] = digest(world)
    row['memory'] = memory()
    print(json.dumps(row),flush=True)
    if profile:
        world=deepcopy(base)
        profiler=cProfile.Profile()
        with copy_counts() as copies:
            profiler.enable()
            outcome=advance(world,days,budget)
            profiler.disable()
        stats=pstats.Stats(profiler)
        calls=dict(copies)
        names=('validate_world','_execute_event','_replace_envelope','_replace',
               'prepare_daily_booking_checkpoint','process_daily_booking_checkpoint',
               'prepare_daily_booking_allocation','prepare_daily_booking_shopping',
               'resolve_model4_active_daily_cohorts','_departure','_completion',
               '_weekly_publication','load_aircraft_catalog','schedule_event',
               'build_confirmed_carriage_manifest','rebuild_model4_indexes','_report')
        calls.update({name:sum(v[0] for k,v in stats.stats.items() if k[2]==name) for name in names})
        print(json.dumps({'profile_case':name,'days':days,'instrumented_outcome':outcome,
                         'counts':calls, 'hotspots':[{'file':Path(k[0]).name,'function':k[2],
                             'calls':v[0],'self_seconds':v[2],'cumulative_seconds':v[3]}
                             for k,v in sorted(stats.stats.items(),key=lambda p:-p[1][3])[:35]]}),flush=True)

    if allocations:
        import tracemalloc
        world = deepcopy(base)
        tracemalloc.start()
        outcome = advance(world,days,budget)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(json.dumps({'allocation_case':name, 'days':days, 'outcome':outcome,
            'retained_bytes':retained, 'peak_bytes':peak,
            'output_sha256':digest(world)}),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--fleets',default='1')
    parser.add_argument('--days',default='1,2,7,30')
    parser.add_argument('--case')
    parser.add_argument('--budget',type=float,default=120)
    parser.add_argument('--profile',action='store_true')
    parser.add_argument('--allocations',action='store_true')
    parser.add_argument('--build-only',action='store_true')
    args=parser.parse_args()
    args.fixtures.mkdir(parents=True,exist_ok=True)
    cases=[args.case] if args.case else ['starter-'+n for n in args.fleets.split(',')]
    for name in cases:
        if name.startswith('starter-'):
            world=fixture(args.fixtures,name,lambda:starting_world(int(name.split('-')[1])))
        elif name == 'quiet-new':
            world=fixture(args.fixtures,name,lambda:fresh(1))
        else:
            world=json.loads((args.fixtures/(name+'.json')).read_text(encoding='utf-8'))
        if args.build_only:
            continue
        for days in map(int,args.days.split(',')):
            measure(name,world,days,args.budget,args.profile,args.allocations)


if __name__=='__main__':
    main()
