"""Atomic Stage 1 weekly outbound-and-return scheduling workflow."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta

from game.world_state.construction import add_connection
from game.world_state.validation import validate_world

from .publication import create_schedule_definition, publish_occurrences_through


@dataclass(frozen=True)
class RotationIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class RotationResult:
    status: str
    schedule_ids: tuple[str, ...] = ()
    dated_flight_ids: tuple[str, ...] = ()
    connection_ids: tuple[str, ...] = ()
    first_operating_date: str | None = None
    issues: tuple[RotationIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _rejected(code, message, path=None, *, status="REJECTED"):
    return RotationResult(status, issues=(RotationIssue(code, message, path),))


def _canonical_date(value):
    if not isinstance(value, str):
        raise ValueError("first_operating_date must be canonical YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("first_operating_date must be canonical YYYY-MM-DD")
    return parsed


def _airport_code_map(world):
    return {
        airport["reference_code"]: airport_id
        for airport_id, airport in world["airports"].items()
    }


def _connection(candidate, airline_id, origin_id, destination_id):
    world = candidate["world_state"]
    market = next(
        (
            item for _market_id, item in sorted(world["directional_markets"].items())
            if item["origin_airport_id"] == origin_id
            and item["destination_airport_id"] == destination_id
        ),
        None,
    )
    if market is None:
        raise ValueError("MISSING_MARKET: directional market is unavailable")
    existing = next(
        (
            item for _connection_id, item in sorted(world["connections"].items())
            if item["airline_id"] == airline_id and item["market_id"] == market["market_id"]
        ),
        None,
    )
    if existing is not None:
        if existing["status"] != "ACTIVE":
            raise ValueError("INACTIVE_CONNECTION: existing connection is not active")
        return existing["connection_id"]
    return add_connection(candidate, airline_id, market["market_id"], status="ACTIVE")


def create_weekly_round_trip_rotation(
    envelope, *, airline_id, aircraft_id, destination_airport_reference_code,
    fare_minor, first_operating_date,
):
    """Create two weekly definitions and publish only their first occurrences."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        issue = validation.errors[0]
        return _rejected("INVALID_WORLD_STATE", issue.message, issue.path)
    try:
        operating_date = _canonical_date(first_operating_date)
    except (TypeError, ValueError) as exc:
        return _rejected("INVALID_DATE", str(exc))
    if isinstance(fare_minor, bool) or not isinstance(fare_minor, int) or fare_minor < 0:
        return _rejected("INVALID_FARE", "fare_minor must be a non-negative integer")
    world = envelope["world_state"]
    airline = world["airlines"].get(airline_id)
    aircraft = world["aircraft"].get(aircraft_id)
    if type(airline) is not dict or type(aircraft) is not dict:
        return _rejected("MISSING_ENTITY", "airline and aircraft must exist")
    if aircraft["airline_id"] != airline_id:
        return _rejected("WRONG_OWNERSHIP", "aircraft is not owned by the airline")
    if aircraft["status"] != "PARKED" or aircraft["current_airport_id"] is None:
        return _rejected("AIRCRAFT_NOT_PARKED", "aircraft must be parked at an airport")
    code = (
        destination_airport_reference_code.strip().upper()
        if isinstance(destination_airport_reference_code, str) else ""
    )
    code_map = _airport_code_map(world)
    destination_id = code_map.get(code)
    origin_id = aircraft["current_airport_id"]
    if destination_id is None:
        return _rejected("INVALID_DESTINATION", "destination airport is unavailable")
    if destination_id == origin_id:
        return _rejected("SAME_ENDPOINT", "origin and destination must differ")
    if airline["base_currency"] != "USD":
        return _rejected("INCONSISTENT_CURRENCY", "Stage 1 rotations require USD authority")

    candidate = deepcopy(envelope)
    try:
        outbound_connection = _connection(candidate, airline_id, origin_id, destination_id)
        return_connection = _connection(candidate, airline_id, destination_id, origin_id)
        weekday = operating_date.weekday()
        common = {
            "airline_id": airline_id,
            "planned_aircraft_id": aircraft_id,
            "weekdays": [weekday],
            "effective_from_local_date": operating_date.isoformat(),
            "capacity": 180,
            "fare_offer": {"currency": "USD", "amount_minor": fare_minor},
        }
        outbound = create_schedule_definition(
            candidate,
            connection_id=outbound_connection,
            origin_airport_id=origin_id,
            destination_airport_id=destination_id,
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            **common,
        )
        if not outbound.succeeded:
            conflict = outbound.conflicts[0]
            return _rejected(conflict.code, conflict.message)
        inbound = create_schedule_definition(
            candidate,
            connection_id=return_connection,
            origin_airport_id=destination_id,
            destination_airport_id=origin_id,
            departure_local_time="12:00:00",
            arrival_local_time="14:00:00",
            **common,
        )
        if not inbound.succeeded:
            conflict = inbound.conflicts[0]
            return _rejected(conflict.code, conflict.message)
        target = f"{operating_date.isoformat()}T23:59:59Z"
        published = publish_occurrences_through(
            candidate,
            target,
            expected_schedule_revisions={
                outbound.schedule_id: outbound.revision,
                inbound.schedule_id: inbound.revision,
            },
        )
        if not published.succeeded:
            if published.conflicts:
                conflict = published.conflicts[0]
                return _rejected(conflict.code, conflict.message, status=published.status)
            return _rejected("STALE_REVISION", "schedule revision changed", status=published.status)
        if len(published.created_dated_flight_ids) != 2:
            return _rejected(
                "UNEXPECTED_PUBLICATION_COUNT",
                "first rotation must publish exactly outbound and return occurrences",
            )
        final = validate_world(candidate)
        if not final.is_valid:
            issue = final.errors[0]
            return _rejected("RESULT_VALIDATION_FAILED", issue.message, issue.path)
    except (KeyError, TypeError, ValueError) as exc:
        message = str(exc)
        code = message.split(":", 1)[0] if ":" in message else "ROTATION_REJECTED"
        return _rejected(code, message.split(":", 1)[-1].strip())
    envelope.clear()
    envelope.update(deepcopy(candidate))
    return RotationResult(
        "COMPLETED",
        (outbound.schedule_id, inbound.schedule_id),
        tuple(published.created_dated_flight_ids),
        (outbound_connection, return_connection),
        operating_date.isoformat(),
    )


def publish_next_rotation(envelope, *, airline_id):
    """Publish the next eligible occurrence of each active weekly player schedule."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        issue = validation.errors[0]
        return _rejected("INVALID_WORLD_STATE", issue.message, issue.path)
    world = envelope["world_state"]
    schedules = [
        schedule for _schedule_id, schedule in sorted(world["schedule_definitions"].items())
        if schedule["airline_id"] == airline_id and schedule["status"] == "ACTIVE"
    ]
    if not schedules:
        return _rejected("NO_ACTIVE_ROTATION", "plan a weekly rotation first")
    weekdays = {
        tuple(schedule["revisions"][str(schedule["current_revision"])]["recurrence"]["weekdays"])
        for schedule in schedules
    }
    if len(weekdays) != 1 or len(next(iter(weekdays))) != 1:
        return _rejected("UNSUPPORTED_RECURRENCE", "active schedules do not form one weekly rotation")
    weekday = next(iter(weekdays))[0]
    schedule_ids = {schedule["schedule_id"] for schedule in schedules}
    published_dates = [
        date.fromisoformat(flight["scheduled_departure_local_date"])
        for flight in world["dated_flights"].values()
        if flight["schedule_id"] in schedule_ids
    ]
    current_date = date.fromisoformat(envelope["simulation"]["time_utc"][:10])
    cursor = max(published_dates, default=current_date - timedelta(days=1)) + timedelta(days=1)
    if cursor < current_date:
        cursor = current_date
    while cursor.weekday() != weekday:
        cursor += timedelta(days=1)
    if cursor <= current_date:
        cursor += timedelta(days=7)
    candidate = deepcopy(envelope)
    expected = {schedule["schedule_id"]: schedule["current_revision"] for schedule in schedules}
    published = publish_occurrences_through(
        candidate, f"{cursor.isoformat()}T23:59:59Z",
        expected_schedule_revisions=expected,
    )
    if not published.succeeded:
        if published.conflicts:
            conflict = published.conflicts[0]
            return _rejected(conflict.code, conflict.message, status=published.status)
        return _rejected("STALE_REVISION", "schedule revision changed", status=published.status)
    final = validate_world(candidate)
    if not final.is_valid:
        issue = final.errors[0]
        return _rejected("RESULT_VALIDATION_FAILED", issue.message, issue.path)
    envelope.clear()
    envelope.update(deepcopy(candidate))
    return RotationResult(
        "COMPLETED", tuple(sorted(schedule_ids)),
        tuple(published.created_dated_flight_ids), first_operating_date=cursor.isoformat(),
    )


__all__ = (
    "RotationIssue", "RotationResult", "create_weekly_round_trip_rotation",
    "publish_next_rotation",
)
