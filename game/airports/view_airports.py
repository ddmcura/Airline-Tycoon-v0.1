# game/airports/view_airports.py

import os
import json
from tabulate import tabulate
from game.utils.render import clear_screen, render_country_names, render_airports_detailed
from game.utils.ui import paginate
from game.airports.airport_detail import view_airport_detail

def view_all_airports(game_state):
    continent_path = "Data/Airports"

    while True:
        clear_screen()
        print("🌍 View Airports from which Continent?\n")

        continents = [c for c in os.listdir(continent_path) if os.path.isdir(os.path.join(continent_path, c))]
        continents.sort()

        selected_continent = paginate(
            continents,
            page_size=9,
            render_func=lambda items: tabulate(
                [[i + 1, c.title()] for i, c in enumerate(items)],
                headers=["#", "Continent"],
                tablefmt="fancy_grid"
            ),
            allow_cancel=True
        )

        if selected_continent in ["BACK", "CANCEL"]:
            return  # Exit to Airports menu

        country_path = os.path.join(continent_path, selected_continent)

        while True:
            clear_screen()
            print(f"🌐 View Airports from which Country in {selected_continent.title()}?\n")

            country_files = [f for f in os.listdir(country_path) if f.endswith(".json")]

            selected_country_file = paginate(
                country_files,
                page_size=9,
                render_func=lambda items: render_country_names(items, country_path),
                allow_cancel=True
            )

            if selected_country_file in ["BACK", "CANCEL"]:
                break  # Back to continent selection

            country_file_path = os.path.join(country_path, selected_country_file)
            with open(country_file_path, "r", encoding="utf-8") as f:
                country_data = json.load(f)

            iso_code = list(country_data.keys())[0]
            airports = country_data[iso_code].get("airports", [])

            while True:
                clear_screen()
                print(f"🛫 Viewing Airports in {country_data[iso_code].get('country', selected_country_file)}\n")

                selected_airport = paginate(
                    airports,
                    page_size=9,
                    render_func=render_airports_detailed,
                    allow_cancel=True
                )

                if selected_airport in ["BACK", "CANCEL"]:
                    break  # Back to country selection
                else:
                    # Go to airport detail view
                    view_airport_detail(game_state, selected_airport)
