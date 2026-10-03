"""Authoritative Stage 1 simulation commands.

Legacy daily-tick code remains available from its explicit module but is not
imported into this authoritative package boundary.
"""

from .kernel import (
    DEFAULT_EVENT_HANDLERS,
    EventContext,
    EventFailure,
    EventHandlerRegistry,
    ProcessingResult,
    advance_by_real_seconds,
    advance_to,
    begin_fast_forward,
    build_event_queue_index,
    cancel_event,
    configure_clock_ratios,
    process_events_through,
    process_next_event,
    run_fast_forward,
    schedule_event,
    set_clock_mode,
    set_operation_revision,
    stop_fast_forward,
    supersede_event,
)
from .projections import project_event_records, project_next_pending_event
from .resolver import (
    ResolutionBoundary, ResolutionProgress, ResolutionRequest,
    begin_resolution, resolve_until, resolve_next_event,
)

__all__ = (
    "DEFAULT_EVENT_HANDLERS",
    "EventContext",
    "EventFailure",
    "EventHandlerRegistry",
    "ProcessingResult",
    "ResolutionBoundary",
    "ResolutionProgress",
    "ResolutionRequest",
    "begin_resolution",
    "resolve_until",
    "resolve_next_event",
    "advance_by_real_seconds",
    "advance_to",
    "begin_fast_forward",
    "build_event_queue_index",
    "cancel_event",
    "configure_clock_ratios",
    "process_events_through",
    "process_next_event",
    "project_event_records",
    "project_next_pending_event",
    "run_fast_forward",
    "schedule_event",
    "set_clock_mode",
    "set_operation_revision",
    "stop_fast_forward",
    "supersede_event",
)

# Importing the built-in domain handler module registers the two schema-4
# fulfilment event types in the runtime-only dispatch table.
from game.aircraft_operations import fulfilment as _flight_fulfilment  # noqa: E402,F401
# Schema-6 marketplace payment/rotation/expiry handlers are likewise runtime
# registrations, never persisted callables.
from game.aircraft_market import step5 as _aircraft_market_step5  # noqa: E402,F401

# The weekly recurrence pump is a deterministic scheduling-domain event.
from game.scheduling import recurrence as _weekly_recurrence  # noqa: E402,F401
