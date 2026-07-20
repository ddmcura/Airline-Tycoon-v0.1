# game/hub_management/add_hub.py

from game.hub_selector import choose_hub
from game.utils.render import clear_screen
from game.hub_management.core import add_hub_to_airline

def acquire_new_hub(game_state):
    clear_screen()
    print("🌍 Let's expand your empire with a new hub!\n")

    selected_airport = choose_hub(caller="add_hub")

    if selected_airport:
        iso_code = selected_airport.get("iso", "XX")
        iata = selected_airport["iata"]
        region = selected_airport.get("region", "Asia")  # Fallback default

        # ✅ Use new core function
        add_hub_to_airline(game_state, selected_airport, region, iso_code)

        print(f"✅ {selected_airport['name']} ({iata}) has been added to your airline's network!")
    else:
        print("❌ Hub acquisition canceled.")

    input("Press Enter to return to Hub Management...")
