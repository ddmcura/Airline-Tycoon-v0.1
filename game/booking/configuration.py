"""Booking-domain access to the canonical world-state configuration witness."""

from game.world_state.booking_fingerprint import (
    calculate_booking_configuration_fingerprint,
    new_booking_configuration,
)

__all__ = (
    "calculate_booking_configuration_fingerprint",
    "new_booking_configuration",
)
