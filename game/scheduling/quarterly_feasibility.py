"""Disposable complete aircraft-chain proof for dormant quarterly commands.

Planning-only repositioning uses the existing proof; it creates no movement.
Private 2D indexes narrow discovery only; no persisted occurrence or certificate.
"""
from datetime import timedelta
from types import SimpleNamespace

from game.utils.quarters import parse_quarter_id
from game.world_state.planning_reference import planning_snapshot, _PlanningReferences
from game.world_state.timestamps import parse_canonical_utc
from .local_time import airport_zone, local_departure
from .planning_feasibility import PlanningFeasibility
from .publication import _expand_schedule
from .service_identity import occurrence_identity
from .timing import flight_reservation, timing_bounds


def temporal_sources(envelope, aircraft_ids, *, index=None):
    """Reconstruct relevant current facts, including absence/insertion coverage.

    Private owned indexes narrow discovery; the reference fallback enumerates
    shared mappings. Booking/accounting is not copied. Full gates remain separate.
    """
    state = envelope['world_state']
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    if index is not None:
        from .quarterly_indexes import QuarterlyDependencyIndex
        if type(index) is not QuarterlyDependencyIndex or not index.matches(envelope):
            raise ValueError('stale dependency index')
        def selected(table, relation, live=False):
            ids = set()
            for aid in aircraft_ids:
                ids.update(index.live_plans(relation, aid) if live else index.ids(relation, aid))
            return {identity: state[table][identity] for identity in sorted(ids)}
        plans = selected('weekly_plans', 'aircraft_plans', True)
        schedules = selected('schedule_definitions', 'aircraft_schedules')
        operations = selected('active_aircraft_operations', 'aircraft_operations')
        ids = {fid for aid in aircraft_ids for fid in index.relevant_flights(aid)}
        flights = {fid: state['dated_flights'][fid] for fid in sorted(ids)}
    else:
        plans = state['weekly_plans']; schedules = state['schedule_definitions']
        operations = state['active_aircraft_operations']; flights = state['dated_flights']
    facts = {
        'configuration': envelope['simulation']['configuration']['scheduling'],
        'aircraft': {aid: state['aircraft'][aid] for aid in sorted(aircraft_ids)},
        'plans': {pid: {'quarter_id': p['quarter_id'], 'current_revision': p['current_revision'],
                       'revision': p['revisions'][str(p['current_revision'])]}
                  for pid, p in plans.items()
                  if parse_quarter_id(p['quarter_id']).end_exclusive_utc > now
                  and any(s['planned_aircraft_id'] in aircraft_ids
                         for s in p['revisions'][str(p['current_revision'])]['slots'])},
        'schedules': {sid: s for sid, s in schedules.items()
                      if any(r['planned_aircraft_id'] in aircraft_ids for r in s['revisions'].values())},
        'flights': {fid: f for fid, f in flights.items()
                    if f['planned_aircraft_id'] in aircraft_ids
                    and f['status'] not in {'SUPERSEDED', 'CANCELLED'}
                    and (flight_reservation(state, f)[1] > now or
                         parse_canonical_utc(f['scheduled_in_block_utc']) + timedelta(seconds=
                         envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']) > now)},
        'operations': {oid: op for oid, op in operations.items()
                       if op['actual_aircraft_id'] in aircraft_ids}}
    airports = {state['aircraft'][aid]['current_airport_id'] for aid in aircraft_ids}
    for plan in facts['plans'].values():
        for slot in plan['revision']['slots']:
            if slot['planned_aircraft_id'] in aircraft_ids:
                airports.update((slot['origin_airport_id'], slot['destination_airport_id']))
    for schedule in facts['schedules'].values():
        for revision in schedule['revisions'].values():
            if revision['planned_aircraft_id'] in aircraft_ids:
                airports.update((revision['origin_airport_id'], revision['destination_airport_id']))
    for flight in facts['flights'].values():
        airports.update((flight['origin_airport_id'], flight['destination_airport_id']))
    facts['airports'] = {identity: state['airports'][identity] for identity in sorted(airports - {None})}
    services = {slot['service_id'] for plan in facts['plans'].values()
                for slot in plan['revision']['slots'] if slot['planned_aircraft_id'] in aircraft_ids}
    if index is not None:
        ids = {pid for sid in services for pid in index.live_plans('service_plans', sid)}
        lineage_plans = {pid: state['weekly_plans'][pid] for pid in sorted(ids)}
    else:
        lineage_plans = state['weekly_plans']
    facts['lineage'] = {pid: {'quarter_id': plan['quarter_id'], 'current_revision': plan['current_revision'],
                            'slots': [s for s in plan['revisions'][str(plan['current_revision'])]['slots']
                                      if s['service_id'] in services]}
                        for pid, plan in lineage_plans.items()
                        if parse_quarter_id(plan['quarter_id']).end_exclusive_utc > now
                        and any(s['service_id'] in services for s in plan['revisions'][str(plan['current_revision'])]['slots'])}
    return facts


def _departures(state, now, plan, slot):
    quarter = parse_quarter_id(plan['quarter_id'])
    if quarter.end_exclusive_utc <= now:
        return
    zone = airport_zone(state, slot['origin_airport_id'])
    beginning = max(now, quarter.start_utc)
    day = beginning.astimezone(zone).date()
    last = (quarter.end_exclusive_utc-timedelta(seconds=1)).astimezone(zone).date()
    while day <= last:
        if day.weekday() in slot['weekdays']:
            departure = local_departure(state, slot['origin_airport_id'], day.isoformat(),
                slot['departure_local_time'], fold=slot['departure_local_fold'])
            if beginning <= departure < quarter.end_exclusive_utc:
                yield occurrence_identity(slot['service_id'], slot['slot_number'], day.isoformat()), departure
        day += timedelta(days=1)


def certify_quarterly_feasibility(envelope, aircraft_ids, *, through_utc=None, index=None,
                                  _execution_blockers=None):
    """Check every relevant current-quarter version and legacy reservation.

    Full finite quarter projection covers weekly wrap, overnight, timezone/DST
    and neighboring quarters. All affected aircraft are checked after removals.
    """
    state = envelope['world_state']; now = parse_canonical_utc(envelope['simulation']['time_utc'])
    references = _PlanningReferences()
    # Lineage is independent of aircraft assignment. Check a continuing service
    # on every current quarter version even when a boundary assigns another aircraft.
    observed = temporal_sources(envelope, aircraft_ids, index=index)
    lineage = observed['lineage']; keys = set()
    for pid, observed in sorted(lineage.items()):
        for slot in observed['slots']:
            for key, departure in _departures(state, now, state['weekly_plans'][pid], slot):
                if key in keys:
                    raise ValueError('DUPLICATE_OCCURRENCE: overlapping quarter lineage')
                keys.add(key)
    for aid in sorted(aircraft_ids):
        aircraft = state['aircraft'][aid]
        if aircraft['status'] not in {'PARKED', 'IN_FLIGHT'}:
            raise ValueError('AIRCRAFT_UNAVAILABLE: no authoritative future availability')
        rows = []; limit = max(now, through_utc or now)
        plan_ids = index.live_plans('aircraft_plans', aid) if index is not None else sorted(state['weekly_plans'])
        for pid in plan_ids:
            plan = state['weekly_plans'][pid]
            quarter = parse_quarter_id(plan['quarter_id'])
            if quarter.end_exclusive_utc <= now:
                continue
            for slot in plan['revisions'][str(plan['current_revision'])]['slots']:
                if slot['planned_aircraft_id'] != aid:
                    continue
                # Recheck live configuration, range and approved airport profiles.
                snapshot = planning_snapshot(state, aid, slot['origin_airport_id'],
                    slot['destination_airport_id'], _references=references)
                if snapshot != slot['planning_timing']:
                    raise ValueError('STALE_TIMING: current authoritative timing differs')
                pre, block, post = timing_bounds(snapshot)[1]
                for key, departure in _departures(state, now, plan, slot):
                    arrival = departure + timedelta(seconds=block)
                    rows.append((departure-timedelta(seconds=pre), arrival+timedelta(seconds=post),
                                 departure, arrival, slot['origin_airport_id'], slot['destination_airport_id']))
                limit = max(limit, quarter.end_exclusive_utc + timedelta(seconds=pre+block+post))
        # Legacy remains the operational writer. Include its committed dated rows
        # and virtual active definitions through the entire proof, not just 90 days.
        flight_ids = index.ids('aircraft_flights', aid) if index is not None else state['dated_flights']
        flights = [state['dated_flights'][fid] for fid in flight_ids if state['dated_flights'][fid]['planned_aircraft_id'] == aid
                   and state['dated_flights'][fid]['status'] not in {'SUPERSEDED', 'CANCELLED'}]
        known = {f['occurrence_key'] for f in flights}
        schedule_ids = index.ids('aircraft_schedules', aid) if index is not None else sorted(state['schedule_definitions'])
        for schedule_id in schedule_ids:
            schedule = state['schedule_definitions'][schedule_id]
            if schedule['status'] != 'ACTIVE' or not any(
                    r['planned_aircraft_id'] == aid for r in schedule['revisions'].values()):
                continue
            desired, conflicts = _expand_schedule(envelope, schedule, now, limit, known_occurrences=known)
            if conflicts:
                raise ValueError(conflicts[0].message)
            # Expansion also returns already materialized keys. Their retained
            # dated facts above own the obligation; do not count the same leg
            # twice or replace its committed facts with a virtual revision.
            flights.extend(f for f in desired.values() if f['planned_aircraft_id'] == aid
                           and f['occurrence_key'] not in known)
        for flight in flights:
            start, end = flight_reservation(state, flight)
            departure = parse_canonical_utc(flight['scheduled_off_block_utc'])
            arrival = parse_canonical_utc(flight['scheduled_in_block_utc'])
            if end > now or arrival + timedelta(seconds=envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']) > now:
                rows.append((start, end, departure, arrival, flight['origin_airport_id'], flight['destination_airport_id']))
        draft = SimpleNamespace(_base=envelope, aircraft_id=aid,
            _snapshot=lambda origin, destination: planning_snapshot(state, aid, origin, destination, _references=references))
        proof = PlanningFeasibility(draft); previous = None
        if aircraft['status'] == 'IN_FLIGHT' and not any(r[2] <= now < r[1] for r in rows):
            raise ValueError('AIRCRAFT_UNAVAILABLE: active arrival reservation is missing')
        for row in sorted(rows):
            if row[2] < now or (aircraft['status'] == 'IN_FLIGHT' and row[2] == now):
                previous = row
                continue
            failure = proof.conflict(previous, row)
            if failure is not None:
                raise failure
            if _execution_blockers is not None:
                location = previous[5] if previous else aircraft['current_airport_id']
                if location != row[4]:
                    _execution_blockers.append((aid, location, row[4], row[2]))
            previous = row
