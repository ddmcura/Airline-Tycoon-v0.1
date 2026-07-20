"""Display aircraft rotations in chronological order."""

from tabulate import tabulate

from game.game_state import get_active_airline
from game.scheduling.helpers import minutes_to_time, time_to_minutes
from game.utils.render import clear_screen


DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def build_scheduled_flight_rows(game_state):
    """Return display rows ordered by weekday, aircraft, and departure time."""
    airline = get_active_airline(game_state)
    rotations = []

    for registration, aircraft in airline.get("fleet", {}).items():
        for day, routes in aircraft.get("schedule", {}).items():
            for route_id, flights in routes.items():
                route_codes = route_id.split("-", 1)
                fallback_origin = route_codes[0] if len(route_codes) == 2 else "?"
                fallback_destination = route_codes[1] if len(route_codes) == 2 else "?"
                for flight in flights:
                    start_minutes = time_to_minutes(flight["start_time"])
                    end_minutes = time_to_minutes(flight["end_time"])
                    origin = flight.get("start_airport", fallback_origin)
                    destination = flight.get("end_airport", fallback_destination)
                    rotations.append(
                        {
                            "day": day,
                            "registration": registration,
                            "route_id": route_id,
                            "route": f"{origin} -> {destination}",
                            "start_minutes": start_minutes,
                            "end_minutes": end_minutes,
                            "service": (
                                "Deadhead"
                                if flight.get("service_type") == "deadhead"
                                else "Passenger"
                            ),
                        }
                    )

    rotations.sort(
        key=lambda flight: (
            DAYS.index(flight["day"]) if flight["day"] in DAYS else len(DAYS),
            flight["registration"],
            flight["start_minutes"],
            flight["end_minutes"],
        )
    )

    sequence = {}
    rows = []
    for flight in rotations:
        sequence_key = (flight["day"], flight["registration"])
        sequence[sequence_key] = sequence.get(sequence_key, 0) + 1
        rows.append(
            [
                flight["day"],
                flight["registration"],
                sequence[sequence_key],
                flight["route"],
                minutes_to_time(flight["start_minutes"]),
                minutes_to_time(flight["end_minutes"]),
                flight["service"],
                flight["route_id"],
            ]
        )
    return rows


def view_scheduled_flights(game_state):
    clear_screen()
    print("VIEW SCHEDULED FLIGHTS")
    print("=" * 50)

    rows = build_scheduled_flight_rows(game_state)
    if not rows:
        print("No scheduled flights yet.")
    else:
        headers = [
            "Day",
            "Aircraft",
            "Seq",
            "Route",
            "Start",
            "End",
            "Service",
            "Route ID",
        ]
        print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))

    input("\nPress Enter to return to Schedule Menu...")
