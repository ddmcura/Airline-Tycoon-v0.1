import os
import json
import sys
import time
from tabulate import tabulate
from .formatting import country_flag
from game.utils.routes import classify_demand

def render_country_names(countries, continent_path):
    table = []
    for i, filename in enumerate(countries, 1):
        filepath = os.path.join(continent_path, filename)  # 🩹 Include continent in path
        try:
            print(f"📝 DEBUG: Attempting to load {filepath}")
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"✅ DEBUG: Successfully loaded JSON file: {filename}")

            # Get ISO key
            iso_key = list(data.keys())[0]
            country_info = data[iso_key]

            # Extract country name from first airport (new JSON structure)
            airports = country_info.get("airports", [])
            if airports and isinstance(airports[0], dict):
                country_name = airports[0].get("country", filename.replace(".json", "").title())
            else:
                country_name = filename.replace(".json", "").title()

            flag = country_flag(iso_key)
            table.append([i, flag, country_name])
        except Exception as e:
            print(f"❌ DEBUG: Failed to load {filename}: {e}")
            table.append([i, "❌", f"Error loading {filename}"])
    return tabulate(table, headers=["#", "🌐", "Country"], tablefmt="fancy_grid")



def render_airports(airport_list):
    table = []
    for i, a in enumerate(airport_list, 1):
        has_cargo = "✅" if a.get("has_cargo_terminal") else "❌"
        table.append([
            i,
            a.get("iata", "N/A"),
            a.get("city", "N/A"),
            a.get("name", "N/A"),
            a.get("airport_class", "N/A").capitalize(),
            a.get("airport_size", "N/A").capitalize(),
            has_cargo
        ])
    return tabulate(
        table,
        headers=["#", "IATA", "City", "Airport Name", "Class", "Size", "Cargo"],
        tablefmt="fancy_grid"
    )
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def render_aircraft_table(aircraft_subset):
    table = [
        [idx+1, ac["model"], ac.get("display_price", f"${ac['base_price']:,}"), ac["capacity"], f"{ac['range_km']:,} km", f"{ac['cruise_speed_kph']} kph"]
        for idx, ac in enumerate(aircraft_subset)
    ]
    headers = ["#", "Model", "Base Price", "Capacity", "Range", "Cruise Speed"]
    return tabulate(table, headers, tablefmt="fancy_grid")


def typewriter(text, speed=0.03, newline=True):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(speed)
    if newline:
        print()


def typewriter_multiline(lines, delay=0.03):
    for line in lines:
        for char in line:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        print()  # move to next line
    print()  # final line spacing

def typewriter_parallel(lines, delay=0.03):
    # Print blank lines first to reserve space
    for _ in lines:
        print()

    # Move the cursor back up to the first line
    sys.stdout.write(f"\033[{len(lines)}A")
    sys.stdout.flush()

    # Prepare padded lines (max display length)
    max_len = max(len(line) for line in lines)
    padded_lines = [line.ljust(max_len) for line in lines]

    for i in range(max_len):
        for idx, line in enumerate(padded_lines):
            # Move cursor to line idx
            sys.stdout.write(f"\033[{idx}E")  # Move down idx lines
            sys.stdout.write("\r")            # Carriage return
            sys.stdout.write(line[:i+1])      # Write partial line
            sys.stdout.write(f"\033[{idx}F")  # Move back to top
        sys.stdout.flush()
        time.sleep(delay)

    # Move cursor down to below the animation area
    sys.stdout.write(f"\033[{len(lines)}E\n")

def slow_print(text, delay=0.02):
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

# utils/render.py

def render_airports_detailed(airport_list):
    """Render airports with full details for browsing."""
    table = []
    for i, a in enumerate(airport_list, 1):
        has_cargo = "✅" if a.get("has_cargo_terminal") else "❌"
        table.append([
            i,
            a.get("iata", "N/A"),
            a.get("name", "N/A"),
            a.get("city", "N/A"),
            a.get("airport_class", "N/A").capitalize(),
            a.get("airport_size", "N/A").capitalize(),
            a.get("runway_length_m", 0),
            has_cargo,
            a.get("max_aircraft_class", "N/A")
        ])
    return tabulate(
        table,
        headers=[
            "#", "IATA", "Name", "City", "Class", "Size",
            "Runway Length (m)", "Cargo", "Max Aircraft Class"
        ],
        tablefmt="fancy_grid"
    )
def render_hub_selection_table(hub_page):
        table = []
        for hub in hub_page:
            table.append([hub["index"], hub["name"], hub["iata"], hub["city"], hub["country"]])
        return tabulate(table, headers=["#", "Name", "IATA", "City", "Country"], tablefmt="fancy_grid")

def render_origin_countries_options(items):
        table = []
        for idx, (iso, cont) in enumerate(items, 1):
            try:
                with open(os.path.join("Data/Airports", cont, f"{iso}.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                airports = data[iso].get("airports", [])
                country_name = airports[0].get("country", iso) if airports else iso
                table.append([idx, country_flag(iso), country_name])
            except:
                table.append([idx, "❌", iso])
        return tabulate(table, headers=["#", "Flag", "Country"], tablefmt="fancy_grid")

def render_origin_airport_demand_table(airport_list):
        clear_screen()
        table = []
        for idx, a in enumerate(airport_list, 1):
            demand = classify_demand(a.get("population", 0))
            table.append([idx, a.get("iata", "N/A"), a.get("city", "N/A"), a.get("name", "N/A"), a.get("airport_class", "N/A"), a.get("airport_size", "N/A"), demand])
        return tabulate(table, headers=["#", "IATA", "City", "Airport Name", "Class", "Size", "Demand"], tablefmt="fancy_grid")

def render_destination_country_options(items, origin_header=""):
    clear_screen()
    if origin_header:
        print(origin_header)
    table = []
    for idx, (iso, continent) in enumerate(items, 1):
        filepath = os.path.join("Data/Airports", continent, f"{iso}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            iso_key = list(data.keys())[0]
            airports = data[iso_key].get("airports", [])
            country_name = airports[0].get("country") if airports else iso
            flag = country_flag(iso_key)
            table.append([idx, flag, country_name])
        except:
            table.append([idx, "❌", f"Error loading {iso}.json"])
    return tabulate(table, headers=["#", "🌐", "Country"], tablefmt="fancy_grid")

def render_destination_airport_demand_table(dest_list, origin_header=""):
    clear_screen()
    if origin_header:
        print(origin_header)
    table = []
    for idx, a in enumerate(dest_list, 1):
        demand = classify_demand(a.get("population", 0))
        table.append([
            idx,
            a.get("iata", "N/A"),
            a.get("city", "N/A"),
            a.get("name", "N/A"),
            a.get("airport_class", "N/A"),
            a.get("airport_size", "N/A"),
            demand
        ])
    return tabulate(table, headers=["#", "IATA", "City", "Airport Name", "Class", "Size", "Demand"], tablefmt="fancy_grid")
