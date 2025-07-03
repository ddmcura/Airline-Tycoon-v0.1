import os
import json
from tabulate import tabulate
from .formatting import country_flag

def render_country_names(countries, path_to_continent):
    table = []
    for i, filename in enumerate(countries, 1):
        filepath = os.path.join(path_to_continent, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Get the ISO code inside the file
            # Handles both formats: {"XX": {...}} or {"iso": "XX", ...}
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