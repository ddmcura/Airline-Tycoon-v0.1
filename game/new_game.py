# New Game Module (game/new_game.py)
# This module handles the logic for starting a new game in Airline Tycoon.
import sys
import os
import json
from datetime import datetime
from tabulate import tabulate
from game.utils.dev import enable_dev_mode
enable_dev_mode()

import game_state
from game.hub_selector import choose_hub
from game_loop import game_loop

def set_difficulty():
    print("\n🎯 Game Setup Parameters\n")
    print("Select your starting difficulty:")

    difficulty_table = [
        [1, "Easy",    "₱500,000,000", "High demand\nCheap expenses"],
        [2, "Normal",  "₱300,000,000", "Normal demand\nNormal expenses"],
        [3, "Hard",    "₱100,000,000", "Lower demand\nHigher expenses"],
        [4, "Extreme", "None", "Very low demand\nVery high expenses\n+ ₱300M Outstanding Loan 💀"],
        [5, "Sandbox", "Unlimited 💸", "Coming soon..."]
    ]

    print(tabulate(difficulty_table, headers=["#", "Difficulty", "Starting Money", "Conditions"], tablefmt="fancy_grid"))

    choices = {
        "1": ("hard", 500_000_000, 0),
        "2": ("normal", 300_000_000, 0),
        "3": ("hard", 100_000_000, 0),
        "4": ("extreme", 0, 300_000_000)
    }

    choice = ""
    while choice not in choices:
        choice = input("Enter your choice (1-4): ").strip()
        if choice == "5":
            print("\n🧪 Sandbox mode is not available yet — stay tuned!\n")

    difficulty, initial_money, debt = choices[choice]
    
    return initial_money, difficulty, debt

def set_starting_date():
    default = datetime.now().strftime("%m-%d-%Y")  # 👈 Format: MM-DD-YYYY
    while True:
        user_input = input(f"Enter your starting date (MM-DD-YYYY) [default: {default}]: ").strip()
        if not user_input:
            return datetime.now().strftime("%Y-%m-%d")  # 👈 Internally store as YYYY-MM-DD
        
        try:
            parsed_date = datetime.strptime(user_input, "%m-%d-%Y")
            return parsed_date.strftime("%Y-%m-%d")  # 👈 Convert to standard ISO format
        except ValueError:
            print("❌ Invalid format. Please use MM-DD-YYYY.")



def start_new_game():
    game_state.reset_game_state()
    print("🔁 game_state ID:", id(game_state.game_state))

    initial_money, difficulty, debt = set_difficulty()
    start_date = set_starting_date()
    print("Hello there! You must be the new CEO? Please tell me your name?\n")
    while True:
        ceo_name = input("Input Your Name: ").strip()
        confirm = input(f"{ceo_name}? Is that correct? (Y/N): ").strip().lower()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")

    print(f"\nYes! {ceo_name}. I am Billie, your assistant. Let's get started! As the new CEO of this company, what do you want to call your Airline?\n")
    while True:
        airline_name = input("Input Airline Name: ").strip()
        confirm = input(f"{airline_name}? Is that correct? (Y/N): ").strip().lower()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")

    print(f"\n{airline_name} is such a cool name! Ok! Moving on, we will need to set up a Hub where you will start your Airline Journey\n")

    game_state.update_game_state({
        "settings": {
            "difficulty": difficulty,
            "starting_money": initial_money
        },
        "finances": {
            "cash_on_hand": initial_money,
            "debt": debt
        },
        "player_info": {
            "ceo_name": ceo_name,
            "airline_name": airline_name
        },
        "game_time": {
            "current_date": f"{start_date} 00:00"
        }
    })

    print("🔁 game_state ID:", id(game_state.game_state))

    choose_hub()

    print("\n🔎 FINAL game_state before save:")
    print(json.dumps(game_state.game_state, indent=2))
    
    print("🔁 game_state ID:", id(game_state.game_state))

    game_state.autosave()
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
