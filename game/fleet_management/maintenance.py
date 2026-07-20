# game/fleet_management/maintenance.py

from game.utils.render import clear_screen
from game.utils.ui import paginate
from game.game_state import get_active_airline
from game.fleet_management.core import get_aircraft_by_reg

def perform_maintenance(game_state, aircraft=None):
    clear_screen()
    print("🛠️ Perform Maintenance")
    print("=" * 40)

    if aircraft:
        # Match reg_no via identity for one-off calls
        active_airline = get_active_airline(game_state)
        fleet = active_airline.get("fleet", {})
        reg_no = next((k for k, v in fleet.items() if v is aircraft), "UNKNOWN")
        _repair_aircraft(reg_no, aircraft)

        input("Press Enter to return...")
        return

    # No specific aircraft? Show list to choose
    active_airline = get_active_airline(game_state)
    fleet = active_airline.get("fleet", {})

    if not fleet:
        print("❌ No aircraft in fleet.")
        input("Press Enter to return...")
        return

    aircraft_list = []
    for reg, ac in fleet.items():
        aircraft_list.append({
            "reg_no": reg,
            "model": ac.get("model", "Unknown"),
            "condition": ac.get("condition", 100),
            "cleanliness": ac.get("cleanliness", 100),
        })

    def render_maintenance_page(page):
        from tabulate import tabulate
        headers = ["#", "Model", "Reg No", "Condition", "Cleanliness"]
        rows = []
        for idx, ac in enumerate(page, 1):
            rows.append([
                idx,
                ac["model"],
                ac["reg_no"],
                f"{ac['condition']}%",
                f"{ac['cleanliness']}%"
            ])
        return tabulate(rows, headers, tablefmt="fancy_grid")

    selected = paginate(aircraft_list, page_size=7, render_func=render_maintenance_page)

    if selected == "BACK":
        return

    reg_no = selected["reg_no"]
    aircraft = get_aircraft_by_reg(game_state, reg_no)
    if not aircraft:
        print("❌ Aircraft not found.")
        input("Press Enter to return...")
        return

    _repair_aircraft(reg_no, aircraft)
    input("Press Enter to return...")

def _repair_aircraft(reg_no, aircraft):


    print(f"✈️ Performing maintenance on {aircraft['model']} ({reg_no})")
