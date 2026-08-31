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

__all__ = (
    "DEFAULT_EVENT_HANDLERS",
    "EventContext",
    "EventFailure",
    "EventHandlerRegistry",
    "ProcessingResult",
    "advance_by_real_seconds",
    "advance_to",
    "begin_fast_forward",
    "build_event_queue_index",
    "cancel_event",
    "configure_clock_ratios",
    "process_events_through",
    "process_next_event",
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
