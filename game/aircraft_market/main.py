# game/aircraft_market/global_exchange.py

import os
from game.utils.render import clear_screen
from game.aircraft_market.new_aircraft import enter_orville_prime
from game.aircraft_market.leasing import enter_lipad_leasing
from game.aircraft_market.used_market import enter_hangar_9

def enter_exchange(game_state):
    while True:
        clear_screen()

        print("🌍✈️  WELCOME TO THE GLOBAL AIRCRAFT EXCHANGE ✈️🌍")
        print("=" * 60)
        print("Where dreams take wing — and fleets take form.\n")

        print("🚪 Choose your point of entry:")
        print("[1] 🛩️ Orville Prime Aviation  - Brand-new aircraft direct from factory")
        print("[2] 💼 LIPAD Leasing Hub        - Flexible lease deals from top lessors")
        print("[3] 🧰 Hangar 9                 - Used aircraft & black market finds")
        print("[0] ⬅️ Return to Dashboard")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            enter_orville_prime(game_state)

        elif choice == "2":
            enter_lipad_leasing(game_state)

        elif choice == "3":
            enter_hangar_9(game_state)

        elif choice == "0":
            print("Returning to dashboard...")
            return  # Fully exit back to game_loop()

        else:
            print("❌ Invalid input. Please choose a valid option.")
