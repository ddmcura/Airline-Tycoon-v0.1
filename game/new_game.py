# New Game Module (game/new_game.py)
# This module handles the logic for starting a new game in Airline Tycoon.
import sys
import os
import json
from tabulate import tabulate
from game.utils.dev import enable_dev_mode
enable_dev_mode()

from game.game_state import game_state, save_game, reset_game_state, update_game_state
from game.hub_selector import choose_hub


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
        "1": ("easy", 500_000_000, 0),
        "2": ("normal", 300_000_000, 0),
        "3": ("hard", 100_000_000, 0),
        "4": ("extreme", 0, 300_000_000)
        # Note: No entry for 5 yet — it's just a teaser
    }

    choice = ""
    while choice not in choices:
        choice = input("Enter your choice (1-4): ").strip()
        if choice == "5":
            print("\n🧪 Sandbox mode is not available yet — stay tuned!\n")

    difficulty, initial_money, debt = choices[choice]
    update_game_state({
        "settings": {
            "difficulty": difficulty,
            "starting_money": initial_money
        },
        "finances": {
            "cash_on_hand": initial_money,
            "debt": debt
        }
    })
    return initial_money, difficulty, debt

def start_new_game():
    reset_game_state()
    initial_money, difficulty, debt = set_difficulty()

    print("Hello there! You must be the new CEO? Please tell me your name?\n")
    while True:
        ceo_name = input("Input Your Name: ").strip()
        confirm = input(f"{ceo_name}? Is that correct? (Y/N): ").strip().lower()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")


    print(f"\nYes! {ceo_name}. I am Billie, your assistant, let's get started! As the new CEO of this company, what do you want to call your Airline?\n")
    while True:
        airline_name = input("Input Airline Name: ").strip()
        confirm = input(f"{airline_name}? Is that correct? (Y/N): ").strip().lower()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")

    
    print(f"\n{airline_name} is such a cool name! Ok! Moving on, we will need to set up a Hub where you will start your Airline Journey\n")
    selected_airport = choose_hub(game_state)
    print("\n🔎 Game State at the end of setup:")
    print(json.dumps(game_state, indent=2))
    save_game(game_state)
    input("\n✅ Game setup complete! Press Enter to return to the Main Menu...")

    

    # Optional: Save the game state later using the variables we gathered
    # ceo_name, airline_name, selected_airport, initial_money, difficulty, debt

    
    
if __name__ == "__main__":
    
    start_new_game()
    
