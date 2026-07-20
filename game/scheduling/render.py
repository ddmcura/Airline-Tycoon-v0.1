
from tabulate import tabulate
from game.scheduling.helpers import time_to_minutes


def render_aircraft_table(page, fleet):
    table = []
    for i, ac in enumerate(page, 1):
        reg = ac["reg"]
        schedule = fleet[reg].get("schedule", {})
        total_minutes = 0
        for day in schedule.values():
            for block in day.values():
                for flight in block:
                    s = time_to_minutes(flight["start_time"])
                    e = time_to_minutes(flight["end_time"])
                    total_minutes += (e - s)

        percent_used = round((total_minutes / 10080) * 100)

        table.append([
            i, ac["reg"], ac["model"], ac["hub"], f"{percent_used}%"
        ])
    return tabulate(table, headers=["#", "Reg No", "Model", "Hub", "% Capacity"], tablefmt="fancy_grid")

def render_route_table(page):
    table = [[i+1, r["id"], f"{r['from']} → {r['to']}", f"{r['duration']}m + 30m"] for i, r in enumerate(page)]
    return tabulate(table, headers=["#", "Route ID", "Route", "Flight Time"], tablefmt="fancy_grid")

def render_schedule_summary(aircraft_schedule):
    """
    Renders a clean day-by-day schedule summary table for a single aircraft.
    """
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    rows = []

    for day in days:
        for route_id, flights in aircraft_schedule.get(day, {}).items():
            for s in flights:
                route = f"{s.get('start_airport', '?')} → {s.get('end_airport', '?')}"
                if s.get("service_type") == "deadhead":
                    route += " [DEADHEAD - NO PASSENGERS]"
                rows.append([day, s["start_time"], route])


    rows.sort(key=lambda x: (days.index(x[0]), x[1]))
    return tabulate(rows, headers=["Day", "Time", "Route"], tablefmt="fancy_grid")
