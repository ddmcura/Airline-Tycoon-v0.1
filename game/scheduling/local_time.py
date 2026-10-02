"""Airport-local input and presentation over pinned authoritative timezone rules."""

from datetime import date, time

from game.world_state.timezones import load_named_timezone
from game.world_state.timestamps import parse_canonical_utc


def airport_zone(world, airport_id):
    return load_named_timezone(world['airports'][airport_id]['timezone'])


def airport_local(world, airport_id, utc):
    return parse_canonical_utc(utc).astimezone(airport_zone(world, airport_id))


def local_departure(world, airport_id, local_date, local_time, *, fold=0):
    """Origin-local input; nonexistent DST slots reject rather than shift."""
    from .publication import _local_to_utc
    parsed_date = date.fromisoformat(local_date)
    if parsed_date.isoformat() != local_date:
        raise ValueError('use YYYY-MM-DD')
    if len(local_time) == 5:
        local_time += ':00'
    parsed_time = time.fromisoformat(local_time)
    if parsed_time.isoformat() != local_time or parsed_time.tzinfo is not None:
        raise ValueError('use HH:MM or HH:MM:SS')
    return _local_to_utc(parsed_date, local_time, fold,
                         airport_zone(world, airport_id), 'departure_local_time')
