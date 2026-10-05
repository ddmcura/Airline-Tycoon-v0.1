"""Initial partial-week activation; derived scheduling state, never saved."""

from datetime import datetime, time, timedelta

from game.world_state.timestamps import parse_canonical_utc
from .local_time import airport_zone


def initial_week_window(envelope, aircraft_id):
    """Home-local week bounds in aware time, including UTC/month boundaries."""
    world = envelope['world_state']
    zone = airport_zone(world, world['aircraft'][aircraft_id]['home_airport_id'])
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    local = now.astimezone(zone).date()
    beginning = datetime.combine(local - timedelta(days=local.weekday()), time(), zone)
    end = beginning + timedelta(days=7)
    return beginning, end


def initial_week_end(envelope, aircraft_id, prototypes):
    """A prototype is (preparation, departure), not an invented past operation."""
    beginning, end = initial_week_window(envelope, aircraft_id)
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    return end if any(beginning <= departure < end and start < now
                      for start, departure in prototypes) else None


def operational_sequence(envelope, aircraft_id, rows, eligible, week_end,
                         *, activated_at=None):
    """Exclude inert intent and an infeasible INITIAL prefix, then stay strict.

    Rows are (reservation start/end, departure/arrival, origin/destination).
    Only new policy/draft rows are eligible; committed obligations are protected.
    The first materialized occurrence is a durable activation boundary derived
    from dated authority, even after it completes. No cache or marker is saved.
    Full normal conflict/continuity validation still runs on the returned rows.
    """
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    aircraft = envelope['world_state']['aircraft'][aircraft_id]
    location = aircraft['current_airport_id']
    ready = now
    turnaround = envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
    ordered = sorted(rows)
    protected = [row for row in ordered if row not in eligible and row[2] >= now]
    result = []
    activated = activated_at is not None and activated_at <= now
    for row in ordered:
        start, end, departure, arrival, origin, destination = row
        if row in eligible and start < now:
            continue  # Elapsed intent never supplies aircraft position/availability.
        if departure < now:
            if row not in eligible and end > now:
                location = destination
                ready = max(ready, end, arrival + timedelta(seconds=turnaround))
                result.append(row)  # Actual active operation, not a pattern slot.
            continue
        can_skip = (not activated and week_end is not None and departure < week_end
                    and row in eligible
                    and (activated_at is None or departure < activated_at))
        following = next((item for item in protected if item[2] >= departure), None) if can_skip else None
        unavailable = (origin != location or start < ready
                       or (following is not None and (
                           end > following[0]
                           or arrival + timedelta(seconds=turnaround) > following[2])))
        if can_skip and unavailable:
            continue
        result.append(row)
        activated = True
        location = destination
        ready = max(end, arrival + timedelta(seconds=turnaround))
    return result
