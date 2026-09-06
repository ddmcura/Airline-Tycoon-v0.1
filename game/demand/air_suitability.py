"""Runtime-only curve evaluation using Model 4's deterministic Decimal context."""

from decimal import Decimal

from .model import _fixed_decimal_context


def interpolate_air_suitability(policy, origin, destination, distance_m):
    """Return fractional basis points without integer quantization."""
    field = (
        "same_ground_network_points"
        if origin["ground_network_id"] == destination["ground_network_id"]
        else "separated_ground_network_points"
    )
    points = policy[field]
    with _fixed_decimal_context(50):
        distance = Decimal(distance_m)
        if not distance.is_finite() or distance < 0:
            raise ValueError("air suitability distance must be finite and non-negative")
        for left, right in zip(points, points[1:]):
            if distance <= right["distance_m"]:
                return Decimal(left["suitability_bps"]) + (
                    (distance - Decimal(left["distance_m"]))
                    * Decimal(right["suitability_bps"] - left["suitability_bps"])
                    / Decimal(right["distance_m"] - left["distance_m"])
                )
        return Decimal(points[-1]["suitability_bps"])
