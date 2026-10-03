"""Opt-in deterministic scheduling benchmarks; no production saves/data.

python -B -m tests.profile_scheduling --fixtures <temporary-directory> --repeats 3
Use the SAME fixtures before/after. --profile prints separate cProfile evidence;
profiling overhead is excluded from the latency samples. --gui measures Kivy
separately. Fixture capital is test-only, as in profile_ph_runtime.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import cProfile
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import pstats
import statistics
import sys
import tempfile
import time

from game.aircraft_market.acquisition import preview_purchase, purchase_aircraft
from game.aircraft_market.reference_catalog import PH_AIRCRAFT_CATALOG_VERSION
from game.economy.acquisition import purchase_accounts
from game.scheduling import WeeklyDraft
from game.scheduling.publication import create_schedule_definition, publish_occurrences_through
from game.scheduling.recurrence import EVENT_TYPE
from game.scheduling.rotation import _connection
from game.simulation import process_events_through, process_next_event
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc

DRAFT_CASES = {
    'single': ((0,), False), 'single-return': ((0,), True),
    'mwf': ((0, 2, 4), False), 'mwf-return': ((0, 2, 4), True),
    'daily': (tuple(range(7)), False), 'daily-return': (tuple(range(7)), True),
}
PUBLISH_CASES = {10: (1, 5), 50: (1, 25), 100: (2, 25),
                 250: (5, 25), 560: (5, 56)}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def memory():
    """Windows process working set and process-lifetime high-water mark."""
    if os.name != 'nt':
        return {}
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in
            ('peak', 'working', 'pp', 'p', 'pnp', 'np', 'pf', 'ppf')]
    result = Counters()
    result.cb = ctypes.sizeof(result)
    handle = ctypes.windll.kernel32.GetCurrentProcess
    handle.restype = wintypes.HANDLE
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if query(handle(), ctypes.byref(result), result.cb):
        return {'working_set_bytes': result.working, 'process_peak_bytes': result.peak}
    return {}


def valid(world):
    result = validate_world(world)
    if not result.is_valid:
        raise ValueError(result.errors[:3])


def fresh(fleet=1):
    world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
        ceo_display_name='Profile', airline_display_name='Scheduling benchmark',
        base_airport_reference_code='MNL')
    state = world['world_state']
    owner = state['player']['primary_airline_id']
    ports = {row['reference_code']: key for key, row in state['airports'].items()}
    if fleet > 1:
        purchase_accounts(state, owner)['cash']['balance_minor'] = 10**14
        for _ in range(fleet - 1):
            purchase_aircraft(world, preview_purchase(world, airline_id=owner,
                model_id='airbus-a320neo', catalog_version=PH_AIRCRAFT_CATALOG_VERSION,
                delivery_airport_id=ports['MNL']))
    valid(world)
    return world


def identities(world):
    state = world['world_state']
    return (state['player']['primary_airline_id'], sorted(state['aircraft'])[0],
            {row['reference_code']: key for key, row in state['airports'].items()})


def definitions(world, aircraft, weekdays, *, only_return=False, rolling=False):
    """Use domain-derived pair timings to author public, unpublished definitions."""
    owner, _, ports = identities(world)
    pair = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
    pair.add(ports['MNL'], ports['DVO'], departure_utc='2026-09-07T00:00:00Z', fare_minor=11600)
    pair.add_return(fare_minor=11600)
    for leg in pair.legs[1:] if only_return else pair.legs:
        origin, destination = leg['origin_airport_id'], leg['destination_airport_id']
        zone = world['world_state']['airports'][origin]['timezone']
        from game.world_state.timezones import load_named_timezone
        from game.scheduling.timing import timing_bounds
        departure = parse_canonical_utc(leg['departure_utc'])
        arrival = departure + timedelta(seconds=timing_bounds(leg['planning_timing'])[1][1])
        local, local_arrival = departure.astimezone(load_named_timezone(zone)), arrival.astimezone(load_named_timezone(zone))
        result = create_schedule_definition(world, airline_id=owner,
            connection_id=_connection(world, owner, origin, destination),
            planned_aircraft_id=aircraft, origin_airport_id=origin,
            destination_airport_id=destination, effective_from_local_date='2026-09-07',
            weekdays=list(weekdays), departure_local_time=local.strftime('%H:%M:%S'),
            arrival_local_time=local_arrival.strftime('%H:%M:%S'), arrival_day_offset=0,
            capacity=world['world_state']['aircraft'][aircraft]['configuration']['economy_capacity'],
            fare_offer={'currency': 'USD', 'amount_minor': 11600},
            passenger_service_classification='ECONOMY', planning_timing=leg['planning_timing'],
            until_local_date='2026-09-13' if only_return else None,
            publication_policy='ROLLING_FOUR_WEEKS_V1' if rolling else None)
        if not result.succeeded:
            raise ValueError(result)


def seed_publication(fleet=1, rolling=False):
    world = fresh(fleet)
    for aircraft in sorted(world['world_state']['aircraft']):
        definitions(world, aircraft, range(7), rolling=rolling)
    valid(world)
    return world


def horizon(days):
    return format_utc(parse_canonical_utc('2026-09-07T23:59:59Z') + timedelta(days=days-1))


def fixture(root, key, build):
    path = root / (key + '.json')
    if path.exists():
        world = json.loads(path.read_text(encoding='utf-8'))
    else:
        started = time.perf_counter()
        world = build()
        valid(world)
        # Preserve insertion order: demand witnesses include ordered categories.
        path.write_text(json.dumps(world, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        print(json.dumps({'fixture': key, 'build_seconds': time.perf_counter()-started}), flush=True)
    valid(world)
    return world


def large_world():
    world = seed_publication(5)
    result = publish_occurrences_through(world, horizon(56))
    if not result.succeeded:
        raise ValueError(result)
    return world


def aged_world():
    world = seed_publication(rolling=True)
    from game.scheduling.recurrence import publish_rolling_window
    publish_rolling_window(world, identities(world)[0])
    result = process_events_through(world, '2026-09-20T15:59:59Z')
    if not result.succeeded:
        raise ValueError(result)
    next_event = min(world['world_state']['pending_events'].values(),
                     key=lambda row: (row['due_at_utc'], row['order_key'], row['event_id']))
    assert next_event['event_type'] == EVENT_TYPE
    return world


@contextmanager
def copy_counts():
    """Count explicit world/draft copies at imported application/domain call sites."""
    import copy
    original = copy.deepcopy
    count = Counter()
    def tracked(value, *args, **kwargs):
        if type(value) is dict and 'world_state' in value and 'simulation' in value:
            count['world_copies'] += 1
        elif isinstance(value, WeeklyDraft):
            count['draft_copies'] += 1
        return original(value, *args, **kwargs)
    patched = []
    for name, module in list(sys.modules.items()):
        if module and (name.startswith('game.') or name.startswith('app.')):
            for attr, value in list(vars(module).items()):
                if value is original:
                    patched.append((module, attr))
                    setattr(module, attr, tracked)
    try:
        yield count
    finally:
        for module, attr in patched:
            setattr(module, attr, original)


def measure(name, world, prepare, repeats, profile=False, allocations=False):
    latencies, witnesses = [], []
    for _ in range(repeats):
        candidate = deepcopy(world)
        run, result = prepare(candidate)
        before_memory = memory()
        start = time.perf_counter()
        run()
        latencies.append(time.perf_counter() - start)
        valid(candidate)
        outcome = result()
        witnesses.append(digest(outcome))
    assert len(set(witnesses)) == 1, (name, witnesses)
    row = {'case': name, 'seconds': latencies, 'median_seconds': statistics.median(latencies),
           'fixture_sha256': digest(world), 'outcome_sha256': witnesses[0],
           'fixture_flights': len(world['world_state']['dated_flights']),
           'fixture_results': len(world['world_state']['flight_results']),
           'fixture_bookings': len(world['world_state']['bookings']),
           'fixture_bytes': len(encoded(world)), 'before_memory': before_memory, 'after_memory': memory()}
    if profile:
        candidate = deepcopy(world)
        run, result = prepare(candidate)
        profiler = cProfile.Profile()
        with copy_counts() as copies:
            profiler.enable()
            run()
            profiler.disable()
        assert digest(result()) == witnesses[0]
        stats = pstats.Stats(profiler)
        names = ('validate_world', 'deepcopy', 'create_schedule_definition', 'publish_occurrences_through',
                 '_replace_envelope', '_expand_schedule', '_movements', 'planning_snapshot',
                 '_continuity_conflicts', '_reconcile_schema4_departure_events', 'schedule_event',
                 'week_rows', 'refresh', '_timeline', 'render_scheduling', '_render_view',
                 'header', 'fleet', 'airports',
                 'load_aircraft_catalog', '__init__', 'validate_current')
        row['calls'] = dict(copies)
        row['calls'].update({name: sum(value[0] for key, value in stats.stats.items() if key[2] == name)
                             for name in names})
        row['calls']['widget_constructions'] = sum(value[0] for key, value in stats.stats.items()
            if Path(key[0]).name == 'widget.py' and key[2] == '__init__')
        row['hotspots'] = [{'file': str(Path(key[0]).name), 'line': key[1], 'function': key[2],
                            'calls': value[0], 'self_seconds': value[2], 'cumulative_seconds': value[3]}
                           for key, value in sorted(stats.stats.items(), key=lambda pair: -pair[1][3])[:15]]
    if allocations:
        import gc
        import tracemalloc
        candidate = deepcopy(world)
        run, result = prepare(candidate)
        gc.collect()
        tracemalloc.start()
        run()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert digest(result()) == witnesses[0]
        row['operation_python_allocations'] = {'retained_bytes': current, 'peak_bytes': peak}
    print(json.dumps(row, sort_keys=True), flush=True)


def draft_operation(world, weekdays, returns, departure='08:00'):
    owner, aircraft, ports = identities(world)
    draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
    dates = tuple((date(2026, 9, 7) + timedelta(days=i)).isoformat() for i in weekdays)
    def run():
        draft.add_weekdays(ports['MNL'], ports['DVO'], dates, departure,
                          return_flight=returns, fare_minor=11600)
    return run, lambda: {'world': world, 'legs': draft.legs}


def publish_operation(world, days):
    result = []
    def run():
        value = publish_occurrences_through(world, horizon(days))
        if not value.succeeded:
            raise ValueError(value)
        result.append(value.created_dated_flight_ids)
    return run, lambda: {'world': world, 'created': result}


def run(args, root):
    wanted = set(args.cases.split(',')) if args.cases else None
    def selected(name):
        return wanted is None or name in wanted
    for name, (weekdays, returns) in DRAFT_CASES.items():
        key = 'draft-' + name
        if not selected(key): continue
        def build(weekdays=weekdays, returns=returns):
            world = fresh()
            if not returns:
                definitions(world, identities(world)[1], weekdays, only_return=True)
            return world
        world = fixture(root, key, build)
        measure(key, world, lambda w: draft_operation(w, weekdays, returns), args.repeats, args.profile, args.allocations)
    for count, (fleet, days) in PUBLISH_CASES.items():
        key = f'publish-{count}'
        if not selected(key): continue
        world = fixture(root, f'publish-seed-{fleet}', lambda: seed_publication(fleet))
        measure(key, world, lambda w: publish_operation(w, days), args.repeats, args.profile, args.allocations)
    if selected('weekly-publish-560'):
        world = fixture(root, 'weekly-publish-fresh', fresh)
        def prepare(world):
            owner, aircraft, ports = identities(world)
            draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
            # Ten short domestic round trips/day. Timings and return departures
            # come from the planner, not invented/overlapping benchmark flights.
            for day in range(7):
                local_date = date(2026, 9, 7) + timedelta(days=day)
                for minute in range(30, 30 + 10 * 140, 140):
                    from game.scheduling.local_time import local_departure
                    departure = local_departure(world['world_state'], ports['MNL'],
                        local_date.isoformat(), f'{minute // 60:02d}:{minute % 60:02d}')
                    draft.add(ports['MNL'], ports['CRK'], departure_utc=format_utc(departure), fare_minor=11600)
                    draft.add_return(fare_minor=11600)
            def run():
                result = draft.save_current(world, repeat_until='2026-11-01')
                if not result.succeeded: raise ValueError(result)
                assert len(result.created_dated_flight_ids) == 560
            return run, lambda: world
        measure('weekly-publish-560', world, prepare, args.repeats, args.profile, args.allocations)
    if selected('draft-existing-560'):
        world = fixture(root, 'existing-560', large_world)
        measure('draft-existing-560', world,
                lambda w: draft_operation(w, range(7), True, '14:00'), args.repeats, args.profile, args.allocations)
    if selected('save-draft-existing-560'):
        world = fixture(root, 'existing-560', large_world)
        def prepare(world):
            owner, aircraft, ports = identities(world)
            draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
            draft.add_weekdays(ports['MNL'], ports['DVO'],
                tuple(f'2026-09-{day:02d}' for day in range(7, 14)),
                '14:00', return_flight=True, fare_minor=11600)
            def run():
                result = draft.save_current(world)
                if not result.succeeded: raise ValueError(result)
            return run, lambda: world
        measure('save-draft-existing-560', world, prepare, args.repeats, args.profile, args.allocations)
    if selected('recurrence-history'):
        world = fixture(root, 'recurrence-history', aged_world)
        def prepare(world):
            def run():
                result = process_next_event(world)
                if not result.succeeded: raise ValueError(result)
            return run, lambda: world
        measure('recurrence-history', world, prepare, args.repeats, args.profile, args.allocations)
    if args.gui:
        from app.gui.app import AirlineTycoonApp
        from app.session import Stage1Session
        for key, build in (('gui-fresh', fresh), ('gui-existing-560', large_world),
                           ('gui-render-existing-560', large_world)):
            if not selected(key): continue
            world = fixture(root, key, build)
            def prepare(world):
                session = Stage1Session(save_root=root / 'temporary-careers', runtime_clock=lambda: 0)
                session.world = world
                app = AirlineTycoonApp(session_factory=lambda: session)
                app.build()
                app._enter_game()
                app.show_view('Schedule')
                app.start_schedule(identities(world)[1])
                app._builder_origin = identities(world)[2]['MNL']
                app._builder_destination = identities(world)[2]['DVO']
                app._builder_time = '14:00'
                app._builder_fare = '116'
                app._builder_return = True
                app._builder_weekdays = set(range(7))
                app.change_schedule_week(1)
                if key == 'gui-render-existing-560':
                    assert app.add_builder_flights() == 14
                def call():
                    if key == 'gui-render-existing-560':
                        app.refresh(force=True)
                    else:
                        assert app.add_builder_flights() == 14
                    app.on_stop()
                return call, lambda: {'world': world, 'legs': app._draft.legs}
            measure(key, world, prepare, args.repeats, args.profile, args.allocations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path)
    parser.add_argument('--cases', help='comma-separated case names; default all domain cases')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--allocations', action='store_true', help='separate untimed tracemalloc repeat')
    args = parser.parse_args()
    if args.repeats < 1: parser.error('repeats must be positive')
    if args.fixtures:
        args.fixtures.mkdir(parents=True, exist_ok=True)
        run(args, args.fixtures)
    else:
        with tempfile.TemporaryDirectory(prefix='at-scheduling-profile-') as directory:
            run(args, Path(directory))
