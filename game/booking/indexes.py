"""Small deterministic runtime-only indexes over Booking authority."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from game.world_state.schema import (
    AGGREGATE_BOOKING_CONTRACT,
    SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT,
    SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT,
)


def _payload(record, compatibility_contract):
    if record.get("contract") == compatibility_contract:
        return record.get("payload", {})
    return record


def _freeze_tuple_mapping(values):
    return MappingProxyType(
        {
            key: tuple(sorted(items))
            for key, items in sorted(values.items(), key=lambda item: item[0])
        }
    )


@dataclass(frozen=True)
class BookingIndexes:
    """Disposable Booking indexes; no mapping is persistent authority."""

    checkpoint_id_by_date: Mapping[str, str]
    booked_passenger_count_by_dated_flight_id: Mapping[str, int]
    booking_ids_by_dated_flight_id: Mapping[str, tuple[str, ...]]
    booking_ids_by_checkpoint_id: Mapping[str, tuple[str, ...]]


def rebuild_booking_indexes(envelope):
    """Build indexes from validated schema-3 authority or raise ValueError."""
    metadata = envelope.get("metadata") if type(envelope) is dict else None
    if type(metadata) is not dict or metadata.get("save_schema_version") not in (3, 4):
        raise ValueError("Booking indexes require save schema version 3")
    try:
        state = envelope["world_state"]
        checkpoints = state["booking_state"]["booking_checkpoints"]
        itineraries = state["itineraries"]
        bookings = state["bookings"]
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid schema-3 Booking index input") from exc
    if any(
        type(value) is not dict
        for value in (state, checkpoints, itineraries, bookings)
    ):
        raise ValueError("invalid schema-3 Booking index input")
    if any(type(key) is not str for key in checkpoints):
        raise ValueError("invalid Booking checkpoint key")
    if any(type(key) is not str for key in bookings):
        raise ValueError("invalid Booking key")
    checkpoint_by_date = {}
    for checkpoint_id in sorted(checkpoints):
        checkpoint = checkpoints[checkpoint_id]
        if type(checkpoint_id) is not str or type(checkpoint) is not dict:
            raise ValueError("invalid Booking checkpoint record")
        checkpoint_date = checkpoint.get("checkpoint_date")
        if type(checkpoint_date) is not str:
            raise ValueError("invalid Booking checkpoint date")
        if checkpoint_date in checkpoint_by_date:
            raise ValueError(f"duplicate Booking checkpoint date: {checkpoint_date}")
        checkpoint_by_date[checkpoint_date] = checkpoint_id

    counts = {}
    booking_ids_by_flight = {}
    booking_ids_by_checkpoint = {}
    for booking_id in sorted(bookings):
        booking_record = bookings[booking_id]
        if type(booking_id) is not str or type(booking_record) is not dict:
            raise ValueError("invalid Booking record")
        compatibility = (
            booking_record.get("contract")
            == SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT
        )
        booking = _payload(
            booking_record, SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT
        )
        if type(booking) is not dict:
            raise ValueError(f"Booking {booking_id} has no valid payload")
        itinerary_id = booking.get("itinerary_id")
        itinerary_record = itineraries.get(itinerary_id)
        if type(itinerary_record) is not dict:
            raise ValueError(f"Booking {booking_id} has no valid itinerary")
        itinerary = _payload(
            itinerary_record, SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT
        )
        if type(itinerary) is not dict:
            raise ValueError(f"Booking {booking_id} has no valid itinerary payload")
        flight_ids = itinerary.get("dated_flight_ids")
        count = booking.get("passenger_count")
        if (
            type(flight_ids) is not list
            or not flight_ids
            or any(type(flight_id) is not str for flight_id in flight_ids)
            or len(set(flight_ids)) != len(flight_ids)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
        ):
            raise ValueError(f"Booking {booking_id} is not indexable")
        for flight_id in flight_ids:
            booking_ids_by_flight.setdefault(flight_id, []).append(booking_id)
            if not compatibility and booking.get("status") == "CONFIRMED":
                counts[flight_id] = counts.get(flight_id, 0) + count
        if booking_record.get("contract") == AGGREGATE_BOOKING_CONTRACT:
            checkpoint_id = booking.get("booking_checkpoint_id")
            booking_ids_by_checkpoint.setdefault(checkpoint_id, []).append(booking_id)

    return BookingIndexes(
        checkpoint_id_by_date=MappingProxyType(dict(sorted(checkpoint_by_date.items()))),
        booked_passenger_count_by_dated_flight_id=MappingProxyType(dict(sorted(counts.items()))),
        booking_ids_by_dated_flight_id=_freeze_tuple_mapping(booking_ids_by_flight),
        booking_ids_by_checkpoint_id=_freeze_tuple_mapping(booking_ids_by_checkpoint),
    )
