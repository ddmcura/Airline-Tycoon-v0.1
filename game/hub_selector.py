import os
import json
from tabulate import tabulate
from game.utils.dev import enable_dev_mode
enable_dev_mode()

from game.utils import paginate, render_country_names, render_airports  # 🌟 simplified!

def choose_hub():
    # Step 1: Select Continent
    continent_path = "data/airports"
    continents = [c for c in os.listdir(continent_path) if os.path.isdir(os.path.join(continent_path, c))]

    print("\n🌍 Select Continent:")
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

    selected_country = selected_country_file.replace(".json", "")
    print(f"\nYou selected {selected_country.title()} ✅")

    # Load airport data
    country_json_path = os.path.join(country_path, selected_country_file)
    with open(country_json_path, "r", encoding="utf-8") as f:
        country_data = json.load(f)

    if isinstance(country_data, dict) and len(country_data) == 1:
        iso = list(country_data.keys())[0]
        airport_list = country_data[iso]["airports"]
    else:
        airport_list = country_data["airports"]

    # Step 3: Select Airport
    selected_airport = paginate(
        airport_list,
        page_size=9,
        render_func=render_airports
    )

    if selected_airport == "BACK":
        return choose_hub()

    return selected_airport

if __name__ == "__main__":
    choose_hub()
