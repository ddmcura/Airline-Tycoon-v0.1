"""Persisted monotonic ID allocation for a save lineage."""

import re

from .schema import (
    ENTITY_TYPES,
    MAX_ENTITY_ID_NUMBER,
    SCHEMA8_ENTITY_TYPES,
    SCHEMA8_ENTITY_COLLECTIONS,
)


_ID_PATTERN = re.compile(r"^(?P<entity_type>[a-z_]+)-(?P<number>[0-9]{12})$")


def new_allocator_state():
    """Return a fresh allocator covering every Stage 1 entity namespace."""
    return {"next_by_type": {entity_type: 1 for entity_type in ENTITY_TYPES}}


def format_entity_id(entity_type, number):
    if entity_type not in SCHEMA8_ENTITY_TYPES:
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
    if entity_type not in SCHEMA8_ENTITY_TYPES:
        return None
    if expected_type is not None and entity_type != expected_type:
        return None
    number = int(match.group("number"))
    if number < 1:
        return None
    return entity_type, number


def allocate_id(envelope, entity_type):
    """Allocate once from authoritative state; allocated numbers are not reused."""
    if entity_type not in SCHEMA8_ENTITY_TYPES:
        raise ValueError(f"Unknown entity type: {entity_type}")
    if entity_type in {'service', 'weekly_plan'} and envelope.get('metadata', {}).get('save_schema_version') not in (8, 9):
        raise ValueError('quarterly identity allocation requires schema 8 or 9')
    if entity_type == "booking_checkpoint":
        metadata = envelope.get("metadata") if type(envelope) is dict else None
        if (
            type(metadata) is not dict
            or metadata.get("save_schema_version") not in (3, 4, 5, 6, 7, 8, 9)
        ):
            raise ValueError(
                "booking_checkpoint IDs require save schema version 3"
            )
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
    if entity_type == "booking_checkpoint":
        collection_name = "booking_checkpoints"
        collection = (
            envelope.get("world_state", {})
            .get("booking_state", {})
            .get(collection_name)
        )
    elif entity_type == "aircraft_market":
        collection_name = "aircraft_market_state"
        state = envelope.get("world_state", {}).get(collection_name)
        collection = {} if state is None else {state.get("aircraft_market_id"): state}
    elif entity_type == "airframe":
        # Airframes are embedded in aircraft/listings and use only the allocator.
        collection_name = "airframe identities"
        collection = {}
        world = envelope.get("world_state", {})
        for aircraft in world.get("aircraft", {}).values():
            lifecycle = aircraft.get("lifecycle", {})
            if type(lifecycle.get("airframe_id")) is str:
                collection[lifecycle["airframe_id"]] = lifecycle
        for listing in world.get("used_aircraft_listings", {}).values():
            if type(listing.get("airframe_id")) is str:
                collection[listing["airframe_id"]] = listing
    else:
        collection_name = SCHEMA8_ENTITY_COLLECTIONS[entity_type][0]
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
