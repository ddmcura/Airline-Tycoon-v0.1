# ================================
# game/utils/render.py starts here
# ================================

import os
import sys
import time
from tabulate import tabulate

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def slow_print(text, delay=0.02):
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

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
    sys.stdout.write(f"\033[{len(lines)}A")  # Move cursor up
    sys.stdout.flush()
    max_len = max(len(line) for line in lines)
    padded_lines = [line.ljust(max_len) for line in lines]
    for i in range(max_len):
        for idx, line in enumerate(padded_lines):
            sys.stdout.write(f"\033[{idx}E")  # Move down idx lines
            sys.stdout.write("\r")            # Carriage return
            sys.stdout.write(line[:i+1])      # Write partial line
            sys.stdout.write(f"\033[{idx}F")  # Move back up
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(f"\033[{len(lines)}E\n")

def render_aircraft_table(aircraft_subset):
    table = [
        [idx+1, ac["model"], f"₱{ac['base_price']:,}", ac["capacity"], f"{ac['range_km']:,} km", f"{ac['cruise_speed_kph']} kph"]
        for idx, ac in enumerate(aircraft_subset)
    ]
    headers = ["#", "Model", "Base Price", "Capacity", "Range", "Cruise Speed"]
    return tabulate(table, headers, tablefmt="fancy_grid")

def render_country_names(countries, path_to_continent):
    table = []
    for i, filename in enumerate(countries, 1):
        filepath = os.path.join(path_to_continent, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and len(data) == 1 and list(data.keys())[0].isalpha() and len(list(data.keys())[0]) == 2:
                iso_key = list(data.keys())[0]
                country_info = data[iso_key]
                country_name = country_info.get("country", filename.replace(".json", "").title())
                iso_code = iso_key
            else:
                country_name = data.get("country", filename.replace(".json", "").title())
                iso_code = data.get("iso", filename[:2].upper())
            flag = country_flag(iso_code)
            table.append([i, flag, country_name])
        except Exception as e:
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

# ================================
# game/utils/json_loader.py starts here
# ================================

import json

def load_json_files(directory):
    """
    Loads all JSON files in a directory into a list of dictionaries.
    """
    data_list = []
    if not os.path.exists(directory):
        print(f"⚠️ Directory {directory} does not exist.")
        return data_list

    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data_list.append(data)
            except Exception as e:
                print(f"❌ Failed to load {filename}: {e}")
    return data_list

# ================================
# game/utils/ui.py starts here
# ================================

def paginate(items, page_size=9, render_func=None):
    """
    Displays paginated items in the terminal, allowing navigation and selection.
    """
    current_page = 0
    total_pages = (len(items) - 1) // page_size + 1

    while True:
        start = current_page * page_size
        end = start + page_size
        page_items = items[start:end]

        print(f"\n Page {current_page + 1}/{total_pages}")
        if render_func:
            print(render_func(page_items))
        else:
            for i, item in enumerate(page_items, 1):
                print(f"{i}. {item}")

        print("\nN: Next | P: Prev | B: Back")
        choice = input("Input Choice: ").strip().lower()

        if choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "p" and current_page > 0:
            current_page -= 1
        elif choice == "b":
            return "BACK"
        elif choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(page_items):
                return page_items[index]
            else:
                print("Invalid choice. Try again.")
        else:
            print("Invalid Choice. Try Again.")

# ================================
# game/utils/formatting.py starts here
# ================================

def country_flag(code):
    if not code or len(code) != 2 or not code.isalpha():
        return "🏳️"  # fallback flag
    return ''.join(chr(127397 + ord(char.upper())) for char in code)
