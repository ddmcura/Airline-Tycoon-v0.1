# Main menu (root/main.py)
# This file serves as the entry point for the Airline Tycoon game.

from game.new_game import start_new_game
from game.game_state import load_game  # ✅ Add this

def show_main_menu():
    print("Welcome to Airline Tycoon")
    print("1. New Game")
    print("2. Load Game")
    print("3. Tutorial")
    print("4. Settings")
    print("5. Exit")

def main():
    while True:
        show_main_menu()
        choice = input("Enter Your Choice: ")
        
        if choice == "1":
            print("\nStarting a New Game!\n")
            start_new_game()
            break

        elif choice == "2":
            print("Choose a save file from the list below:\n")
            load_game()

        elif choice == "3":
            print("Welcome to the Tutorial!\n")
        
        elif choice == "4":
            print("Settings:\n")

        elif choice == "5":
            print("Thank you for playing! Good Bye!\n")
            break

main()
