"""Demand and capacity estimates used while building a schedule."""

from game.economy.demand import calculate_adjusted_daily_demand
from game.game_state import get_active_airline


LAYOUT_KEYS = ("economy", "business_class", "first_class")


def aircraft_seat_capacity(aircraft, specs):
    layout = aircraft.get("layout", {})
    seats = sum(
        max(0, int(layout.get(cabin, {}).get("seats", 0)))
        for cabin in LAYOUT_KEYS
    )
    return seats or max(0, int(specs.get("capacity", 0)))


def scheduled_seats_by_route(game_state, day="Mon"):
    """Return planned passenger seats for each directional route on one day."""
    airline = get_active_airline(game_state)
    reference = game_state.get("aircraft_reference", {})
    totals = {}
    for aircraft in airline.get("fleet", {}).values():
        specs = reference.get(aircraft.get("model"), {})
        capacity = aircraft_seat_capacity(aircraft, specs)
        for route_id, flights in aircraft.get("schedule", {}).get(day, {}).items():
            passenger_flights = sum(
                1
                for flight in flights
                if flight.get("service_type", "passenger") != "deadhead"
            )
            totals[route_id] = totals.get(route_id, 0) + capacity * passenger_flights
    return totals


def route_demand_metrics(game_state, routes, day="Mon"):
    """Return demand, assigned seats, and unmet demand by direction."""
    difficulty = game_state.get("settings", {}).get("difficulty", "Normal")
    assigned = scheduled_seats_by_route(game_state, day)
    metrics = {}
    for route_id, route in routes.items():
        demand = calculate_adjusted_daily_demand(route, difficulty)
        seats = assigned.get(route_id, 0)
        metrics[route_id] = {
            "demand": demand,
            "assigned_seats": seats,
            "demand_left": max(0, demand - seats),
            "oversupply": max(0, seats - demand),
        }
    return metrics


def format_direction_metrics(route_id, metrics):
    values = metrics.get(route_id, {})
    demand = values.get("demand", 0)
    assigned = values.get("assigned_seats", 0)
    remaining = values.get("demand_left", 0)
    return f"{route_id}: {demand} demand / {assigned} seats / {remaining} left"
