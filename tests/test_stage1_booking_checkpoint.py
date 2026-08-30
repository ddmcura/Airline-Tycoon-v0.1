import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from game.booking import (
    prepare_daily_booking_allocation,
    process_daily_booking_checkpoint,
)
from game.simulation import process_next_event
from game.scheduling import revise_future_schedule
from game.world_state import validate_world
from tests.test_stage1_booking_allocation import (
    allocation_arguments,
    committed_base_booking_configuration,
)
from tests.test_stage1_booking_shopping import schema3_world


def checkpoint_arguments(world):
    allocation_args = allocation_arguments(world)
    probe = deepcopy(world)
    plan = prepare_daily_booking_allocation(probe, **allocation_args)
    if not plan.succeeded:
        raise AssertionError(plan.issues)
    paid_airlines = {
        selected.airline_id
        for market in plan.market_results
        for group in market.desired_date_results
        for selected in group.selected_offer_allocations
        if world["world_state"]["dated_flights"][selected.dated_flight_id][
            "fare_offer"
        ]["amount_minor"]
    }
    return {
        **allocation_args,
        "expected_booking_revision": world["world_state"]["booking_state"][
            "booking_revision"
        ],
        "expected_finance_revisions": {
            airline_id: world["world_state"]["airlines"][airline_id][
                "finance_revision"
            ]
            for airline_id in sorted(paid_airlines)
        },
        "expected_event_order_cursor": world["simulation"]["event_order_cursor"],
    }


class DailyBookingCheckpointTests(unittest.TestCase):
    def test_atomic_checkpoint_persists_capacity_finance_outcomes_and_event(self):
        world, _market_id, flight_id = schema3_world()
        airline_id = world["world_state"]["dated_flights"][flight_id]["airline_id"]
        accounts = {
            world["world_state"]["financial_accounts"][account_id]["code"]: account_id
            for account_id in world["world_state"]["airlines"][airline_id][
                "financial_account_ids"
            ]
        }
        cash_before = world["world_state"]["financial_accounts"][accounts["cash"]][
            "balance_minor"
        ]
        result = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.checkpoint_date, world["simulation"]["time_utc"][:10])
        self.assertEqual(result.booked_passengers, 180)
        self.assertEqual(len(result.booking_ids), 7)
        self.assertEqual(len(result.itinerary_ids), 7)
        self.assertEqual(len(result.transaction_ids), 1)
        self.assertEqual(world["world_state"]["booking_state"]["booking_revision"], 1)
        self.assertEqual(world["world_state"]["dated_flights"][flight_id]["inventory_revision"], 1)
        self.assertEqual(world["world_state"]["airlines"][airline_id]["finance_revision"], 1)
        transaction = world["world_state"]["transactions"][result.transaction_ids[0]]
        gross = sum(world["world_state"]["bookings"][booking_id]["total_fare_minor"] for booking_id in result.booking_ids)
        self.assertEqual(sum(entry["amount_minor"] for entry in transaction["entries"]), 0)
        self.assertEqual(transaction["source_type"], "BOOKING_CHECKPOINT")
        self.assertEqual(world["world_state"]["financial_accounts"][accounts["cash"]]["balance_minor"], cash_before + gross)
        self.assertEqual(world["world_state"]["financial_accounts"][accounts["unflown_tickets"]]["balance_minor"], gross)
        self.assertEqual(world["world_state"]["financial_accounts"][accounts["passenger_revenue"]]["balance_minor"], 0)
        self.assertEqual(result.next_event_due_at_utc, "2026-08-21T00:00:00Z")
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())

    def test_repeat_is_byte_identical_and_ignores_new_expectations(self):
        world, _market_id, _flight_id = schema3_world()
        first = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        encoded = json.dumps(world, sort_keys=True, separators=(",", ":"))
        repeated = process_daily_booking_checkpoint(
            world,
            expected_booking_revision="ignored",
            expected_demand_revision="ignored",
            expected_market_pack_revision="ignored",
            expected_booking_configuration_revision="ignored",
            expected_booking_configuration_fingerprint=None,
            expected_inventory_revisions=[],
            expected_finance_revisions=[],
            expected_event_order_cursor="ignored",
        )
        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.booking_ids, first.booking_ids)
        self.assertEqual(json.dumps(world, sort_keys=True, separators=(",", ":")), encoded)

    def test_stale_finance_expectation_rejects_without_allocator_movement(self):
        world, _market_id, _flight_id = schema3_world()
        arguments = checkpoint_arguments(world)
        airline_id = next(iter(arguments["expected_finance_revisions"]))
        arguments["expected_finance_revisions"][airline_id] += 1
        before = deepcopy(world)
        result = process_daily_booking_checkpoint(world, **arguments)
        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)

    def test_zero_fare_reserves_capacity_without_finance_mutation(self):
        world, _market_id, flight_id = schema3_world()
        airline_id = world["world_state"]["dated_flights"][flight_id]["airline_id"]
        world["world_state"]["dated_flights"][flight_id]["fare_offer"]["amount_minor"] = 0
        schedule_id = world["world_state"]["dated_flights"][flight_id]["schedule_id"]
        world["world_state"]["schedule_definitions"][schedule_id]["revisions"]["1"]["fare_offer"]["amount_minor"] = 0
        result = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        self.assertGreater(result.booked_passengers, 0)
        self.assertEqual(result.transaction_ids, ())
        self.assertEqual(world["world_state"]["airlines"][airline_id]["finance_revision"], 0)
        self.assertTrue(all(world["world_state"]["bookings"][booking_id]["finance_transaction_id"] is None for booking_id in result.booking_ids))

    def test_revision_one_requires_explicit_transition(self):
        world, _market_id, flight_id = schema3_world()
        world["simulation"]["configuration"]["booking"] = committed_base_booking_configuration()
        configuration = world["simulation"]["configuration"]["booking"]
        before = deepcopy(world)
        result = process_daily_booking_checkpoint(
            world,
            expected_booking_revision=0,
            expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"],
            expected_market_pack_revision=world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"],
            expected_booking_configuration_revision=1,
            expected_booking_configuration_fingerprint=configuration["configuration_fingerprint"],
            expected_inventory_revisions={flight_id: 0},
            expected_finance_revisions={},
            expected_event_order_cursor=0,
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "INVALID_BOOKING_CONFIGURATION")
        self.assertEqual(world, before)

    def test_event_executes_same_checkpoint_boundary_and_recurs_once(self):
        world, _market_id, _flight_id = schema3_world()
        first = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        processed = process_next_event(world)
        self.assertTrue(processed.succeeded, processed.failure)
        self.assertEqual(world["simulation"]["time_utc"], first.next_event_due_at_utc)
        self.assertEqual(len(world["world_state"]["booking_state"]["booking_checkpoints"]), 2)
        self.assertEqual(len(world["world_state"]["pending_events"]), 1)
        self.assertEqual(len(world["world_state"]["event_history"]), 1)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())

    def test_booked_occurrence_rejects_schedule_reconciliation(self):
        world, _market_id, flight_id = schema3_world()
        schedule_id = world["world_state"]["dated_flights"][flight_id]["schedule_id"]
        world["world_state"]["schedule_definitions"][schedule_id]["revisions"]["1"][
            "effective_from_local_date"
        ] = "2026-08-17"
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())
        result = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        before = deepcopy(world)
        revised = revise_future_schedule(
            world,
            schedule_id,
            effective_from_local_date="2026-08-24",
            expected_revision=1,
            capacity=100,
        )
        self.assertEqual(revised.status, "CONFLICT")
        self.assertEqual(
            revised.conflicts[0].code,
            "BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW",
        )
        self.assertEqual(world, before)

    def test_exact_allocator_advancement_current_date_bootstrap_and_detachment(self):
        world, _market_id, _flight_id = schema3_world()
        world["simulation"]["time_utc"] = "2026-08-20T23:59:59Z"
        before = deepcopy(
            world["deterministic_state"]["id_allocator"]["next_by_type"]
        )
        result = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        after = world["deterministic_state"]["id_allocator"]["next_by_type"]
        self.assertEqual(after["booking_checkpoint"] - before["booking_checkpoint"], 1)
        self.assertEqual(after["itinerary"] - before["itinerary"], len(result.itinerary_ids))
        self.assertEqual(after["booking"] - before["booking"], len(result.booking_ids))
        self.assertEqual(after["transaction"] - before["transaction"], len(result.transaction_ids))
        self.assertEqual(after["event"] - before["event"], 1)
        self.assertEqual(
            {item["checkpoint_date"] for item in world["world_state"]["booking_state"]["booking_checkpoints"].values()},
            {"2026-08-20"},
        )
        detached = deepcopy(result)
        world["world_state"]["bookings"][result.booking_ids[0]]["passenger_count"] += 1
        self.assertEqual(result, detached)

    def test_completed_checkpoint_successor_topology_is_world_validated(self):
        for mutation in ("missing", "payload", "revision"):
            with self.subTest(mutation=mutation):
                world, _market_id, _flight_id = schema3_world()
                result = process_daily_booking_checkpoint(
                    world, **checkpoint_arguments(world)
                )
                if mutation == "missing":
                    del world["world_state"]["pending_events"][result.next_event_id]
                elif mutation == "payload":
                    world["world_state"]["pending_events"][result.next_event_id][
                        "payload"
                    ] = {"checkpoint_date": "1999-01-01"}
                else:
                    world["world_state"]["pending_events"][result.next_event_id][
                        "operation_revision"
                    ] = 0
                validation = validate_world(world)
                self.assertFalse(validation.is_valid)
                self.assertIn(
                    "invalid_booking_checkpoint",
                    {issue.code for issue in validation.errors},
                )

    def test_paid_transaction_amount_accounts_and_zero_fare_lineage_are_strict(self):
        for mutation in ("gross", "revenue"):
            with self.subTest(mutation=mutation):
                world, _market_id, _flight_id = schema3_world()
                result = process_daily_booking_checkpoint(
                    world, **checkpoint_arguments(world)
                )
                transaction = world["world_state"]["transactions"][
                    result.transaction_ids[0]
                ]
                if mutation == "gross":
                    transaction["entries"][0]["amount_minor"] += 1
                    transaction["entries"][1]["amount_minor"] -= 1
                else:
                    account_ids = world["world_state"]["airlines"][
                        transaction["airline_id"]
                    ]["financial_account_ids"]
                    revenue_id = next(
                        account_id
                        for account_id in account_ids
                        if world["world_state"]["financial_accounts"][account_id][
                            "code"
                        ]
                        == "passenger_revenue"
                    )
                    transaction["entries"][0]["account_id"] = revenue_id
                self.assertIn(
                    "invalid_transaction",
                    {issue.code for issue in validate_world(world).errors},
                )

        zero_world, _market_id, flight_id = schema3_world()
        zero_world["world_state"]["dated_flights"][flight_id]["fare_offer"][
            "amount_minor"
        ] = 0
        schedule_id = zero_world["world_state"]["dated_flights"][flight_id][
            "schedule_id"
        ]
        zero_world["world_state"]["schedule_definitions"][schedule_id]["revisions"][
            "1"
        ]["fare_offer"]["amount_minor"] = 0
        zero_result = process_daily_booking_checkpoint(
            zero_world, **checkpoint_arguments(zero_world)
        )
        paid_world, _market_id, _flight_id = schema3_world()
        paid_result = process_daily_booking_checkpoint(
            paid_world, **checkpoint_arguments(paid_world)
        )
        unrelated = deepcopy(
            paid_world["world_state"]["transactions"][paid_result.transaction_ids[0]]
        )
        transaction_id = paid_result.transaction_ids[0]
        zero_world["world_state"]["transactions"][transaction_id] = unrelated
        checkpoint = zero_world["world_state"]["booking_state"]["booking_checkpoints"][
            zero_result.checkpoint_id
        ]
        checkpoint["financial_transaction_ids"] = [transaction_id]
        for booking_id in zero_result.booking_ids:
            zero_world["world_state"]["bookings"][booking_id][
                "finance_transaction_id"
            ] = transaction_id
        self.assertIn(
            "invalid_booking",
            {issue.code for issue in validate_world(zero_world).errors},
        )

    def test_desired_date_booking_lineage_and_global_revision_are_strict(self):
        world, _market_id, _flight_id = schema3_world()
        result = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        checkpoint = world["world_state"]["booking_state"]["booking_checkpoints"][
            result.checkpoint_id
        ]
        market = next(iter(checkpoint["market_results"].values()))
        equal_groups = [
            group
            for group in market["desired_date_results"].values()
            if group["booked_passenger_count"] == 28
        ]
        self.assertGreaterEqual(len(equal_groups), 2)
        equal_groups[0]["booking_ids"], equal_groups[1]["booking_ids"] = (
            equal_groups[1]["booking_ids"],
            equal_groups[0]["booking_ids"],
        )
        self.assertIn(
            "result_validation_failed",
            {issue.code for issue in validate_world(world).errors},
        )

        revision_world, _market_id, _flight_id = schema3_world()
        process_daily_booking_checkpoint(
            revision_world, **checkpoint_arguments(revision_world)
        )
        revision_world["world_state"]["booking_state"]["booking_revision"] += 1
        self.assertIn(
            "inconsistent_booking_revision",
            {issue.code for issue in validate_world(revision_world).errors},
        )

    def test_multi_day_recurrence_retry_safety_and_direct_event_equivalence(self):
        world, _market_id, _flight_id = schema3_world()
        first = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
        for expected_count in range(2, 6):
            processed = process_next_event(world)
            self.assertTrue(processed.succeeded, processed.failure)
            self.assertEqual(
                len(world["world_state"]["booking_state"]["booking_checkpoints"]),
                expected_count,
            )
            self.assertEqual(len(world["world_state"]["pending_events"]), 1)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())

        retry_world, _market_id, _flight_id = schema3_world()
        process_daily_booking_checkpoint(
            retry_world, **checkpoint_arguments(retry_world)
        )
        uninterrupted = deepcopy(retry_world)
        before_failure = deepcopy(retry_world)
        with patch(
            "game.booking.checkpoint.process_daily_booking_checkpoint",
            side_effect=RuntimeError("injected event failure"),
        ):
            failed = process_next_event(retry_world)
        self.assertEqual(failed.status, "BLOCKED")
        self.assertEqual(retry_world, before_failure)
        self.assertTrue(process_next_event(retry_world).succeeded)
        self.assertTrue(process_next_event(uninterrupted).succeeded)
        self.assertEqual(retry_world, uninterrupted)

        direct, _market_id, _flight_id = schema3_world()
        initial = process_daily_booking_checkpoint(direct, **checkpoint_arguments(direct))
        evented = deepcopy(direct)
        direct["simulation"]["time_utc"] = initial.next_event_due_at_utc
        direct_result = process_daily_booking_checkpoint(
            direct, **checkpoint_arguments(direct)
        )
        self.assertTrue(process_next_event(evented).succeeded)
        evented_checkpoint = next(
            checkpoint
            for checkpoint in evented["world_state"]["booking_state"][
                "booking_checkpoints"
            ].values()
            if checkpoint["checkpoint_date"] == direct_result.checkpoint_date
        )
        self.assertEqual(
            direct["world_state"]["booking_state"]["booking_checkpoints"][
                direct_result.checkpoint_id
            ],
            evented_checkpoint,
        )
        self.assertEqual(
            {
                booking_id: booking
                for booking_id, booking in direct["world_state"]["bookings"].items()
                if booking.get("booking_checkpoint_id") == direct_result.checkpoint_id
            },
            {
                booking_id: booking
                for booking_id, booking in evented["world_state"]["bookings"].items()
                if booking.get("booking_checkpoint_id") == direct_result.checkpoint_id
            },
        )

    def test_late_event_failure_rolls_back_and_dictionary_order_is_irrelevant(self):
        world, _market_id, _flight_id = schema3_world()
        before = deepcopy(world)
        with patch(
            "game.booking.checkpoint.schedule_event",
            side_effect=RuntimeError("injected late event failure"),
        ):
            failed = process_daily_booking_checkpoint(
                world, **checkpoint_arguments(world)
            )
        self.assertFalse(failed.succeeded)
        self.assertEqual(world, before)

        left, _market_id, _flight_id = schema3_world()
        right = deepcopy(left)
        for collection in (
            "directional_markets",
            "dated_flights",
            "airlines",
            "schedule_definitions",
        ):
            right["world_state"][collection] = dict(
                reversed(tuple(right["world_state"][collection].items()))
            )
        left_result = process_daily_booking_checkpoint(
            left, **checkpoint_arguments(left)
        )
        right_result = process_daily_booking_checkpoint(
            right, **checkpoint_arguments(right)
        )
        self.assertEqual(left_result, right_result)
        self.assertEqual(
            json.dumps(left, sort_keys=True, separators=(",", ":")),
            json.dumps(right, sort_keys=True, separators=(",", ":")),
        )


if __name__ == "__main__":
    unittest.main()
