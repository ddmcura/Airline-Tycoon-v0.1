from game.scheduling.helpers import time_to_minutes, minutes_to_time


def _blocks(existing):
    return sorted(
        (
            time_to_minutes(flight["start_time"]),
            time_to_minutes(flight["end_time"]),
        )
        for flight in existing
    )


def suggest_available_slots(existing, flight_duration, limit=5):
    """Return useful openings, prioritizing time after scheduled flying."""
    day_minutes = 24 * 60
    if not existing:
        return [minutes_to_time(0)]

    blocks = _blocks(existing)
    openings = []
    if day_minutes - blocks[-1][1] >= flight_duration:
        openings.append(blocks[-1][1])
    for i in range(len(blocks) - 1):
        gap_start = blocks[i][1]
        gap_end = blocks[i + 1][0]
        if gap_end - gap_start >= flight_duration:
            openings.append(gap_start)
    if blocks[0][0] >= flight_duration:
        openings.append(0)

    unique = []
    for opening in openings:
        value = minutes_to_time(opening)
        if value not in unique:
            unique.append(value)
    return unique[:limit]


def next_available_after(existing, requested_start, flight_duration):
    """Return the earliest non-overlapping start at or after a request."""
    candidate = requested_start
    for start, end in _blocks(existing):
        candidate_end = candidate + flight_duration
        if candidate_end <= start:
            break
        if candidate < end and candidate_end > start:
            candidate = end
    if candidate + flight_duration > 24 * 60:
        return None
    return candidate


def suggest_next_available(existing, flight_duration):
    useful_slots = suggest_available_slots(existing, flight_duration)
    if useful_slots:
        return ", ".join(useful_slots)

    day_minutes = 24 * 60
    if not existing:
        return minutes_to_time(0)

    blocks = sorted([
        (time_to_minutes(s["start_time"]), time_to_minutes(s["end_time"]))
        for s in existing
    ])

    # Check before first block
    if blocks[0][0] >= flight_duration:
        return minutes_to_time(0)

    # Check between existing blocks
    for i in range(len(blocks) - 1):
        gap_start = blocks[i][1]
        gap_end = blocks[i + 1][0]
        if gap_end - gap_start >= flight_duration:
            return minutes_to_time(gap_start)

    # No gaps — suggest after last block
    if day_minutes - blocks[-1][1] >= flight_duration:
        return minutes_to_time(blocks[-1][1])

    return "No available slot"