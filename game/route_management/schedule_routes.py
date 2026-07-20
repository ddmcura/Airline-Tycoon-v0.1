# game/route_management/schedule_routes.py

from game.utils.render import clear_screen
from game.route_management.billie_ai import run_feasibility_simulation
from game.game_state import get_active_airline

def schedule_route(game_state):
    clear_screen()
    print("📅 Route Scheduling")
    print("-" * 40)

    active_airline = get_active_airline(game_state)
    routes = active_airline.get("routes", {})

    if not routes:
        print("❌ No routes available to schedule.")
        input("Press Enter to return...")
        return

    # Placeholder for scheduling logic
    print("Step 1: Assign Aircraft")
    print("Step 2: Set Frequency & Times")
    print("\n🤖 Billie AI Feasibility Simulation (₱100,000)")
    print("Projected Load Factor: 82%")
    print("Operating Cost/Flight: ₱1,200,000")
    print("Estimated Monthly Profit: ₱4,000,000")

    input("\nPress Enter to save route and return...")
