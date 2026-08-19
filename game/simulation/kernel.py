"""Deterministic continuous clock and event kernel for Stage 1 authority.

The envelope is the only authority.  Heap entries, handler callables, and stop
conditions are runtime objects and are intentionally never persisted.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
import heapq
from typing import Callable

from game.world_state.ids import allocate_id
from game.world_state.schema import (
    CLOCK_STATES,
    PENDING_EVENT_STATUS,
    TERMINAL_EVENT_STATUSES,
)
from game.world_state.serialization import require_json_compatible
from game.world_state.timestamps import format_utc, parse_canonical_utc
from game.world_state.validation import validate_world


EventHandler = Callable[["EventContext"], None]
StopCondition = Callable[[dict], bool]
DEFAULT_MAX_EVENTS_PER_ADVANCE = 10_000
DEFAULT_MAX_GENERATED_EVENTS_PER_ADVANCE = 100


@dataclass(frozen=True)
class EventFailure:
    code: str
    message: str
    event_id: str | None = None
    validation_errors: tuple[dict, ...] = ()


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    started_at_utc: str
    ended_at_utc: str
    completed_event_ids: tuple[str, ...] = ()
    skipped_event_ids: tuple[str, ...] = ()
    failure: EventFailure | None = None

    @property
    def succeeded(self):
        return self.failure is None


class EventHandlerRegistry:
    """Explicit runtime dispatch table; registrations are not save data."""

    def __init__(self):
        self._handlers: dict[str, EventHandler] = {}

    def register(self, event_type, handler):
        event_type = _required_text(event_type, "event_type")
        if not callable(handler):
            raise ValueError("handler must be callable")
        if event_type in self._handlers:
            raise ValueError(f"handler already registered for {event_type}")
        self._handlers[event_type] = handler

    def handler_for(self, event_type):
        return self._handlers.get(event_type)


@dataclass(frozen=True)
class EventContext:
    envelope: dict
    event: dict

    @property
    def payload(self):
        return self.event["payload"]

    def schedule_event(self, **event_fields):
        return schedule_event(self.envelope, **event_fields)

    def pause(self):
        """Request a pause at this completed event transaction boundary."""
        self.envelope["simulation"]["clock_state"] = "PAUSED"
        self.envelope["simulation"]["fast_forward"]["target_time_utc"] = None


def _no_op(_context):
    return None


def _required_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _nonnegative_int(value, field_name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _positive_int(value, field_name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


DEFAULT_EVENT_HANDLERS = EventHandlerRegistry()
DEFAULT_EVENT_HANDLERS.register("NO_OP", _no_op)


def _valid_world_failure(envelope):
    result = validate_world(envelope)
    if result.is_valid:
        return None
    return EventFailure(
        "INVALID_WORLD",
        "authoritative world validation failed",
        validation_errors=tuple(issue.as_dict() for issue in result.errors),
    )


def _event_key(event):
    priority, sequence = event["order_key"]
    return (
        parse_canonical_utc(event["due_at_utc"], "due_at_utc"),
        priority,
        sequence,
        event["event_id"],
    )


def build_event_queue_index(envelope):
    """Rebuild and return a derived heap from authoritative pending events."""
    heap = [_event_key(event) for event in envelope["world_state"]["pending_events"].values()]
    heapq.heapify(heap)
    return heap


def configure_clock_ratios(envelope, *, normal=None, fast=None):
    ratios = envelope["simulation"]["configuration"]["clock_ratios"]
    new_normal = ratios["NORMAL"] if normal is None else _positive_int(normal, "normal")
    new_fast = ratios["FAST"] if fast is None else _positive_int(fast, "fast")
    if normal is not None:
        ratios["NORMAL"] = new_normal
    if fast is not None:
        ratios["FAST"] = new_fast
    return dict(ratios)


def set_clock_mode(envelope, mode):
    mode = _required_text(mode, "mode").upper()
    if mode not in CLOCK_STATES:
        raise ValueError(f"unknown clock mode: {mode}")
    if mode == "FAST_FORWARD":
        raise ValueError("use begin_fast_forward to supply an explicit target")
    envelope["simulation"]["clock_state"] = mode
    envelope["simulation"]["fast_forward"]["target_time_utc"] = None
    return mode


def set_operation_revision(envelope, owner_id, revision):
    _require_event_owner(envelope, None, owner_id)
    revision = _nonnegative_int(revision, "revision")
    revisions = envelope["simulation"]["operation_revisions"]
    current = revisions.get(owner_id, 0)
    if revision < current:
        raise ValueError("operation revision cannot move backward")
    revisions[owner_id] = revision
    return revision


def _owner_collections(envelope):
    world = envelope["world_state"]
    return {
        "airline": world["airlines"],
        "aircraft": world["aircraft"],
        "connection": world["connections"],
        "dated_flight": world["dated_flights"],
        "booking": world["bookings"],
    }


def _require_event_owner(envelope, owner_type, owner_id):
    targets = _owner_collections(envelope)
    if owner_type is None:
        if not isinstance(owner_id, str):
            raise ValueError("owner_id must be a string")
        matches = [kind for kind, records in targets.items() if owner_id in records]
        if len(matches) != 1:
            raise ValueError("owner_id must identify one supported existing entity")
        return matches[0]
    if owner_type not in targets or not isinstance(owner_id, str) or owner_id not in targets[owner_type]:
        raise ValueError("event owner must reference an existing supported entity")
    return owner_type


def schedule_event(
    envelope,
    *,
    event_type,
    due_at_utc,
    owner_type,
    owner_id,
    payload=None,
    operation_revision=None,
    priority=0,
):
    """Persist one event, assigning collision-safe ID and stable sequence."""
    event_type = _required_text(event_type, "event_type")
    due = parse_canonical_utc(due_at_utc, "due_at_utc")
    now = parse_canonical_utc(envelope["simulation"]["time_utc"], "simulation.time_utc")
    if due < now:
        raise ValueError("events cannot be scheduled in the past")
    owner_type = _require_event_owner(envelope, owner_type, owner_id)
    priority = _nonnegative_int(priority, "priority")
    payload = {} if payload is None else payload
    require_json_compatible(payload, "payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    revisions = envelope["simulation"]["operation_revisions"]
    current_revision = revisions.get(owner_id, 0)
    if operation_revision is None:
        operation_revision = current_revision
    operation_revision = _nonnegative_int(operation_revision, "operation_revision")
    if operation_revision > current_revision:
        raise ValueError("event revision cannot exceed its owner's current revision")

    sequence = envelope["simulation"]["event_order_cursor"]
    _nonnegative_int(sequence, "event_order_cursor")
    next_event_number = envelope["deterministic_state"]["id_allocator"]["next_by_type"]["event"]
    if sequence != next_event_number - 1:
        world = envelope["world_state"]
        existing_events = tuple(world["pending_events"].values()) + tuple(
            world["event_history"].values()
        )
        if any(
            isinstance(event.get("order_key"), list)
            and len(event["order_key"]) == 2
            and event["order_key"][1] == sequence
            for event in existing_events
        ):
            raise ValueError(f"event ordering cursor collision at sequence {sequence}")
    event_id = allocate_id(envelope, "event")
    event = {
        "event_id": event_id,
        "event_type": event_type,
        "due_at_utc": due_at_utc,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "operation_revision": operation_revision,
        "order_key": [priority, sequence],
        "payload": deepcopy(payload),
        "status": PENDING_EVENT_STATUS,
    }
    envelope["world_state"]["pending_events"][event_id] = event
    revisions.setdefault(owner_id, 0)
    envelope["simulation"]["event_order_cursor"] = sequence + 1
    return event_id


def _resolve_without_handler(envelope, event_id, status, resolved_at_utc=None):
    if status not in TERMINAL_EVENT_STATUSES:
        raise ValueError("invalid terminal event status")
    world = envelope["world_state"]
    event = world["pending_events"][event_id]
    resolved = dict(event)
    resolved["status"] = status
    resolved["resolved_at_utc"] = resolved_at_utc or envelope["simulation"]["time_utc"]
    world["event_history"][event_id] = resolved
    del world["pending_events"][event_id]


def cancel_event(envelope, event_id):
    if event_id not in envelope["world_state"]["pending_events"]:
        raise ValueError("event is not pending")
    _resolve_without_handler(envelope, event_id, "CANCELLED")


def supersede_event(envelope, event_id):
    if event_id not in envelope["world_state"]["pending_events"]:
        raise ValueError("event is not pending")
    _resolve_without_handler(envelope, event_id, "SUPERSEDED")


def _replace_envelope(target, candidate):
    committed = deepcopy(candidate)
    target.clear()
    target.update(committed)


def _handler_contract_error(original, candidate, due_at_utc):
    original_simulation = original["simulation"]
    candidate_simulation = candidate["simulation"]
    if candidate_simulation.get("time_utc") != due_at_utc:
        return "handlers cannot change the event timestamp selected by the kernel"
    if candidate_simulation.get("configuration") != original_simulation.get("configuration"):
        return "handlers cannot change clock configuration"
    original_mode = original_simulation.get("clock_state")
    candidate_mode = candidate_simulation.get("clock_state")
    original_target = original_simulation.get("fast_forward", {}).get("target_time_utc")
    candidate_target = candidate_simulation.get("fast_forward", {}).get("target_time_utc")
    if not (
        (candidate_mode == original_mode and candidate_target == original_target)
        or (candidate_mode == "PAUSED" and candidate_target is None)
    ):
        return "handlers can only preserve the clock mode or request PAUSED"

    original_world = original["world_state"]
    candidate_world = candidate["world_state"]
    for collection_name in ("pending_events", "event_history"):
        candidate_collection = candidate_world[collection_name]
        for existing_id, existing_record in original_world[collection_name].items():
            if candidate_collection.get(existing_id) != existing_record:
                return f"handlers cannot alter existing {collection_name} records"

    original_ids = set(original_world["pending_events"]) | set(
        original_world["event_history"]
    )
    candidate_ids = set(candidate_world["pending_events"]) | set(
        candidate_world["event_history"]
    )
    new_event_count = len(candidate_ids - original_ids)
    if candidate_simulation.get("event_order_cursor") != (
        original_simulation.get("event_order_cursor") + new_event_count
    ):
        return "event ordering advances only through newly persisted events"
    original_next = original["deterministic_state"]["id_allocator"]["next_by_type"][
        "event"
    ]
    candidate_next = candidate["deterministic_state"]["id_allocator"][
        "next_by_type"
    ]["event"]
    if candidate_next != original_next + new_event_count:
        return "event IDs advance only through newly persisted events"
    return None


def _execute_event(envelope, event_id, registry):
    event = envelope["world_state"]["pending_events"].get(event_id)
    if event is None:
        return None, EventFailure("EVENT_NOT_PENDING", "event is no longer pending", event_id), ()
    due = event["due_at_utc"]
    current_revision = envelope["simulation"]["operation_revisions"].get(event["owner_id"], 0)
    if event["operation_revision"] < current_revision:
        envelope["simulation"]["time_utc"] = due
        _resolve_without_handler(envelope, event_id, "STALE", due)
        return "STALE", None, ()

    handler = registry.handler_for(event["event_type"])
    if handler is None:
        return None, EventFailure(
            "UNKNOWN_EVENT_TYPE",
            f"no handler registered for {event['event_type']}",
            event_id,
        ), ()

    # The built-in no-op lifecycle has no handler mutation to isolate.  This
    # O(1) path makes queue throughput independent of total world size.
    if handler is _no_op:
        envelope["simulation"]["time_utc"] = due
        _resolve_without_handler(envelope, event_id, "COMPLETED", due)
        return "COMPLETED", None, ()

    candidate = deepcopy(envelope)
    candidate_event = candidate["world_state"]["pending_events"][event_id]
    candidate["simulation"]["time_utc"] = due
    try:
        handler_result = handler(EventContext(candidate, deepcopy(candidate_event)))
    except Exception as exc:  # handler boundary deliberately converts to data
        return None, EventFailure("HANDLER_FAILED", str(exc), event_id), ()
    if handler_result is not None:
        return None, EventFailure(
            "HANDLER_CONTRACT_VIOLATION",
            "event handlers must mutate only the candidate context and return None",
            event_id,
        ), ()

    try:
        contract_error = _handler_contract_error(envelope, candidate, due)
    except Exception:
        contract_error = "handler damaged kernel-owned authoritative structure"
    if contract_error:
        return None, EventFailure(
            "HANDLER_CONTRACT_VIOLATION", contract_error, event_id
        ), ()

    original_pending = envelope["world_state"]["pending_events"]
    candidate_pending = candidate["world_state"]["pending_events"]
    new_event_ids = tuple(sorted(set(candidate_pending) - set(original_pending)))
    _resolve_without_handler(candidate, event_id, "COMPLETED", due)
    validation = validate_world(candidate)
    if not validation.is_valid:
        return None, EventFailure(
            "RESULT_VALIDATION_FAILED",
            "handler result did not satisfy authoritative validation",
            event_id,
            tuple(issue.as_dict() for issue in validation.errors),
        ), ()
    _replace_envelope(envelope, candidate)
    return "COMPLETED", None, new_event_ids


def _failure_result(started, envelope, failure, completed=(), skipped=()):
    return ProcessingResult(
        "BLOCKED",
        started,
        envelope["simulation"]["time_utc"],
        tuple(completed),
        tuple(skipped),
        failure,
    )


def process_events_through(
    envelope,
    target_time_utc,
    *,
    registry=DEFAULT_EVENT_HANDLERS,
    stop_condition: StopCondition | None = None,
    max_events=DEFAULT_MAX_EVENTS_PER_ADVANCE,
    max_generated_events=DEFAULT_MAX_GENERATED_EVENTS_PER_ADVANCE,
):
    """Process eligible events transactionally, then stop at the exact target."""
    max_events = _positive_int(max_events, "max_events")
    max_generated_events = _positive_int(
        max_generated_events, "max_generated_events"
    )
    target = parse_canonical_utc(target_time_utc, "target_time_utc")
    started = envelope["simulation"]["time_utc"]
    started_mode = envelope["simulation"]["clock_state"]
    current = parse_canonical_utc(started, "simulation.time_utc")
    if target < current:
        raise ValueError("simulation time cannot move backward")
    failure = _valid_world_failure(envelope)
    if failure:
        return _failure_result(started, envelope, failure)

    heap = build_event_queue_index(envelope)
    completed = []
    skipped = []
    generated_event_count = 0
    while heap and heap[0][0] <= target:
        if len(completed) + len(skipped) >= max_events:
            next_event_id = heap[0][3]
            return _failure_result(
                started,
                envelope,
                EventFailure(
                    "EVENT_LIMIT_REACHED",
                    f"processing stopped after {max_events} events; retry explicitly to continue",
                    next_event_id,
                ),
                completed,
                skipped,
            )
        _due, _priority, _sequence, event_id = heapq.heappop(heap)
        if event_id not in envelope["world_state"]["pending_events"]:
            continue
        outcome, failure, new_event_ids = _execute_event(envelope, event_id, registry)
        if failure:
            return _failure_result(started, envelope, failure, completed, skipped)
        (skipped if outcome == "STALE" else completed).append(event_id)
        for new_event_id in new_event_ids:
            heapq.heappush(
                heap,
                _event_key(envelope["world_state"]["pending_events"][new_event_id]),
            )
        generated_event_count += len(new_event_ids)
        if (
            generated_event_count >= max_generated_events
            and heap
            and heap[0][0] <= target
        ):
            return _failure_result(
                started,
                envelope,
                EventFailure(
                    "EVENT_GENERATION_LIMIT_REACHED",
                    "processing stopped after the generated-event safety limit; retry explicitly to continue",
                    heap[0][3],
                ),
                completed,
                skipped,
            )
        if started_mode != "PAUSED" and envelope["simulation"]["clock_state"] == "PAUSED":
            return ProcessingResult(
                "STOPPED",
                started,
                envelope["simulation"]["time_utc"],
                tuple(completed),
                tuple(skipped),
            )
        if stop_condition is not None:
            try:
                should_stop = bool(stop_condition(deepcopy(envelope)))
            except Exception as exc:
                envelope["simulation"]["clock_state"] = "PAUSED"
                envelope["simulation"]["fast_forward"]["target_time_utc"] = None
                return _failure_result(
                    started,
                    envelope,
                    EventFailure("STOP_CONDITION_FAILED", str(exc)),
                    completed,
                    skipped,
                )
            if should_stop:
                envelope["simulation"]["clock_state"] = "PAUSED"
                envelope["simulation"]["fast_forward"]["target_time_utc"] = None
                return ProcessingResult(
                    "STOPPED",
                    started,
                    envelope["simulation"]["time_utc"],
                    tuple(completed),
                    tuple(skipped),
                )

    last_committed_time = envelope["simulation"]["time_utc"]
    envelope["simulation"]["time_utc"] = target_time_utc
    validation = validate_world(envelope)
    if not validation.is_valid:
        # Lifecycle-only paths are prevalidated and structurally constrained;
        # this guards implementation defects and exposes them diagnostically.
        failure = EventFailure(
            "RESULT_VALIDATION_FAILED",
            "event processing produced an invalid authoritative world",
            validation_errors=tuple(issue.as_dict() for issue in validation.errors),
        )
        envelope["simulation"]["time_utc"] = last_committed_time
        return _failure_result(started, envelope, failure, completed, skipped)
    return ProcessingResult(
        "COMPLETED",
        started,
        target_time_utc,
        tuple(completed),
        tuple(skipped),
    )


def process_next_event(envelope, *, registry=DEFAULT_EVENT_HANDLERS):
    started = envelope["simulation"]["time_utc"]
    failure = _valid_world_failure(envelope)
    if failure:
        return _failure_result(started, envelope, failure)
    heap = build_event_queue_index(envelope)
    if not heap:
        return ProcessingResult("NO_EVENT", started, started)
    _due, _priority, _sequence, event_id = heap[0]
    outcome, failure, _new_event_ids = _execute_event(envelope, event_id, registry)
    if failure:
        return _failure_result(started, envelope, failure)
    completed = () if outcome == "STALE" else (event_id,)
    skipped = (event_id,) if outcome == "STALE" else ()
    return ProcessingResult(
        "COMPLETED", started, envelope["simulation"]["time_utc"], completed, skipped
    )


def advance_to(envelope, target_time_utc, *, registry=DEFAULT_EVENT_HANDLERS):
    target = parse_canonical_utc(target_time_utc, "target_time_utc")
    current = parse_canonical_utc(envelope["simulation"]["time_utc"], "simulation.time_utc")
    if target < current:
        raise ValueError("simulation time cannot move backward")
    if envelope["simulation"]["clock_state"] == "PAUSED":
        now = envelope["simulation"]["time_utc"]
        return ProcessingResult("PAUSED", now, now)
    return process_events_through(envelope, target_time_utc, registry=registry)


def advance_by_real_seconds(envelope, real_seconds, *, registry=DEFAULT_EVENT_HANDLERS):
    real_seconds = _nonnegative_int(real_seconds, "real_seconds")
    mode = envelope["simulation"]["clock_state"]
    now = envelope["simulation"]["time_utc"]
    if mode == "PAUSED":
        return ProcessingResult("PAUSED", now, now)
    if mode == "FAST_FORWARD":
        raise ValueError("use run_fast_forward while in FAST_FORWARD mode")
    if not isinstance(mode, str) or mode not in {"NORMAL", "FAST"}:
        raise ValueError("world contains an invalid clock mode")
    ratio = _positive_int(
        envelope["simulation"]["configuration"]["clock_ratios"][mode],
        f"{mode} clock ratio",
    )
    try:
        target = parse_canonical_utc(now) + timedelta(
            seconds=real_seconds * ratio
        )
    except OverflowError as exc:
        raise ValueError("advance exceeds the supported timestamp range") from exc
    return process_events_through(envelope, format_utc(target), registry=registry)


def begin_fast_forward(envelope, target_time_utc):
    target = parse_canonical_utc(target_time_utc, "target_time_utc")
    current = parse_canonical_utc(envelope["simulation"]["time_utc"], "simulation.time_utc")
    if target < current:
        raise ValueError("simulation time cannot move backward")
    envelope["simulation"]["clock_state"] = "FAST_FORWARD"
    envelope["simulation"]["fast_forward"]["target_time_utc"] = target_time_utc


def stop_fast_forward(envelope):
    envelope["simulation"]["clock_state"] = "PAUSED"
    envelope["simulation"]["fast_forward"]["target_time_utc"] = None


def run_fast_forward(
    envelope,
    *,
    registry=DEFAULT_EVENT_HANDLERS,
    stop_condition: StopCondition | None = None,
):
    simulation = envelope["simulation"]
    if simulation["clock_state"] != "FAST_FORWARD":
        raise ValueError("fast-forward has not been started")
    target = simulation["fast_forward"]["target_time_utc"]
    result = process_events_through(
        envelope,
        target,
        registry=registry,
        stop_condition=stop_condition,
    )
    stop_fast_forward(envelope)
    return result
