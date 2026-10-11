"""Detached bounded planning reads for the exclusive application owner.

These helpers do not validate arbitrary worlds or authorize commands. The session
establishes its existing validated read epoch before calling them.
"""
from copy import deepcopy
from datetime import date

from game.utils.quarters import quarter_containing, parse_quarter_id
from game.world_state.timestamps import format_utc
from game.world_state.quarterly_consumers import quarterly_mode
from game.world_state.quarterly_boundary import obligations, boundary, correction_target
from .quarterly_commands import _target
from .quarterly_readiness import publication_boundary
from .quarterly_publication import _baseline
from .service_identity import flight_number, plan_lifecycle
from .quarterly_occurrences import (
    QuarterlyOccurrenceReference, OccurrenceReadRequest, _project_times)


def page_options(offset, limit):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 128:
        raise ValueError('use a nonnegative offset and a page size from 1 to 128')


def planning_page(envelope, owner, *, plan_id=None, offset=0, limit=32):
    page_options(offset, limit)
    world = envelope['world_state']; now = envelope['simulation']['time_utc']
    target = _target(world, owner, now)
    entry = obligations(envelope).get(owner)
    fence = None if entry is None else dict(deepcopy(entry), due_at_utc=boundary(entry['next_quarter_id']))
    selected_quarter = entry['next_quarter_id'] if entry and entry['failure'] else target
    plans = sorted((p for p in world['weekly_plans'].values() if p['airline_id'] == owner),
                   key=lambda p: (p['quarter_id'], p['weekly_plan_id']))
    selected = next((p for p in plans if p['weekly_plan_id'] == plan_id), None) if plan_id else next(
        (p for p in plans if p['quarter_id'] == selected_quarter), None)
    if plan_id and selected is None:
        raise ValueError('selected plan is absent or belongs to another airline; refresh')
    if selected:
        selected_quarter = selected['quarter_id']
    baseline = _baseline(plans, parse_quarter_id(selected_quarter))
    inherited = [] if baseline is None else [s for s in baseline['revisions'][str(baseline['current_revision'])]['slots']
        if world['services'][s['service_id']]['retired_at_utc'] is None]
    current = selected['revisions'][str(selected['current_revision'])] if selected else None
    published = current['published_at_utc'] if current else None
    slots = current['slots'] if current else list(inherited)
    editable = published is None and (selected_quarter == target or correction_target(envelope, owner, selected_quarter))
    if entry and entry['failure']:
        editable = published is None and correction_target(envelope,owner,selected_quarter)
    rows = []
    for slot in slots[offset:offset + limit]:
        row = deepcopy(slot)
        row.update(flight_number=flight_number(world, slot['service_id']),
            retired=world['services'][slot['service_id']]['retired_at_utc'] is not None,
            origin_code=world['airports'][slot['origin_airport_id']]['reference_code'],
            destination_code=world['airports'][slot['destination_airport_id']]['reference_code'],
            origin_timezone=world['airports'][slot['origin_airport_id']]['timezone'],
            aircraft_registration=world['aircraft'][slot['planned_aircraft_id']]['display_registration'])
        rows.append(row)
    return dict(quarterly=quarterly_mode(envelope), time_utc=now,
        flight_number_prefix=world['service_numbering'].get(owner,{}).get('flight_number_prefix'),
        binding_clock=envelope['simulation']['clock_state'],
        operating_quarter=quarter_containing(now).quarter_id, target_quarter=target,
        selected_quarter=selected_quarter, plan_id=None if selected is None else selected['weekly_plan_id'],
        revision=0 if selected is None else selected['current_revision'], published_at_utc=published,
        deadline_utc=format_utc(publication_boundary(parse_quarter_id(selected_quarter))),
        baseline=None if baseline is None else dict(plan_id=baseline['weekly_plan_id'],
            quarter_id=baseline['quarter_id'], revision=baseline['current_revision']),
        carry_forward=current is None and baseline is not None, editable=editable,
        total=len(slots), offset=offset, limit=limit, rows=rows, fence=fence,
        # Navigation is bounded separately from service rows; historical selection
        # accepts an explicit stable plan ID through the same owner check.
        plans=[dict(plan_id=p['weekly_plan_id'], quarter_id=p['quarter_id'],
            revision=p['current_revision'], status=plan_lifecycle(p, now)) for p in plans[-64:]],
        services=[dict(service_id=s['service_id'], flight_number=flight_number(world,s['service_id']),
            retired=s['retired_at_utc'] is not None) for s in sorted(world['services'].values(),key=lambda s:s['service_id'])
            if s['airline_id'] == owner][-128:])


def slot_input(envelope, owner, *, aircraft_id, origin_id, destination_id,
               weekdays, departure_local_time, fare_minor, service_type='PASSENGER', fold=0):
    world = envelope['world_state']; aircraft = world['aircraft'].get(aircraft_id)
    if aircraft is None or aircraft['airline_id'] != owner:
        raise ValueError('select an owned aircraft')
    if origin_id not in world['airports'] or destination_id not in world['airports']:
        raise ValueError('select existing airports')
    connection = None
    if service_type == 'PASSENGER':
        for c in world['connections'].values():
            market = world['directional_markets'][c['market_id']]
            if c['airline_id'] == owner and c['status'] == 'ACTIVE' and (
                    market['origin_airport_id'],market['destination_airport_id']) == (origin_id,destination_id):
                connection = c['connection_id']; break
        if connection is None:
            raise ValueError('this directional route has no active connection; select an established route')
    return dict(planned_aircraft_id=aircraft_id, origin_airport_id=origin_id,
        destination_airport_id=destination_id, weekdays=list(weekdays),
        departure_local_time=departure_local_time, departure_local_fold=fold,
        service_type=service_type, connection_id=connection,
        capacity=aircraft['configuration']['economy_capacity'] if service_type == 'PASSENGER' else 0,
        fare_offer=dict(currency=world['airlines'][owner]['base_currency'],
                        amount_minor=fare_minor if service_type == 'PASSENGER' else 0))


def day_requests(envelope, owner, plan_id, operating_date, *, offset=0, limit=32):
    page_options(offset, limit)
    day = date.fromisoformat(operating_date)
    if day.isoformat() != operating_date:
        raise ValueError('use a canonical origin-local date')
    world = envelope['world_state']; plan = world['weekly_plans'].get(plan_id)
    if not plan or plan['airline_id'] != owner:
        raise ValueError('select an owned published plan')
    revision = plan['current_revision']; current = plan['revisions'][str(revision)]
    if current['published_at_utc'] is None:
        raise ValueError('select a published plan')
    quarter = parse_quarter_id(plan['quarter_id']); requests = []
    for slot in current['slots']:
        if day.weekday() not in slot['weekdays']:
            continue
        departure = _project_times(world,slot,operating_date)[0]
        if quarter.start_utc <= departure < quarter.end_exclusive_utc:
            requests.append(OccurrenceReadRequest(QuarterlyOccurrenceReference(plan_id,revision,
                slot['service_id'],slot['slot_number'],operating_date),revision,current['published_at_utc']))
    return tuple(requests[offset:offset+limit]), len(requests)
