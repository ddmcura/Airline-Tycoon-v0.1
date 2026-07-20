# game/aircraft_market/leasing.py

import os
import json
from game.utils.render import clear_screen
from tabulate import tabulate
from game.utils.json_loader import load_json_files

LESSORS_DIR = "Data/lessors"

def enter_lipad_leasing(game_state):
    while True:
        clear_screen()
        print("🛩️ LIPAD LEASING HUB")
        print("=" * 50)
        print("Flexible fleet solutions for every airline.\n")

        print("[1] 🏢 View Leasing Companies")
        print("[2] 📂 View Active Leases")
        print("[0] ⬅️ Return to Global Aircraft Exchange")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            view_leasing_companies(game_state)
        elif choice == "2":
            view_active_leases(game_state)
        elif choice == "0":
            print("Returning to Global Aircraft Exchange...")
            # Lazy import to avoid circular dependency
            from game.aircraft_market.main import enter_exchange
            enter_exchange(game_state)
            return  # Exit Lipad Leasing completely
        else:
            print("❌ Invalid input. Please try again.")
            input("Press Enter to continue...")

def view_leasing_companies(game_state):
    lessors = load_json_files(LESSORS_DIR)
    if not lessors:
        print("⚠️ No leasing companies found.")
        input("Press Enter to return...")
        return

    while True:
        clear_screen()
        print("🏢 Available Leasing Companies")
        print("=" * 50)

        table = []
        for idx, lessor in enumerate(lessors, start=1):
            services = lessor.get("services", "unknown").replace("_", " ").title()
            table.append([idx, lessor["name"], services])

        print(tabulate(table, headers=["#", "Company", "Services"], tablefmt="fancy_grid"))
        print("\n[0] ⬅️ Return")

        choice = input("\nSelect a company: ").strip()

        if choice == "0":
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(lessors):
            selected_lessor = lessors[int(choice) - 1]
            view_lessor_details(game_state, selected_lessor)
        else:
            print("❌ Invalid selection.")
            input("Press Enter to try again...")

def view_lessor_details(game_state, lessor):
    while True:
        clear_screen()
        print(f"🏢 {lessor['name']}")
        print("=" * 50)
        print(f"Services: {lessor['services'].replace('_', ' ').title()}\n")

        menu_options = []
        if lessor["services"] in ["lease_only", "both"]:
            menu_options.append("[1] 🔥 View Planes for Lease")
        if lessor["services"] in ["rent_to_own_only", "both"]:
            menu_options.append("[2] 🏡 View Planes for Rent-to-Own")
        menu_options.append("[0] ⬅️ Back to Company List")

        for option in menu_options:
            print(option)

        choice = input("\nEnter your choice: ").strip()

        if choice == "1" and lessor["services"] in ["lease_only", "both"]:
            browse_lease_offers(lessor)
        elif choice == "2" and lessor["services"] in ["rent_to_own_only", "both"]:
            browse_rent_to_own_offers(lessor)
        elif choice == "0":
            break
        else:
            print("❌ Invalid input.")
            input("Press Enter to continue...")

def browse_lease_offers(lessor):
    fleet = lessor.get("fleet_for_lease", {})
    if not fleet:
        print("🚧 This company has no planes available for lease right now.")
        input("Press Enter to return...")
        return

    while True:
        clear_screen()
        print(f"🔥 Lease Offers - {lessor['name']}\n")
        table = []
        for idx, (model, details) in enumerate(fleet.items(), start=1):
            table.append([
                idx,
                model,
                f"₱{details['weekly_rate']:,.0f} / week",
                f"{details['available_units']} units"
            ])
        print(tabulate(table, headers=["#", "Aircraft", "Weekly Rate", "Available Units"], tablefmt="fancy_grid"))
        print("\n[0] ⬅️ Back")

        choice = input("\nSelect an aircraft to lease: ").strip()
        if choice == "0":
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(fleet):
            selected_model = list(fleet.keys())[int(choice) - 1]
            confirm_lease(selected_model, fleet[selected_model])
        else:
            print("❌ Invalid selection.")
            input("Press Enter to try again...")

def browse_rent_to_own_offers(lessor):
    fleet = lessor.get("fleet_for_rent_to_own", {})
    if not fleet:
        print("🚧 This company has no planes available for rent-to-own.")
        input("Press Enter to return...")
        return

    while True:
        clear_screen()
        print(f"🏡 Rent-to-Own Offers - {lessor['name']}\n")
        table = []
        for idx, (model, details) in enumerate(fleet.items(), start=1):
            terms = ", ".join(f"{term}y" for term in details["terms"])
            table.append([
                idx,
                model,
                f"₱{details['base_price']:,.0f}",
                f"Terms: {terms}"
            ])
        print(tabulate(table, headers=["#", "Aircraft", "Base Price", "Terms"], tablefmt="fancy_grid"))
        print("\n[0] ⬅️ Back")

        choice = input("\nSelect an aircraft for rent-to-own: ").strip()
        if choice == "0":
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(fleet):
            selected_model = list(fleet.keys())[int(choice) - 1]
            confirm_rent_to_own(selected_model, fleet[selected_model])
        else:
            print("❌ Invalid selection.")
            input("Press Enter to try again...")

def confirm_lease(model, details):
    clear_screen()
    print(f"✅ Lease Confirmation - {model}")
    print("=" * 50)
    print(f"Weekly Rate: ₱{details['weekly_rate']:,.0f}")
    print("⚠️ Lease flow logic not implemented yet.")
    input("Press Enter to return...")

def confirm_rent_to_own(model, details):
    clear_screen()
    print(f"✅ Rent-to-Own Confirmation - {model}")
    print("=" * 50)
    print(f"Base Price: ₱{details['base_price']:,.0f}")
    print("⚠️ Rent-to-Own flow logic not implemented yet.")
    input("Press Enter to return...")

def view_active_leases(game_state):
    clear_screen()
    print("📂 Active Leases")
    print("=" * 50)
    leases = game_state.get("active_leases", [])
    if not leases:
        print("📂 No active leases yet. Sign one today to grow your fleet!")
    else:
        for lease in leases:
            print(f"✈️ {lease['model']} - {lease['lessor']}")
    input("\nPress Enter to return...")
