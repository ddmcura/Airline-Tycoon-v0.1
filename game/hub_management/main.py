# game/hub_management/main.py

from game.utils.render import clear_screen, slow_print
from game.hub_management.core import get_all_owned_hubs
from game.hub_management.view_hubs import view_owned_hubs
from game.hub_management.add_hub import acquire_new_hub

def enter_hub_management(game_state):
    clear_screen()
    slow_print("🏢 HUB MANAGEMENT\n" + "=" * 50)
    slow_print('💬 Billie: "Welcome back, boss! Here’s where we grow your empire from the ground up."\n')
    slow_print('💬 Billie: "We can check on your hubs, expand into new territories, or start building world-class facilities!"\n')

    while True:
        print("[1] 🌍 View Owned Hubs")
        print("[2] ➕ Acquire New Hubs")
        print("[0] ⬅️ Return to Dashboard")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            view_owned_hubs(game_state)
        elif choice == "2":
            acquire_new_hub(game_state)
        elif choice == "0":
            slow_print('💬 Billie: "Alrighty boss, taking you back to the dashboard!"')
            break
        else:
            print("❌ Invalid input. Please try again.")
            input("Press Enter to continue...")
