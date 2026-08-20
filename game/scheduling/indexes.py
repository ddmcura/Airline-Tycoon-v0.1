"""Rebuildable runtime indexes over authoritative dated flights."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from game.world_state.timestamps import parse_canonical_utc


ACTIVE_SERVICE_STATUSES = frozenset({"PLANNED", "OPERATIONALLY_LOCKED"})


def _validated_range(start_utc, end_utc):
    start = parse_canonical_utc(start_utc, "start_utc")
    end = parse_canonical_utc(end_utc, "end_utc")
    if end < start:
        raise ValueError("end_utc cannot precede start_utc")


def _freeze_lists(values):
    return MappingProxyType(
        {
            key: tuple(item[1] for item in sorted(items))
            for key, items in sorted(values.items(), key=lambda pair: repr(pair[0]))
        }
    )


@dataclass(frozen=True)
class DatedFlightIndexes:
    """Disposable indexes; none of these mappings belong in saved authority."""

    by_origin: Mapping[str, tuple[str, ...]]
    direct_services_by_market: Mapping[tuple[str, str], tuple[str, ...]]
    by_airline: Mapping[str, tuple[str, ...]]
    by_aircraft: Mapping[str, tuple[str, ...]]
    by_schedule: Mapping[str, tuple[str, ...]]
    by_occurrence_key: Mapping[str, str]
    departure_utc_by_id: Mapping[str, str]

    def departures_from(self, origin_airport_id, start_utc, end_utc):
        """Return indexed departures in the inclusive canonical UTC range."""
        _validated_range(start_utc, end_utc)
        return tuple(
            flight_id
            for flight_id in self.by_origin.get(origin_airport_id, ())
            if start_utc <= self.departure_utc_by_id[flight_id] <= end_utc
        )

    def direct_services(self, origin_airport_id, destination_airport_id, start_utc, end_utc):
        """Return active passenger services for one direction and UTC range."""
        _validated_range(start_utc, end_utc)
        return tuple(
            flight_id
            for flight_id in self.direct_services_by_market.get(
                (origin_airport_id, destination_airport_id), ()
            )
            if start_utc <= self.departure_utc_by_id[flight_id] <= end_utc
        )


def rebuild_dated_flight_indexes(envelope):
    """Deterministically rebuild indexes without mutating authoritative state."""
    origins = {}
    markets = {}
    airlines = {}
    aircraft = {}
    schedules = {}
    occurrence_keys = {}
    departure_times = {}
    flights = envelope["world_state"]["dated_flights"]
    for flight_id in sorted(flights):
        flight = flights[flight_id]
        departure = flight["scheduled_off_block_utc"]
        order_item = ((departure, flight_id), flight_id)
        origins.setdefault(flight["origin_airport_id"], []).append(order_item)
        airlines.setdefault(flight["airline_id"], []).append(order_item)
        aircraft.setdefault(flight["planned_aircraft_id"], []).append(order_item)
        schedules.setdefault(flight["schedule_id"], []).append(order_item)
        if (
            flight["service_type"] == "PASSENGER"
            and flight["status"] in ACTIVE_SERVICE_STATUSES
        ):
            market = (flight["origin_airport_id"], flight["destination_airport_id"])
            markets.setdefault(market, []).append(order_item)
        occurrence_key = flight["occurrence_key"]
        if occurrence_key in occurrence_keys:
            raise ValueError(f"duplicate occurrence key: {occurrence_key}")
        occurrence_keys[occurrence_key] = flight_id
        departure_times[flight_id] = departure
    return DatedFlightIndexes(
        by_origin=_freeze_lists(origins),
        direct_services_by_market=_freeze_lists(markets),
        by_airline=_freeze_lists(airlines),
        by_aircraft=_freeze_lists(aircraft),
        by_schedule=_freeze_lists(schedules),
        by_occurrence_key=MappingProxyType(dict(sorted(occurrence_keys.items()))),
        departure_utc_by_id=MappingProxyType(dict(sorted(departure_times.items()))),
    )
