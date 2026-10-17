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

    def __init__(self, *, runtime_clock=None, save_root=None, closed_owner=False,
                 scoped_completion=False):
        if type(closed_owner) is not bool:
            raise ValueError('closed_owner must be a boolean')
        if type(scoped_completion) is not bool or (scoped_completion and not closed_owner):
            raise ValueError('scoped_completion requires an explicitly closed-owner session')
        self._scoped_completion_enabled = scoped_completion
        self._owned_event = None
        self._closed_owner = closed_owner
        self._ownership_acquisitions = 0
        self._ownership_clones = 0
        self._world_exports = 0
        self._runtime_generation = 0
        initialize_runtime_handlers()
        scenario = load_stage1_scenario(STAGE1_SCENARIO_ID)
        self._display_rates = deepcopy(scenario["display_currencies"])
        self._replace_world(None)
        self.display_currency = "USD"
        self.changed = False
        self._runtime = None
        self.runtime_clock = runtime_clock
        self.on_advance_boundary = None
        self._save_store = SaveStore() if save_root is None else SaveStore(save_root)
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
        if self.closed_owner:
            raise AttributeError('closed-owner world is private; use named session queries')
        return self._world

    @property
    def closed_owner(self):
        return self._closed_owner

    @property
    def runtime(self):
        if self.closed_owner:
            raise AttributeError('closed-owner runtime is private; use runtime_view()')
        return self._runtime

    @runtime.setter
    def runtime(self, value):
        if self.closed_owner:
            raise AttributeError('closed-owner runtime cannot be replaced')
        self._runtime = value
        self._runtime_generation += 1

    @property
    def save_store(self):
        if self.closed_owner:
            raise AttributeError('closed-owner storage is private; use session save/load commands')
        return self._save_store

    @save_store.setter
    def save_store(self, value):
        if self.closed_owner:
            raise AttributeError('closed-owner storage cannot be replaced')
        self._save_store = value

    def runtime_view(self):
        """Detached status only: no controller, request or execution capability."""
        from .session_ownership import RuntimeView
        runtime = self._runtime
        return None if runtime is None else RuntimeView(
            runtime.state, runtime.draining, runtime.processing, runtime.running,
            runtime.blocked, runtime.closed, runtime.diagnostic,
            runtime.earned_target_utc, runtime.credit_ns)

    @property
    def runtime_binding(self):
        """Deferred-action identity, independent of committed read generations."""
        return self.binding_revision, self._runtime_generation

    def ownership_counts(self):
        """Runtime-only diagnostics; explicit full exports are counted separately."""
        return dict(acquisitions=self._ownership_acquisitions,
                    acquisition_clones=self._ownership_clones,
                    full_world_exports=self._world_exports)

    def _acquire_foreign(self, value):
        from .session_ownership import detach_foreign_world
        candidate = detach_foreign_world(value)
        self._ownership_clones += 1
        return candidate

    @world.setter
    def world(self, value):
        if self.closed_owner and value is not None:
            value = self._acquire_foreign(value)
        self._replace_world(value)

    def _replace_world(self, value):
        # Only private constructors and validated detached SaveStore results use
        # this transfer boundary. No public trusted/adopt switch is admitted.
        if self._owned_event is not None:
            self._owned_event.close()
        self._owned_event = None
        if self.closed_owner and value is not None:
            self._ownership_acquisitions += 1
        if self.closed_owner and getattr(self, '_runtime', None) is not None:
            self._runtime.cancel_work()
            self._runtime.closed = True
            self._runtime = None
        if self.closed_owner and getattr(self, '_bulk_work', None) is not None:
            self._bulk_work.close()
            self._bulk_work = None
        self._world = value
        if self._scoped_completion_enabled and value is not None:
            from game.simulation.owned_event import _new_owned_completion_authority
            self._owned_event = _new_owned_completion_authority(value)
        self.binding_revision = getattr(self, 'binding_revision', 0) + 1
        self._read_views = None
        # Runtime-only owner-issued preparations die on New/Load/foreign rebind.
        from weakref import WeakValueDictionary
        self._quarterly_preparations = WeakValueDictionary()
        self._quarterly_readiness = WeakValueDictionary()
        self._route_preparations = WeakValueDictionary()
        # Foreign borrowed dictionaries have no exclusive-writer provenance.
        # They retain authoritative source-scan fallback, including in-place edits.
        self._quarterly_indexes = None

    def _bind_owned_reads(self):
        self._read_views = _OwnedReadViews(self._world, self.progression_revision)

    def _event_options(self):
        return {} if self._owned_event is None else {'_owned_event': self._owned_event}

    def scoped_completion_status(self):
        """Detached runtime-only pilot diagnostics; no execution capability."""
        return None if self._owned_event is None else self._owned_event.diagnostics()

    def _owned_reads(self):
        if not self.active:
            return None
        if self._read_views is None or not self._read_views.matches(
                self._world, self.progression_revision):
            # A foreign replacement has no session commit proof. Public/external
            # bindings keep the complete gate, once before acquiring ownership.
            self._read_views = None
            try:
                valid = validate_world(self._world).is_valid
            except Exception:
                valid = False
            if not valid:
                return None
            self._bind_owned_reads()
        return self._read_views

    @property
    def runtime_speed(self):
        return self._runtime.selected_speed if self._runtime else PLAYER_SPEEDS[0]

    @property
    def runtime_status(self):
        if not self.active:
            return 'No active career'
        self._ensure_runtime()
        return self._runtime.status_text

    @property
    def active(self):
        return self._world is not None

    @property
    def airline_id(self):
        if self._world is None:
            return None
        return self._world["world_state"]["player"]["primary_airline_id"]

    @property
    def display_rates(self):
        return deepcopy(self._display_rates)

    def new_game(self, ceo_display_name, airline_display_name, base_code):
        self._replace_world(create_stage1_new_game(
            scenario_id=STAGE1_SCENARIO_ID,
            ceo_display_name=ceo_display_name,
            airline_display_name=airline_display_name,
            base_airport_reference_code=base_code,
        ))
        self.display_currency = "USD"
        self.career_id = self._save_store.new_career_id()
        self.progression_revision = 0
        self.unsaved_progress = True
        self.autosave_error = None
        self._reset_autosave_clocks()
        self.changed = True
        self._ensure_runtime()
        self._bind_owned_reads()

        from game.scheduling.quarterly_indexes import QuarterlyIndexOwner
        self._quarterly_indexes = QuarterlyIndexOwner()

    def new_quarterly_development_game(self, ceo_display_name, airline_display_name, base_code):
        """Explicit paid-route development start, never ordinary New Game.

        Enroll the untouched private PH candidate in the certified isolated
        backend. Route rights must be purchased through the existing commands.
        No service, plan, booking, flight or operational event is seeded.
        """
        from game.scheduling.quarterly_backend import enable_quarterly_backend_for_testing
        candidate = create_stage1_new_game(scenario_id=STAGE1_SCENARIO_ID,
            ceo_display_name=ceo_display_name, airline_display_name=airline_display_name,
            base_airport_reference_code=base_code)
        enable_quarterly_backend_for_testing(candidate)
        career_id = self._save_store.new_career_id()
        if self._runtime is not None:
            self._runtime.cancel_work(); self._runtime.closed = True
        self._replace_world(candidate)
        self._runtime = None
        self.career_id = career_id
        self.display_currency = 'USD'
        self.progression_revision = 0
        self.unsaved_progress = True
        self.autosave_error = None
        self._reset_autosave_clocks()
        self.changed = True
        self._ensure_runtime(); self._bind_owned_reads()
        from game.scheduling.quarterly_indexes import QuarterlyIndexOwner
        self._quarterly_indexes = QuarterlyIndexOwner()

    @property
    def quarterly_career(self):
        from game.world_state.quarterly_consumers import quarterly_mode
        return self.active and quarterly_mode(self._world)

    @property
    def simulation_time_utc(self):
        return self._world['simulation']['time_utc'] if self.active else None

    def quarterly_planning_page(self, plan_id=None, *, offset=0, limit=32):
        from game.scheduling.quarterly_presentation import planning_page
        views = self._owned_reads()
        if views is None or not self.quarterly_career:
            raise ValueError('quarterly planning requires an isolated quarterly career')
        return views._page(('quarterly-planning',self.airline_id,plan_id,offset,limit),lambda:
            planning_page(self._world,self.airline_id,plan_id=plan_id,offset=offset,limit=limit))

    def quarterly_slot_input(self, **values):
        from game.scheduling.quarterly_presentation import slot_input
        if self._owned_reads() is None or not self.quarterly_career:
            raise ValueError('select an isolated quarterly career')
        return slot_input(self._world,self.airline_id,**values)

    def quarterly_published_day(self, plan_id, operating_date, *, offset=0, limit=32):
        """Bounded Stage 3B resolution, decorated with existing stored outcomes."""
        from game.scheduling.quarterly_presentation import day_requests
        views = self._owned_reads()
        if views is None or not self.quarterly_career:
            raise ValueError('select an isolated quarterly career')
        requests,total = day_requests(self._world,self.airline_id,plan_id,operating_date,offset=offset,limit=limit)
        if not requests:
            return dict(rows=[],total=total,offset=offset)
        result = self.quarterly_occurrences(requests)
        if not result.succeeded:
            raise ValueError('; '.join(i.code+': '+i.message for i in result.issues))
        stored = {r['occurrence_key']:r for r in self._world['world_state']['dated_flights'].values()
                  if r['airline_id'] == self.airline_id and r.get('quarterly_lineage')}
        from game.aircraft_operations.fulfilment import _build_confirmed_carriage_manifest
        lookup = views._operations()
        rows=[]
        for occurrence in result.occurrences:
            facts=occurrence.slot_facts; flight=stored.get(occurrence.occurrence_key)
            passengers=0; status='Published'; revenue=None
            if flight:
                status=flight['status']
                finalized=self._world['world_state']['flight_results'].get(flight['dated_flight_id'])
                if finalized:
                    passengers=finalized['carried_passenger_count']; revenue=finalized['recognized_revenue_minor']
                else:
                    manifest=_build_confirmed_carriage_manifest(self._world,flight['dated_flight_id'],
                        booking_ids=lookup.booking_ids_by_flight.get(flight['dated_flight_id'],()))
                    if not manifest.succeeded: raise ValueError('invalid confirmed carriage projection')
                    passengers=manifest.carried_passenger_count
            world=self._world['world_state']
            rows.append(dict(key=occurrence.occurrence_key,flight_number=occurrence.flight_number,
                departure_utc=occurrence.departure_utc,arrival_utc=occurrence.planning_arrival_utc,
                aircraft=world['aircraft'][facts['planned_aircraft_id']]['display_registration'],
                origin=world['airports'][facts['origin_airport_id']]['reference_code'],
                destination=world['airports'][facts['destination_airport_id']]['reference_code'],
                published_at_utc=occurrence.published_at_utc,plan_id=occurrence.reference.weekly_plan_id,
                revision=occurrence.reference.revision,status=status,passengers=passengers,
                capacity=facts['capacity'],revenue_minor=revenue))
        return dict(rows=rows,total=total,offset=offset)

    def retry_quarterly_publication(self):
        """Explicit single existing kernel event retry; never clear a fence here."""
        failure=self._quarterly_command_boundary()
        if failure is not None: raise ValueError(failure.issues[0].message)
        status=self.quarterly_boundary_status()
        if not self.quarterly_career or not status or not status['failure']:
            raise ValueError('no failed quarterly publication to retry')
        return self.advance_next_event()

    def _clock_ns(self):
        from game.simulation.pacing import active_monotonic_ns
        return (self.runtime_clock or active_monotonic_ns)()

    def _reset_autosave_clocks(self):
        self._active_start_ns = self._clock_ns()
        self._last_auto_active_ns = self._active_start_ns
        self._last_auto_sim_time = self._world['simulation']['time_utc']

    def _mark_progress(self, *, preserve_quarterly_indexes=False):
        self.changed = True
        self.unsaved_progress = True
        self.progression_revision += 1
        if not preserve_quarterly_indexes and self._quarterly_indexes is not None:
            self._quarterly_indexes.invalidate()
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
        self._save_store.save(self.career_id, 'manual', self._world,
                             progression_revision=self.progression_revision)
        self.unsaved_progress = False
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self._world['simulation']['time_utc']
        return self.career_id

    def _save_boundary(self):
        # Normal requests stop accrual and finish owed work before manual storage.
        # Errors remain savable at their last valid committed prefix; no debt is
        # serialized. A frontend may defer/retry this same existing save command.
        self.pause()
        if self._runtime.draining:
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
        bookmark_id = self._save_store.save(self.career_id, 'bookmark', self._world,
                                           bookmark_name=name,
                                           progression_revision=self.progression_revision)
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self._world['simulation']['time_utc']
        return bookmark_id

    def load_saved(self, career_id, kind='manual', *, bookmark_id=None,
                   foundation_snapshot=None):
        if self._bulk_work is not None:
            raise SaveError('ADVANCEMENT_ACTIVE', 'Finish or cancel advancement before loading')
        candidate, data = self._save_store.load(career_id, kind, bookmark_id=bookmark_id,
                                                foundation_snapshot=foundation_snapshot)
        now = self._clock_ns()
        options = {} if self.runtime_clock is None else {'clock': self.runtime_clock}
        new_runtime = RuntimeController(candidate, **options)
        if self._runtime is not None:
            self._runtime.cancel_work()
            self._runtime.closed = True
        self._replace_world(candidate)
        self.career_id = career_id
        self.progression_revision = data['progression_revision']
        self.unsaved_progress = False
        self.autosave_error = None
        self.display_currency = 'USD'
        self._runtime = new_runtime
        if self._owned_event is not None:
            self._runtime._owned_event = self._owned_event
            self._runtime.execution_state = self._owned_event.execution_state
        self._runtime_generation += 1
        self._active_start_ns = now
        self._last_auto_active_ns = now
        self._last_auto_sim_time = candidate['simulation']['time_utc']
        self.changed = True
        self._bind_owned_reads()
        from game.scheduling.quarterly_indexes import QuarterlyIndexOwner
        self._quarterly_indexes = QuarterlyIndexOwner()
        return data

    def list_careers(self):
        return self._save_store.list_careers()

    def list_bookmarks(self, career_id=None):
        return self._save_store.list_bookmarks(career_id or self.career_id)

    def delete_bookmark(self, bookmark_id):
        if not self.active:
            raise SaveError('NO_GAME', 'No active game')
        return self._save_store.delete_bookmark(self.career_id, bookmark_id)

    def newer_autosave(self, career_id):
        return self._save_store.newer_autosave(career_id)

    def maybe_autosave(self):
        if not self.active or self.career_id is None:
            return False
        now = self._clock_ns()
        elapsed_real = now - self._last_auto_active_ns
        elapsed_sim = (parse_canonical_utc(self._world['simulation']['time_utc']) -
                       parse_canonical_utc(self._last_auto_sim_time)).total_seconds()
        if elapsed_real < 15 * 60 * 1_000_000_000 and elapsed_sim < 7 * 86400:
            return False
        try:
            self._save_store.save(self.career_id, 'autosave', self._world,
                                 progression_revision=self.progression_revision)
        except SaveError as exc:
            self.autosave_error = f'{exc.code}: {exc}'
            self._last_auto_active_ns = now  # throttle repeated storage failures
            self._last_auto_sim_time = self._world['simulation']['time_utc']
            return False
        self.autosave_error = None
        self._last_auto_active_ns = now
        self._last_auto_sim_time = self._world['simulation']['time_utc']
        return True

    def _ensure_runtime(self):
        if self._runtime is not None and self._runtime.world is self._world:
            return
        if self._runtime is not None:
            self._runtime.cancel_work()
            self._runtime.closed = True
        options = {} if self.runtime_clock is None else {'clock': self.runtime_clock}
        self._runtime = RuntimeController(self._world, **options, **self._event_options())
        self._runtime_generation += 1

    def resume(self, speed=None):
        if self.quarterly_career:
            fence=self.quarterly_planning_page()['fence']
            if fence and fence['failure']:
                raise ValueError('Publication is blocked: correct the unpublished quarter and explicitly Retry publication before Resume')
        self._ensure_runtime()
        before = (self._world['simulation']['clock_state'],
                  self._world['simulation']['configuration']['clock_ratios']['NORMAL'])
        self._runtime.resume(speed)
        after = (self._world['simulation']['clock_state'],
                 self._world['simulation']['configuration']['clock_ratios']['NORMAL'])
        if after != before:
            self._mark_progress()

    def pause(self):
        self._ensure_runtime()
        before = self._world['simulation']['clock_state']
        if self._bulk_work is not None:
            self._runtime.hard_pause()  # Explicit Advance cancellation boundary.
        else:
            self._runtime.pause()
        if self._world['simulation']['clock_state'] != before:
            self._mark_progress()

    def hard_pause(self):
        self._ensure_runtime()
        before = self._world['simulation']['clock_state']
        self._runtime.hard_pause()
        if self._world['simulation']['clock_state'] != before:
            self._mark_progress()

    def close(self):
        self.cancel_advance()
        if self._runtime is not None:
            self._runtime.close()
        if self._owned_event is not None:
            self._owned_event.close()

    def leave_game(self):
        self.cancel_advance()
        if self._runtime is not None:
            self._runtime.close()
        self._replace_world(None)
        self._runtime = None
        self.career_id = None
        self.unsaved_progress = False

    def pump(self):
        if not self.active:
            return None
        if self._bulk_work is not None:
            return None
        self._ensure_runtime()
        before = (self._runtime.commit_serial, self._world['simulation']['clock_state'])
        try:
            result = self._runtime.pump()
        finally:
            if (self._runtime.commit_serial, self._world['simulation']['clock_state']) != before:
                # One epoch notification per safe unit, never speculative reads.
                self._mark_progress()
        self.maybe_autosave()
        return result

    def _management_changed(self, *, preserve_quarterly_indexes=False):
        self._mark_progress(preserve_quarterly_indexes=preserve_quarterly_indexes)
        if self._runtime is not None:
            self._runtime.management_changed()

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
        if self._world is None:
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
                self._world["world_state"]["airports"].items(),
                key=lambda item: (item[1]["reference_code"], item[0]),
            )
            if airport.get("demand_allocation_member") is True
            and airport.get("passenger_demand_eligible") is True
        )

    def market_opportunities(self, *, origin_airport_id=None, limit=100):
        return project_market_opportunities(
            self._world, origin_airport_id=origin_airport_id, limit=limit
        )

    def route_pair_status(self, origin_airport_id, destination_airport_id):
        if self._owned_reads() is None:
            raise ValueError('no valid active career')
        world = self._world['world_state']
        pair = {origin_airport_id,destination_airport_id}
        rows = [c for c in world['connections'].values() if c['airline_id']==self.airline_id
                and {world['directional_markets'][c['market_id']]['origin_airport_id'],
                     world['directional_markets'][c['market_id']]['destination_airport_id']}==pair]
        return 'ACTIVE' if len(rows)==2 and all(c['status']=='ACTIVE' for c in rows) else 'CLOSED' if rows else 'NOT ESTABLISHED'

    def quote_route(self, hub_airport_id, origin_airport_id, destination_airport_id, *, action='ESTABLISH'):
        from game.route_management.establishment import quote_route
        failure = self._quarterly_command_boundary()
        if failure is not None:
            raise ValueError('pause and finish runtime work before route management')
        quote = quote_route(self._world,airline_id=self.airline_id,hub_airport_id=hub_airport_id,
            origin_airport_id=origin_airport_id,destination_airport_id=destination_airport_id,action=action)
        self._route_preparations[id(quote)] = quote
        return quote

    def apply_route(self, quote):
        from game.route_management.establishment import apply_route
        failure = self._quarterly_command_boundary()
        if failure is not None:
            raise ValueError('pause and finish runtime work before route management')
        if self._route_preparations.get(id(quote)) is not quote:
            raise ValueError('stale or foreign route confirmation; review again')
        before = self.authoritative_bytes()
        result = apply_route(self._world,quote)
        self._route_preparations.pop(id(quote),None)
        if before != self.authoritative_bytes():
            self.changed = True
            self._management_changed()
        return result

    def suggested_economy_fare(self, origin_airport_id, destination_airport_id):
        from game.economy.fare_reference import suggested_economy_fare_minor

        return suggested_economy_fare_minor(
            self._world["world_state"], origin_airport_id, destination_airport_id
        )

    def authoritative_bytes(self):
        if self._world is None:
            return b""
        if self.closed_owner:
            self._world_exports += 1
        return json.dumps(
            self._world, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")

    def aircraft_catalog(self):
        """Load detached reference content only when the player opens the catalog."""
        return load_aircraft_catalog(catalog_version=PH_AIRCRAFT_CATALOG_VERSION)

    def set_display_currency(self, currency):
        if currency not in self._display_rates:
            raise ValueError("unsupported display currency")
        self.display_currency = currency

    def overview(self):
        return project_airline_overview(self._world, self.airline_id)

    def header(self):
        """Fresh bounded identity/cash read for the application-owned world."""
        return _project_owned_airline_header(self._world, self.airline_id)

    def fleet(self, *, offset=0, limit=20):
        from game.aircraft_operations.projections import _page_options
        _page_options(limit, offset)
        views = self._owned_reads()
        return views.fleet(self.airline_id, offset=offset, limit=limit) if views else None

    def management_fleet(self):
        if self._owned_reads() is None: raise ValueError("no valid active career")
        from game.fleet_management.management_projection import _project_management_fleet_owned
        return _project_management_fleet_owned(self._world, self.airline_id)

    def aircraft_details(self, aircraft_id):
        if self._owned_reads() is None: raise ValueError("no valid active career")
        from game.fleet_management.management_projection import _project_aircraft_details_owned
        return _project_aircraft_details_owned(self._world, self.airline_id, aircraft_id)

    def compatible_aircraft(self, origin_id, destination_id):
        if self._owned_reads() is None: raise ValueError("no valid active career")
        from game.scheduling.route_compatibility import compatible_aircraft
        return compatible_aircraft(self._world, self.airline_id, origin_id, destination_id)

    def scheduling_aircraft(self, aircraft_id):
        """Fresh detached row for the planner; command boundaries own validation."""
        return _project_owned_scheduling_aircraft(self._world, self.airline_id, aircraft_id)

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
        return resolve_quarterly_reads(self._world, airline_id=self.airline_id,
                                      selections=(request, *compare_with))

    def quarterly_publication_readiness(self, weekly_plan_id=None, *, expected_revision=None,
                                       expected_time_utc=None, previous=None):
        """Paused boundary diagnostic; issued results have no publication capability."""
        from game.scheduling.quarterly_readiness import (
            PublicationReadinessRequest, PublicationReadinessResult,
            inspect_quarterly_publication_readiness,
        )
        from game.scheduling.quarterly_reads import ReadIssue
        failure = self._quarterly_command_boundary()
        if failure is not None:
            return PublicationReadinessResult(issues=failure.issues)
        if previous is not None and self._quarterly_readiness.get(id(previous)) is not previous:
            return PublicationReadinessResult(issues=(ReadIssue(
                'STALE_CONTEXT', 'previous', 'inspect again after Load/rebind or foreign result'),))
        if previous is not None and (
                (weekly_plan_id is not None and previous.weekly_plan_id != weekly_plan_id)
                or (expected_revision is not None and (previous.revision or 0) != expected_revision)):
            return PublicationReadinessResult(issues=(ReadIssue(
                'INVALID_REQUEST', 'previous', 'previous result must describe the same selection'),))
        request = PublicationReadinessRequest(weekly_plan_id, expected_revision, expected_time_utc,
                                              None if previous is None else previous.sources)
        result = inspect_quarterly_publication_readiness(self._world, airline_id=self.airline_id,
                                                       request=request, _indexes=self._quarterly_indexes)
        if result.succeeded:
            self._quarterly_readiness[id(result)] = result
        return result

    def quarterly_occurrences(self, requests, *, require_published=True, expected_time_utc=None):
        """Resolve explicit lineage at a paused completed boundary; no supply writes."""
        from game.scheduling.quarterly_occurrences import OccurrenceReadResult, resolve_quarterly_occurrences
        failure = self._quarterly_command_boundary()
        if failure is not None:
            return OccurrenceReadResult(issues=failure.issues)
        return resolve_quarterly_occurrences(self._world, airline_id=self.airline_id,
            requests=requests, require_published=require_published, expected_time_utc=expected_time_utc)

    def quarterly_boundary_status(self):
        """Detached durable obligation/failure diagnostics; never an edit capability."""
        from copy import deepcopy
        from game.world_state.quarterly_boundary import obligations, boundary
        if not self.active or not validate_world(self._world).is_valid:
            return None
        entry = obligations(self._world).get(self.airline_id)
        if entry is None:
            return None
        return dict(deepcopy(entry), due_at_utc=boundary(entry['next_quarter_id']))

    def _quarterly_command_boundary(self):
        from game.scheduling.quarterly_commands import rejected
        if not self.active:
            return rejected('INVALID_WORLD', 'session', 'no active career')
        try:
            paused = self._world['simulation']['clock_state'] == 'PAUSED'
        except (KeyError, TypeError):
            return rejected('INVALID_WORLD', 'session', 'invalid simulation authority')
        if (self._bulk_work is not None or not paused
                or (self._runtime is not None and self._runtime.processing)):
            return rejected('COMMAND_BOUNDARY', 'session', 'pause and finish runtime work before editing')
        return None

    def prepare_quarterly_command(self, request):
        """Prepare dormant intent; issuance creates no authoritative allocation."""
        from game.scheduling.quarterly_commands import prepare_quarterly_command
        failure = self._quarterly_command_boundary()
        if failure is not None:
            return failure
        result = prepare_quarterly_command(self._world, airline_id=self.airline_id, request=request,
                                          _indexes=self._quarterly_indexes)
        if result.succeeded:
            self._quarterly_preparations[id(result.prepared)] = result.prepared
        return result

    def apply_quarterly_command(self, prepared):
        """Synchronous owner boundary; stale/foreign/forged preparations fail closed."""
        from game.scheduling.quarterly_commands import apply_quarterly_command, rejected
        failure = self._quarterly_command_boundary()
        if failure is not None:
            return failure
        if self._quarterly_preparations.get(id(prepared)) is not prepared:
            return rejected('STALE_CONTEXT', 'prepared', 'refresh after Load/rebind or foreign preparation')
        result = apply_quarterly_command(self._world, airline_id=self.airline_id, prepared=prepared,
                                        _indexes=self._quarterly_indexes)
        if result.succeeded:
            self._quarterly_preparations.pop(id(prepared), None)
            if not result.skipped:
                self._management_changed(preserve_quarterly_indexes=True)
        return result

    def delivery_locations(self):
        from game.fleet_management.acquisition import delivery_locations
        ids = delivery_locations(self._world['world_state'], self.airline_id)
        return tuple(a for a in self.airports() if a['airport_id'] in ids)

    def preview_purchase(self, model_id, delivery_airport_id):
        from game.aircraft_market.acquisition import preview_purchase
        return preview_purchase(self._world, airline_id=self.airline_id,
            model_id=model_id, catalog_version=PH_AIRCRAFT_CATALOG_VERSION,
            delivery_airport_id=delivery_airport_id)

    def purchase(self, preview):
        from game.aircraft_market.acquisition import purchase_aircraft
        before = self.authoritative_bytes()
        aircraft_id = purchase_aircraft(self._world, preview)
        if before != self.authoritative_bytes():
            self.changed = True
            self._management_changed()
        return aircraft_id

    def leasing_offers(self):
        state = self._world['world_state']
        return tuple(deepcopy(state['aircraft_lease_offers'][key]) for key in
                     state['aircraft_market_state']['active_lease_offer_ids'])

    def used_listings(self):
        today = date.fromisoformat(self._world['simulation']['time_utc'][:10])
        rows = []
        for _key, record in sorted(self._world['world_state']['used_aircraft_listings'].items()):
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
            self._world['world_state']['aircraft_contracts'].items())
            if row['airline_id'] == self.airline_id and row['status'] in {'ACTIVE', 'FUTURE'})

    def preview_lease(self, offer_id, contract_type, term_years, delivery_airport_id):
        from game.aircraft_market.step5 import preview_lease
        return preview_lease(self._world, airline_id=self.airline_id, offer_id=offer_id,
            contract_type=contract_type, term_years=term_years,
            delivery_airport_id=delivery_airport_id)

    def accept_lease(self, preview):
        from game.aircraft_market.step5 import accept_lease
        aircraft_id = accept_lease(self._world, preview)
        self.changed = True
        self._management_changed()
        return aircraft_id

    def preview_used_purchase(self, listing_id, delivery_airport_id):
        from game.aircraft_market.step5 import preview_used_purchase
        return preview_used_purchase(self._world, airline_id=self.airline_id,
            listing_id=listing_id, delivery_airport_id=delivery_airport_id)

    def purchase_used(self, preview):
        from game.aircraft_market.step5 import purchase_used_aircraft
        aircraft_id = purchase_used_aircraft(self._world, preview)
        self.changed = True
        self._management_changed()
        return aircraft_id

    def renew_operating_lease(self, aircraft_id, term_years, command_id,
                              expected_world_fingerprint=None):
        from game.aircraft_market.step5 import renew_operating_lease
        if expected_world_fingerprint is None:
            expected_world_fingerprint = self.preview_operating_renewal(
                aircraft_id, term_years).world_fingerprint
        result = renew_operating_lease(self._world, aircraft_id=aircraft_id,
                                       term_years=term_years, command_id=command_id,
                                       expected_world_fingerprint=expected_world_fingerprint)
        self.changed = True
        self._management_changed()
        return result

    def preview_operating_renewal(self, aircraft_id, term_years):
        from game.aircraft_market.step5 import preview_operating_renewal
        return preview_operating_renewal(self._world, aircraft_id=aircraft_id,
                                         term_years=term_years)

    def terminate_contract(self, aircraft_id, command_id):
        from game.aircraft_market.step5 import terminate_contract
        result = terminate_contract(self._world, aircraft_id=aircraft_id,
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
        return _operational_context_owned(self._world,self.airline_id)

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
        return project_next_pending_event(self._world)

    def next_event_for_display(self):
        """Fresh bounded read of session-owned pending events for GUI refresh."""
        return _project_next_pending_event_owned(self._world)

    def default_operating_date(self):
        current = date.fromisoformat(self._world["simulation"]["time_utc"][:10])
        return (current + timedelta(days=6)).isoformat()

    def plan_rotation(self, aircraft_id, destination_code, fare_minor, operating_date):
        before = self.authoritative_bytes()
        result = create_weekly_round_trip_rotation(
            self._world,
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
            airport_id = self._world['world_state']['airlines'][self.airline_id]['base_airport_ids'][0]
        return airport_local(self._world['world_state'], airport_id, self._world['simulation']['time_utc'])

    def local_clock(self, airport_id=None):
        local = self.local_datetime(airport_id)
        return f"{local:%Y-%m-%d %H:%M:%S} {local.tzinfo.key}"

    def has_recurring_pattern(self, aircraft_id):
        from game.scheduling.recurrence import rolling_schedules
        return bool(rolling_schedules(self._world, self.airline_id, aircraft_id))

    def begin_scheduling(self, aircraft_id, *, edit_recurring=False):
        from game.scheduling.weekly import WeeklyDraft
        factory = WeeklyDraft.edit_recurring if edit_recurring else WeeklyDraft
        draft = factory(self._world, airline_id=self.airline_id, aircraft_id=aircraft_id)
        if self.closed_owner:
            draft._session_binding = self.binding_revision
        return draft

    def _check_draft(self, draft):
        from game.scheduling.weekly import WeeklyDraft
        if self.closed_owner and type(draft) is not WeeklyDraft:
            raise ValueError('closed-owner planning requires a built-in WeeklyDraft')
        if self.closed_owner and getattr(draft, '_session_binding', None) != self.binding_revision:
            raise ValueError('stale scheduling draft; reopen after career replacement')

    def validate_scheduling(self, draft):
        """Validate a detached draft without lending the current world to a caller."""
        self._check_draft(draft)
        current = draft.validate_current(self._world)
        if self.closed_owner:
            current._session_binding = self.binding_revision
        return current

    def planning_departure(self, airport_id, operating_date, local_time):
        from game.scheduling.local_time import local_departure
        return local_departure(self._world['world_state'], airport_id, operating_date, local_time)

    def save_scheduling(self, draft, *, repeat_until=None, continuous=False):
        self._check_draft(draft)
        result = draft.save_current(self._world, repeat_until=repeat_until, continuous=continuous)
        self.changed = True
        self._management_changed()
        return result

    def publish_next_rotation(self):
        before = self.authoritative_bytes()
        result = publish_next_rotation(self._world, airline_id=self.airline_id)
        if result.succeeded:
            self.changed = True
            self._management_changed()
        elif self.authoritative_bytes() != before:
            raise RuntimeError("rejected publication mutated authoritative state")
        return result

    def _report(self, result):
        ids = tuple(result.completed_event_ids) + tuple(result.skipped_event_ids)
        rows = _project_event_records_owned(self._world, ids) if result.succeeded else (project_event_records(self._world, ids) or [])
        if result.completed_event_ids or result.skipped_event_ids or (
            result.ended_at_utc != result.started_at_utc
        ) or (result.failure is not None and self.quarterly_boundary_status() is not None):
            self._mark_progress()
        return AdvancementReport(result, tuple(rows))

    def advance_next_event(self):
        self._manual_start()
        try:
            return self._report(resolve_next_event(self._world, **self._event_options()))
        finally:
            stop_fast_forward(self._world)
            self._refresh_owned_reads()
            self._last_auto_sim_time = self._world['simulation']['time_utc']

    def _manual_start(self):
        self.hard_pause()
        self._runtime.cancel_work()
        # An explicit time jump replaces the outstanding pacing target.
        self._runtime.credit_ns = 0

    def advance_seconds(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
            raise ValueError("advance duration must be positive whole seconds")
        target = format_utc(
            parse_canonical_utc(self._world["simulation"]["time_utc"])
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
        if target < parse_canonical_utc(self._world['simulation']['time_utc']):
            raise ValueError('simulation time cannot move backward')
        self._manual_start()
        begin_fast_forward(self._world, target_time_utc)
        self._refresh_owned_reads()
        # Explicit catch-up retains a whole-request cap, but routine horizon
        # extension must not exhaust the normal pacing generation budget of 100.
        self._bulk_work = begin_resolution(self._world, target_time_utc,
            max_generated_events=DEFAULT_MAX_EVENTS_PER_ADVANCE,
            shared=True, max_batch_events=self._runtime.max_batch_events,
            execution_state=self._runtime.execution_state, **self._event_options())

    def advance_tick(self):
        """Return None after a committed event, or the final advancement report."""
        if self._bulk_work is None:
            raise ValueError('no advancement is active')
        try:
            progress = self._bulk_work.step()
            if progress.finished:
                if progress.processing_result.failure:
                    failure = progress.processing_result.failure
                    self._runtime._stop_error(f'{failure.code}: {failure.message}')
                return self._report(progress.processing_result)
            self._mark_progress()
            return None
        finally:
            if self._bulk_work is not None and self._bulk_work.finished:
                self._bulk_work = None
                stop_fast_forward(self._world)
                self._refresh_owned_reads()
                self._last_auto_sim_time = self._world['simulation']['time_utc']

    def cancel_advance(self):
        """Cancel between complete events, leaving every committed event intact."""
        if self._bulk_work is not None:
            self._bulk_work.close()
            self._bulk_work = None
            stop_fast_forward(self._world)
            self._refresh_owned_reads()
            self._last_auto_sim_time = self._world['simulation']['time_utc']

    def validate(self):
        if self._world is None:
            return True
        return validate_world(self._world).is_valid


__all__ = ("AdvancementReport", "Stage1Session")
