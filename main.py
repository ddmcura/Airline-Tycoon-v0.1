# Main menu (root/main.py)
# Entry point for Airline Tycoon

import json
import os
import sys
import time
import random

def configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()
from game import game_state
from game.new_game import start_new_game, load_game_menu
from game.game_state import load_game
from game.game_loop import game_loop
from game.utils.render import clear_screen, typewriter, typewriter_multiline, typewriter_parallel  # 👈 Make sure this exists
from settings import DEV_MODE
from game.settings_menu import enter_settings_menu

def get_random_slogan():
    slogans = [
        "Where every flight tells a story.",
        "Taking your dreams to cruising altitude.",
        "Beyond borders, beyond limits.",
        "Sky's not the limit—it's home.",
        "Your journey, our passion.",
        "Fueled by ambition. Flown by excellence.",
        "Airborne ambitions, delivered daily.",
        "Because legends take off, not walk.",
        "We don't just fly. We elevate.",
        "Connecting worlds, one flight at a time.",
        "🛠️  Powered by Passion, Fueled by Code."
    ]
    return random.choice(slogans)

def show_main_menu():
    clear_screen()
    lines = [
        "🛫" * 30,
        "        ✈️  AIRLINE TYCOON v0.1  ✈️",
        "🛬" * 30
    ]
    typewriter_multiline(lines)
    typewriter("\nWelcome aboard, CEO. What would you like to do?\n")

    print(" [1] 🌟 New Game")
    time.sleep(0.25)
    print(" [2] 💾 Load Game")
    time.sleep(0.25)
    print(" [3] 📘 Tutorial")
    time.sleep(0.25)
    print(" [4] ⚙️  Settings")
    time.sleep(0.25)
    print(" [5] 🚪 Exit\n")
    time.sleep(0.25)
    typewriter(f"💬 {get_random_slogan()}\n")

def main():
    while True:
        show_main_menu()
        choice = input("🧭 Enter Your Choice: ").strip()

        if choice == "1":
            print("\n🎬 Starting a New Game!\n")
            start_new_game()

            if DEV_MODE:

                print("\n🔍 DEBUG - game_state BEFORE GAME LOOP:")
                print(json.dumps(game_state.game_state, indent=2))
            break

        elif choice == "2":
            print("\n📂 Loading a saved game...\n")
            load_game_menu()
            break

        elif choice == "3":
            print("\n📘 Tutorial - Coming soon!\n")
            input("Press Enter to return to main menu...")

        elif choice == "4":
            enter_settings_menu(game_state.game_state)

        elif choice == "5":
            print("\n👋 Thank you for flying with us. Goodbye!\n")
            break

        else:
            print("❌ Invalid choice. Please enter a number from 1 to 5.")
            input("Press Enter to try again...")

if __name__ == "__main__":
    main()
