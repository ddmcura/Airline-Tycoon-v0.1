
import os
import json

def choose_hub():
    # 🔹 Step 1: Select Continent
    continent_path = "data/airports"
    continents = [c for c in os.listdir(continent_path) if os.path.isdir(os.path.join(continent_path, c))]

    print("\n🌍 Select Continent:")
    for i, c in enumerate(continents, 1):
        print(f"{i}. {c.capitalize()}")

    while True:
        try:
            continent_choice = int(input("Enter choice: ")) - 1
            chosen_continent = continents[continent_choice]
            break
        except (ValueError, IndexError):
            print("Invalid input. Please enter a valid number.")

    # 🔹 Step 2: Select Country
    country_path = os.path.join(continent_path, chosen_continent)
    country_files = [f for f in os.listdir(country_path) if f.endswith(".json")]
    countries = [f.replace(".json", "") for f in country_files]

    print(f"\n🌎 Select Country in {chosen_continent.capitalize()}:")
    for i, c in enumerate(countries, 1):
        print(f"{i}. {c.capitalize()}")

    while True:
        try:
            country_choice = int(input("Enter choice: ")) - 1
            chosen_country = countries[country_choice]
            break
        except (ValueError, IndexError):
            print("Invalid input. Please enter a valid number.")

    # 🔹 Step 3: Load Airport Data
    file_path = os.path.join(country_path, f"{chosen_country}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Assumes the first key is the country code like "PH"
    airport_list = list(data.values())[0]["airports"]

    print(f"\n🛫 Select Airport in {chosen_country.capitalize()}:")
    for i, airport in enumerate(airport_list, 1):
        print(f"{i}. {airport['iata']} - {airport['name']} ({airport['city']})")

    # 🔹 Step 4: Choose Airport
    while True:
        try:
            airport_choice = int(input("Enter choice: ")) - 1
            selected_airport = airport_list[airport_choice]
            break
        except (ValueError, IndexError):
            print("Invalid input. Please enter a valid number.")

    print(f"\n✅ You selected: {selected_airport['name']} in {selected_airport['city']} ({selected_airport['iata']})")
    return selected_airport
