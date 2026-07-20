# game/fleet_management/render.py

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
