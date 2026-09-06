"""Detached deterministic projections for pending and resolved events."""

from copy import deepcopy

from game.world_state.validation import validate_world


def _event_row(event):
    return {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "due_at_utc": event["due_at_utc"],
        "priority": event["order_key"][0],
        "sequence": event["order_key"][1],
        "owner_type": event["owner_type"],
        "owner_id": event["owner_id"],
        "status": event["status"],
    }


def project_next_pending_event(envelope):
    """Return the next persisted event by canonical kernel ordering."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        return None
    pending = envelope["world_state"]["pending_events"]
    if not pending:
        return None
    event = min(
        pending.values(),
        key=lambda item: (
            item["due_at_utc"], item["order_key"][0],
            item["order_key"][1], item["event_id"],
        ),
    )
    return deepcopy(_event_row(event))


def project_event_records(envelope, event_ids, *, limit=100):
    """Project selected pending/history rows in caller-supplied event order."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100:
        raise ValueError("limit must be an integer from 0 through 100")
    if not isinstance(event_ids, (tuple, list)) or any(
        not isinstance(event_id, str) for event_id in event_ids
    ):
        raise ValueError("event_ids must be a sequence of strings")
    validation = validate_world(envelope)
    if not validation.is_valid:
        return None
    world = envelope["world_state"]
    rows = []
    for event_id in event_ids[:limit]:
        event = world["event_history"].get(event_id) or world["pending_events"].get(event_id)
        if event is not None:
            rows.append(_event_row(event))
    return deepcopy(rows)


__all__ = ("project_event_records", "project_next_pending_event")
