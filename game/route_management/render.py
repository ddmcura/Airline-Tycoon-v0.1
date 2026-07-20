from game.utils.render import (
    slow_print,
    render_airports,
    country_flag,
    render_hub_selection_table,
    render_origin_countries_options,
    render_origin_airport_demand_table,
    render_destination_country_options,
    render_destination_airport_demand_table
)

from tabulate import tabulate

def render_route_table(routes_dict):
    table = []
    for route_id, route_info in routes_dict.items():
        origin = f"{route_info.get('origin_name', 'Unknown')} ({route_info.get('origin_iata', '---')})"
        destination = f"{route_info.get('destination_name', 'Unknown')} ({route_info.get('destination_iata', '---')})"
        route_type = route_info.get("route_type", "Unknown")
        status = route_info.get("status", "Planned")
        table.append([
            route_id,
            origin,
            destination,
            route_type,
            status,
            route_info.get("base_daily_demand", 0)
        ])
    return tabulate(table, headers=["Route ID", "Origin", "Destination", "Type", "Status", "Base Demand"], tablefmt="fancy_grid")
