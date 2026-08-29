"""Booking-domain access to the canonical world-state configuration witness."""

from game.world_state.booking_fingerprint import (
    BookingConfigurationTransitionIssue,
    BookingConfigurationTransitionResult,
    calculate_booking_configuration_fingerprint,
    new_booking_configuration,
    transition_booking_configuration_to_production_choice,
)

__all__ = (
    "BookingConfigurationTransitionIssue",
    "BookingConfigurationTransitionResult",
    "calculate_booking_configuration_fingerprint",
    "new_booking_configuration",
    "transition_booking_configuration_to_production_choice",
)
