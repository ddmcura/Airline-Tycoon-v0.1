# game/aircraft_market/catalogue.py
import os
import json
from game.utils.render import clear_screen, render_aircraft_table
from game.utils.ui import paginate
from tabulate import tabulate
from game.utils.seating import assign_seat_layout
from game.utils.registration import generate_registration_number
from game.aircraft_market.core_purchase import purchase_aircraft
from game.economy.currency import format_money

PLANES_DIR = "Data/planes"

def list_manufacturers(game_state):
    files = [f for f in os.listdir(PLANES_DIR) if f.endswith(".json")]
    manufacturers = [os.path.splitext(f)[0].replace("_", " ").title() for f in files]

    manufacturer_map = dict(zip(manufacturers, files))

    def render_manufacturer_table(manufacturer_subset):
        table = [
            [idx + 1, name]
            for idx, name in enumerate(manufacturer_subset)
        ]
        return tabulate(table, headers=["#", "Manufacturer"], tablefmt="fancy_grid")

    while True:
        clear_screen()
        print("🛠️  Select Aircraft Manufacturer:\n")

        selected = paginate(
            manufacturers,
            page_size=5,
            render_func=render_manufacturer_table
        )

        if selected in ["BACK", "CANCEL"]:
            return selected  # pass upward cleanly
        return manufacturer_map[selected]

def load_aircraft_from_file(filename):
    path = os.path.join(PLANES_DIR, filename)

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
    while True:
        manufacturer_file = list_manufacturers(game_state)
        if manufacturer_file in ["BACK", "CANCEL"]:
            return  # stay inside new_aircraft.py, just return clean

        aircraft_data = load_aircraft_from_file(manufacturer_file)
        for aircraft in aircraft_data:
            aircraft["display_price"] = format_money(
                game_state, aircraft["base_price"], decimals=0
            )

        chosen = paginate(aircraft_data, page_size=5, render_func=render_aircraft_table)
        if chosen == "BACK":
            continue  # go back to manufacturer selection
        elif chosen == "CANCEL" or chosen is None:
            return  # exit to enter_orville_prime()


        clear_screen()
        model = chosen["model"]
        price = chosen["full_data"]["purchase_price"]
        capacity = chosen["full_data"]["capacity"]
        default_display_layout = chosen["full_data"]["default_layout"]

        model_data = chosen["full_data"]

        print(f"\n✅ You selected the {model} ✈️\n")
        print("Default Cabin Layout (Display Only):")
        print("  First Class     : 0 seats")
        print("  Business Class  : 0 seats")
        print(f"  Economy Class   : {capacity} seats")
        print(f"✈️ Aircraft Cost: {format_money(game_state, price, decimals=0)}\n")

        layout_choice = input("Would you like to configure the seats? (Y/N): ").strip().upper()
        if layout_choice == "Y":
            layout = assign_seat_layout(capacity)  # Still economy-only in v1.0
            print("(Seat configuration module coming in v1.1 — full economy applied.)")
        else:
            layout = assign_seat_layout(capacity)

        # Choose hub
        airline = game_state["player_info"]["airline_name"]
        hubs_dict = game_state["airline_list"][airline].get("hubs", {})
        hub_iata_list = []

        for country_hubs in hubs_dict.values():
            hub_iata_list.extend(country_hubs.keys())

        if not hub_iata_list:
            print("\n❌ You do not have any hubs to assign this aircraft to.")
            input("Press Enter to return...")
            return


        print("\n📍 Choose a hub to assign these aircraft:")
        for idx, hub_code in enumerate(hub_iata_list, 1):
            print(f"[{idx}] {hub_code}")

        while True:
            try:
                hub_choice = int(input("Enter choice: "))
                if 1 <= hub_choice <= len(hub_iata_list):
                    selected_hub_iata = hub_iata_list[hub_choice - 1]
                    break
                else:
                    print("Invalid hub selection.")
            except ValueError:
                print("Please enter a valid number.")

        while True:
            try:
                quantity = int(input("How many would you like to purchase? "))
                if quantity <= 0:
                    print("Please enter a valid number.")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a number.")

        total_cost = quantity * price
        finances = game_state["airline_list"][airline].setdefault("finances", {})
        player_money = finances.get("cash_on_hand", 0)

        if total_cost > player_money:
            print("\n❌ You do not have enough funds to complete this purchase.")
            input("Press Enter to return...")
            return

        print("\n🧾 Purchase Summary")
        print("=" * 30)
        print(f"Model      : {model}")
        print(
            f"Seat Config: "
            f"{layout['economy']['seats']}Y "
            f"{layout['business_class']['seats']}J "
            f"{layout['first_class']['seats']}F"
        )

        print(f"Quantity   : {quantity}")
        print(f"Unit Price : {format_money(game_state, price, decimals=0)}")
        print(f"Total Cost : {format_money(game_state, total_cost, decimals=0)}")
        print(f"Hub        : {selected_hub_iata}")
        print("=" * 30)

        confirm = input("Confirm purchase? (Y/N): ").strip().upper()
        if confirm != "Y":
            print("❌ Purchase cancelled.")
            input("Press Enter to return...")
            return


        success, result = purchase_aircraft(game_state, model, model_data, selected_hub_iata, quantity)


        if not success:
            print(f"\n❌ {result}")
            input("Press Enter to return...")
            return

        layout = result["layout"]
        total_cost = result["total_cost"]


        seat_summary = (
            f"{layout['first_class']['seats']}F-"
            f"{layout['business_class']['seats']}J-"
            f"{layout['economy']['seats']}Y"
        )

        clear_screen()
        print("✅ Purchase Complete!")
        print(f"Added {quantity} aircraft: {model} - {seat_summary}")
        print(f"Assigned to hub: {selected_hub_iata}")
        print(f"Total Cost: {format_money(game_state, total_cost, decimals=0)}")
        input("\nPress Enter to return to Orville Prime...")
        return
