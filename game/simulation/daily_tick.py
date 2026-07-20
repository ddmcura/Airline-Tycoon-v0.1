"""Simulate scheduled flights and their financial results for one game day."""

from random import Random

from game.game_state import get_active_airline
from game.economy.demand import (
    backfill_route_demand,
    calculate_adjusted_daily_demand,
)


DEFAULT_FUEL_PRICE_PER_LITER = 0.85
DEFAULT_NON_FUEL_COST_PER_SEAT_KM = 0.035
CLASS_LAYOUT_KEYS = {
    "Economy": "economy",
    "Business": "business_class",
    "First": "first_class",
}


def _increment(target, key, amount):
    target[key] = target.get(key, 0) + amount


def _seat_counts(aircraft, specs):
    layout = aircraft.get("layout", {})
    counts = {
        cabin: max(0, int(layout.get(layout_key, {}).get("seats", 0)))
        for cabin, layout_key in CLASS_LAYOUT_KEYS.items()
    }
    if sum(counts.values()) == 0:
        counts["Economy"] = max(0, int(specs.get("capacity", 0)))
    return counts




def _route_financials(game_state, route, aircraft, specs, passenger_limit):
    distance_km = max(0.0, float(route.get("distance_km", 0)))
    cruise_speed = max(1.0, float(specs.get("cruise_speed_kph", 800)))
    flight_hours = distance_km / cruise_speed
    seats = _seat_counts(aircraft, specs)
    available_seats = sum(seats.values())
    passenger_target = min(available_seats, max(0, int(passenger_limit)))
    load_factor = passenger_target / available_seats if available_seats else 0
    pricing = route.get("pricing", {})

    passengers = 0
    revenue = 0.0
    for cabin, seat_count in seats.items():
        remaining = max(0, passenger_target - passengers)
        cabin_passengers = min(
            seat_count,
            remaining,
            round(seat_count * load_factor),
        )
        passengers += cabin_passengers
        revenue += cabin_passengers * float(pricing.get(cabin, 0))

    economy = game_state.get("settings", {}).get("economy", {})
    fuel_price = float(
        economy.get("fuel_price_per_liter", DEFAULT_FUEL_PRICE_PER_LITER)
    )
    non_fuel_rate = float(
        economy.get(
            "non_fuel_cost_per_seat_km",
            DEFAULT_NON_FUEL_COST_PER_SEAT_KM,
        )
    )
    fuel_burn = max(0.0, float(specs.get("fuel_burn_lph", 0)))
    fuel_cost = fuel_burn * flight_hours * fuel_price
    non_fuel_cost = sum(seats.values()) * distance_km * non_fuel_rate
    operating_cost = fuel_cost + non_fuel_cost

    return {
        "passengers": passengers,
        "available_seats": available_seats,
        "load_factor": load_factor,
        "flight_hours": flight_hours,
        "revenue": revenue,
        "fuel_expense": fuel_cost,
        "non_fuel_expense": non_fuel_cost,
        "operating_cost": operating_cost,
        "profit": revenue - operating_cost,
    }


def _record_flight(route, aircraft, registration, result, date_text):
    route["status"] = "Active"
    assigned = route.setdefault("assigned_aircraft", [])
    if registration not in assigned:
        assigned.append(registration)

    route_stats = route.setdefault("statistics", {})
    _increment(route_stats, "flights", 1)
    _increment(route_stats, "passengers", result["passengers"])
    _increment(route_stats, "available_seats", result["available_seats"])
    _increment(route_stats, "revenue", result["revenue"])
    _increment(route_stats, "fuel_expenses", result["fuel_expense"])
    _increment(route_stats, "non_fuel_expenses", result["non_fuel_expense"])
    _increment(route_stats, "expenses", result["operating_cost"])
    _increment(route_stats, "profit", result["profit"])
    route_stats["last_operated_date"] = date_text

    aircraft_stats = aircraft.setdefault("statistics", {})
    _increment(aircraft_stats, "cycles", 1)
    _increment(aircraft_stats, "flight_hours", result["flight_hours"])
    _increment(aircraft_stats, "passengers", result["passengers"])
    _increment(aircraft_stats, "revenue", result["revenue"])
    _increment(aircraft_stats, "expenses", result["operating_cost"])


def _record_deadhead(aircraft, result):
    aircraft_stats = aircraft.setdefault("statistics", {})
    _increment(aircraft_stats, "cycles", 1)
    _increment(aircraft_stats, "flight_hours", result["flight_hours"])
    _increment(aircraft_stats, "deadhead_flights", 1)
    _increment(aircraft_stats, "deadhead_expenses", result["operating_cost"])
    _increment(aircraft_stats, "expenses", result["operating_cost"])


def simulate_airline_day(game_state, current_dt, rng=None):
    """Run all flights scheduled for current_dt and return a daily summary."""
    rng = rng or Random()
    airline = get_active_airline(game_state)
    routes = airline.get("routes", {})
    fleet = airline.get("fleet", {})
    aircraft_reference = game_state.get("aircraft_reference", {})
    day = current_dt.strftime("%a")
    date_text = current_dt.strftime("%Y-%m-%d")

    summary = {
        "date": date_text,
        "day": day,
        "flights": 0,
        "passengers": 0,
        "available_seats": 0,
        "fuel_expenses": 0.0,
        "non_fuel_expenses": 0.0,
        "revenue": 0.0,
        "expenses": 0.0,
        "profit": 0.0,
        "skipped_flights": 0,
        "deadhead_flights": 0,
    }

    difficulty = game_state.get("settings", {}).get("difficulty", "Normal")
    remaining_demand = {}
    for route_id, route in routes.items():
        backfill_route_demand(route, route_id=route_id)
        adjusted = calculate_adjusted_daily_demand(route, difficulty)
        variation = 1.0 + rng.uniform(-0.05, 0.05)
        remaining_demand[route_id] = max(0, round(adjusted * variation))

    for registration, aircraft in fleet.items():
        if aircraft.get("status", "active").lower() != "active":
            continue
        if aircraft.get("delivery_status", "delivered").lower() != "delivered":
            continue

        specs = aircraft_reference.get(aircraft.get("model"), {})
        day_schedule = aircraft.get("schedule", {}).get(day, {})
        for route_id, flight_blocks in day_schedule.items():
            route = routes.get(route_id)
            for flight_block in flight_blocks:
                is_deadhead = flight_block.get("service_type") == "deadhead"
                operation_route = route
                if operation_route is None and is_deadhead:
                    operation_route = {}
                    backfill_route_demand(operation_route, route_id=route_id)
                if operation_route is None:
                    summary["skipped_flights"] += 1
                    continue

                passenger_limit = (
                    0 if is_deadhead else remaining_demand.get(route_id, 0)
                )
                result = _route_financials(
                    game_state,
                    operation_route,
                    aircraft,
                    specs,
                    passenger_limit,
                )
                if is_deadhead:
                    _record_deadhead(aircraft, result)
                    summary["deadhead_flights"] += 1
                else:
                    remaining_demand[route_id] = max(
                        0,
                        remaining_demand.get(route_id, 0) - result["passengers"],
                    )
                    _record_flight(
                        operation_route, aircraft, registration, result, date_text
                    )
                summary["flights"] += 1
                summary["passengers"] += result["passengers"]
                if not is_deadhead:
                    summary["available_seats"] += result["available_seats"]
                summary["revenue"] += result["revenue"]
                summary["fuel_expenses"] += result["fuel_expense"]
                summary["non_fuel_expenses"] += result["non_fuel_expense"]
                summary["expenses"] += result["operating_cost"]
                summary["profit"] += result["profit"]

    for key in ("revenue", "fuel_expenses", "non_fuel_expenses", "expenses", "profit"):
        summary[key] = round(summary[key], 2)

    finances = airline.setdefault("finances", {})
    _increment(finances, "cash_on_hand", summary["profit"])
    _increment(finances, "total_revenue", summary["revenue"])
    _increment(finances, "total_expenses", summary["expenses"])
    _increment(finances, "total_profit", summary["profit"])
    summary["closing_cash"] = round(finances.get("cash_on_hand", 0), 2)
    finances.setdefault("daily_history", []).append(summary.copy())

    return summary
