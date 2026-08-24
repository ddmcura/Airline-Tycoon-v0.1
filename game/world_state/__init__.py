"""Authoritative Stage 1 world foundation, separate from legacy ``game_state``."""

from .compatibility import build_legacy_read_projection
from .construction import (
    add_aircraft,
    add_airline,
    add_airport_reference,
    add_connection,
    add_directional_market,
    create_new_world,
)
from .ids import allocate_id
from .migration import MigrationResult, migrate_schema_1_to_2
from .money import major_to_minor, minor_to_decimal
from .validation import ValidationIssue, ValidationResult, validate_world
from .timestamps import normalize_utc_timestamp

__all__ = (
    "ValidationIssue",
    "ValidationResult",
    "MigrationResult",
    "add_aircraft",
    "add_airline",
    "add_airport_reference",
    "add_connection",
    "add_directional_market",
    "allocate_id",
    "build_legacy_read_projection",
    "create_new_world",
    "major_to_minor",
    "migrate_schema_1_to_2",
    "minor_to_decimal",
    "normalize_utc_timestamp",
    "validate_world",
)
