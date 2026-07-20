from game.utils.render import clear_screen
from game.route_management.core import get_all_routes
from game.route_management import render

def view_existing_routes(game_state):
    clear_screen()
    print("🌍 Current Routes")
    print("-" * 40)

    routes = get_all_routes(game_state)

    if not routes:
        print("❌ No routes created yet.")
    else:
        print(render.render_route_table(routes))

    input("\nPress Enter to return to Route Management...")
