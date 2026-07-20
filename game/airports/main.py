# game/airports/main.py

from game.utils.render import clear_screen
from game.airports.view_airports import view_all_airports

def enter_airports_menu(game_state):
    while True:
        clear_screen()
        print("🛫 AIRPORTS MENU\n" + "=" * 50)
        print('💬 Billie: "Here’s where we handle everything airport-related."\n')

        print("[1] 🌍 View All Airports")
        print("[2] 🔎 Search Airport (Coming Soon)")
        print("[0] ⬅ Return to Dashboard")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            view_all_airports(game_state)
        elif choice == "2":
            print("\n🚧 Search Airport feature is coming soon!")
            input("Press Enter to return...")
        elif choice == "0":
            print('💬 Billie: "Alright, heading back to the dashboard!"')
            break
        else:
            print("❌ Invalid input. Please try again.")
            input("Press Enter to continue...")
