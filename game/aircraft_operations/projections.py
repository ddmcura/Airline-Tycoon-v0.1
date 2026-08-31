"""Detached Milestone 7 read projections over Milestone 6 authority."""

from copy import deepcopy

from .fulfilment import build_confirmed_carriage_manifest, calculate_operating_cost
from game.world_state.validation import validate_world


def _validated_world(envelope):
    if type(envelope) is not dict:
        return None
    try:
        validation = validate_world(envelope)
    except Exception:
        return None
    if not validation.is_valid:
        return None
    return envelope["world_state"]


def _account_balances(world, airline_id):
    airline = world["airlines"][airline_id]
    return {
        world["financial_accounts"][account_id]["code"]:
        world["financial_accounts"][account_id]["balance_minor"]
        for account_id in airline["financial_account_ids"]
    }


def project_flight_fulfilment(envelope, dated_flight_id):
    """Project one flight without retaining or exposing authoritative aliases."""
    world = _validated_world(envelope)
    if world is None or type(dated_flight_id) is not str:
        return None
    flight = world["dated_flights"].get(dated_flight_id)
    if type(flight) is not dict:
        return None
    result = world.get("flight_results", {}).get(dated_flight_id)
    if type(result) is dict:
        carried = result["carried_passenger_count"]
        revenue = result["recognized_revenue_minor"]
        cost = result["operating_cost_minor"]
        completion = result["completed_at_utc"]
        ticket_sales = sum(
            world["bookings"][booking_id]["total_fare_minor"]
            for booking_id in result["source_booking_ids"]
        )
    else:
        manifest = build_confirmed_carriage_manifest(envelope, dated_flight_id)
        carried = 0
        revenue = 0
        cost = calculate_operating_cost(envelope, flight)["operating_cost_minor"]
        completion = None
        ticket_sales = (
            manifest.recognized_revenue_minor if manifest.succeeded else 0
        )
    manifest = build_confirmed_carriage_manifest(envelope, dated_flight_id)
    booked = manifest.carried_passenger_count if manifest.succeeded else 0
    capacity = flight["capacity"]
    load_bps = 0 if capacity == 0 else (carried * 10_000) // capacity
    return deepcopy({
        "dated_flight_id": dated_flight_id,
        "status": flight["status"],
        "booked_passenger_count": booked,
        "carried_passenger_count": carried,
        "published_capacity": capacity,
        "load_factor_numerator": carried,
        "load_factor_denominator": capacity,
        "load_factor_basis_points": load_bps,
        "ticket_sales_minor": ticket_sales,
        "recognized_revenue_minor": revenue,
        "operating_cost_minor": cost,
        "operating_profit_minor": revenue - cost,
        "currency": world["airlines"][flight["airline_id"]]["base_currency"],
        "completion_timestamp_utc": completion,
    })


def project_recent_flight_results(envelope, airline_id, *, limit=10):
    """Project airline balances, cumulative fulfilment, and recent results."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    world = _validated_world(envelope)
    if world is None or type(airline_id) is not str:
        return None
    airline = world["airlines"].get(airline_id)
    if type(airline) is not dict:
        return None
    results = sorted(
        (result for result in world.get("flight_results", {}).values()
         if result.get("airline_id") == airline_id),
        key=lambda result: (result["completed_at_utc"], result["dated_flight_id"]),
        reverse=True,
    )
    balances = _account_balances(world, airline_id)
    revenue = sum(item["recognized_revenue_minor"] for item in results)
    cost = sum(item["operating_cost_minor"] for item in results)
    return deepcopy({
        "airline_id": airline_id,
        "currency": airline["base_currency"],
        "cash_minor": balances["cash"],
        "unflown_ticket_liability_minor": balances["unflown_tickets"],
        "passenger_revenue_minor": balances["passenger_revenue"],
        "operating_expenses_minor": balances["operating_expenses"],
        "recent_results": [
            project_flight_fulfilment(envelope, item["dated_flight_id"])
            for item in results[:limit]
        ],
        "cumulative_revenue_minor": revenue,
        "cumulative_cost_minor": cost,
        "cumulative_profit_minor": revenue - cost,
    })


__all__ = ("project_flight_fulfilment", "project_recent_flight_results")
