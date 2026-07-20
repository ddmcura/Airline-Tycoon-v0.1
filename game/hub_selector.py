# Choose Hub module (game/hub_selector.py)
# This module handles the logic for selecting a hub airport in Airline Tycoon.

import os
import json
from game import game_state
from tabulate import tabulate
from game.utils.dev import enable_dev_mode
from game.utils.render import clear_screen
from game.utils.airports import add_hub_to_game_state
from settings import DEV_MODE
from game.game_state import get_active_airline

enable_dev_mode()
from game.utils import paginate, render_country_names, render_airports

def choose_hub(caller="unknown"):
    while True:
        # 🌍 STEP 1: Select Continent
        continent_path = "data/airports"
        continents = [c for c in os.listdir(continent_path) if os.path.isdir(os.path.join(continent_path, c))]

        clear_screen()
        print("🌍 Select Continent:")
        continent_table = [[i, c.replace('_', ' ').title()] for i, c in enumerate(continents, 1)]
        print(tabulate(continent_table, headers=["#", "Continent"], tablefmt="fancy_grid"))
        print("[C] ⬅️ Cancel")

        choice = input("Enter the letter or number of your chosen continent: ").strip().lower()
        if choice == "c":
            if caller == "new_game":
                print("❌ You haven’t chosen a hub yet. A starting hub is required to continue.")
                return None
            elif caller == "add_hub":
                print("⬅️ Returning to Hub Management...")
                return None
            else:
                print("⬅️ Cancelled.")
                return None
        try:
            continent_choice = int(choice) - 1
            chosen_continent = continents[continent_choice]
        except (ValueError, IndexError):
            print("❌ Please enter a valid choice.\n")
            continue

        while True:
            # 🗺️ STEP 2: Select Country
            clear_screen()
            print(f"🌐 Select Country in {chosen_continent.title()}:")
            country_path = os.path.join(continent_path, chosen_continent)
            country_files = [f for f in os.listdir(country_path) if f.endswith(".json")]

            def render_countries_with_cancel(items):
                table = render_country_names(items, country_path)
                return f"{table}\n[C] ⬅️ Cancel"

            selected_country_file = paginate(
                country_files,
                page_size=9,
                render_func=render_countries_with_cancel,
                allow_cancel=True
            )

            if selected_country_file == "BACK":
                break  # Go back to continent selection
            if selected_country_file == "CANCEL":
                if caller == "new_game":
                    print("❌ You haven’t chosen a hub yet. A starting hub is required to continue.")
                    return None
                elif caller == "add_hub":
                    print("⬅️ Returning to Hub Management...")
                    return None
                else:
                    print("⬅️ Cancelled.")
                    return None

            country_json_path = os.path.join(country_path, selected_country_file)
            with open(country_json_path, "r", encoding="utf-8") as f:
                country_data = json.load(f)

            # Dynamically extract ISO code key from JSON
            iso_code = list(country_data.keys())[0]

            while True:
                # 🛫 STEP 3: Select Airport
                clear_screen()
                print(f"📍 Select Airport in {iso_code}:")
                active_airline = get_active_airline(game_state.game_state)
                owned_hubs = active_airline.get("hubs", {}).get(iso_code, {})
                airport_list = [
                    airport for airport in country_data[iso_code]["airports"]
                    if airport["iata"] not in owned_hubs
                ]

                def render_airports_with_cancel(items):
                    table = render_airports(items)
                    return f"{table}\n[C] ⬅️ Cancel"

                selected_airport = paginate(
                    airport_list,
                    page_size=9,
                    render_func=render_airports_with_cancel,
                    allow_cancel=True
                )

                if selected_airport == "BACK":
                    break  # Go back to country selection
                if selected_airport == "CANCEL":
                    if caller == "new_game":
                        print("❌ You haven’t chosen a hub yet. A starting hub is required to continue.")
                        return None
                    elif caller == "add_hub":
                        print("⬅️ Returning to Hub Management...")
                        return None
                    else:
                        print("⬅️ Cancelled.")
                        return None

                selected_airport["iso"] = iso_code

                # ✅ Add the chosen hub to game state (pass ISO code as outer key)
                add_hub_to_game_state(
                    game_state.game_state,
                    selected_airport,
                    region=chosen_continent,
                    iso_code=iso_code
                )

                if DEV_MODE:
                    print("🔁 game_state ID:", id(game_state.game_state))

                return selected_airport

if __name__ == "__main__":
    choose_hub()
