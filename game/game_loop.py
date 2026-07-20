# game/game_loop.py
import json
from game.game_state import get_active_airline, save_game
from game.economy.currency import format_money

from game.utils.render import clear_screen
from game.utils.time_utils import advance_game_day
from game.aircraft_market.main import enter_exchange
from game.hub_management.main import enter_hub_management
from game.fleet_management.main import enter_fleet_management
from game.route_management.main import enter_route_management
from game.financial_reports.main import enter_financial_reports
from game.settings_menu import enter_settings_menu
from game.airports.main import enter_airports_menu
from game.scheduling.main import enter_schedule_management
#from game.schedule_management.main import enter_schedule_management
# No import for enter_airports since it's Coming Soon

DEV_MODE = True  # Toggle this off in production

def render_dashboard(game_state, menu_options):
    clear_screen()

    # Basic airline info
    full_dt = game_state['game_time'].get("current_date", "Unknown")
    date = full_dt
    airline = game_state['player_info'].get('airline_name', "Unknown Airline")
    ceo = game_state['player_info'].get('ceo_name', "CEO")
    funds = get_active_airline(game_state).get("finances", {}).get("cash_on_hand", 0)

    print(f"📅 Date: {date}")
    print(f"✈️  Airline: {airline:<30} Funds: {format_money(game_state, funds)}")
    print(f"👤 CEO: {ceo}\n")

    # Render menu dynamically
    for idx, (label, _) in enumerate(menu_options, start=1):
        print(f"[{idx}] {label}")

    print("\n[S] Save Game  |  [A] Advance One Day  |  [Q] Quit")
    if DEV_MODE:
        print("[D] Debug: Show Full Game State (DEV ONLY)")

def game_loop(game_state):
    running = True

    menu_options = [
        ("Hub Management", enter_hub_management),
        ("Fleet Management", enter_fleet_management),
        ("Global Aircraft Exchange", enter_exchange),
        ("Route Management", enter_route_management),
        ("Schedule Management", enter_schedule_management),
        ("Airports", enter_airports_menu),  # No action yet
        ("Financial Reports", enter_financial_reports),
        ("Settings", enter_settings_menu),
    ]

    while running:
        render_dashboard(game_state, menu_options)
        choice = input("\nEnter your choice: ").strip().lower()

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(menu_options):
                label, action = menu_options[index]
                if action:
                    action(game_state)
                else:
                    print(f"🚧 {label} feature is coming soon!")
                    input("Press Enter to continue...")
            else:
                print("❌ Invalid option.")
                input("Press Enter to continue...")
        elif choice == "s":
            save_game(game_state)
            print("💾 Game saved.")
            input("Press Enter to continue...")
        elif choice == "a":
            summary = advance_game_day(game_state)
            print("🕐 One in-game day has passed.")
            print(
                f"Flights: {summary['flights']}  |  "
                f"Passengers: {summary['passengers']:,}  |  "
                f"Net profit: {format_money(game_state, summary['profit'])}"
            )
            if summary.get("deadhead_flights"):
                print(f"Deadhead flights: {summary['deadhead_flights']} (no passengers)")
            if summary["skipped_flights"]:
                print(f"Skipped schedule entries: {summary['skipped_flights']}")
            input("Press Enter to continue...")
        elif choice == "q":
            confirm = input("Are you sure you want to quit? (y/n): ").lower()
            if confirm == "y":
                running = False
        elif choice == "d" and DEV_MODE:
            clear_screen()
            print("🧠 FULL GAME STATE DEBUG DUMP:\n")
            print(json.dumps(game_state, indent=2))
            input("\nPress Enter to return to dashboard...")
        else:
            print("⚠️ Invalid input. Try again.")
            input("Press Enter to continue...")
