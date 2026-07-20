# game/aircraft_market/used_market.py

import random
from game.utils.render import clear_screen
from tabulate import tabulate

def enter_hangar_9(game_state):
    # Add a dummy pool if it doesn't exist yet
    if "used_market_pool" not in game_state or not game_state["used_market_pool"]:
        game_state["used_market_pool"] = get_dummy_used_market_pool()

    while True:
        clear_screen()
        print("🧰 HANGAR 9 - USED AIRCRAFT MARKET")
        print("=" * 50)
        print("Where fleets go to get a second life.\n")

        print("[1] 🔍 View Used Aircraft Listings")
        print("[2] 📂 View Your Active Bids")
        print("[0] ⬅️ Return to Global Aircraft Exchange")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            view_used_aircraft_listings(game_state)
        elif choice == "2":
            view_active_bids(game_state)
        elif choice == "0":
            print("Returning to Global Aircraft Exchange...")
            from game.aircraft_market.main import enter_exchange
            enter_exchange(game_state)
            return
        else:
            print("❌ Invalid input.")
            input("Press Enter to continue...")

def view_used_aircraft_listings(game_state):
    clear_screen()
    used_pool = game_state.get("used_market_pool", [])

    if not used_pool:
        print("🚧 No used aircraft available right now.")
        print("✅ New listings appear weekly as airlines offload planes.")
        input("Press Enter to return...")
        return

    table = []
    for idx, plane in enumerate(used_pool, start=1):
        table.append([
            idx,
            plane["model"],
            plane["seller_airline"],
            f"{plane['age']} yrs",
            f"{plane['flight_hours']:,} hrs",
            plane["condition"],
            f"₱{plane['price']:,.0f}",
            f"{plane['weeks_remaining']} wks left"
        ])
    print(tabulate(table, headers=[
        "#", "Aircraft", "Seller", "Age", "Flight Hours", "Condition", "Price", "Expires"
    ], tablefmt="fancy_grid"))

    print("\n[0] ⬅️ Back")
    choice = input("\nSelect an aircraft to inspect or [0] Back: ").strip()
    if choice == "0":
        return
    elif choice.isdigit() and 1 <= int(choice) <= len(used_pool):
        selected_plane = used_pool[int(choice) - 1]
        inspect_used_aircraft(selected_plane)
    else:
        print("❌ Invalid selection.")
        input("Press Enter to continue...")

def inspect_used_aircraft(plane):
    clear_screen()
    print(f"✈️ Inspecting: {plane['model']}")
    print("=" * 50)
    print(f"Seller: {plane['seller_airline']}")
    print(f"Age: {plane['age']} years")
    print(f"Flight Hours: {plane['flight_hours']:,} hrs")
    print(f"Condition: {plane['condition']}")
    print(f"Asking Price: ₱{plane['price']:,.0f}")
    print(f"Listing expires in {plane['weeks_remaining']} weeks.\n")
    print("⚠️ Purchase flow not implemented yet.")
    input("Press Enter to return...")

def view_active_bids(game_state):
    clear_screen()
    print("📂 Active Bids")
    print("=" * 50)
    print("🚧 Feature coming soon.")
    input("Press Enter to return...")

def get_dummy_used_market_pool():
    """
    Creates a static pool of dummy used aircraft for testing Hangar 9 UI.
    """
    return [
        {
            "model": "Airbus A320",
            "seller_airline": "SkyWings (Philippines)",
            "age": 12,
            "flight_hours": 34000,
            "condition": "B",
            "price": 32000000,
            "weeks_remaining": 8
        },
        {
            "model": "Boeing 737-800",
            "seller_airline": "AeroNova (Japan)",
            "age": 15,
            "flight_hours": 46000,
            "condition": "C",
            "price": 22000000,
            "weeks_remaining": 4
        },
        {
            "model": "De Havilland Dash 8",
            "seller_airline": "Blue Horizon (Australia)",
            "age": 7,
            "flight_hours": 12000,
            "condition": "A",
            "price": 15000000,
            "weeks_remaining": 10
        }
    ]
