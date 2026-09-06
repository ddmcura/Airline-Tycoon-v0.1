"""Scheduling package boundaries.

The exports below are the non-interactive authoritative Milestone 3 API. Legacy
weekly schedule helpers remain in their explicit modules and are not authority.
"""

from .indexes import DatedFlightIndexes, rebuild_dated_flight_indexes
from .publication import (
    BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW,
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
from .rotation import (
    RotationIssue,
    RotationResult,
    create_weekly_round_trip_rotation,
    publish_next_rotation,
)

__all__ = (
    "BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW",
    "DatedFlightIndexes",
    "PublicationResult",
    "RotationIssue",
    "RotationResult",
    "ScheduleDefinitionResult",
    "SchedulingConflict",
    "configured_publication_horizon_utc",
    "create_schedule_definition",
    "create_weekly_round_trip_rotation",
    "extend_publication_window",
    "publish_configured_window",
    "publish_occurrences_through",
    "publish_next_rotation",
    "rebuild_dated_flight_indexes",
    "revise_future_schedule",
    "validate_schedule_definition",
)
