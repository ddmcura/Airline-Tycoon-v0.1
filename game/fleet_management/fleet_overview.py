# game/fleet_management/fleet_overview.py

from game.utils.render import clear_screen
from game.utils.ui import paginate
from game.fleet_management.aircraft_detail import aircraft_detail
from game.fleet_management.render import render_fleet_page  # 👈 use local renderer
from game.game_state import get_active_airline
from tabulate import tabulate

def render_fleet_page(fleet_page):
    """Render a single page of fleet data as a table."""
    headers = ["#", "Model", "Reg No.", "Hub", "Status", "Age", "Total Pax"]
    table_data = []
    for idx, aircraft in enumerate(fleet_page, start=1):
        table_data.append([
            idx,
            aircraft.get("model", "N/A"),
            aircraft.get("reg_no", "N/A"),
            aircraft.get("hub", "N/A"),
            aircraft.get("status", "N/A"),
            aircraft.get("age", "N/A"),
            aircraft.get("total_pax", "0")
        ])
    return tabulate(table_data, headers, tablefmt="fancy_grid")

def view_fleet_overview(game_state):
    clear_screen()
    print("🛩️  Fleet Overview")
    print("=" * 40 + "\n")

    active_airline = get_active_airline(game_state)
    fleet = active_airline.get("fleet", {})

    if not fleet:
        print("❌ No aircraft in your fleet yet.")
        input("Press Enter to return...")
        return

    fleet_list = []
    for reg_no, aircraft in fleet.items():
        aircraft_entry = {
            "model": aircraft.get("model", "Unknown"),
            "reg_no": reg_no,
            "hub": aircraft.get("hub", "Unknown"),
            "status": aircraft.get("status", "Idle"),
            "age": aircraft.get("age", "0 yr"),
            "total_pax": aircraft.get("total_pax", 0)
        }
        fleet_list.append(aircraft_entry)

    selected_aircraft = paginate(fleet_list, page_size=9, render_func=render_fleet_page)

    print("🧠 SELECTED AIRCRAFT from paginate:", selected_aircraft)
    if isinstance(selected_aircraft, dict):
        print("🧠 selected_aircraft.get('reg_no') =", selected_aircraft.get("reg_no"))

    input("Press Enter to continue...")

    if not selected_aircraft or selected_aircraft in ("BACK", "CANCEL"):
        return

    reg_no = selected_aircraft.get("reg_no")
    if not reg_no:
        print("❌ No registration number found in selected aircraft.")
        input("Press Enter to return...")
        return

    real_aircraft = active_airline["fleet"].get(reg_no)
    if real_aircraft:
        aircraft_detail(game_state, real_aircraft)

        print("🧠 DEBUG: Passing into aircraft_detail():")
        print("real_aircraft =", real_aircraft)
        input("Press Enter to continue...")

    else:
        print(f"❌ Could not find aircraft with reg_no: {reg_no}")
        input("Press Enter to return...")
