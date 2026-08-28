"""Canonical Stage 1 Booking configuration construction and fingerprinting."""

from copy import deepcopy
import hashlib
import json

from .schema import (
    BOOKING_CONFIGURATION_FINGERPRINT_CONTRACT,
    DEFAULT_BOOKING_CONFIGURATION,
)


def _configuration_from(value):
    if type(value) is not dict:
        raise ValueError("Booking configuration input must be a dictionary")
    if "simulation" in value:
        try:
            return value["simulation"]["configuration"]["booking"]
        except (KeyError, TypeError) as exc:
            raise ValueError("world has no Booking configuration") from exc
    return value


def calculate_booking_configuration_fingerprint(value):
    """Return the canonical witness over Booking configuration only."""
    configuration = _configuration_from(value)
    if type(configuration) is not dict:
        raise ValueError("Booking configuration must be a dictionary")
    try:
        material = {
            "fingerprint_contract": BOOKING_CONFIGURATION_FINGERPRINT_CONTRACT,
            "configuration": {
                key: configuration[key]
                for key in sorted(configuration)
                if key != "configuration_fingerprint"
            },
        }
        encoded = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError(
            "Booking configuration inputs must be finite canonical JSON values"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def new_booking_configuration():
    """Return a detached approved V1 configuration with its integrity witness."""
    configuration = deepcopy(DEFAULT_BOOKING_CONFIGURATION)
    configuration["configuration_fingerprint"] = (
        calculate_booking_configuration_fingerprint(configuration)
    )
    return configuration
