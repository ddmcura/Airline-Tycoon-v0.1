"""Opt-in PH GUI/history benchmark, using only temporary career storage.

Run: python -m tests.profile_gui_growth --max-day 90
Each JSON line is a completed checkpoint; the same harness serves before/after.
"""
import argparse
from datetime import timedelta
import json
import os
import tempfile
import time

from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc


def elapsed(call):
    start = time.perf_counter()
    value = call()
    return round(time.perf_counter() - start, 6), value


def memory_bytes():
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in
            ('peak', 'working', 'pp', 'p', 'pnp', 'np', 'pf', 'ppf')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess
    handle.restype = wintypes.HANDLE
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    return counters.working if query(handle(), ctypes.byref(counters), counters.cb) else None


def counts(world):
    state = world['world_state']
    keys = ('dated_flights', 'bookings', 'flight_results', 'transactions',
            'event_history', 'pending_events', 'processed_demand_cohorts',
            'booking_checkpoints')
    return {key: len(state[key]) for key in keys if key in state}


def run(max_day):
    with tempfile.TemporaryDirectory() as save_root:
        session = Stage1Session(save_root=save_root, runtime_clock=lambda: 0)
        session.new_game('Benchmark CEO', 'Benchmark Air', 'MNL')
        airports = {row['reference_code']: row['airport_id'] for row in session.airports()}
        aircraft = session.fleet()[0]['aircraft_id']
        draft = session.begin_scheduling(aircraft)
        for index in range(7):
            departure = parse_canonical_utc('2026-09-07T00:00:00Z') + timedelta(days=index)
            draft.add(airports['MNL'], airports['DVO'],
                      departure_utc=format_utc(departure), fare_minor=11600)
            draft.add_return(fare_minor=11600)
        session.save_scheduling(draft)
        start_utc = parse_canonical_utc(session.world['simulation']['time_utc'])
        app = AirlineTycoonApp(session_factory=lambda: session)
        app.build()
        app._enter_game()
        checkpoints = (0, 1, 7, 30, 90)
        try:
            current_day = 0
            for target_day in checkpoints:
                if target_day > max_day:
                    break
                if target_day > current_day:
                    target_utc = format_utc(start_utc + timedelta(days=target_day))
                    advance_seconds, report = elapsed(lambda: session.advance_to(target_utc))
                    if report.result.failure:
                        raise RuntimeError(report.result.failure)
                    current_day = target_day
                else:
                    advance_seconds = 0
                world = session.world
                valid_seconds, validation = elapsed(lambda: validate_world(world))
                if not validation.is_valid:
                    raise RuntimeError(validation.errors[:3])
                overview_seconds, _ = elapsed(session.overview)
                fleet_seconds, _ = elapsed(lambda: session.fleet(limit=20))
                finance_seconds, _ = elapsed(session.finances)
                research_seconds, _ = elapsed(lambda: session.market_opportunities(
                    origin_airport_id=airports['MNL'], limit=100))
                try:
                    schedule_seconds, weekly = elapsed(lambda: session.begin_scheduling(aircraft))
                    week_rows_seconds, _ = elapsed(lambda: weekly.week_rows(
                        (start_utc + timedelta(days=target_day)).date().isoformat()))
                except ValueError as exc:
                    if str(exc) != 'select a parked aircraft':
                        raise
                    schedule_seconds = week_rows_seconds = None
                refresh_seconds, _ = elapsed(lambda: app.refresh(force=True))
                view_seconds = {}
                for view in ('Overview', 'Fleet', 'Research', 'Schedule'):
                    view_seconds[view], _ = elapsed(lambda view=view: app.show_view(view))
                print(json.dumps({
                    'day': target_day, 'simulation_time_utc': world['simulation']['time_utc'],
                    'advance_segment_seconds': advance_seconds,
                    'validate_seconds': valid_seconds, 'overview_seconds': overview_seconds,
                    'fleet_seconds': fleet_seconds, 'finance_seconds': finance_seconds,
                    'research_seconds': research_seconds, 'schedule_open_seconds': schedule_seconds,
                    'schedule_rows_seconds': week_rows_seconds,
                    'gui_refresh_seconds': refresh_seconds,
                    'gui_view_seconds': view_seconds,
                    'counts': counts(world), 'serialized_bytes': len(json.dumps(world)),
                    'working_set_bytes': memory_bytes(),
                }, sort_keys=True), flush=True)
        finally:
            app.on_stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-day', type=int, default=90)
    run(parser.parse_args().max_day)
