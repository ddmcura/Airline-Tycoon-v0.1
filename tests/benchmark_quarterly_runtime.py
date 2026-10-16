"""B2 opt-in measurements: real temporary careers, bounded complete-event stops.

python -B -m tests.benchmark_quarterly_runtime --root <temporary path> --build
python -B -m tests.benchmark_quarterly_runtime --root <same path> --label baseline
Never use real Saves. Fixtures are immutable JSON with digest/audit sidecars.
"""
import argparse
from collections import Counter
from copy import deepcopy
import cProfile
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import platform
import pstats
import statistics
import tempfile
from time import perf_counter

from app.session import Stage1Session
from game.world_state import validate_world
from game.world_state.timestamps import parse_canonical_utc, format_utc
from tests.profile_ph_runtime import memory_bytes


def digest(world):
    return hashlib.sha256(json.dumps(world, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def valid(world):
    report = validate_world(world)
    if not report.is_valid:
        raise ValueError(str(report.errors[:3]))


def audit(world):
    state = world['world_state']
    return dict(time=world['simulation']['time_utc'], hash=digest(world),
        counts={k: len(state[k]) for k in ('aircraft', 'connections', 'weekly_plans',
            'services', 'bookings', 'itineraries', 'dated_flights', 'flight_results',
            'transactions', 'event_history', 'pending_events')},
        events=dict(Counter(e['event_type'] for e in state['event_history'].values())),
        published=[p['quarter_id'] for p in state['weekly_plans'].values()
            if p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None])


def session_for(world, root):
    session = Stage1Session(save_root=root, runtime_clock=lambda: 0)
    session.world = deepcopy(world)
    session._ensure_runtime()
    session._bind_owned_reads()
    session.career_id = session.save_store.new_career_id()
    return session


def advance(session, target, budget):
    start = perf_counter()
    before = set(session.world['world_state']['event_history'])
    session.begin_advance_to(target)
    report = None
    status = 'INCOMPLETE_BUDGET'
    while session.advancing:
        if perf_counter() - start >= budget:
            session.cancel_advance()  # Only a completed committed prefix is exposed.
            break
        report = session.advance_tick()
        if report is not None:
            status = ('COMPLETED' if report.result.succeeded
                and session.world['simulation']['time_utc'] == target else 'BLOCKED')
    elapsed = perf_counter() - start
    events = [e for k, e in session.world['world_state']['event_history'].items() if k not in before]
    return dict(status=status, wall_s=elapsed, target=target,
        reached=session.world['simulation']['time_utc'], events=len(events),
        event_types=dict(Counter(e['event_type'] for e in events)),
        peak_bytes=memory_bytes(), hash=digest(session.world),
        diagnostic=str(report) if status == 'BLOCKED' else None)


def build(size, root, budget, *, source_only=False,
          start_time='2026-08-31T00:00:00Z'):
    """Private constructor-built draft, real paid routes/acquisition/publication/events."""
    from game.world_state.stage1_scenario import create_stage1_new_game
    from game.aircraft_market.acquisition import preview_purchase, purchase_aircraft
    from game.aircraft_market.reference_catalog import PH_AIRCRAFT_CATALOG_VERSION
    from game.economy.acquisition import purchase_accounts
    from game.economy.fare_reference import suggested_economy_fare_minor
    from game.route_management.establishment import quote_route, apply_route
    from game.scheduling.quarterly_backend import enable_quarterly_backend_for_testing
    from game.scheduling import WeeklyDraft
    from game.scheduling.local_time import airport_zone
    from game.scheduling.timing import timing_bounds
    from game.world_state.quarterly_construction import create_service, allocate_service_slot, create_weekly_plan
    from game.scheduling.quarterly_publication import PublishQuarterlyPlan
    from game.scheduling.quarterly_commands import prepare_quarterly_command, apply_quarterly_command

    start = perf_counter()
    with tempfile.TemporaryDirectory() as temporary:
        scenario = json.loads(Path('Data/Stage1/philippines_v1.json').read_text(encoding='utf-8'))
        scenario['start_time_utc'] = start_time
        path = Path(temporary) / 'scenario.json'
        path.write_text(json.dumps(scenario), encoding='utf-8')
        world = create_stage1_new_game(scenario_id='stage1-philippines-v1', ceo_display_name='Benchmark',
            airline_display_name='Quarterly benchmark', base_airport_reference_code='MNL', reference_path=path)
    state = world['world_state']; owner = state['player']['primary_airline_id']
    ports = {a['reference_code']: k for k, a in state['airports'].items()}
    # Declared test-only capital; all subsequent acquisitions and route journals are real.
    purchase_accounts(state, owner)['cash']['balance_minor'] = 10**14
    for _ in range(size - 1):
        purchase_aircraft(world, preview_purchase(world, airline_id=owner, model_id='airbus-a320neo',
            catalog_version=PH_AIRCRAFT_CATALOG_VERSION, delivery_airport_id=ports['MNL']))
    enable_quarterly_backend_for_testing(world)
    for dest in ('DVO', 'CEB', 'ILO', 'BCD', 'PPS'):
        apply_route(world, quote_route(world, airline_id=owner, hub_airport_id=ports['MNL'],
            origin_airport_id=ports['MNL'], destination_airport_id=ports[dest]))
    slots = []
    for index, aircraft in enumerate(sorted(world['world_state']['aircraft'])):
        draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
        for cycle in range(2):
            dest = ports[('DVO', 'CEB', 'ILO', 'BCD', 'PPS')[(index + cycle) % 5]]
            departure = parse_canonical_utc('2026-10-01T01:00:00Z') + timedelta(hours=cycle*6, minutes=index*2)
            draft.add(ports['MNL'], dest, departure_utc=format_utc(departure),
                fare_minor=suggested_economy_fare_minor(world['world_state'], ports['MNL'], dest))
            draft.add_return(fare_minor=suggested_economy_fare_minor(world['world_state'], dest, ports['MNL']))
        for leg in draft.legs:
            state = world['world_state']; origin = leg['origin_airport_id']; dest = leg['destination_airport_id']
            service = create_service(world, owner, flight_number_prefix='BM')
            number = allocate_service_slot(world, service)
            connection = next(c['connection_id'] for c in state['connections'].values()
                if c['airline_id'] == owner and (state['directional_markets'][c['market_id']]['origin_airport_id'],
                   state['directional_markets'][c['market_id']]['destination_airport_id']) == (origin, dest))
            local = parse_canonical_utc(leg['departure_utc']).astimezone(airport_zone(state, origin))
            slots.append(dict(service_id=service, slot_number=number, weekdays=list(range(7)),
                departure_local_time=local.strftime('%H:%M:%S'), departure_local_fold=0,
                origin_airport_id=origin, destination_airport_id=dest, planned_aircraft_id=aircraft,
                connection_id=connection, service_type='PASSENGER',
                capacity=state['aircraft'][aircraft]['configuration']['economy_capacity'],
                fare_offer={'currency': 'USD', 'amount_minor': leg['fare_minor']},
                planning_timing=deepcopy(leg['planning_timing'])))
    pid = create_weekly_plan(world, owner, '2026-Q4', slots=slots)
    valid(world)
    root.mkdir(parents=True, exist_ok=True)
    (root/f'publication-{size}.json').write_text(json.dumps(world), encoding='utf-8')
    request = PublishQuarterlyPlan('MANUAL', '2026-Q4', pid, 1, world['simulation']['time_utc'])
    t = perf_counter(); prepared = prepare_quarterly_command(world, airline_id=owner, request=request)
    prepare_s = perf_counter() - t
    assert prepared.succeeded, prepared.issues
    t = perf_counter(); result = apply_quarterly_command(world, airline_id=owner, prepared=prepared.prepared)
    apply_s = perf_counter() - t
    assert result.succeeded, result.issues
    if source_only:
        valid(world)
        return world, dict(fleet=size, setup_s=perf_counter()-start,
            publication_prepare_s=prepare_s, publication_apply_s=apply_s,
            audit=audit(world))
    with tempfile.TemporaryDirectory() as temporary:
        session = session_for(world, temporary)
        warm = advance(session, '2026-10-02T03:00:00Z', budget)
        if warm['status'] != 'COMPLETED':
            record = dict(fleet=size, setup_s=perf_counter()-start, publication_prepare_s=prepare_s,
                publication_apply_s=apply_s, warmup=warm, fixture='NOT_READY')
            # This prefix is recovery evidence, never silently substituted as a ready workload.
            valid(session.world)
            (root/f'incomplete-{size}.json').write_text(json.dumps(session.world), encoding='utf-8')
            (root/f'incomplete-{size}-audit.json').write_text(json.dumps(record), encoding='utf-8')
            session.close()
            return record
        world = session.world
        valid(world); info = audit(world)
        assert info['counts']['bookings'] and info['counts']['flight_results'], info
        session.close()
    root.mkdir(parents=True, exist_ok=True)
    (root/f'fleet-{size}.json').write_text(json.dumps(world), encoding='utf-8')
    record = dict(fleet=size, setup_s=perf_counter()-start, publication_prepare_s=prepare_s,
        publication_apply_s=apply_s, warmup=warm, audit=info, fixture='READY')
    (root/f'fleet-{size}-audit.json').write_text(json.dumps(record), encoding='utf-8')
    return record


def summarize(samples):
    values = [s['wall_s'] for s in samples]
    return dict(median_s=statistics.median(values), min_s=min(values), max_s=max(values), samples=samples)


def components(size, root, repeats):
    """Explicitly preparatory measurements; no claim of operating-career throughput."""
    from game.scheduling.quarterly_commands import prepare_quarterly_command, apply_quarterly_command
    from game.scheduling.quarterly_publication import PublishQuarterlyPlan
    from game.scheduling.quarterly_supply import QuarterlySupply
    from game.scheduling.quarterly_backend import reconcile_candidate
    path = root/f'publication-{size}.json'
    if not path.exists(): return dict(fleet=size, status='NO_PUBLICATION_SOURCE')
    source = json.loads(path.read_text(encoding='utf-8')); valid(source)
    owner = source['world_state']['player']['primary_airline_id']
    pid = next(iter(source['world_state']['weekly_plans']))
    samples = []
    for _ in range(repeats):
        world = deepcopy(source)
        t = perf_counter(); prepared = prepare_quarterly_command(world, airline_id=owner,
            request=PublishQuarterlyPlan('MANUAL', '2026-Q4', pid, 1, world['simulation']['time_utc']))
        prepare_s = perf_counter()-t; assert prepared.succeeded, prepared.issues
        t = perf_counter(); result = apply_quarterly_command(world, airline_id=owner, prepared=prepared.prepared)
        apply_s = perf_counter()-t; assert result.succeeded, result.issues
        t = perf_counter(); changed = reconcile_candidate(world); reconciliation_s = perf_counter()-t
        samples.append(dict(prepare_s=prepare_s, apply_s=apply_s, reconciliation_s=reconciliation_s,
            changed=changed, hash=digest(world), peak_bytes=memory_bytes()))
    assert len({s['hash'] for s in samples}) == 1
    # Compare lazy resolution versus transient per-date prepared windows, without persisting rows.
    horizons = {}
    for days in (1, 7, 30, 90):
        values = []
        for _ in range(repeats):
            supply = QuarterlySupply(world)
            t = perf_counter(); count = 0
            for offset in range(days):
                count += len(supply.on_date((parse_canonical_utc('2026-10-02T00:00:00Z')
                    + timedelta(days=offset)).date().isoformat()))
            values.append(dict(wall_s=perf_counter()-t, rows=count, peak_bytes=memory_bytes()))
        horizons[str(days)] = summarize(values)
    result = dict(fleet=size, status='PREPARATORY_ONLY', samples=samples, horizons=horizons)
    (root/f'components-{size}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def run(size, root, label, repeats, budget, profile):
    path = root/f'fleet-{size}.json'
    if not path.exists(): return dict(fleet=size, status='NO_READY_FIXTURE')
    base = json.loads(path.read_text(encoding='utf-8')); valid(base)
    assert digest(base) == json.loads((root/f'fleet-{size}-audit.json').read_text())['audit']['hash']
    result = dict(fleet=size, label=label, audit=audit(base), advances={}, lookups=[], save_load=[])
    for days in (1, 7, 30, 45, 90):
        samples = []
        for _ in range(repeats):
            with tempfile.TemporaryDirectory() as temporary:
                session = session_for(base, temporary)
                target = format_utc(parse_canonical_utc(base['simulation']['time_utc']) + timedelta(days=days))
                sample = advance(session, target, budget); samples.append(sample)
                session.close()
        result['advances'][str(days)] = summarize(samples)
        print(json.dumps(dict(label=label, fleet=size, days=days, **result['advances'][str(days)])), flush=True)
    from game.scheduling.quarterly_supply import QuarterlySupply
    for _ in range(repeats):
        t = perf_counter(); supply = QuarterlySupply(base); rows = supply.on_date('2026-10-03')
        result['lookups'].append(dict(wall_s=perf_counter()-t, rows=len(rows), peak_bytes=memory_bytes()))
        with tempfile.TemporaryDirectory() as temporary:
            session = session_for(base, temporary)
            t = perf_counter(); session.save_manual(); save_s = perf_counter()-t
            t = perf_counter(); session.load_saved(session.career_id); load_s = perf_counter()-t
            assert digest(session.world) == digest(base)
            result['save_load'].append(dict(save_s=save_s, load_s=load_s, peak_bytes=memory_bytes()))
            session.close()
    if profile:
        with tempfile.TemporaryDirectory() as temporary:
            session = session_for(base, temporary)
            profiler = cProfile.Profile(); profiler.enable()
            diagnostic = advance(session, format_utc(parse_canonical_utc(base['simulation']['time_utc'])
                + timedelta(days=1)), budget)
            profiler.disable(); profiler.dump_stats(str(root/f'{label}-{size}.prof'))
            pstats.Stats(profiler).strip_dirs().sort_stats('cumulative').print_stats(25)
            result['profile_run'] = diagnostic; session.close()
    (root/f'{label}-{size}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--fleets', nargs='+', type=int, default=[1, 10, 25, 50])
    parser.add_argument('--build', action='store_true'); parser.add_argument('--label', default='baseline')
    parser.add_argument('--repeats', type=int, default=3); parser.add_argument('--budget', type=float, default=30)
    parser.add_argument('--setup-budget', type=float, default=600); parser.add_argument('--profile', action='store_true')
    parser.add_argument('--components', action='store_true')
    args = parser.parse_args()
    protected = (Path(__file__).resolve().parents[1]/'Saves').resolve()
    if args.root.resolve() == protected or protected in args.root.resolve().parents:
        parser.error('benchmark files must not use the real Saves directory')
    if args.repeats < 1 or any(n < 1 for n in args.fleets) or args.budget < 0 or args.setup_budget < 0:
        parser.error('positive fleet/repeats and nonnegative budgets required')
    print(json.dumps(dict(environment=platform.platform(), python=platform.python_version(),
        processor=platform.processor(), label=args.label)), flush=True)
    for size in args.fleets:
        value = (components(size, args.root, args.repeats) if args.components else
            build(size, args.root, args.setup_budget) if args.build else run(size, args.root,
            args.label, args.repeats, args.budget, args.profile))
        print(json.dumps(value), flush=True)


if __name__ == '__main__': main()
