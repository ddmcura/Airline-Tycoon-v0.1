# game/route_management/create_routes.py
from game.utils.render import clear_screen, slow_print, render_airports, country_flag, render_hub_selection_table, render_origin_countries_options, render_origin_airport_demand_table, render_destination_country_options, render_destination_airport_demand_table
from game.utils.ui import paginate
from game.utils.routes import classify_demand
from game.route_management.route_calculators import calculate_distance, calculate_base_fare
from game.game_state import get_active_airline
from game.route_management import render

import os
import json
from tabulate import tabulate
from game.route_management.core import (
    confirm_and_create_route,
    select_origin_airport,
    select_destination_airport
)


def select_hub(game_state, active_airline):
    clear_screen()
    slow_print("🛣️ Create New Route.\nChoose the Hub where your Route will base on:")
    print("=" * 50)

    # STEP 1: Select Hub (Paginated Table)
    hubs = []
    hub_index_map = {}
    idx = 1
    for country_code, hub_dict in active_airline.get("hubs", {}).items():
        for iata, hub_info in hub_dict.items():
            hubs.append({
                "index": idx,
                "iata": iata,
                "name": hub_info['name'],
                "city": hub_info['city'],
                "country": hub_info['country'],
                "iso": country_code
            })
            hub_index_map[idx] = (country_code, iata)
            idx += 1

    if not hubs:
        print("❌ You do not own any hubs yet.")
        input("Press Enter to return...")
        return None, None, None

    selected_hub = paginate(hubs, page_size=9, render_func=render_hub_selection_table)
    if selected_hub == "CANCEL":
        return "CANCEL"
    if selected_hub == "BACK":
        return "BACK"
    if not isinstance(selected_hub, dict):
        return None


    selected_country_code, selected_iata = hub_index_map[selected_hub["index"]]
    selected_hub_info = active_airline['hubs'][selected_country_code][selected_iata]

    return selected_hub_info, selected_country_code, selected_iata

def create_new_route(game_state):
    active_airline = get_active_airline(game_state)

    # STEP 1: Select Hub
    while True:
        hub_info = select_hub(game_state, active_airline)
        if hub_info in ["CANCEL", None]:
            return
        if hub_info == "BACK":
            continue

        try:
            hub_info, hub_country_code, hub_iata = hub_info
            break
        except:
            print("⚠️ Unexpected hub info. Try again.")

    # Loop here to allow BACK from destination to return to origin
    while True:
        # STEP 2: Select Origin
        origin_airport = select_origin_airport(game_state, active_airline, hub_country_code)
        if origin_airport == "CANCEL":
            return
        if origin_airport == "BACK":
            # go back to hub selection
            return create_new_route(game_state)
        if not isinstance(origin_airport, dict):
            continue

        # STEP 3: Select Destination
        while True:
            destination_airport = select_destination_airport(game_state, origin_airport)
            if destination_airport == "CANCEL":
                return
            if destination_airport == "BACK":
                break  # Go back to origin step
            if not isinstance(destination_airport, dict):
                continue

            # STEP 4: Confirm
            confirm_and_create_route(game_state, origin_airport, destination_airport)
            return
