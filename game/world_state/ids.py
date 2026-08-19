"""Persisted monotonic ID allocation for a save lineage."""

import re

from .schema import ENTITY_COLLECTIONS, ENTITY_TYPES, MAX_ENTITY_ID_NUMBER


_ID_PATTERN = re.compile(r"^(?P<entity_type>[a-z_]+)-(?P<number>[0-9]{12})$")


def new_allocator_state():
    """Return a fresh allocator covering every Stage 1 entity namespace."""
    return {"next_by_type": {entity_type: 1 for entity_type in ENTITY_TYPES}}


def format_entity_id(entity_type, number):
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unknown entity type: {entity_type}")
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or number < 1
        or number > MAX_ENTITY_ID_NUMBER
    ):
        raise ValueError("ID number is outside the supported 12-digit range")
    return f"{entity_type}-{number:012d}"


def parse_entity_id(value, expected_type=None):
    """Return ``(entity_type, number)`` or ``None`` for a malformed ID."""
    if not isinstance(value, str):
        return None
    match = _ID_PATTERN.fullmatch(value)
    if not match:
        return None
    entity_type = match.group("entity_type")
    if entity_type not in ENTITY_TYPES:
        return None
    if expected_type is not None and entity_type != expected_type:
        return None
    number = int(match.group("number"))
    if number < 1:
        return None
    return entity_type, number


def allocate_id(envelope, entity_type):
    """Allocate once from authoritative state; allocated numbers are not reused."""
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unknown entity type: {entity_type}")
    try:
        next_by_type = envelope["deterministic_state"]["id_allocator"]["next_by_type"]
        number = next_by_type[entity_type]
    except (KeyError, TypeError) as exc:
        raise ValueError("Envelope does not contain a valid ID allocator") from exc
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or number < 1
        or number > MAX_ENTITY_ID_NUMBER
    ):
        raise ValueError(f"Invalid allocator value for {entity_type}")
    entity_id = format_entity_id(entity_type, number)
    collection_name = ENTITY_COLLECTIONS[entity_type][0]
    collection = envelope.get("world_state", {}).get(collection_name)
    if not isinstance(collection, dict):
        raise ValueError(f"Envelope does not contain a valid {collection_name} collection")
    if entity_id in collection or (
        entity_type == "event"
        and entity_id in envelope.get("world_state", {}).get("event_history", {})
    ):
        raise ValueError(f"ID allocator collision for {entity_id}")
    next_by_type[entity_type] = number + 1
    return entity_id
