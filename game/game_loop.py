import os
import json
import time
import game_state

from utils.render import clear_screen
from utils.time_utils import advance_game_day
from aircraft_market.global_exchange import enter_exchange

DEV_MODE = True  # Toggle this off in production

def render_dashboard(game_state):
    clear_screen()

    full_dt = game_state['game_time'].get("current_date", "Unknown")
    date = full_dt  # No hours for now
    airline = game_state['player_info']['airline_name']
    ceo = game_state['player_info']['ceo_name']
    funds = game_state['finances']['cash_on_hand']
    #reputation = game_state['player_info'].get('reputation', "Neutral")
    #model = game_state['player_info'].get('business_model', "Low Cost Carrier")
    #license_type = game_state['player_info'].get('license', "Domestic")

    print(f"📅 Date: {date}\n")
    print(f"✈️  Airline: {airline:<30} 💰 Funds: ₱{funds:,.2f}")
    print(f"👤 CEO: {ceo}")
    #print(f"🌟 Reputation: {reputation}")
    #print(f"📦 Type: Passenger")
    #print(f"🏷️  Business Model: {model}")
    #print(f"🪪 License: {license_type}\n")

    print("[1] Hub Management         (coming soon)")
    print("[2] Fleet Management       (coming soon)")
    print("[3] Global Aircraft Exchange")
    print("[4] Route Management       (coming soon)")
    print("[5] Save Game")
    print("[6] Quit to Main Menu")
    print("[7] Advance One Day")  # 🔥 Manual Tick

    if DEV_MODE:
        print("[D] Debug: Show Full Game State (dev only)")

def game_loop(game_state):
    running = True

    while running:
        render_dashboard(game_state)

        choice = input("\nEnter your choice: ").strip().lower()

        if choice == "5":
            game_state.save_game()
            print("💾 Game saved.")
            input("Press Enter to continue...")

        elif choice == "3":
            enter_exchange(game_state)

        elif choice == "6":
            confirm = input("Are you sure you want to quit? (y/n): ").lower()
            if confirm == "y":
                running = False

        elif choice == "7":
            advance_game_day(game_state)
            print("🕐 One in-game day has passed.")
            input("Press Enter to continue...")

        elif choice == "d" and DEV_MODE:
            clear_screen()
            print("🧠 FULL GAME STATE DEBUG DUMP:\n")
            print(json.dumps(game_state, indent=2))
            input("\nPress Enter to return to dashboard...")

        else:
            print("⚠️ That feature’s not implemented yet.")
            input("Press Enter to return to dashboard...")
