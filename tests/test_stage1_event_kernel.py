"""Milestone 2 continuous-clock and deterministic event-kernel tests."""

from copy import deepcopy
import heapq
from time import perf_counter
from types import MappingProxyType
import unittest
from unittest.mock import patch

from game.simulation import (
    EventHandlerRegistry,
    advance_by_real_seconds,
    advance_to,
    begin_fast_forward,
    build_event_queue_index,
    cancel_event,
    configure_clock_ratios,
    process_events_through,
    process_next_event,
    run_fast_forward,
    schedule_event,
    set_clock_mode,
    set_operation_revision,
    stop_fast_forward,
    supersede_event,
)
from game.world_state import validate_world
from tests.test_stage1_world_state import make_world


START = "2026-08-20T04:30:00Z"


def airline_id(world):
    return world["world_state"]["player"]["primary_airline_id"]


def schedule(world, due, *, event_type="NO_OP", payload=None, priority=0):
    return schedule_event(
        world,
        event_type=event_type,
        due_at_utc=due,
        owner_type="airline",
        owner_id=airline_id(world),
        payload=payload,
        priority=priority,
    )


def recording_registry():
    registry = EventHandlerRegistry()

    def record(context):
        context.envelope["world_state"]["history"]["operations"].append(
            context.payload["label"]
        )

    registry.register("RECORD", record)
    return registry


class Stage1ClockTests(unittest.TestCase):
    def test_new_world_begins_paused_and_paused_advance_is_frozen(self):
        world = make_world()
        self.assertEqual(world["simulation"]["clock_state"], "PAUSED")
        result = advance_by_real_seconds(world, 3_600)
        self.assertEqual(result.status, "PAUSED")
        self.assertEqual(world["simulation"]["time_utc"], START)

    def test_normal_and_fast_use_configurable_exact_ratios(self):
        world = make_world()
        configure_clock_ratios(world, normal=3, fast=120)
        set_clock_mode(world, "NORMAL")
        advance_by_real_seconds(world, 10)
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T04:30:30Z")
        set_clock_mode(world, "FAST")
        advance_by_real_seconds(world, 2)
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T04:34:30Z")

    def test_repeated_small_real_advances_equal_one_large_advance(self):
        small = make_world()
        configure_clock_ratios(small, normal=7)
        set_clock_mode(small, "NORMAL")
        large = deepcopy(small)
        for _index in range(10):
            advance_by_real_seconds(small, 3)
        advance_by_real_seconds(large, 30)
        self.assertEqual(small, large)

    def test_ratio_inputs_reject_boolean_zero_negative_and_partial_mutation(self):
        for invalid in (True, 0, -1, 1.5):
            world = make_world()
            original = deepcopy(world["simulation"]["configuration"]["clock_ratios"])
            with self.assertRaises(ValueError):
                configure_clock_ratios(world, normal=2, fast=invalid)
            self.assertEqual(world["simulation"]["configuration"]["clock_ratios"], original)

    def test_excessive_exact_advance_rejects_without_mutation(self):
        world = make_world()
        configure_clock_ratios(world, normal=10**100)
        set_clock_mode(world, "NORMAL")
        before = deepcopy(world)
        with self.assertRaises(ValueError):
            advance_by_real_seconds(world, 1)
        self.assertEqual(world, before)

    def test_backward_and_noncanonical_utc_advancement_are_rejected(self):
        world = make_world()
        set_clock_mode(world, "NORMAL")
        for target in (
            "2026-08-20T04:29:59Z",
            "2026-08-20T04:31:00+00:00",
            "2026-08-20T12:31:00+08:00",
            "2026-08-20T04:31:00",
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                advance_to(world, target)

    def test_fast_forward_requires_explicit_target_and_stops_paused(self):
        world = make_world()
        begin_fast_forward(world, "2026-08-20T05:00:00Z")
        self.assertEqual(world["simulation"]["clock_state"], "FAST_FORWARD")
        result = run_fast_forward(world)
        self.assertEqual(result.ended_at_utc, "2026-08-20T05:00:00Z")
        self.assertEqual(world["simulation"]["clock_state"], "PAUSED")
        self.assertIsNone(world["simulation"]["fast_forward"]["target_time_utc"])

    def test_fast_forward_can_be_stopped_without_advancing(self):
        world = make_world()
        begin_fast_forward(world, "2026-08-21T00:00:00Z")
        stop_fast_forward(world)
        self.assertEqual(world["simulation"]["time_utc"], START)
        self.assertTrue(validate_world(world).is_valid)

    def test_fast_forward_failure_pauses_at_blocking_boundary(self):
        world = make_world()
        failed = schedule(world, "2026-08-20T05:00:00Z", event_type="UNKNOWN")
        begin_fast_forward(world, "2026-08-20T06:00:00Z")
        result = run_fast_forward(world)
        self.assertEqual(result.failure.event_id, failed)
        self.assertEqual(world["simulation"]["time_utc"], START)
        self.assertEqual(world["simulation"]["clock_state"], "PAUSED")
        self.assertIsNone(world["simulation"]["fast_forward"]["target_time_utc"])

    def test_validator_covers_modes_ratios_and_fast_forward_target(self):
        mutations = (
            lambda world: world["simulation"].update(clock_state="FAST FORWARD"),
            lambda world: world["simulation"]["configuration"]["clock_ratios"].update(NORMAL=True),
            lambda world: world["simulation"].update(
                clock_state="FAST_FORWARD",
                fast_forward={"target_time_utc": "2026-08-20T05:00:00+00:00"},
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                world = make_world()
                mutate(world)
                self.assertFalse(validate_world(world).is_valid)


class Stage1EventOrderingTests(unittest.TestCase):
    def test_events_execute_by_timestamp_and_equal_time_persisted_order(self):
        world = make_world()
        registry = recording_registry()
        third = schedule(world, "2026-08-20T05:00:00Z", event_type="RECORD", payload={"label": "third"})
        first = schedule(world, "2026-08-20T04:40:00Z", event_type="RECORD", payload={"label": "first"})
        second = schedule(world, "2026-08-20T05:00:00Z", event_type="RECORD", payload={"label": "second"}, priority=0)
        result = process_events_through(world, "2026-08-20T05:00:00Z", registry=registry)
        self.assertEqual(result.completed_event_ids, (first, third, second))
        self.assertEqual(world["world_state"]["history"]["operations"], ["first", "third", "second"])

    def test_dictionary_insertion_order_does_not_affect_queue(self):
        left = make_world()
        ids = [schedule(left, "2026-08-20T05:00:00Z", priority=value) for value in (2, 0, 1)]
        right = deepcopy(left)
        pending = right["world_state"]["pending_events"]
        right["world_state"]["pending_events"] = {
            key: pending[key] for key in reversed(tuple(pending))
        }
        left_heap = build_event_queue_index(left)
        right_heap = build_event_queue_index(right)
        left_order = [heapq.heappop(left_heap)[3] for _ in range(len(left_heap))]
        right_order = [heapq.heappop(right_heap)[3] for _ in range(len(right_heap))]
        self.assertEqual(left_order, right_order)
        self.assertEqual(process_events_through(left, "2026-08-20T05:00:00Z").completed_event_ids, tuple(ids[1:] + ids[:1]))
        process_events_through(right, "2026-08-20T05:00:00Z")
        self.assertEqual(left, right)

    def test_queue_index_is_derived_and_rebuildable(self):
        world = make_world()
        late = schedule(world, "2026-08-20T06:00:00Z")
        early = schedule(world, "2026-08-20T05:00:00Z")
        index_one = build_event_queue_index(world)
        index_two = build_event_queue_index(deepcopy(world))
        self.assertEqual(index_one, index_two)
        self.assertEqual(index_one[0][3], early)
        self.assertNotIn("event_queue", world["world_state"])
        self.assertIn(late, world["world_state"]["pending_events"])

    def test_event_id_and_sequence_are_collision_safe_after_history(self):
        world = make_world()
        first = schedule(world, "2026-08-20T05:00:00Z")
        process_next_event(world)
        world["deterministic_state"]["id_allocator"]["next_by_type"]["event"] = 1
        self.assertIn("id_allocator_collision", {issue.code for issue in validate_world(world).errors})
        with self.assertRaises(ValueError):
            schedule(world, "2026-08-20T06:00:00Z")
        world["deterministic_state"]["id_allocator"]["next_by_type"]["event"] = 2
        second = schedule(world, "2026-08-20T06:00:00Z")
        self.assertNotEqual(first, second)
        self.assertEqual(world["world_state"]["pending_events"][second]["order_key"], [0, 1])

    def test_rewound_order_cursor_is_refused_before_collision(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z")
        world["simulation"]["event_order_cursor"] = 0
        with self.assertRaises(ValueError):
            schedule(world, "2026-08-20T06:00:00Z")

    def test_validator_rejects_duplicate_order_values_and_bad_cursor(self):
        world = make_world()
        first = schedule(world, "2026-08-20T05:00:00Z")
        second = schedule(world, "2026-08-20T05:00:00Z")
        world["world_state"]["pending_events"][second]["order_key"] = list(
            world["world_state"]["pending_events"][first]["order_key"]
        )
        codes = {issue.code for issue in validate_world(world).errors}
        self.assertIn("duplicate_event_order", codes)
        world["simulation"]["event_order_cursor"] = 0
        self.assertIn("invalid_event_cursor", {issue.code for issue in validate_world(world).errors})

    def test_validator_rejects_pending_past_and_pending_history_conflict(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z")
        world["world_state"]["pending_events"][event_id]["due_at_utc"] = "2026-08-20T04:00:00Z"
        self.assertIn("event_scheduled_in_past", {issue.code for issue in validate_world(world).errors})
        conflict = deepcopy(world["world_state"]["pending_events"][event_id])
        conflict.update(status="COMPLETED", resolved_at_utc=START)
        world["world_state"]["event_history"][event_id] = conflict
        self.assertIn("duplicate_id", {issue.code for issue in validate_world(world).errors})

    def test_validator_rejects_impossible_terminal_resolution_time(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z")
        process_next_event(world)
        world["world_state"]["event_history"][event_id]["resolved_at_utc"] = "2026-08-20T06:00:00Z"
        self.assertIn("invalid_event_resolution", {issue.code for issue in validate_world(world).errors})

    def test_malformed_authority_returns_structured_errors_without_crashing(self):
        def event_world():
            world = make_world()
            event_id = schedule(world, "2026-08-20T05:00:00Z")
            return world, event_id

        cases = []
        world = make_world()
        world["simulation"]["clock_state"] = []
        cases.append(world)
        world = make_world()
        world["simulation"]["configuration"]["clock_ratios"][1] = 2
        cases.append(world)
        world = make_world()
        world["simulation"]["configuration"]["clock_ratios"]["FAST"] = -1
        cases.append(world)
        world, event_id = event_world()
        world["world_state"]["pending_events"][event_id]["status"] = []
        cases.append(world)
        world, event_id = event_world()
        world["world_state"]["pending_events"][event_id]["order_key"] = [False, True]
        cases.append(world)
        world, event_id = event_world()
        world["world_state"]["pending_events"][event_id]["operation_revision"] = -1
        cases.append(world)
        world, event_id = event_world()
        world["world_state"]["pending_events"][event_id]["payload"] = {"bad": float("nan")}
        cases.append(world)
        world, event_id = event_world()
        world["world_state"]["pending_events"][event_id]["resolved_at_utc"] = START
        cases.append(world)
        world, event_id = event_world()
        pending = world["world_state"]["pending_events"].pop(event_id)
        pending["status"] = "COMPLETED"
        world["world_state"]["event_history"][event_id] = pending
        cases.append(world)
        world, event_id = event_world()
        pending = world["world_state"]["pending_events"].pop(event_id)
        pending.update(status=[], resolved_at_utc=START)
        world["world_state"]["event_history"][event_id] = pending
        cases.append(world)
        world, event_id = event_world()
        world["world_state"]["pending_events"][event_id].update(
            owner_type="aircraft", owner_id=airline_id(world)
        )
        cases.append(world)
        world = make_world()
        world[1] = {}
        cases.append(world)
        world = make_world()
        owner = airline_id(world)
        world["world_state"]["airlines"][owner]["control_type"] = []
        cases.append(world)
        world = make_world()
        owner = airline_id(world)
        account_id = world["world_state"]["airlines"][owner]["financial_account_ids"][0]
        world["world_state"]["financial_accounts"][account_id]["category"] = []
        cases.append(world)

        for index, malformed in enumerate(cases):
            with self.subTest(case=index):
                result = validate_world(malformed)
                self.assertFalse(result.is_valid)
                self.assertTrue(result.errors)

    def test_deeply_nested_non_json_payload_returns_structured_error(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z")
        nested = {"bad": set()}
        for _index in range(1_200):
            nested = [nested]
        world["world_state"]["pending_events"][event_id]["payload"] = {
            "nested": nested
        }
        result = validate_world(world)
        self.assertFalse(result.is_valid)
        self.assertIn("not_json_compatible", {issue.code for issue in result.errors})


class Stage1EventLifecycleTests(unittest.TestCase):
    def test_event_executes_at_most_once_and_moves_to_history(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z")
        first = process_next_event(world)
        second = process_next_event(world)
        self.assertEqual(first.completed_event_ids, (event_id,))
        self.assertEqual(second.status, "NO_EVENT")
        self.assertNotIn(event_id, world["world_state"]["pending_events"])
        self.assertEqual(world["world_state"]["event_history"][event_id]["status"], "COMPLETED")

    def test_process_next_executes_exactly_one_equal_time_event(self):
        world = make_world()
        first = schedule(world, "2026-08-20T05:00:00Z")
        second = schedule(world, "2026-08-20T05:00:00Z")
        result = process_next_event(world)
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertIn(second, world["world_state"]["pending_events"])

    def test_cancelled_and_superseded_events_never_execute(self):
        for resolver, status in ((cancel_event, "CANCELLED"), (supersede_event, "SUPERSEDED")):
            with self.subTest(status=status):
                world = make_world()
                event_id = schedule(world, "2026-08-20T05:00:00Z")
                resolver(world, event_id)
                result = process_events_through(world, "2026-08-20T06:00:00Z")
                self.assertEqual(result.completed_event_ids, ())
                self.assertEqual(world["world_state"]["event_history"][event_id]["status"], status)

    def test_stale_revision_is_archived_without_handler_mutation(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z", event_type="RECORD", payload={"label": "bad"})
        set_operation_revision(world, airline_id(world), 1)
        result = process_events_through(world, "2026-08-20T05:00:00Z", registry=recording_registry())
        self.assertEqual(result.skipped_event_ids, (event_id,))
        self.assertEqual(world["world_state"]["history"]["operations"], [])
        self.assertEqual(world["world_state"]["event_history"][event_id]["status"], "STALE")

    def test_revision_cannot_move_backward_or_schedule_a_future_revision(self):
        world = make_world()
        owner = airline_id(world)
        set_operation_revision(world, owner, 2)
        before = deepcopy(world)
        with self.assertRaises(ValueError):
            set_operation_revision(world, owner, 1)
        self.assertEqual(world, before)
        with self.assertRaises(ValueError):
            schedule_event(
                world,
                event_type="NO_OP",
                due_at_utc="2026-08-20T05:00:00Z",
                owner_type="airline",
                owner_id=owner,
                operation_revision=3,
            )
        self.assertEqual(world, before)

    def test_event_allocator_exhaustion_rejects_without_partial_mutation(self):
        world = make_world()
        world["deterministic_state"]["id_allocator"]["next_by_type"][
            "event"
        ] = 1_000_000_000_000
        before = deepcopy(world)
        with self.assertRaises(ValueError):
            schedule(world, "2026-08-20T05:00:00Z")
        self.assertEqual(world, before)

    def test_unknown_event_type_blocks_and_remains_pending(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z", event_type="UNKNOWN")
        before = deepcopy(world)
        result = process_events_through(world, "2026-08-20T06:00:00Z")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.failure.code, "UNKNOWN_EVENT_TYPE")
        self.assertEqual(result.failure.event_id, event_id)
        self.assertEqual(world, before)

    def test_malformed_or_unserializable_payload_fails_structurally(self):
        world = make_world()
        with self.assertRaises(ValueError):
            schedule(world, "2026-08-20T05:00:00Z", payload={"callback": lambda: None})
        with self.assertRaises(ValueError):
            schedule(
                world,
                "2026-08-20T05:00:00Z",
                payload={"proxy": MappingProxyType({"value": 1})},
            )
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                schedule(world, "2026-08-20T05:00:00Z", payload={"value": value})
        event_id = schedule(world, "2026-08-20T05:00:00Z")
        world["world_state"]["pending_events"][event_id]["payload"] = {"bad"}
        result = process_next_event(world)
        self.assertEqual(result.failure.code, "INVALID_WORLD")
        self.assertTrue(result.failure.validation_errors)

    def test_handler_exception_rolls_back_every_mutation(self):
        world = make_world()
        event_id = schedule(world, "2026-08-20T05:00:00Z", event_type="FAIL")
        registry = EventHandlerRegistry()

        def fail(context):
            context.envelope["world_state"]["history"]["operations"].append("partial")
            raise RuntimeError("intentional")

        registry.register("FAIL", fail)
        before = deepcopy(world)
        result = process_next_event(world, registry=registry)
        self.assertEqual(result.failure.code, "HANDLER_FAILED")
        self.assertEqual(result.failure.event_id, event_id)
        self.assertEqual(world, before)

    def test_failed_handler_does_not_leak_created_events_or_payload_mutation(self):
        world = make_world()
        event_id = schedule(
            world,
            "2026-08-20T05:00:00Z",
            event_type="FAIL_AFTER_SPAWN",
            payload={"nested": {"values": [1]}},
        )
        registry = EventHandlerRegistry()

        def fail_after_spawn(context):
            context.payload["nested"]["values"].append(2)
            context.schedule_event(
                event_type="NO_OP",
                due_at_utc=context.event["due_at_utc"],
                owner_type=context.event["owner_type"],
                owner_id=context.event["owner_id"],
            )
            raise RuntimeError("rollback everything")

        registry.register("FAIL_AFTER_SPAWN", fail_after_spawn)
        before = deepcopy(world)
        result = process_next_event(world, registry=registry)
        self.assertEqual(result.failure.code, "HANDLER_FAILED")
        self.assertEqual(world, before)
        self.assertEqual(
            world["world_state"]["pending_events"][event_id]["payload"],
            {"nested": {"values": [1]}},
        )

    def test_result_validation_failure_rolls_back_every_mutation(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z", event_type="INVALID")
        registry = EventHandlerRegistry()

        def invalidate(context):
            context.envelope["world_state"]["history"]["operations"].append(
                lambda: None
            )

        registry.register("INVALID", invalidate)
        before = deepcopy(world)
        result = process_next_event(world, registry=registry)
        self.assertEqual(result.failure.code, "RESULT_VALIDATION_FAILED")
        self.assertEqual(world, before)

    def test_handler_return_and_existing_event_mutation_violate_contract(self):
        scenarios = {
            "RETURN": lambda _context: {"unvalidated": "result"},
            "ALTER_QUEUE": lambda context: context.envelope["world_state"][
                "pending_events"
            ][context.event["event_id"]].update(priority=99),
            "JUMP_TIME": lambda context: context.envelope["simulation"].update(
                time_utc="2026-08-20T06:00:00Z"
            ),
            "BURN_CURSOR": lambda context: context.envelope["simulation"].update(
                event_order_cursor=context.envelope["simulation"][
                    "event_order_cursor"
                ]
                + 1
            ),
            "DESTROY_ROOT": lambda context: context.envelope.clear(),
        }
        for event_type, handler in scenarios.items():
            with self.subTest(event_type=event_type):
                world = make_world()
                schedule(world, "2026-08-20T05:00:00Z", event_type=event_type)
                registry = EventHandlerRegistry()
                registry.register(event_type, handler)
                before = deepcopy(world)
                result = process_next_event(world, registry=registry)
                self.assertEqual(result.failure.code, "HANDLER_CONTRACT_VIOLATION")
                self.assertEqual(world, before)

    def test_handler_cannot_rewrite_existing_terminal_history(self):
        world = make_world()
        historical_id = schedule(world, "2026-08-20T04:40:00Z")
        process_next_event(world)
        schedule(world, "2026-08-20T05:00:00Z", event_type="REWRITE")
        registry = EventHandlerRegistry()

        def rewrite(context):
            context.envelope["world_state"]["event_history"][historical_id][
                "payload"
            ]["rewritten"] = True

        registry.register("REWRITE", rewrite)
        before = deepcopy(world)
        result = process_next_event(world, registry=registry)
        self.assertEqual(result.failure.code, "HANDLER_CONTRACT_VIOLATION")
        self.assertEqual(world, before)

    def test_handler_payload_is_a_detached_command_copy(self):
        world = make_world()
        event_id = schedule(
            world,
            "2026-08-20T05:00:00Z",
            event_type="TOUCH_PAYLOAD",
            payload={"nested": [1]},
        )
        registry = EventHandlerRegistry()
        registry.register(
            "TOUCH_PAYLOAD", lambda context: context.payload["nested"].append(2)
        )
        self.assertTrue(process_next_event(world, registry=registry).succeeded)
        self.assertEqual(
            world["world_state"]["event_history"][event_id]["payload"],
            {"nested": [1]},
        )

    def test_handler_context_does_not_expose_live_registry(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z", event_type="INSPECT")
        registry = EventHandlerRegistry()

        def inspect(context):
            self.assertFalse(hasattr(context, "registry"))

        registry.register("INSPECT", inspect)
        with self.assertRaises(ValueError):
            registry.register("INSPECT", inspect)
        self.assertTrue(process_next_event(world, registry=registry).succeeded)

    def test_custom_no_op_registration_does_not_use_builtin_shortcut(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z")
        registry = EventHandlerRegistry()
        registry.register(
            "NO_OP",
            lambda context: context.envelope["world_state"]["history"][
                "operations"
            ].append("custom handler ran"),
        )
        self.assertTrue(process_next_event(world, registry=registry).succeeded)
        self.assertEqual(
            world["world_state"]["history"]["operations"],
            ["custom handler ran"],
        )

    def test_successful_handler_commit_shares_no_mutable_state_with_old_world(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z", event_type="MUTATE")
        old_operations = world["world_state"]["history"]["operations"]
        registry = EventHandlerRegistry()
        registry.register(
            "MUTATE",
            lambda context: context.envelope["world_state"]["history"][
                "operations"
            ].append("committed"),
        )
        self.assertTrue(process_next_event(world, registry=registry).succeeded)
        self.assertIsNot(
            old_operations, world["world_state"]["history"]["operations"]
        )
        old_operations.append("leak")
        self.assertEqual(
            world["world_state"]["history"]["operations"], ["committed"]
        )

    def test_handler_retained_candidate_cannot_mutate_committed_authority(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z", event_type="CAPTURE")
        captured = []
        registry = EventHandlerRegistry()

        def capture(context):
            captured.append(context.envelope)
            context.envelope["world_state"]["history"]["operations"].append(
                "committed"
            )

        registry.register("CAPTURE", capture)
        self.assertTrue(process_next_event(world, registry=registry).succeeded)
        captured[0]["world_state"]["history"]["operations"].append("late leak")
        self.assertEqual(
            world["world_state"]["history"]["operations"], ["committed"]
        )

    def test_handler_scheduled_eligible_event_is_processed_in_same_advance(self):
        world = make_world()
        registry = EventHandlerRegistry()

        def spawn(context):
            context.schedule_event(
                event_type="NO_OP",
                due_at_utc=context.event["due_at_utc"],
                owner_type=context.event["owner_type"],
                owner_id=context.event["owner_id"],
            )

        registry.register("SPAWN", spawn)
        registry.register("NO_OP", lambda _context: None)
        original = schedule(world, "2026-08-20T05:00:00Z", event_type="SPAWN")
        preexisting = schedule(world, "2026-08-20T05:00:00Z")
        result = process_events_through(world, "2026-08-20T05:00:00Z", registry=registry)
        self.assertEqual(result.completed_event_ids[0], original)
        self.assertEqual(result.completed_event_ids[1], preexisting)
        self.assertEqual(len(result.completed_event_ids), 3)
        self.assertEqual(world["world_state"]["pending_events"], {})

    def test_same_timestamp_self_scheduling_hits_deterministic_limit(self):
        world = make_world()
        registry = EventHandlerRegistry()

        def repeat(context):
            context.schedule_event(
                event_type="REPEAT",
                due_at_utc=context.event["due_at_utc"],
                owner_type=context.event["owner_type"],
                owner_id=context.event["owner_id"],
            )

        registry.register("REPEAT", repeat)
        schedule(world, "2026-08-20T05:00:00Z", event_type="REPEAT")
        result = process_events_through(
            world,
            "2026-08-20T06:00:00Z",
            registry=registry,
            max_generated_events=5,
        )
        self.assertEqual(result.failure.code, "EVENT_GENERATION_LIMIT_REACHED")
        self.assertEqual(len(result.completed_event_ids), 5)
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T05:00:00Z")
        self.assertEqual(len(world["world_state"]["pending_events"]), 1)
        self.assertTrue(validate_world(world).is_valid)

    def test_total_processing_limit_leaves_next_event_pending(self):
        world = make_world()
        event_ids = [schedule(world, "2026-08-20T05:00:00Z") for _ in range(3)]
        result = process_events_through(
            world, "2026-08-20T06:00:00Z", max_events=2
        )
        self.assertEqual(result.failure.code, "EVENT_LIMIT_REACHED")
        self.assertEqual(result.completed_event_ids, tuple(event_ids[:2]))
        self.assertIn(event_ids[2], world["world_state"]["pending_events"])
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T05:00:00Z")

    def test_blocking_failure_is_not_bypassed(self):
        world = make_world()
        failed = schedule(world, "2026-08-20T05:00:00Z", event_type="UNKNOWN")
        later = schedule(world, "2026-08-20T06:00:00Z")
        result = process_events_through(world, "2026-08-20T07:00:00Z")
        self.assertEqual(result.failure.event_id, failed)
        self.assertEqual(world["simulation"]["time_utc"], START)
        self.assertIn(later, world["world_state"]["pending_events"])


class Stage1DeterminismAndPerformanceTests(unittest.TestCase):
    def test_target_is_exact_and_chunked_equals_one_shot(self):
        one_shot = make_world()
        schedule(one_shot, "2026-08-20T05:00:00Z")
        chunked = deepcopy(one_shot)
        process_events_through(one_shot, "2026-08-20T07:00:00Z")
        process_events_through(chunked, "2026-08-20T05:30:00Z")
        process_events_through(chunked, "2026-08-20T07:00:00Z")
        self.assertEqual(one_shot["simulation"]["time_utc"], "2026-08-20T07:00:00Z")
        self.assertEqual(one_shot, chunked)

    def test_speed_changes_do_not_change_event_results(self):
        normal = make_world()
        schedule(normal, "2026-08-20T05:00:00Z", event_type="RECORD", payload={"label": "same"})
        fast = deepcopy(normal)
        configure_clock_ratios(normal, normal=60)
        configure_clock_ratios(fast, fast=120)
        set_clock_mode(normal, "NORMAL")
        set_clock_mode(fast, "FAST")
        advance_by_real_seconds(normal, 60, registry=recording_registry())
        advance_by_real_seconds(fast, 30, registry=recording_registry())
        set_clock_mode(normal, "PAUSED")
        set_clock_mode(fast, "PAUSED")
        normal["simulation"]["configuration"]["clock_ratios"] = fast["simulation"]["configuration"]["clock_ratios"]
        self.assertEqual(normal, fast)

    def test_normal_and_fast_forward_produce_equivalent_authority(self):
        ordinary = make_world()
        for due in ("2026-08-20T05:00:00Z", "2026-08-20T06:00:00Z"):
            schedule(ordinary, due)
        fast_forward = deepcopy(ordinary)
        set_clock_mode(ordinary, "NORMAL")
        advance_to(ordinary, "2026-08-20T07:00:00Z")
        set_clock_mode(ordinary, "PAUSED")
        begin_fast_forward(fast_forward, "2026-08-20T07:00:00Z")
        run_fast_forward(fast_forward)
        self.assertEqual(ordinary, fast_forward)

    def test_equal_time_order_matches_next_advance_and_fast_forward(self):
        stepped = make_world()
        for priority in (2, 0, 1):
            schedule(stepped, "2026-08-20T05:00:00Z", priority=priority)
        advanced = deepcopy(stepped)
        fast_forward = deepcopy(stepped)
        stepped_order = tuple(
            process_next_event(stepped).completed_event_ids[0] for _index in range(3)
        )
        set_clock_mode(advanced, "NORMAL")
        advanced_order = advance_to(
            advanced, "2026-08-20T05:00:00Z"
        ).completed_event_ids
        begin_fast_forward(fast_forward, "2026-08-20T05:00:00Z")
        fast_order = run_fast_forward(fast_forward).completed_event_ids
        self.assertEqual(stepped_order, advanced_order)
        self.assertEqual(stepped_order, fast_order)

    def test_unrelated_future_event_does_not_reorder_eligible_work(self):
        base = make_world()
        for label in ("a", "b"):
            schedule(base, "2026-08-20T05:00:00Z", event_type="RECORD", payload={"label": label})
        extra = deepcopy(base)
        schedule(extra, "2026-08-21T05:00:00Z")
        left = process_events_through(base, "2026-08-20T06:00:00Z", registry=recording_registry())
        right = process_events_through(extra, "2026-08-20T06:00:00Z", registry=recording_registry())
        self.assertEqual(left.completed_event_ids, right.completed_event_ids)
        self.assertEqual(base["world_state"]["history"], extra["world_state"]["history"])

    def test_stop_condition_pauses_at_completed_transaction(self):
        world = make_world()
        first = schedule(world, "2026-08-20T05:00:00Z")
        second = schedule(world, "2026-08-20T06:00:00Z")
        begin_fast_forward(world, "2026-08-20T07:00:00Z")
        result = run_fast_forward(
            world,
            stop_condition=lambda state: len(state["world_state"]["event_history"]) == 1,
        )
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertIn(second, world["world_state"]["pending_events"])
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T05:00:00Z")
        self.assertEqual(world["simulation"]["clock_state"], "PAUSED")

    def test_stop_condition_cannot_write_back_to_authority(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z")
        begin_fast_forward(world, "2026-08-20T06:00:00Z")

        def mutate_snapshot(snapshot):
            snapshot["world_state"]["history"]["operations"].append("leak")
            return False

        run_fast_forward(world, stop_condition=mutate_snapshot)
        self.assertEqual(world["world_state"]["history"]["operations"], [])

    def test_handler_pause_stops_after_its_committed_transaction(self):
        world = make_world()
        registry = EventHandlerRegistry()
        registry.register("PAUSE", lambda context: context.pause())
        first = schedule(world, "2026-08-20T05:00:00Z", event_type="PAUSE")
        second = schedule(world, "2026-08-20T06:00:00Z", event_type="PAUSE")
        set_clock_mode(world, "NORMAL")
        result = advance_to(world, "2026-08-20T07:00:00Z", registry=registry)
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertIn(second, world["world_state"]["pending_events"])
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T05:00:00Z")

    def test_focus_and_legacy_daily_tick_do_not_affect_processing(self):
        left = make_world()
        schedule(left, "2026-08-20T05:00:00Z")
        right = deepcopy(left)
        right["ui_state"]["current_focus_airline_id"] = None
        with patch(
            "game.simulation.daily_tick.simulate_airline_day",
            side_effect=AssertionError("legacy daily tick was called"),
        ):
            process_events_through(left, "2026-08-20T05:00:00Z")
            process_events_through(right, "2026-08-20T05:00:00Z")
        left["ui_state"] = right["ui_state"]
        self.assertEqual(left, right)

    def test_authority_remains_json_compatible_and_has_no_runtime_objects(self):
        world = make_world()
        schedule(world, "2026-08-20T05:00:00Z", payload={"values": [1, "two", None]})
        self.assertTrue(validate_world(world).is_valid)

        def walk(value):
            self.assertFalse(callable(value))
            if isinstance(value, dict):
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        walk(world)

    def test_ten_thousand_events_process_without_frame_polling(self):
        world = make_world()
        for _index in range(10_000):
            schedule(world, "2026-08-20T05:00:00Z")
        started = perf_counter()
        result = process_events_through(world, "2026-08-20T05:00:00Z")
        elapsed = perf_counter() - started
        self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(len(result.completed_event_ids), 10_000)
        self.assertEqual(len(world["world_state"]["event_history"]), 10_000)
        self.assertLess(elapsed, 15.0, f"10,000 events took {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
