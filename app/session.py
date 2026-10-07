"""Application-owned PH career session shared by graphical and terminal clients."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
import json

from game.aircraft_operations import (
    project_airline_overview,
)
from .owned_reads import _OwnedReadViews
from game.aircraft_operations.projections import (
    _project_owned_airline_header, _project_owned_scheduling_aircraft)
from game.simulation.projections import _project_event_records_owned, _project_next_pending_event_owned
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
from game.simulation.speeds import PLAYER_SPEEDS
from game.simulation.pacing import RuntimeController
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.kernel import (
    begin_fast_forward, stop_fast_forward, DEFAULT_MAX_EVENTS_PER_ADVANCE)
from game.simulation.resolver import begin_resolution, resolve_next_event


@dataclass(frozen=True)
class AdvancementReport:
    result: object
    event_rows: tuple[dict, ...]


class Stage1Session:
    """Holds authority in memory; runtime preferences never enter the world."""

    def __init__(self, *, runtime_clock=None, save_root=None):
        initialize_runtime_handlers()
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
        self._bulk_work = None

    @property
    def world(self):
        """Borrowed authority for existing commands; callers must not write rows.

        Rebinding arbitrary input revokes read trust. Production mutations are
        serialized session/domain commands, never frontend writes.
        """
        return self._world

    @world.setter
    def world(self, value):
        self._world = value
        self._read_views = None

    def _bind_owned_reads(self):
        self._read_views = _OwnedReadViews(self.world, self.progression_revision)

    def _owned_reads(self):
        if not self.active:
            return None
        if self._read_views is None or not self._read_views.matches(
                self.world, self.progression_revision):
            # A foreign replacement has no session commit proof. Public/external
            # bindings keep the complete gate, once before acquiring ownership.
            self._read_views = None
            try:
                valid = validate_world(self.world).is_valid
            except Exception:
                valid = False
            if not valid:
                return None
            self._bind_owned_reads()
        return self._read_views

    @property
    def runtime_speed(self):
        return self.runtime.selected_speed if self.runtime else PLAYER_SPEEDS[0]

    @property
    def runtime_status(self):
        if not self.active:
            return 'No active career'
        self._ensure_runtime()
        return self.runtime.status_text

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
        self._bind_owned_reads()

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
        # Known successful session commands/events already passed their owning
        # gate. Discard the complete old epoch, including all pages and IDs.
        # A foreign binding never acquires trust through this notification alone.
        self._refresh_owned_reads()

    def _refresh_owned_reads(self):
        if self._read_views is not None:
            self._bind_owned_reads()

    def save_manual(self):
        if self._bulk_work is not None:
            raise SaveError('ADVANCEMENT_ACTIVE', 'Finish or cancel advancement before saving')
        if not self.active:
            raise SaveError('NO_GAME', 'No active game')
        self._save_boundary()
        now = self._clock_ns()
        self.save_store.save(self.career_id, 'manual', self.world,
                             progression_revision=self.progression_revision)
        self.unsaved_progress = False
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self.world['simulation']['time_utc']
        return self.career_id

    def _save_boundary(self):
        # Normal requests stop accrual and finish owed work before manual storage.
        # Errors remain savable at their last valid committed prefix; no debt is
        # serialized. A frontend may defer/retry this same existing save command.
        self.pause()
        if self.runtime.draining:
            raise SaveError('RUNTIME_DRAINING', 'Draining earned time; retry Save when paused')

    def resolve_departure(self, choice):
        """Apply an explicit Save/discard/cancel choice before leaving a career."""
        if not self.active or not self.unsaved_progress:
            return True
        if choice == 'save':
            self.save_manual()
            return True
        return choice == 'discard'

    def save_bookmark(self, name):
        if self._bulk_work is not None:
            raise SaveError('ADVANCEMENT_ACTIVE', 'Finish or cancel advancement before bookmarking')
        if not self.active:
            raise SaveError('NO_GAME', 'No active game')
        self._save_boundary()
        now = self._clock_ns()
        bookmark_id = self.save_store.save(self.career_id, 'bookmark', self.world,
                                           bookmark_name=name,
                                           progression_revision=self.progression_revision)
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self.world['simulation']['time_utc']
        return bookmark_id

    def load_saved(self, career_id, kind='manual', *, bookmark_id=None,
                   foundation_snapshot=None):
        if self._bulk_work is not None:
            raise SaveError('ADVANCEMENT_ACTIVE', 'Finish or cancel advancement before loading')
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
        self._bind_owned_reads()
        return data

    def list_careers(self):
        return self.save_store.list_careers()

    def list_bookmarks(self, career_id=None):
        return self.save_store.list_bookmarks(career_id or self.career_id)

    def delete_bookmark(self, bookmark_id):
        if not self.active:
            raise SaveError('NO_GAME', 'No active game')
        return self.save_store.delete_bookmark(self.career_id, bookmark_id)

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

    def resume(self, speed=None):
        self._ensure_runtime()
        before = (self.world['simulation']['clock_state'],
                  self.world['simulation']['configuration']['clock_ratios']['NORMAL'])
        self.runtime.resume(speed)
        after = (self.world['simulation']['clock_state'],
                 self.world['simulation']['configuration']['clock_ratios']['NORMAL'])
        if after != before:
            self._mark_progress()

    def pause(self):
        self._ensure_runtime()
        before = self.world['simulation']['clock_state']
        if self._bulk_work is not None:
            self.runtime.hard_pause()  # Explicit Advance cancellation boundary.
        else:
            self.runtime.pause()
        if self.world['simulation']['clock_state'] != before:
            self._mark_progress()

    def hard_pause(self):
        self._ensure_runtime()
        before = self.world['simulation']['clock_state']
        self.runtime.hard_pause()
        if self.world['simulation']['clock_state'] != before:
            self._mark_progress()

    def close(self):
        self.cancel_advance()
        if self.runtime is not None:
            self.runtime.close()

    def leave_game(self):
        self.cancel_advance()
        if self.runtime is not None:
            self.runtime.close()
        self.world = None
        self.runtime = None
        self.career_id = None
        self.unsaved_progress = False

    def pump(self):
        if not self.active:
            return None
        if self._bulk_work is not None:
            return None
        self._ensure_runtime()
        before = (self.runtime.commit_serial, self.world['simulation']['clock_state'])
        try:
            result = self.runtime.pump()
        finally:
            if (self.runtime.commit_serial, self.world['simulation']['clock_state']) != before:
                # One epoch notification per safe unit, never speculative reads.
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
                "timezone": airport["timezone"],
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

    def suggested_economy_fare(self, origin_airport_id, destination_airport_id):
        from game.economy.fare_reference import suggested_economy_fare_minor

        return suggested_economy_fare_minor(
            self.world["world_state"], origin_airport_id, destination_airport_id
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

    def header(self):
        """Fresh bounded identity/cash read for the application-owned world."""
        return _project_owned_airline_header(self.world, self.airline_id)

    def fleet(self, *, offset=0, limit=20):
        from game.aircraft_operations.projections import _page_options
        _page_options(limit, offset)
        views = self._owned_reads()
        return views.fleet(self.airline_id, offset=offset, limit=limit) if views else None

    def management_fleet(self):
        if self._owned_reads() is None: raise ValueError("no valid active career")
        from game.fleet_management.management_projection import _project_management_fleet_owned
        return _project_management_fleet_owned(self.world, self.airline_id)

    def aircraft_details(self, aircraft_id):
        if self._owned_reads() is None: raise ValueError("no valid active career")
        from game.fleet_management.management_projection import _project_aircraft_details_owned
        return _project_aircraft_details_owned(self.world, self.airline_id, aircraft_id)

    def compatible_aircraft(self, origin_id, destination_id):
        if self._owned_reads() is None: raise ValueError("no valid active career")
        from game.scheduling.route_compatibility import compatible_aircraft
        return compatible_aircraft(self.world, self.airline_id, origin_id, destination_id)

    def scheduling_aircraft(self, aircraft_id):
        """Fresh detached row for the planner; command boundaries own validation."""
        return _project_owned_scheduling_aircraft(self.world, self.airline_id, aircraft_id)

    def quarterly_plan_dependencies(self, weekly_plan_id, *, expected_revision,
                                    revision=None, slot_keys=None, compare_with=()):
        """Dormant immutable reads; comparisons cover explicitly supplied versions only."""
        from game.scheduling.quarterly_reads import (
            PlanReadRequest, QuarterlyReadResult, ReadIssue, resolve_quarterly_reads,
        )
        if self._owned_reads() is None:
            return QuarterlyReadResult(issues=(ReadIssue(
                'INVALID_WORLD', 'session', 'no valid active career'),))
        if type(compare_with) is not tuple:
            return QuarterlyReadResult(issues=(ReadIssue(
                'INVALID_REQUEST', 'compare_with', 'immutable comparison requests required'),))
        request = PlanReadRequest(weekly_plan_id, expected_revision, revision, slot_keys)
        return resolve_quarterly_reads(self.world, airline_id=self.airline_id,
                                      selections=(request, *compare_with))

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

    def flights(self, *, offset=0, limit=20):
        from game.aircraft_operations.projections import _page_options
        _page_options(limit, offset)
        views = self._owned_reads()
        return views.flights(self.airline_id, offset=offset, limit=limit) if views else None

    def operational_context(self):
        if self._owned_reads() is None: raise ValueError('no valid active career')
        from game.aircraft_operations.management_projection import _operational_context_owned
        return _operational_context_owned(self.world,self.airline_id)

    def operational_flights(self, start_date, *, days=1, market=None, include_spanning=False):
        if type(days) is not int or days not in (1,7): raise ValueError('query one day or one week')
        views=self._owned_reads()
        if views is None: raise ValueError('no valid active career')
        return views.operational_rows(self.airline_id,start_date,days,market,include_spanning)

    def service_markets(self):
        views=self._owned_reads()
        if views is None: raise ValueError('no valid active career')
        return views.service_markets(self.airline_id)

    def finances(self):
        views = self._owned_reads()
        return views.finances(self.airline_id) if views else None

    def next_event(self):
        return project_next_pending_event(self.world)

    def next_event_for_display(self):
        """Fresh bounded read of session-owned pending events for GUI refresh."""
        return _project_next_pending_event_owned(self.world)

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

    def local_datetime(self, airport_id=None):
        from game.scheduling.local_time import airport_local
        if airport_id is None:
            airport_id = self.world['world_state']['airlines'][self.airline_id]['base_airport_ids'][0]
        return airport_local(self.world['world_state'], airport_id, self.world['simulation']['time_utc'])

    def local_clock(self, airport_id=None):
        local = self.local_datetime(airport_id)
        return f"{local:%Y-%m-%d %H:%M:%S} {local.tzinfo.key}"

    def has_recurring_pattern(self, aircraft_id):
        from game.scheduling.recurrence import rolling_schedules
        return bool(rolling_schedules(self.world, self.airline_id, aircraft_id))

    def begin_scheduling(self, aircraft_id, *, edit_recurring=False):
        from game.scheduling.weekly import WeeklyDraft
        factory = WeeklyDraft.edit_recurring if edit_recurring else WeeklyDraft
        return factory(self.world, airline_id=self.airline_id, aircraft_id=aircraft_id)

    def save_scheduling(self, draft, *, repeat_until=None, continuous=False):
        result = draft.save_current(self.world, repeat_until=repeat_until, continuous=continuous)
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
        rows = _project_event_records_owned(self.world, ids) if result.succeeded else (project_event_records(self.world, ids) or [])
        if result.completed_event_ids or result.skipped_event_ids or (
            result.ended_at_utc != result.started_at_utc
        ):
            self._mark_progress()
        return AdvancementReport(result, tuple(rows))

    def advance_next_event(self):
        self._manual_start()
        try:
            return self._report(resolve_next_event(self.world))
        finally:
            stop_fast_forward(self.world)
            self._refresh_owned_reads()
            self._last_auto_sim_time = self.world['simulation']['time_utc']

    def _manual_start(self):
        self.hard_pause()
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
        self.begin_advance_to(target_time_utc)
        try:
            while True:
                report = self.advance_tick()
                if report is not None:
                    return report
                if self.on_advance_boundary is not None:
                    self.on_advance_boundary()
        finally:
            self.cancel_advance()

    @property
    def advancing(self):
        return self._bulk_work is not None

    def begin_advance_to(self, target_time_utc):
        """Begin a cooperative explicit jump; each step publishes a bounded prefix."""
        if self._bulk_work is not None:
            raise ValueError('advancement is already active')
        target = parse_canonical_utc(target_time_utc)
        if target < parse_canonical_utc(self.world['simulation']['time_utc']):
            raise ValueError('simulation time cannot move backward')
        self._manual_start()
        begin_fast_forward(self.world, target_time_utc)
        self._refresh_owned_reads()
        # Explicit catch-up retains a whole-request cap, but routine horizon
        # extension must not exhaust the normal pacing generation budget of 100.
        self._bulk_work = begin_resolution(self.world, target_time_utc,
            max_generated_events=DEFAULT_MAX_EVENTS_PER_ADVANCE,
            shared=True, max_batch_events=self.runtime.max_batch_events,
            execution_state=self.runtime.execution_state)

    def advance_tick(self):
        """Return None after a committed event, or the final advancement report."""
        if self._bulk_work is None:
            raise ValueError('no advancement is active')
        try:
            progress = self._bulk_work.step()
            if progress.finished:
                if progress.processing_result.failure:
                    failure = progress.processing_result.failure
                    self.runtime._stop_error(f'{failure.code}: {failure.message}')
                return self._report(progress.processing_result)
            self._mark_progress()
            return None
        finally:
            if self._bulk_work is not None and self._bulk_work.finished:
                self._bulk_work = None
                stop_fast_forward(self.world)
                self._refresh_owned_reads()
                self._last_auto_sim_time = self.world['simulation']['time_utc']

    def cancel_advance(self):
        """Cancel between complete events, leaving every committed event intact."""
        if self._bulk_work is not None:
            self._bulk_work.close()
            self._bulk_work = None
            stop_fast_forward(self.world)
            self._refresh_owned_reads()
            self._last_auto_sim_time = self.world['simulation']['time_utc']

    def validate(self):
        if self.world is None:
            return True
        return validate_world(self.world).is_valid


__all__ = ("AdvancementReport", "Stage1Session")
