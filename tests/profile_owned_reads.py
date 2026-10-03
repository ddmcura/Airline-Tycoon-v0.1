"""Opt-in Stage 2 paired-fixture measurements (never writes production saves).

python -B -m tests.profile_owned_reads --fixtures <temp-dir> --output <temp-json>
Fixtures are plain validated envelopes prepared separately. Input/output hashes
allow exact before/after comparison. The first Fleet read includes the foreign
binding validation (production New Game/Load already establish that proof).
Cold-owned profiling discards derived pages after that proof, not world authority.
Setup/copy/hash/post-validation are excluded.
Instrumented timings are separate from uninstrumented latency samples.
"""
import argparse
from copy import deepcopy
import cProfile
import json
from pathlib import Path
import pstats
import tempfile
from time import perf_counter

from app.session import Stage1Session
from game.world_state import validate_world
from tests.resolution_oracle import world_digest
from tests.profile_scheduling import memory


def timed(run):
    started = perf_counter()
    result = run()
    return perf_counter() - started, result


def profile(run):
    profiler = cProfile.Profile()
    profiler.runcall(run)
    stats = pstats.Stats(profiler)
    names = ('validate_world', '_clone_runtime_world', 'load_aircraft_catalog',
             'parse_aircraft_catalog', 'validate_aircraft_catalog', '_project_flight',
             'build_confirmed_carriage_manifest', '_build_confirmed_carriage_manifest',
             'rebuild_booking_indexes', '_build_operations_lookup', '_execute_event')
    return {name: {'calls': sum(v[0] for k,v in stats.stats.items() if k[2] == name),
                  'seconds': sum(v[3] for k,v in stats.stats.items() if k[2] == name)}
            for name in names}


def measure(base, root):
    session = Stage1Session(save_root=root, runtime_clock=lambda: 0)
    session.world = deepcopy(base)
    session._reset_autosave_clocks()
    row = dict(input_sha256=world_digest(base),
               flights=len(base['world_state']['dated_flights']),
               bookings=len(base['world_state']['bookings']),
               results=len(base['world_state']['flight_results']))
    row['validation_seconds'], valid = timed(lambda: validate_world(base))
    assert valid.is_valid
    reads = dict(fleet=session.fleet, flights=session.flights, results=session.finances)
    row['read_seconds'] = {}
    for name, read in reads.items():
        cold, expected = timed(read)
        warm, actual = timed(read)
        assert expected == actual
        row['read_seconds'][name] = dict(first=cold, repeat=warm)
    row['read_profile'] = profile(lambda: [read() for read in reads.values()])
    row['read_output'] = {name: read() for name,read in reads.items()}
    if hasattr(session, '_refresh_owned_reads'):
        session._refresh_owned_reads()
        row['cold_owned_profile'] = profile(lambda: [read() for read in reads.values()])
        views = session._read_views
        row['lookup'] = dict(
            indexed_booking_ids=sum(len(ids) for ids in views._lookup.booking_ids_by_flight.values()),
            pending_flight_groups=len(views._lookup.next_event_id_by_flight),
            encoded_page_bytes=sum(len(value.encode('utf-8')) for value in views._pages.values()))
        import tracemalloc
        session._refresh_owned_reads()
        tracemalloc.start()
        for read in reads.values():
            read()
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        row['derived_allocation_bytes'] = dict(retained=retained, peak=peak)
    event = deepcopy(base)
    session.world = event
    row['next_event_seconds'], report = timed(session.advance_next_event)
    assert report.result.succeeded, report.result.failure
    row['next_event_output_sha256'] = world_digest(event)
    session.world = deepcopy(base)
    row['next_event_profile'] = profile(session.advance_next_event)
    session.world = deepcopy(base)
    row['advance_seconds'], report = timed(lambda:session.advance_seconds(3600))
    assert report.result.succeeded, report.result.failure
    row['advance_events'] = len(report.result.completed_event_ids)
    row['advance_output_sha256'] = world_digest(session.world)
    assert validate_world(session.world).is_valid
    row['memory'] = memory()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--cases', default='observed-save,starter-1,aged-recurring,starter-10')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path, help='Previous result JSON; assert exact identities')
    args = parser.parse_args()
    previous = json.loads(args.compare.read_text(encoding='utf-8')) if args.compare else None
    rows = {}
    for name in args.cases.split(','):
        base = json.loads((args.fixtures/(name+'.json')).read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='at-owned-profile-') as root:
            rows[name] = measure(base, root)
        if previous is not None:
            for key in ('input_sha256','read_output','next_event_output_sha256',
                        'advance_output_sha256'):
                assert rows[name][key] == previous[name][key], (name,key)
        args.output.write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps(dict(case=name, **{k:v for k,v in rows[name].items()
              if k != 'read_output'})),flush=True)


if __name__ == '__main__':
    main()
