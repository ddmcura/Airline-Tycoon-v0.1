"""Focused deterministic tests for Stage 1 Milestone 6 fulfilment."""

from copy import deepcopy
from datetime import timedelta
import json
import unittest

from game.aircraft_operations import (
    build_confirmed_carriage_manifest,
    process_flight_completion,
    process_flight_departure,
    project_flight_fulfilment,
    project_recent_flight_results,
)
from game.aircraft_operations.fulfilment import calculate_operating_cost
from game.booking import process_daily_booking_checkpoint
from game.scheduling import (
    BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW,
    create_schedule_definition,
    publish_occurrences_through,
)
from game.simulation import process_events_through, process_next_event, schedule_event
from game.world_state.schema import (
    FLIGHT_DEPARTURE_EVENT_CONTRACT,
    FLIGHT_DEPARTURE_EVENT_TYPE,
    FLIGHT_EVENT_PRIORITY,
    MAX_ENTITY_ID_NUMBER,
)
from game.world_state import (
    add_aircraft,
    add_connection,
    migrate_schema_2_to_3,
    migrate_schema_3_to_4,
    validate_world,
)
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.test_stage1_booking_checkpoint import checkpoint_arguments
from tests.test_stage1_booking_shopping import schema3_world
from tests.test_stage1_demand_model4 import model4_world


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def migrated_empty():
    world, market_id, flight_id = schema3_world()
    result = migrate_schema_3_to_4(world)
    if not result.succeeded:
        raise AssertionError(result.as_dict())
    return result.world, market_id, flight_id


def migrated_booked(*, zero_fare=False):
    world, market_id, flight_id = schema3_world()
    if zero_fare:
        flight = world["world_state"]["dated_flights"][flight_id]
        flight["fare_offer"]["amount_minor"] = 0
        world["world_state"]["schedule_definitions"][flight["schedule_id"]][
            "revisions"
        ]["1"]["fare_offer"]["amount_minor"] = 0
    booked = process_daily_booking_checkpoint(world, **checkpoint_arguments(world))
    if not booked.succeeded:
        raise AssertionError(booked.issues)
    result = migrate_schema_3_to_4(world)
    if not result.succeeded:
        raise AssertionError(result.as_dict())
    return result.world, market_id, flight_id, booked


def departure_witnesses(world, flight_id):
    flight = world["world_state"]["dated_flights"][flight_id]
    configuration = world["simulation"]["configuration"]["flight_fulfilment"]
    return {
        "expected_operation_revision": flight["operation_revision"],
        "expected_booking_revision": world["world_state"]["booking_state"]["booking_revision"],
        "expected_inventory_revision": flight["inventory_revision"],
        "expected_event_order_cursor": world["simulation"]["event_order_cursor"],
        "expected_configuration_revision": configuration["current_revision"],
        "expected_configuration_fingerprint": configuration["configuration_fingerprint"],
    }


def completion_witnesses(world, flight_id):
    result = departure_witnesses(world, flight_id)
    airline_id = world["world_state"]["dated_flights"][flight_id]["airline_id"]
    result["expected_finance_revision"] = world["world_state"]["airlines"][airline_id]["finance_revision"]
    return result


def make_one_booking_zero_fare(world, booked):
    state = world["world_state"]
    booking_id = booked.booking_ids[0]
    booking = state["bookings"][booking_id]
    old_total = booking["total_fare_minor"]
    transaction_id = booking["finance_transaction_id"]
    transaction = state["transactions"][transaction_id]
    booking["total_fare_minor"] = 0
    booking["finance_transaction_id"] = None
    state["itineraries"][booking["itinerary_id"]]["fare_offer_snapshot"][
        "amount_minor"
    ] = 0
    transaction["source_booking_ids"].remove(booking_id)
    transaction["entries"][0]["amount_minor"] -= old_total
    transaction["entries"][1]["amount_minor"] += old_total
    airline = state["airlines"][booking["airline_id"]]
    accounts = {
        state["financial_accounts"][account_id]["code"]: account_id
        for account_id in airline["financial_account_ids"]
    }
    state["financial_accounts"][accounts["cash"]]["balance_minor"] -= old_total
    state["financial_accounts"][accounts["unflown_tickets"]]["balance_minor"] -= old_total
    return booking_id, booking["passenger_count"], old_total


def reduce_bookings_to_half_capacity(world, booked):
    state = world["world_state"]
    booking_ids = sorted(
        booking_id for booking_id, booking in state["bookings"].items()
        if booking.get("contract") == "STAGE1_AGGREGATE_BOOKING_V1"
    )
    total = sum(state["bookings"][booking_id]["passenger_count"] for booking_id in booking_ids)
    counts = {
        booking_id: max(
            1, state["bookings"][booking_id]["passenger_count"] * 90 // total
        )
        for booking_id in booking_ids
    }
    difference = 90 - sum(counts.values())
    index = 0
    while difference:
        booking_id = booking_ids[index % len(booking_ids)]
        if difference > 0:
            counts[booking_id] += 1
            difference -= 1
        elif counts[booking_id] > 1:
            counts[booking_id] -= 1
            difference += 1
        index += 1
    for booking_id, count in counts.items():
        booking = state["bookings"][booking_id]
        booking["passenger_count"] = count
        booking["total_fare_minor"] = count * 10_000
    for checkpoint in state["booking_state"]["booking_checkpoints"].values():
        for market_result in checkpoint["market_results"].values():
            for desired in market_result["desired_date_results"].values():
                new_count = sum(counts[booking_id] for booking_id in desired["booking_ids"])
                delta = desired["booked_passenger_count"] - new_count
                desired["booked_passenger_count"] = new_count
                desired["outside_option_passenger_count"] += delta
            market_result["booked_passenger_count"] = sum(
                item["booked_passenger_count"]
                for item in market_result["desired_date_results"].values()
            )
            market_result["outside_option_passenger_count"] = sum(
                item["outside_option_passenger_count"]
                for item in market_result["desired_date_results"].values()
            )
    old_gross = 0
    new_gross = 0
    booking_transactions = [
        transaction for transaction in state["transactions"].values()
        if transaction.get("source_type") == "BOOKING_CHECKPOINT"
    ]
    for transaction in booking_transactions:
        old_gross += transaction["entries"][0]["amount_minor"]
        gross = sum(
            state["bookings"][booking_id]["total_fare_minor"]
            for booking_id in transaction["source_booking_ids"]
        )
        new_gross += gross
        transaction["entries"][0]["amount_minor"] = gross
        transaction["entries"][1]["amount_minor"] = -gross
    airline = state["airlines"][booking_transactions[0]["airline_id"]]
    accounts = {
        state["financial_accounts"][account_id]["code"]: account_id
        for account_id in airline["financial_account_ids"]
    }
    reduction = old_gross - new_gross
    state["financial_accounts"][accounts["cash"]]["balance_minor"] -= reduction
    state["financial_accounts"][accounts["unflown_tickets"]]["balance_minor"] -= reduction


class Schema4MigrationTests(unittest.TestCase):
    def test_migration_departure_time_boundary_is_exact(self):
        for offset_seconds, expected in ((-1, True), (0, True), (1, False)):
            with self.subTest(offset_seconds=offset_seconds):
                source, _market_id, flight_id = schema3_world()
                flight = source["world_state"]["dated_flights"][flight_id]
                source["simulation"]["time_utc"] = format_utc(
                    parse_canonical_utc(flight["scheduled_off_block_utc"])
                    + timedelta(seconds=offset_seconds)
                )
                before = encoded(source)
                result = migrate_schema_3_to_4(source)
                self.assertEqual(result.succeeded, expected, result.issues)
                self.assertEqual(encoded(source), before)
                if expected:
                    event = next(
                        event
                        for event in result.world["world_state"][
                            "pending_events"
                        ].values()
                        if event["event_type"] == FLIGHT_DEPARTURE_EVENT_TYPE
                    )
                    self.assertEqual(
                        event["due_at_utc"], flight["scheduled_off_block_utc"]
                    )
                else:
                    self.assertEqual(
                        result.issues[0].code, "UNRESOLVED_PAST_DUE_FLIGHT"
                    )

    def test_migration_detaches_profiles_and_allocates_one_departure(self):
        source, _market_id, flight_id = schema3_world()
        before = encoded(source)
        event_next = source["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]["event"]
        result = migrate_schema_3_to_4(source)
        self.assertTrue(result.succeeded, result.issues)
        world = result.world
        self.assertEqual(encoded(source), before)
        self.assertIsNot(world, source)
        self.assertEqual(world["metadata"]["save_schema_version"], 4)
        configuration = world["simulation"]["configuration"]["flight_fulfilment"]
        profiles = configuration["revisions"]["1"]["currency_profiles"]
        self.assertEqual(set(profiles), {"EUR", "PHP", "USD"})
        self.assertEqual(
            (profiles["USD"]["fixed_flight_cost_minor"],
             profiles["USD"]["capacity_cost_minor_per_seat"],
             profiles["USD"]["seat_block_minute_rate_numerator"],
             profiles["USD"]["seat_block_minute_rate_denominator"]),
            (75_000, 300, 25, 100),
        )
        events = list(world["world_state"]["pending_events"].values())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "STAGE1_FLIGHT_DEPARTURE")
        self.assertEqual(events[0]["owner_id"], flight_id)
        self.assertEqual(
            world["deterministic_state"]["id_allocator"]["next_by_type"]["event"],
            event_next + 1,
        )
        self.assertTrue(validate_world(world).is_valid)

    def test_unsupported_currency_and_past_due_are_atomic_rejections(self):
        for case in ("currency", "past"):
            with self.subTest(case=case):
                world, _market_id, flight_id = schema3_world()
                flight = world["world_state"]["dated_flights"][flight_id]
                if case == "currency":
                    airline = world["world_state"]["airlines"][flight["airline_id"]]
                    airline["base_currency"] = "JPY"
                    for account_id in airline["financial_account_ids"]:
                        world["world_state"]["financial_accounts"][account_id]["currency"] = "JPY"
                    flight["fare_offer"]["currency"] = "JPY"
                    world["world_state"]["schedule_definitions"][flight["schedule_id"]]["revisions"]["1"]["fare_offer"]["currency"] = "JPY"
                else:
                    world["simulation"]["time_utc"] = flight["scheduled_off_block_utc"][:-1] + "Z"
                    world["simulation"]["time_utc"] = flight["scheduled_in_block_utc"]
                self.assertTrue(validate_world(world).is_valid)
                before = encoded(world)
                result = migrate_schema_3_to_4(world)
                self.assertFalse(result.succeeded)
                self.assertEqual(encoded(world), before)
                self.assertEqual(
                    result.issues[0].code,
                    "UNSUPPORTED_FULFILMENT_CURRENCY" if case == "currency"
                    else "UNRESOLVED_PAST_DUE_FLIGHT",
                )

    def test_migration_reuses_an_exact_existing_departure_event(self):
        source, _market_id, flight_id = schema3_world()
        flight = source["world_state"]["dated_flights"][flight_id]
        event_id = schedule_event(
            source,
            event_type=FLIGHT_DEPARTURE_EVENT_TYPE,
            due_at_utc=flight["scheduled_off_block_utc"],
            owner_type="dated_flight",
            owner_id=flight_id,
            operation_revision=0,
            priority=FLIGHT_EVENT_PRIORITY,
            payload={
                "contract": FLIGHT_DEPARTURE_EVENT_CONTRACT,
                "dated_flight_id": flight_id,
                "schedule_id": flight["schedule_id"],
                "schedule_revision": flight["schedule_revision"],
                "occurrence_key": flight["occurrence_key"],
            },
        )
        before = encoded(source)
        next_event = source["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]["event"]
        cursor = source["simulation"]["event_order_cursor"]
        result = migrate_schema_3_to_4(source)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(encoded(source), before)
        self.assertEqual(
            tuple(result.world["world_state"]["pending_events"]), (event_id,)
        )
        self.assertEqual(
            result.world["deterministic_state"]["id_allocator"][
                "next_by_type"
            ]["event"],
            next_event,
        )
        self.assertEqual(result.world["simulation"]["event_order_cursor"], cursor)

    def test_migration_rejects_conflicting_dated_flight_event_authority(self):
        source, _market_id, flight_id = schema3_world()
        flight = source["world_state"]["dated_flights"][flight_id]
        schedule_event(
            source,
            event_type="WRONG_FLIGHT_EVENT",
            due_at_utc=flight["scheduled_off_block_utc"],
            owner_type="dated_flight",
            owner_id=flight_id,
            operation_revision=0,
            priority=FLIGHT_EVENT_PRIORITY,
            payload={"dated_flight_id": flight_id},
        )
        before = encoded(source)
        result = migrate_schema_3_to_4(source)
        self.assertFalse(result.succeeded)
        self.assertEqual(encoded(source), before)
        self.assertTrue(
            any(issue.code == "invalid_lifecycle_event" for issue in result.issues),
            result.as_dict(),
        )

    def test_model4_v2_demand_with_strict_v1_bookings_fulfils(self):
        source, airport_ids, _old = model4_world()
        market_id = next(
            market_id
            for market_id, market in source["world_state"][
                "directional_markets"
            ].items()
            if market["origin_airport_id"] == airport_ids["MNL"]
            and market["destination_airport_id"] == airport_ids["DVO"]
        )
        airline_id = source["world_state"]["player"]["primary_airline_id"]
        connection_id = add_connection(
            source, airline_id, market_id, status="ACTIVE"
        )
        aircraft_id = add_aircraft(
            source,
            airline_id,
            "RP-M4F1",
            "A320",
            home_airport_id=airport_ids["MNL"],
        )
        schedule = create_schedule_definition(
            source,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=airport_ids["MNL"],
            destination_airport_id=airport_ids["DVO"],
            weekdays=[0],
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            effective_from_local_date="2026-08-24",
            capacity=180,
            fare_offer={"currency": "USD", "amount_minor": 10_000},
        )
        self.assertTrue(schedule.succeeded, schedule.conflicts)
        published = publish_occurrences_through(
            source, "2026-08-24T00:00:00Z"
        )
        self.assertTrue(published.succeeded, published.conflicts)
        schema3 = migrate_schema_2_to_3(source)
        self.assertTrue(schema3.succeeded, schema3.issues)
        booked = process_daily_booking_checkpoint(
            schema3.world, **checkpoint_arguments(schema3.world)
        )
        self.assertTrue(booked.succeeded, booked.issues)
        self.assertTrue(booked.booking_ids)
        migrated = migrate_schema_3_to_4(schema3.world)
        self.assertTrue(migrated.succeeded, migrated.issues)
        world = migrated.world
        flight_id = published.created_dated_flight_ids[0]
        flight = world["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        result = world["world_state"]["flight_results"][flight_id]
        self.assertEqual(result["carried_passenger_count"], 180)
        self.assertEqual(
            {
                world["world_state"]["bookings"][booking_id]["contract"]
                for booking_id in result["source_booking_ids"]
            },
            {"STAGE1_AGGREGATE_BOOKING_V1"},
        )


class FlightLifecycleTests(unittest.TestCase):
    def test_fulfilment_allocator_exhaustion_is_atomic_and_retry_safe(self):
        departure_world, _market_id, flight_id = migrated_empty()
        departure_flight = departure_world["world_state"]["dated_flights"][
            flight_id
        ]
        departure_world["simulation"]["time_utc"] = departure_flight[
            "scheduled_off_block_utc"
        ]
        clean_departure = deepcopy(departure_world)
        clean_result = process_flight_departure(
            clean_departure,
            flight_id,
            **departure_witnesses(clean_departure, flight_id),
        )
        self.assertTrue(clean_result.succeeded, clean_result.issues)
        last_event_slot = deepcopy(departure_world)
        last_event_slot["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]["event"] = MAX_ENTITY_ID_NUMBER
        last_event = process_flight_departure(
            last_event_slot,
            flight_id,
            **departure_witnesses(last_event_slot, flight_id),
        )
        self.assertTrue(last_event.succeeded, last_event.issues)
        self.assertEqual(
            last_event_slot["deterministic_state"]["id_allocator"][
                "next_by_type"
            ]["event"],
            MAX_ENTITY_ID_NUMBER + 1,
        )
        allocator = departure_world["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]
        original_event_next = allocator["event"]
        allocator["event"] = MAX_ENTITY_ID_NUMBER + 1
        before = encoded(departure_world)
        rejected = process_flight_departure(
            departure_world,
            flight_id,
            **departure_witnesses(departure_world, flight_id),
        )
        self.assertFalse(rejected.succeeded)
        self.assertEqual(encoded(departure_world), before)
        allocator["event"] = original_event_next
        retried = process_flight_departure(
            departure_world,
            flight_id,
            **departure_witnesses(departure_world, flight_id),
        )
        self.assertTrue(retried.succeeded, retried.issues)
        self.assertEqual(encoded(departure_world), encoded(clean_departure))

        completion_world = departure_world
        completion_flight = completion_world["world_state"]["dated_flights"][
            flight_id
        ]
        completion_world["simulation"]["time_utc"] = completion_flight[
            "scheduled_in_block_utc"
        ]
        clean_completion = deepcopy(completion_world)
        clean_result = process_flight_completion(
            clean_completion,
            flight_id,
            **completion_witnesses(clean_completion, flight_id),
        )
        self.assertTrue(clean_result.succeeded, clean_result.issues)
        last_transaction_slot = deepcopy(completion_world)
        last_transaction_slot["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]["transaction"] = MAX_ENTITY_ID_NUMBER
        last_transaction = process_flight_completion(
            last_transaction_slot,
            flight_id,
            **completion_witnesses(last_transaction_slot, flight_id),
        )
        self.assertTrue(last_transaction.succeeded, last_transaction.issues)
        self.assertEqual(
            last_transaction_slot["deterministic_state"]["id_allocator"][
                "next_by_type"
            ]["transaction"],
            MAX_ENTITY_ID_NUMBER + 1,
        )
        allocator = completion_world["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]
        original_transaction_next = allocator["transaction"]
        allocator["transaction"] = MAX_ENTITY_ID_NUMBER + 1
        before = encoded(completion_world)
        rejected = process_flight_completion(
            completion_world,
            flight_id,
            **completion_witnesses(completion_world, flight_id),
        )
        self.assertFalse(rejected.succeeded)
        self.assertEqual(encoded(completion_world), before)
        allocator["transaction"] = original_transaction_next
        retried = process_flight_completion(
            completion_world,
            flight_id,
            **completion_witnesses(completion_world, flight_id),
        )
        self.assertTrue(retried.succeeded, retried.issues)
        self.assertEqual(encoded(completion_world), encoded(clean_completion))

    def test_schema4_booked_protection_excludes_compatibility_wrappers(self):
        protected, _market_id, flight_id, _booked = migrated_booked()
        flight = protected["world_state"]["dated_flights"][flight_id]
        protected["world_state"]["schedule_definitions"][
            flight["schedule_id"]
        ]["status"] = "RETIRED"
        self.assertTrue(validate_world(protected).is_valid)
        snapshot = encoded(protected)
        blocked = publish_occurrences_through(
            protected, flight["scheduled_off_block_utc"]
        )
        self.assertEqual(blocked.status, "CONFLICT")
        self.assertEqual(
            blocked.conflicts[0].code,
            BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW,
        )
        self.assertEqual(encoded(protected), snapshot)

        compatible, _market_id, compatible_id = migrated_empty()
        compatible_flight = compatible["world_state"]["dated_flights"][
            compatible_id
        ]
        compatible["world_state"]["schedule_definitions"][
            compatible_flight["schedule_id"]
        ]["status"] = "RETIRED"
        changed = publish_occurrences_through(
            compatible, compatible_flight["scheduled_off_block_utc"]
        )
        self.assertTrue(changed.succeeded, changed.conflicts)
        self.assertEqual(changed.superseded_dated_flight_ids, (compatible_id,))

    def test_empty_flight_direct_and_kernel_are_byte_identical(self):
        direct, _market_id, flight_id = migrated_empty()
        kernel = deepcopy(direct)
        flight = direct["world_state"]["dated_flights"][flight_id]
        direct["simulation"]["time_utc"] = flight["scheduled_off_block_utc"]
        departure = process_flight_departure(
            direct, flight_id, **departure_witnesses(direct, flight_id)
        )
        processed = process_next_event(kernel)
        self.assertTrue(departure.succeeded, departure.issues)
        self.assertTrue(processed.succeeded, processed.failure)
        self.assertEqual(encoded(direct), encoded(kernel))

        completion_copy = deepcopy(direct)
        direct["simulation"]["time_utc"] = flight["scheduled_in_block_utc"]
        completion = process_flight_completion(
            direct, flight_id, **completion_witnesses(direct, flight_id)
        )
        processed = process_next_event(completion_copy)
        self.assertTrue(completion.succeeded, completion.issues)
        self.assertTrue(processed.succeeded, processed.failure)
        self.assertEqual(encoded(direct), encoded(completion_copy))
        result = direct["world_state"]["flight_results"][flight_id]
        self.assertEqual(result["carried_passenger_count"], 0)
        self.assertEqual(result["recognized_revenue_minor"], 0)
        self.assertEqual(result["operating_cost_minor"], 669_000)
        self.assertEqual(
            len(direct["world_state"]["transactions"][
                result["settlement_transaction_id"]
            ]["entries"]),
            2,
        )

    def test_full_paid_flight_recognizes_revenue_and_is_idempotent(self):
        world, _market_id, flight_id, booked = migrated_booked()
        flight = world["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        result = world["world_state"]["flight_results"][flight_id]
        self.assertEqual(result["carried_passenger_count"], 180)
        self.assertEqual(result["recognized_revenue_minor"], 1_800_000)
        self.assertEqual(result["operating_cost_minor"], 669_000)
        self.assertEqual(len(result["source_booking_ids"]), len(booked.booking_ids))
        settlement = world["world_state"]["transactions"][
            result["settlement_transaction_id"]
        ]
        self.assertEqual(
            [entry["amount_minor"] for entry in settlement["entries"]],
            [1_800_000, -1_800_000, 669_000, -669_000],
        )
        snapshot = encoded(world)
        repeated = process_flight_completion(
            world, flight_id, **completion_witnesses(world, flight_id)
        )
        self.assertTrue(repeated.succeeded)
        self.assertTrue(repeated.reused)
        self.assertEqual(encoded(world), snapshot)
        projection = project_flight_fulfilment(world, flight_id)
        self.assertEqual(projection["load_factor_basis_points"], 10_000)
        self.assertEqual(projection["operating_profit_minor"], 1_131_000)
        airline = project_recent_flight_results(world, result["airline_id"])
        self.assertEqual(airline["cumulative_profit_minor"], 1_131_000)

    def test_zero_fare_passengers_are_carried_without_revenue(self):
        world, _market_id, flight_id, _booked = migrated_booked(zero_fare=True)
        flight = world["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        result = world["world_state"]["flight_results"][flight_id]
        self.assertEqual(result["carried_passenger_count"], 180)
        self.assertEqual(result["paid_passenger_count"], 0)
        self.assertEqual(result["zero_fare_passenger_count"], 180)
        self.assertEqual(result["recognized_revenue_minor"], 0)
        self.assertEqual(result["paid_booking_ids"], [])
        self.assertTrue(result["zero_fare_booking_ids"])
        self.assertTrue(validate_world(world).is_valid)

    def test_mixed_paid_and_zero_fare_manifest_partitions_exactly(self):
        schema3, _market_id, flight_id = schema3_world()
        booked = process_daily_booking_checkpoint(
            schema3, **checkpoint_arguments(schema3)
        )
        zero_id, zero_passengers, zero_value = make_one_booking_zero_fare(
            schema3, booked
        )
        self.assertTrue(validate_world(schema3).is_valid, validate_world(schema3).as_dict())
        world = migrate_schema_3_to_4(schema3).world
        flight = world["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        result = world["world_state"]["flight_results"][flight_id]
        self.assertIn(zero_id, result["zero_fare_booking_ids"])
        self.assertNotIn(zero_id, result["paid_booking_ids"])
        self.assertEqual(result["zero_fare_passenger_count"], zero_passengers)
        self.assertEqual(result["recognized_revenue_minor"], 1_800_000 - zero_value)
        self.assertEqual(result["carried_passenger_count"], 180)

    def test_half_full_flight_has_exact_positive_contribution(self):
        schema3, _market_id, flight_id = schema3_world()
        booked = process_daily_booking_checkpoint(
            schema3, **checkpoint_arguments(schema3)
        )
        world = migrate_schema_3_to_4(schema3).world
        flight = world["world_state"]["dated_flights"][flight_id]
        before_departure = format_utc(
            parse_canonical_utc(flight["scheduled_off_block_utc"])
            - timedelta(seconds=1)
        )
        processed = process_events_through(world, before_departure)
        self.assertTrue(processed.succeeded, processed.failure)
        processed = process_next_event(world)
        self.assertTrue(processed.succeeded, processed.failure)
        reduce_bookings_to_half_capacity(world, booked)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        projection = project_flight_fulfilment(world, flight_id)
        self.assertEqual(projection["carried_passenger_count"], 90)
        self.assertEqual(projection["load_factor_basis_points"], 5_000)
        self.assertEqual(projection["recognized_revenue_minor"], 900_000)
        self.assertEqual(projection["operating_cost_minor"], 669_000)
        self.assertEqual(projection["operating_profit_minor"], 231_000)

    def test_failed_completion_leaves_event_and_every_cursor_retryable(self):
        world, _market_id, flight_id, _booked = migrated_booked()
        flight = world["world_state"]["dated_flights"][flight_id]
        departed = process_events_through(world, flight["scheduled_off_block_utc"])
        self.assertTrue(departed.succeeded, departed.failure)
        airline = world["world_state"]["airlines"][flight["airline_id"]]
        liability_id = next(
            account_id for account_id in airline["financial_account_ids"]
            if world["world_state"]["financial_accounts"][account_id]["code"]
            == "unflown_tickets"
        )
        world["world_state"]["financial_accounts"][liability_id]["balance_minor"] = 0
        before = encoded(world)
        cursors = deepcopy(world["deterministic_state"]["id_allocator"])
        failed = process_next_event(world)
        self.assertFalse(failed.succeeded)
        self.assertEqual(failed.failure.code, "HANDLER_FAILED")
        self.assertEqual(encoded(world), before)
        self.assertEqual(world["deterministic_state"]["id_allocator"], cursors)
        self.assertIn(
            next(iter(world["world_state"]["pending_events"])),
            world["world_state"]["pending_events"],
        )

    def test_whole_world_validation_recomputes_immutable_operating_cost(self):
        world, _market_id, flight_id = migrated_empty()
        flight = world["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        result = world["world_state"]["flight_results"][flight_id]
        transaction = world["world_state"]["transactions"][
            result["settlement_transaction_id"]
        ]
        result["operating_cost_minor"] = 1
        transaction["entries"][-2]["amount_minor"] = 1
        transaction["entries"][-1]["amount_minor"] = -1
        validation = validate_world(world)
        self.assertFalse(validation.is_valid)
        self.assertTrue(
            any(issue.code == "result_validation_failed" for issue in validation.errors),
            validation.as_dict(),
        )
        snapshot = encoded(world)
        repeated = process_flight_completion(
            world, flight_id, **completion_witnesses(world, flight_id)
        )
        self.assertFalse(repeated.succeeded)
        self.assertEqual(encoded(world), snapshot)

    def test_whole_world_validation_binds_operation_and_aircraft_topology(self):
        world, _market_id, flight_id = migrated_empty()
        flight = world["world_state"]["dated_flights"][flight_id]
        departed = process_events_through(world, flight["scheduled_off_block_utc"])
        self.assertTrue(departed.succeeded, departed.failure)
        operation = world["world_state"]["active_aircraft_operations"][flight_id]
        operation["booking_revision"] += 1
        operation["inventory_revision"] += 1
        validation = validate_world(world)
        self.assertFalse(validation.is_valid)

        completed, _market_id, completed_id = migrated_empty()
        completed_flight = completed["world_state"]["dated_flights"][completed_id]
        processed = process_events_through(
            completed, completed_flight["scheduled_in_block_utc"]
        )
        self.assertTrue(processed.succeeded, processed.failure)
        aircraft = completed["world_state"]["aircraft"][
            completed_flight["planned_aircraft_id"]
        ]
        aircraft["current_airport_id"] = completed_flight["origin_airport_id"]
        validation = validate_world(completed)
        self.assertFalse(validation.is_valid)

    def test_public_helpers_contain_malformed_inputs_without_mutation(self):
        world, _market_id, flight_id = migrated_empty()
        snapshot = encoded(world)
        manifest = build_confirmed_carriage_manifest(world, [])
        self.assertFalse(manifest.succeeded)
        self.assertEqual(manifest.issues[0].code, "INVALID_FLIGHT_ID")
        self.assertIsNone(project_flight_fulfilment([], flight_id))
        self.assertIsNone(project_flight_fulfilment(world, []))
        self.assertIsNone(project_recent_flight_results([], "airline-000000000001"))
        self.assertEqual(encoded(world), snapshot)

    def test_malformed_result_values_return_structured_validation_issues(self):
        base, _market_id, flight_id = migrated_empty()
        flight = base["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(base, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        corruptions = {
            "paid_booking_ids": 1,
            "actual_aircraft_id": [],
            "operating_cost_minor": [],
            "settlement_transaction_id": [],
        }
        for field, value in corruptions.items():
            with self.subTest(field=field):
                world = deepcopy(base)
                world["world_state"]["flight_results"][flight_id][field] = value
                validation = validate_world(world)
                self.assertFalse(validation.is_valid)
                self.assertTrue(validation.errors)

    def test_repeat_rejects_malformed_but_ignores_stale_well_formed_witnesses(self):
        world, _market_id, flight_id = migrated_empty()
        flight = world["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(world, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        snapshot = encoded(world)
        malformed = completion_witnesses(world, flight_id)
        malformed["expected_operation_revision"] = []
        rejected = process_flight_completion(world, flight_id, **malformed)
        self.assertFalse(rejected.succeeded)
        self.assertEqual(encoded(world), snapshot)

        stale = completion_witnesses(world, flight_id)
        for key in tuple(stale):
            if key != "expected_configuration_fingerprint":
                stale[key] = 0
        reused = process_flight_completion(world, flight_id, **stale)
        self.assertTrue(reused.succeeded, reused.issues)
        self.assertTrue(reused.reused)
        self.assertEqual(encoded(world), snapshot)

    def test_completed_result_requires_terminal_exact_event_history(self):
        base, _market_id, flight_id = migrated_empty()
        flight = base["world_state"]["dated_flights"][flight_id]
        processed = process_events_through(base, flight["scheduled_in_block_utc"])
        self.assertTrue(processed.succeeded, processed.failure)
        result = base["world_state"]["flight_results"][flight_id]

        tampered = deepcopy(base)
        event = tampered["world_state"]["event_history"][
            result["completion_event_id"]
        ]
        event["payload"]["occurrence_key"] = "forged"
        self.assertFalse(validate_world(tampered).is_valid)

        pending = deepcopy(base)
        pending["simulation"]["time_utc"] = flight["scheduled_in_block_utc"]
        event = pending["world_state"]["event_history"].pop(
            result["completion_event_id"]
        )
        event["status"] = "PENDING"
        event.pop("resolved_at_utc")
        pending["world_state"]["pending_events"][event["event_id"]] = event
        self.assertFalse(validate_world(pending).is_valid)

    def test_cost_profiles_are_exact_integer_calibrations(self):
        expected = {"USD": 669_000, "PHP": 38_802_000, "EUR": 575_340}
        for currency, amount in expected.items():
            with self.subTest(currency=currency):
                source, _market_id, flight_id = schema3_world()
                flight = source["world_state"]["dated_flights"][flight_id]
                airline = source["world_state"]["airlines"][flight["airline_id"]]
                airline["base_currency"] = currency
                flight["fare_offer"]["currency"] = currency
                source["world_state"]["schedule_definitions"][
                    flight["schedule_id"]
                ]["revisions"]["1"]["fare_offer"]["currency"] = currency
                for account_id in airline["financial_account_ids"]:
                    source["world_state"]["financial_accounts"][account_id][
                        "currency"
                    ] = currency
                migrated = migrate_schema_3_to_4(source)
                self.assertTrue(migrated.succeeded, migrated.issues)
                cost = calculate_operating_cost(
                    migrated.world,
                    migrated.world["world_state"]["dated_flights"][flight_id],
                )
                self.assertEqual(cost["operating_cost_minor"], amount)


if __name__ == "__main__":
    unittest.main()
