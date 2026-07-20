# game/aircraft_market/new_aircraft.py

from game.utils.render import clear_screen

from game.aircraft_market.catalogue import start_aircraft_catalogue_flow

def enter_orville_prime(game_state):
    while True:
        clear_screen()

        print("🚩 ORVILLE PRIME AVIATION")
        print("=" * 50)
        print("Where firsts take flight again.")
        print("Welcome to Orville Prime Aviation — your gateway to brand-new,")
        print("factory-fresh aircraft built for the future of aviation.\n")

        print("🍭  MAIN MENU\n")
        print("[1] ✨ View Aircraft Catalogue")
        print("[2] 🔍 Search for Aircraft")
        print("[3] 📦 View Current Orders")
        print("[0] ⬅️ Return to Global Aircraft Exchange")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            start_aircraft_catalogue_flow(game_state)

        elif choice == "2":
            search_aircraft_menu()
        elif choice == "3":
            view_current_orders()
        elif choice == "0":
            print("Returning to Global Aircraft Exchange...")
            return
        else:
            print("❌ Invalid input. Please try again.")
            input("Press Enter to continue...")

# Placeholder functions
def view_aircraft_catalogue():
    clear_screen()
    print("✨ Aircraft Catalogue (Coming Soon)")
    input("Press Enter to return to the showroom...")

def search_aircraft_menu():
    clear_screen()
    print("🔍 Aircraft Search (Coming Soon)")
    input("Press Enter to return to the showroom...")

def view_current_orders():
    clear_screen()
    print("📦 Aircraft Orders (Coming Soon)")
    input("Press Enter to return to the showroom...")
