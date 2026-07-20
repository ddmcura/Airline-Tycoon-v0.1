"""Plan aircraft positioning flights without mutating the schedule."""

import math

from game.route_management.route_calculators import calculate_distance
from game.scheduling.helpers import time_to_minutes


TURNAROUND_MINUTES = 30


def aircraft_position_before(existing, requested_start, initial_airport):
    """Return aircraft location and time available before a requested start."""
    previous = [
        flight
        for flight in existing
        if time_to_minutes(flight["end_time"]) <= requested_start
    ]
    if not previous:
        return initial_airport, 0
    latest = max(
        previous,
        key=lambda flight: time_to_minutes(flight["end_time"]),
    )
    return latest.get("end_airport", initial_airport), time_to_minutes(
        latest["end_time"]
    )


def plan_deadhead(
    existing,
    requested_start,
    service_origin,
    initial_airport,
    cruise_speed,
    airport_index,
    max_range_km=None,
):
    """Return a positioning plan when the aircraft is not at service_origin."""
    current_airport, available_time = aircraft_position_before(
        existing, requested_start, initial_airport
    )
    if not current_airport or current_airport == service_origin:
        return None

    current = airport_index.get(current_airport, {})
    target = airport_index.get(service_origin, {})
    if not current.get("coordinates") or not target.get("coordinates"):
        return {"error": f"No airport data for {current_airport}-{service_origin}."}

    distance = calculate_distance(current["coordinates"], target["coordinates"])
    if max_range_km and distance > max_range_km:
        return {
            "error": (
                f"Deadhead {current_airport}-{service_origin} is {distance:,.0f} km, "
                f"beyond this aircraft's {max_range_km:,.0f} km range."
            )
        }
    flight_minutes = int(
        math.ceil(((distance / max(1, cruise_speed)) * 60) / 5) * 5
    )
    passenger_start = max(
        requested_start,
        available_time + flight_minutes + TURNAROUND_MINUTES,
    )
    return {
        "route_id": f"{current_airport}-{service_origin}",
        "origin": current_airport,
        "destination": service_origin,
        "start": available_time,
        "end": available_time + flight_minutes,
        "passenger_start": passenger_start,
        "distance_km": distance,
    }
