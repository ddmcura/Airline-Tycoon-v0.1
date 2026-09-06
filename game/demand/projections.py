"""Detached, bounded player-facing projections over Model 4 market authority."""

from __future__ import annotations

from copy import deepcopy

from game.scheduling import configured_publication_horizon_utc
from game.world_state.timestamps import parse_canonical_utc

from .activation import is_usable_direct_passenger_flight
from .model import _distance_km
from .model4 import _pair_projection_from_indexes, rebuild_model4_indexes


MAX_MARKET_OPPORTUNITY_RESULTS = 2_000


def _resolved_origin_id(world, origin_airport_id):
    if origin_airport_id is None:
        return None
    if not isinstance(origin_airport_id, str) or not origin_airport_id:
        raise ValueError("origin_airport_id must be an airport ID or reference code")
    if origin_airport_id in world["airports"]:
        return origin_airport_id
    matches = [
        airport_id
        for airport_id, airport in world["airports"].items()
        if airport.get("reference_code") == origin_airport_id.upper()
    ]
    if len(matches) != 1:
        raise ValueError("origin airport is unavailable or ambiguous")
    return matches[0]


def _current_revision_witness(world):
    state = world["demand_state"]
    revision = state["demand_model_revision"]
    contexts = [
        (context_id, context)
        for context_id, context in state["model4_revision_contexts"].items()
        if context["demand_model_revision"] == revision
    ]
    if len(contexts) != 1:
        raise ValueError("current Model 4 revision context is missing or ambiguous")
    context_id, context = contexts[0]
    return {
        "demand_model_version": context["demand_model_version"],
        "demand_model_revision": revision,
        "demand_input_fingerprint": state["input_fingerprint"],
        "revision_context_id": context_id,
        "revision_context_fingerprint": context["context_fingerprint"],
    }


def _player_service_by_market(envelope, airline_id):
    from game.booking.indexes import rebuild_booking_indexes

    world = envelope["world_state"]
    start = parse_canonical_utc(envelope["simulation"]["time_utc"])
    end = parse_canonical_utc(configured_publication_horizon_utc(envelope))
    booking_indexes = rebuild_booking_indexes(envelope)
    connections = world["connections"]
    service = {}
    for flight_id in sorted(world["dated_flights"]):
        flight = world["dated_flights"][flight_id]
        if flight.get("airline_id") != airline_id or not is_usable_direct_passenger_flight(
            envelope,
            flight_id,
            flight,
            start,
            end,
        ):
            continue
        market_id = connections[flight["connection_id"]]["market_id"]
        item = service.setdefault(
            market_id,
            {"capacity": 0, "fares": set(), "confirmed": 0, "flight_ids": []},
        )
        item["capacity"] += flight["capacity"]
        item["fares"].add(flight["fare_offer"]["amount_minor"])
        item["confirmed"] += booking_indexes.booked_passenger_count_by_dated_flight_id.get(
            flight_id, 0
        )
        item["flight_ids"].append(flight_id)
    return service


def project_market_opportunities(envelope, *, origin_airport_id=None, limit=100):
    """Project current directional opportunity rows without creating demand.

    The one Model 4 index rebuild performs world validation once.  Pair rows then
    reuse the validated Model 4 allocation authority directly; no cohort,
    connection, schedule, flight, random input, revision, or persistent record is
    created.
    """
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 0 <= limit <= MAX_MARKET_OPPORTUNITY_RESULTS
    ):
        raise ValueError(
            f"limit must be an integer from 0 through {MAX_MARKET_OPPORTUNITY_RESULTS}"
        )
    if limit == 0:
        return []
    indexes = rebuild_model4_indexes(envelope)
    world = envelope["world_state"]
    origin_filter = _resolved_origin_id(world, origin_airport_id)
    airline_id = world["player"]["primary_airline_id"]
    service_by_market = _player_service_by_market(envelope, airline_id)
    witness = _current_revision_witness(world)
    rows = []
    for market_id in sorted(world["directional_markets"]):
        market = world["directional_markets"][market_id]
        origin_id = market["origin_airport_id"]
        destination_id = market["destination_airport_id"]
        if origin_filter is not None and origin_id != origin_filter:
            continue
        pair = _pair_projection_from_indexes(
            envelope, indexes, origin_id, destination_id
        )
        origin = world["airports"][origin_id]
        destination = world["airports"][destination_id]
        player_service = service_by_market.get(market_id)
        fares = player_service["fares"] if player_service is not None else set()
        rows.append({
            "market_id": market_id,
            "origin_airport_id": origin_id,
            "origin_airport_reference_code": origin["reference_code"],
            "origin_airport_name": origin["display_name"],
            "origin_airport_city": origin.get("city"),
            "destination_airport_id": destination_id,
            "destination_airport_reference_code": destination["reference_code"],
            "destination_airport_name": destination["display_name"],
            "destination_airport_city": destination.get("city"),
            **witness,
            "base_daily_directional_bookers": pair["base_daily_bookers"],
            "diagnostic_demand_share": pair["diagnostic_pair_share"],
            "distance_km": _distance_km(origin, destination),
            "market_available": pair["available"],
            "qualifying_player_service_exists": player_service is not None,
            "player_published_capacity": (
                player_service["capacity"] if player_service is not None else 0
            ),
            "player_fare_minor": next(iter(fares)) if len(fares) == 1 else None,
            "current_confirmed_bookings": (
                player_service["confirmed"] if player_service is not None else 0
            ),
            "qualifying_player_dated_flight_ids": tuple(
                player_service["flight_ids"] if player_service is not None else ()
            ),
        })
        if len(rows) == limit:
            break
    return deepcopy(rows)


__all__ = ("MAX_MARKET_OPPORTUNITY_RESULTS", "project_market_opportunities")
