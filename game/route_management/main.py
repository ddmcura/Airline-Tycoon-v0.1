from game.utils.render import clear_screen
from game.route_management.create_routes import create_new_route
from game.route_management.view_routes import view_existing_routes
from game.route_management.pricing import edit_route_prices

def enter_route_management(game_state):
    while True:
        clear_screen()
        print("🌐 Airline Tycoon - Route Management")
        print("========================================")
        print("Create, view, and manage your airline's routes.\n")

        menu_options = [
            "[1] Create New Route",
            "[2] View Existing Routes",
            "[3] Edit Route Prices",
            "[4] Back to Main Menu"
        ]

        for option in menu_options:
            print(option)

        choice = input("\nSelect an option: ").strip()

        if choice == '1':
            create_new_route(game_state)
        elif choice == '2':
            view_existing_routes(game_state)
        elif choice == '3':
            edit_route_prices(game_state)
        elif choice == '4':
            break
        else:
            print("\n❌ Invalid choice. Please select a valid option.")
            input("Press Enter to continue...")
