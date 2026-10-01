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
from game.world_state.persistence import SaveStore, SaveError
from game.simulation.pacing import RuntimeController
from game.simulation.kernel import iter_events_through, begin_fast_forward, stop_fast_forward


@dataclass(frozen=True)
class AdvancementReport:
    result: object
    event_rows: tuple[dict, ...]


class Stage1Session:
    """Holds authority in memory; runtime preferences never enter the world."""

    def __init__(self, *, runtime_clock=None, save_root=None):
        scenario = load_stage1_scenario(STAGE1_SCENARIO_ID)
        self._display_rates = deepcopy(scenario["display_currencies"])
        self.world = None
        self.display_currency = "USD"
        self.changed = False
        self.runtime = None
        self.runtime_clock = runtime_clock
        self.on_advance_boundary = None
        self.save_store = SaveStore() if save_root is None else SaveStore(save_root)
        self.career_id = None
        self.progression_revision = 0
        self.unsaved_progress = False
        self._active_start_ns = None
        self._last_auto_active_ns = None
        self._last_auto_sim_time = None
        self.autosave_error = None

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
        self.career_id = self.save_store.new_career_id()
        self.progression_revision = 0
        self.unsaved_progress = True
        self.autosave_error = None
        self._reset_autosave_clocks()
        self.changed = True
        self._ensure_runtime()

    def _clock_ns(self):
        from game.simulation.pacing import active_monotonic_ns
        return (self.runtime_clock or active_monotonic_ns)()

    def _reset_autosave_clocks(self):
        self._active_start_ns = self._clock_ns()
        self._last_auto_active_ns = self._active_start_ns
        self._last_auto_sim_time = self.world['simulation']['time_utc']

    def _mark_progress(self):
        self.changed = True
        self.unsaved_progress = True
        self.progression_revision += 1

    def save_manual(self):
        if not self.active:
            raise SaveError('NO_GAME', 'No active game')
        now = self._clock_ns()
        self.save_store.save(self.career_id, 'manual', self.world,
                             progression_revision=self.progression_revision)
        self.unsaved_progress = False
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self.world['simulation']['time_utc']
        return self.career_id

    def save_bookmark(self, name):
        if not self.active:
            raise SaveError('NO_GAME', 'No active game')
        now = self._clock_ns()
        bookmark_id = self.save_store.save(self.career_id, 'bookmark', self.world,
                                           bookmark_name=name,
                                           progression_revision=self.progression_revision)
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self.world['simulation']['time_utc']
        return bookmark_id

    def load_saved(self, career_id, kind='manual', *, bookmark_id=None,
                   foundation_snapshot=None):
        candidate, data = self.save_store.load(career_id, kind, bookmark_id=bookmark_id,
                                                foundation_snapshot=foundation_snapshot)
        now = self._clock_ns()
        options = {} if self.runtime_clock is None else {'clock': self.runtime_clock}
        new_runtime = RuntimeController(candidate, **options)
        if self.runtime is not None:
            self.runtime.cancel_work()
            self.runtime.closed = True
        self.world = candidate
        self.career_id = career_id
        self.progression_revision = data['progression_revision']
        self.unsaved_progress = False
        self.autosave_error = None
        self.display_currency = 'USD'
        self.runtime = new_runtime
        self._active_start_ns = now
        self._last_auto_active_ns = now
        self._last_auto_sim_time = candidate['simulation']['time_utc']
        self.changed = True
        return data

    def list_careers(self):
        return self.save_store.list_careers()

    def list_bookmarks(self, career_id=None):
        return self.save_store.list_bookmarks(career_id or self.career_id)

    def newer_autosave(self, career_id):
        return self.save_store.newer_autosave(career_id)

    def maybe_autosave(self):
        if not self.active or self.career_id is None:
            return False
        now = self._clock_ns()
        elapsed_real = now - self._last_auto_active_ns
        elapsed_sim = (parse_canonical_utc(self.world['simulation']['time_utc']) -
                       parse_canonical_utc(self._last_auto_sim_time)).total_seconds()
        if elapsed_real < 15 * 60 * 1_000_000_000 and elapsed_sim < 7 * 86400:
            return False
        try:
            self.save_store.save(self.career_id, 'autosave', self.world,
                                 progression_revision=self.progression_revision)
        except SaveError as exc:
            self.autosave_error = f'{exc.code}: {exc}'
            self._last_auto_active_ns = now  # throttle repeated storage failures
            self._last_auto_sim_time = self.world['simulation']['time_utc']
            return False
        self.autosave_error = None
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self.world['simulation']['time_utc']
        return True

    def _ensure_runtime(self):
        if self.runtime is not None and self.runtime.world is self.world:
            return
        if self.runtime is not None:
            self.runtime.cancel_work()
            self.runtime.closed = True
        options = {} if self.runtime_clock is None else {'clock': self.runtime_clock}
        self.runtime = RuntimeController(self.world, **options)

    def resume(self):
        self._ensure_runtime()
        before = (self.world['simulation']['clock_state'],
                  self.world['simulation']['configuration']['clock_ratios']['NORMAL'])
        self.runtime.resume()
        after = (self.world['simulation']['clock_state'],
                 self.world['simulation']['configuration']['clock_ratios']['NORMAL'])
        if after != before:
            self._mark_progress()

    def pause(self):
        self._ensure_runtime()
        before = self.world['simulation']['clock_state']
        self.runtime.pause()
        if self.world['simulation']['clock_state'] != before:
            self._mark_progress()

    def close(self):
        if self.runtime is not None:
            self.runtime.close()

    def leave_game(self):
        if self.runtime is not None:
            self.runtime.close()
        self.world = None
        self.runtime = None
        self.career_id = None
        self.unsaved_progress = False

    def pump(self):
        if not self.active:
            return None
        self._ensure_runtime()
        result = self.runtime.pump()
        if result is not None:
            self._mark_progress()
        self.maybe_autosave()
        return result

    def _management_changed(self):
        self._mark_progress()
        if self.runtime is not None:
            self.runtime.management_changed()

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
            self._management_changed()
        return aircraft_id

    def leasing_offers(self):
        state = self.world['world_state']
        return tuple(deepcopy(state['aircraft_lease_offers'][key]) for key in
                     state['aircraft_market_state']['active_lease_offer_ids'])

    def used_listings(self):
        today = date.fromisoformat(self.world['simulation']['time_utc'][:10])
        rows = []
        for _key, record in sorted(self.world['world_state']['used_aircraft_listings'].items()):
            if record['status'] != 'ACTIVE':
                continue
            row = deepcopy(record)
            made = date.fromisoformat(row['manufactured_date'])
            row['age_months'] = ((today.year - made.year) * 12 + today.month - made.month
                                 - (1 if today.day < made.day else 0))
            rows.append(row)
        return tuple(rows)

    def aircraft_contracts(self):
        return tuple(deepcopy(row) for _key, row in sorted(
            self.world['world_state']['aircraft_contracts'].items())
            if row['airline_id'] == self.airline_id and row['status'] in {'ACTIVE', 'FUTURE'})

    def preview_lease(self, offer_id, contract_type, term_years, delivery_airport_id):
        from game.aircraft_market.step5 import preview_lease
        return preview_lease(self.world, airline_id=self.airline_id, offer_id=offer_id,
            contract_type=contract_type, term_years=term_years,
            delivery_airport_id=delivery_airport_id)

    def accept_lease(self, preview):
        from game.aircraft_market.step5 import accept_lease
        aircraft_id = accept_lease(self.world, preview)
        self.changed = True
        self._management_changed()
        return aircraft_id

    def preview_used_purchase(self, listing_id, delivery_airport_id):
        from game.aircraft_market.step5 import preview_used_purchase
        return preview_used_purchase(self.world, airline_id=self.airline_id,
            listing_id=listing_id, delivery_airport_id=delivery_airport_id)

    def purchase_used(self, preview):
        from game.aircraft_market.step5 import purchase_used_aircraft
        aircraft_id = purchase_used_aircraft(self.world, preview)
        self.changed = True
        self._management_changed()
        return aircraft_id

    def renew_operating_lease(self, aircraft_id, term_years, command_id,
                              expected_world_fingerprint=None):
        from game.aircraft_market.step5 import renew_operating_lease
        if expected_world_fingerprint is None:
            expected_world_fingerprint = self.preview_operating_renewal(
                aircraft_id, term_years).world_fingerprint
        result = renew_operating_lease(self.world, aircraft_id=aircraft_id,
                                       term_years=term_years, command_id=command_id,
                                       expected_world_fingerprint=expected_world_fingerprint)
        self.changed = True
        self._management_changed()
        return result

    def preview_operating_renewal(self, aircraft_id, term_years):
        from game.aircraft_market.step5 import preview_operating_renewal
        return preview_operating_renewal(self.world, aircraft_id=aircraft_id,
                                         term_years=term_years)

    def terminate_contract(self, aircraft_id, command_id):
        from game.aircraft_market.step5 import terminate_contract
        result = terminate_contract(self.world, aircraft_id=aircraft_id,
                                    command_id=command_id)
        self.changed = True
        self._management_changed()
        return result

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
            self._management_changed()
        elif self.authoritative_bytes() != before:
            raise RuntimeError("rejected rotation mutated authoritative state")
        return result

    def begin_scheduling(self, aircraft_id):
        from game.scheduling.weekly import WeeklyDraft
        return WeeklyDraft(self.world, airline_id=self.airline_id, aircraft_id=aircraft_id)

    def save_scheduling(self, draft, *, repeat_until=None):
        result = draft.save_current(self.world, repeat_until=repeat_until)
        self.changed = True
        self._management_changed()
        return result

    def publish_next_rotation(self):
        before = self.authoritative_bytes()
        result = publish_next_rotation(self.world, airline_id=self.airline_id)
        if result.succeeded:
            self.changed = True
            self._management_changed()
        elif self.authoritative_bytes() != before:
            raise RuntimeError("rejected publication mutated authoritative state")
        return result

    def _report(self, result):
        ids = tuple(result.completed_event_ids) + tuple(result.skipped_event_ids)
        rows = project_event_records(self.world, ids) or []
        if result.completed_event_ids or result.skipped_event_ids or (
            result.ended_at_utc != result.started_at_utc
        ):
            self._mark_progress()
        return AdvancementReport(result, tuple(rows))

    def advance_next_event(self):
        self._manual_start()
        try:
            return self._report(process_next_event(self.world))
        finally:
            stop_fast_forward(self.world)
            self._last_auto_sim_time = self.world['simulation']['time_utc']

    def _manual_start(self):
        self.pause()
        self.runtime.cancel_work()
        # An explicit time jump replaces the outstanding pacing target.
        self.runtime.credit_ns = 0

    def advance_seconds(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
            raise ValueError("advance duration must be positive whole seconds")
        target = format_utc(
            parse_canonical_utc(self.world["simulation"]["time_utc"])
            + timedelta(seconds=seconds)
        )
        return self.advance_to(target)

    def advance_to(self, target_time_utc):
        target = parse_canonical_utc(target_time_utc)
        if target < parse_canonical_utc(self.world['simulation']['time_utc']):
            raise ValueError('simulation time cannot move backward')
        self._manual_start()
        begin_fast_forward(self.world, target_time_utc)
        work = iter_events_through(self.world, target_time_utc)
        try:
            while True:
                try:
                    next(work)
                except StopIteration as done:
                    return self._report(done.value)
                if self.on_advance_boundary is not None:
                    self.on_advance_boundary()
        finally:
            work.close()
            stop_fast_forward(self.world)
            self._last_auto_sim_time = self.world['simulation']['time_utc']

    def validate(self):
        if self.world is None:
            return True
        return validate_world(self.world).is_valid


__all__ = ("AdvancementReport", "Stage1Session")
