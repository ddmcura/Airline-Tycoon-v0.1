"""Strict schema-4 flight-fulfilment authority validation."""

import hashlib
import json

from .fulfilment_fingerprint import (
    calculate_flight_fulfilment_configuration_fingerprint,
)
from .money import is_minor_amount
from .schema import (
    AGGREGATE_BOOKING_CONTRACT,
    DEFAULT_FLIGHT_FULFILMENT_CONFIGURATION,
    DIRECT_ECONOMY_ITINERARY_CONTRACT,
    FLIGHT_COMPLETION_EVENT_CONTRACT,
    FLIGHT_COMPLETION_EVENT_TYPE,
    FLIGHT_DEPARTURE_EVENT_CONTRACT,
    FLIGHT_DEPARTURE_EVENT_TYPE,
    FLIGHT_EVENT_PRIORITY,
    FLIGHT_FULFILMENT_CONFIGURATION_CONTRACT,
    FLIGHT_FULFILMENT_CONFIGURATION_VERSION,
    FLIGHT_FULFILMENT_FORMULA,
    FLIGHT_FULFILMENT_OPERATION_CONTRACT,
    FLIGHT_RESULT_CONTRACT,
    FLIGHT_RESULT_VERSION,
)
from .timestamps import parse_canonical_utc


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _hash(value):
    return (
        type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sorted_ids(value):
    return (
        type(value) is list and value == sorted(value)
        and len(value) == len(set(value))
        and all(type(item) is str for item in value)
    )


def _add(validator, code, path, message, entity_type=None, entity_id=None):
    validator.add(code, path, message, entity_type, entity_id)


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")).hexdigest()


def _validate_manifest_witnesses(validator, record, path, world, flight):
    source_ids = record.get("source_booking_ids", [])
    witnesses = record.get("booking_witnesses")
    if type(witnesses) is not list or len(witnesses) != len(source_ids):
        _add(validator, "result_validation_failed", f"{path}.booking_witnesses",
             "must contain one witness per source Booking")
        return
    expected_witnesses = []
    expected_sales = set()
    for booking_id in source_ids:
        booking = world.get("bookings", {}).get(booking_id)
        itinerary = world.get("itineraries", {}).get(
            booking.get("itinerary_id") if type(booking) is dict else None
        )
        if type(booking) is not dict or type(itinerary) is not dict:
            _add(validator, "invalid_booking_authority", f"{path}.source_booking_ids",
                 "source IDs must reference strict Booking authority")
            continue
        market_id = world.get("connections", {}).get(
            flight.get("connection_id"), {}
        ).get("market_id")
        if (
            booking.get("contract") != AGGREGATE_BOOKING_CONTRACT
            or booking.get("status") != "CONFIRMED"
            or itinerary.get("contract") != DIRECT_ECONOMY_ITINERARY_CONTRACT
            or itinerary.get("status") != "CONFIRMED"
            or itinerary.get("dated_flight_ids") != [flight.get("dated_flight_id")]
            or booking.get("airline_id") != flight.get("airline_id")
            or itinerary.get("airline_id") != flight.get("airline_id")
            or itinerary.get("market_id") != market_id
            or itinerary.get("origin_airport_id") != flight.get("origin_airport_id")
            or itinerary.get("destination_airport_id")
            != flight.get("destination_airport_id")
            or itinerary.get("scheduled_departure_utc")
            != flight.get("scheduled_off_block_utc")
            or itinerary.get("scheduled_arrival_utc")
            != flight.get("scheduled_in_block_utc")
            or itinerary.get("schedule_lineage") != {
                "schedule_id": flight.get("schedule_id"),
                "schedule_revision": flight.get("schedule_revision"),
                "occurrence_key": flight.get("occurrence_key"),
            }
        ):
            _add(validator, "invalid_booking_authority", f"{path}.source_booking_ids",
                 "source Booking and itinerary must match the exact fulfilled flight")
        source = {
            "booking_id": booking_id,
            "itinerary_id": booking.get("itinerary_id"),
            "booking_checkpoint_id": booking.get("booking_checkpoint_id"),
            "cohort_key": booking.get("cohort_key"),
            "desired_travel_date": booking.get("desired_travel_date"),
            "passenger_count": booking.get("passenger_count"),
            "total_fare_minor": booking.get("total_fare_minor"),
            "currency": booking.get("currency"),
            "booking_revision": booking.get("booking_revision"),
            "inventory_revision_at_commit": booking.get(
                "inventory_revision_at_commit"
            ),
            "finance_transaction_id": booking.get("finance_transaction_id"),
            "schedule_lineage": itinerary.get("schedule_lineage"),
        }
        witness = dict(source)
        witness["authority_fingerprint"] = _canonical_hash(source)
        expected_witnesses.append(witness)
        if booking.get("total_fare_minor", 0) > 0:
            expected_sales.add(booking.get("finance_transaction_id"))
    if witnesses != expected_witnesses:
        _add(validator, "result_validation_failed", f"{path}.booking_witnesses",
             "Booking witnesses must match immutable source authority")
    if record.get("source_ticket_sale_transaction_ids") != sorted(expected_sales):
        _add(validator, "result_validation_failed",
             f"{path}.source_ticket_sale_transaction_ids",
             "must list exactly the paid source ticket-sale transactions")
    expected_inventory = [{
        "dated_flight_id": flight.get("dated_flight_id"),
        "inventory_revision": flight.get("inventory_revision"),
        "published_capacity": flight.get("capacity"),
    }]
    if record.get("inventory_witnesses") != expected_inventory:
        _add(validator, "result_validation_failed", f"{path}.inventory_witnesses",
             "must equal the dated-flight inventory witness")


def _validate_configuration(validator):
    configuration = validator.envelope.get("simulation", {}).get(
        "configuration", {}
    ).get("flight_fulfilment")
    path = "$.simulation.configuration.flight_fulfilment"
    fields = {
        "contract", "configuration_version", "current_revision", "revisions",
        "configuration_fingerprint",
    }
    if type(configuration) is not dict or set(configuration) != fields:
        _add(validator, "invalid_settlement_configuration", path,
             "must contain exactly the canonical fulfilment configuration fields")
        return None
    if (configuration.get("contract") != FLIGHT_FULFILMENT_CONFIGURATION_CONTRACT
            or configuration.get("configuration_version")
            != FLIGHT_FULFILMENT_CONFIGURATION_VERSION
            or configuration.get("current_revision") != 1):
        _add(validator, "invalid_settlement_configuration", path,
             "contract, version, and current revision must be revision 1")
    revisions = configuration.get("revisions")
    revision = revisions.get("1") if type(revisions) is dict else None
    revision_fields = {
        "revision", "formula_identifier", "block_minute_rounding_policy",
        "variable_cost_rounding_policy", "currency_profiles",
    }
    if type(revisions) is not dict or set(revisions) != {"1"} or type(revision) is not dict or set(revision) != revision_fields:
        _add(validator, "invalid_settlement_configuration", f"{path}.revisions",
             "must contain exactly immutable revision 1")
        return configuration
    if (
        revision.get("revision") != 1
        or revision.get("formula_identifier") != FLIGHT_FULFILMENT_FORMULA
        or revision.get("block_minute_rounding_policy")
        != "CEILING_WHOLE_MINUTE_V1"
        or revision.get("variable_cost_rounding_policy")
        != "CEILING_MINOR_UNIT_V1"
    ):
        _add(validator, "invalid_settlement_configuration", f"{path}.revisions.1",
             "formula and rounding policies must match revision 1")
    if revision != DEFAULT_FLIGHT_FULFILMENT_CONFIGURATION["revisions"]["1"]:
        _add(validator, "invalid_settlement_configuration", f"{path}.revisions.1",
             "revision 1 is immutable and must equal the approved Balanced profiles")
    profiles = revision.get("currency_profiles")
    profile_fields = {
        "currency", "calibration_reference_currency",
        "calibration_ratio_numerator", "calibration_ratio_denominator",
        "fixed_flight_cost_minor", "capacity_cost_minor_per_seat",
        "seat_block_minute_rate_numerator",
        "seat_block_minute_rate_denominator",
    }
    if type(profiles) is not dict or not profiles:
        _add(validator, "invalid_settlement_configuration", f"{path}.revisions.1.currency_profiles",
             "must contain explicit currency profiles")
        profiles = {}
    for currency, profile in profiles.items():
        profile_path = f"{path}.revisions.1.currency_profiles.{currency}"
        if (type(currency) is not str or len(currency) != 3 or currency != currency.upper()
                or type(profile) is not dict or set(profile) != profile_fields
                or profile.get("currency") != currency
                or profile.get("calibration_reference_currency") != "USD"):
            _add(validator, "invalid_settlement_configuration", profile_path,
                 "profile must use exact canonical fields and currency identity")
            continue
        for field in (
            "calibration_ratio_numerator", "calibration_ratio_denominator",
            "seat_block_minute_rate_numerator",
            "seat_block_minute_rate_denominator",
        ):
            if not _integer(profile.get(field), 1):
                _add(validator, "invalid_settlement_configuration", f"{profile_path}.{field}",
                     "must be a positive integer")
        for field in ("fixed_flight_cost_minor", "capacity_cost_minor_per_seat"):
            if not _integer(profile.get(field), 0):
                _add(validator, "invalid_settlement_configuration", f"{profile_path}.{field}",
                     "must be a non-negative integer minor-unit amount")
    try:
        expected = calculate_flight_fulfilment_configuration_fingerprint(
            configuration
        )
    except (KeyError, TypeError, ValueError):
        expected = None
    fingerprint = configuration.get("configuration_fingerprint")
    if not _hash(fingerprint) or fingerprint != expected:
        _add(validator, "inconsistent_settlement_configuration_fingerprint",
             f"{path}.configuration_fingerprint",
             "must equal the canonical fulfilment-only SHA-256 witness")
    for airline_id, airline in validator.world.get("airlines", {}).items():
        currency = airline.get("base_currency") if type(airline) is dict else None
        if currency not in profiles:
            _add(validator, "invalid_settlement_configuration",
                 f"$.world_state.airlines.{airline_id}.base_currency",
                 "airline currency requires an explicit fulfilment profile",
                 "airline", airline_id)
    return configuration


OPERATION_FIELDS = {
    "contract", "dated_flight_id", "aircraft_id", "state", "revision",
    "airline_id", "market_id", "schedule_id", "schedule_revision",
    "occurrence_key", "planned_aircraft_id", "actual_aircraft_id",
    "origin_airport_id", "destination_airport_id",
    "scheduled_off_block_utc", "scheduled_in_block_utc",
    "actual_departure_utc", "published_capacity", "source_booking_ids",
    "paid_booking_ids", "zero_fare_booking_ids",
    "source_ticket_sale_transaction_ids", "booking_witnesses",
    "inventory_witnesses", "booking_revision", "inventory_revision",
    "operation_revision_before", "fulfilment_configuration_revision",
    "fulfilment_configuration_fingerprint", "departure_event_id",
    "completion_event_id",
}

RESULT_FIELDS = {
    "contract", "result_version", "dated_flight_id", "airline_id", "market_id",
    "schedule_id", "schedule_revision", "occurrence_key",
    "planned_aircraft_id", "actual_aircraft_id", "origin_airport_id",
    "destination_airport_id", "scheduled_off_block_utc",
    "scheduled_in_block_utc", "actual_departure_utc", "actual_arrival_utc",
    "completed_at_utc", "published_capacity", "carried_passenger_count",
    "paid_passenger_count", "zero_fare_passenger_count", "source_booking_ids",
    "paid_booking_ids", "zero_fare_booking_ids",
    "source_ticket_sale_transaction_ids", "settlement_transaction_id",
    "departure_event_id", "completion_event_id", "recognized_revenue_minor",
    "operating_cost_minor", "currency", "booking_witnesses",
    "inventory_witnesses", "finance_revision_before", "finance_revision_after",
    "operation_revision_before", "operation_revision_after",
    "fulfilment_configuration_revision", "fulfilment_configuration_fingerprint",
}


def _event_payload(flight, contract):
    return {
        "contract": contract,
        "dated_flight_id": flight.get("dated_flight_id"),
        "schedule_id": flight.get("schedule_id"),
        "schedule_revision": flight.get("schedule_revision"),
        "occurrence_key": flight.get("occurrence_key"),
    }


def _valid_flight_event(
    event, flight, *, event_type, contract, due_at_utc, operation_revision,
    status,
):
    return (
        type(event) is dict
        and event.get("event_type") == event_type
        and event.get("owner_type") == "dated_flight"
        and event.get("owner_id") == flight.get("dated_flight_id")
        and event.get("due_at_utc") == due_at_utc
        and event.get("operation_revision") == operation_revision
        and event.get("order_key", [None])[0] == FLIGHT_EVENT_PRIORITY
        and event.get("payload") == _event_payload(flight, contract)
        and event.get("status") == status
    )


def _expected_operating_cost(configuration, world, flight):
    try:
        airline = world["airlines"][flight["airline_id"]]
        revision = configuration["revisions"][
            str(configuration["current_revision"])
        ]
        profile = revision["currency_profiles"][airline["base_currency"]]
        duration = (
            parse_canonical_utc(flight["scheduled_in_block_utc"])
            - parse_canonical_utc(flight["scheduled_off_block_utc"])
        )
        seconds = duration.days * 86_400 + duration.seconds
        if seconds <= 0:
            return None
        minutes = (seconds + 59) // 60
        numerator = (
            flight["capacity"]
            * minutes
            * profile["seat_block_minute_rate_numerator"]
            * 100
        )
        denominator = profile["seat_block_minute_rate_denominator"]
        variable = (numerator + denominator - 1) // denominator
        return (
            profile["fixed_flight_cost_minor"]
            + flight["capacity"] * profile["capacity_cost_minor_per_seat"]
            + variable
        )
    except (KeyError, OverflowError, TypeError, ValueError):
        return None


def _all_events(world):
    return {
        **(world.get("event_history") if type(world.get("event_history")) is dict else {}),
        **(world.get("pending_events") if type(world.get("pending_events")) is dict else {}),
    }


def _validate_schema4_fulfilment_authority(validator):
    configuration = _validate_configuration(validator)
    world = validator.world
    flights = world.get("dated_flights", {})
    operations = world.get("active_aircraft_operations", {})
    results = world.get("flight_results")
    transactions = world.get("transactions", {})
    events = _all_events(world)
    pending = world.get("pending_events", {})
    history = world.get("event_history", {})
    if type(results) is not dict:
        _add(validator, "result_validation_failed", "$.world_state.flight_results",
             "must be a dictionary keyed by dated-flight ID")
        results = {}
    for event_id, event in events.items():
        if (
            type(event) is dict
            and event.get("owner_type") == "dated_flight"
            and event.get("event_type") not in {
                FLIGHT_DEPARTURE_EVENT_TYPE, FLIGHT_COMPLETION_EVENT_TYPE,
            }
        ):
            event_path = (
                f"$.world_state.pending_events.{event_id}"
                if event_id in pending
                else f"$.world_state.event_history.{event_id}"
            )
            _add(validator, "invalid_lifecycle_event", event_path,
                 "dated-flight events must use a supported fulfilment type")
    revisions = validator.envelope.get("simulation", {}).get(
        "operation_revisions", {}
    )
    current_time = validator.envelope.get("simulation", {}).get("time_utc")
    paid_booking_owner = {}
    carried_booking_owner = {}
    active_aircraft_owner = {}
    latest_result_by_aircraft = {}
    for result_id, result in results.items():
        if type(result) is not dict:
            continue
        aircraft_id = result.get("actual_aircraft_id")
        completed_at = result.get("completed_at_utc")
        if type(aircraft_id) is str and type(completed_at) is str:
            key = (completed_at, result_id)
            previous = latest_result_by_aircraft.get(aircraft_id)
            if previous is None or key > previous[0]:
                latest_result_by_aircraft[aircraft_id] = (key, result_id)

    for flight_id, flight in flights.items():
        if type(flight) is not dict:
            continue
        path = f"$.world_state.dated_flights.{flight_id}"
        operation_revision = flight.get("operation_revision")
        if not _integer(operation_revision) or revisions.get(flight_id) != operation_revision:
            _add(validator, "invalid_revision", f"{path}.operation_revision",
                 "must equal persisted dated-flight operation authority",
                 "dated_flight", flight_id)
        status = flight.get("status")
        operation = operations.get(flight_id) if type(operations) is dict else None
        result = results.get(flight_id)
        departure_events = [event for event in events.values() if type(event) is dict
                            and event.get("event_type") == FLIGHT_DEPARTURE_EVENT_TYPE
                            and event.get("owner_id") == flight_id]
        completion_events = [event for event in events.values() if type(event) is dict
                             and event.get("event_type") == FLIGHT_COMPLETION_EVENT_TYPE
                             and event.get("owner_id") == flight_id]
        eligible = (
            flight.get("service_type") == "PASSENGER"
            and flight.get("passenger_service_classification") == "ECONOMY"
            and type(flight.get("connection_id")) is str
            and type(world.get("schedule_definitions", {}).get(
                flight.get("schedule_id")
            )) is dict
            and world["schedule_definitions"][flight["schedule_id"]].get(
                "status"
            ) == "ACTIVE"
        )
        if eligible and status == "PLANNED" and flight.get("scheduled_off_block_utc", "") >= current_time:
            current = [event for event in departure_events
                       if event.get("status") == "PENDING"
                       and event.get("operation_revision") == operation_revision]
            if len(current) != 1:
                _add(validator, "invalid_lifecycle_event", path,
                     "eligible planned flight requires exactly one current departure event")
        if status == "OPERATIONALLY_LOCKED":
            if type(operation) is not dict or result is not None:
                _add(validator, "result_validation_failed", path,
                     "locked flight requires one active operation and no result")
        elif operation is not None:
            _add(validator, "result_validation_failed",
                 f"$.world_state.active_aircraft_operations.{flight_id}",
                 "only a locked flight may retain an active operation")
        if status == "COMPLETED":
            if type(result) is not dict:
                _add(validator, "result_validation_failed", path,
                     "completed flight requires exactly one result")
        elif result is not None:
            _add(validator, "result_validation_failed",
                 f"$.world_state.flight_results.{flight_id}",
                 "only a completed flight may own a result")

        for event, event_type, contract, due in (
            *((event, FLIGHT_DEPARTURE_EVENT_TYPE, FLIGHT_DEPARTURE_EVENT_CONTRACT,
               flight.get("scheduled_off_block_utc")) for event in departure_events),
            *((event, FLIGHT_COMPLETION_EVENT_TYPE, FLIGHT_COMPLETION_EVENT_CONTRACT,
               flight.get("scheduled_in_block_utc")) for event in completion_events),
        ):
            event_path = (f"$.world_state.pending_events.{event.get('event_id')}"
                          if event.get("event_id") in pending else
                          f"$.world_state.event_history.{event.get('event_id')}")
            current_event = event.get("operation_revision") == operation_revision
            if (
                event.get("event_type") != event_type
                or event.get("owner_type") != "dated_flight"
                or event.get("order_key", [None])[0] != FLIGHT_EVENT_PRIORITY
                or type(event.get("payload")) is not dict
                or event["payload"].get("contract") != contract
                or event["payload"].get("dated_flight_id") != flight_id
                or (current_event and event.get("due_at_utc") != due)
                or (current_event and event.get("payload")
                    != _event_payload(flight, contract))
            ):
                _add(validator, "invalid_lifecycle_event", event_path,
                     "flight event must preserve exact type, owner, due time, priority, and payload")

    if type(operations) is dict:
        for flight_id, operation in operations.items():
            path = f"$.world_state.active_aircraft_operations.{flight_id}"
            flight = flights.get(flight_id, {})
            if type(operation) is not dict or set(operation) != OPERATION_FIELDS:
                _add(validator, "result_validation_failed", path,
                     "active operation must contain exactly the canonical fields")
                continue
            if (
                operation.get("contract") != FLIGHT_FULFILMENT_OPERATION_CONTRACT
                or operation.get("state") != "OPERATIONALLY_LOCKED"
                or operation.get("revision") != flight.get("operation_revision")
                or operation.get("actual_departure_utc") != flight.get("scheduled_off_block_utc")
                or operation.get("published_capacity") != flight.get("capacity")
                or operation.get("source_booking_ids")
                != sorted(operation.get("paid_booking_ids", []) + operation.get("zero_fare_booking_ids", []))
                or not _sorted_ids(operation.get("source_booking_ids"))
                or not _sorted_ids(operation.get("paid_booking_ids"))
                or not _sorted_ids(operation.get("zero_fare_booking_ids"))
                or not _sorted_ids(operation.get("source_ticket_sale_transaction_ids"))
                or operation.get("airline_id") != flight.get("airline_id")
                or operation.get("schedule_id") != flight.get("schedule_id")
                or operation.get("schedule_revision") != flight.get("schedule_revision")
                or operation.get("occurrence_key") != flight.get("occurrence_key")
                or operation.get("planned_aircraft_id") != flight.get("planned_aircraft_id")
                or operation.get("aircraft_id") != flight.get("planned_aircraft_id")
                or operation.get("actual_aircraft_id") != flight.get("planned_aircraft_id")
                or operation.get("actual_aircraft_id") != operation.get("aircraft_id")
                or operation.get("market_id") != world.get("connections", {}).get(
                    flight.get("connection_id"), {}
                ).get("market_id")
                or operation.get("origin_airport_id") != flight.get("origin_airport_id")
                or operation.get("destination_airport_id") != flight.get("destination_airport_id")
                or operation.get("scheduled_off_block_utc") != flight.get("scheduled_off_block_utc")
                or operation.get("scheduled_in_block_utc") != flight.get("scheduled_in_block_utc")
                or operation.get("operation_revision_before", -1) + 1
                != operation.get("revision")
                or operation.get("inventory_revision")
                != flight.get("inventory_revision")
                or not _integer(operation.get("booking_revision"))
                or operation.get("booking_revision")
                > world.get("booking_state", {}).get("booking_revision", -1)
                or operation.get("fulfilment_configuration_revision")
                != (configuration or {}).get("current_revision")
                or operation.get("fulfilment_configuration_fingerprint")
                != (configuration or {}).get("configuration_fingerprint")
            ):
                _add(validator, "result_validation_failed", path,
                     "active operation lineage or frozen manifest is inconsistent")
            _validate_manifest_witnesses(
                validator, operation, path, world, flight
            )
            aircraft = world.get("aircraft", {}).get(operation.get("actual_aircraft_id"))
            if type(aircraft) is not dict or aircraft.get("status") != "IN_FLIGHT" or aircraft.get("current_airport_id") is not None:
                _add(validator, "aircraft_unavailable", f"{path}.actual_aircraft_id",
                     "operation aircraft must be IN_FLIGHT with null current airport")
            aircraft_id = operation.get("actual_aircraft_id")
            previous_operation = active_aircraft_owner.get(aircraft_id)
            if previous_operation is not None:
                _add(validator, "aircraft_unavailable", f"{path}.actual_aircraft_id",
                     f"aircraft is already used by {previous_operation}")
            elif type(aircraft_id) is str:
                active_aircraft_owner[aircraft_id] = flight_id
            for booking_id in operation.get("source_booking_ids", []):
                previous_flight = carried_booking_owner.get(booking_id)
                if previous_flight is not None:
                    _add(validator, "settlement_result_conflict",
                         f"{path}.source_booking_ids",
                         f"Booking is already carried by {previous_flight}")
                else:
                    carried_booking_owner[booking_id] = flight_id
            departure = events.get(operation.get("departure_event_id"))
            completion = events.get(operation.get("completion_event_id"))
            if not _valid_flight_event(
                departure,
                flight,
                event_type=FLIGHT_DEPARTURE_EVENT_TYPE,
                contract=FLIGHT_DEPARTURE_EVENT_CONTRACT,
                due_at_utc=flight.get("scheduled_off_block_utc"),
                operation_revision=operation.get("operation_revision_before"),
                status="COMPLETED",
            ):
                _add(validator, "invalid_lifecycle_event", f"{path}.departure_event_id",
                     "operation must reference its exact completed departure event")
            if not _valid_flight_event(
                completion,
                flight,
                event_type=FLIGHT_COMPLETION_EVENT_TYPE,
                contract=FLIGHT_COMPLETION_EVENT_CONTRACT,
                due_at_utc=flight.get("scheduled_in_block_utc"),
                operation_revision=operation.get("revision"),
                status="PENDING",
            ):
                _add(validator, "invalid_lifecycle_event", f"{path}.completion_event_id",
                     "operation must reference its exact pending completion event")
            if len(completion_events := [
                event for event in events.values()
                if type(event) is dict
                and event.get("event_type") == FLIGHT_COMPLETION_EVENT_TYPE
                and event.get("owner_id") == flight_id
            ]) != 1:
                _add(validator, "invalid_lifecycle_event", path,
                     "locked flight must own exactly one completion event")
            if len([
                event for event in events.values()
                if type(event) is dict
                and event.get("event_type") == FLIGHT_DEPARTURE_EVENT_TYPE
                and event.get("owner_id") == flight_id
            ]) != 1:
                _add(validator, "invalid_lifecycle_event", path,
                     "locked flight must own exactly one departure event")

    for flight_id, result in results.items():
        path = f"$.world_state.flight_results.{flight_id}"
        flight = flights.get(flight_id, {})
        if type(result) is not dict or set(result) != RESULT_FIELDS:
            _add(validator, "result_validation_failed", path,
                 "flight result must contain exactly the canonical immutable fields")
            continue
        if (
            result.get("contract") != FLIGHT_RESULT_CONTRACT
            or result.get("result_version") != FLIGHT_RESULT_VERSION
            or result.get("dated_flight_id") != flight_id
            or result.get("actual_departure_utc") != flight.get("scheduled_off_block_utc")
            or result.get("actual_arrival_utc") != flight.get("scheduled_in_block_utc")
            or result.get("completed_at_utc") != flight.get("scheduled_in_block_utc")
            or result.get("published_capacity") != flight.get("capacity")
            or result.get("source_booking_ids")
            != sorted(result.get("paid_booking_ids", []) + result.get("zero_fare_booking_ids", []))
            or not _sorted_ids(result.get("source_booking_ids"))
            or not _sorted_ids(result.get("paid_booking_ids"))
            or not _sorted_ids(result.get("zero_fare_booking_ids"))
            or result.get("airline_id") != flight.get("airline_id")
            or result.get("schedule_id") != flight.get("schedule_id")
            or result.get("schedule_revision") != flight.get("schedule_revision")
            or result.get("occurrence_key") != flight.get("occurrence_key")
            or result.get("planned_aircraft_id") != flight.get("planned_aircraft_id")
            or result.get("actual_aircraft_id") != flight.get("planned_aircraft_id")
            or result.get("origin_airport_id") != flight.get("origin_airport_id")
            or result.get("destination_airport_id") != flight.get("destination_airport_id")
            or result.get("scheduled_off_block_utc") != flight.get("scheduled_off_block_utc")
            or result.get("scheduled_in_block_utc") != flight.get("scheduled_in_block_utc")
        ):
            _add(validator, "result_validation_failed", path,
                 "result identity, timestamps, capacity, or Booking partition is invalid")
        _validate_manifest_witnesses(validator, result, path, world, flight)
        expected_cost = _expected_operating_cost(configuration, world, flight)
        if expected_cost is None or result.get("operating_cost_minor") != expected_cost:
            _add(validator, "result_validation_failed",
                 f"{path}.operating_cost_minor",
                 "must equal the immutable fulfilment configuration and flight inputs")
        counts = (
            result.get("carried_passenger_count"),
            result.get("paid_passenger_count"),
            result.get("zero_fare_passenger_count"),
        )
        if (any(not _integer(value) for value in counts)
                or counts[0] != counts[1] + counts[2]
                or counts[0] > result.get("published_capacity", -1)):
            _add(validator, "result_validation_failed", path,
                 "passenger counts must conserve within capacity")
        for booking_id in result.get("paid_booking_ids", []):
            previous = paid_booking_owner.get(booking_id)
            if previous is not None:
                _add(validator, "settlement_result_conflict", f"{path}.paid_booking_ids",
                     f"paid Booking already recognized by {previous}")
            else:
                paid_booking_owner[booking_id] = flight_id
        for booking_id in result.get("source_booking_ids", []):
            previous_flight = carried_booking_owner.get(booking_id)
            if previous_flight is not None:
                _add(validator, "settlement_result_conflict",
                     f"{path}.source_booking_ids",
                     f"Booking is already carried by {previous_flight}")
            else:
                carried_booking_owner[booking_id] = flight_id
        paid_bookings = [world.get("bookings", {}).get(booking_id)
                         for booking_id in result.get("paid_booking_ids", [])]
        zero_bookings = [world.get("bookings", {}).get(booking_id)
                         for booking_id in result.get("zero_fare_booking_ids", [])]
        revenue = sum(booking.get("total_fare_minor", 0) for booking in paid_bookings
                      if type(booking) is dict)
        paid_passengers = sum(booking.get("passenger_count", 0)
                              for booking in paid_bookings
                              if type(booking) is dict)
        zero_passengers = sum(booking.get("passenger_count", 0)
                              for booking in zero_bookings
                              if type(booking) is dict)
        if (result.get("recognized_revenue_minor") != revenue
                or result.get("paid_passenger_count") != paid_passengers
                or result.get("zero_fare_passenger_count") != zero_passengers
                or any(type(booking) is not dict or booking.get("total_fare_minor", 0) <= 0
                       for booking in paid_bookings)
                or any(type(booking) is not dict or booking.get("total_fare_minor") != 0
                       for booking in zero_bookings)
                or not is_minor_amount(result.get("operating_cost_minor"))
                or result.get("operating_cost_minor", -1) < 0):
            _add(validator, "result_validation_failed", path,
                 "Booking fare partition, recognized revenue, or operating cost is invalid")
        transaction = transactions.get(result.get("settlement_transaction_id"))
        airline = world.get("airlines", {}).get(result.get("airline_id"), {})
        account_by_code = {
            world["financial_accounts"].get(account_id, {}).get("code"): account_id
            for account_id in airline.get("financial_account_ids", [])
        } if type(airline) is dict else {}
        expected_entries = []
        if revenue:
            expected_entries.extend([
                {"account_id": account_by_code.get("unflown_tickets"), "amount_minor": revenue},
                {"account_id": account_by_code.get("passenger_revenue"), "amount_minor": -revenue},
            ])
        expected_entries.extend([
            {"account_id": account_by_code.get("operating_expenses"), "amount_minor": result.get("operating_cost_minor")},
            {"account_id": account_by_code.get("cash"), "amount_minor": -result.get("operating_cost_minor", 0)},
        ])
        if (
            type(transaction) is not dict
            or transaction.get("source_type") != "FLIGHT_FULFILMENT"
            or transaction.get("source_id") != flight_id
            or transaction.get("source_booking_ids") != result.get("paid_booking_ids")
            or transaction.get("source_ticket_sale_transaction_ids")
            != result.get("source_ticket_sale_transaction_ids")
            or transaction.get("occurred_at_utc") != result.get("completed_at_utc")
            or transaction.get("currency") != result.get("currency")
            or transaction.get("entries") != expected_entries
        ):
            _add(validator, "settlement_result_conflict", f"{path}.settlement_transaction_id",
                 "settlement transaction must exactly reconcile result lineage and journal")
        actual_aircraft = world.get("aircraft", {}).get(result.get("actual_aircraft_id"))
        market_id = world.get("connections", {}).get(
            flight.get("connection_id"), {}
        ).get("market_id")
        if (
            result.get("market_id") != market_id
            or type(actual_aircraft) is not dict
            or actual_aircraft.get("airline_id") != result.get("airline_id")
        ):
            _add(validator, "result_validation_failed", path,
                 "market and actual-aircraft completion topology is inconsistent")
        latest = latest_result_by_aircraft.get(result.get("actual_aircraft_id"))
        if (
            latest is not None
            and latest[1] == flight_id
            and result.get("actual_aircraft_id") not in active_aircraft_owner
            and type(actual_aircraft) is dict
            and (
                actual_aircraft.get("status") != "PARKED"
                or actual_aircraft.get("current_airport_id")
                != result.get("destination_airport_id")
            )
        ):
            _add(validator, "result_validation_failed", path,
                 "latest completed aircraft must be parked at its destination")
        if (
            not _integer(result.get("finance_revision_before"))
            or result.get("finance_revision_after")
            != result.get("finance_revision_before", -1) + 1
            or result.get("finance_revision_after", -1)
            > world.get("airlines", {}).get(
                result.get("airline_id"), {}
            ).get("finance_revision", -1)
            or result.get("operation_revision_after") != result.get("operation_revision_before", -1) + 1
            or result.get("operation_revision_after") != flight.get("operation_revision")
            or result.get("fulfilment_configuration_revision")
            != (configuration or {}).get("current_revision")
            or result.get("fulfilment_configuration_fingerprint")
            != (configuration or {}).get("configuration_fingerprint")
        ):
            _add(validator, "result_validation_failed", path,
                 "revision or fulfilment-configuration witnesses are inconsistent")
        departure = history.get(result.get("departure_event_id"))
        completion = history.get(result.get("completion_event_id"))
        if not _valid_flight_event(
            departure,
            flight,
            event_type=FLIGHT_DEPARTURE_EVENT_TYPE,
            contract=FLIGHT_DEPARTURE_EVENT_CONTRACT,
            due_at_utc=flight.get("scheduled_off_block_utc"),
            operation_revision=result.get("operation_revision_before", 0) - 1,
            status="COMPLETED",
        ) or not _valid_flight_event(
            completion,
            flight,
            event_type=FLIGHT_COMPLETION_EVENT_TYPE,
            contract=FLIGHT_COMPLETION_EVENT_CONTRACT,
            due_at_utc=flight.get("scheduled_in_block_utc"),
            operation_revision=result.get("operation_revision_before"),
            status="COMPLETED",
        ):
            _add(validator, "invalid_lifecycle_event", path,
                 "completed result requires exact terminal departure and completion events")
        completion_events = [
            event for event in events.values()
            if type(event) is dict
            and event.get("event_type") == FLIGHT_COMPLETION_EVENT_TYPE
            and event.get("owner_id") == flight_id
        ]
        if len(completion_events) != 1:
            _add(validator, "invalid_lifecycle_event", path,
                 "completed flight must own exactly one completion event")
        departure_events = [
            event for event in events.values()
            if type(event) is dict
            and event.get("event_type") == FLIGHT_DEPARTURE_EVENT_TYPE
            and event.get("owner_id") == flight_id
        ]
        if len(departure_events) != 1:
            _add(validator, "invalid_lifecycle_event", path,
                 "completed flight must own exactly one departure event")

    settlement_owner = {}
    for transaction_id, transaction in transactions.items():
        if type(transaction) is not dict or transaction.get("source_type") != "FLIGHT_FULFILMENT":
            continue
        flight_id = transaction.get("source_id")
        previous = settlement_owner.get(flight_id)
        if previous is not None:
            _add(validator, "settlement_result_conflict",
                 f"$.world_state.transactions.{transaction_id}",
                 f"flight already owns settlement {previous}")
        else:
            settlement_owner[flight_id] = transaction_id
        result = results.get(flight_id)
        if type(result) is not dict or result.get("settlement_transaction_id") != transaction_id:
            _add(validator, "settlement_result_conflict",
                 f"$.world_state.transactions.{transaction_id}",
                 "fulfilment settlement must be owned by exactly one result")

    for aircraft_id, aircraft in world.get("aircraft", {}).items():
        if type(aircraft) is not dict:
            continue
        if aircraft.get("status") == "IN_FLIGHT" and aircraft_id not in active_aircraft_owner:
            _add(validator, "aircraft_unavailable",
                 f"$.world_state.aircraft.{aircraft_id}.status",
                 "IN_FLIGHT aircraft must belong to exactly one active operation")


def validate_schema4_fulfilment_authority(validator):
    """Add structured issues for all malformed schema-4 fulfilment authority."""
    try:
        _validate_schema4_fulfilment_authority(validator)
    except Exception as exc:
        _add(
            validator,
            "invalid_fulfilment_authority",
            "$.world_state",
            "malformed fulfilment authority could not be validated safely: "
            f"{type(exc).__name__}",
        )


__all__ = ("validate_schema4_fulfilment_authority",)
