"""Shared coordinate distance, preserving the Model 4 metre quantization."""

import math
from decimal import Decimal, Context, localcontext, ROUND_HALF_EVEN, MIN_EMIN, MAX_EMAX


def distance_km(origin, destination):
    lat1 = math.radians(origin["latitude_microdegrees"] / 1_000_000)
    lon1 = math.radians(origin["longitude_microdegrees"] / 1_000_000)
    lat2 = math.radians(destination["latitude_microdegrees"] / 1_000_000)
    lon2 = math.radians(destination["longitude_microdegrees"] / 1_000_000)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    haversine = min(1.0, max(0.0, haversine))
    kilometres = 6_371 * 2 * math.asin(math.sqrt(haversine))
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=MIN_EMIN, Emax=MAX_EMAX)):
        decimal_kilometres = Decimal(str(kilometres))
        return decimal_kilometres.quantize(
            Decimal("0.001"), rounding=ROUND_HALF_EVEN
        )
