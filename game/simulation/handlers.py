"""Explicit runtime-only initialization of the complete built-in dispatch set.

Domain modules retain their import registrations for direct-command compatibility.
Application startup explicitly binds/verifies every built-in rather than relying
on new-world creation or incidental frontend imports. No registry enters saves.
"""


def initialize_runtime_handlers():
    """Idempotently prepare the default registry; reject conflicting bindings.

    Imports are deliberately deferred until runtime/session construction, after
    the package import graph has settled (domain modules also import the kernel).
    Custom registries remain explicit, caller-owned test/extension boundaries.
    """
    from .kernel import DEFAULT_EVENT_HANDLERS, _no_op
    from game.aircraft_operations.fulfilment import (
        FLIGHT_DEPARTURE_EVENT_TYPE, FLIGHT_COMPLETION_EVENT_TYPE,
        _departure_handler, _completion_handler,
    )
    from game.aircraft_market.step5 import (
        ROTATION_EVENT, PAYMENT_EVENT, EXPIRY_EVENT,
        _rotation_handler, _payment_handler, _expiry_handler,
    )
    from game.booking.checkpoint import BOOKING_CHECKPOINT_EVENT_TYPE, _event_handler
    from game.scheduling.recurrence import EVENT_TYPE, _weekly_publication

    bindings = (
        ('NO_OP', _no_op),
        (FLIGHT_DEPARTURE_EVENT_TYPE, _departure_handler),
        (FLIGHT_COMPLETION_EVENT_TYPE, _completion_handler),
        (ROTATION_EVENT, _rotation_handler),
        (PAYMENT_EVENT, _payment_handler),
        (EXPIRY_EVENT, _expiry_handler),
        (BOOKING_CHECKPOINT_EVENT_TYPE, _event_handler),
        (EVENT_TYPE, _weekly_publication),
    )
    registry = DEFAULT_EVENT_HANDLERS
    for event_type, handler in bindings:
        existing = registry.handler_for(event_type)
        if existing is not None and existing is not handler:
            raise ValueError(f'conflicting built-in runtime handler for {event_type}')
    for event_type, handler in bindings:
        if registry.handler_for(event_type) is None:
            registry.register(event_type, handler)
    return registry
