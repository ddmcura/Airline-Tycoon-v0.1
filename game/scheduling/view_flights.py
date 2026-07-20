# game/scheduling/view_flights.py

from game.utils.render import clear_screen
from game.game_state import get_active_airline
from game.scheduling.helpers import time_to_minutes
from tabulate import tabulate



def view_scheduled_flights(game_state):
    clear_screen()
    print("📅 VIEW SCHEDULED FLIGHTS")
    print("=" * 50)

    airline = get_active_airline(game_state)
    routes = airline.get("routes", {})

    if not routes:
        print("❌ No routes found.")
        input("Press Enter to return...")
        return

    all_rows = []

    for route_id, route_data in routes.items():
        schedule = route_data.get("schedule", {})
        for day, ac_block in schedule.items():
            for reg, directions in ac_block.items():
                for direction_key, blocks in directions.items():
                    for flight in blocks:
                        route_str = direction_key.replace("-", " → ")
                        all_rows.append([
                            day,
                            reg,
                            route_str,
                            flight['start_time'],
                            flight['end_time'],
                            direction_key  # optional: keep raw ID for debugging
                        ])


    if not all_rows:
        print("No scheduled flights yet.")
    else:
        headers = ["Day", "Aircraft", "Route", "Start", "End", "Direction"]
        print(tabulate(sorted(all_rows), headers=headers, tablefmt="fancy_grid"))

    input("\nPress Enter to return to Schedule Menu...")
