"""Opt-in real PH workload profiling: python -B -m tests.profile_ph_runtime.

Fixtures use extra test capital; no production balance changes or save files.
"""
import argparse
import json
import os
import platform
import time
from copy import deepcopy
from datetime import timedelta

from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import parse_canonical_utc, format_utc
from game.aircraft_market.acquisition import preview_purchase, purchase_aircraft
from game.aircraft_market.reference_catalog import load_aircraft_catalog, PH_AIRCRAFT_CATALOG_VERSION
from game.economy.acquisition import purchase_accounts
from game.scheduling import WeeklyDraft
from game.simulation.kernel import iter_events_through, process_events_through
from game.simulation.pacing import RuntimeController, active_monotonic_ns, NANOSECOND


def workload(fleet_size, days=7):
    world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
        ceo_display_name='Profile', airline_display_name='PH workload',
        base_airport_reference_code='MNL')
    state = world['world_state']
    owner = state['player']['primary_airline_id']
    airports = {row['reference_code']: key for key, row in state['airports'].items()}
    purchase_accounts(state, owner)['cash']['balance_minor'] = 10**14
    catalog = load_aircraft_catalog(catalog_version=PH_AIRCRAFT_CATALOG_VERSION)
    model = next(row for manufacturer in catalog.manufacturers()
                 for row in catalog.models(manufacturer['manufacturer_id'])
                 if 150 <= row['max_economy_seats'] <= 200)
    for _ in range(fleet_size - 1):
        purchase_aircraft(world, preview_purchase(world, airline_id=owner,
            model_id=model['model_id'], catalog_version=PH_AIRCRAFT_CATALOG_VERSION,
            delivery_airport_id=airports['MNL']))
    aircraft_ids = list(world['world_state']['aircraft'])
    for index, aircraft_id in enumerate(aircraft_ids):
        draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft_id)
        destination = airports[('CEB', 'DVO', 'ILO', 'BCD', 'PPS')[index % 5]]
        # Daily return pair, staggered departures, booked before operation.
        for day in range(days):
            departure = parse_canonical_utc('2026-09-07T00:00:00Z') + timedelta(days=day, minutes=index * 3)
            draft.add(airports['MNL'], destination, departure_utc=format_utc(departure), fare_minor=5000)
            draft.add(destination, airports['MNL'], fare_minor=5000)
        draft.save(world)
    validation = validate_world(world)
    if not validation.is_valid:
        raise ValueError(validation.errors)
    return world


def memory_bytes():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'working', 'pp', 'p', 'pnp', 'np', 'pf', 'ppf')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess
        handle.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if query(handle(), ctypes.byref(counters), counters.cb):
            return counters.peak
    return None


def live_profile(world, seconds, label):
    controller = RuntimeController(world)
    start_utc = parse_canonical_utc(world['simulation']['time_utc'])
    history = len(world['world_state']['event_history'])
    controller.resume()
    start_ns = active_monotonic_ns()
    slowest = 0
    window_ns = start_ns
    window_sim = 0
    window_credit = controller.credit_ns
    windows = []
    accounted_windows = []
    while active_monotonic_ns() - start_ns < seconds * NANOSECOND and controller.running:
        before = time.perf_counter()
        controller.pump()
        slowest = max(slowest, time.perf_counter()-before)
        sampled_ns = active_monotonic_ns()
        if sampled_ns - window_ns >= 60 * NANOSECOND:
            sampled_sim = (parse_canonical_utc(world['simulation']['time_utc'])-start_utc).total_seconds()
            window_seconds = (sampled_ns-window_ns)/NANOSECOND
            windows.append((sampled_sim-window_sim)/window_seconds)
            accounted_windows.append(
                (sampled_sim-window_sim
                 + (controller.credit_ns-window_credit)/NANOSECOND) / window_seconds)
            print(json.dumps({'live_phase': label, 'window_speed': windows[-1],
                              'window_accounted_speed': accounted_windows[-1],
                              'credit_seconds': controller.credit_ns/NANOSECOND}), flush=True)
            window_ns, window_sim = sampled_ns, sampled_sim
            window_credit = controller.credit_ns
        time.sleep(.01)
    controller.pause()
    elapsed = (active_monotonic_ns()-start_ns)/NANOSECOND
    simulated = (parse_canonical_utc(world['simulation']['time_utc'])-start_utc).total_seconds()
    print(json.dumps({'live_phase': label, 'active_seconds': elapsed,
        'simulated_seconds': simulated, 'achieved_speed': simulated/elapsed,
        'accounted_speed': (simulated + controller.credit_ns/NANOSECOND)/elapsed,
        'credit_simulation_seconds': controller.credit_ns/NANOSECOND,
        'max_pump_seconds': slowest,
        'completed_window_speeds': windows,
        'completed_accounted_window_speeds': accounted_windows,
        'events': len(world['world_state']['event_history'])-history,
        'diagnostic': controller.diagnostic}), flush=True)
    controller.close()


def profile(size, days, live_seconds=0):
    build = time.perf_counter()
    world = workload(size, days)
    print(json.dumps({'fleet': size, 'build_seconds': time.perf_counter()-build}), flush=True)
    start_time = parse_canonical_utc(world['simulation']['time_utc'])
    target = format_utc(parse_canonical_utc('2026-09-07T00:00:00Z') + timedelta(days=days))
    before_history = len(world['world_state']['event_history'])
    live_booking = None
    live_operations = None
    if live_seconds:
        live_booking = deepcopy(world)
        process_events_through(live_booking, '2026-09-01T23:59:59Z')
    elapsed = 0
    latencies = []
    # Explicitly resume limit-blocked bulk commands, reporting each limit.
    # This profiler is not the live controller and never hides a limit.
    limits = []
    while True:
        work = iter_events_through(world, target)
        while True:
            begin = time.perf_counter()
            history_before_pump = len(world['world_state']['event_history'])
            try:
                next(work)
            except StopIteration as done:
                duration = time.perf_counter()-begin
                elapsed += duration
                if len(world['world_state']['event_history']) > history_before_pump:
                    latencies.append(duration)
                result = done.value
                break
            duration = time.perf_counter()-begin
            elapsed += duration
            latencies.append(duration)
            if live_seconds and live_operations is None and world['simulation']['time_utc'] >= '2026-09-07T00:00:00Z':
                live_operations = deepcopy(world)
            if len(latencies) % 20 == 0 or duration >= 10:
                print(json.dumps({'fleet': size, 'completed': len(latencies),
                                  'time_utc': world['simulation']['time_utc'],
                                  'transaction_seconds': duration}), flush=True)
        if result.succeeded:
            break
        if result.failure.code not in {'EVENT_LIMIT_REACHED', 'EVENT_GENERATION_LIMIT_REACHED'}:
            raise RuntimeError(result)
        limits.append(result.failure.code)
    state = world['world_state']
    simulated = (parse_canonical_utc(target)-start_time).total_seconds()
    print(json.dumps({'fleet': size, 'days_operating': days, 'processing_seconds': elapsed,
        'simulated_seconds': simulated, 'maximum_processing_speed': simulated/elapsed,
        'events': len(latencies), 'events_per_second': len(latencies)/elapsed,
        'max_transaction_seconds': max(latencies, default=0),
        'p95_transaction_seconds': sorted(latencies)[int(len(latencies)*.95)] if latencies else 0,
        'peak_working_set_bytes': memory_bytes(),
        'event_history_growth': len(state['event_history'])-before_history,
        'serialized_bytes': len(json.dumps(world)), 'explicit_limit_continuations': limits}), flush=True)
    if live_seconds:
        live_profile(live_booking, live_seconds, 'Booking midnight')
        live_profile(live_operations, live_seconds, 'Operating departures')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fleets', nargs='+', type=int, default=[1, 10, 50])
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--live-seconds', type=int, default=0)
    parser.add_argument('--live-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps({'platform': platform.platform(), 'cpu': platform.processor(),
                      'logical_cpus': os.cpu_count(), 'python': platform.python_version()}), flush=True)
    for size in args.fleets:
        if args.live_only:
            world = workload(size, args.days)
            prepared = process_events_through(world, '2026-09-06T23:59:59Z')
            if not prepared.succeeded:
                raise RuntimeError(prepared)
            live_profile(world, args.live_seconds, f'{size} aircraft: midnight into departures')
        else:
            profile(size, args.days, args.live_seconds)
