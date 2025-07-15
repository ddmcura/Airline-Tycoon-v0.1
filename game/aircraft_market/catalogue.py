# game/aircraft_market/catalogue.py
import os
import json

from utils.render import clear_screen, render_aircraft_table
from utils.ui import paginate
from tabulate import tabulate
from game.aircraft_market.seat_configuration import configure_seats

PLANES_DIR = "Data/planes"

def list_manufacturers():
    files = [f for f in os.listdir(PLANES_DIR) if f.endswith(".json")]
    manufacturers = [os.path.splitext(f)[0].replace("_", " ").title() for f in files]
    
    # Pair file names with user-friendly names
    manufacturer_map = dict(zip(manufacturers, files))

    clear_screen()
    print("🛠️  Select Aircraft Manufacturer:\n")

    selected = paginate(manufacturers, page_size=7)

    if selected == "BACK":
        return None

    return manufacturer_map[selected]  # Return filename
def load_aircraft_from_file(filename):
    path = os.path.join("Data/planes", filename)

    with open(path, "r") as f:
        data = json.load(f)

    aircraft_list = []

    for family, variants in data.items():
        for model, specs in variants.items():
            aircraft_list.append({
                "model": model,
                "family": family,
                "base_price": specs.get("base_price", 0),
                "capacity": specs.get("capacity", 0),
                "range_km": specs.get("range_km", 0),
                "cruise_speed_kph": specs.get("cruise_speed_kph", 0),
                "full_data": specs
            })

    return aircraft_list

def start_aircraft_catalogue_flow(game_state):
    manufacturer_file = list_manufacturers()
    if not manufacturer_file:
        return  # Back to previous menu

    aircraft_data = load_aircraft_from_file(manufacturer_file)

    chosen = paginate(aircraft_data, page_size=5, render_func=render_aircraft_table)

    if chosen == "BACK":
        return

    clear_screen()
    print(f"\n✅ You selected the {chosen['model']} ✈️\n")

    # 👉 Go to seat configuration with full aircraft spec

    configure_seats(game_state, chosen)

