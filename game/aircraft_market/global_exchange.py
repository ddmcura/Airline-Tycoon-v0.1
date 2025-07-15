# game/aircraft_market/global_exchange.py

import os
from utils.render import clear_screen
from game.aircraft_market.new_aircraft import enter_orville_prime

def enter_exchange(game_state):
    clear_screen()

    print("🌍✈️  WELCOME TO THE GLOBAL AIRCRAFT EXCHANGE ✈️🌍")
    print("=" * 60)
    print("Where dreams take wing — and fleets take form.\n")

    print("🚪 Choose your point of entry:")
    print("[1] 🛩️ Orville Prime Aviation  - Brand-new aircraft direct from factory")
    print("[2] 💼 LIPAD Leasing Hub        - Flexible lease deals from top lessors")
    print("[3] 🧰 Hangar 9                 - Used aircraft & black market finds")
    print("[0] ⬅️ Return to Main Menu")

    while True:
        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            # Placeholder — import and call later
            print("🛠️ Launching Orville Prime Aviation...")
            input("Press Enter to continue...")
            enter_orville_prime(game_state)

        elif choice == "2":
            print("🛠️ Entering LIPAD Leasing Hub...")
            input("Press Enter to continue...")

        elif choice == "3":
            print("🛠️ Opening Hangar 9 inventory...")
            input("Press Enter to continue...")

        elif choice == "0":
            print("Returning to dashboard...")
            break

        else:
            print("❌ Invalid input. Please choose a valid option.")
