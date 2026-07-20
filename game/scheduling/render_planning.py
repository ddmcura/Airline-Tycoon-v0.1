"""Tables for demand-aware schedule planning."""

from tabulate import tabulate


def render_route_planning_table(page):
    table = [
        [
            index + 1,
            route["label"],
            route["demand_summary"],
            f"{route['duration']}m + 30m",
        ]
        for index, route in enumerate(page)
    ]
    return tabulate(
        table,
        headers=[
            "#",
            "Route Pair",
            "Demand / Scheduled Seats / Demand Left",
            "Flight Time",
        ],
        tablefmt="fancy_grid",
    )
