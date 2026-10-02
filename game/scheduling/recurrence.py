"""Deterministic weekly publication over existing schedule revisions and events."""

from datetime import date, datetime, time, timedelta

from game.world_state.timestamps import format_utc, parse_canonical_utc
from .local_time import airport_zone

POLICY = 'ROLLING_FOUR_WEEKS_V1'
EVENT_TYPE = 'STAGE1_WEEKLY_PUBLICATION'


def base_zone(envelope, airline_id):
    world = envelope['world_state']
    bases = world['airlines'][airline_id]['base_airport_ids']
    if not bases:
        raise ValueError('weekly publication requires an authoritative airline base')
    return airport_zone(world, bases[0])


def rolling_schedules(envelope, airline_id, aircraft_id=None):
    """Return movements still having an effective rolling revision now or later."""
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    selected = []
    for schedule in sorted(envelope['world_state']['schedule_definitions'].values(),
                           key=lambda row: row['schedule_id']):
        if schedule['airline_id'] != airline_id or schedule['status'] != 'ACTIVE':
            continue
        for revision in schedule['revisions'].values():
            recurrence = revision['recurrence']
            local_now = now.astimezone(airport_zone(envelope['world_state'],
                                      revision['origin_airport_id'])).date().isoformat()
            ends = [value for value in (revision['effective_until_local_date'],
                    recurrence.get('until_local_date')) if value is not None]
            if (recurrence.get('publication_policy') == POLICY
                    and recurrence.get('enabled', True)
                    and (aircraft_id is None or revision['planned_aircraft_id'] == aircraft_id)
                    and (not ends or min(ends) >= local_now)):
                selected.append(schedule)
                break
    return tuple(selected)


def rolling_horizon(envelope, airline_id):
    from .publication import configured_publication_horizon_utc
    zone = base_zone(envelope, airline_id)
    local = parse_canonical_utc(envelope['simulation']['time_utc']).astimezone(zone)
    monday = local.date() - timedelta(days=local.weekday())
    end = datetime.combine(monday + timedelta(days=34), time(23, 59, 59), zone)
    horizon = format_utc(end)
    if horizon > configured_publication_horizon_utc(envelope):
        raise ValueError('configured publication horizon is too short for four future weeks')
    return horizon


def ensure_publication_event(envelope, airline_id, *, excluding=None):
    """One future Monday event, persisted in the normal queue, never a UI timer."""
    from game.simulation import schedule_event
    if not rolling_schedules(envelope, airline_id):
        return
    pending = [event for event in envelope['world_state']['pending_events'].values()
               if event['event_type'] == EVENT_TYPE and event['owner_id'] == airline_id
               and event['event_id'] != excluding]
    if pending:
        return
    zone = base_zone(envelope, airline_id)
    now = parse_canonical_utc(envelope['simulation']['time_utc']).astimezone(zone)
    following = now.date() - timedelta(days=now.weekday()) + timedelta(days=7)
    due = format_utc(datetime.combine(following, time(), zone))
    revision = envelope['simulation']['operation_revisions'].get(airline_id, 0)
    schedule_event(envelope, event_type=EVENT_TYPE, due_at_utc=due,
                   owner_type='airline', owner_id=airline_id,
                   operation_revision=revision, priority=0,
                   payload={'contract': POLICY})


def publish_rolling_window(envelope, airline_id):
    from .publication import publish_occurrences_through
    result = publish_occurrences_through(envelope, rolling_horizon(envelope, airline_id),
        schedule_ids=tuple(row['schedule_id'] for row in rolling_schedules(envelope, airline_id)))
    if not result.succeeded:
        conflict = result.conflicts[0] if result.conflicts else None
        raise ValueError(f'{conflict.code}: {conflict.message}' if conflict else result.status)
    ensure_publication_event(envelope, airline_id)
    return result


def pattern_edit_date(envelope, airline_id, aircraft_id):
    """First unmaterialized home-local week; existing reservations stay protected."""
    world = envelope['world_state']
    aircraft = world['aircraft'][aircraft_id]
    if aircraft['airline_id'] != airline_id:
        raise ValueError('select an aircraft owned by the player')
    zone = airport_zone(world, aircraft['home_airport_id'])
    now = parse_canonical_utc(envelope['simulation']['time_utc']).astimezone(zone).date()
    last = now
    for flight in world['dated_flights'].values():
        if flight['planned_aircraft_id'] == aircraft_id:
            last = max(last, parse_canonical_utc(flight['scheduled_in_block_utc']).astimezone(zone).date())
    # A queued revision is immutable as well; subsequent edits follow its week.
    for schedule in rolling_schedules(envelope, airline_id, aircraft_id):
        current = schedule['revisions'][str(schedule['current_revision'])]
        last = max(last, date.fromisoformat(current['effective_from_local_date']))
    following = last - timedelta(days=last.weekday()) + timedelta(days=7)
    schedules = rolling_schedules(envelope, airline_id, aircraft_id)
    protected_dates = {}
    for schedule in schedules:
        protected_dates[schedule['schedule_id']] = max(
            [schedule['revisions'][str(schedule['current_revision'])]['effective_from_local_date']]
            + [flight['scheduled_departure_local_date']
               for flight in world['dated_flights'].values()
               if flight['schedule_id'] == schedule['schedule_id']])
    while True:
        boundary = datetime.combine(following, time(), zone)
        # Revisions replace whole origin-local dates. A home Monday may still
        # be Sunday at a western origin; never split its published Sunday.
        if all(boundary.astimezone(airport_zone(world, schedule['revisions'][str(
                    schedule['current_revision'])]['origin_airport_id'])).date().isoformat()
               > protected_dates[schedule['schedule_id']]
               for schedule in schedules):
            return following.isoformat()
        following += timedelta(days=7)


def _weekly_publication(context):
    from .publication import publish_occurrences_through
    if context.payload != {'contract': POLICY}:
        raise ValueError('invalid weekly publication event payload')
    if rolling_schedules(context.envelope, context.event['owner_id']):
        result = publish_occurrences_through(context.envelope,
                    rolling_horizon(context.envelope, context.event['owner_id']),
                    schedule_ids=tuple(row['schedule_id'] for row in rolling_schedules(
                        context.envelope, context.event['owner_id'])))
        if not result.succeeded:
            raise ValueError(result.conflicts[0].message if result.conflicts else result.status)
        ensure_publication_event(context.envelope, context.event['owner_id'],
                                 excluding=context.event['event_id'])


from game.simulation.kernel import DEFAULT_EVENT_HANDLERS
DEFAULT_EVENT_HANDLERS.register(EVENT_TYPE, _weekly_publication)
