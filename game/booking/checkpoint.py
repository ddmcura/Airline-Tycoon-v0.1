"""Milestone 5D atomic daily Booking checkpoint persistence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta

from game.simulation.kernel import DEFAULT_EVENT_HANDLERS, schedule_event
from game.world_state.ids import allocate_id
from game.world_state.schema import (
    AGGREGATE_BOOKING_CONTRACT,
    BOOKING_CHOICE_POLICY_CONTRACT,
    DIRECT_ECONOMY_ITINERARY_CONTRACT,
)
from game.world_state.validation import validate_world

from .allocation import prepare_daily_booking_allocation


BOOKING_CHECKPOINT_EVENT_TYPE = "DAILY_BOOKING_CHECKPOINT"
BOOKING_CHECKPOINT_EVENT_PRIORITY = 0


@dataclass(frozen=True)
class BookingCheckpointIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class BookingCheckpointDesiredDateResult:
    desired_travel_date: str
    requested_passengers: int
    booked_passengers: int
    outside_option_passengers: int
    insufficient_capacity_passengers: int
    no_eligible_service_passengers: int
    no_departure_on_desired_date_passengers: int
    booking_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BookingCheckpointMarketResult:
    market_id: str
    cohort_key: str
    requested_passengers: int
    booked_passengers: int
    outside_option_passengers: int
    insufficient_capacity_passengers: int
    no_eligible_service_passengers: int
    no_departure_on_desired_date_passengers: int
    booking_ids: tuple[str, ...] = ()
    desired_date_results: tuple[BookingCheckpointDesiredDateResult, ...] = ()


@dataclass(frozen=True)
class BookingCheckpointResult:
    status: str
    checkpoint_id: str | None
    checkpoint_date: str
    previous_booking_revision: int
    resulting_booking_revision: int
    reused: bool = False
    requested_passengers: int = 0
    booked_passengers: int = 0
    unsuccessful_passengers: int = 0
    booking_ids: tuple[str, ...] = ()
    itinerary_ids: tuple[str, ...] = ()
    transaction_ids: tuple[str, ...] = ()
    next_event_id: str | None = None
    next_event_due_at_utc: str | None = None
    market_results: tuple[BookingCheckpointMarketResult, ...] = ()
    issues: tuple[BookingCheckpointIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _message(exc):
    try:
        value = str(exc)
    except Exception:
        value = type(exc).__name__
    return value if type(value) is str else type(exc).__name__


def _observed(envelope):
    try:
        state = envelope["world_state"]["booking_state"]
        return envelope["simulation"]["time_utc"][:10], state["booking_revision"]
    except Exception:
        return "", 0


def _reject(envelope, code, message, path=None, *, status="REJECTED"):
    checkpoint_date, revision = _observed(envelope)
    return BookingCheckpointResult(
        status, None, checkpoint_date, revision, revision,
        issues=(BookingCheckpointIssue(code, message, path),),
    )


def _replace(target, candidate):
    committed = deepcopy(candidate)
    target.clear()
    target.update(committed)


def _exact_revision_map(value, name):
    if type(value) is not dict:
        raise TypeError(f"{name} must be a dictionary")
    if any(type(key) is not str or type(revision) is not int or revision < 0
           for key, revision in value.items()):
        raise TypeError(f"{name} requires string IDs and non-negative integer revisions")
    return dict(value)


def _checkpoint_for_date(envelope, checkpoint_date):
    matches = [
        item for item in envelope["world_state"]["booking_state"]["booking_checkpoints"].values()
        if type(item) is dict and item.get("checkpoint_date") == checkpoint_date
    ]
    if len(matches) > 1:
        raise ValueError("checkpoint date is not unique")
    return matches[0] if matches else None


def _next_due(checkpoint_date):
    return f"{(date.fromisoformat(checkpoint_date) + timedelta(days=1)).isoformat()}T00:00:00Z"


def _matching_next_events(envelope, checkpoint_id, due):
    return tuple(
        event for event in envelope["world_state"]["pending_events"].values()
        if type(event) is dict
        and event.get("event_type") == BOOKING_CHECKPOINT_EVENT_TYPE
        and event.get("due_at_utc") == due
        and event.get("owner_type") == "booking_checkpoint"
        and event.get("owner_id") == checkpoint_id
        and event.get("payload") == {"checkpoint_date": due[:10]}
        and event.get("status") == "PENDING"
    )


def _booking_events_due(envelope, due):
    return tuple(
        event for event in envelope["world_state"]["pending_events"].values()
        if type(event) is dict
        and event.get("event_type") == BOOKING_CHECKPOINT_EVENT_TYPE
        and event.get("due_at_utc") == due
        and event.get("status") == "PENDING"
    )


def _future_booking_events(envelope, due):
    return tuple(
        event for event in envelope["world_state"]["pending_events"].values()
        if type(event) is dict
        and event.get("event_type") == BOOKING_CHECKPOINT_EVENT_TYPE
        and type(event.get("due_at_utc")) is str
        and event.get("due_at_utc") >= due
        and event.get("status") == "PENDING"
    )


def _market_result_from_record(record):
    desired = tuple(
        BookingCheckpointDesiredDateResult(
            item["desired_travel_date"], item["requested_passenger_count"],
            item["booked_passenger_count"], item["outside_option_passenger_count"],
            item["insufficient_capacity_passenger_count"],
            item["no_eligible_service_passenger_count"],
            item["no_departure_on_desired_date_passenger_count"],
            tuple(item["booking_ids"]),
        )
        for _key, item in sorted(record.get("desired_date_results", {}).items())
    )
    return BookingCheckpointMarketResult(
        record["market_id"], record["cohort_key"],
        record["desired_passenger_count"], record["booked_passenger_count"],
        record["outside_option_passenger_count"],
        record.get("insufficient_capacity_passenger_count", 0),
        record.get("no_eligible_service_passenger_count", 0),
        record.get("no_departure_on_desired_date_passenger_count", 0),
        tuple(record["booking_ids"]), desired,
    )


def _result_from_checkpoint(envelope, checkpoint, *, reused):
    market_results = tuple(
        _market_result_from_record(item)
        for _market_id, item in sorted(checkpoint["market_results"].items())
    )
    booking_ids = tuple(
        booking_id for item in market_results for booking_id in item.booking_ids
    )
    itinerary_ids = tuple(
        envelope["world_state"]["bookings"][booking_id]["itinerary_id"]
        for booking_id in booking_ids
    )
    requested = sum(item.requested_passengers for item in market_results)
    booked = sum(item.booked_passengers for item in market_results)
    due = _next_due(checkpoint["checkpoint_date"])
    next_events = _matching_next_events(
        envelope, checkpoint["booking_checkpoint_id"], due
    )
    if len(next_events) != 1 or len(_future_booking_events(envelope, due)) != 1:
        raise ValueError("completed checkpoint must own exactly one next daily event")
    return BookingCheckpointResult(
        "COMPLETED", checkpoint["booking_checkpoint_id"], checkpoint["checkpoint_date"],
        checkpoint["booking_revision"] - 1, checkpoint["booking_revision"], reused,
        requested, booked, requested - booked, booking_ids, itinerary_ids,
        tuple(checkpoint["financial_transaction_ids"]), next_events[0]["event_id"], due,
        market_results,
    )


def _account_ids(world, airline_id):
    airline = world["airlines"][airline_id]
    accounts = {
        world["financial_accounts"][account_id]["code"]: account_id
        for account_id in airline["financial_account_ids"]
    }
    for code, category in (("cash", "CASH"), ("unflown_tickets", "LIABILITY")):
        account_id = accounts.get(code)
        account = world["financial_accounts"].get(account_id)
        if (type(account) is not dict or account.get("airline_id") != airline_id
                or account.get("category") != category
                or account.get("currency") != airline["base_currency"]):
            raise ValueError(f"invalid {code} account for {airline_id}")
    return accounts["cash"], accounts["unflown_tickets"]


def _canonical_batches(plan, world):
    rows = []
    for market in plan.market_results:
        for group in market.desired_date_results:
            for selected in group.selected_offer_allocations:
                rows.append((
                    market.market_id, group.desired_travel_date,
                    selected.dated_flight_id, selected.airline_id,
                    selected.selected_passengers, market.cohort_key,
                ))
    return tuple(sorted(rows, key=lambda row: (
        row[0], row[1], world["dated_flights"][row[2]]["scheduled_off_block_utc"],
        row[2], row[3]
    )))


def process_daily_booking_checkpoint(
    envelope, *, expected_booking_revision, expected_demand_revision,
    expected_market_pack_revision, expected_booking_configuration_revision,
    expected_booking_configuration_fingerprint, expected_inventory_revisions,
    expected_finance_revisions, expected_event_order_cursor,
    multipliers_by_market=None, demand_indexes=None, activation_providers=None,
    dated_flight_indexes=None,
):
    """Atomically persist the current UTC date's complete Booking outcome."""
    try:
        validation = validate_world(envelope)
    except Exception as exc:
        return _reject(envelope, "INVALID_WORLD_STATE", _message(exc))
    if not validation.is_valid:
        issue = validation.errors[0]
        return _reject(envelope, "INVALID_WORLD_STATE", issue.message, issue.path)
    if envelope["metadata"]["save_schema_version"] not in (3, 4):
        return _reject(envelope, "INVALID_WORLD_STATE", "Booking checkpoints require schema 3")
    checkpoint_date = envelope["simulation"]["time_utc"][:10]
    try:
        existing = _checkpoint_for_date(envelope, checkpoint_date)
        if existing is not None:
            if existing.get("status") != "COMPLETED":
                return _reject(envelope, "INVALID_BOOKING_CHECKPOINT", "existing checkpoint is not complete")
            return deepcopy(_result_from_checkpoint(envelope, existing, reused=True))
    except Exception as exc:
        return _reject(envelope, "INVALID_BOOKING_CHECKPOINT", _message(exc))

    configuration = envelope["simulation"]["configuration"]["booking"]
    observed = (
        envelope["world_state"]["booking_state"]["booking_revision"],
        envelope["world_state"]["demand_state"]["demand_model_revision"],
        envelope["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"],
        configuration["revision"], envelope["simulation"]["event_order_cursor"],
    )
    expected = (expected_booking_revision, expected_demand_revision,
                expected_market_pack_revision, expected_booking_configuration_revision,
                expected_event_order_cursor)
    if any(type(value) is not int or value < 0 for value in expected):
        return _reject(envelope, "STALE_REVISION", "expected revisions must be non-negative integers", status="STALE_REVISION")
    if expected != observed:
        return _reject(envelope, "STALE_REVISION", "an expected revision does not match", status="STALE_REVISION")
    if type(expected_booking_configuration_fingerprint) is not str or expected_booking_configuration_fingerprint != configuration["configuration_fingerprint"]:
        return _reject(envelope, "INCONSISTENT_BOOKING_CONFIGURATION_FINGERPRINT", "expected Booking configuration fingerprint does not match")
    if configuration.get("revision") != 2 or configuration.get("choice_policy", {}).get("contract") != BOOKING_CHOICE_POLICY_CONTRACT:
        return _reject(envelope, "INVALID_BOOKING_CONFIGURATION", "Booking persistence requires explicit production revision 2")
    try:
        inventory_expectations = _exact_revision_map(expected_inventory_revisions, "expected_inventory_revisions")
        finance_expectations = _exact_revision_map(expected_finance_revisions, "expected_finance_revisions")
        candidate = deepcopy(envelope)
        checkpoint_id = allocate_id(candidate, "booking_checkpoint")
        candidate["world_state"]["booking_state"]["booking_checkpoints"][checkpoint_id] = {
            "booking_checkpoint_id": checkpoint_id, "checkpoint_date": checkpoint_date,
            "due_at_utc": f"{checkpoint_date}T00:00:00Z", "status": "PENDING",
            "processed_at_utc": None, "booking_revision": expected_booking_revision,
            "booking_configuration_revision": configuration["revision"],
            "booking_configuration_fingerprint": configuration["configuration_fingerprint"],
            "demand_model_revision": expected_demand_revision,
            "market_pack_revision": expected_market_pack_revision,
            "market_results": {}, "financial_transaction_ids": [],
        }
        plan = prepare_daily_booking_allocation(
            candidate,
            expected_demand_revision=expected_demand_revision,
            expected_market_pack_revision=expected_market_pack_revision,
            expected_booking_configuration_revision=expected_booking_configuration_revision,
            expected_booking_configuration_fingerprint=expected_booking_configuration_fingerprint,
            expected_inventory_revisions=inventory_expectations,
            multipliers_by_market=multipliers_by_market, demand_indexes=demand_indexes,
            activation_providers=activation_providers,
            dated_flight_indexes=dated_flight_indexes,
        )
        if not plan.succeeded:
            issue = plan.issues[0]
            return _reject(envelope, issue.code, issue.message, issue.path, status=plan.status)
        world = candidate["world_state"]
        candidate_configuration = candidate["simulation"]["configuration"]["booking"]
        if (
            world["demand_state"]["demand_model_revision"] != expected_demand_revision
            or candidate["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"] != expected_market_pack_revision
            or candidate_configuration["revision"] != expected_booking_configuration_revision
            or candidate_configuration["configuration_fingerprint"] != expected_booking_configuration_fingerprint
        ):
            raise RuntimeError("late demand, pack, or Booking configuration change")
        if world["booking_state"]["booking_revision"] != expected_booking_revision:
            raise RuntimeError("late Booking revision change")
        observed_inventory = {item.dated_flight_id: item.observed_inventory_revision for item in plan.observed_inventory_revisions}
        if observed_inventory != inventory_expectations:
            raise RuntimeError("allocation inventory witness changed")
        rows = _canonical_batches(plan, world)
        identifiers = []
        for row in rows:
            flight = world["dated_flights"][row[2]]
            identifiers.append((row, allocate_id(candidate, "itinerary"), allocate_id(candidate, "booking"), flight))
        gross_by_airline = {}
        paid_booking_ids_by_airline = {}
        for row, _itinerary_id, booking_id, flight in identifiers:
            if flight["fare_offer"]["currency"] != world["airlines"][row[3]]["base_currency"]:
                raise ValueError(
                    f"fare currency must match base currency for {row[3]}"
                )
            total = row[4] * flight["fare_offer"]["amount_minor"]
            if total:
                gross_by_airline[row[3]] = gross_by_airline.get(row[3], 0) + total
                paid_booking_ids_by_airline.setdefault(row[3], []).append(booking_id)
        if set(finance_expectations) != set(gross_by_airline):
            return _reject(envelope, "INVALID_FINANCE_REVISION", "expected_finance_revisions must contain exactly paid affected airlines")
        for airline_id in sorted(gross_by_airline):
            if world["airlines"][airline_id]["finance_revision"] != finance_expectations[airline_id]:
                return _reject(envelope, "STALE_REVISION", f"stale finance revision for {airline_id}", status="STALE_REVISION")
        transaction_by_airline = {
            airline_id: allocate_id(candidate, "transaction")
            for airline_id in sorted(gross_by_airline)
        }
        affected_flights = {row[2] for row in rows}
        selected_by_flight = {}
        for row in rows:
            selected_by_flight[row[2]] = selected_by_flight.get(row[2], 0) + row[4]
        existing_booked = {}
        for booking in world["bookings"].values():
            if type(booking) is dict and booking.get("contract") == AGGREGATE_BOOKING_CONTRACT and booking.get("status") == "CONFIRMED":
                itinerary = world["itineraries"].get(booking.get("itinerary_id"), {})
                for flight_id in itinerary.get("dated_flight_ids", []):
                    existing_booked[flight_id] = existing_booked.get(flight_id, 0) + booking["passenger_count"]
        for flight_id in sorted(affected_flights):
            flight = world["dated_flights"][flight_id]
            if flight["inventory_revision"] != inventory_expectations[flight_id]:
                raise RuntimeError(f"late inventory revision change for {flight_id}")
            if existing_booked.get(flight_id, 0) + selected_by_flight[flight_id] > flight["capacity"]:
                raise ValueError(f"capacity exceeded for {flight_id}")
            flight["inventory_revision"] += 1
        resulting_revision = expected_booking_revision + 1
        booking_ids_by_market_date = {}
        for row, itinerary_id, booking_id, flight in identifiers:
            market_id, desired_date, flight_id, airline_id, passengers, cohort_key = row
            fare = deepcopy(flight["fare_offer"])
            world["itineraries"][itinerary_id] = {
                "itinerary_id": itinerary_id, "contract": DIRECT_ECONOMY_ITINERARY_CONTRACT,
                "market_id": market_id, "airline_id": airline_id,
                "origin_airport_id": flight["origin_airport_id"],
                "destination_airport_id": flight["destination_airport_id"],
                "dated_flight_ids": [flight_id],
                "scheduled_departure_utc": flight["scheduled_off_block_utc"],
                "scheduled_arrival_utc": flight["scheduled_in_block_utc"],
                "cabin": "ECONOMY", "fare_offer_snapshot": fare,
                "schedule_lineage": {"schedule_id": flight["schedule_id"], "schedule_revision": flight["schedule_revision"], "occurrence_key": flight["occurrence_key"]},
                "status": "CONFIRMED",
            }
            total = passengers * fare["amount_minor"]
            world["bookings"][booking_id] = {
                "booking_id": booking_id, "contract": AGGREGATE_BOOKING_CONTRACT,
                "booking_checkpoint_id": checkpoint_id, "cohort_key": cohort_key,
                "desired_travel_date": desired_date, "airline_id": airline_id,
                "itinerary_id": itinerary_id, "passenger_count": passengers,
                "booked_at_utc": candidate["simulation"]["time_utc"],
                "total_fare_minor": total, "currency": fare["currency"],
                "inventory_revision_at_commit": world["dated_flights"][flight_id]["inventory_revision"],
                "finance_transaction_id": transaction_by_airline.get(airline_id) if total else None,
                "booking_revision": resulting_revision, "status": "CONFIRMED",
            }
            booking_ids_by_market_date.setdefault((market_id, desired_date), []).append(booking_id)
        transaction_ids = []
        for airline_id in sorted(gross_by_airline):
            if world["airlines"][airline_id]["finance_revision"] != finance_expectations[airline_id]:
                raise RuntimeError(f"late finance revision change for {airline_id}")
            gross = gross_by_airline[airline_id]
            transaction_id = transaction_by_airline[airline_id]
            cash_id, liability_id = _account_ids(world, airline_id)
            world["transactions"][transaction_id] = {
                "transaction_id": transaction_id, "airline_id": airline_id,
                "occurred_at_utc": candidate["simulation"]["time_utc"],
                "description": "Stage 1 Booking checkpoint ticket sales",
                "source_type": "BOOKING_CHECKPOINT", "source_id": checkpoint_id,
                "source_booking_ids": sorted(paid_booking_ids_by_airline[airline_id]),
                "currency": world["airlines"][airline_id]["base_currency"],
                "entries": [{"account_id": cash_id, "amount_minor": gross}, {"account_id": liability_id, "amount_minor": -gross}],
            }
            world["financial_accounts"][cash_id]["balance_minor"] += gross
            world["financial_accounts"][liability_id]["balance_minor"] += gross
            world["airlines"][airline_id]["finance_revision"] += 1
            transaction_ids.append(transaction_id)
        world["booking_state"]["booking_revision"] = resulting_revision
        persisted_markets = {}
        returned_markets = []
        for market in plan.market_results:
            desired_records = {}
            market_booking_ids = []
            returned_dates = []
            for group in market.desired_date_results:
                ids = sorted(booking_ids_by_market_date.get((market.market_id, group.desired_travel_date), []))
                market_booking_ids.extend(ids)
                desired_records[group.desired_travel_date] = {
                    "desired_travel_date": group.desired_travel_date,
                    "requested_passenger_count": group.requested_passengers,
                    "booked_passenger_count": group.selected_passengers,
                    "outside_option_passenger_count": group.outside_option_passengers,
                    "insufficient_capacity_passenger_count": group.insufficient_capacity_passengers,
                    "no_eligible_service_passenger_count": group.no_eligible_service_passengers,
                    "no_departure_on_desired_date_passenger_count": group.no_departure_on_desired_date_passengers,
                    "booking_ids": ids,
                }
                returned_dates.append(_market_result_from_record({
                    "market_id": market.market_id, "cohort_key": market.cohort_key,
                    "desired_passenger_count": group.requested_passengers,
                    "booked_passenger_count": group.selected_passengers,
                    "outside_option_passenger_count": group.outside_option_passengers,
                    "insufficient_capacity_passenger_count": group.insufficient_capacity_passengers,
                    "no_eligible_service_passenger_count": group.no_eligible_service_passengers,
                    "no_departure_on_desired_date_passenger_count": group.no_departure_on_desired_date_passengers,
                    "booking_ids": ids, "desired_date_results": {group.desired_travel_date: desired_records[group.desired_travel_date]},
                }).desired_date_results[0])
            record = {
                "market_id": market.market_id, "cohort_key": market.cohort_key,
                "desired_passenger_count": market.requested_passengers,
                "booked_passenger_count": market.selected_passengers,
                "outside_option_passenger_count": market.outside_option_passengers,
                "insufficient_capacity_passenger_count": market.insufficient_capacity_passengers,
                "no_eligible_service_passenger_count": market.no_eligible_service_passengers,
                "no_departure_on_desired_date_passenger_count": market.no_departure_on_desired_date_passengers,
                "booking_ids": sorted(market_booking_ids), "desired_date_results": desired_records,
            }
            persisted_markets[market.market_id] = record
            returned_markets.append(_market_result_from_record(record))
        checkpoint = world["booking_state"]["booking_checkpoints"][checkpoint_id]
        checkpoint.update({"status": "COMPLETED", "processed_at_utc": candidate["simulation"]["time_utc"],
                           "booking_revision": resulting_revision, "market_results": persisted_markets,
                           "financial_transaction_ids": sorted(transaction_ids)})
        candidate["simulation"]["operation_revisions"][checkpoint_id] = resulting_revision
        if candidate["simulation"]["event_order_cursor"] != expected_event_order_cursor:
            raise RuntimeError("late event authority change")
        due = _next_due(checkpoint_date)
        existing_next = _matching_next_events(candidate, checkpoint_id, due)
        all_next = _future_booking_events(candidate, due)
        if all_next and (len(all_next) != 1 or len(existing_next) != 1):
            raise ValueError("conflicting or duplicate next Booking checkpoint event")
        next_event_id = existing_next[0]["event_id"] if existing_next else schedule_event(
            candidate, event_type=BOOKING_CHECKPOINT_EVENT_TYPE, due_at_utc=due,
            owner_type="booking_checkpoint", owner_id=checkpoint_id,
            operation_revision=resulting_revision,
            priority=BOOKING_CHECKPOINT_EVENT_PRIORITY,
            payload={"checkpoint_date": due[:10]},
        )
        final = validate_world(candidate)
        if not final.is_valid:
            issue = final.errors[0]
            raise ValueError(f"{issue.code}: {issue.path}: {issue.message}")
        result = BookingCheckpointResult(
            "COMPLETED", checkpoint_id, checkpoint_date, expected_booking_revision,
            resulting_revision, False, plan.requested_passengers, plan.selected_passengers,
            plan.requested_passengers - plan.selected_passengers,
            tuple(booking_id for _row, _iid, booking_id, _flight in identifiers),
            tuple(itinerary_id for _row, itinerary_id, _bid, _flight in identifiers),
            tuple(sorted(transaction_ids)), next_event_id, due, tuple(returned_markets),
        )
        if result.requested_passengers != result.booked_passengers + result.unsuccessful_passengers:
            raise ValueError("checkpoint result conservation failed")
        _replace(envelope, candidate)
        return deepcopy(result)
    except Exception as exc:
        message = _message(exc)
        lowered = message.lower()
        if "finance" in lowered or "account" in lowered or "currency" in lowered:
            code = "FINANCIAL_POSTING_FAILED"
        elif "capacity" in lowered or "inventory" in lowered:
            code = "INVALID_INVENTORY"
        elif "event" in lowered:
            code = "EVENT_SCHEDULING_FAILED"
        elif "allocator" in lowered or "id allocation" in lowered or "collision" in lowered:
            code = "ID_ALLOCATION_FAILED"
        else:
            code = "RESULT_VALIDATION_FAILED"
        return _reject(envelope, code, message)


def _event_handler(context):
    payload = context.payload
    if type(payload) is not dict or payload != {"checkpoint_date": context.event["due_at_utc"][:10]}:
        raise ValueError("invalid Booking checkpoint event payload")
    envelope = context.envelope
    booking = envelope["simulation"]["configuration"]["booking"]
    existing = _checkpoint_for_date(envelope, envelope["simulation"]["time_utc"][:10])
    if type(existing) is dict and existing.get("status") == "COMPLETED":
        reused = process_daily_booking_checkpoint(
            envelope,
            expected_booking_revision=0,
            expected_demand_revision=0,
            expected_market_pack_revision=0,
            expected_booking_configuration_revision=0,
            expected_booking_configuration_fingerprint="",
            expected_inventory_revisions={},
            expected_finance_revisions={},
            expected_event_order_cursor=0,
        )
        if not reused.succeeded or not reused.reused:
            raise ValueError(
                reused.issues[0].message if reused.issues else "completed checkpoint was not reusable"
            )
        return
    # Event execution owns its concurrency snapshot.  A detached 5C probe finds
    # the exact capacity and paid-airline witness sets; the authoritative call
    # repeats the same deterministic pipeline against the untouched candidate.
    probe = deepcopy(envelope)
    from .shopping import prepare_daily_booking_shopping
    shopping = prepare_daily_booking_shopping(
        probe,
        expected_demand_revision=envelope["world_state"]["demand_state"]["demand_model_revision"],
        expected_market_pack_revision=envelope["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"],
        expected_booking_configuration_revision=booking["revision"],
        expected_booking_configuration_fingerprint=booking["configuration_fingerprint"],
    )
    if not shopping.succeeded:
        raise ValueError(shopping.issues[0].message)
    inventory = {offer.dated_flight_id: offer.observed_inventory_revision for market in shopping.market_plans for group in market.desired_date_groups for offer in group.offers}
    allocation_probe = deepcopy(envelope)
    plan = prepare_daily_booking_allocation(
        allocation_probe,
        expected_demand_revision=envelope["world_state"]["demand_state"]["demand_model_revision"],
        expected_market_pack_revision=envelope["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"],
        expected_booking_configuration_revision=booking["revision"],
        expected_booking_configuration_fingerprint=booking["configuration_fingerprint"],
        expected_inventory_revisions=inventory,
    )
    if not plan.succeeded:
        raise ValueError(plan.issues[0].message)
    paid = set()
    for market in plan.market_results:
        for group in market.desired_date_results:
            for selected in group.selected_offer_allocations:
                if envelope["world_state"]["dated_flights"][selected.dated_flight_id]["fare_offer"]["amount_minor"]:
                    paid.add(selected.airline_id)
    result = process_daily_booking_checkpoint(
        envelope,
        expected_booking_revision=envelope["world_state"]["booking_state"]["booking_revision"],
        expected_demand_revision=envelope["world_state"]["demand_state"]["demand_model_revision"],
        expected_market_pack_revision=envelope["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"],
        expected_booking_configuration_revision=booking["revision"],
        expected_booking_configuration_fingerprint=booking["configuration_fingerprint"],
        expected_inventory_revisions=inventory,
        expected_finance_revisions={airline_id: envelope["world_state"]["airlines"][airline_id]["finance_revision"] for airline_id in sorted(paid)},
        expected_event_order_cursor=envelope["simulation"]["event_order_cursor"],
    )
    if not result.succeeded:
        raise ValueError(result.issues[0].message)


DEFAULT_EVENT_HANDLERS.register(BOOKING_CHECKPOINT_EVENT_TYPE, _event_handler)


__all__ = (
    "BOOKING_CHECKPOINT_EVENT_TYPE", "BookingCheckpointDesiredDateResult",
    "BookingCheckpointIssue", "BookingCheckpointMarketResult",
    "BookingCheckpointResult", "process_daily_booking_checkpoint",
)
