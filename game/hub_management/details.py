# game/hub_management/details.py

from game.game_state import get_active_airline
from game.hub_management.core import remove_hub_from_airline
from game.utils.render import clear_screen
from tabulate import tabulate

def manage_facilities(game_state, iso_code, iata_code):
    hub = get_active_airline(game_state).get("hubs", {}).get(iso_code.upper(), {}).get(iata_code.upper())

    if not hub:
        print(f"❌ Hub {iata_code} not found in {iso_code}.")
        input("Press Enter to return...")
        return

    clear_screen()
    print(f"🏗 Managing Facilities for {hub['name']} ({iata_code})\n")

    facilities = hub.get("facilities", {})
    for facility, status in facilities.items():
        print(f"{facility.replace('_', ' ').title()}: {'✅' if status else '❌'}")

    print("\n🚧 Facility upgrades coming soon.")
    input("Press Enter to return...")

def purchase_airport(game_state, iso_code, iata_code):
    hub = get_active_airline(game_state).get("hubs", {}).get(iso_code.upper(), {}).get(iata_code.upper())

    if not hub:
        print(f"❌ Hub {iata_code} not found in {iso_code}.")
        input("Press Enter to return...")
        return

    clear_screen()
    print(f"🏢 Purchase Airport: {hub['name']} ({iata_code})\n")

    if hub.get("airport_owned", False):
        print("✅ You already own this airport outright.")
    else:
        print("💸 Purchasing this airport will give you full control over its operations.")
        confirm = input("Do you want to proceed with the purchase? (y/n): ").strip().lower()
        if confirm == "y":
            hub["airport_owned"] = True
            print(f"✅ {hub['name']} is now fully owned by your airline!")
        else:
            print("❌ Purchase cancelled.")

    input("Press Enter to return...")

def view_hub_statistics(game_state, iso_code, iata_code):
    hub = get_active_airline(game_state).get("hubs", {}).get(iso_code.upper(), {}).get(iata_code.upper())

    if not hub:
        print(f"❌ Hub {iata_code} not found in {iso_code}.")
        input("Press Enter to return...")
        return

    clear_screen()
    print(f"📊 Statistics for {hub['name']} ({iata_code})\n")

    stats = hub.get("stats", {})

    if not stats:
        print("❌ No statistics available for this hub yet.")
    else:
        table = [[stat.replace('_', ' ').title(), value] for stat, value in stats.items()]
        print(tabulate(table, headers=["Statistic", "Value"], tablefmt="fancy_grid"))

    input("Press Enter to return...")

def view_assigned_planes(game_state, iso_code, iata_code):
    active_airline = get_active_airline(game_state)
    country_hubs = active_airline.get("hubs", {}).get(iso_code.upper(), {})
    hub = country_hubs.get(iata_code.upper())

    if not hub:
        print(f"❌ Hub {iata_code} not found in {iso_code}.")
        input("Press Enter to return...")
        return

    clear_screen()
    print(f"✈️ Airplanes Assigned to {hub['name']} ({iata_code})\n")

    assigned_planes = hub.get("assigned_planes", [])

    if not assigned_planes:
        print("❌ No airplanes are currently assigned to this hub.")
    else:
        table = []
        fleet = active_airline.get("fleet", {})
        for reg_no in assigned_planes:
            aircraft = fleet.get(reg_no, {})
            table.append([
                reg_no,
                aircraft.get("model", "Unknown"),
                aircraft.get("status", "Inactive")
            ])

        print(tabulate(table, headers=["Registration", "Model", "Status"], tablefmt="fancy_grid"))

    input("Press Enter to return...")

def view_hub_routes(game_state, iso_code, iata_code):
    hub = get_active_airline(game_state).get("hubs", {}).get(iso_code.upper(), {}).get(iata_code.upper())

    if not hub:
        print(f"❌ Hub {iata_code} not found in {iso_code}.")
        input("Press Enter to return...")
        return

    clear_screen()
    print(f"🛫 Routes for {hub['name']} ({iata_code})\n")

    routes = hub.get("routes", {})

    if not routes:
        print("❌ No routes have been created for this hub yet.")
    else:
        table = []
        for route_id, route_info in routes.items():
            destination_name = route_info.get("destination", {}).get("name", "Unknown")
            table.append([
                route_id,
                destination_name,
                route_info.get("status", "Planned"),
                route_info.get("frequency", "Not Set")
            ])

        print(tabulate(table, headers=["Route ID", "Destination", "Status", "Frequency"], tablefmt="fancy_grid"))

    input("Press Enter to return...")

def remove_hub(game_state, iso_code, iata_code):
    clear_screen()
    print(f"🗑 Removing Hub: {iata_code}\n")

    confirm = input(f"⚠️ Are you sure you want to remove {iata_code}? This action cannot be undone. (y/n): ").strip().lower()
    if confirm == "y":
        success = remove_hub_from_airline(game_state, iso_code, iata_code)
        if success:
            print(f"✅ Hub {iata_code} has been removed from {iso_code}.")
        else:
            print("❌ Hub not found.")
    else:
        print("❌ Hub removal cancelled.")

    input("Press Enter to return...")