# game/fleet_management/aircraft_detail.py

from game.utils.render import clear_screen
from game.utils.seating import assign_seat_layout
from game.fleet_management.maintenance import perform_maintenance
from game.game_state import get_active_airline
from game.fleet_management.core import remove_aircraft_by_reg


def aircraft_detail(game_state, aircraft):
    active_airline = get_active_airline(game_state)
    active_airline = get_active_airline(game_state)
    fleet = active_airline.get("fleet", {})

    # 🔍 Find reg_no by matching object identity
    reg_no = next((k for k, v in fleet.items() if v is aircraft), None)

    if not reg_no:
        print("❌ Could not determine registration number of aircraft.")
        input("Press Enter to return...")
        return

    aircraft_data = aircraft



    while True:
        print("🧠 DEBUG aircraft_detail() received:")
        print("aircraft =", aircraft)
        input("Press Enter to continue...")

        clear_screen()
        print(f"🛫 Aircraft: {reg_no} ({aircraft_data.get('model', 'N/A')})")

        print("=" * 40)
        print(f"Hub: {aircraft_data.get('hub', 'N/A')}")
        print(f"Status: {aircraft_data.get('status', 'N/A')}")
        print(f"Age: {aircraft_data.get('age', 'N/A')}")
        print(f"Total Passengers Delivered: {aircraft_data.get('total_pax', 0):,}")
        print(f"Total Distance Flown: {aircraft_data.get('distance_flown', 0):,} km")
        print(f"Total Revenue: ₱{aircraft_data.get('revenue', 0):,}")
        print(f"Maintenance Condition: {aircraft_data.get('condition', 100)}%")
        print(f"Cabin Cleanliness: {aircraft_data.get('cleanliness', 100)}%\n")

        options = [
            "[1] Reconfigure Seats",
            "[2] Perform Maintenance",
            "[3] Sell Aircraft",
            "[4] Back to Fleet Overview"
        ]
        for option in options:
            print(option)

        choice = input("\nSelect an option: ").strip()

        if choice == '1':
            clear_screen()
            print("💺 Reconfigure Seats")
            print("=" * 40)
            # Get accurate seat count from aircraft_reference
            active_airline = get_active_airline(game_state)
            aircraft_ref = game_state.get("aircraft_reference", {})
            model = aircraft_data.get("model")

            default_capacity = aircraft_ref.get(model, {}).get("capacity", 0)
            layout = assign_seat_layout(default_capacity)

            aircraft_data["seat_layout"] = layout
            print("✅ Seat layout updated.")
            input("Press Enter to return...")
        elif choice == '2':
            perform_maintenance(game_state, aircraft_data)
        elif choice == '3':
            sell_aircraft(game_state, aircraft_data)

            break  # Exit detail view after selling
        elif choice == '4':
            break
        else:
            print("❌ Invalid choice. Please try again.")
            input("Press Enter to continue...")

def sell_aircraft(game_state, aircraft):


    clear_screen()
    print("💸 Sell Aircraft")
    print("=" * 40)

    print("🧠 DEBUG - sell_aircraft received:")
    print("aircraft =", aircraft)
    print("type:", type(aircraft))
    input("Press Enter to continue...")


    if not aircraft:
        print("❌ No aircraft selected to sell.")
        input("Press Enter to return...")
        return

    # 🔍 Match the aircraft object to its reg_no key
    active_airline = get_active_airline(game_state)
    reg_no = None
    for key, obj in active_airline.get("fleet", {}).items():
        if obj is aircraft:
            reg_no = key
            break

    if not reg_no:
        print("❌ Could not match aircraft to registration number.")
        input("Press Enter to return...")
        return

    confirm = input(f"Are you sure you want to sell {aircraft.get('model', 'Unknown')} ({reg_no})? (y/n): ").strip().lower()
    if confirm == "y":
        removed = remove_aircraft_by_reg(game_state, reg_no)
        if removed:
            print(f"✅ Aircraft {reg_no} sold successfully!")
        else:
            print("❌ Sale failed. Aircraft not found.")
    else:
        print("❌ Sale cancelled.")

    input("Press Enter to return...")
