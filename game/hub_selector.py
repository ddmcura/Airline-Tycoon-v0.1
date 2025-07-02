import os
import json
from tabulate import tabulate
#PAGINATE FUNCTION START#
def paginate(items, page_size=9, render_func=None):
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
            if 0<= index < len(page_items):
                return page_items[index]
            else:
                print("Invalid choice. Try again.")
        else:
            print("Invalid Choice. Try Again.")
#PAGINATE FUNCTION END

def country_flag(code):
    if not code or len(code) != 2 or not code.isalpha():
        return "🏳️"  # fallback flag
    return ''.join(chr(127397 + ord(char.upper())) for char in code)


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




# test for paginate
#airports = ["MNL", "DVO", "CEB", "TAG", "ILO", "CGY", "KLO", "ZAM", "GES", "LGP", "USU", "PPS"]
#selected = paginate(airports)
#print(f"\n You selected: {selected}")

#countries = [
#    {"country": "Philippines", "population": 113000000, "airports": ["MNL", "DVO", "CEB"]},
#    {"country": "Japan", "population": 125000000, "airports": ["HND", "NRT"]},
#    {"country": "Vietnam", "population": 98000000, "airports": ["SGN", "HAN"]},
#    {"country": "Thailand", "population": 69000000, "airports": ["BKK", "DMK"]},
#    {"country": "Malaysia", "population": 33000000, "airports": ["KUL", "PEN"]},
#    {"country": "Indonesia", "population": 270000000, "airports": ["CGK", "DPS", "SUB"]},
#    {"country": "Singapore", "population": 5700000, "airports": ["SIN"]},
#    {"country": "South Korea", "population": 51000000, "airports": ["ICN", "GMP"]},
#    {"country": "China", "population": 1410000000, "airports": ["PEK", "PVG", "CAN", "CTU"]},
#    {"country": "India", "population": 1390000000, "airports": ["DEL", "BOM", "BLR", "MAA"]},
#    {"country": "Nepal", "population": 30000000, "airports": ["KTM"]},
#]

#def render_country_table(items):
#    table = []
#    for i, country in enumerate(items, 1):
#        name = country.get("country", "Unknown")
#        population = f"{country.get('population', 0):,}"
#        airport_count = len(country.get("airports", []))
#        table.append([i, name, population, airport_count])
#    return tabulate(table, headers=["#", "Country", "Population", "# Airports"], tablefmt="fancy_grid")
#selected = paginate(countries, page_size=5, render_func=render_country_table)

#if selected == "BACK":
#    print("🔙 Back to previous menu.")
#else:
#    print(f"\n✅ You selected: {selected['country']}")

    

def choose_hub():
    #Step 1: Select Continent
    continent_path = "data/airports"
    continents = [c for c in os.listdir(continent_path) if os.path.isdir(os.path.join(continent_path, c))]

    print("\n🌍 Select Continent:")
    #for is for looping with a list
    continent_table = [[i, c.title()] for i, c in enumerate(continents, 1)]
    print(tabulate(continent_table, headers=["#", "Continent"], tablefmt="fancy_grid"))

    while True:
        try:
            continent_choice = int(input("Enter Number of Choice: ")) - 1
            chosen_continent = continents[continent_choice]
            break
        except (ValueError, IndexError):
            print("Please choose a valid number.")
        
    print(f"You have chosen {chosen_continent}")

    # Step 2: Select Country
    country_path = os.path.join(continent_path, chosen_continent)
    country_files = [f for f in os.listdir(country_path) if f.endswith(".json")]

    selected_country_file = paginate(
        country_files,
        page_size=9,
        render_func=lambda items: render_country_names(items, country_path)
    )

    if selected_country_file == "BACK":
        return choose_hub()

    # Remove .json to get clean name
    selected_country = selected_country_file.replace(".json", "")
    print(f"\nYou selected {selected_country.title()} ✅")

    # Load selected country's airport data
    country_json_path = os.path.join(country_path, selected_country_file)
    with open(country_json_path, "r", encoding="utf-8") as f:
        country_data = json.load(f)

    # Detect structure (either {"PH": {...}} or just airport list directly)
    if isinstance(country_data, dict) and len(country_data) == 1:
        iso = list(country_data.keys())[0]
        airport_list = country_data[iso]["airports"]
    else:
        airport_list = country_data["airports"]

# Paginate airport selection
    selected_airport = paginate(
        airport_list,
        page_size=9,
        render_func=render_airports
    )

    if selected_airport == "BACK":
        return choose_hub()

# Final confirmation
    

    return selected_airport
    

    
if __name__ == "__main__":
    choose_hub()
