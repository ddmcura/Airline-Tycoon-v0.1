import os
import json
from game.route_management.route_calculators import calculate_distance, calculate_base_fare
from game.game_state import get_active_airline
from game.economy.demand import calculate_adjusted_daily_demand
from game.route_management.route_factory import build_directional_route_pair
from game.utils.render import clear_screen, render_destination_country_options, render_origin_airport_demand_table, slow_print, render_destination_airport_demand_table
from game.utils.routes import classify_demand
from game.utils.ui import paginate

def confirm_and_create_route(game_state, origin_airport, destination_airport):
    if not isinstance(origin_airport, dict) or not isinstance(destination_airport, dict):
        print("❌ Route creation cancelled.")
        input("Press Enter to return...")
        return
    clear_screen()

    origin_header = f"====================\nOrigin City: {origin_airport['city']} ({origin_airport['iata']})\n===================="
    print(origin_header)

    forward_demand = classify_demand(destination_airport.get("population", 0))
    reverse_demand = classify_demand(origin_airport.get("population", 0))

    print(f"Origin: {origin_airport['name']} [{origin_airport['iata']}]")
    print(f"Destination: {destination_airport['name']} [{destination_airport['iata']}]")
    print("\nPossible Demand:")
    print(f"{origin_airport['iata']} → {destination_airport['iata']}: {forward_demand}")
    print(f"{destination_airport['iata']} → {origin_airport['iata']}: {reverse_demand}\n")

    # Check if route or reverse route already exists
    route_id = f"{origin_airport['iata']}-{destination_airport['iata']}"
    reverse_id = f"{destination_airport['iata']}-{origin_airport['iata']}"

    active_airline = get_active_airline(game_state)
    existing_routes = active_airline.get("routes", {})

    if route_id in existing_routes or reverse_id in existing_routes:
        print("❌ This route or its reverse already exists.")
        input("Press Enter to return...")
        return

    preview_pair = build_directional_route_pair(origin_airport, destination_airport)
    difficulty = game_state.get("settings", {}).get("difficulty", "Normal")
    print(f"\nEstimated daily demand at suggested fares ({difficulty}):")
    for direction_id, preview_route in preview_pair.items():
        demand = calculate_adjusted_daily_demand(preview_route, difficulty)
        print(f"  {direction_id}: {demand:,} passengers/day")
    print()

    confirm = input("Proceed to create this route? (y/n): ").strip().lower()
    if confirm != "y":
        print("❌ Route creation cancelled.")
        input("Press Enter to return...")
        return

    route_pair = build_directional_route_pair(origin_airport, destination_airport)
    active_airline.setdefault("routes", {}).update(route_pair)
    print(f"Linked reverse route {reverse_id} has been created.")
    print(f"📝 Route {route_id} has been created!")
    input("Press Enter to return to Route Management...")


def select_origin_airport(game_state, active_airline, hub_country_code):
    # STEP 2: Choose Origin Country (from available licenses)
    clear_screen()
    print("\n🌍 Choose origin country:")

    licensed_countries = [
        code for code, has_license in active_airline.get("licenses", {}).get("country", {}).items()
        if has_license
    ]

    if hub_country_code not in licensed_countries:
        licensed_countries.append(hub_country_code)  # Always include hub country

    origin_country_options = []
    continents = [c for c in os.listdir("Data/Airports") if os.path.isdir(os.path.join("Data/Airports", c))]
    for continent in continents:
        continent_dir = os.path.join("Data/Airports", continent)
        for code in licensed_countries:
            path = os.path.join(continent_dir, f"{code}.json")
            if os.path.exists(path):
                origin_country_options.append((code, continent))

    origin_header = ""
    selected_origin = paginate(
        origin_country_options,
        page_size=9,
        render_func=lambda page: render_destination_country_options(page, origin_header)
    )

    if selected_origin == "CANCEL":
        print("❌ Cancelled. Returning to Route Management...")
        input("Press Enter to continue...")
        return None

    if selected_origin == "BACK":
        return "BACK"

    if not isinstance(selected_origin, tuple):
        return None


    origin_country_code, origin_continent = selected_origin

    origin_country_file = os.path.join("Data/Airports", origin_continent, f"{origin_country_code}.json")
    with open(origin_country_file, "r", encoding="utf-8") as f:
        origin_data = json.load(f)
    origin_airports = origin_data[origin_country_code]["airports"]

    origin_airport = paginate(
        origin_airports,
        page_size=9,
        render_func=render_origin_airport_demand_table
    )
    if origin_airport == "BACK":
        return select_origin_airport(game_state, active_airline, hub_country_code)

    return origin_airport

def select_destination_airport(game_state, origin_airport):
    if origin_airport == "CANCEL":
        print("❌ Route creation cancelled.")
        input("Press Enter to return...")
        return None

    if origin_airport == "BACK":
        return "BACK"

    if not isinstance(origin_airport, dict):
        return None


    clear_screen()
    slow_print("🌏 Destination Country")
    print("=" * 50)

    # Rebuild country list
    all_countries = []
    for continent in os.listdir("Data/Airports"):
        continent_dir = os.path.join("Data/Airports", continent)
        if not os.path.isdir(continent_dir):
            continue
        for file in os.listdir(continent_dir):
            if file.endswith(".json"):
                country_iso = file.replace(".json", "")
                all_countries.append((country_iso, continent))

    origin_header = f"====================\nOrigin City: {origin_airport['city']} ({origin_airport['iata']})\n===================="

    selected_country = paginate(
        all_countries,
        page_size=9,
        render_func=lambda page: render_destination_country_options(page, origin_header)
    )

    if selected_country == "CANCEL":
        print("❌ Cancelled. Returning to Route Management...")
        input("Press Enter to continue...")
        return None

    if selected_country == "BACK":
        return "BACK"

    if not isinstance(selected_country, tuple):
        return None


    dest_country_code, dest_continent = selected_country

    dest_country_path = os.path.join("Data/Airports", dest_continent, f"{dest_country_code}.json")
    with open(dest_country_path, "r", encoding="utf-8") as f:
        dest_data = json.load(f)

    active_airline = get_active_airline(game_state)
    existing_routes = active_airline.get("routes", {})
    origin_iata = origin_airport["iata"]

    # Build a set of blocked IATAs
    blocked_iatas = set()
    for route_id in existing_routes:
        from_iata, to_iata = route_id.split("-")
        if from_iata == origin_iata:
            blocked_iatas.add(to_iata)
        elif to_iata == origin_iata:
            blocked_iatas.add(from_iata)

    # Filter destination airports
    dest_airports = dest_data[dest_country_code]["airports"]
    dest_airports = [
        a for a in dest_airports
        if a["iata"] != origin_iata and a["iata"] not in blocked_iatas
    ]

    if not dest_airports:
        print("⚠️ No available destinations from this origin. All options already used.")
        input("Press Enter to return...")
        return None

    destination_airport = paginate(
        dest_airports,
        page_size=9,
        render_func=lambda page: render_destination_airport_demand_table(page, origin_header)
    )
    if destination_airport == "BACK":
        return select_destination_airport(game_state, origin_airport)

    return destination_airport

def get_all_routes(game_state):
    active_airline = get_active_airline(game_state)
    return active_airline.get("routes", {})
