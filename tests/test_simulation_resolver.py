"""Stage 1 resolver boundaries and exact deterministic continuation gates."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.aircraft_market.step5 import accept_lease, preview_lease
from game.scheduling import WeeklyDraft
from game.simulation import kernel
from game.simulation.resolver import (
    PROTECTED_CAUSAL_FENCES, ResolutionRequest,
    begin_resolution, resolve_until, resolve_next_event,
)
from game.simulation.pacing import RuntimeController, NANOSECOND
from game.world_state import create_stage1_new_game, load_stage1_scenario, validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.resolution_oracle import assert_equivalent, canonical_world, save_reload, strict_until
from tests.test_stage1_event_kernel import make_world, schedule, recording_registry


class ResolverBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.world = make_world()

    def test_same_timestamp_is_not_fully_resolved_after_first_event(self):
        self.world = ph_world()
        due = "2026-09-01T01:00:00Z"
        first = schedule(self.world, due)
        second = schedule(self.world, due)
        request = begin_resolution(self.world, due)
        before = deepcopy(self.world)
        self.assertIsNone(request.boundary().last_committed_event_utc)
        self.assertEqual(self.world, before)
        progress = request.step()
        self.assertEqual(progress.status, "YIELDED")
        self.assertEqual(progress.event_id, first)
        self.assertEqual(progress.unresolved_target_utc, due)
        boundary = request.boundary()
        self.assertEqual(boundary.authoritative_utc, due)
        self.assertEqual(boundary.last_committed_event_id, first)
        self.assertFalse(boundary.current_utc_fully_resolved)
        self.assertTrue(validate_world(self.world).is_valid)
        # A save is legal here, despite the equal-time event still pending.
        restored = save_reload(self.world)
        self.assertEqual(restored, self.world)
        self.assertEqual(request.step().event_id, second)
        self.assertTrue(request.boundary().current_utc_fully_resolved)
        final = request.step()
        self.assertEqual(final.status, "COMPLETED")
        self.assertTrue(final.finished)
        self.assertIsNone(final.unresolved_target_utc)
        self.assertEqual(final.completed_event_count, 2)
        self.assertTrue(resolve_until(restored, due).succeeded)
        self.assertEqual(restored, self.world)

    def test_clock_only_completion_does_not_invent_an_event_boundary(self):
        target = "2026-08-20T05:00:00Z"
        request = begin_resolution(self.world, target)
        progress = request.step()
        self.assertTrue(progress.finished)
        self.assertEqual(progress.completed_event_count, 0)
        self.assertIsNone(request.boundary().last_committed_event_utc)
        self.assertEqual(progress.authoritative_utc, target)
        self.assertTrue(request.boundary().current_utc_fully_resolved)

    def test_next_event_keeps_equal_time_second_event_pending(self):
        due = "2026-08-20T05:00:00Z"
        ids = [schedule(self.world, due) for _ in range(2)]
        expected = deepcopy(self.world)
        self.assertEqual(resolve_next_event(self.world), kernel.process_next_event(expected))
        self.assertEqual(self.world, expected)
        self.assertEqual(tuple(self.world["world_state"]["pending_events"]), (ids[1],))

    def test_next_event_empty_and_unknown_registry_preserve_kernel_behavior(self):
        self.assertEqual(resolve_next_event(self.world).status, "NO_EVENT")
        schedule(self.world, "2026-08-20T05:00:00Z", event_type="UNREGISTERED")
        before = deepcopy(self.world)
        result = resolve_next_event(self.world)
        self.assertEqual(result.failure.code, "UNKNOWN_EVENT_TYPE")
        self.assertEqual(self.world, before)

    def test_close_keeps_committed_prefix_and_does_not_change_clock_policy(self):
        due = "2026-08-20T05:00:00Z"
        first = schedule(self.world, due)
        second = schedule(self.world, due)
        request = begin_resolution(self.world, "2026-08-20T06:00:00Z")
        request.step()
        before = deepcopy(self.world)
        request.close()
        self.assertTrue(request.finished)
        self.assertEqual(self.world, before)
        self.assertIn(first, self.world["world_state"]["event_history"])
        self.assertIn(second, self.world["world_state"]["pending_events"])
        with self.assertRaisesRegex(ValueError, "finished"):
            request.step()

    def test_invalid_world_and_target_keep_existing_failures(self):
        self.world["world_state"]["player"]["primary_airline_id"] = "missing"
        before = deepcopy(self.world)
        result = resolve_until(self.world, "2026-08-20T05:00:00Z")
        self.assertEqual(result.failure.code, "INVALID_WORLD")
        self.assertEqual(self.world, before)
        for target in ("2026-08-19T00:00:00Z", "bad UTC"):
            world = make_world()
            before = deepcopy(world)
            with self.assertRaises(ValueError):
                resolve_until(world, target)
            self.assertEqual(world, before)

    def test_management_change_refreshes_the_same_request(self):
        due = "2026-08-20T05:00:00Z"
        first = schedule(self.world, due)
        request = begin_resolution(self.world, "2026-08-20T06:00:00Z")
        request.step()
        added = schedule(self.world, due)
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertEqual(request.step(management_changed=True).event_id, added)
        self.assertEqual(request.step().processing_result.completed_event_ids, (first, added))

    def test_event_limit_accumulates_across_steps(self):
        due = "2026-08-20T05:00:00Z"
        ids = [schedule(self.world, due) for _ in range(3)]
        request = begin_resolution(self.world, due, max_events=2)
        request.step()
        request.step()
        progress = request.step()
        self.assertEqual(progress.status, "BLOCKED")
        self.assertEqual(progress.processing_result.failure.code, "EVENT_LIMIT_REACHED")
        self.assertEqual(progress.completed_event_count, 2)
        self.assertFalse(request.boundary().current_utc_fully_resolved)
        self.assertEqual(tuple(self.world["world_state"]["pending_events"]), (ids[2],))

    def test_generated_limit_preserves_unyielded_commit_and_last_event(self):
        due = "2026-08-20T05:00:00Z"
        registry = kernel.EventHandlerRegistry()
        def generate(context):
            context.schedule_event(event_type="UNKNOWN", due_at_utc=due,
                owner_type="airline", owner_id=context.event["owner_id"], priority=0)
        registry.register("GENERATE", generate)
        event = schedule(self.world, due, event_type="GENERATE", priority=10)
        request = begin_resolution(self.world, due, registry=registry, max_generated_events=1)
        progress = request.step()
        self.assertEqual(progress.status, "BLOCKED")
        self.assertEqual(progress.processing_result.failure.code, "EVENT_GENERATION_LIMIT_REACHED")
        self.assertEqual(progress.completed_event_count, 1)
        self.assertEqual(request.boundary().last_committed_event_id, event)

    def test_handler_pause_and_stop_condition_preserve_terminal_semantics(self):
        due = "2026-08-20T05:00:00Z"
        for by_handler in (False, True):
            world = make_world()
            registry = kernel.EventHandlerRegistry()
            registry.register("PAUSE", lambda context: context.pause())
            schedule(world, due, event_type="PAUSE" if by_handler else "NO_OP")
            kernel.set_clock_mode(world, "NORMAL")
            options = {"registry": registry} if by_handler else {"stop_condition": lambda _: True}
            request = begin_resolution(world, "2026-08-20T06:00:00Z", **options)
            final = request.step()
            self.assertEqual(final.status, "STOPPED")
            self.assertEqual(final.completed_event_count, 1)
            self.assertEqual(request.boundary().last_committed_event_utc, due)
            self.assertEqual(world["simulation"]["clock_state"], "PAUSED")
            self.assertEqual(final.unresolved_target_utc, "2026-08-20T06:00:00Z")

    def test_failure_retains_successful_prefix_without_retry(self):
        due = "2026-08-20T05:00:00Z"
        registry = kernel.EventHandlerRegistry()
        calls = []
        def fail(context):
            calls.append(context.event["event_id"])
            context.envelope["world_state"]["history"]["operations"].append("partial")
            raise RuntimeError("failure")
        registry.register("FAIL", fail)
        first = schedule(self.world, due)
        # Custom registry also binds the unchanged built-in NO_OP.
        registry.register("NO_OP", kernel.DEFAULT_EVENT_HANDLERS.handler_for("NO_OP"))
        failed = schedule(self.world, due, event_type="FAIL")
        request = begin_resolution(self.world, due, registry=registry)
        request.step()
        prefix = deepcopy(self.world)
        final = request.step()
        self.assertEqual(final.processing_result.failure.code, "HANDLER_FAILED")
        self.assertEqual(self.world, prefix)
        self.assertEqual(final.processing_result.completed_event_ids, (first,))
        self.assertEqual(calls, [failed])
        self.assertEqual(request.boundary().last_committed_event_id, first)

    def test_custom_handlers_keep_isolation_and_full_validation(self):
        due = "2026-08-20T05:00:00Z"
        registry = recording_registry()
        retained = []
        def retain(context):
            retained.append(context.envelope)
        registry.register("RETAIN", retain)
        schedule(self.world, due, event_type="RETAIN")
        self.assertTrue(resolve_until(self.world, due, registry=registry).succeeded)
        expected = deepcopy(self.world)
        retained[0]["world_state"]["history"]["operations"].append("leak")
        self.assertEqual(self.world, expected)
        world = make_world()
        def corrupt(context):
            context.envelope["simulation"]["event_order_cursor"] = -1
        registry.register("CORRUPT", corrupt)
        schedule(world, due, event_type="CORRUPT")
        before = deepcopy(world)
        result = resolve_until(world, due, registry=registry)
        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)

    def test_result_validation_failure_keeps_failed_event_pending(self):
        due = "2026-08-20T05:00:00Z"
        registry = kernel.EventHandlerRegistry()
        def corrupt(context):
            owner = context.event["owner_id"]
            context.envelope["world_state"]["airlines"][owner]["finance_revision"] = -1
        registry.register("CORRUPT_RESULT", corrupt)
        event = schedule(self.world, due, event_type="CORRUPT_RESULT")
        before = deepcopy(self.world)
        request = begin_resolution(self.world, due, registry=registry)
        progress = request.step()
        self.assertEqual(progress.processing_result.failure.code, "RESULT_VALIDATION_FAILED")
        self.assertEqual(self.world, before)
        self.assertIn(event, self.world["world_state"]["pending_events"])
        self.assertIsNone(request.boundary().last_committed_event_id)

    def test_stale_owner_and_unknown_event_match_strict_oracle(self):
        due = "2026-08-20T05:00:00Z"
        stale = schedule(self.world, due, event_type="UNREGISTERED")
        owner = self.world["world_state"]["player"]["primary_airline_id"]
        kernel.set_operation_revision(self.world, owner, 1)
        expected = assert_equivalent(self, self.world, due, ["2026-08-20T04:59:59Z"])
        self.assertEqual(expected["world_state"]["event_history"][stale]["status"], "STALE")
        world = make_world()
        schedule(world, due, event_type="UNREGISTERED")
        expected = deepcopy(world)
        left = resolve_until(world, due)
        right = strict_until(expected, due)
        self.assertEqual(left.failure, right.failure)
        self.assertEqual(world, expected)

    def test_timestamp_priority_sequence_generated_order_and_partitions(self):
        due = "2026-08-20T05:00:00Z"
        registry = recording_registry()
        def generate(context):
            context.envelope["world_state"]["history"]["operations"].append("parent")
            context.schedule_event(event_type="RECORD", due_at_utc=due,
                owner_type="airline", owner_id=context.event["owner_id"],
                priority=0, payload={"label": "generated"})
        registry.register("GENERATE", generate)
        schedule(self.world, due, event_type="RECORD", payload={"label": "later"}, priority=20)
        schedule(self.world, due, event_type="GENERATE", priority=10)
        schedule(self.world, due, event_type="RECORD", payload={"label": "first"}, priority=0)
        expected = assert_equivalent(self, self.world, "2026-08-20T05:00:01Z",
            ["2026-08-20T04:59:59Z", due], registry=registry)
        self.assertEqual(expected["world_state"]["history"]["operations"],
                         ["first", "parent", "generated", "later"])
        reordered = deepcopy(self.world)
        reordered["world_state"]["pending_events"] = dict(reversed(
            tuple(reordered["world_state"]["pending_events"].items())))
        resolve_until(reordered, "2026-08-20T05:00:01Z", registry=registry)
        self.assertEqual(canonical_world(reordered), canonical_world(expected))

    def test_pause_resume_and_callers_use_facade_without_persisting_requests(self):
        with tempfile.TemporaryDirectory() as root:
            session = Stage1Session(save_root=root, runtime_clock=lambda: 0)
            session.new_game("CEO", "Resolver caller", "MNL")
            now = parse_canonical_utc(session.world["simulation"]["time_utc"])
            schedule(session.world, format_utc(now + timedelta(seconds=1)))
            session.resume()
            session.runtime.credit_ns = 2 * NANOSECOND
            session.pump()
            self.assertIsInstance(session.runtime.work, ResolutionRequest)
            request = session.runtime.work
            session.pause()
            self.assertIs(session.runtime.work, request)
            self.assertEqual(session.runtime.state, 'PLAYER_DRAIN')
            session.pump()
            self.assertEqual(session.world['simulation']['time_utc'], format_utc(now + timedelta(seconds=2)))
            self.assertEqual(session.runtime.credit_ns, 0)
            self.assertEqual(session.runtime.state, 'PAUSED')
            self.assertTrue(request.finished)
            session.resume()
            self.assertIsNone(session.runtime.work)
            session.pump()
            session.pause()
            session.begin_advance_to(format_utc(now + timedelta(seconds=3)))
            self.assertIsInstance(session._bulk_work, ResolutionRequest)
            while session.advancing:
                session.advance_tick()
            session.save_manual()
            restored = save_reload(session.world)
            self.assertEqual(restored, session.world)
            self.assertNotIn("requested_target_utc", canonical_world(restored))
            self.assertEqual(restored["simulation"]["clock_state"], "PAUSED")

    def test_protected_fences_recorded_and_kernel_transaction_counts_unchanged(self):
        self.assertEqual(PROTECTED_CAUSAL_FENCES, {
            "DAILY_BOOKING_CHECKPOINT", "STAGE1_WEEKLY_PUBLICATION", "AIRCRAFT_CONTRACT_EXPIRY",
            "QUARTERLY_PUBLICATION"})
        registry = recording_registry()
        due = "2026-08-20T05:00:00Z"
        for label in ("a", "b"):
            schedule(self.world, due, event_type="RECORD", payload={"label": label})
        counts = []
        worlds = []
        for run in (kernel.process_events_through, resolve_until):
            world = deepcopy(self.world)
            with patch.object(kernel, "validate_world", wraps=validate_world) as validations, patch.object(
                    kernel, "_clone_runtime_world", wraps=kernel._clone_runtime_world) as copies:
                result = run(world, due, registry=registry)
            self.assertTrue(result.succeeded)
            counts.append((validations.call_count, copies.call_count))
            worlds.append(world)
        self.assertEqual(counts, [(4, 4), (4, 4)])
        self.assertEqual(worlds[0], worlds[1])


def ph_world(seed=None):
    arguments = dict(scenario_id="stage1-philippines-v1", ceo_display_name="Oracle",
                     airline_display_name="Resolver Air", base_airport_reference_code="MNL")
    if seed is None:
        return create_stage1_new_game(**arguments)
    pack = deepcopy(load_stage1_scenario("stage1-philippines-v1"))
    pack["simulation_seed"] = seed
    with tempfile.TemporaryDirectory() as root:
        reference = Path(root) / "scenario.json"
        reference.write_text(json.dumps(pack), encoding="utf-8")
        return create_stage1_new_game(**arguments, reference_path=reference)


def published_pair(world, *, continuous=False, finite=False):
    state = world["world_state"]
    owner = state["player"]["primary_airline_id"]
    ports = {row["reference_code"]: key for key, row in state["airports"].items()}
    draft = WeeklyDraft(world, airline_id=owner, aircraft_id=next(iter(state["aircraft"])))
    draft.add_weekdays(ports["MNL"], ports["DVO"], ("2026-08-31",), "08:00",
                       return_flight=True, fare_minor=11600)
    result = draft.save_current(world, continuous=continuous,
                                repeat_until="2026-09-14" if finite else None)
    if not result.succeeded:
        raise AssertionError(result)
    return world


class ResolverGameplayEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ph_world()

    def test_continuous_week_roll_booking_flights_finance_and_inflight_save(self):
        base = published_pair(deepcopy(self.base), continuous=True)
        expected = assert_equivalent(self, base, "2026-09-07T04:00:00Z",
            ["2026-09-02T00:00:00Z", "2026-09-06T15:59:59Z",
             "2026-09-06T16:00:00Z", "2026-09-07T00:00:00Z",
             "2026-09-07T01:40:00Z", "2026-09-07T02:10:00Z"],
             save_at="2026-09-07T00:00:01Z")
        state = expected["world_state"]
        self.assertEqual(len(state["flight_results"]), 2)
        self.assertTrue(state["bookings"])
        types = {event["event_type"] for event in state["event_history"].values()}
        self.assertTrue(PROTECTED_CAUSAL_FENCES - {"AIRCRAFT_CONTRACT_EXPIRY", "QUARTERLY_PUBLICATION"} <= types)
        self.assertNotIn('QUARTERLY_PUBLICATION', types)
        self.assertNotIn('quarterly_publication', expected['simulation'])
        self.assertIn("STAGE1_FLIGHT_DEPARTURE", types)
        self.assertIn("STAGE1_FLIGHT_COMPLETION", types)

    def test_finite_recurrence_and_different_seed_booking_partitioning(self):
        base = published_pair(ph_world(314159), finite=True)
        expected = assert_equivalent(self, base, "2026-09-07T04:00:00Z",
            ["2026-09-03T12:34:56Z", "2026-09-06T23:59:59Z",
             "2026-09-07T00:00:00Z"], save_at="2026-09-07T02:10:01Z")
        self.assertTrue(expected["world_state"]["bookings"])
        reordered = deepcopy(base)
        for collection in ("dated_flights", "pending_events", "schedule_definitions",
                           "aircraft", "directional_markets"):
            reordered["world_state"][collection] = dict(reversed(
                tuple(reordered["world_state"][collection].items())))
        self.assertTrue(resolve_until(reordered, "2026-09-07T04:00:00Z").succeeded)
        self.assertEqual(canonical_world(reordered), canonical_world(expected))
        self.assertEqual(expected["deterministic_state"]["world_seed"], 314159)
        self.assertEqual(len(expected["world_state"]["flight_results"]), 2)
        self.assertTrue(all(schedule["revisions"]["1"]["recurrence"]["until_local_date"]
                            == "2026-09-14"
                            for schedule in expected["world_state"]["schedule_definitions"].values()))

    def test_month_rotation_and_contract_payment_same_boundary(self):
        world = deepcopy(self.base)
        state = world["world_state"]
        owner = state["player"]["primary_airline_id"]
        offer = state["aircraft_market_state"]["active_lease_offer_ids"][0]
        preview = preview_lease(world, airline_id=owner, offer_id=offer,
            contract_type="LEASE_TO_OWN", term_years=1,
            delivery_airport_id=state["airlines"][owner]["base_airport_ids"][0])
        accept_lease(world, preview)
        # Reach the real boundary through the oracle, never fabricate game time.
        self.assertTrue(strict_until(world, "2026-09-30T23:59:59Z").succeeded)
        expected = assert_equivalent(self, world, "2026-10-01T00:00:01Z",
            ["2026-10-01T00:00:00Z"], save_at="2026-10-01T00:00:00Z")
        contract = next(iter(expected["world_state"]["aircraft_contracts"].values()))
        self.assertEqual(contract["paid_installments"], 1)
        records = [row for row in expected["world_state"]["event_history"].values()
                   if row["due_at_utc"] == "2026-10-01T00:00:00Z"]
        self.assertEqual({row["event_type"] for row in records}, {
            "DAILY_BOOKING_CHECKPOINT", "AIRCRAFT_MARKET_ROTATION", "AIRCRAFT_CONTRACT_PAYMENT"})

    def test_real_contract_expiry_final_payment_and_month_boundary(self):
        world = deepcopy(self.base)
        state = world["world_state"]
        owner = state["player"]["primary_airline_id"]
        preview = preview_lease(world, airline_id=owner,
            offer_id=state["aircraft_market_state"]["active_lease_offer_ids"][0],
            contract_type="OPERATING_LEASE", term_years=1,
            delivery_airport_id=state["airlines"][owner]["base_airport_ids"][0])
        aircraft = accept_lease(world, preview)
        contract = next(iter(world["world_state"]["aircraft_contracts"].values()))
        expiry = contract["expires_at_utc"]
        before = format_utc(parse_canonical_utc(expiry) - timedelta(seconds=1))
        # Mature the actual one-year obligation through production events.
        # No shortened term, fabricated paid installments, or clock mutation.
        result = kernel.process_events_through(world, before, max_generated_events=10000)
        self.assertTrue(result.succeeded, result.failure)
        target = format_utc(parse_canonical_utc(expiry) + timedelta(seconds=1))
        expected = assert_equivalent(self, world, target, [expiry], save_at=expiry)
        state = expected["world_state"]
        self.assertEqual(state["aircraft"][aircraft]["status"], "RETURNED")
        settled = state["aircraft_contracts"][contract["aircraft_contract_id"]]
        self.assertEqual(settled["paid_installments"], settled["total_installments"])
        self.assertTrue(any(row["event_type"] == "AIRCRAFT_CONTRACT_EXPIRY"
                            and row["due_at_utc"] == expiry
                            for row in state["event_history"].values()))

    def test_booked_protection_with_same_player_revision_action(self):
        base = published_pair(deepcopy(self.base), continuous=True)
        worlds = []
        for run in (strict_until, resolve_until):
            world = deepcopy(base)
            self.assertTrue(run(world, "2026-09-02T00:00:00Z").succeeded)
            before = deepcopy(world["world_state"]["dated_flights"])
            owner = world["world_state"]["player"]["primary_airline_id"]
            draft = WeeklyDraft.edit_recurring(world, airline_id=owner,
                        aircraft_id=next(iter(world["world_state"]["aircraft"])))
            draft.reschedule(0, "2026-10-05", "07:50")
            self.assertTrue(draft.save_current(world, continuous=True).succeeded)
            self.assertEqual(world["world_state"]["dated_flights"], before)
            self.assertTrue(run(world, "2026-09-06T16:00:00Z").succeeded)
            worlds.append(world)
        self.assertEqual(canonical_world(worlds[0]), canonical_world(worlds[1]))

    def test_capacity_contention_with_existing_booking_fixture(self):
        from tests.test_stage1_booking_shopping import schema3_world
        from game.booking import prepare_daily_booking_checkpoint, process_daily_booking_checkpoint
        world, _market, flight = schema3_world()
        prepared = prepare_daily_booking_checkpoint(world)
        self.assertTrue(prepared.succeeded, prepared.issues)
        self.assertTrue(process_daily_booking_checkpoint(world, **prepared.arguments).succeeded)
        target = "2026-08-21T00:00:01Z"
        expected = assert_equivalent(self, world, target,
            ["2026-08-20T23:59:59Z", "2026-08-21T00:00:00Z"])
        self.assertTrue(expected["world_state"]["bookings"])
        from game.booking.indexes import rebuild_booking_indexes
        self.assertEqual(rebuild_booking_indexes(world).booked_passenger_count_by_dated_flight_id[flight], 180)


if __name__ == "__main__":
    unittest.main()
