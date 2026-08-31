"""Canonical fingerprinting for immutable Stage 1 flight fulfilment policy."""

from copy import deepcopy
import hashlib
import json

from .schema import DEFAULT_FLIGHT_FULFILMENT_CONFIGURATION


def calculate_flight_fulfilment_configuration_fingerprint(value):
    """Hash only fulfilment-owned semantic configuration fields."""
    configuration = (
        value.get("simulation", {}).get("configuration", {}).get(
            "flight_fulfilment"
        )
        if type(value) is dict and "simulation" in value
        else value
    )
    if type(configuration) is not dict:
        raise ValueError("flight fulfilment configuration must be a dictionary")
    semantic = deepcopy(configuration)
    semantic.pop("configuration_fingerprint", None)
    encoded = json.dumps(
        semantic,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def new_flight_fulfilment_configuration():
    configuration = deepcopy(DEFAULT_FLIGHT_FULFILMENT_CONFIGURATION)
    configuration["configuration_fingerprint"] = (
        calculate_flight_fulfilment_configuration_fingerprint(configuration)
    )
    return configuration


__all__ = (
    "calculate_flight_fulfilment_configuration_fingerprint",
    "new_flight_fulfilment_configuration",
)
