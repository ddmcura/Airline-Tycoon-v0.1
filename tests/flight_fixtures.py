"""Current PH flight fixtures, public commands and real Booking history only."""
from datetime import timedelta
from game.simulation import kernel
from game.simulation.handlers import initialize_runtime_handlers
from game.scheduling import WeeklyDraft
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.profile_scheduling import fresh, identities


def flight_world(count=1, *, stagger_seconds=0, days=1, fare_minor=11600, history=0):
    initialize_runtime_handlers()
    world = fresh(count)
    owner, _, ports = identities(world)
    start = parse_canonical_utc('2026-09-07T00:01:00Z')
    for index, aircraft_id in enumerate(sorted(world['world_state']['aircraft'])):
        draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft_id)
        for day in range(days):
            departure = format_utc(start + timedelta(days=day, seconds=index * stagger_seconds))
            draft.add(ports['MNL'], ports['DVO'], departure_utc=departure, fare_minor=fare_minor)
            draft.add_return(fare_minor=fare_minor)
        result = draft.save(world)
        assert result.succeeded, result
    result = kernel.process_events_through(world, format_utc(start - timedelta(seconds=1)))
    assert result.succeeded, result.failure
    now = world['simulation']['time_utc']
    for _ in range(history):
        kernel.schedule_event(world, event_type='NO_OP', due_at_utc=now, owner_type='airline', owner_id=owner)
    if history:
        assert kernel.process_events_through(world, now).succeeded
    assert validate_world(world).is_valid
    return world


def window(world, kind):
    flights = world['world_state']['dated_flights'].values()
    outbound = [f for f in flights if f['origin_airport_id'] == next(
        key for key,row in world['world_state']['airports'].items() if row['reference_code']=='MNL')]
    if kind == 'departure': return max(f['scheduled_off_block_utc'] for f in outbound)
    if kind == 'completion':
        result = kernel.process_events_through(world, max(f['scheduled_off_block_utc'] for f in outbound))
        assert result.succeeded, result.failure
        return max(f['scheduled_in_block_utc'] for f in outbound)
    return max(f['scheduled_in_block_utc'] for f in flights)
