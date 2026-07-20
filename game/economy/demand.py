"""Directional route-demand and price-sensitivity formulas.

The base market is generated from the origin population, then narrowed by the
share of travellers attracted to the destination and adjusted for distance.
Additional route modifiers can be supplied later without changing the daily
simulation contract.
"""

DIFFICULTY_DEMAND_MULTIPLIERS = {
    "easy": 1.50,
    "normal": 1.00,
    "hard": 0.70,
    "extreme": 0.50,
}
PRICE_SENSITIVITY = {
    "easy": (0.00, 0.00),
    "normal": (0.40, 0.60),
    "hard": (0.60, 1.20),
    "extreme": (0.80, 2.00),
}

DEFAULT_DAILY_TRAVEL_RATE = 0.004
DESTINATION_SHARE_BASE = 0.0108
DESTINATION_SHARE_SCALE = 0.015
DESTINATION_POPULATION_SCALE = 2_000_000
MIN_DESTINATION_SHARE = 0.005
MAX_DESTINATION_SHARE = 0.05
DISTANCE_DECAY_KM = 12_000
MIN_DISTANCE_MULTIPLIER = 0.35
DEMAND_MODEL_VERSION = 3


def _clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


def calculate_destination_share(destination_population):
    """Estimate what share of origin travellers choose this destination.

    Larger destinations attract a larger share, but the square-root curve and
    cap prevent megacities from consuming an unrealistic portion of every
    origin market. Routes may override this estimate with
    ``destination_attractiveness`` when richer airport data is available.
    """
    destination_population = max(0, int(destination_population or 0))
    if destination_population == 0:
        return MIN_DESTINATION_SHARE

    population_ratio = destination_population / DESTINATION_POPULATION_SCALE
    estimated_share = DESTINATION_SHARE_BASE + (
        DESTINATION_SHARE_SCALE * population_ratio**0.5
    )
    return _clamp(
        estimated_share,
        MIN_DESTINATION_SHARE,
        MAX_DESTINATION_SHARE,
    )


def calculate_distance_multiplier(distance_km):
    """Reduce demand gradually as distance increases.

    A 960 km route receives a multiplier of 0.92, matching the MNL-DVO design
    example while retaining a floor for viable long-haul markets.
    """
    distance_km = max(0.0, float(distance_km or 0))
    return max(
        MIN_DISTANCE_MULTIPLIER,
        1.0 - (distance_km / DISTANCE_DECAY_KM),
    )


def calculate_directional_base_demand(
    origin_population,
    destination_population,
    distance_km,
    travel_rate=DEFAULT_DAILY_TRAVEL_RATE,
    destination_attractiveness=None,
):
    """Calculate the total directional market before airline modifiers.

    Formula::

        origin population
        x daily travel rate
        x destination share
        x distance multiplier

    The origin therefore drives trip generation, while the destination decides
    how much of that travel market it can attract. This intentionally produces
    different demand for A->B and B->A.
    """
    origin_population = max(0, int(origin_population or 0))
    destination_population = max(0, int(destination_population or 0))
    travel_rate = max(0.0, float(travel_rate or 0))

    if destination_attractiveness is None:
        destination_share = calculate_destination_share(destination_population)
    else:
        destination_share = _clamp(
            float(destination_attractiveness),
            MIN_DESTINATION_SHARE,
            MAX_DESTINATION_SHARE,
        )

    potential_travellers = origin_population * travel_rate
    distance_multiplier = calculate_distance_multiplier(distance_km)
    base_demand = potential_travellers * destination_share * distance_multiplier
    return max(0, round(base_demand))


def backfill_route_demand(route, airport_index=None, route_id=None):
    """Upgrade a pre-demand-model route in place using bundled airport data."""
    if airport_index is None:
        from game.utils.airport_lookup import load_airport_index

        airport_index = load_airport_index()

    if route_id and "-" in route_id:
        origin_iata, destination_iata = route_id.split("-", 1)
        route.setdefault("origin_iata", origin_iata.upper())
        route.setdefault("destination_iata", destination_iata.upper())

    origin_iata = str(route.get("origin_iata", "")).upper()
    destination_iata = str(route.get("destination_iata", "")).upper()
    origin = airport_index.get(origin_iata, {})
    destination = airport_index.get(destination_iata, {})

    if origin:
        route.setdefault("origin_name", origin.get("name", origin_iata))
    if destination:
        route.setdefault(
            "destination_name", destination.get("name", destination_iata)
        )
    if not route.get("origin_population"):
        route["origin_population"] = int(origin.get("population", 0) or 0)
    if not route.get("destination_population"):
        route["destination_population"] = int(
            destination.get("population", 0) or 0
        )

    if not route.get("distance_km") and origin and destination:
        from game.route_management.route_calculators import calculate_distance

        route["distance_km"] = calculate_distance(
            origin["coordinates"], destination["coordinates"]
        )

    if origin and destination:
        route.setdefault(
            "route_type",
            "Domestic"
            if origin.get("country") == destination.get("country")
            else "International",
        )
    if origin_iata and destination_iata:
        route.setdefault("route_pair_id", "-".join(sorted((origin_iata, destination_iata))))
        route.setdefault("reverse_route_id", f"{destination_iata}-{origin_iata}")

    if not route.get("suggested_pricing"):
        if route.get("pricing"):
            route["suggested_pricing"] = dict(route["pricing"])
        elif route.get("distance_km"):
            from game.route_management.route_calculators import calculate_base_fare

            route["suggested_pricing"] = {
                cabin: calculate_base_fare(route["distance_km"], cabin)
                for cabin in ("Economy", "Business", "First")
            }
    if not route.get("pricing"):
        route["pricing"] = dict(route.get("suggested_pricing", {}))

    populations_available = (
        route.get("origin_population") is not None
        and route.get("destination_population") is not None
        and (
            route.get("origin_population", 0) > 0
            or route.get("destination_population", 0) > 0
        )
    )
    model_outdated = route.get("demand_model_version") != DEMAND_MODEL_VERSION
    if not route.get("base_daily_demand") or (model_outdated and populations_available):
        route["base_daily_demand"] = calculate_directional_base_demand(
            route.get("origin_population", 0),
            route.get("destination_population", 0),
            route.get("distance_km", 0),
            travel_rate=route.get("daily_travel_rate", DEFAULT_DAILY_TRAVEL_RATE),
            destination_attractiveness=route.get("destination_attractiveness"),
        )
        route["demand_model_version"] = DEMAND_MODEL_VERSION
    return route["base_daily_demand"]


def price_demand_multiplier(difficulty, actual_fare, suggested_fare):
    difficulty = str(difficulty or "normal").lower()
    if difficulty == "easy" or suggested_fare <= 0:
        return 1.0

    cheaper_slope, expensive_slope = PRICE_SENSITIVITY.get(
        difficulty, PRICE_SENSITIVITY["normal"]
    )
    price_ratio = max(0.01, float(actual_fare) / float(suggested_fare))
    if price_ratio <= 1.0:
        multiplier = 1.0 + (1.0 - price_ratio) * cheaper_slope
    else:
        multiplier = 1.0 - (price_ratio - 1.0) * expensive_slope
    return min(1.50, max(0.25, multiplier))


def calculate_adjusted_daily_demand(route, difficulty):
    """Apply game and airline modifiers to the total directional market."""
    base_demand = route.get("base_daily_demand")
    populations_available = (
        route.get("origin_population") is not None
        and route.get("destination_population") is not None
        and (
            route.get("origin_population", 0) > 0
            or route.get("destination_population", 0) > 0
        )
    )
    if (
        base_demand is None
        or (
            populations_available
            and route.get("demand_model_version") != DEMAND_MODEL_VERSION
        )
    ):
        base_demand = calculate_directional_base_demand(
            route.get("origin_population", 0),
            route.get("destination_population", 0),
            route.get("distance_km", 0),
            travel_rate=route.get("daily_travel_rate", DEFAULT_DAILY_TRAVEL_RATE),
            destination_attractiveness=route.get("destination_attractiveness"),
        )
        route["base_daily_demand"] = base_demand
        route["demand_model_version"] = DEMAND_MODEL_VERSION

    pricing = route.get("pricing", {})
    suggested = route.get("suggested_pricing", pricing)
    price_multiplier = price_demand_multiplier(
        difficulty,
        pricing.get("Economy", 0),
        suggested.get("Economy", 0),
    )
    difficulty_multiplier = DIFFICULTY_DEMAND_MULTIPLIERS.get(
        str(difficulty or "normal").lower(), 1.0
    )

    seasonality_multiplier = max(
        0.0, float(route.get("seasonality_multiplier", 1.0) or 0)
    )
    reputation_multiplier = max(
        0.0, float(route.get("reputation_multiplier", 1.0) or 0)
    )
    competition_multiplier = max(
        0.0, float(route.get("competition_multiplier", 1.0) or 0)
    )

    adjusted_demand = (
        base_demand
        * difficulty_multiplier
        * price_multiplier
        * seasonality_multiplier
        * reputation_multiplier
        * competition_multiplier
    )
    return max(0, round(adjusted_demand))
