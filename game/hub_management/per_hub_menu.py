# game/hub_management/per_hub_menu.py

from game.utils.render import clear_screen
from game.hub_management.details import (
    manage_facilities,
    purchase_airport,
    view_hub_routes,
    view_assigned_planes,
    view_hub_statistics,
    remove_hub
)
from game.game_state import get_active_airline


def enter_per_hub_menu(game_state, iso_code, iata_code):
    active_airline = get_active_airline(game_state)
    country_hubs = active_airline.get("hubs", {}).get(iso_code.upper(), {})
    hub_info = country_hubs.get(iata_code.upper(), {})

    if not hub_info:
        print(f"❌ Hub {iata_code} not found in {iso_code}.")
        input("Press Enter to return.")
        return

    hub_name = hub_info.get("name", "Unknown Airport")
    hub_city = hub_info.get("city", "Unknown City")

    while True:
        clear_screen()
        print(f"🏢 HUB: {hub_name} ({iata_code})")
        print("=" * 50)
        print(f"📍 Location: {hub_city}, {iso_code}\n")

        print("[1] 🏗 Purchase/Upgrade Facilities")
        print("[2] 🏢 Purchase Airport")
        print("[3] 🛫 View Routes")
        print("[4] ✈️ View Airplanes Assigned")
        print("[5] 📊 View Hub Statistics")
        print("[6] 🗑 Remove Hub")
        print("[0] ⬅️ Back to Hub List")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            manage_facilities(game_state, iso_code, iata_code)
        elif choice == "2":
            purchase_airport(game_state, iso_code, iata_code)
        elif choice == "3":
            view_hub_routes(game_state, iso_code, iata_code)
        elif choice == "4":
            view_assigned_planes(game_state, iso_code, iata_code)
        elif choice == "5":
            view_hub_statistics(game_state, iso_code, iata_code)
        elif choice == "6":
            remove_hub(game_state, iso_code, iata_code)
        elif choice == "0":
            break
        else:
            print("❌ Invalid input.")
            input("Press Enter to continue.")
