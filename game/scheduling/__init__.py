"""Scheduling package boundaries.

The exports below are the non-interactive authoritative Milestone 3 API. Legacy
weekly schedule helpers remain in their explicit modules and are not authority.
"""

from .indexes import DatedFlightIndexes, rebuild_dated_flight_indexes
from .publication import (
    PublicationResult,
    ScheduleDefinitionResult,
    SchedulingConflict,
    configured_publication_horizon_utc,
    create_schedule_definition,
    extend_publication_window,
    publish_configured_window,
    publish_occurrences_through,
    revise_future_schedule,
    validate_schedule_definition,
)

__all__ = (
    "DatedFlightIndexes",
    "PublicationResult",
    "ScheduleDefinitionResult",
    "SchedulingConflict",
    "configured_publication_horizon_utc",
    "create_schedule_definition",
    "extend_publication_window",
    "publish_configured_window",
    "publish_occurrences_through",
    "rebuild_dated_flight_indexes",
    "revise_future_schedule",
    "validate_schedule_definition",
)
