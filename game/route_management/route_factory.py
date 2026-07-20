from game.economy.demand import (
    DEMAND_MODEL_VERSION,
    calculate_directional_base_demand,
)
from game.route_management.route_calculators import calculate_base_fare, calculate_distance


def _direction(origin, destination, distance, route_type, pair_id, reverse_id):
    suggested = {
        cabin: calculate_base_fare(distance, cabin)
        for cabin in ("Economy", "Business", "First")
    }
    origin_population = int(origin.get("population", 0) or 0)
    destination_population = int(destination.get("population", 0) or 0)
    return {
        "origin_iata": origin["iata"],
        "origin_name": origin["name"],
        "origin_population": origin_population,
        "destination_iata": destination["iata"],
        "destination_name": destination["name"],
        "destination_population": destination_population,
        "distance_km": distance,
        "suggested_pricing": suggested,
        "pricing": suggested.copy(),
        "base_daily_demand": calculate_directional_base_demand(
            origin_population, destination_population, distance
        ),
        "demand_model_version": DEMAND_MODEL_VERSION,
        "route_type": route_type,
        "route_pair_id": pair_id,
        "reverse_route_id": reverse_id,
        "status": "Planned",
        "frequency": None,
        "assigned_aircraft": [],
    }


def build_directional_route_pair(origin, destination):
    forward_id = f"{origin['iata']}-{destination['iata']}"
    reverse_id = f"{destination['iata']}-{origin['iata']}"
    pair_id = "-".join(sorted((origin["iata"], destination["iata"])))
    distance = calculate_distance(origin["coordinates"], destination["coordinates"])
    route_type = "Domestic" if origin["country"] == destination["country"] else "International"
    return {
        forward_id: _direction(origin, destination, distance, route_type, pair_id, reverse_id),
        reverse_id: _direction(destination, origin, distance, route_type, pair_id, forward_id),
    }
