"""Detached, bounded Milestone 7 views over aircraft and finance authority."""

from copy import deepcopy

from .fulfilment import (
    _PROJECTION_VALIDATION_TOKEN,
    build_confirmed_carriage_manifest,
    calculate_operating_cost,
)
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


def _airport_code(world, airport_id):
    airport = world["airports"].get(airport_id, {})
    return airport.get("reference_code")


def _next_flight_event(world, dated_flight_id):
    events = sorted(
        (
            event for event in world["pending_events"].values()
            if event.get("owner_type") == "dated_flight"
            and event.get("owner_id") == dated_flight_id
        ),
        key=lambda event: (
            event["due_at_utc"], event["order_key"][0],
            event["order_key"][1], event["event_id"],
        ),
    )
    if not events:
        return None
    event = events[0]
    return {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "due_at_utc": event["due_at_utc"],
    }


def _project_flight(envelope, world, dated_flight_id):
    flight = world["dated_flights"].get(dated_flight_id)
    if type(flight) is not dict:
        return None
    result = world.get("flight_results", {}).get(dated_flight_id)
    manifest = build_confirmed_carriage_manifest(
        envelope, dated_flight_id,
        _validation_token=_PROJECTION_VALIDATION_TOKEN,
    )
    booked = manifest.carried_passenger_count if manifest.succeeded else 0
    booked_paid = manifest.paid_passenger_count if manifest.succeeded else 0
    booked_zero = manifest.zero_fare_passenger_count if manifest.succeeded else 0
    ticket_sales = manifest.recognized_revenue_minor if manifest.succeeded else 0
    if type(result) is dict:
        carried = result["carried_passenger_count"]
        paid = result["paid_passenger_count"]
        zero = result["zero_fare_passenger_count"]
        revenue = result["recognized_revenue_minor"]
        cost = result["operating_cost_minor"]
        completion = result["completed_at_utc"]
        transaction_id = result["settlement_transaction_id"]
        identity = {
            "contract": result["contract"],
            "result_version": result["result_version"],
            "dated_flight_id": result["dated_flight_id"],
        }
    else:
        carried = paid = zero = revenue = 0
        cost = calculate_operating_cost(envelope, flight)["operating_cost_minor"]
        completion = transaction_id = identity = None
    capacity = flight["capacity"]
    booked_bps = 0 if capacity == 0 else (booked * 10_000) // capacity
    carried_bps = 0 if capacity == 0 else (carried * 10_000) // capacity
    aircraft_id = flight["planned_aircraft_id"]
    active = world["active_aircraft_operations"].get(dated_flight_id)
    if type(active) is dict:
        aircraft_id = active["actual_aircraft_id"]
    aircraft = world["aircraft"][aircraft_id]
    airline = world["airlines"][flight["airline_id"]]
    return deepcopy({
        "dated_flight_id": dated_flight_id,
        "airline_id": flight["airline_id"],
        "airline_display_name": airline["display_name"],
        "origin_airport_id": flight["origin_airport_id"],
        "origin_airport_reference_code": _airport_code(world, flight["origin_airport_id"]),
        "destination_airport_id": flight["destination_airport_id"],
        "destination_airport_reference_code": _airport_code(world, flight["destination_airport_id"]),
        "scheduled_departure_utc": flight["scheduled_off_block_utc"],
        "scheduled_arrival_utc": flight["scheduled_in_block_utc"],
        "aircraft_id": aircraft_id,
        "aircraft_registration": aircraft["display_registration"],
        "aircraft_status": aircraft["status"],
        "aircraft_current_airport_id": aircraft["current_airport_id"],
        "aircraft_current_airport_reference_code": _airport_code(
            world, aircraft["current_airport_id"]
        ) if aircraft["current_airport_id"] else None,
        "status": flight["status"],
        "fare_minor": flight["fare_offer"]["amount_minor"],
        "currency": flight["fare_offer"]["currency"],
        "published_capacity": capacity,
        "booked_passenger_count": booked,
        "remaining_capacity": capacity - booked,
        "booked_load_factor_numerator": booked,
        "booked_load_factor_denominator": capacity,
        "booked_load_factor_basis_points": booked_bps,
        "booked_paid_passenger_count": booked_paid,
        "booked_zero_fare_passenger_count": booked_zero,
        "carried_passenger_count": carried,
        "paid_passenger_count": paid,
        "zero_fare_passenger_count": zero,
        "carried_load_factor_numerator": carried,
        "carried_load_factor_denominator": capacity,
        "carried_load_factor_basis_points": carried_bps,
        "load_factor_numerator": carried,
        "load_factor_denominator": capacity,
        "load_factor_basis_points": carried_bps,
        "ticket_sales_minor": ticket_sales,
        "recognized_revenue_minor": revenue,
        "operating_cost_minor": cost,
        "operating_profit_minor": revenue - cost,
        "completion_timestamp_utc": completion,
        "completion_transaction_id": transaction_id,
        "result_identity": identity,
        "next_lifecycle_event": _next_flight_event(world, dated_flight_id),
    })


def project_flight_fulfilment(envelope, dated_flight_id):
    world = _validated_world(envelope)
    if world is None or type(dated_flight_id) is not str:
        return None
    return _project_flight(envelope, world, dated_flight_id)


def project_airline_flights(envelope, airline_id, *, limit=20, statuses=None):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100:
        raise ValueError("limit must be an integer from 0 through 100")
    if statuses is not None:
        if not isinstance(statuses, (set, frozenset, tuple, list)) or any(
            not isinstance(status, str) for status in statuses
        ):
            raise ValueError("statuses must be a collection of status strings")
        statuses = frozenset(statuses)
    world = _validated_world(envelope)
    if world is None or type(airline_id) is not str or airline_id not in world["airlines"]:
        return None
    flights = sorted(
        (
            flight for flight in world["dated_flights"].values()
            if flight["airline_id"] == airline_id
            and (statuses is None or flight["status"] in statuses)
        ),
        key=lambda flight: (flight["scheduled_off_block_utc"], flight["dated_flight_id"]),
    )
    return deepcopy([
        _project_flight(envelope, world, flight["dated_flight_id"])
        for flight in flights[:limit]
    ])


def project_airline_fleet(envelope, airline_id, *, limit=20):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100:
        raise ValueError("limit must be an integer from 0 through 100")
    world = _validated_world(envelope)
    if world is None or airline_id not in world["airlines"]:
        return None
    rows = []
    for aircraft_id, aircraft in sorted(world["aircraft"].items()):
        if aircraft["airline_id"] != airline_id:
            continue
        rows.append({
            "aircraft_id": aircraft_id,
            "display_registration": aircraft["display_registration"],
            "model_reference": aircraft["model_reference"],
            "status": aircraft["status"],
            "home_airport_id": aircraft["home_airport_id"],
            "home_airport_reference_code": _airport_code(world, aircraft["home_airport_id"]),
            "current_airport_id": aircraft["current_airport_id"],
            "current_airport_reference_code": _airport_code(
                world, aircraft["current_airport_id"]
            ) if aircraft["current_airport_id"] else None,
        })
    return deepcopy(rows[:limit])


def project_airline_overview(envelope, airline_id):
    world = _validated_world(envelope)
    if world is None or airline_id not in world["airlines"]:
        return None
    airline = world["airlines"][airline_id]
    player = world["player"]
    return deepcopy({
        "airline_id": airline_id,
        "airline_display_name": airline["display_name"],
        "ceo_display_name": player["ceo_display_name"],
        "base_currency": airline["base_currency"],
        "base_airports": [
            {"airport_id": airport_id, "reference_code": _airport_code(world, airport_id)}
            for airport_id in sorted(airline["base_airport_ids"])
        ],
        "simulation_time_utc": envelope["simulation"]["time_utc"],
        "clock_state": envelope["simulation"]["clock_state"],
    })


def project_recent_flight_results(envelope, airline_id, *, limit=10):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    limit = min(limit, 10)
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
    transactions = sorted(
        (transaction for transaction in world["transactions"].values()
         if transaction["airline_id"] == airline_id),
        key=lambda transaction: (
            transaction["occurred_at_utc"], transaction["transaction_id"]
        ),
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
            _project_flight(envelope, world, item["dated_flight_id"])
            for item in results[:limit]
        ],
        "recent_transactions": [
            {
                "transaction_id": item["transaction_id"],
                "occurred_at_utc": item["occurred_at_utc"],
                "description": item["description"],
                "source_type": item["source_type"],
                "source_id": item["source_id"],
                "currency": item["currency"],
                "entries": deepcopy(item["entries"]),
            }
            for item in transactions[:10]
        ],
        "cumulative_revenue_minor": revenue,
        "cumulative_cost_minor": cost,
        "cumulative_profit_minor": revenue - cost,
    })


__all__ = (
    "project_airline_fleet", "project_airline_flights", "project_airline_overview",
    "project_flight_fulfilment", "project_recent_flight_results",
)
