"""Authoritative Stage 1 repeating schedules and dated-flight publication."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Mapping
from zoneinfo import ZoneInfoNotFoundError

from .timing import timed_deadhead, timing_bounds

from game.simulation import schedule_event, set_operation_revision
from game.world_state.ids import allocate_id
from game.world_state.schema import (
    FLIGHT_DEPARTURE_EVENT_CONTRACT,
    FLIGHT_DEPARTURE_EVENT_TYPE,
    FLIGHT_EVENT_PRIORITY,
)
from game.world_state.timezones import load_named_timezone
from game.world_state.timestamps import format_utc, parse_canonical_utc
from game.world_state.validation import validate_world


REVISION_MUTABLE_STATUSES = frozenset({"PLANNED", "SUPERSEDED"})
ACTIVE_DATED_FLIGHT_STATUSES = frozenset({"PLANNED", "OPERATIONALLY_LOCKED"})
BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW = (
    "BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW"
)
_REVISION_FIELDS = frozenset(
    {
        "connection_id",
        "planned_aircraft_id",
        "origin_airport_id",
        "destination_airport_id",
        "service_type",
        "recurrence",
        "capacity",
        "fare_offer",
        "passenger_service_classification",
        "planning_timing",
    }
)


@dataclass(frozen=True)
class SchedulingConflict:
    code: str
    message: str
    schedule_id: str | None = None
    dated_flight_id: str | None = None
    aircraft_id: str | None = None
    previous_dated_flight_id: str | None = None
    required_origin_airport_id: str | None = None
    actual_airport_id: str | None = None

    @property
    def requires_repositioning(self):
        return self.code == "REPOSITIONING_REQUIRED"

    def as_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "schedule_id": self.schedule_id,
            "dated_flight_id": self.dated_flight_id,
            "aircraft_id": self.aircraft_id,
            "previous_dated_flight_id": self.previous_dated_flight_id,
            "required_origin_airport_id": self.required_origin_airport_id,
            "actual_airport_id": self.actual_airport_id,
            "requires_repositioning": self.requires_repositioning,
        }


@dataclass(frozen=True)
class ScheduleDefinitionResult:
    status: str
    schedule_id: str | None = None
    revision: int | None = None
    conflicts: tuple[SchedulingConflict, ...] = ()
    created_dated_flight_ids: tuple[str, ...] = ()
    updated_dated_flight_ids: tuple[str, ...] = ()
    superseded_dated_flight_ids: tuple[str, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


@dataclass(frozen=True)
class PublicationResult:
    status: str
    target_horizon_utc: str
    created_dated_flight_ids: tuple[str, ...] = ()
    updated_dated_flight_ids: tuple[str, ...] = ()
    superseded_dated_flight_ids: tuple[str, ...] = ()
    unchanged_dated_flight_ids: tuple[str, ...] = ()
    stale_schedule_ids: tuple[str, ...] = ()
    conflicts: tuple[SchedulingConflict, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _replace_envelope(target, candidate):
    committed = deepcopy(candidate)
    target.clear()
    target.update(committed)


def _strict_confirmed_booking_counts(world):
    counts = {}
    itineraries = world.get("itineraries", {})
    for booking in world.get("bookings", {}).values():
        if (
            type(booking) is not dict
            or booking.get("contract") != "STAGE1_AGGREGATE_BOOKING_V1"
            or booking.get("status") != "CONFIRMED"
            or type(booking.get("passenger_count")) is not int
        ):
            continue
        itinerary = itineraries.get(booking.get("itinerary_id"))
        if type(itinerary) is not dict or itinerary.get("contract") != "STAGE1_DIRECT_ECONOMY_ITINERARY_V1":
            continue
        for flight_id in itinerary.get("dated_flight_ids", []):
            if type(flight_id) is str:
                counts[flight_id] = counts.get(flight_id, 0) + booking["passenger_count"]
    return counts


def _booked_change_conflict(flight, wanted, booked_count):
    if wanted is None:
        return True
    protected_fields = (
        "airline_id", "schedule_id", "schedule_revision", "occurrence_key",
        "connection_id", "planned_aircraft_id", "origin_airport_id",
        "destination_airport_id", "service_type", "scheduled_off_block_utc",
        "scheduled_in_block_utc", "passenger_service_classification",
        "fare_offer", "status",
    )
    if any(flight.get(field) != wanted.get(field) for field in protected_fields):
        return True
    capacity = wanted.get("capacity")
    return type(capacity) is not int or capacity < booked_count


def _conflicts_from_validation(result):
    return tuple(
        SchedulingConflict(
            code=issue.code.upper(),
            message=f"{issue.path}: {issue.message}",
            schedule_id=issue.entity_id if issue.entity_type == "schedule" else None,
            dated_flight_id=(
                issue.entity_id if issue.entity_type == "dated_flight" else None
            ),
        )
        for issue in result.errors
    )


def _canonical_local_date(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be canonical YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be canonical YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must be canonical YYYY-MM-DD")
    return parsed


def _canonical_local_time(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be whole-second HH:MM:SS")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be whole-second HH:MM:SS") from exc
    if (
        parsed.tzinfo is not None
        or parsed.microsecond
        or parsed.strftime("%H:%M:%S") != value
    ):
        raise ValueError(f"{field_name} must be whole-second HH:MM:SS")
    return parsed


def _timezone_for(envelope, airport_id):
    airport = envelope["world_state"]["airports"].get(airport_id)
    if airport is None:
        raise ValueError(f"airport does not exist: {airport_id}")
    timezone_name = airport.get("timezone")
    try:
        return load_named_timezone(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError(
            f"airport {airport_id} has invalid named timezone {timezone_name!r}"
        ) from exc


def _local_to_utc(local_date, local_time_text, fold, zone, field_name):
    local_time = _canonical_local_time(local_time_text, field_name)
    if isinstance(fold, bool) or fold not in (0, 1):
        raise ValueError(f"{field_name} fold must be 0 or 1")
    naive = datetime.combine(local_date, local_time)
    aware = naive.replace(tzinfo=zone, fold=fold)
    utc_value = aware.astimezone(timezone.utc)
    round_trip = utc_value.astimezone(zone)
    if round_trip.replace(tzinfo=None) != naive or round_trip.fold != fold:
        raise ValueError(
            f"{field_name} does not exist with fold {fold} in timezone {zone.key}"
        )
    return utc_value


def _make_recurrence(
    *,
    weekdays,
    departure_local_time,
    arrival_local_time,
    arrival_day_offset,
    departure_local_fold,
    arrival_local_fold,
):
    return {
        "frequency": "WEEKLY",
        "weekdays": list(weekdays) if isinstance(weekdays, (list, tuple)) else weekdays,
        "departure_local_time": departure_local_time,
        "departure_local_fold": departure_local_fold,
        "arrival_local_time": arrival_local_time,
        "arrival_day_offset": arrival_day_offset,
        "arrival_local_fold": arrival_local_fold,
    }


def _initial_revision(
    envelope,
    *,
    airline_id,
    connection_id,
    planned_aircraft_id,
    origin_airport_id,
    destination_airport_id,
    service_type,
    weekdays,
    departure_local_time,
    arrival_local_time,
    arrival_day_offset,
    departure_local_fold,
    arrival_local_fold,
    effective_from_local_date,
    capacity,
    fare_offer,
    passenger_service_classification,
):
    airline = (
        envelope["world_state"]["airlines"].get(airline_id, {})
        if isinstance(airline_id, str)
        else {}
    )
    if fare_offer is None:
        fare_offer = {
            "currency": airline.get("base_currency"),
            "amount_minor": 0,
        }
    return {
        "revision": 1,
        "effective_from_local_date": effective_from_local_date,
        "effective_until_local_date": None,
        "connection_id": connection_id,
        "planned_aircraft_id": planned_aircraft_id,
        "origin_airport_id": origin_airport_id,
        "destination_airport_id": destination_airport_id,
        "service_type": service_type,
        "recurrence": _make_recurrence(
            weekdays=weekdays,
            departure_local_time=departure_local_time,
            arrival_local_time=arrival_local_time,
            arrival_day_offset=arrival_day_offset,
            departure_local_fold=departure_local_fold,
            arrival_local_fold=arrival_local_fold,
        ),
        "capacity": capacity,
        "fare_offer": deepcopy(fare_offer),
        "passenger_service_classification": passenger_service_classification,
    }


def create_schedule_definition(
    envelope,
    *,
    airline_id,
    connection_id,
    planned_aircraft_id,
    origin_airport_id,
    destination_airport_id,
    weekdays,
    departure_local_time,
    arrival_local_time,
    effective_from_local_date,
    capacity,
    fare_offer,
    service_type="PASSENGER",
    passenger_service_classification="ECONOMY",
    arrival_day_offset=0,
    departure_local_fold=0,
    arrival_local_fold=0,
    status="ACTIVE",
    planning_timing=None,
    until_local_date=None,
    publication_policy=None,
):
    """Create one structurally valid repeating plan without publishing it."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        return ScheduleDefinitionResult('REJECTED', conflicts=_conflicts_from_validation(validation))
    candidate = deepcopy(envelope)
    result = _stage_schedule_definition(candidate,
        airline_id=airline_id,
        connection_id=connection_id,
        planned_aircraft_id=planned_aircraft_id,
        origin_airport_id=origin_airport_id,
        destination_airport_id=destination_airport_id,
        weekdays=weekdays,
        departure_local_time=departure_local_time,
        arrival_local_time=arrival_local_time,
        effective_from_local_date=effective_from_local_date,
        capacity=capacity,
        fare_offer=fare_offer,
        service_type=service_type,
        passenger_service_classification=passenger_service_classification,
        arrival_day_offset=arrival_day_offset,
        departure_local_fold=departure_local_fold,
        arrival_local_fold=arrival_local_fold,
        status=status,
        planning_timing=planning_timing,
        until_local_date=until_local_date,
        publication_policy=publication_policy,
    )
    if not result.succeeded:
        return result
    validation = validate_world(candidate)
    if not validation.is_valid:
        return ScheduleDefinitionResult('REJECTED', conflicts=_conflicts_from_validation(validation))
    _replace_envelope(envelope, candidate)
    return result


def _stage_schedule_definition(
    envelope,
    *,
    airline_id,
    connection_id,
    planned_aircraft_id,
    origin_airport_id,
    destination_airport_id,
    weekdays,
    departure_local_time,
    arrival_local_time,
    effective_from_local_date,
    capacity,
    fare_offer,
    service_type="PASSENGER",
    passenger_service_classification="ECONOMY",
    arrival_day_offset=0,
    departure_local_fold=0,
    arrival_local_fold=0,
    status="ACTIVE",
    planning_timing=None,
    until_local_date=None,
    publication_policy=None,
):
    """Stage on an isolated scheduling candidate; caller validates before commit.

    Only WeeklyDraft/public wrappers own these detached candidates. This does
    not accept live authority as a substitute for the public command boundary.
    """
    candidate = envelope
    try:
        schedule_id = allocate_id(candidate, "schedule")
    except ValueError as exc:
        return ScheduleDefinitionResult(
            "REJECTED", conflicts=(SchedulingConflict("ID_ALLOCATION_FAILED", str(exc)),)
        )
    revision = _initial_revision(
        candidate,
        airline_id=airline_id,
        connection_id=connection_id,
        planned_aircraft_id=planned_aircraft_id,
        origin_airport_id=origin_airport_id,
        destination_airport_id=destination_airport_id,
        service_type=service_type,
        weekdays=weekdays,
        departure_local_time=departure_local_time,
        arrival_local_time=arrival_local_time,
        arrival_day_offset=arrival_day_offset,
        departure_local_fold=departure_local_fold,
        arrival_local_fold=arrival_local_fold,
        effective_from_local_date=effective_from_local_date,
        capacity=capacity,
        fare_offer=fare_offer,
        passenger_service_classification=passenger_service_classification,
    )
    if planning_timing is not None:
        revision["planning_timing"] = deepcopy(planning_timing)
    if until_local_date is not None:
        revision["recurrence"]["until_local_date"] = until_local_date
    if publication_policy is not None:
        revision["recurrence"]["publication_policy"] = publication_policy
    candidate["world_state"]["schedule_definitions"][schedule_id] = {
        "schedule_id": schedule_id,
        "airline_id": airline_id,
        "status": status,
        "current_revision": 1,
        "revisions": {"1": revision},
    }
    set_operation_revision(candidate, schedule_id, 1)
    if publication_policy is not None:
        from .recurrence import ensure_publication_event
        try:
            ensure_publication_event(candidate, airline_id)
        except (ValueError, KeyError) as exc:
            return ScheduleDefinitionResult('REJECTED', conflicts=(
                SchedulingConflict('INVALID_PUBLICATION_POLICY', str(exc)),))
    return ScheduleDefinitionResult("COMPLETED", schedule_id, 1)


def _revision_for_date(schedule, local_date):
    for revision_number in range(schedule["current_revision"], 0, -1):
        revision = schedule["revisions"][str(revision_number)]
        effective_start = date.fromisoformat(
            revision["effective_from_local_date"]
        )
        if local_date < effective_start:
            continue
        end_text = revision["effective_until_local_date"]
        if end_text is None or local_date <= date.fromisoformat(end_text):
            return revision
    return None


def _occurrence_record(envelope, schedule, revision, local_date, *, flight_id=None):
    origin_zone = _timezone_for(envelope, revision["origin_airport_id"])
    destination_zone = _timezone_for(envelope, revision["destination_airport_id"])
    recurrence = revision["recurrence"]
    departure = _local_to_utc(
        local_date,
        recurrence["departure_local_time"],
        recurrence["departure_local_fold"],
        origin_zone,
        "departure_local_time",
    )
    try:
        arrival_local_date = local_date + timedelta(
            days=recurrence["arrival_day_offset"]
        )
    except OverflowError as exc:
        raise ValueError("arrival local date exceeds the supported range") from exc
    if recurrence.get('publication_policy') == 'ROLLING_FOUR_WEEKS_V1' and 'planning_timing' in revision:
        arrival = departure + timedelta(seconds=timing_bounds(revision['planning_timing'])[1][1])
    else:
        arrival = _local_to_utc(
            arrival_local_date,
            recurrence["arrival_local_time"],
            recurrence["arrival_local_fold"],
            destination_zone,
            "arrival_local_time",
        )
    if arrival <= departure:
        raise ValueError("scheduled arrival must be after scheduled departure in UTC")
    local_date_text = local_date.isoformat()
    record = {
        "dated_flight_id": flight_id,
        "occurrence_key": f"{schedule['schedule_id']}@{local_date_text}",
        "schedule_id": schedule["schedule_id"],
        "schedule_revision": revision["revision"],
        "airline_id": schedule["airline_id"],
        "connection_id": revision["connection_id"],
        "planned_aircraft_id": revision["planned_aircraft_id"],
        "origin_airport_id": revision["origin_airport_id"],
        "destination_airport_id": revision["destination_airport_id"],
        "service_type": revision["service_type"],
        "scheduled_departure_local_date": local_date_text,
        "scheduled_off_block_utc": format_utc(departure),
        "scheduled_in_block_utc": format_utc(arrival),
        "capacity": revision["capacity"],
        "fare_offer": deepcopy(revision["fare_offer"]),
        "passenger_service_classification": revision[
            "passenger_service_classification"
        ],
        "status": "PLANNED",
        "published_at_utc": envelope["simulation"]["time_utc"],
        "superseded_by_schedule_revision": None,
    }
    if envelope.get("metadata", {}).get("save_schema_version") in (3, 4, 5, 6, 7, 8):
        record["inventory_revision"] = 0
    if envelope.get("metadata", {}).get("save_schema_version") in (4, 5, 6, 7, 8):
        record["operation_revision"] = 0
    return record


def _departure_payload(flight):
    return {
        "contract": FLIGHT_DEPARTURE_EVENT_CONTRACT,
        "dated_flight_id": flight["dated_flight_id"],
        "schedule_id": flight["schedule_id"],
        "schedule_revision": flight["schedule_revision"],
        "occurrence_key": flight["occurrence_key"],
    }


def _reconcile_schema4_departure_events(candidate):
    if candidate.get("metadata", {}).get("save_schema_version") not in (4, 5, 6, 7, 8):
        return
    world = candidate["world_state"]
    now = candidate["simulation"]["time_utc"]
    eligible = sorted(
        (flight for flight in world["dated_flights"].values()
         if flight["status"] == "PLANNED"
         and ((flight["service_type"] == "PASSENGER"
               and flight["passenger_service_classification"] == "ECONOMY"
               and type(flight.get("connection_id")) is str)
              or timed_deadhead(world, flight))
         and flight["scheduled_off_block_utc"] >= now),
        key=lambda flight: (
            flight["scheduled_off_block_utc"], flight["schedule_id"],
            flight["scheduled_departure_local_date"], flight["dated_flight_id"],
        ),
    )
    events_by_flight = {}
    for event in world['pending_events'].values():
        if (event.get('event_type') == FLIGHT_DEPARTURE_EVENT_TYPE
                and event.get('owner_type') == 'dated_flight'):
            events_by_flight.setdefault(event.get('owner_id'), []).append(event)
    for flight in eligible:
        matches = [event for event in events_by_flight.get(flight['dated_flight_id'], ())
                   if event.get('owner_id') == flight['dated_flight_id']
                   and event.get("due_at_utc") == flight["scheduled_off_block_utc"]
                   and event.get("operation_revision") == flight["operation_revision"]
                   and event.get("payload") == _departure_payload(flight)]
        if len(matches) > 1:
            raise ValueError("duplicate current departure events")
        if not matches:
            schedule_event(
                candidate, event_type=FLIGHT_DEPARTURE_EVENT_TYPE,
                due_at_utc=flight["scheduled_off_block_utc"],
                owner_type="dated_flight", owner_id=flight["dated_flight_id"],
                operation_revision=flight["operation_revision"],
                priority=FLIGHT_EVENT_PRIORITY, payload=_departure_payload(flight),
            )


def _expand_schedule(envelope, schedule, window_start, window_end, *, known_occurrences=None):
    desired = {}
    conflicts = []
    if known_occurrences is None:
        known_occurrences = {flight['occurrence_key'] for flight in envelope['world_state']['dated_flights'].values()}
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    for revision_number in range(1, schedule["current_revision"] + 1):
        revision = schedule["revisions"][str(revision_number)]
        if not revision["recurrence"].get("enabled", True):
            continue
        try:
            origin_zone = _timezone_for(envelope, revision["origin_airport_id"])
        except ValueError as exc:
            conflicts.append(
                SchedulingConflict("INVALID_TIMEZONE", str(exc), schedule["schedule_id"])
            )
            continue
        first_date = window_start.astimezone(origin_zone).date()
        last_date = window_end.astimezone(origin_zone).date()
        effective_start = date.fromisoformat(revision["effective_from_local_date"])
        effective_end = (
            date.fromisoformat(revision["effective_until_local_date"])
            if revision["effective_until_local_date"] is not None
            else last_date
        )
        current = max(first_date, effective_start)
        last = min(last_date, effective_end)
        if "until_local_date" in revision["recurrence"]:
            last = min(last, date.fromisoformat(revision["recurrence"]["until_local_date"]))
        weekdays = set(revision["recurrence"]["weekdays"])
        preparation_seconds = (timing_bounds(revision['planning_timing'])[1][0]
                               if 'planning_timing' in revision else 0)
        while current <= last:
            if current.weekday() in weekdays:
                try:
                    occurrence = _occurrence_record(
                        envelope, schedule, revision, current
                    )
                except ValueError as exc:
                    conflicts.append(
                        SchedulingConflict(
                            "INVALID_LOCAL_OCCURRENCE",
                            f"{current.isoformat()}: {exc}",
                            schedule["schedule_id"],
                        )
                    )
                else:
                    departure = parse_canonical_utc(
                        occurrence["scheduled_off_block_utc"]
                    )
                    if window_start <= departure <= window_end:
                        known = occurrence['occurrence_key'] in known_occurrences
                        preparation = departure - timedelta(seconds=preparation_seconds)
                        if not (revision['recurrence'].get('publication_policy') == 'ROLLING_FOUR_WEEKS_V1'
                                and not known and preparation < now):
                            desired[occurrence["occurrence_key"]] = occurrence
            current += timedelta(days=1)
    return desired, conflicts


def _continuity_conflicts(envelope):
    world = envelope["world_state"]
    minimum_turnaround = envelope["simulation"]["configuration"]["scheduling"][
        "minimum_turnaround_seconds"
    ]
    now = envelope["simulation"]["time_utc"]
    conflicts = []
    future_by_aircraft = {aircraft_id: [] for aircraft_id in world["aircraft"]}
    schema4 = envelope.get("metadata", {}).get("save_schema_version") in (4, 5, 6, 7, 8)
    for flight in world["dated_flights"].values():
        aircraft_id = flight["planned_aircraft_id"]
        if (
            aircraft_id in future_by_aircraft
            and flight["status"] in (
                {"PLANNED"} if schema4 else ACTIVE_DATED_FLIGHT_STATUSES
            )
            and flight["scheduled_off_block_utc"] >= now
        ):
            future_by_aircraft[aircraft_id].append(flight)
    for aircraft_id in sorted(world["aircraft"]):
        aircraft = world["aircraft"][aircraft_id]
        future = sorted(
            future_by_aircraft[aircraft_id],
            key=lambda flight: (
                flight["scheduled_off_block_utc"],
                flight["dated_flight_id"],
            ),
        )
        expected_origin = aircraft.get("current_airport_id")
        if schema4 and aircraft.get("status") == "IN_FLIGHT":
            active = [operation for operation in world["active_aircraft_operations"].values()
                      if type(operation) is dict
                      and operation.get("actual_aircraft_id") == aircraft_id
                      and operation.get("state") == "OPERATIONALLY_LOCKED"]
            if len(active) == 1:
                expected_origin = active[0].get("destination_airport_id")
        previous = None
        for flight in future:
            if flight["origin_airport_id"] != expected_origin:
                conflicts.append(
                    SchedulingConflict(
                        "REPOSITIONING_REQUIRED",
                        (
                            f"aircraft {aircraft_id} is at {expected_origin}; "
                            f"flight {flight['dated_flight_id']} departs "
                            f"{flight['origin_airport_id']} and requires an explicit deadhead"
                        ),
                        schedule_id=flight["schedule_id"],
                        dated_flight_id=flight["dated_flight_id"],
                        aircraft_id=aircraft_id,
                        previous_dated_flight_id=(
                            previous["dated_flight_id"] if previous else None
                        ),
                        required_origin_airport_id=flight["origin_airport_id"],
                        actual_airport_id=expected_origin,
                    )
                )
            if previous is not None:
                gap_seconds = int(
                    (
                        parse_canonical_utc(flight["scheduled_off_block_utc"])
                        - parse_canonical_utc(previous["scheduled_in_block_utc"])
                    ).total_seconds()
                )
                if gap_seconds < 0:
                    conflicts.append(
                        SchedulingConflict(
                            "AIRCRAFT_OVERLAP",
                            f"flight {flight['dated_flight_id']} overlaps {previous['dated_flight_id']}",
                            schedule_id=flight["schedule_id"],
                            dated_flight_id=flight["dated_flight_id"],
                            aircraft_id=aircraft_id,
                            previous_dated_flight_id=previous["dated_flight_id"],
                        )
                    )
                elif gap_seconds < minimum_turnaround:
                    conflicts.append(
                        SchedulingConflict(
                            "INSUFFICIENT_TURNAROUND",
                            (
                                f"flight {flight['dated_flight_id']} has {gap_seconds} seconds "
                                f"after {previous['dated_flight_id']}; "
                                f"{minimum_turnaround} are required"
                            ),
                            schedule_id=flight["schedule_id"],
                            dated_flight_id=flight["dated_flight_id"],
                            aircraft_id=aircraft_id,
                            previous_dated_flight_id=previous["dated_flight_id"],
                        )
                    )
            previous = flight
            expected_origin = flight["destination_airport_id"]
    return tuple(conflicts)


def _publication_limit(envelope):
    now = parse_canonical_utc(envelope["simulation"]["time_utc"])
    days = envelope["simulation"]["configuration"]["scheduling"][
        "publication_horizon_days"
    ]
    try:
        return now + timedelta(days=days)
    except OverflowError as exc:
        raise ValueError("configured publication horizon exceeds timestamp range") from exc


def configured_publication_horizon_utc(envelope):
    """Return the exact configured rolling UTC horizon without mutation."""
    return format_utc(_publication_limit(envelope))


def publish_occurrences_through(
    envelope, target_horizon_utc, *, expected_schedule_revisions=None, schedule_ids=None
):
    """Atomically publish selected (default all) active plans through a UTC horizon."""
    try:
        target = parse_canonical_utc(target_horizon_utc, "target_horizon_utc")
    except ValueError as exc:
        return PublicationResult(
            "REJECTED",
            str(target_horizon_utc),
            conflicts=(SchedulingConflict("INVALID_HORIZON", str(exc)),),
        )
    if expected_schedule_revisions is not None and not isinstance(
        expected_schedule_revisions, Mapping
    ):
        return PublicationResult(
            "REJECTED",
            target_horizon_utc,
            conflicts=(
                SchedulingConflict(
                    "INVALID_EXPECTED_REVISIONS",
                    "expected_schedule_revisions must be a mapping",
                ),
            ),
        )
    if expected_schedule_revisions is not None and any(
        not isinstance(schedule_id, str)
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
        for schedule_id, revision in expected_schedule_revisions.items()
    ):
        return PublicationResult(
            "REJECTED",
            target_horizon_utc,
            conflicts=(
                SchedulingConflict(
                    "INVALID_EXPECTED_REVISIONS",
                    "expected revisions require string schedule IDs and positive integers",
                ),
            ),
        )

    initial_validation = validate_world(envelope)
    if not initial_validation.is_valid:
        return PublicationResult(
            "REJECTED",
            target_horizon_utc,
            conflicts=_conflicts_from_validation(initial_validation),
        )

    start, target, failure = _publication_window(envelope, target_horizon_utc)
    if failure is not None:
        return failure

    schedules = envelope["world_state"]["schedule_definitions"]
    selected_ids = None
    if schedule_ids is not None:
        if (not isinstance(schedule_ids, (list, tuple, set, frozenset))
                or any(not isinstance(key, str) or key not in schedules for key in schedule_ids)):
            return PublicationResult('REJECTED', target_horizon_utc, conflicts=(
                SchedulingConflict('INVALID_SCHEDULE_SELECTION', 'select existing authoritative schedule IDs'),))
        selected_ids = frozenset(schedule_ids)
    stale = []
    for schedule_id, expected in sorted((expected_schedule_revisions or {}).items()):
        schedule = schedules.get(schedule_id)
        if schedule is None or schedule.get("current_revision") != expected:
            stale.append(schedule_id)
    if stale:
        return PublicationResult(
            "STALE_REVISION",
            target_horizon_utc,
            stale_schedule_ids=tuple(stale),
        )

    candidate = deepcopy(envelope)
    result = _publish_candidate(candidate, start, target, target_horizon_utc, selected_ids)
    if not result.succeeded:
        return result
    validation = validate_world(candidate)
    if not validation.is_valid:
        return PublicationResult('REJECTED', target_horizon_utc,
                                 conflicts=_conflicts_from_validation(validation))
    _replace_envelope(envelope, candidate)
    return result


def _publication_window(envelope, target_horizon_utc):
    target = parse_canonical_utc(target_horizon_utc, 'target_horizon_utc')
    start = parse_canonical_utc(envelope["simulation"]["time_utc"])
    if target < start:
        return None, None, PublicationResult(
            "REJECTED",
            target_horizon_utc,
            conflicts=(
                SchedulingConflict(
                    "INVALID_HORIZON", "publication horizon cannot precede simulation time"
                ),
            ),
        )
    try:
        publication_limit = _publication_limit(envelope)
    except ValueError as exc:
        return None, None, PublicationResult(
            "REJECTED",
            target_horizon_utc,
            conflicts=(SchedulingConflict("INVALID_HORIZON", str(exc)),),
        )
    if target > publication_limit:
        return None, None, PublicationResult(
            "REJECTED",
            target_horizon_utc,
            conflicts=(
                SchedulingConflict(
                    "HORIZON_EXCEEDS_CONFIGURATION",
                    "target exceeds the configured rolling publication window",
                ),
            ),
        )

    return start, target, None


def _publish_detached(candidate, target_horizon_utc, *, selected_ids=None):
    """No copies/commit: isolated owner must validate the complete result."""
    start, target, failure = _publication_window(candidate, target_horizon_utc)
    if failure is not None:
        return failure
    return _publish_candidate(candidate, start, target, target_horizon_utc, selected_ids)


def _publish_candidate(candidate, start, target, target_horizon_utc, selected_ids):
    """Reconcile a detached candidate. Caller validates its complete boundary.

    Input/world validation and committing stay with the public transaction or
    kernel event owner; conflict, booking and continuity checks stay here.
    """
    desired = {}
    expansion_conflicts = []
    known_occurrences = {flight['occurrence_key'] for flight in candidate['world_state']['dated_flights'].values()}
    for schedule_id in sorted(candidate["world_state"]["schedule_definitions"]):
        schedule = candidate["world_state"]["schedule_definitions"][schedule_id]
        if schedule["status"] != "ACTIVE" or (selected_ids is not None and schedule_id not in selected_ids):
            continue
        schedule_desired, conflicts = _expand_schedule(
            candidate, schedule, start, target, known_occurrences=known_occurrences
        )
        desired.update(schedule_desired)
        expansion_conflicts.extend(conflicts)
    if expansion_conflicts:
        return PublicationResult(
            "CONFLICT",
            target_horizon_utc,
            conflicts=tuple(expansion_conflicts),
        )

    _initial_partial_activation(candidate, desired)

    flights = candidate["world_state"]["dated_flights"]
    booked_counts = _strict_confirmed_booking_counts(candidate["world_state"])
    existing_by_key = {
        flight["occurrence_key"]: flight_id
        for flight_id, flight in flights.items()
    }
    created = []
    updated = []
    superseded = []
    unchanged = []

    for key, flight_id in sorted(existing_by_key.items()):
        flight = flights[flight_id]
        if selected_ids is not None and flight["schedule_id"] not in selected_ids:
            unchanged.append(flight_id)
            continue
        if key not in desired and not (
            candidate["simulation"]["time_utc"]
            <= flight["scheduled_off_block_utc"]
            <= target_horizon_utc
        ):
            continue
        schedule = candidate["world_state"]["schedule_definitions"].get(
            flight["schedule_id"]
        )
        wanted = desired.get(key) if schedule and schedule["status"] == "ACTIVE" else None
        if (
            flight["status"] not in REVISION_MUTABLE_STATUSES
            or flight_id
            in candidate["world_state"]["active_aircraft_operations"]
        ):
            unchanged.append(flight_id)
            desired.pop(key, None)
            continue
        if flight_id in booked_counts and _booked_change_conflict(
            flight, wanted, booked_counts[flight_id]
        ):
            return PublicationResult(
                "CONFLICT",
                target_horizon_utc,
                conflicts=(SchedulingConflict(
                    BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW,
                    "confirmed Bookings protect this dated-flight occurrence until a disruption workflow exists",
                    schedule_id=flight.get("schedule_id"),
                    dated_flight_id=flight_id,
                    aircraft_id=flight.get("planned_aircraft_id"),
                ),),
            )
        if wanted is None:
            if flight["status"] != "SUPERSEDED":
                if candidate["metadata"]["save_schema_version"] in (4, 5, 6, 7, 8):
                    flight["operation_revision"] += 1
                    set_operation_revision(
                        candidate, flight_id, flight["operation_revision"]
                    )
                flight["status"] = "SUPERSEDED"
                flight["superseded_by_schedule_revision"] = (
                    schedule["current_revision"] if schedule else flight["schedule_revision"]
                )
                superseded.append(flight_id)
            else:
                unchanged.append(flight_id)
            continue
        desired.pop(key, None)
        first_published = flight["published_at_utc"]
        wanted["dated_flight_id"] = flight_id
        wanted["published_at_utc"] = first_published
        if "inventory_revision" in flight:
            wanted["inventory_revision"] = flight["inventory_revision"]
        if "operation_revision" in flight:
            wanted["operation_revision"] = flight["operation_revision"]
        if flight != wanted:
            if candidate["metadata"]["save_schema_version"] in (4, 5, 6, 7, 8):
                wanted["operation_revision"] += 1
                set_operation_revision(
                    candidate, flight_id, wanted["operation_revision"]
                )
            flights[flight_id] = wanted
            updated.append(flight_id)
        else:
            unchanged.append(flight_id)

    ordered_new = sorted(
        desired.values(),
        key=lambda flight: (
            flight["scheduled_off_block_utc"],
            flight["schedule_id"],
            flight["scheduled_departure_local_date"],
        ),
    )
    for flight in ordered_new:
        revision = candidate['world_state']['schedule_definitions'][flight['schedule_id']]['revisions'][str(flight['schedule_revision'])]
        if 'planning_timing' in revision:
            preparation = parse_canonical_utc(flight['scheduled_off_block_utc']) - timedelta(
                seconds=timing_bounds(revision['planning_timing'])[1][0])
            if preparation < start:
                return PublicationResult('REJECTED', target_horizon_utc,
                    conflicts=(SchedulingConflict('PAST_PREPARATION',
                        'new flight preparation cannot start before simulation time'),))
        try:
            flight_id = allocate_id(candidate, "dated_flight")
        except ValueError as exc:
            return PublicationResult(
                "REJECTED",
                target_horizon_utc,
                conflicts=(
                    SchedulingConflict("ID_ALLOCATION_FAILED", str(exc)),
                ),
            )
        flight["dated_flight_id"] = flight_id
        flights[flight_id] = flight
        if candidate["metadata"]["save_schema_version"] in (4, 5, 6, 7, 8):
            candidate["simulation"]["operation_revisions"][flight_id] = 0
        created.append(flight_id)

    try:
        _reconcile_schema4_departure_events(candidate)
    except ValueError as exc:
        return PublicationResult(
            "REJECTED", target_horizon_utc,
            conflicts=(SchedulingConflict("EVENT_SCHEDULING_FAILED", str(exc)),),
        )

    conflicts = _continuity_conflicts(candidate)
    if conflicts:
        return PublicationResult(
            "CONFLICT",
            target_horizon_utc,
            conflicts=conflicts,
        )
    return PublicationResult(
        "COMPLETED",
        target_horizon_utc,
        tuple(created),
        tuple(updated),
        tuple(superseded),
        tuple(sorted(set(unchanged))),
    )


def _initial_partial_activation(envelope, desired):
    """Filter only unpublished initial policy prefixes; never alter definitions."""
    from .activation import initial_week_end, initial_week_window, operational_sequence
    from .timing import flight_reservation
    world = envelope['world_state']
    known = {flight['occurrence_key'] for flight in world['dated_flights'].values()}
    prototypes = {}
    initial_ids = {}
    for schedule in world['schedule_definitions'].values():
        if schedule['status'] != 'ACTIVE' or schedule['current_revision'] != 1:
            continue
        revision = schedule['revisions']['1']
        if revision['recurrence'].get('publication_policy') != 'ROLLING_FOUR_WEEKS_V1':
            continue
        aircraft_id = revision['planned_aircraft_id']
        # Examine actual selected weekdays, not an effective date that may
        # itself be a non-operating day. At most the current calendar week.
        beginning, end = initial_week_window(envelope, aircraft_id)
        zone = _timezone_for(envelope, revision['origin_airport_id'])
        recurrence = revision['recurrence']
        if not recurrence.get('enabled', True):
            continue
        first = date.fromisoformat(revision['effective_from_local_date'])
        while first.weekday() not in recurrence['weekdays']:
            first += timedelta(days=1)
        try:
            first_occurrence = _occurrence_record(envelope, schedule, revision, first)
        except ValueError:
            continue
        first_departure = parse_canonical_utc(first_occurrence['scheduled_off_block_utc'])
        if not beginning <= first_departure < end:
            continue  # Established recurrences/revisions never reacquire initial skipping.
        initial_ids.setdefault(aircraft_id, set()).add(schedule['schedule_id'])
        current = max(beginning.astimezone(zone).date(),
                      date.fromisoformat(revision['effective_from_local_date']))
        last = parse_canonical_utc(envelope['simulation']['time_utc']).astimezone(zone).date()
        if recurrence.get('until_local_date'):
            last = min(last, date.fromisoformat(recurrence['until_local_date']))
        while current <= last:
            if current.weekday() in recurrence['weekdays']:
                try:
                    prototype = _occurrence_record(envelope, schedule, revision, current)
                except ValueError:
                    # Future invalid local occurrences are rejected by normal
                    # expansion. An invalid elapsed intent cannot activate.
                    pass
                else:
                    prototypes.setdefault(aircraft_id, []).append((flight_reservation(world, prototype)[0],
                        parse_canonical_utc(prototype['scheduled_off_block_utc'])))
            current += timedelta(days=1)
    for aircraft_id, starts in prototypes.items():
        end = initial_week_end(envelope, aircraft_id, starts)
        if end is None:
            continue
        rows = []
        eligible = set()
        keys = {}
        for key, flight in desired.items():
            if flight['planned_aircraft_id'] != aircraft_id:
                continue
            row = (*flight_reservation(world, flight),
                   parse_canonical_utc(flight['scheduled_off_block_utc']),
                   parse_canonical_utc(flight['scheduled_in_block_utc']),
                   flight['origin_airport_id'], flight['destination_airport_id'])
            rows.append(row)
            if key not in known and flight['schedule_id'] in initial_ids[aircraft_id]:
                eligible.add(row)
                keys[key] = row
        activated = []
        for flight in world['dated_flights'].values():
            if flight['planned_aircraft_id'] != aircraft_id or flight['status'] in {'SUPERSEDED', 'CANCELLED'}:
                continue
            if flight['schedule_id'] in initial_ids[aircraft_id]:
                activated.append(parse_canonical_utc(flight['scheduled_off_block_utc']))
            if flight['occurrence_key'] not in desired:
                rows.append((*flight_reservation(world, flight),
                    parse_canonical_utc(flight['scheduled_off_block_utc']),
                    parse_canonical_utc(flight['scheduled_in_block_utc']),
                    flight['origin_airport_id'], flight['destination_airport_id']))
        retained = set(operational_sequence(envelope, aircraft_id, rows, eligible, end,
                       activated_at=min(activated) if activated else None))
        for key, row in keys.items():
            if row not in retained:
                del desired[key]


def publish_configured_window(envelope, *, expected_schedule_revisions=None):
    try:
        target = configured_publication_horizon_utc(envelope)
    except (KeyError, TypeError, ValueError) as exc:
        return PublicationResult(
            "REJECTED",
            envelope.get("simulation", {}).get("time_utc", ""),
            conflicts=(SchedulingConflict("INVALID_HORIZON", str(exc)),),
        )
    return publish_occurrences_through(
        envelope,
        target,
        expected_schedule_revisions=expected_schedule_revisions,
    )


def extend_publication_window(envelope, publication_horizon_days):
    """Atomically increase the configured horizon and publish newly exposed work."""
    if (
        isinstance(publication_horizon_days, bool)
        or not isinstance(publication_horizon_days, int)
        or publication_horizon_days < 1
    ):
        raise ValueError("publication_horizon_days must be a positive integer")
    validation = validate_world(envelope)
    if not validation.is_valid:
        return PublicationResult(
            "REJECTED",
            envelope.get("simulation", {}).get("time_utc", ""),
            conflicts=_conflicts_from_validation(validation),
        )
    current = envelope["simulation"]["configuration"]["scheduling"][
        "publication_horizon_days"
    ]
    if publication_horizon_days <= current:
        raise ValueError("publication window extension must increase the horizon")
    candidate = deepcopy(envelope)
    candidate["simulation"]["configuration"]["scheduling"][
        "publication_horizon_days"
    ] = publication_horizon_days
    result = publish_configured_window(candidate)
    if result.succeeded:
        _replace_envelope(envelope, candidate)
    return result


def validate_schedule_definition(envelope, schedule_id, *, target_horizon_utc=None):
    """Return structural and publication conflicts without mutating authority."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        return _conflicts_from_validation(validation)
    if (
        not isinstance(schedule_id, str)
        or schedule_id not in envelope["world_state"]["schedule_definitions"]
    ):
        return (
            SchedulingConflict(
                "MISSING_SCHEDULE", f"schedule does not exist: {schedule_id}"
            ),
        )
    candidate = deepcopy(envelope)
    candidate["world_state"]["schedule_definitions"][schedule_id]["status"] = "ACTIVE"
    target = (
        target_horizon_utc
        if target_horizon_utc is not None
        else configured_publication_horizon_utc(candidate)
    )
    result = publish_occurrences_through(candidate, target)
    return result.conflicts


def _apply_revision_changes(revision, changes):
    changes = dict(changes)
    recurrence = deepcopy(revision["recurrence"])
    recurrence_keys = {
        "weekdays",
        "departure_local_time",
        "arrival_local_time",
        "arrival_day_offset",
        "departure_local_fold",
        "arrival_local_fold",
    }
    supplied_recurrence = changes.pop("recurrence", None)
    if supplied_recurrence is not None:
        recurrence = deepcopy(supplied_recurrence)
    for key in tuple(changes):
        if key in recurrence_keys:
            recurrence[key] = deepcopy(changes.pop(key))
    unknown = set(changes) - _REVISION_FIELDS
    if unknown:
        raise ValueError(f"unsupported revision fields: {sorted(unknown)}")
    updated = deepcopy(revision)
    for key, value in changes.items():
        updated[key] = deepcopy(value)
    updated["recurrence"] = recurrence
    return updated


def revise_future_schedule(
    envelope,
    schedule_id,
    *,
    effective_from_local_date,
    expected_revision=None,
    _defer_publication=False,
    **changes,
):
    """Create an effective-dated revision and reconcile unlocked publication."""
    initial_validation = validate_world(envelope)
    if not initial_validation.is_valid:
        return ScheduleDefinitionResult(
            "REJECTED",
            schedule_id if isinstance(schedule_id, str) else None,
            conflicts=_conflicts_from_validation(initial_validation),
        )
    candidate = deepcopy(envelope)
    staged = _stage_schedule_revision(candidate, schedule_id,
        effective_from_local_date=effective_from_local_date,
        expected_revision=expected_revision, **changes)
    if not staged.succeeded:
        return staged
    current_revision = staged.revision - 1
    new_revision = staged.revision
    candidate_schedule = candidate['world_state']['schedule_definitions'][schedule_id]
    proposed = candidate_schedule['revisions'][str(new_revision)]
    structural = validate_world(candidate)
    if not structural.is_valid:
        return ScheduleDefinitionResult(
            "REJECTED",
            schedule_id,
            current_revision,
            _conflicts_from_validation(structural),
        )
    if candidate_schedule["status"] == "ACTIVE" and not _defer_publication:
        if proposed['recurrence'].get('publication_policy') == 'ROLLING_FOUR_WEEKS_V1':
            from .recurrence import rolling_horizon
            publication = publish_occurrences_through(candidate,
                rolling_horizon(candidate, candidate_schedule['airline_id']),
                expected_schedule_revisions={schedule_id: new_revision})
        else:
            publication = publish_configured_window(
                candidate, expected_schedule_revisions={schedule_id: new_revision})
        if not publication.succeeded:
            return ScheduleDefinitionResult(
                publication.status,
                schedule_id,
                current_revision,
                publication.conflicts,
            )
        created = publication.created_dated_flight_ids
        updated = publication.updated_dated_flight_ids
        superseded = publication.superseded_dated_flight_ids
    else:
        created = ()
        updated = ()
        superseded = ()
    _replace_envelope(envelope, candidate)
    return ScheduleDefinitionResult(
        "COMPLETED",
        schedule_id,
        new_revision,
        created_dated_flight_ids=created,
        updated_dated_flight_ids=updated,
        superseded_dated_flight_ids=superseded,
    )


def _stage_schedule_revision(envelope, schedule_id, *, effective_from_local_date,
                             expected_revision=None, **changes):
    """Apply a revision only to an isolated candidate; no publication/commit."""
    schedule = (
        envelope["world_state"]["schedule_definitions"].get(schedule_id)
        if isinstance(schedule_id, str)
        else None
    )
    if schedule is None:
        return ScheduleDefinitionResult(
            "REJECTED",
            conflicts=(
                SchedulingConflict(
                    "MISSING_SCHEDULE", f"schedule does not exist: {schedule_id}"
                ),
            ),
        )
    current_revision = schedule["current_revision"]
    if expected_revision is not None and (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 1
    ):
        return ScheduleDefinitionResult(
            "REJECTED",
            schedule_id,
            current_revision,
            (
                SchedulingConflict(
                    "INVALID_EXPECTED_REVISION",
                    "expected_revision must be a positive integer",
                    schedule_id,
                ),
            ),
        )
    if expected_revision is not None and expected_revision != current_revision:
        return ScheduleDefinitionResult("STALE_REVISION", schedule_id, current_revision)
    try:
        effective_date = _canonical_local_date(
            effective_from_local_date, "effective_from_local_date"
        )
        current_plan = schedule["revisions"][str(current_revision)]
        proposed = _apply_revision_changes(current_plan, changes)
        local_now = parse_canonical_utc(
            envelope["simulation"]["time_utc"]
        ).astimezone(_timezone_for(envelope, proposed["origin_airport_id"])).date()
    except ValueError as exc:
        return ScheduleDefinitionResult(
            "REJECTED",
            schedule_id,
            current_revision,
            (SchedulingConflict("INVALID_REVISION", str(exc), schedule_id),),
        )
    current_start = date.fromisoformat(current_plan["effective_from_local_date"])
    if effective_date <= current_start or effective_date < local_now:
        return ScheduleDefinitionResult(
            "REJECTED",
            schedule_id,
            current_revision,
            (
                SchedulingConflict(
                    "INVALID_EFFECTIVE_DATE",
                    "new revision must start after the current revision and not in the local past",
                    schedule_id,
                ),
            ),
        )

    candidate = envelope
    candidate_schedule = candidate["world_state"]["schedule_definitions"][schedule_id]
    previous = candidate_schedule["revisions"][str(current_revision)]
    previous["effective_until_local_date"] = (
        effective_date - timedelta(days=1)
    ).isoformat()
    new_revision = current_revision + 1
    proposed["revision"] = new_revision
    proposed["effective_from_local_date"] = effective_date.isoformat()
    proposed["effective_until_local_date"] = None
    candidate_schedule["revisions"][str(new_revision)] = proposed
    candidate_schedule["current_revision"] = new_revision
    set_operation_revision(candidate, schedule_id, new_revision)

    if proposed['recurrence'].get('publication_policy') == 'ROLLING_FOUR_WEEKS_V1':
        from .recurrence import ensure_publication_event
        ensure_publication_event(candidate, candidate_schedule['airline_id'])
    return ScheduleDefinitionResult('COMPLETED', schedule_id, new_revision)


def _publish_event_occurrences(context, target_horizon_utc, *, schedule_ids):
    """Publish inside an existing complete-event candidate, never live state."""
    from game.simulation.kernel import _EVENT_TRANSACTION_TOKEN
    if context._transaction_token is not _EVENT_TRANSACTION_TOKEN:
        raise ValueError('publication requires an isolated kernel event transaction')
    return _publish_detached(context.envelope, target_horizon_utc,
                             selected_ids=frozenset(schedule_ids))
