"""Basic directional route-demand and price-sensitivity formulas."""

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
ORIGIN_POPULATION_WEIGHT = 0.65


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

    if not route.get("base_daily_demand"):
        route["base_daily_demand"] = calculate_directional_base_demand(
            route.get("origin_population", 0),
            route.get("destination_population", 0),
            route.get("distance_km", 0),
        )
    return route["base_daily_demand"]


DESTINATION_POPULATION_WEIGHT = 0.35
POPULATION_NORMALIZER = 25_000


def calculate_directional_base_demand(
    origin_population, destination_population, distance_km
):
    origin_population = max(0, int(origin_population or 0))
    destination_population = max(0, int(destination_population or 0))
    population_score = (
        origin_population * ORIGIN_POPULATION_WEIGHT
        + destination_population * DESTINATION_POPULATION_WEIGHT
    )
    distance_factor = max(1.0, (max(0.0, float(distance_km)) / 500) ** 0.5)
    return max(0, round(population_score / POPULATION_NORMALIZER / distance_factor))


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
    base_demand = route.get("base_daily_demand")
    if base_demand is None:
        base_demand = calculate_directional_base_demand(
            route.get("origin_population", 0),
            route.get("destination_population", 0),
            route.get("distance_km", 0),
        )
        route["base_daily_demand"] = base_demand

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
    return max(0, round(base_demand * difficulty_multiplier * price_multiplier))
