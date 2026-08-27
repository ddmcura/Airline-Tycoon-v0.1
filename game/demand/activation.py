"""Rebuildable demand activation from published dated passenger service.

Activation selects sparse daily work.  It never supplies a Model 3 formula
input, changes normalization, or proves that an itinerary can be booked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfoNotFoundError

from game.scheduling import (
    DatedFlightIndexes,
    configured_publication_horizon_utc,
)
from game.scheduling.indexes import ACTIVE_SERVICE_STATUSES
from game.world_state.schema import DEMAND_DESTINATION_TYPES
from game.world_state.timestamps import format_utc, parse_canonical_utc
from game.world_state.timezones import load_named_timezone


@dataclass(frozen=True)
class ActivationWindow:
    """Inclusive UTC window in which published service may activate a pair."""

    start_utc: str
    end_utc: str

    def __post_init__(self):
        start = parse_canonical_utc(self.start_utc, "start_utc")
        end = parse_canonical_utc(self.end_utc, "end_utc")
        if end < start:
            raise ValueError("activation end_utc cannot precede start_utc")


class DemandActivationProvider(Protocol):
    """Runtime boundary for one source of potentially usable itineraries.

    Milestone 5 may add providers for permitted connecting patterns and apply a
    Booking-owned horizon before combining their directional-pair results.
    """

    def active_market_ids(
        self,
        envelope,
        window: ActivationWindow,
        *,
        dated_flight_indexes: DatedFlightIndexes | None = None,
    ) -> tuple[str, ...]:
        """Return stable immutable market IDs activated by this source."""


def _valid_fare_offer(fare_offer):
    return (
        isinstance(fare_offer, Mapping)
        and isinstance(fare_offer.get("currency"), str)
        and bool(fare_offer["currency"])
        and isinstance(fare_offer.get("amount_minor"), int)
        and not isinstance(fare_offer.get("amount_minor"), bool)
        and fare_offer["amount_minor"] >= 0
    )


def _canonical_local_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _canonical_local_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return None
    if (
        parsed.tzinfo is not None
        or parsed.microsecond
        or parsed.strftime("%H:%M:%S") != value
    ):
        return None
    return parsed


def _local_to_utc(local_date, local_time_text, fold, timezone_name):
    local_time = _canonical_local_time(local_time_text)
    if local_time is None or isinstance(fold, bool) or fold not in (0, 1):
        return None
    try:
        zone = load_named_timezone(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        return None
    naive = datetime.combine(local_date, local_time)
    aware = naive.replace(tzinfo=zone, fold=fold)
    resolved = aware.astimezone(timezone.utc)
    round_trip = resolved.astimezone(zone)
    if round_trip.replace(tzinfo=None) != naive or round_trip.fold != fold:
        return None
    return resolved


def _schedule_trace_is_valid(envelope, flight, revision):
    """Check the immutable publication snapshot without trusting stale indexes."""
    trace_fields = (
        "connection_id",
        "planned_aircraft_id",
        "origin_airport_id",
        "destination_airport_id",
        "service_type",
        "capacity",
        "fare_offer",
        "passenger_service_classification",
    )
    if any(flight.get(field) != revision.get(field) for field in trace_fields):
        return False
    local_date_text = flight.get("scheduled_departure_local_date")
    local_date = _canonical_local_date(local_date_text)
    if (
        local_date is None
        or flight.get("occurrence_key")
        != f"{flight.get('schedule_id')}@{local_date_text}"
    ):
        return False
    effective_from = _canonical_local_date(revision.get("effective_from_local_date"))
    effective_until_text = revision.get("effective_until_local_date")
    effective_until = (
        None
        if effective_until_text is None
        else _canonical_local_date(effective_until_text)
    )
    if (
        effective_from is None
        or (effective_until_text is not None and effective_until is None)
        or local_date < effective_from
        or (effective_until is not None and local_date > effective_until)
    ):
        return False
    recurrence = revision.get("recurrence")
    if not isinstance(recurrence, Mapping):
        return False
    day_offset = recurrence.get("arrival_day_offset")
    weekdays = recurrence.get("weekdays")
    if (
        isinstance(day_offset, bool)
        or not isinstance(day_offset, int)
        or not isinstance(weekdays, Sequence)
        or isinstance(weekdays, (str, bytes))
        or local_date.weekday() not in weekdays
    ):
        return False
    try:
        arrival_local_date = local_date + timedelta(days=day_offset)
    except OverflowError:
        return False
    airports = envelope["world_state"]["airports"]
    origin = airports[flight["origin_airport_id"]]
    destination = airports[flight["destination_airport_id"]]
    expected_departure = _local_to_utc(
        local_date,
        recurrence.get("departure_local_time"),
        recurrence.get("departure_local_fold"),
        origin.get("timezone"),
    )
    expected_arrival = _local_to_utc(
        arrival_local_date,
        recurrence.get("arrival_local_time"),
        recurrence.get("arrival_local_fold"),
        destination.get("timezone"),
    )
    if expected_departure is None or expected_arrival is None:
        return False
    return (
        flight.get("scheduled_off_block_utc") == format_utc(expected_departure)
        and flight.get("scheduled_in_block_utc") == format_utc(expected_arrival)
    )


def _airport_is_in_demand_universe(airport, universe_date):
    if (
        not isinstance(airport, Mapping)
        or airport.get("passenger_demand_eligible") is not True
    ):
        return False
    population = airport.get("population")
    latitude = airport.get("latitude_microdegrees")
    longitude = airport.get("longitude_microdegrees")
    if (
        isinstance(population, bool)
        or not isinstance(population, int)
        or population <= 0
        or isinstance(latitude, bool)
        or not isinstance(latitude, int)
        or not -90_000_000 <= latitude <= 90_000_000
        or isinstance(longitude, bool)
        or not isinstance(longitude, int)
        or not -180_000_000 <= longitude <= 180_000_000
        or not isinstance(airport.get("country_reference"), str)
        or not airport["country_reference"].strip()
        or airport.get("demand_destination_type") not in DEMAND_DESTINATION_TYPES
    ):
        return False
    active_from = airport.get("active_from_date")
    active_until = airport.get("active_until_date")
    try:
        parsed_universe = date.fromisoformat(universe_date)
        parsed_from = (
            date.fromisoformat(active_from) if active_from is not None else None
        )
        parsed_until = (
            date.fromisoformat(active_until) if active_until is not None else None
        )
    except (TypeError, ValueError):
        return False
    if (
        parsed_universe.isoformat() != universe_date
        or (parsed_from is not None and parsed_from.isoformat() != active_from)
        or (parsed_until is not None and parsed_until.isoformat() != active_until)
    ):
        return False
    return not (
        parsed_from is not None and parsed_universe < parsed_from
    ) and not (
        parsed_until is not None and parsed_universe >= parsed_until
    )


def _country_pack_is_enabled_on(pack, universe_date):
    """Resolve the current status without applying a future transition early."""
    if not isinstance(pack, Mapping):
        return False
    status = pack.get("status")
    effective = pack.get("status_effective_date")
    if status == "ENABLED":
        return effective is None or effective <= universe_date
    if status == "DISABLED":
        return effective is not None and effective > universe_date
    return False


def _usable_direct_passenger_flight(
    envelope,
    flight_id,
    flight,
    window_start,
    window_end,
    *,
    duplicate_occurrence_keys=frozenset(),
):
    if not isinstance(flight_id, str) or not isinstance(flight, Mapping):
        return False
    if flight.get("dated_flight_id") != flight_id:
        return False
    if (
        flight.get("service_type") != "PASSENGER"
        or flight.get("passenger_service_classification") != "ECONOMY"
        or flight.get("status") not in ACTIVE_SERVICE_STATUSES
        or flight.get("superseded_by_schedule_revision") is not None
        or flight.get("occurrence_key") in duplicate_occurrence_keys
    ):
        return False
    capacity = flight.get("capacity")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        return False
    if not _valid_fare_offer(flight.get("fare_offer")):
        return False
    try:
        departure = parse_canonical_utc(
            flight.get("scheduled_off_block_utc"), "scheduled_off_block_utc"
        )
        arrival = parse_canonical_utc(
            flight.get("scheduled_in_block_utc"), "scheduled_in_block_utc"
        )
    except (TypeError, ValueError):
        return False
    if arrival <= departure:
        return False
    if not window_start <= departure <= window_end:
        return False

    state = envelope.get("world_state")
    if not isinstance(state, Mapping):
        return False
    origin = flight.get("origin_airport_id")
    destination = flight.get("destination_airport_id")
    airports = state.get("airports")
    if (
        not isinstance(airports, Mapping)
        or not isinstance(origin, str)
        or not isinstance(destination, str)
        or origin == destination
        or origin not in airports
        or destination not in airports
        or not isinstance(airports[origin], Mapping)
        or not isinstance(airports[destination], Mapping)
        or airports[origin].get("airport_id") != origin
        or airports[destination].get("airport_id") != destination
    ):
        return False

    airlines = state.get("airlines")
    aircraft = state.get("aircraft")
    airline_id = flight.get("airline_id")
    aircraft_id = flight.get("planned_aircraft_id")
    airline = airlines.get(airline_id) if isinstance(airlines, Mapping) else None
    aircraft_record = aircraft.get(aircraft_id) if isinstance(aircraft, Mapping) else None
    if (
        not isinstance(airlines, Mapping)
        or not isinstance(airline_id, str)
        or not isinstance(airline, Mapping)
        or airline.get("airline_id") != airline_id
        or not isinstance(aircraft, Mapping)
        or not isinstance(aircraft_id, str)
        or not isinstance(aircraft_record, Mapping)
        or aircraft_record.get("aircraft_id") != aircraft_id
        or aircraft_record.get("airline_id") != airline_id
        or flight["fare_offer"]["currency"] != airline.get("base_currency")
    ):
        return False

    connections = state.get("connections")
    markets = state.get("directional_markets")
    connection_id = flight.get("connection_id")
    if (
        not isinstance(connections, Mapping)
        or not isinstance(markets, Mapping)
        or connection_id not in connections
    ):
        return False
    connection = connections[connection_id]
    if not isinstance(connection, Mapping):
        return False
    market_id = connection.get("market_id")
    if not isinstance(market_id, str) or market_id not in markets:
        return False
    market = markets[market_id]
    if (
        not isinstance(market, Mapping)
        or connection.get("connection_id") != connection_id
        or connection.get("status") != "ACTIVE"
        or connection.get("airline_id") != airline_id
        or market.get("market_id") != market_id
        or market.get("origin_airport_id") != origin
        or market.get("destination_airport_id") != destination
    ):
        return False

    schedules = state.get("schedule_definitions")
    schedule_id = flight.get("schedule_id")
    schedule_revision = flight.get("schedule_revision")
    if not isinstance(schedules, Mapping) or schedule_id not in schedules:
        return False
    schedule = schedules[schedule_id]
    if not isinstance(schedule, Mapping):
        return False
    revisions = schedule.get("revisions")
    revision = revisions.get(str(schedule_revision)) if isinstance(revisions, Mapping) else None
    if (
        schedule.get("schedule_id") != schedule_id
        or schedule.get("airline_id") != airline_id
        or (
            flight.get("status") == "PLANNED"
            and schedule.get("status") != "ACTIVE"
        )
        or not isinstance(revisions, Mapping)
        or isinstance(schedule_revision, bool)
        or not isinstance(schedule_revision, int)
        or str(schedule_revision) not in revisions
        or not isinstance(revision, Mapping)
        or revision.get("revision") != schedule_revision
    ):
        return False
    try:
        parse_canonical_utc(flight.get("published_at_utc"), "published_at_utc")
    except (TypeError, ValueError):
        return False
    return _schedule_trace_is_valid(envelope, flight, revision)


class DirectPublishedServiceActivationProvider:
    """Discover direct markets from usable published passenger occurrences."""

    def active_market_ids(
        self,
        envelope,
        window: ActivationWindow,
        *,
        dated_flight_indexes: DatedFlightIndexes | None = None,
    ):
        flights = envelope.get("world_state", {}).get("dated_flights", {})
        if not isinstance(flights, Mapping):
            return ()
        try:
            window_start = parse_canonical_utc(window.start_utc)
            window_end = parse_canonical_utc(window.end_utc)
        except (AttributeError, TypeError, ValueError):
            return ()
        authoritative_candidate_ids = tuple(
            sorted(
                flight_id
                for flight_id, flight in flights.items()
                if isinstance(flight_id, str)
                and isinstance(flight, Mapping)
                and flight.get("service_type") == "PASSENGER"
                and flight.get("status") in ACTIVE_SERVICE_STATUSES
            )
        )
        indexes = dated_flight_indexes
        indexed_candidate_ids = ()
        if isinstance(indexes, DatedFlightIndexes):
            indexed_candidate_ids = tuple(
                sorted(
                    {
                        flight_id
                        for flight_ids in indexes.direct_services_by_market.values()
                        for flight_id in flight_ids
                        if isinstance(flight_id, str)
                    }
                )
            )
        candidate_ids = (
            indexed_candidate_ids
            if indexed_candidate_ids == authoritative_candidate_ids
            else authoritative_candidate_ids
        )
        occurrence_counts = {}
        for flight in flights.values():
            if not isinstance(flight, Mapping):
                continue
            occurrence_key = flight.get("occurrence_key")
            if isinstance(occurrence_key, str):
                occurrence_counts[occurrence_key] = occurrence_counts.get(occurrence_key, 0) + 1
        duplicate_occurrence_keys = frozenset(
            key for key, count in occurrence_counts.items() if count > 1
        )
        state = envelope.get("world_state", {})
        connections = state.get("connections", {}) if isinstance(state, Mapping) else {}
        market_ids = {
            connections[flight["connection_id"]]["market_id"]
            for flight_id in candidate_ids
            if (flight := flights.get(flight_id)) is not None
            and _usable_direct_passenger_flight(
                envelope,
                flight_id,
                flight,
                window_start,
                window_end,
                duplicate_occurrence_keys=duplicate_occurrence_keys,
            )
        }
        return tuple(sorted(market_ids))


DIRECT_PUBLISHED_SERVICE_PROVIDER = DirectPublishedServiceActivationProvider()


def discover_active_market_ids(
    envelope,
    *,
    start_utc=None,
    end_utc=None,
    providers: Sequence[DemandActivationProvider] | None = None,
    dated_flight_indexes: DatedFlightIndexes | None = None,
    require_model4_pack_authority=False,
):
    """Return activated authoritative market IDs in stable immutable-ID order.

    The default window is the current simulation instant through Scheduling's
    configured publication horizon.  Passing an explicit window lets Booking
    later impose its own horizon without moving that policy into Demand.
    """
    start_utc = (
        envelope.get("simulation", {}).get("time_utc")
        if start_utc is None
        else start_utc
    )
    end_utc = (
        configured_publication_horizon_utc(envelope)
        if end_utc is None
        else end_utc
    )
    window = ActivationWindow(start_utc, end_utc)
    providers = (
        (DIRECT_PUBLISHED_SERVICE_PROVIDER,)
        if providers is None
        else tuple(providers)
    )
    active_market_ids = set()
    custom_market_ids = set()
    for provider in providers:
        provider_envelope = (
            envelope
            if type(provider) is DirectPublishedServiceActivationProvider
            else deepcopy(envelope)
        )
        provider_snapshot = deepcopy(provider_envelope)
        try:
            provided = provider.active_market_ids(
                provider_envelope,
                window,
                dated_flight_indexes=dated_flight_indexes,
            )
            if isinstance(provided, (str, bytes)):
                raise ValueError("activation provider results must be an iterable of market IDs")
            provided = tuple(provided)
            active_market_ids.update(provided)
            if type(provider) is not DirectPublishedServiceActivationProvider:
                custom_market_ids.update(provided)
            if require_model4_pack_authority and provider_envelope != provider_snapshot:
                raise ValueError("activation provider mutated its detached state")
        except Exception as exc:
            raise ValueError(f"invalid activation provider result: {exc}") from exc

    markets = envelope.get("world_state", {}).get("directional_markets", {})
    state = envelope.get("world_state", {})
    airports = state.get("airports", {}) if isinstance(state, Mapping) else {}
    demand_state = state.get("demand_state", {}) if isinstance(state, Mapping) else {}
    universe_date = (
        envelope.get("simulation", {}).get("time_utc", "")[:10]
        if require_model4_pack_authority
        else demand_state.get("universe_date") if isinstance(demand_state, Mapping) else None
    )
    if (
        not isinstance(markets, Mapping)
        or not isinstance(airports, Mapping)
        or not isinstance(universe_date, str)
    ):
        return ()
    eligible_market_ids = []
    rejected_market_ids = []
    pack_configuration = envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("market_pack_configuration", {})
    packs = pack_configuration.get("market_packs", {}) if isinstance(pack_configuration, Mapping) else {}
    enabled_country_ids = {
        pack.get("country_id")
        for pack in packs.values()
        if isinstance(pack, Mapping)
        and _country_pack_is_enabled_on(pack, universe_date)
    }
    mapped_airport_ids = {
        airport_id
        for pack in packs.values()
        if isinstance(pack, Mapping)
        for airport_id in pack.get("airport_id_by_catalog_id", {}).values()
    }
    # Schema-2 foundation airports predate 4.5B-3 catalog mappings. They remain
    # an already-materialized enabled compatibility pack until explicitly
    # represented by lifecycle authority; countries with no airports stay latent.
    enabled_country_ids.update(
        airport.get("country_id")
        for airport_id, airport in airports.items()
        if isinstance(airport, Mapping)
        and airport.get("demand_allocation_member") is True
        and airport_id not in mapped_airport_ids
    )
    for market_id in sorted(
        key for key in active_market_ids if isinstance(key, str)
    ):
        market = markets.get(market_id)
        if not isinstance(market, Mapping):
            continue
        origin = market.get("origin_airport_id")
        destination = market.get("destination_airport_id")
        if (
            market.get("market_id") == market_id
            and isinstance(origin, str)
            and isinstance(destination, str)
            and origin != destination
            and origin in airports
            and destination in airports
            and isinstance(airports[origin], Mapping)
            and isinstance(airports[destination], Mapping)
            and airports[origin].get("airport_id") == origin
            and airports[destination].get("airport_id") == destination
            and _airport_is_in_demand_universe(airports[origin], universe_date)
            and _airport_is_in_demand_universe(airports[destination], universe_date)
            and (
                not require_model4_pack_authority
                or (
                    airports[origin].get("country_id") in enabled_country_ids
                    and airports[destination].get("country_id") in enabled_country_ids
                    and airports[origin].get("demand_allocation_member") is True
                    and airports[destination].get("demand_allocation_member") is True
                )
            )
        ):
            eligible_market_ids.append(market_id)
        else:
            rejected_market_ids.append(market_id)
    if require_model4_pack_authority:
        unknown = sorted(
            market_id
            for market_id in custom_market_ids
            if not isinstance(market_id, str) or market_id not in markets
        )
        if unknown:
            raise ValueError(f"UNAVAILABLE_DEMAND_MARKET: unknown activation-provider markets: {unknown!r}")
        rejected_custom = sorted(set(rejected_market_ids) & custom_market_ids)
        if rejected_custom:
            raise ValueError(f"UNAVAILABLE_DEMAND_MARKET: unavailable activation-provider markets: {rejected_custom!r}")
        if custom_market_ids:
            direct_ids = set(
                DIRECT_PUBLISHED_SERVICE_PROVIDER.active_market_ids(
                    envelope, window, dated_flight_indexes=dated_flight_indexes
                )
            )
            unserved = sorted(custom_market_ids - direct_ids)
            if unserved:
                raise ValueError(f"UNAVAILABLE_DEMAND_MARKET: markets lack valid direct published passenger service: {unserved!r}")
    return tuple(eligible_market_ids)
