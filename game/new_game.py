import sys
import os
from game.utils.dev import enable_dev_mode
enable_dev_mode()

from game.hub_selector import choose_hub

def start_new_game():
    print("Hello there! You must be the new CEO? Please tell me your name?\n")
    while True:
        ceo_name = input("Input Your Name: ").strip()
        confirm = input(f"{ceo_name}? Is that correct? (Y/N): ").strip()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")

    print(f"\nYes! {ceo_name}. I am Billie, your assistant, let's get started! As the new CEO of this company, what do you want to call your Airline?\n")
    while True:
        airline_name = input("Input Airline Name: ").strip()
        confirm = input(f"{airline_name}? Is that correct? (Y/N): ").strip()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")
    print(f"\n{airline_name} is such a cool name! Ok! Moving on, We will need to set up a Hub where you will start your Airline Journey\n")
    selected_airport = choose_hub()
    print(f"\n🛫 You selected: {selected_airport['name']} in {selected_airport['city']} ({selected_airport['iata']}) ✅")
    
if __name__ == "__main__":
    start_new_game()
