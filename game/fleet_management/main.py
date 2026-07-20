# game/fleet_management/main.py

from game.utils.render import clear_screen
from game.fleet_management.fleet_overview import view_fleet_overview
from game.fleet_management.maintenance import perform_maintenance

def enter_fleet_management(game_state):
    while True:
        clear_screen()
        print("🛩️  Airline Tycoon - Fleet Management")
        print("========================================")
        print("Manage your fleet: view aircraft stats, perform maintenance, or reconfigure layouts.\n")

        menu_options = [
            "[1] View Fleet Overview",
            "[2] Perform Maintenance (All / Selective)",
            "[3] Return to Main Menu"
        ]

        for option in menu_options:
            print(option)

        choice = input("\nSelect an option: ").strip()

        if choice == '1':
            view_fleet_overview(game_state)
        elif choice == '2':
            perform_maintenance(game_state)
        elif choice == '3':
            break
        else:
            print("\n❌ Invalid choice. Please select a valid option.")
            input("\nPress Enter to continue...")
