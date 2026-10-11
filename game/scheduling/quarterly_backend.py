"""Dormant isolated quarterly operational dispatch and sold-row construction."""
from copy import deepcopy
from datetime import timedelta

from game.world_state.quarterly_consumers import MODE, quarterly_mode, projected_flight
from game.world_state.timestamps import parse_canonical_utc, format_utc
from game.world_state.ids import allocate_id
from game.world_state.validation import validate_world
from .quarterly_supply import QuarterlySupply

EVENT_TYPE = 'QUARTERLY_DISPATCH'
CONTRACT = 'QUARTERLY_DISPATCH_V1'


def materialize_candidate(envelope, projected, *, _aliases=None):
    """One caller-owned occurrence alias; no publication/Booking cache persists."""
    from game.simulation.kernel import schedule_event
    from game.world_state.fulfilment_validation import _event_payload
    from game.world_state.schema import FLIGHT_DEPARTURE_EVENT_TYPE, FLIGHT_DEPARTURE_EVENT_CONTRACT
    world = envelope['world_state']
    key = projected['occurrence_key']
    if _aliases is None:
        existing = [f for f in world['dated_flights'].values() if f['occurrence_key'] == key]
    else:
        identity = _aliases.get(key)
        existing = [] if identity is None else [world['dated_flights'][identity]]
    if existing:
        if (len(existing) != 1 or existing[0]['occurrence_key'] != key
                or existing[0]['quarterly_lineage'] != projected['quarterly_lineage']):
            raise ValueError('occurrence alias/publication collision')
        return existing[0]['dated_flight_id']
    row = deepcopy(projected)
    flight_id = allocate_id(envelope, 'dated_flight')
    row['dated_flight_id'] = flight_id
    world['dated_flights'][flight_id] = row
    if _aliases is not None:
        _aliases[key] = flight_id
    envelope['simulation']['operation_revisions'][flight_id] = row['operation_revision']
    schedule_event(envelope, event_type=FLIGHT_DEPARTURE_EVENT_TYPE,
        due_at_utc=row['scheduled_off_block_utc'], owner_type='dated_flight', owner_id=flight_id,
        operation_revision=row['operation_revision'], priority=100,
        payload=_event_payload(row, FLIGHT_DEPARTURE_EVENT_CONTRACT))
    return flight_id


def next_occurrence(envelope, aircraft_id, *, after_utc=None):
    """At most eight local-date probes per published frequency, not a quarter table."""
    from game.utils.quarters import parse_quarter_id
    from game.world_state.timezones import load_named_timezone
    supply = QuarterlySupply(envelope, sales=False)
    now = parse_canonical_utc(after_utc or envelope['simulation']['time_utc'])
    candidates = []
    for plan, revision, slot in supply.slots:
        if slot['planned_aircraft_id'] != aircraft_id:
            continue
        quarter = parse_quarter_id(plan['quarter_id'])
        if quarter.end_exclusive_utc <= now:
            continue
        zone = load_named_timezone(supply.world['airports'][slot['origin_airport_id']]['timezone'])
        day = max(now, quarter.start_utc).astimezone(zone).date()
        for offset in range(8):
            operating = day + timedelta(days=offset)
            if operating.weekday() not in slot['weekdays']:
                continue
            lineage = dict(weekly_plan_id=plan['weekly_plan_id'], revision=plan['current_revision'],
                service_id=slot['service_id'], slot_number=slot['slot_number'],
                operating_date=operating.isoformat(), published_at_utc=revision['published_at_utc'])
            try:
                row = projected_flight(supply.world, lineage)
            except ValueError as exc:
                if str(exc) == 'date outside published UTC quarter':
                    continue
                raise
            if parse_canonical_utc(row['scheduled_off_block_utc']) < now:
                continue
            existing = supply.rows.get(row['occurrence_key'])
            if existing is not None and existing['status'] != 'PLANNED':
                continue
            candidates.append(row)
            break
    return min(candidates, key=lambda f: (f['scheduled_off_block_utc'], f['occurrence_key'])) if candidates else None


def reconcile_candidate(envelope, *, after_utc=None):
    from game.simulation.kernel import schedule_event
    if not quarterly_mode(envelope):
        return False
    changed = False
    from game.world_state.quarterly_boundary import enroll_candidate, obligations
    owners = {p['airline_id'] for p in envelope['world_state']['weekly_plans'].values()}
    for owner in sorted(owners - set(obligations(envelope))):
        enroll_candidate(envelope, owner)
        changed = True
    for aircraft_id in sorted(envelope['world_state']['aircraft']):
        row = next_occurrence(envelope, aircraft_id, after_utc=after_utc)
        if row is None:
            continue
        payload = {'contract': CONTRACT, 'quarterly_lineage': row['quarterly_lineage']}
        revision = envelope['simulation']['operation_revisions'].get(aircraft_id, 0)
        if any(e['event_type'] == EVENT_TYPE and e['owner_id'] == aircraft_id
               and e['payload'] == payload and e['operation_revision'] == revision
               for e in envelope['world_state']['pending_events'].values()):
            continue
        schedule_event(envelope, event_type=EVENT_TYPE, due_at_utc=row['scheduled_off_block_utc'],
            owner_type='aircraft', owner_id=aircraft_id, operation_revision=revision,
            priority=90, payload=payload)
        changed = True
    return changed


def reconcile(envelope):
    if not quarterly_mode(envelope):
        return
    initialize_handler()
    candidate = deepcopy(envelope)
    if reconcile_candidate(candidate):
        report = validate_world(candidate)
        if not report.is_valid:
            raise ValueError(report.errors[0].message)
        from game.simulation.kernel import _replace_envelope
        _replace_envelope(envelope, candidate)


def _dispatch(context):
    if not quarterly_mode(context.envelope):
        raise ValueError('quarterly dispatch requires exclusive quarterly authority')
    row = projected_flight(context.envelope['world_state'], context.payload['quarterly_lineage'])
    if (row['planned_aircraft_id'] != context.event['owner_id']
            or row['scheduled_off_block_utc'] != context.envelope['simulation']['time_utc']):
        raise ValueError('dispatch does not match exact published assignment/time')
    materialize_candidate(context.envelope, row)
    reconcile_candidate(context.envelope,
        after_utc=format_utc(parse_canonical_utc(row['scheduled_off_block_utc']) + timedelta(seconds=1)))


def initialize_handler():
    from game.simulation.kernel import DEFAULT_EVENT_HANDLERS
    from game.simulation.execution_contracts import HandlerExecutionContract, ExecutionMode
    registry = DEFAULT_EVENT_HANDLERS
    current = registry.handler_for(EVENT_TYPE)
    if current is not None and current is not _dispatch:
        raise ValueError('conflicting quarterly dispatch handler')
    if current is None:
        registry.register(EVENT_TYPE, _dispatch)
    registry._execution_contracts[EVENT_TYPE] = HandlerExecutionContract(
        _dispatch, ExecutionMode.FENCE, 'quarterly-dispatch-strict-v1')


def enable_quarterly_backend_for_testing(envelope):
    """Isolated NEW-career capability; ordinary New/Load never enroll.

    Stage 3F's explicit development GUI entry may enroll a private new candidate.
    """
    report = validate_world(envelope)
    if not report.is_valid or envelope['simulation']['clock_state'] != 'PAUSED':
        raise ValueError('isolated new career requires valid paused source')
    if quarterly_mode(envelope):
        return
    world = envelope['world_state']
    if any(world[name] for name in ('schedule_definitions', 'dated_flights', 'itineraries',
                                  'bookings', 'active_aircraft_operations', 'flight_results')):
        raise ValueError('existing operational careers cannot be converted')
    checkpoints = world['booking_state']['booking_checkpoints']
    if (envelope['simulation']['time_utc'] != envelope['metadata']['world_created_at_utc']
            or world['demand_state']['processed_cohorts']
            or any(c['market_results'] or c['financial_transaction_ids'] for c in checkpoints.values())):
        raise ValueError('only an untouched empty new-career bootstrap may enroll')
    candidate = deepcopy(envelope)
    candidate['simulation']['operational_authority'] = MODE
    reconcile_candidate(candidate)
    report = validate_world(candidate)
    if not report.is_valid:
        raise ValueError(report.errors[0].message)
    initialize_handler()
    from game.simulation.kernel import _replace_envelope
    _replace_envelope(envelope, candidate)
