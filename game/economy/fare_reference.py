"""Modern PH Economy fare guidance, separate from Booking choice authority."""

from decimal import Context, Decimal, MAX_EMAX, MIN_EMIN, ROUND_HALF_EVEN, localcontext

from game.utils.geo_distance import distance_km


ECONOMY_REFERENCE_USD_PER_KM = Decimal("0.12")


def suggested_economy_fare_minor(world, origin_airport_id, destination_airport_id):
    """Return a whole-USD neutral reference for an existing directional market.

    This is informational. Booking scores published fares against competing
    offers and does not consume this reference value.
    """
    airports = world["airports"]
    if (origin_airport_id not in airports or destination_airport_id not in airports
            or origin_airport_id == destination_airport_id):
        raise ValueError("select two distinct available airports")
    if not any(
        market["origin_airport_id"] == origin_airport_id
        and market["destination_airport_id"] == destination_airport_id
        for market in world["directional_markets"].values()
    ):
        raise ValueError("directional market is unavailable")
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN,
                              Emin=MIN_EMIN, Emax=MAX_EMAX)):
        kilometres = distance_km(airports[origin_airport_id],
                                 airports[destination_airport_id])
        whole_usd = (kilometres * ECONOMY_REFERENCE_USD_PER_KM).quantize(
            Decimal("1"), rounding=ROUND_HALF_EVEN)
    return int(whole_usd) * 100
