"""Atomic two-event Stage 1 flight fulfilment."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

from game.simulation.kernel import DEFAULT_EVENT_HANDLERS, schedule_event
from game.world_state.ids import allocate_id
from game.world_state.schema import (
    AGGREGATE_BOOKING_CONTRACT,
    DIRECT_ECONOMY_ITINERARY_CONTRACT,
    FLIGHT_COMPLETION_EVENT_CONTRACT,
    FLIGHT_COMPLETION_EVENT_TYPE,
    FLIGHT_DEPARTURE_EVENT_CONTRACT,
    FLIGHT_DEPARTURE_EVENT_TYPE,
    FLIGHT_EVENT_PRIORITY,
    FLIGHT_FULFILMENT_OPERATION_CONTRACT,
    FLIGHT_RESULT_CONTRACT,
    FLIGHT_RESULT_VERSION,
)
from game.world_state.timestamps import parse_canonical_utc
from game.world_state.validation import validate_world


@dataclass(frozen=True)
class FlightFulfilmentIssue:
    code: str
    message: str
    path: str | None = None

    def as_dict(self):
        return {"code": self.code, "message": self.message, "path": self.path}


@dataclass(frozen=True)
class FlightManifest:
    dated_flight_id: str
    source_booking_ids: tuple[str, ...]
    paid_booking_ids: tuple[str, ...]
    zero_fare_booking_ids: tuple[str, ...]
    source_ticket_sale_transaction_ids: tuple[str, ...]
    carried_passenger_count: int
    paid_passenger_count: int
    zero_fare_passenger_count: int
    recognized_revenue_minor: int
    currency: str
    booking_witnesses: tuple[dict, ...]
    inventory_witnesses: tuple[dict, ...]
    issues: tuple[FlightFulfilmentIssue, ...] = ()

    @property
    def succeeded(self):
        return not self.issues

    def as_dict(self):
        return {
            "dated_flight_id": self.dated_flight_id,
            "source_booking_ids": list(self.source_booking_ids),
            "paid_booking_ids": list(self.paid_booking_ids),
            "zero_fare_booking_ids": list(self.zero_fare_booking_ids),
            "source_ticket_sale_transaction_ids": list(
                self.source_ticket_sale_transaction_ids
            ),
            "carried_passenger_count": self.carried_passenger_count,
            "paid_passenger_count": self.paid_passenger_count,
            "zero_fare_passenger_count": self.zero_fare_passenger_count,
            "recognized_revenue_minor": self.recognized_revenue_minor,
            "currency": self.currency,
            "booking_witnesses": deepcopy(list(self.booking_witnesses)),
            "inventory_witnesses": deepcopy(list(self.inventory_witnesses)),
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class FlightFulfilmentResult:
    status: str
    dated_flight_id: str | None
    reused: bool = False
    event_id: str | None = None
    completion_event_id: str | None = None
    settlement_transaction_id: str | None = None
    flight_result: dict | None = None
    manifest: FlightManifest | None = None
    issues: tuple[FlightFulfilmentIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _reject(envelope, flight_id, code, message, path=None, *, status="REJECTED"):
    return FlightFulfilmentResult(
        status,
        flight_id if type(flight_id) is str else None,
        issues=(FlightFulfilmentIssue(code, message, path),),
    )


def _witnesses_are_well_formed(witnesses):
    for name, value in witnesses.items():
        if name == "expected_configuration_fingerprint":
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                return False
        elif type(value) is not int or value < 0:
            return False
    return True


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")).hexdigest()


def _booking_checkpoint_contains(world, booking):
    state = world.get("booking_state", {})
    checkpoint = state.get("booking_checkpoints", {}).get(
        booking.get("booking_checkpoint_id")
    )
    if type(checkpoint) is not dict or checkpoint.get("status") != "COMPLETED":
        return False
    market_id = world["itineraries"][booking["itinerary_id"]]["market_id"]
    result = checkpoint.get("market_results", {}).get(market_id)
    if type(result) is not dict or booking["booking_id"] not in result.get(
        "booking_ids", []
    ):
        return False
    desired = result.get("desired_date_results", {}).get(
        booking.get("desired_travel_date")
    )
    return type(desired) is dict and booking["booking_id"] in desired.get(
        "booking_ids", []
    )


def _sale_lineage_valid(world, booking):
    transaction_id = booking.get("finance_transaction_id")
    if booking.get("total_fare_minor") == 0:
        return transaction_id is None
    transaction = world.get("transactions", {}).get(transaction_id)
    return (
        type(transaction) is dict
        and transaction.get("source_type") == "BOOKING_CHECKPOINT"
        and transaction.get("source_id") == booking.get("booking_checkpoint_id")
        and transaction.get("airline_id") == booking.get("airline_id")
        and transaction.get("currency") == booking.get("currency")
        and booking.get("booking_id") in transaction.get("source_booking_ids", [])
    )


def build_confirmed_carriage_manifest(envelope, dated_flight_id):
    """Return the detached strict confirmed V1 Booking manifest."""
    empty = lambda issue: FlightManifest(
        dated_flight_id if type(dated_flight_id) is str else "",
        (), (), (), (), 0, 0, 0, 0, "", (), (), (issue,),
    )
    if type(envelope) is not dict:
        return empty(FlightFulfilmentIssue(
            "INVALID_WORLD_STATE", "world envelope must be a dictionary", "$"
        ))
    validation = validate_world(envelope)
    if not validation.is_valid:
        issue = validation.errors[0]
        return empty(FlightFulfilmentIssue(
            "INVALID_WORLD_STATE", issue.message, issue.path
        ))
    if type(dated_flight_id) is not str:
        return empty(FlightFulfilmentIssue(
            "INVALID_FLIGHT_ID", "dated flight ID must be a string",
            "$.world_state.dated_flights",
        ))
    world = envelope["world_state"]
    flight = world["dated_flights"].get(dated_flight_id)
    if type(flight) is not dict:
        return empty(FlightFulfilmentIssue(
            "FLIGHT_NOT_FOUND", "dated flight does not exist",
            f"$.world_state.dated_flights.{dated_flight_id}",
        ))
    airline = world["airlines"][flight["airline_id"]]
    market = world["directional_markets"].get(
        world["connections"].get(flight.get("connection_id"), {}).get("market_id")
    )
    if (
        flight.get("service_type") != "PASSENGER"
        or flight.get("passenger_service_classification") != "ECONOMY"
        or type(market) is not dict
    ):
        return empty(FlightFulfilmentIssue(
            "FLIGHT_NOT_OPERABLE", "flight is not a direct Economy passenger service"
        ))

    rows = []
    for booking_id in sorted(world["bookings"]):
        booking = world["bookings"][booking_id]
        if (
            type(booking) is not dict
            or booking.get("contract") != AGGREGATE_BOOKING_CONTRACT
            or booking.get("status") != "CONFIRMED"
        ):
            continue
        itinerary = world["itineraries"].get(booking.get("itinerary_id"))
        if (
            type(itinerary) is not dict
            or itinerary.get("contract") != DIRECT_ECONOMY_ITINERARY_CONTRACT
            or itinerary.get("status") != "CONFIRMED"
            or itinerary.get("dated_flight_ids") != [dated_flight_id]
        ):
            continue
        exact = (
            booking.get("airline_id") == flight["airline_id"]
            and itinerary.get("airline_id") == flight["airline_id"]
            and itinerary.get("market_id") == market["market_id"]
            and itinerary.get("origin_airport_id") == flight["origin_airport_id"]
            and itinerary.get("destination_airport_id")
            == flight["destination_airport_id"]
            and itinerary.get("scheduled_departure_utc")
            == flight["scheduled_off_block_utc"]
            and itinerary.get("scheduled_arrival_utc")
            == flight["scheduled_in_block_utc"]
            and itinerary.get("cabin") == "ECONOMY"
            and itinerary.get("schedule_lineage") == {
                "schedule_id": flight["schedule_id"],
                "schedule_revision": flight["schedule_revision"],
                "occurrence_key": flight["occurrence_key"],
            }
            and booking.get("currency") == airline["base_currency"]
            and booking.get("inventory_revision_at_commit", -1)
            <= flight["inventory_revision"]
            and _booking_checkpoint_contains(world, booking)
            and _sale_lineage_valid(world, booking)
        )
        if not exact:
            return empty(FlightFulfilmentIssue(
                "INVALID_BOOKING_AUTHORITY",
                f"Booking {booking_id} does not match exact flight lineage",
                f"$.world_state.bookings.{booking_id}",
            ))
        witness_source = {
            "booking_id": booking_id,
            "itinerary_id": booking["itinerary_id"],
            "booking_checkpoint_id": booking["booking_checkpoint_id"],
            "cohort_key": booking["cohort_key"],
            "desired_travel_date": booking["desired_travel_date"],
            "passenger_count": booking["passenger_count"],
            "total_fare_minor": booking["total_fare_minor"],
            "currency": booking["currency"],
            "booking_revision": booking["booking_revision"],
            "inventory_revision_at_commit": booking[
                "inventory_revision_at_commit"
            ],
            "finance_transaction_id": booking["finance_transaction_id"],
            "schedule_lineage": deepcopy(itinerary["schedule_lineage"]),
        }
        witness = deepcopy(witness_source)
        witness["authority_fingerprint"] = _canonical_hash(witness_source)
        rows.append((booking, witness))

    total = sum(booking["passenger_count"] for booking, _ in rows)
    if total > flight["capacity"]:
        return empty(FlightFulfilmentIssue(
            "CAPACITY_EXCEEDED", "confirmed manifest exceeds published capacity"
        ))
    paid = [booking for booking, _ in rows if booking["total_fare_minor"] > 0]
    zero = [booking for booking, _ in rows if booking["total_fare_minor"] == 0]
    sale_ids = sorted({booking["finance_transaction_id"] for booking in paid})
    return FlightManifest(
        dated_flight_id,
        tuple(booking["booking_id"] for booking, _ in rows),
        tuple(booking["booking_id"] for booking in paid),
        tuple(booking["booking_id"] for booking in zero),
        tuple(sale_ids),
        total,
        sum(booking["passenger_count"] for booking in paid),
        sum(booking["passenger_count"] for booking in zero),
        sum(booking["total_fare_minor"] for booking in paid),
        airline["base_currency"],
        tuple(deepcopy(witness) for _booking, witness in rows),
        ({
            "dated_flight_id": dated_flight_id,
            "inventory_revision": flight["inventory_revision"],
            "published_capacity": flight["capacity"],
        },),
    )


def _event_key(event):
    return (
        parse_canonical_utc(event["due_at_utc"]),
        event["order_key"][0], event["order_key"][1], event["event_id"],
    )


def _next_event(envelope):
    events = envelope["world_state"]["pending_events"].values()
    return min(events, key=_event_key) if events else None


def _matching_event(envelope, flight, event_type, contract, due):
    expected_payload = {
        "contract": contract,
        "dated_flight_id": flight["dated_flight_id"],
        "schedule_id": flight["schedule_id"],
        "schedule_revision": flight["schedule_revision"],
        "occurrence_key": flight["occurrence_key"],
    }
    matches = [event for event in envelope["world_state"]["pending_events"].values()
               if event.get("owner_type") == "dated_flight"
               and event.get("owner_id") == flight["dated_flight_id"]
               and event.get("event_type") == event_type
               and event.get("due_at_utc") == due
               and event.get("payload") == expected_payload
               and event.get("operation_revision") == flight["operation_revision"]]
    return matches[0] if len(matches) == 1 else None


def _resolve_event(candidate, event_id):
    world = candidate["world_state"]
    event = world["pending_events"].pop(event_id)
    resolved = deepcopy(event)
    resolved["status"] = "COMPLETED"
    resolved["resolved_at_utc"] = event["due_at_utc"]
    world["event_history"][event_id] = resolved


def _replace(target, candidate):
    target.clear()
    target.update(deepcopy(candidate))


def _configuration(envelope):
    configuration = envelope["simulation"]["configuration"]["flight_fulfilment"]
    revision = configuration["current_revision"]
    return configuration, configuration["revisions"][str(revision)]


def calculate_operating_cost(envelope, flight):
    configuration, revision = _configuration(envelope)
    profile = revision["currency_profiles"][
        envelope["world_state"]["airlines"][flight["airline_id"]]["base_currency"]
    ]
    duration = (
        parse_canonical_utc(flight["scheduled_in_block_utc"])
        - parse_canonical_utc(flight["scheduled_off_block_utc"])
    )
    seconds = duration.days * 86_400 + duration.seconds
    if seconds <= 0:
        raise ValueError("flight block duration must be positive")
    minutes = (seconds + 59) // 60
    # Revision 1 expresses the Balanced variable rate in hundredths of a
    # minor unit.  The approved USD 25/100 profile therefore bills 25 minor
    # units per seat-block-minute and reproduces the normative 669000 total.
    numerator = (flight["capacity"] * minutes
                 * profile["seat_block_minute_rate_numerator"] * 100)
    denominator = profile["seat_block_minute_rate_denominator"]
    variable = (numerator + denominator - 1) // denominator
    total = (profile["fixed_flight_cost_minor"]
             + flight["capacity"] * profile["capacity_cost_minor_per_seat"]
             + variable)
    return {
        "block_seconds": seconds,
        "billed_block_minutes": minutes,
        "fixed_cost_minor": profile["fixed_flight_cost_minor"],
        "capacity_cost_minor": (
            flight["capacity"] * profile["capacity_cost_minor_per_seat"]
        ),
        "variable_cost_minor": variable,
        "operating_cost_minor": total,
        "configuration_revision": configuration["current_revision"],
        "configuration_fingerprint": configuration["configuration_fingerprint"],
    }


def _common_checks(envelope, flight_id):
    if type(envelope) is not dict:
        return None, _reject(envelope, flight_id, "INVALID_WORLD_STATE", "world must be a dictionary")
    validation = validate_world(envelope)
    if not validation.is_valid:
        issue = validation.errors[0]
        errors = validation.errors
        if any(item.code == "missing_financial_account" for item in errors) or any(
            item.code == "invalid_ownership"
            and ("financial_accounts" in item.path or "financial_account_ids" in item.path)
            for item in errors
        ):
            code = "MISSING_FINANCIAL_ACCOUNT"
        elif any(
            item.code == "invalid_currency"
            and ("financial_accounts" in item.path or "transactions" in item.path)
            for item in errors
        ):
            code = "CURRENCY_MISMATCH"
        elif any(
            item.code == "invalid_ownership"
            and ("planned_aircraft_id" in item.path or ".aircraft." in item.path)
            for item in errors
        ):
            code = "AIRCRAFT_OWNERSHIP_MISMATCH"
        elif any(
            "settlement_configuration_fingerprint" in item.code
            for item in errors
        ):
            code = "INCONSISTENT_SETTLEMENT_CONFIGURATION_FINGERPRINT"
        elif any("settlement_configuration" in item.code for item in errors):
            code = "INVALID_SETTLEMENT_CONFIGURATION"
        elif any(
            item.path.startswith(("$.world_state.bookings", "$.world_state.itineraries", "$.world_state.booking_state"))
            for item in errors
        ):
            code = "INVALID_BOOKING_AUTHORITY"
        elif any(item.code == "invalid_inventory" for item in errors):
            code = "CAPACITY_EXCEEDED"
        else:
            code = "INVALID_WORLD_STATE"
        return None, _reject(envelope, flight_id, code, issue.message, issue.path)
    if envelope["metadata"]["save_schema_version"] != 4:
        return None, _reject(envelope, flight_id, "INVALID_WORLD_STATE", "flight fulfilment requires schema 4")
    flight = envelope["world_state"]["dated_flights"].get(flight_id)
    if type(flight) is not dict:
        return None, _reject(envelope, flight_id, "FLIGHT_NOT_FOUND", "dated flight does not exist")
    return flight, None


def _departure(envelope, flight_id, *, resolve_event, expected_operation_revision=None,
               expected_booking_revision=None, expected_inventory_revision=None,
               expected_event_order_cursor=None, expected_configuration_revision=None,
               expected_configuration_fingerprint=None):
    flight, rejection = _common_checks(envelope, flight_id)
    if rejection:
        return rejection
    world = envelope["world_state"]
    if flight["status"] == "OPERATIONALLY_LOCKED":
        operation = world["active_aircraft_operations"].get(flight_id)
        if type(operation) is dict and operation.get("contract") == FLIGHT_FULFILMENT_OPERATION_CONTRACT:
            return FlightFulfilmentResult(
                "COMPLETED", flight_id, True,
                event_id=operation["departure_event_id"],
                completion_event_id=operation["completion_event_id"],
                manifest=build_confirmed_carriage_manifest(envelope, flight_id),
            )
    if flight["status"] != "PLANNED":
        return _reject(envelope, flight_id, "INVALID_FLIGHT_STATUS", "departure requires PLANNED status")
    if envelope["simulation"]["time_utc"] != flight["scheduled_off_block_utc"]:
        return _reject(envelope, flight_id, "INVALID_LIFECYCLE_EVENT", "departure must execute at scheduled off-block time")
    configuration, _revision = _configuration(envelope)
    witnesses = (
        (expected_operation_revision, flight["operation_revision"], "STALE_OPERATION_REVISION"),
        (expected_booking_revision, world["booking_state"]["booking_revision"], "STALE_BOOKING_REVISION"),
        (expected_inventory_revision, flight["inventory_revision"], "STALE_INVENTORY_REVISION"),
        (expected_event_order_cursor, envelope["simulation"]["event_order_cursor"], "STALE_EVENT_ORDER_CURSOR"),
        (expected_configuration_revision, configuration["current_revision"], "STALE_SETTLEMENT_CONFIGURATION"),
        (expected_configuration_fingerprint, configuration["configuration_fingerprint"], "STALE_SETTLEMENT_CONFIGURATION"),
    )
    for expected, actual, code in witnesses:
        if expected is not None and expected != actual:
            return _reject(envelope, flight_id, code, f"expected witness {expected!r} does not match {actual!r}", status="STALE_REVISION")
    event = _matching_event(envelope, flight, FLIGHT_DEPARTURE_EVENT_TYPE,
                            FLIGHT_DEPARTURE_EVENT_CONTRACT, flight["scheduled_off_block_utc"])
    if event is None:
        return _reject(envelope, flight_id, "INVALID_LIFECYCLE_EVENT", "exact departure event is missing")
    next_event = _next_event(envelope)
    if next_event is None or next_event["event_id"] != event["event_id"]:
        return _reject(envelope, flight_id, "EVENT_NOT_NEXT", "departure event is not the next canonical pending event")
    aircraft = world["aircraft"][flight["planned_aircraft_id"]]
    if aircraft["airline_id"] != flight["airline_id"]:
        return _reject(envelope, flight_id, "AIRCRAFT_OWNERSHIP_MISMATCH", "aircraft belongs to another airline")
    if aircraft.get("status") != "PARKED" or aircraft.get("current_airport_id") != flight["origin_airport_id"]:
        return _reject(envelope, flight_id, "AIRCRAFT_UNAVAILABLE", "aircraft must be parked at the origin")
    manifest = build_confirmed_carriage_manifest(envelope, flight_id)
    if not manifest.succeeded:
        issue = manifest.issues[0]
        return _reject(envelope, flight_id, issue.code, issue.message, issue.path)
    try:
        candidate = deepcopy(envelope)
        cworld = candidate["world_state"]
        cflight = cworld["dated_flights"][flight_id]
        previous_revision = cflight["operation_revision"]
        cflight["operation_revision"] += 1
        candidate["simulation"]["operation_revisions"][flight_id] = cflight["operation_revision"]
        cflight["status"] = "OPERATIONALLY_LOCKED"
        caircraft = cworld["aircraft"][cflight["planned_aircraft_id"]]
        caircraft["current_airport_id"] = None
        caircraft["status"] = "IN_FLIGHT"
        operation = {
            "contract": FLIGHT_FULFILMENT_OPERATION_CONTRACT,
            "dated_flight_id": flight_id,
            "aircraft_id": cflight["planned_aircraft_id"],
            "state": "OPERATIONALLY_LOCKED",
            "revision": cflight["operation_revision"],
            "airline_id": cflight["airline_id"],
            "market_id": cworld["connections"][cflight["connection_id"]]["market_id"],
            "schedule_id": cflight["schedule_id"],
            "schedule_revision": cflight["schedule_revision"],
            "occurrence_key": cflight["occurrence_key"],
            "planned_aircraft_id": cflight["planned_aircraft_id"],
            "actual_aircraft_id": cflight["planned_aircraft_id"],
            "origin_airport_id": cflight["origin_airport_id"],
            "destination_airport_id": cflight["destination_airport_id"],
            "scheduled_off_block_utc": cflight["scheduled_off_block_utc"],
            "scheduled_in_block_utc": cflight["scheduled_in_block_utc"],
            "actual_departure_utc": cflight["scheduled_off_block_utc"],
            "published_capacity": cflight["capacity"],
            "source_booking_ids": list(manifest.source_booking_ids),
            "paid_booking_ids": list(manifest.paid_booking_ids),
            "zero_fare_booking_ids": list(manifest.zero_fare_booking_ids),
            "source_ticket_sale_transaction_ids": list(manifest.source_ticket_sale_transaction_ids),
            "booking_witnesses": deepcopy(list(manifest.booking_witnesses)),
            "inventory_witnesses": deepcopy(list(manifest.inventory_witnesses)),
            "booking_revision": cworld["booking_state"]["booking_revision"],
            "inventory_revision": cflight["inventory_revision"],
            "operation_revision_before": previous_revision,
            "fulfilment_configuration_revision": configuration["current_revision"],
            "fulfilment_configuration_fingerprint": configuration["configuration_fingerprint"],
            "departure_event_id": event["event_id"],
            "completion_event_id": None,
        }
        cworld["active_aircraft_operations"][flight_id] = operation
        completion_id = schedule_event(
            candidate, event_type=FLIGHT_COMPLETION_EVENT_TYPE,
            due_at_utc=cflight["scheduled_in_block_utc"], owner_type="dated_flight",
            owner_id=flight_id, operation_revision=cflight["operation_revision"],
            priority=FLIGHT_EVENT_PRIORITY,
            payload={"contract": FLIGHT_COMPLETION_EVENT_CONTRACT,
                     "dated_flight_id": flight_id, "schedule_id": cflight["schedule_id"],
                     "schedule_revision": cflight["schedule_revision"],
                     "occurrence_key": cflight["occurrence_key"]},
        )
        operation["completion_event_id"] = completion_id
        if resolve_event:
            _resolve_event(candidate, event["event_id"])
            final = validate_world(candidate)
            if not final.is_valid:
                issue = final.errors[0]
                raise ValueError(f"{issue.code}: {issue.path}: {issue.message}")
        _replace(envelope, candidate)
        return FlightFulfilmentResult(
            "COMPLETED", flight_id, False, event["event_id"], completion_id,
            manifest=deepcopy(manifest),
        )
    except Exception as exc:
        message = str(exc)
        code = "EVENT_SCHEDULING_FAILED" if "event" in message.lower() else "RESULT_VALIDATION_FAILED"
        return _reject(envelope, flight_id, code, message)


def process_flight_departure(envelope, dated_flight_id, **witnesses):
    required = {
        "expected_operation_revision", "expected_booking_revision",
        "expected_inventory_revision", "expected_event_order_cursor",
        "expected_configuration_revision",
        "expected_configuration_fingerprint",
    }
    if set(witnesses) != required:
        return _reject(
            envelope, dated_flight_id, "INVALID_LIFECYCLE_EVENT",
            f"departure witnesses must be exactly {sorted(required)}",
        )
    if not _witnesses_are_well_formed(witnesses):
        return _reject(
            envelope, dated_flight_id, "INVALID_LIFECYCLE_EVENT",
            "departure witnesses must use canonical non-negative revisions and fingerprint",
        )
    try:
        return _departure(
            envelope, dated_flight_id, resolve_event=True, **witnesses
        )
    except Exception as exc:
        return _reject(
            envelope, dated_flight_id, "INVALID_LIFECYCLE_EVENT", str(exc)
        )


def _account_ids(world, airline_id):
    airline = world["airlines"][airline_id]
    accounts = {}
    for account_id in airline["financial_account_ids"]:
        account = world["financial_accounts"].get(account_id)
        if type(account) is dict and account.get("airline_id") == airline_id:
            accounts[account.get("code")] = account_id
    required = {"cash", "unflown_tickets", "passenger_revenue", "operating_expenses"}
    if not required <= set(accounts):
        raise ValueError("MISSING_FINANCIAL_ACCOUNT")
    for code in required:
        account = world["financial_accounts"][accounts[code]]
        if account["currency"] != airline["base_currency"]:
            raise ValueError("CURRENCY_MISMATCH")
    return accounts


def _completion(envelope, flight_id, *, resolve_event, expected_operation_revision=None,
                expected_booking_revision=None, expected_inventory_revision=None,
                expected_finance_revision=None, expected_event_order_cursor=None,
                expected_configuration_revision=None,
                expected_configuration_fingerprint=None):
    flight, rejection = _common_checks(envelope, flight_id)
    if rejection:
        return rejection
    world = envelope["world_state"]
    if flight["status"] == "COMPLETED":
        result = world["flight_results"].get(flight_id)
        transaction = world["transactions"].get(
            result.get("settlement_transaction_id") if type(result) is dict else None
        )
        if type(result) is dict and type(transaction) is dict:
            return FlightFulfilmentResult(
                "COMPLETED", flight_id, True,
                event_id=result["completion_event_id"],
                settlement_transaction_id=transaction["transaction_id"],
                flight_result=deepcopy(result),
            )
        return _reject(envelope, flight_id, "SETTLEMENT_RESULT_CONFLICT", "completed flight result topology is invalid")
    if flight["status"] != "OPERATIONALLY_LOCKED":
        return _reject(envelope, flight_id, "INVALID_FLIGHT_STATUS", "completion requires OPERATIONALLY_LOCKED status")
    if envelope["simulation"]["time_utc"] != flight["scheduled_in_block_utc"]:
        return _reject(envelope, flight_id, "INVALID_LIFECYCLE_EVENT", "completion must execute at scheduled in-block time")
    operation = world["active_aircraft_operations"].get(flight_id)
    if type(operation) is not dict or operation.get("contract") != FLIGHT_FULFILMENT_OPERATION_CONTRACT:
        return _reject(envelope, flight_id, "FLIGHT_NOT_OPERABLE", "matching frozen operation is missing")
    configuration, _revision = _configuration(envelope)
    airline = world["airlines"][flight["airline_id"]]
    witnesses = (
        (expected_operation_revision, flight["operation_revision"], "STALE_OPERATION_REVISION"),
        (expected_booking_revision, world["booking_state"]["booking_revision"], "STALE_BOOKING_REVISION"),
        (expected_inventory_revision, flight["inventory_revision"], "STALE_INVENTORY_REVISION"),
        (expected_finance_revision, airline["finance_revision"], "STALE_FINANCE_REVISION"),
        (expected_event_order_cursor, envelope["simulation"]["event_order_cursor"], "STALE_EVENT_ORDER_CURSOR"),
        (expected_configuration_revision, configuration["current_revision"], "STALE_SETTLEMENT_CONFIGURATION"),
        (expected_configuration_fingerprint, configuration["configuration_fingerprint"], "STALE_SETTLEMENT_CONFIGURATION"),
    )
    for expected, actual, code in witnesses:
        if expected is not None and expected != actual:
            return _reject(envelope, flight_id, code, f"expected witness {expected!r} does not match {actual!r}", status="STALE_REVISION")
    if (operation["fulfilment_configuration_revision"] != configuration["current_revision"]
            or operation["fulfilment_configuration_fingerprint"] != configuration["configuration_fingerprint"]):
        return _reject(envelope, flight_id, "STALE_SETTLEMENT_CONFIGURATION", "operation pins a different fulfilment configuration")
    event = _matching_event(envelope, flight, FLIGHT_COMPLETION_EVENT_TYPE,
                            FLIGHT_COMPLETION_EVENT_CONTRACT, flight["scheduled_in_block_utc"])
    if event is None or event["event_id"] != operation["completion_event_id"]:
        return _reject(envelope, flight_id, "INVALID_LIFECYCLE_EVENT", "exact completion event is missing")
    next_event = _next_event(envelope)
    if next_event is None or next_event["event_id"] != event["event_id"]:
        return _reject(envelope, flight_id, "EVENT_NOT_NEXT", "completion event is not the next canonical pending event")
    manifest = build_confirmed_carriage_manifest(envelope, flight_id)
    if not manifest.succeeded:
        issue = manifest.issues[0]
        return _reject(envelope, flight_id, issue.code, issue.message, issue.path)
    frozen = manifest.as_dict()
    for key in ("source_booking_ids", "paid_booking_ids", "zero_fare_booking_ids",
                "source_ticket_sale_transaction_ids", "booking_witnesses", "inventory_witnesses"):
        if operation[key] != frozen[key]:
            return _reject(envelope, flight_id, "INVALID_BOOKING_AUTHORITY", "frozen manifest was corrupted or substituted")
    try:
        candidate = deepcopy(envelope)
        cworld = candidate["world_state"]
        cflight = cworld["dated_flights"][flight_id]
        coperation = cworld["active_aircraft_operations"][flight_id]
        cairline = cworld["airlines"][cflight["airline_id"]]
        accounts = _account_ids(cworld, cflight["airline_id"])
        revenue = manifest.recognized_revenue_minor
        liability = cworld["financial_accounts"][accounts["unflown_tickets"]]
        if liability["balance_minor"] < revenue:
            raise ValueError("INSUFFICIENT_UNFLOWN_TICKET_LIABILITY")
        cost = calculate_operating_cost(candidate, cflight)
        transaction_id = allocate_id(candidate, "transaction")
        entries = []
        if revenue:
            entries.extend([
                {"account_id": accounts["unflown_tickets"], "amount_minor": revenue},
                {"account_id": accounts["passenger_revenue"], "amount_minor": -revenue},
            ])
        entries.extend([
            {"account_id": accounts["operating_expenses"], "amount_minor": cost["operating_cost_minor"]},
            {"account_id": accounts["cash"], "amount_minor": -cost["operating_cost_minor"]},
        ])
        cworld["transactions"][transaction_id] = {
            "transaction_id": transaction_id,
            "airline_id": cflight["airline_id"],
            "occurred_at_utc": cflight["scheduled_in_block_utc"],
            "description": "Stage 1 flight fulfilment settlement",
            "source_type": "FLIGHT_FULFILMENT",
            "source_id": flight_id,
            "source_booking_ids": list(manifest.paid_booking_ids),
            "source_ticket_sale_transaction_ids": list(manifest.source_ticket_sale_transaction_ids),
            "currency": manifest.currency,
            "entries": entries,
        }
        liability["balance_minor"] -= revenue
        cworld["financial_accounts"][accounts["passenger_revenue"]]["balance_minor"] += revenue
        cworld["financial_accounts"][accounts["operating_expenses"]]["balance_minor"] += cost["operating_cost_minor"]
        cworld["financial_accounts"][accounts["cash"]]["balance_minor"] -= cost["operating_cost_minor"]
        finance_before = cairline["finance_revision"]
        cairline["finance_revision"] += 1
        operation_before = cflight["operation_revision"]
        cflight["operation_revision"] += 1
        candidate["simulation"]["operation_revisions"][flight_id] = cflight["operation_revision"]
        cflight["status"] = "COMPLETED"
        aircraft = cworld["aircraft"][coperation["actual_aircraft_id"]]
        aircraft["current_airport_id"] = cflight["destination_airport_id"]
        aircraft["status"] = "PARKED"
        result = {
            "contract": FLIGHT_RESULT_CONTRACT,
            "result_version": FLIGHT_RESULT_VERSION,
            "dated_flight_id": flight_id,
            "airline_id": cflight["airline_id"],
            "market_id": coperation["market_id"],
            "schedule_id": cflight["schedule_id"],
            "schedule_revision": cflight["schedule_revision"],
            "occurrence_key": cflight["occurrence_key"],
            "planned_aircraft_id": cflight["planned_aircraft_id"],
            "actual_aircraft_id": coperation["actual_aircraft_id"],
            "origin_airport_id": cflight["origin_airport_id"],
            "destination_airport_id": cflight["destination_airport_id"],
            "scheduled_off_block_utc": cflight["scheduled_off_block_utc"],
            "scheduled_in_block_utc": cflight["scheduled_in_block_utc"],
            "actual_departure_utc": cflight["scheduled_off_block_utc"],
            "actual_arrival_utc": cflight["scheduled_in_block_utc"],
            "completed_at_utc": cflight["scheduled_in_block_utc"],
            "published_capacity": cflight["capacity"],
            "carried_passenger_count": manifest.carried_passenger_count,
            "paid_passenger_count": manifest.paid_passenger_count,
            "zero_fare_passenger_count": manifest.zero_fare_passenger_count,
            "source_booking_ids": list(manifest.source_booking_ids),
            "paid_booking_ids": list(manifest.paid_booking_ids),
            "zero_fare_booking_ids": list(manifest.zero_fare_booking_ids),
            "source_ticket_sale_transaction_ids": list(manifest.source_ticket_sale_transaction_ids),
            "settlement_transaction_id": transaction_id,
            "departure_event_id": coperation["departure_event_id"],
            "completion_event_id": event["event_id"],
            "recognized_revenue_minor": revenue,
            "operating_cost_minor": cost["operating_cost_minor"],
            "currency": manifest.currency,
            "booking_witnesses": deepcopy(list(manifest.booking_witnesses)),
            "inventory_witnesses": deepcopy(list(manifest.inventory_witnesses)),
            "finance_revision_before": finance_before,
            "finance_revision_after": cairline["finance_revision"],
            "operation_revision_before": operation_before,
            "operation_revision_after": cflight["operation_revision"],
            "fulfilment_configuration_revision": configuration["current_revision"],
            "fulfilment_configuration_fingerprint": configuration["configuration_fingerprint"],
        }
        cworld["flight_results"][flight_id] = result
        del cworld["active_aircraft_operations"][flight_id]
        if resolve_event:
            _resolve_event(candidate, event["event_id"])
            final = validate_world(candidate)
            if not final.is_valid:
                issue = final.errors[0]
                raise ValueError(f"{issue.code}: {issue.path}: {issue.message}")
        _replace(envelope, candidate)
        return FlightFulfilmentResult(
            "COMPLETED", flight_id, False, event["event_id"],
            settlement_transaction_id=transaction_id,
            flight_result=deepcopy(result), manifest=deepcopy(manifest),
        )
    except Exception as exc:
        message = str(exc)
        known = ("INSUFFICIENT_UNFLOWN_TICKET_LIABILITY", "MISSING_FINANCIAL_ACCOUNT", "CURRENCY_MISMATCH")
        code = next((value for value in known if value in message), None)
        if code is None:
            code = "ID_ALLOCATION_FAILED" if "allocator" in message.lower() or "collision" in message.lower() else "FINANCIAL_POSTING_FAILED"
        return _reject(envelope, flight_id, code, message)


def process_flight_completion(envelope, dated_flight_id, **witnesses):
    required = {
        "expected_operation_revision", "expected_booking_revision",
        "expected_inventory_revision", "expected_finance_revision",
        "expected_event_order_cursor", "expected_configuration_revision",
        "expected_configuration_fingerprint",
    }
    if set(witnesses) != required:
        return _reject(
            envelope, dated_flight_id, "INVALID_LIFECYCLE_EVENT",
            f"completion witnesses must be exactly {sorted(required)}",
        )
    if not _witnesses_are_well_formed(witnesses):
        return _reject(
            envelope, dated_flight_id, "INVALID_LIFECYCLE_EVENT",
            "completion witnesses must use canonical non-negative revisions and fingerprint",
        )
    try:
        return _completion(
            envelope, dated_flight_id, resolve_event=True, **witnesses
        )
    except Exception as exc:
        return _reject(
            envelope, dated_flight_id, "INVALID_LIFECYCLE_EVENT", str(exc)
        )


def _departure_handler(context):
    flight_id = context.payload.get("dated_flight_id") if type(context.payload) is dict else None
    result = _departure(context.envelope, flight_id, resolve_event=False)
    if not result.succeeded:
        raise ValueError(result.issues[0].message)


def _completion_handler(context):
    flight_id = context.payload.get("dated_flight_id") if type(context.payload) is dict else None
    result = _completion(context.envelope, flight_id, resolve_event=False)
    if not result.succeeded:
        raise ValueError(result.issues[0].message)


DEFAULT_EVENT_HANDLERS.register(FLIGHT_DEPARTURE_EVENT_TYPE, _departure_handler)
DEFAULT_EVENT_HANDLERS.register(FLIGHT_COMPLETION_EVENT_TYPE, _completion_handler)


__all__ = (
    "FlightFulfilmentIssue", "FlightFulfilmentResult", "FlightManifest",
    "build_confirmed_carriage_manifest", "process_flight_completion",
    "process_flight_departure",
)
