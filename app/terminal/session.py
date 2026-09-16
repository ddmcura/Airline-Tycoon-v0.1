"""Runtime-only owner for one temporary deterministic terminal session."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
import json

from game.aircraft_operations import (
    project_airline_fleet,
    project_airline_flights,
    project_airline_overview,
    project_recent_flight_results,
)
from game.aircraft_market.reference_catalog import (
    PH_AIRCRAFT_CATALOG_VERSION,
    load_aircraft_catalog,
)
from game.demand import project_market_opportunities
from game.scheduling import (
    create_weekly_round_trip_rotation,
    publish_next_rotation,
)
from game.simulation import (
    process_events_through,
    process_next_event,
    project_event_records,
    project_next_pending_event,
)
from game.world_state import (
    STAGE1_SCENARIO_ID,
    active_stage1_airports,
    create_stage1_new_game,
    load_stage1_scenario,
    validate_world,
)
from game.world_state.timestamps import format_utc, parse_canonical_utc


@dataclass(frozen=True)
class AdvancementReport:
    result: object
    event_rows: tuple[dict, ...]


class Stage1Session:
    """Holds authority in memory; runtime preferences never enter the world."""

    def __init__(self):
        scenario = load_stage1_scenario(STAGE1_SCENARIO_ID)
        self._display_rates = deepcopy(scenario["display_currencies"])
        self.world = None
        self.display_currency = "USD"
        self.changed = False

    @property
    def active(self):
        return self.world is not None

    @property
    def airline_id(self):
        if self.world is None:
            return None
        return self.world["world_state"]["player"]["primary_airline_id"]

    @property
    def display_rates(self):
        return deepcopy(self._display_rates)

    def new_game(self, ceo_display_name, airline_display_name, base_code):
        self.world = create_stage1_new_game(
            scenario_id=STAGE1_SCENARIO_ID,
            ceo_display_name=ceo_display_name,
            airline_display_name=airline_display_name,
            base_airport_reference_code=base_code,
        )
        self.display_currency = "USD"
        self.changed = True

    def available_airports(self):
        return tuple(
            {
                "reference_code": record["reference_code"],
                "display_name": record["display_name"],
                "city": record["city"],
            }
            for record in active_stage1_airports()
        )

    def airports(self):
        if self.world is None:
            return self.available_airports()
        return tuple(
            {
                "airport_id": airport_id,
                "reference_code": airport["reference_code"],
                "display_name": airport["display_name"],
                "city": airport.get("city"),
            }
            for airport_id, airport in sorted(
                self.world["world_state"]["airports"].items(),
                key=lambda item: (item[1]["reference_code"], item[0]),
            )
            if airport.get("demand_allocation_member") is True
            and airport.get("passenger_demand_eligible") is True
        )

    def market_opportunities(self, *, origin_airport_id=None, limit=100):
        return project_market_opportunities(
            self.world, origin_airport_id=origin_airport_id, limit=limit
        )

    def authoritative_bytes(self):
        if self.world is None:
            return b""
        return json.dumps(
            self.world, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")

    def aircraft_catalog(self):
        """Load detached reference content only when the player opens the catalog."""
        return load_aircraft_catalog(catalog_version=PH_AIRCRAFT_CATALOG_VERSION)

    def set_display_currency(self, currency):
        if currency not in self._display_rates:
            raise ValueError("unsupported display currency")
        self.display_currency = currency

    def overview(self):
        return project_airline_overview(self.world, self.airline_id)

    def fleet(self, *, offset=0, limit=20):
        return project_airline_fleet(self.world, self.airline_id, offset=offset, limit=limit)

    def delivery_locations(self):
        from game.fleet_management.acquisition import delivery_locations
        ids = delivery_locations(self.world['world_state'], self.airline_id)
        return tuple(a for a in self.airports() if a['airport_id'] in ids)

    def preview_purchase(self, model_id, delivery_airport_id):
        from game.aircraft_market.acquisition import preview_purchase
        return preview_purchase(self.world, airline_id=self.airline_id,
            model_id=model_id, catalog_version=PH_AIRCRAFT_CATALOG_VERSION,
            delivery_airport_id=delivery_airport_id)

    def purchase(self, preview):
        from game.aircraft_market.acquisition import purchase_aircraft
        before = self.authoritative_bytes()
        aircraft_id = purchase_aircraft(self.world, preview)
        if before != self.authoritative_bytes():
            self.changed = True
        return aircraft_id

    def flights(self):
        return project_airline_flights(self.world, self.airline_id, limit=20)

    def finances(self):
        return project_recent_flight_results(self.world, self.airline_id, limit=10)

    def next_event(self):
        return project_next_pending_event(self.world)

    def default_operating_date(self):
        current = date.fromisoformat(self.world["simulation"]["time_utc"][:10])
        return (current + timedelta(days=6)).isoformat()

    def plan_rotation(self, aircraft_id, destination_code, fare_minor, operating_date):
        before = self.authoritative_bytes()
        result = create_weekly_round_trip_rotation(
            self.world,
            airline_id=self.airline_id,
            aircraft_id=aircraft_id,
            destination_airport_reference_code=destination_code,
            fare_minor=fare_minor,
            first_operating_date=operating_date,
        )
        if result.succeeded:
            self.changed = True
        elif self.authoritative_bytes() != before:
            raise RuntimeError("rejected rotation mutated authoritative state")
        return result

    def begin_scheduling(self, aircraft_id):
        from game.scheduling.weekly import WeeklyDraft
        return WeeklyDraft(self.world, airline_id=self.airline_id, aircraft_id=aircraft_id)

    def save_scheduling(self, draft, *, repeat_until=None):
        result = draft.save(self.world, repeat_until=repeat_until)
        self.changed = True
        return result

    def publish_next_rotation(self):
        before = self.authoritative_bytes()
        result = publish_next_rotation(self.world, airline_id=self.airline_id)
        if result.succeeded:
            self.changed = True
        elif self.authoritative_bytes() != before:
            raise RuntimeError("rejected publication mutated authoritative state")
        return result

    def _report(self, result):
        ids = tuple(result.completed_event_ids) + tuple(result.skipped_event_ids)
        rows = project_event_records(self.world, ids) or []
        if result.completed_event_ids or result.skipped_event_ids or (
            result.ended_at_utc != result.started_at_utc
        ):
            self.changed = True
        return AdvancementReport(result, tuple(rows))

    def advance_next_event(self):
        return self._report(process_next_event(self.world))

    def advance_seconds(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
            raise ValueError("advance duration must be positive whole seconds")
        target = format_utc(
            parse_canonical_utc(self.world["simulation"]["time_utc"])
            + timedelta(seconds=seconds)
        )
        return self.advance_to(target)

    def advance_to(self, target_time_utc):
        return self._report(process_events_through(self.world, target_time_utc))

    def validate(self):
        if self.world is None:
            return True
        return validate_world(self.world).is_valid


__all__ = ("AdvancementReport", "Stage1Session")
