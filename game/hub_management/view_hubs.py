from game.utils.render import clear_screen
from tabulate import tabulate
from game.hub_management.core import get_all_owned_hubs
from game.hub_management.per_hub_menu import enter_per_hub_menu

def view_owned_hubs(game_state):
    clear_screen()
    print("📊 Your Airline Hubs\n")

    hubs_by_country = get_all_owned_hubs(game_state)

    if not hubs_by_country:
        print("❌ You do not own any hubs yet.")
        input("Press Enter to return...")
        return

    hub_list = []
    index = 1
    index_map = {}

    for iso_code, hubs in hubs_by_country.items():
        for iata, hub in hubs.items():
            hub_list.append([
                index,
                iata,
                hub.get("name", "Unknown"),
                hub.get("city", "Unknown"),
                hub.get("airport_size", "Unknown").capitalize(),
                iso_code
            ])
            index_map[str(index)] = (iso_code, iata)
            index += 1

    print(tabulate(hub_list, headers=["#", "IATA", "Name", "City", "Size", "Country"], tablefmt="fancy_grid"))

    print("\nSelect a hub to manage or press Enter to go back.")
    choice = input("Enter hub number: ").strip()

    if choice in index_map:
        iso_code, iata_code = index_map[choice]
        enter_per_hub_menu(game_state, iso_code, iata_code)
    else:
        print("⬅️ Returning to Hub Management...")
