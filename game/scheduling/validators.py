from game.scheduling.helpers import time_to_minutes, minutes_to_time

def has_conflict(existing, new_start, new_end):
    for sched in existing:
        s = time_to_minutes(sched["start_time"])
        e = time_to_minutes(sched["end_time"])
        if not (new_end <= s or new_start >= e):
            return True
    return False


def validate_aircraft_continuity(
    existing, new_start, new_end, origin, destination, initial_airport
):
    """Ensure a new flight connects to the aircraft's adjacent flights."""
    previous_flights = [
        flight
        for flight in existing
        if time_to_minutes(flight["end_time"]) <= new_start
    ]
    if previous_flights:
        previous = max(
            previous_flights,
            key=lambda flight: time_to_minutes(flight["end_time"]),
        )
        expected_origin = previous.get("end_airport")
    else:
        expected_origin = initial_airport

    if expected_origin and expected_origin != origin:
        return False, f"Aircraft is at {expected_origin}, not {origin}."

    later_flights = [
        flight
        for flight in existing
        if time_to_minutes(flight["start_time"]) >= new_end
    ]
    if later_flights:
        following = min(
            later_flights,
            key=lambda flight: time_to_minutes(flight["start_time"]),
        )
        required_destination = following.get("start_airport")
        if required_destination and destination != required_destination:
            return (
                False,
                f"Next flight departs {required_destination}, not {destination}.",
            )

    return True, ""


def find_between_blocks(existing_schedule, new_start, new_end):
    """
    Returns a list of time blocks where the new flight fits perfectly between existing blocks.
    Only returns first fit for each day.
    """
    matches = []
    existing_times = [
        (time_to_minutes(e["start_time"]), time_to_minutes(e["start_time"]) + 120)
        for e in existing_schedule
    ]
    existing_times.sort()
    for i in range(len(existing_times) - 1):
        if existing_times[i][1] <= new_start and new_end <= existing_times[i + 1][0]:
            matches.append((
                minutes_to_time(existing_times[i][1]),
                minutes_to_time(existing_times[i + 1][0])
            ))
            break
    return matches