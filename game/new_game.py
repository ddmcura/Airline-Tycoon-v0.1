# New Game Module (game/new_game.py)
# This module handles the logic for starting a new game in Airline Tycoon.
import os
import json
from game.utils.save_utils import legacy_cleanup

from settings import DEV_MODE, set_difficulty, set_starting_date
from game import game_state
from game.hub_selector import choose_hub
from game.utils.render import clear_screen, slow_print
from game.game_loop import game_loop

def start_new_game():
    clear_screen()
    game_state.reset_game_state()
    legacy_cleanup(game_state.game_state)

    if DEV_MODE:
        print("🔁 game_state ID:", id(game_state.game_state))
        input("\n Press Enter to continue...")

    clear_screen()
    initial_money, difficulty, debt = set_difficulty()
    start_date = set_starting_date()
    clear_screen()

    print("🌟 Hello there! You must be the new boss?\n")
    print("Well I am Billie! Your new executive assistant. So glad to finally meet you!\n")
    print("First things first... what should I call you?")
    while True:
        ceo_name = input("Input Your Name: ").strip()
        confirm = input(f"💬{ceo_name}? Love it! Just making sure this is your final answer? (Y/N): ").strip().lower()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")
    clear_screen()
    print(f"\n🔥 {ceo_name}, wow that name's got some power!\n")
    print("Every sky titan needs a mighty empire in the clouds.\n")
    print("What should we call your airline?\n")
    while True:
        airline_name = input("Input Airline Name: ").strip()
        confirm = input(f"{airline_name}? Sounds legendary! Let's lock it in? (Y/N): ").strip().lower()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")

    print(f"\n{airline_name} is officially on the runway to greatness.\n")
    print("Time to choose your starting stronghold in this cutthroat industry.")
    input("\nPress Enter to continue...")
    clear_screen()

    # 🌟 Inject parent airline into airline_list and set current focus
    game_state.update_game_state({
        "settings": {
            "difficulty": difficulty,
            "starting_money": initial_money
        },
        "player_info": {
            "ceo_name": ceo_name,
            "airline_name": airline_name,
            "current_focus": airline_name
        },
        "airline_list": {
            airline_name: {
                "hubs": {},
                "routes": {},
                "fleet": {},
                "finances": {
                    "cash_on_hand": initial_money,
                    "debt": debt
                },
                "subsidiaries": {},
                "ai_mode": "player_controlled"
            }
        },
        "game_time": {
            "current_date": f"{start_date} 00:00"
        }
    })

    if DEV_MODE:
        print("🔁 game_state ID:", id(game_state.game_state))
        input("Press Enter to continue...")

    # Loop until player chooses a hub
    while True:
        selected_hub = choose_hub(caller="new_game")
        if selected_hub is None:
            clear_screen()
            print(f"😅 Oh {ceo_name}! I think you forgot to choose your main hub yet!")
            print("Please choose where your home base will be.")
            input("\nPress Enter to continue...")
        else:
            break

    if DEV_MODE:
        print("\n🔎 FINAL game_state before save:")
        print(json.dumps(game_state.game_state, indent=2))
        print("🔁 game_state ID:", id(game_state.game_state))

    game_state.autosave()

    # ✈️ Billie dialogue before entering game loop
    clear_screen()
    print(f"💬 Billie: Wow {selected_hub['name']}! How wonderful!")
    print("💬 Billie: I’m looking forward to watching this airline grow!")
    input("\nPress Enter to begin your journey...")

    if DEV_MODE:
        print("\n🧠 DEBUG inside start_new_game:")
        print(json.dumps(game_state.game_state, indent=2))
        input("\n✅ Game setup complete! Press Enter...")

    game_loop(game_state.game_state)

def load_game_menu():
    save_dir = "Saves"
    save_files = [f for f in os.listdir(save_dir) if f.endswith(".json")]

    if not save_files:
        print("⚠️ No save files found.")
        input("Press Enter to return to main menu...")
        return

    print("\n📂 Choose a save file from the list below:")
    for idx, filename in enumerate(save_files, start=1):
        print(f"{idx}. {filename}")

    while True:
        choice = input("\nEnter the number of your choice: ")
        if not choice.isdigit():
            print("❌ Please enter a valid number.")
            continue

        index = int(choice)
        if 1 <= index <= len(save_files):
            selected_file = save_files[index - 1]
            game_state.load_game(selected_file)

            ceo_name = game_state.game_state.get("player_info", {}).get("ceo_name", "CEO")
            print(f"\n👋 Welcome back, {ceo_name}!")
            input("Press Enter to continue...")

            # ✅ Launch the game loop now!
            game_loop(game_state.game_state)
            break
        else:
            print("❌ Invalid selection. Please try again.")

if __name__ == "__main__":
    start_new_game()
