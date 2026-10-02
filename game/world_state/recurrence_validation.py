"""Schema-7 rolling-pattern event completeness and exact event contract."""

from datetime import datetime, time, timedelta

from game.world_state.timestamps import parse_canonical_utc


def validate_recurrence(envelope):
    from game.scheduling.recurrence import EVENT_TYPE, POLICY, base_zone, rolling_schedules
    world = envelope['world_state']
    events = {}
    for event in world['pending_events'].values():
        if event['event_type'] != EVENT_TYPE:
            continue
        if (event['owner_type'] != 'airline' or event['payload'] != {'contract': POLICY}
                or event['order_key'][0] != 0):
            raise ValueError('invalid weekly publication event contract')
        airline_id = event['owner_id']
        if event['operation_revision'] != envelope['simulation']['operation_revisions'].get(airline_id):
            raise ValueError('weekly publication event must have the current airline revision')
        local = parse_canonical_utc(event['due_at_utc']).astimezone(base_zone(envelope, airline_id))
        if local.weekday() != 0 or local.time() != time():
            raise ValueError('weekly publication event must be due at base-local Monday midnight')
        now = parse_canonical_utc(envelope['simulation']['time_utc']).astimezone(base_zone(envelope, airline_id))
        following = now.date() - timedelta(days=now.weekday()) + timedelta(days=7)
        expected = datetime.combine(following, time(), base_zone(envelope, airline_id))
        if local != expected and local != now:
            raise ValueError('weekly publication event must be due at the next Monday boundary')
        if airline_id in events:
            raise ValueError('duplicate weekly publication events')
        events[airline_id] = event
    for airline_id in world['airlines']:
        if rolling_schedules(envelope, airline_id) and airline_id not in events:
            raise ValueError('rolling schedule is missing its weekly publication event')
