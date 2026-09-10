"""Pure planning arithmetic; no live handling or random operational duration."""

from datetime import timedelta
from game.world_state.timestamps import parse_canonical_utc


def timing_bounds(snapshot):
    """Return min/max pre, gate-to-gate, and post durations in exact seconds."""
    activities = snapshot['activities']
    airborne = max(300, ((snapshot['distance_m'] * 3600
                         + snapshot['cruise_speed_kph'] * 1000 * 300 - 1)
                        // (snapshot['cruise_speed_kph'] * 1000 * 300)) * 300)
    result = []
    for bound in (0, 1):
        pre = snapshot['taxi_to_stand_seconds'][bound] + max(
            activities['baggage_loading'][bound], activities['catering'][bound],
            activities['refueling'][bound],
            activities['cleaning'][bound] + activities['boarding'][bound])
        block = (snapshot['taxi_out_seconds'][bound] + airborne
                 + snapshot['taxi_in_seconds'][bound])
        post = max(activities['disembarking'][bound],
                   activities['baggage_unloading'][bound])
        result.append((pre, block, post))
    return tuple(result)


def flight_reservation(world, flight):
    revision = world['schedule_definitions'][flight['schedule_id']]['revisions'][
        str(flight['schedule_revision'])]
    snapshot = revision.get('planning_timing')
    pre, _, post = timing_bounds(snapshot)[1] if snapshot else (0, 0, 0)
    return (parse_canonical_utc(flight['scheduled_off_block_utc']) - timedelta(seconds=pre),
            parse_canonical_utc(flight['scheduled_in_block_utc']) + timedelta(seconds=post))


def timed_deadhead(world, flight):
    if (type(flight) is not dict or type(flight.get('schedule_id')) is not str
            or type(flight.get('schedule_revision')) is not int):
        return False
    revision = world.get('schedule_definitions', {}).get(
        flight.get('schedule_id'), {}).get('revisions', {}).get(
            str(flight.get('schedule_revision')), {})
    return (type(revision) is dict and flight.get('service_type') == 'DEADHEAD'
            and flight.get('passenger_service_classification') == 'NON_PASSENGER'
            and 'planning_timing' in revision)
