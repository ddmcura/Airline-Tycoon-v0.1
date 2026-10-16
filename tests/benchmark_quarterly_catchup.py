"""Opt-in AT-058 baseline; artifacts and saves must live outside the repository.

python -B -m tests.benchmark_quarterly_catchup --root <TEMP-directory> --fleet 1
No automatic retry. Budget cancellation happens only between committed events.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import timedelta
import json
from pathlib import Path
import platform
import tempfile
from time import perf_counter
from unittest.mock import patch

from tests import benchmark_quarterly_runtime as existing
from game.simulation.resolver import begin_resolution
from game.world_state.timestamps import parse_canonical_utc, format_utc

START = '2026-08-31T00:00:00Z'
OPERATING_START = '2026-10-02T03:00:00Z'


def safe_root(root):
    root = Path(root).resolve()
    repo = Path(__file__).resolve().parents[1]
    if root == repo or repo in root.parents:
        raise ValueError('measurement artifacts require a temporary location outside the repository')
    return root


def constrained_resolution(world, target, **options):
    # Session currently supplies 10,000 for generated children. This measurement
    # explicitly requires the stricter existing kernel default, 100 same-time
    # children, as well as 10,000 processed events. No counter resets at yields.
    options['max_generated_events'] = 100
    options['max_events'] = 10_000
    return begin_resolution(world, target, **options)


def correctness(world):
    existing.valid(world)
    state = world['world_state']
    results = list(state['flight_results'].values())
    settlements = [t for t in state['transactions'].values() if t['source_type'] == 'FLIGHT_FULFILMENT']
    assert len({r['dated_flight_id'] for r in results}) == len(results)
    assert len({r['settlement_transaction_id'] for r in results}) == len(results)
    assert {t['transaction_id'] for t in settlements} == {r['settlement_transaction_id'] for r in results}
    assert len({t['source_id'] for t in settlements}) == len(settlements)
    assert all(sum(e['amount_minor'] for e in t['entries']) == 0 for t in state['transactions'].values())
    assert len({f['occurrence_key'] for f in state['dated_flights'].values()}) == len(state['dated_flights'])
    for result in results:
        assert result['actual_departure_utc'] <= result['actual_arrival_utc'] <= world['simulation']['time_utc']
        assert result['carried_passenger_count'] == sum(state['bookings'][bid]['passenger_count']
                                                       for bid in result['source_booking_ids'])
    # Full validation additionally verifies active operations, parked positions,
    # complete aircraft chains, inventory, pool conservation and all lineage.
    by_aircraft = {}
    for row in results:
        by_aircraft.setdefault(row['actual_aircraft_id'], []).append(row)
    for aid, rows in by_aircraft.items():
        rows.sort(key=lambda r: (r['actual_departure_utc'], r['dated_flight_id']))
        for previous, following in zip(rows, rows[1:]):
            assert previous['actual_arrival_utc'] <= following['actual_departure_utc']
            assert previous['destination_airport_id'] == following['origin_airport_id']
        aircraft = state['aircraft'][aid]
        if aircraft['status'] == 'PARKED':
            assert aircraft['current_airport_id'] == rows[-1]['destination_airport_id']
    for event in state['event_history'].values():
        if event['event_type'] != 'DAILY_BOOKING_CHECKPOINT':
            continue
        for pending in state['pending_events'].values():
            assert not (pending['event_type'] == 'QUARTERLY_PUBLICATION'
                        and pending['due_at_utc'] <= event['due_at_utc'])
    return dict(world_validation=True, unique_operations_settlements=True,
                passenger_conservation_lineage=True, aircraft_chronology_position=True,
                publication_before_booking=True,
                carried_passengers=sum(r['carried_passenger_count'] for r in results),
                transactions=dict(Counter(t['source_type'] for t in state['transactions'].values())),
                publication_boundaries=[dict(event_id=e['event_id'], due=e['due_at_utc'],
                    status=e['status'], payload=e['payload']) for e in state['event_history'].values()
                    if e['event_type'] == 'QUARTERLY_PUBLICATION'],
                booked_passengers=sum(b['passenger_count'] for b in state['bookings'].values()))


def measure(session, target, budget, heartbeat=None):
    before = set(session.world['world_state']['event_history'])
    start = perf_counter()
    report = None
    next_heartbeat = 60
    status = 'MEASUREMENT_BUDGET'
    try:
        with patch('app.session.begin_resolution', constrained_resolution):
            session.begin_advance_to(target)
        while session.advancing:
            elapsed = perf_counter() - start
            if budget is not None and elapsed >= budget:
                break
            report = session.advance_tick()
            if report is not None:
                status = ('COMPLETED' if report.result.succeeded
                          and session.world['simulation']['time_utc'] == target else 'ENGINE_STOP')
            if heartbeat and elapsed >= next_heartbeat:
                heartbeat(dict(elapsed_s=elapsed, reached=session.world['simulation']['time_utc'],
                               events=len(session.world['world_state']['event_history'])-len(before)))
                next_heartbeat = elapsed + 60
    finally:
        session.cancel_advance()
    elapsed = perf_counter() - start
    events = [e for k, e in session.world['world_state']['event_history'].items() if k not in before]
    return dict(status=status, elapsed_s=elapsed, target=target,
                reached=session.world['simulation']['time_utc'], requests=1, retries=0,
                events=len(events), event_types=dict(Counter(e['event_type'] for e in events)),
                publication_boundaries=[dict(event_id=e['event_id'], due=e['due_at_utc'],
                    status=e['status'], payload=e['payload']) for e in events
                    if e['event_type'] == 'QUARTERLY_PUBLICATION'],
                diagnostic=repr(report.result.failure) if report and report.result.failure else None,
                failure_code=report.result.failure.code if report and report.result.failure else None,
                current_utc_fully_resolved=not any(e['due_at_utc'] <= session.world['simulation']['time_utc']
                    for e in session.world['world_state']['pending_events'].values()),
                peak_process_working_set_bytes=existing.memory_bytes())


def checkpoint(session, path):
    start = perf_counter()
    before = existing.digest(session.world)
    session.save_manual()
    session.load_saved(session.career_id)
    assert existing.digest(session.world) == before
    assert session.world['simulation']['clock_state'] == 'PAUSED'
    existing.valid(session.world)
    save_load_s = perf_counter()-start
    path.write_text(json.dumps(session.world), encoding='utf-8')
    return dict(save_load_s=save_load_s, checkpoint_io_s=perf_counter()-start,
                save_load_exact_paused=True)


def run(root, size, budget, repeat=0, setup_budget=None, request_days=7):
    root = safe_root(root)
    root.mkdir(parents=True, exist_ok=True)
    source_path = root / f'operating-source-{size}.json'
    setup_path = root / f'operating-setup-{size}.json'
    if source_path.exists():
        world = json.loads(source_path.read_text(encoding='utf-8'))
        setup = json.loads(setup_path.read_text(encoding='utf-8'))
        existing.valid(world)
        assert existing.digest(world) == setup['audit']['hash']
    else:
        world, setup = existing.build(size, root, 0, source_only=True, start_time=START)
        construction_s = setup['setup_s']
        with tempfile.TemporaryDirectory(prefix='at058-warmup-') as saves:
            session = existing.session_for(world, saves)
            try:
                warmup = measure(session, OPERATING_START, setup_budget,
                    lambda row: print(json.dumps(dict(stage='warmup', fleet=size, **row)), flush=True))
                setup['warmup'] = warmup
                setup['construction_s'] = construction_s
                setup['setup_s'] = construction_s + warmup['elapsed_s']
                setup['warmup_checks'] = correctness(session.world)
                setup['audit'] = existing.audit(session.world)
                if warmup['status'] != 'COMPLETED':
                    setup['status'] = 'NO_OPERATING_FIXTURE'
                    setup['checkpoint'] = checkpoint(session, root/f'operating-incomplete-{size}-checkpoint.json')
                    (root/f'operating-incomplete-{size}.json').write_text(json.dumps(setup, indent=2), encoding='utf-8')
                    print(json.dumps(setup), flush=True)
                    return setup
                assert setup['audit']['counts']['bookings'] > 0
                assert setup['audit']['counts']['flight_results'] > 0
                world = session.world
            finally:
                session.close()
        source_path.write_text(json.dumps(world), encoding='utf-8')
        setup_path.write_text(json.dumps(setup, indent=2), encoding='utf-8')
    print(json.dumps(dict(stage='fixture', **setup)), flush=True)
    started = world['simulation']['time_utc']
    assert started == OPERATING_START
    target = format_utc(parse_canonical_utc(started) + timedelta(days=90))
    label = f'quiet-{size}-{repeat}'
    with tempfile.TemporaryDirectory(prefix='at058-save-') as saves, ExitStack() as stack:
        session = existing.session_for(world, saves)
        stack.callback(session.close)
        requests = []
        workflow_start = perf_counter()
        while session.world['simulation']['time_utc'] < target:
            bounded_target = min(target, format_utc(
                parse_canonical_utc(session.world['simulation']['time_utc']) + timedelta(days=request_days)))
            sample = measure(session, bounded_target, budget,
                lambda row: print(json.dumps(dict(stage='progress', fleet=size,
                    request=len(requests)+1, **row)), flush=True))
            requests.append(sample)
            if sample['status'] != 'COMPLETED':
                break
            assert sample['current_utc_fully_resolved']
            print(json.dumps(dict(stage='bounded_request_complete', fleet=size,
                request=len(requests), **sample)), flush=True)
        result = dict(requests[-1])
        event_types = Counter()
        for sample in requests:
            event_types.update(sample['event_types'])
        result.update(elapsed_s=sum(r['elapsed_s'] for r in requests),
            workflow_elapsed_s=perf_counter()-workflow_start,
            requests=len(requests), retries=0, target=target,
            request_days=request_days,
            events=sum(r['events'] for r in requests), event_types=dict(event_types),
            publication_boundaries=[b for r in requests for b in r['publication_boundaries']],
            advancement_requests=requests)
        result['days'] = (parse_canonical_utc(result['reached'])-parse_canonical_utc(started)).total_seconds()/86400
        result['audit'] = existing.audit(session.world)
        result['source_audit'] = setup['audit']
        result['activity_changes'] = {key: count-setup['audit']['counts'][key]
                                     for key, count in result['audit']['counts'].items()}
        result['checks'] = correctness(session.world)
        result['checkpoint'] = checkpoint(session, root/f'{label}-checkpoint.json')
        result.update(fleet=size, setup=setup, budget_s=budget, repeat=repeat,
                      environment=dict(python=platform.python_version(), platform=platform.platform(),
                                       processor=platform.processor()),
                      baseline='5f70abd51a822bc99295011cee1d5abc35756569')
        (root/f'{label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--fleet', type=int, choices=(1, 10, 25, 50), required=True)
    parser.add_argument('--budget', type=float, default=0,
                        help='simulation seconds; 0 means no wall-time cancellation')
    parser.add_argument('--repeat', type=int, default=0)
    parser.add_argument('--setup-budget', type=float, default=0)
    parser.add_argument('--request-days', type=int, default=7)
    args = parser.parse_args()
    if args.budget < 0 or args.setup_budget < 0 or args.request_days < 1:
        parser.error('budgets must be nonnegative and request days positive')
    run(args.root, args.fleet, args.budget or None, args.repeat,
        args.setup_budget or None, args.request_days)


if __name__ == '__main__':
    main()
