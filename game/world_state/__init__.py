"""Authoritative Stage 1 world foundation, separate from legacy ``game_state``."""

from .compatibility import build_legacy_read_projection
from .booking_fingerprint import (
    BookingConfigurationTransitionIssue,
    BookingConfigurationTransitionResult,
    calculate_booking_configuration_fingerprint,
    new_booking_configuration,
    transition_booking_configuration_to_production_choice,
)
from .construction import (
    add_aircraft,
    add_airline,
    add_airport_reference,
    add_connection,
    add_directional_market,
    create_new_world,
)
from .ids import allocate_id
from .migration import MigrationResult, migrate_schema_1_to_2, migrate_schema_2_to_3
from .market_packs import (
    MarketPackIssue,
    MarketPackLifecycleResult,
    disable_country_pack,
    enable_country_pack,
    materialize_country_pack,
)
from .money import major_to_minor, minor_to_decimal
from .validation import ValidationIssue, ValidationResult, validate_world
from .timestamps import normalize_utc_timestamp

__all__ = (
    "ValidationIssue",
    "ValidationResult",
    "MigrationResult",
    "BookingConfigurationTransitionIssue",
    "BookingConfigurationTransitionResult",
    "MarketPackIssue",
    "MarketPackLifecycleResult",
    "add_aircraft",
    "add_airline",
    "add_airport_reference",
    "add_connection",
    "add_directional_market",
    "allocate_id",
    "build_legacy_read_projection",
    "calculate_booking_configuration_fingerprint",
    "create_new_world",
    "disable_country_pack",
    "enable_country_pack",
    "major_to_minor",
    "migrate_schema_1_to_2",
    "migrate_schema_2_to_3",
    "minor_to_decimal",
    "materialize_country_pack",
    "normalize_utc_timestamp",
    "new_booking_configuration",
    "transition_booking_configuration_to_production_choice",
    "validate_world",
)
