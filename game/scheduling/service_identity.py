"""Read-only recurring identity and lifecycle primitives; no publication workflow."""
from datetime import date
from game.world_state.ids import parse_entity_id
from game.world_state.timestamps import parse_canonical_utc
from game.utils.quarters import parse_quarter_id


def flight_number(world, service_id):
    service = world['services'][service_id]
    prefix = world['service_numbering'][service['airline_id']]['flight_number_prefix']
    return f"{prefix}{service['flight_number_number']:02d}"


def occurrence_identity(service_id, slot_number, operating_date):
    if parse_entity_id(service_id, 'service') is None:
        raise ValueError('invalid recurring service identity')
    if type(slot_number) is not int or slot_number < 1:
        raise ValueError('invalid occurrence slot number')
    if type(operating_date) is not str or date.fromisoformat(operating_date).isoformat() != operating_date:
        raise ValueError('operating date must be canonical YYYY-MM-DD')
    return f'{service_id}@{operating_date}#{slot_number}'


def plan_lifecycle(plan, time_utc):
    quarter = parse_quarter_id(plan['quarter_id']); now = parse_canonical_utc(time_utc)
    current = plan['revisions'][str(plan['current_revision'])]
    if current['published_at_utc'] is None or now < parse_canonical_utc(current['published_at_utc']):
        return 'PLANNING'
    if now < quarter.start_utc:
        return 'PUBLISHED'
    if now < quarter.end_exclusive_utc:
        return 'ACTIVE'
    return 'HISTORICAL'


def plan_occurrence_identity(envelope, weekly_plan_id, revision, service_id, slot_number, operating_date):
    """Resolve identity from a retained slot; no rows/IDs/events are allocated."""
    world = envelope['world_state']; plan = world['weekly_plans'][weekly_plan_id]
    slots = plan['revisions'][str(revision)]['slots']
    identity = occurrence_identity(service_id, slot_number, operating_date)
    slot = next((s for s in slots if s['service_id'] == service_id and s['slot_number'] == slot_number), None)
    if slot is None or date.fromisoformat(operating_date).weekday() not in slot['weekdays']:
        raise ValueError('date does not belong to plan service slot')
    from .local_time import local_departure
    depart = local_departure(world, slot['origin_airport_id'], operating_date,
                             slot['departure_local_time'], fold=slot['departure_local_fold'])
    quarter = parse_quarter_id(plan['quarter_id'])
    if not quarter.start_utc <= depart < quarter.end_exclusive_utc:
        raise ValueError('occurrence departure is outside UTC plan quarter')
    return identity
