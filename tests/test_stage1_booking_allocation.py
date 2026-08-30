import unittest
from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from decimal import ROUND_UP, getcontext
from fractions import Fraction
import hashlib
import json
from unittest.mock import patch
from types import SimpleNamespace

from game.booking import (
    CAPACITY_RESIDUAL_RANK_PURPOSE,
    CHOICE_RESIDUAL_RANK_PURPOSE,
    DailyBookingAllocationResult,
    DesiredDateAllocationResult,
    DirectShoppingOffer,
    FareSnapshot,
    MarketAllocationResult,
    OfferScoreEvidence,
    ShoppingScheduleLineage,
    desired_date_score,
    fare_score,
    journey_duration_score,
    new_booking_configuration,
    prepare_daily_booking_allocation,
    score_group_offers,
    transition_booking_configuration_to_production_choice,
)
from game.booking.allocation import _largest_remainder, _validate_result
from game.scheduling import create_schedule_definition, publish_occurrences_through
from game.simulation import schedule_event
from game.world_state import (
    add_aircraft,
    allocate_id,
    calculate_booking_configuration_fingerprint,
    migrate_schema_2_to_3,
    validate_world,
)
from tests.test_stage1_demand_model4 import model4_world
from tests.test_stage1_booking_shopping import run_shopping, schema3_world
from game.booking.shopping import prepare_daily_booking_shopping


def offer(flight_id, fare, deviation=0, duration=3600, airline_id="airline-000000000001"):
    return DirectShoppingOffer(
        "STAGE1_DIRECT_ECONOMY_SHOPPING_OFFER_V1",
        "market-000000000001",
        "2026-08-20",
        flight_id,
        airline_id,
        "airport-000000000001",
        "airport-000000000002",
        "2026-08-20T01:00:00Z",
        "2026-08-20T02:00:00Z",
        deviation,
        duration,
        "ECONOMY",
        FareSnapshot("USD", fare),
        ShoppingScheduleLineage("schedule-000000000001", 1, "occurrence"),
        "PLANNED",
        100,
        0,
    )


def allocation_arguments(world):
    probe = deepcopy(world)
    shopping = run_shopping(probe)
    relevant = {
        item.dated_flight_id: item.observed_inventory_revision
        for plan in shopping.market_plans
        for group in plan.desired_date_groups
        for item in group.offers
    }
    booking = world["simulation"]["configuration"]["booking"]
    return {
        "expected_demand_revision": world["world_state"]["demand_state"]["demand_model_revision"],
        "expected_market_pack_revision": world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"],
        "expected_booking_configuration_revision": booking["revision"],
        "expected_booking_configuration_fingerprint": booking["configuration_fingerprint"],
        "expected_inventory_revisions": relevant,
    }


def committed_base_booking_configuration():
    configuration = {
        "contract": "STAGE1_BOOKING_CONFIGURATION_V1",
        "configuration_version": "stage1-booking-v1",
        "revision": 1,
        "booking_horizon_days": 365,
        "desired_date_policy": "STAGE1_DESIRED_DATE_POLICY_V1",
        "lead_time_buckets": [
            {"minimum_lead_days": 0, "maximum_lead_days": 0, "weight_bps": 500},
            {"minimum_lead_days": 1, "maximum_lead_days": 6, "weight_bps": 1_500},
            {"minimum_lead_days": 7, "maximum_lead_days": 29, "weight_bps": 3_500},
            {"minimum_lead_days": 30, "maximum_lead_days": 89, "weight_bps": 3_000},
            {"minimum_lead_days": 90, "maximum_lead_days": 365, "weight_bps": 1_500},
        ],
        "desired_date_tolerance_days": 3,
        "choice_policy": {
            "contract": "STAGE1_BOOKING_CHOICE_POLICY_V1",
            "production_input_families": ["FARE", "SCHEDULE"],
            "schedule_inputs": ["DATE_DEVIATION", "DEPARTURE_TIMING", "DURATION"],
            "absent_airline_quality_signals": "NEUTRAL",
            "deterministic_rank_usage": "INTEGER_RESIDUALS_AND_EXACT_TIES_ONLY",
            "currency_policy": "SINGLE_CURRENCY_ONLY",
        },
        "configuration_fingerprint": "",
    }
    configuration["configuration_fingerprint"] = (
        calculate_booking_configuration_fingerprint(configuration)
    )
    return configuration


def add_strict_confirmed_booking(world, market_id, flight_id, passenger_count):
    state = world["world_state"]
    flight = state["dated_flights"][flight_id]
    airline_id = flight["airline_id"]
    itinerary_id = allocate_id(world, "itinerary")
    booking_id = allocate_id(world, "booking")
    transaction_id = allocate_id(world, "transaction")
    checkpoint_id = allocate_id(world, "booking_checkpoint")
    fare = flight["fare_offer"]["amount_minor"]
    total_fare = passenger_count * fare
    accounts = state["airlines"][airline_id]["financial_account_ids"]
    state["transactions"][transaction_id] = {
        "transaction_id": transaction_id,
        "airline_id": airline_id,
        "occurred_at_utc": world["simulation"]["time_utc"],
        "description": "Strict confirmed allocation-capacity fixture",
        "source_type": "BOOKING_CHECKPOINT",
        "source_id": checkpoint_id,
        "source_booking_ids": [booking_id],
        "currency": flight["fare_offer"]["currency"],
        "entries": [
            {"account_id": accounts[0], "amount_minor": total_fare},
            {"account_id": accounts[3], "amount_minor": -total_fare},
        ],
    }
    state["itineraries"][itinerary_id] = {
        "itinerary_id": itinerary_id,
        "contract": "STAGE1_DIRECT_ECONOMY_ITINERARY_V1",
        "market_id": market_id,
        "airline_id": airline_id,
        "origin_airport_id": flight["origin_airport_id"],
        "destination_airport_id": flight["destination_airport_id"],
        "dated_flight_ids": [flight_id],
        "scheduled_departure_utc": flight["scheduled_off_block_utc"],
        "scheduled_arrival_utc": flight["scheduled_in_block_utc"],
        "cabin": "ECONOMY",
        "fare_offer_snapshot": deepcopy(flight["fare_offer"]),
        "schedule_lineage": {
            "schedule_id": flight["schedule_id"],
            "schedule_revision": flight["schedule_revision"],
            "occurrence_key": flight["occurrence_key"],
        },
        "status": "CONFIRMED",
    }
    state["booking_state"]["booking_revision"] = 1
    state["bookings"][booking_id] = {
        "booking_id": booking_id,
        "contract": "STAGE1_AGGREGATE_BOOKING_V1",
        "booking_checkpoint_id": checkpoint_id,
        "cohort_key": f"{market_id}@2026-08-20",
        "desired_travel_date": flight["scheduled_departure_local_date"],
        "airline_id": airline_id,
        "itinerary_id": itinerary_id,
        "passenger_count": passenger_count,
        "booked_at_utc": world["simulation"]["time_utc"],
        "total_fare_minor": total_fare,
        "currency": flight["fare_offer"]["currency"],
        "inventory_revision_at_commit": flight["inventory_revision"],
        "finance_transaction_id": transaction_id,
        "booking_revision": 1,
        "status": "CONFIRMED",
    }
    booking_configuration = world["simulation"]["configuration"]["booking"]
    pack = world["simulation"]["configuration"]["demand"][
        "market_pack_configuration"
    ]
    state["booking_state"]["booking_checkpoints"][checkpoint_id] = {
        "booking_checkpoint_id": checkpoint_id,
        "checkpoint_date": "2026-08-20",
        "due_at_utc": "2026-08-20T00:00:00Z",
        "status": "COMPLETED",
        "processed_at_utc": world["simulation"]["time_utc"],
        "booking_revision": 1,
        "booking_configuration_revision": booking_configuration["revision"],
        "booking_configuration_fingerprint": booking_configuration[
            "configuration_fingerprint"
        ],
        "demand_model_revision": state["demand_state"]["demand_model_revision"],
        "market_pack_revision": pack["revision"],
        "market_results": {
            market_id: {
                "market_id": market_id,
                "cohort_key": f"{market_id}@2026-08-20",
                "desired_passenger_count": passenger_count,
                "booked_passenger_count": passenger_count,
                "outside_option_passenger_count": 0,
                "insufficient_capacity_passenger_count": 0,
                "no_eligible_service_passenger_count": 0,
                "no_departure_on_desired_date_passenger_count": 0,
                "booking_ids": [booking_id],
                "desired_date_results": {
                    flight["scheduled_departure_local_date"]: {
                        "desired_travel_date": flight["scheduled_departure_local_date"],
                        "requested_passenger_count": passenger_count,
                        "booked_passenger_count": passenger_count,
                        "outside_option_passenger_count": 0,
                        "insufficient_capacity_passenger_count": 0,
                        "no_eligible_service_passenger_count": 0,
                        "no_departure_on_desired_date_passenger_count": 0,
                        "booking_ids": [booking_id],
                    }
                },
            }
        },
        "financial_transaction_ids": [transaction_id],
    }
    world["simulation"]["operation_revisions"][checkpoint_id] = 1
    schedule_event(
        world,
        event_type="DAILY_BOOKING_CHECKPOINT",
        due_at_utc="2026-08-21T00:00:00Z",
        owner_type="booking_checkpoint",
        owner_id=checkpoint_id,
        operation_revision=1,
        payload={"checkpoint_date": "2026-08-21"},
    )
    if not validate_world(world).is_valid:
        raise AssertionError(validate_world(world).as_dict())
    return booking_id


def add_same_day_competing_flight(
    world, market_id, reference_flight_id, *, registration, fare, capacity
):
    reference = world["world_state"]["dated_flights"][reference_flight_id]
    departure_date = reference["scheduled_departure_local_date"]
    airline_id = reference["airline_id"]
    connection_id = next(
        connection_id
        for connection_id, connection in world["world_state"]["connections"].items()
        if connection["market_id"] == market_id
        and connection["airline_id"] == airline_id
    )
    aircraft_id = add_aircraft(
        world,
        airline_id,
        registration,
        "A320",
        home_airport_id=reference["origin_airport_id"],
    )
    created = create_schedule_definition(
        world,
        airline_id=airline_id,
        connection_id=connection_id,
        planned_aircraft_id=aircraft_id,
        origin_airport_id=reference["origin_airport_id"],
        destination_airport_id=reference["destination_airport_id"],
        weekdays=[date.fromisoformat(departure_date).weekday()],
        departure_local_time="11:00:00",
        arrival_local_time="13:00:00",
        effective_from_local_date=departure_date,
        capacity=capacity,
        fare_offer={"currency": "USD", "amount_minor": fare},
    )
    if not created.succeeded:
        raise AssertionError(created.conflicts)
    published = publish_occurrences_through(
        world, f'{reference["scheduled_off_block_utc"][:10]}T23:59:59Z'
    )
    if not published.succeeded:
        raise AssertionError(published.conflicts)
    return published.created_dated_flight_ids[-1]


def independent_rank(
    purpose, world_seed, cohort_date, market_id, desired_date, identity, fingerprint
):
    material = {
        "purpose": purpose,
        "world_seed": world_seed,
        "cohort_date": cohort_date,
        "market_id": market_id,
        "desired_travel_date": desired_date,
        "choice_identity": identity,
        "choice_policy_contract": "STAGE1_BALANCED_FARE_SCHEDULE_CHOICE_V1",
        "booking_configuration_fingerprint": fingerprint,
    }
    encoded = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def independent_largest_remainder(total, weights, rank):
    denominator = sum(weights.values(), Fraction(0))
    exact = {
        key: Fraction(total) * value / denominator for key, value in weights.items()
    }
    allocated = {
        key: value.numerator // value.denominator for key, value in exact.items()
    }
    residual = total - sum(allocated.values())
    order = sorted(
        weights,
        key=lambda key: (-(exact[key] - allocated[key]), rank(key), key),
    )
    for key in order[:residual]:
        allocated[key] += 1
    return allocated


class ChoiceScoreTests(unittest.TestCase):
    def test_exact_policy_constants_and_independent_tie_purposes(self):
        policy = new_booking_configuration()["choice_policy"]
        self.assertEqual(policy["contract"], "STAGE1_BALANCED_FARE_SCHEDULE_CHOICE_V1")
        self.assertEqual(
            policy["component_weights_bps"],
            {"fare": 5000, "desired_date_deviation": 3000, "journey_duration": 2000},
        )
        self.assertEqual(policy["outside_option_weight_score_units"], 2500)
        self.assertNotEqual(CHOICE_RESIDUAL_RANK_PURPOSE, CAPACITY_RESIDUAL_RANK_PURPOSE)

    def test_exact_fare_date_and_duration_scores(self):
        self.assertEqual([fare_score(value, 100) for value in (100, 125, 150, 200, 201)], [10000, 7500, 5000, 0, 0])
        self.assertEqual(fare_score(0, 0), 10000)
        self.assertEqual(fare_score(1, 0), 0)
        self.assertEqual([desired_date_score(value) for value in range(4)], [10000, 7500, 5000, 2500])
        self.assertEqual(journey_duration_score(3600, 3600), 10000)
        self.assertEqual(journey_duration_score(7200, 3600), 5000)
        self.assertEqual(journey_duration_score(10800, 3600), 3333)

    def test_composite_retains_exact_numerator_and_zero_fare_score_can_compete(self):
        scores = score_group_offers((offer("dated-flight-000000000001", 100), offer("dated-flight-000000000002", 200)))
        self.assertEqual(scores[0].composite_numerator, 100_000_000)
        self.assertEqual(scores[1].fare_score, 0)
        self.assertEqual(scores[1].composite_numerator, 50_000_000)

    def test_one_perfect_offer_is_exactly_eighty_twenty(self):
        allocation = _largest_remainder(
            100, {"offer": 10_000, "outside": 2_500}, lambda identity: identity
        )
        self.assertEqual(allocation, {"offer": 80, "outside": 20})

    def test_global_decimal_context_is_irrelevant(self):
        context = getcontext()
        previous = (context.prec, context.rounding)
        try:
            context.prec = 2
            context.rounding = ROUND_UP
            self.assertEqual(fare_score(125, 100), 7500)
            self.assertEqual(journey_duration_score(10800, 3600), 3333)
        finally:
            context.prec, context.rounding = previous

    def test_fare_score_rejects_an_offer_below_the_declared_minimum(self):
        with self.assertRaises(ValueError):
            fare_score(99, 100)

    def test_half_even_fare_boundaries_and_huge_integer_inputs_are_exact(self):
        self.assertEqual(fare_score(20_002, 20_001), 10_000)
        self.assertEqual(fare_score(20_001, 20_000), 10_000)
        self.assertEqual(fare_score(20_000, 19_999), 9_999)
        self.assertEqual(fare_score(20_003, 20_000), 9_998)
        huge = 10**500
        self.assertEqual(fare_score(huge, huge), 10_000)
        self.assertEqual(fare_score(2 * huge, huge), 0)
        for invalid in (-1, True, 1.0, "1"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    fare_score(invalid, 1)

    def test_date_and_duration_boundaries_reject_noncanonical_inputs(self):
        self.assertEqual(desired_date_score(-3), 2_500)
        for invalid in (-4, 4, True, 1.0):
            with self.subTest(date_deviation=invalid):
                with self.assertRaises(ValueError):
                    desired_date_score(invalid)
        for invalid in (0, -1, True, 1.0):
            with self.subTest(duration=invalid):
                with self.assertRaises(ValueError):
                    journey_duration_score(invalid, 1)

    def test_zero_and_many_identical_choice_weights_conserve_with_keyed_ties(self):
        identities = tuple(f"dated-flight-{index:012d}" for index in range(1, 21))
        weights = {identity: 10_000 for identity in identities}
        weights["__OUTSIDE_OPTION__"] = 2_500
        zero = _largest_remainder(0, weights, lambda identity: identity)
        self.assertEqual(sum(zero.values()), 0)
        allocated = _largest_remainder(
            37,
            weights,
            lambda identity: independent_rank(
                CHOICE_RESIDUAL_RANK_PURPOSE,
                7,
                "2026-08-20",
                "market-000000000001",
                "2026-08-20",
                identity,
                "a" * 64,
            ),
        )
        self.assertEqual(sum(allocated.values()), 37)
        self.assertEqual(set(allocated), set(weights))

    def test_all_zero_real_weights_assign_everyone_outside(self):
        allocation = _largest_remainder(
            999,
            {"real-a": 0, "real-b": 0, "__OUTSIDE_OPTION__": 2_500},
            lambda identity: identity,
        )
        self.assertEqual(allocation["__OUTSIDE_OPTION__"], 999)
        self.assertEqual(allocation["real-a"] + allocation["real-b"], 0)


class AllocationPlanValidationTests(unittest.TestCase):
    def test_duplicate_market_results_reject_even_when_empty(self):
        market = MarketAllocationResult(
            "market-000000000001",
            "market-000000000001@2026-08-20",
            "MODEL3_PROCESSED_COHORT_V1",
            0,
            0,
            0,
            0,
            0,
            0,
        )
        result = DailyBookingAllocationResult(
            "COMPLETED",
            "STAGE1_DAILY_BOOKING_ALLOCATION_PLAN_V1",
            "stage1-booking-allocation-v1",
            "2026-08-20",
            1,
            1,
            2,
            "a" * 64,
            market_results=(market, market),
        )
        self.assertFalse(_validate_result(result))

    def test_invalid_score_evidence_rejects(self):
        group = DesiredDateAllocationResult(
            "2026-08-20",
            1,
            0,
            1,
            0,
            0,
            0,
            offer_scores=(
                OfferScoreEvidence(
                    "dated-flight-000000000001",
                    "airline-000000000001",
                    -1,
                    10_000,
                    10_000,
                    99_995_000,
                ),
            ),
        )
        market = MarketAllocationResult(
            "market-000000000001",
            "market-000000000001@2026-08-20",
            "MODEL3_PROCESSED_COHORT_V1",
            1,
            0,
            1,
            0,
            0,
            0,
            (group,),
        )
        result = DailyBookingAllocationResult(
            "COMPLETED",
            "STAGE1_DAILY_BOOKING_ALLOCATION_PLAN_V1",
            "stage1-booking-allocation-v1",
            "2026-08-20",
            1,
            1,
            2,
            "a" * 64,
            1,
            0,
            1,
            0,
            0,
            0,
            (market,),
        )
        self.assertFalse(_validate_result(result))


class BookingConfigurationCompatibilityTests(unittest.TestCase):
    def test_committed_base_schema3_configuration_remains_valid(self):
        world, _market_id, _flight_id = schema3_world()
        legacy = committed_base_booking_configuration()
        self.assertEqual(
            legacy["configuration_fingerprint"],
            "a11407e6fd5e13d8ea51cd7f10f2423ef1427bf5511d83b2fb80c7cc757b10eb",
        )
        world["simulation"]["configuration"]["booking"] = legacy
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())

    def test_explicit_transition_is_atomic_revision_owned_and_idempotent(self):
        world, _market_id, _flight_id = schema3_world()
        world["simulation"]["configuration"]["booking"] = (
            committed_base_booking_configuration()
        )
        before = deepcopy(world)
        legacy = world["simulation"]["configuration"]["booking"]
        stale = transition_booking_configuration_to_production_choice(
            world,
            expected_booking_configuration_revision=legacy["revision"],
            expected_booking_configuration_fingerprint="0" * 64,
        )
        self.assertFalse(stale.succeeded)
        self.assertEqual(world, before)

        result = transition_booking_configuration_to_production_choice(
            world,
            expected_booking_configuration_revision=legacy["revision"],
            expected_booking_configuration_fingerprint=legacy[
                "configuration_fingerprint"
            ],
        )
        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(result.changed)
        current = world["simulation"]["configuration"]["booking"]
        self.assertEqual((result.previous_revision, result.current_revision), (1, 2))
        self.assertNotEqual(result.previous_fingerprint, result.current_fingerprint)
        self.assertEqual(current["choice_policy"], new_booking_configuration()["choice_policy"])
        expected = deepcopy(before)
        expected_configuration = expected["simulation"]["configuration"]["booking"]
        expected_configuration["revision"] = current["revision"]
        expected_configuration["choice_policy"] = deepcopy(current["choice_policy"])
        expected_configuration["configuration_fingerprint"] = current[
            "configuration_fingerprint"
        ]
        self.assertEqual(world, expected)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())

        transitioned = deepcopy(world)
        repeated = transition_booking_configuration_to_production_choice(
            world,
            expected_booking_configuration_revision=current["revision"],
            expected_booking_configuration_fingerprint=current[
                "configuration_fingerprint"
            ],
        )
        self.assertTrue(repeated.succeeded, repeated.issues)
        self.assertFalse(repeated.changed)
        self.assertEqual(world, transitioned)

    def test_fresh_schema3_model3_and_model4_worlds_use_production_revision(self):
        model3, _market_id, _flight_id = schema3_world()
        self.assertEqual(
            model3["simulation"]["configuration"]["booking"]["revision"], 2
        )
        self.assertTrue(validate_world(model3).is_valid, validate_world(model3).as_dict())

        model4, _ids, _old = model4_world()
        migration = migrate_schema_2_to_3(model4)
        self.assertTrue(migration.succeeded, migration.issues)
        model4 = migration.world
        booking = model4["simulation"]["configuration"]["booking"]
        self.assertEqual(booking["revision"], 2)
        self.assertEqual(
            booking["choice_policy"]["contract"],
            "STAGE1_BALANCED_FARE_SCHEDULE_CHOICE_V1",
        )
        self.assertTrue(validate_world(model4).is_valid, validate_world(model4).as_dict())

    def test_committed_base_model4_world_has_the_same_explicit_transition(self):
        source, _ids, _old = model4_world()
        migrated = migrate_schema_2_to_3(source)
        self.assertTrue(migrated.succeeded, migrated.issues)
        world = migrated.world
        legacy = committed_base_booking_configuration()
        world["simulation"]["configuration"]["booking"] = deepcopy(legacy)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())
        before = deepcopy(world)
        result = transition_booking_configuration_to_production_choice(
            world,
            expected_booking_configuration_revision=legacy["revision"],
            expected_booking_configuration_fingerprint=legacy[
                "configuration_fingerprint"
            ],
        )
        self.assertTrue(result.succeeded, result.issues)
        expected = deepcopy(before)
        expected["simulation"]["configuration"]["booking"] = deepcopy(
            world["simulation"]["configuration"]["booking"]
        )
        self.assertEqual(world, expected)

    def test_forged_revision_policy_pair_rejects(self):
        world, _market_id, _flight_id = schema3_world()
        configuration = world["simulation"]["configuration"]["booking"]
        configuration["revision"] = 1
        configuration["configuration_fingerprint"] = (
            calculate_booking_configuration_fingerprint(configuration)
        )
        self.assertFalse(validate_world(world).is_valid)

    def test_legacy_world_is_not_rewritten_by_5b_and_requires_explicit_5c_transition(self):
        world, _market_id, _flight_id = schema3_world()
        world["simulation"]["configuration"]["booking"] = (
            committed_base_booking_configuration()
        )
        legacy = deepcopy(world["simulation"]["configuration"]["booking"])
        shopping = run_shopping(world)
        self.assertTrue(shopping.succeeded, shopping.issues)
        self.assertEqual(world["simulation"]["configuration"]["booking"], legacy)
        rejected = prepare_daily_booking_allocation(
            world, **allocation_arguments(world)
        )
        self.assertFalse(rejected.succeeded)
        self.assertEqual(world["simulation"]["configuration"]["booking"], legacy)
        transitioned = transition_booking_configuration_to_production_choice(
            world,
            expected_booking_configuration_revision=legacy["revision"],
            expected_booking_configuration_fingerprint=legacy[
                "configuration_fingerprint"
            ],
        )
        self.assertTrue(transitioned.succeeded, transitioned.issues)
        completed = prepare_daily_booking_allocation(
            world, **allocation_arguments(world)
        )
        self.assertTrue(completed.succeeded, completed.issues)


class AllocationCommandTests(unittest.TestCase):
    def test_detached_plan_conserves_and_mutates_only_the_5b_marker(self):
        world, _market_id, _flight_id = schema3_world()
        before = deepcopy(world)
        booking_state = deepcopy(world["world_state"]["booking_state"])
        flights = deepcopy(world["world_state"]["dated_flights"])
        finances = {
            key: value["finance_revision"]
            for key, value in world["world_state"]["airlines"].items()
        }
        booking_configuration = deepcopy(
            world["simulation"]["configuration"]["booking"]
        )
        pack_configuration = deepcopy(
            world["simulation"]["configuration"]["demand"][
                "market_pack_configuration"
            ]
        )
        demand_revision = world["world_state"]["demand_state"][
            "demand_model_revision"
        ]
        transactions = deepcopy(world["world_state"]["transactions"])
        pending_events = deepcopy(world["world_state"]["pending_events"])
        event_history = deepcopy(world["world_state"]["event_history"])
        allocator = deepcopy(world["deterministic_state"]["id_allocator"])
        result = prepare_daily_booking_allocation(world, **allocation_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(
            result.requested_passengers,
            result.selected_passengers
            + result.outside_option_passengers
            + result.insufficient_capacity_passengers
            + result.no_eligible_service_passengers
            + result.no_departure_on_desired_date_passengers,
        )
        self.assertEqual(world["world_state"]["booking_state"], booking_state)
        self.assertEqual(world["world_state"]["dated_flights"], flights)
        self.assertEqual(
            {key: value["finance_revision"] for key, value in world["world_state"]["airlines"].items()},
            finances,
        )
        self.assertEqual(before["world_state"]["bookings"], world["world_state"]["bookings"])
        self.assertEqual(before["world_state"]["itineraries"], world["world_state"]["itineraries"])
        self.assertEqual(
            world["simulation"]["configuration"]["booking"],
            booking_configuration,
        )
        self.assertEqual(
            world["simulation"]["configuration"]["demand"][
                "market_pack_configuration"
            ],
            pack_configuration,
        )
        self.assertEqual(
            world["world_state"]["demand_state"]["demand_model_revision"],
            demand_revision,
        )
        self.assertEqual(world["world_state"]["transactions"], transactions)
        self.assertEqual(world["world_state"]["pending_events"], pending_events)
        self.assertEqual(world["world_state"]["event_history"], event_history)
        self.assertEqual(world["deterministic_state"]["id_allocator"], allocator)

    def test_tiny_capacity_creates_outside_and_capacity_failure_without_oversell(self):
        world, _market_id, flight_id = schema3_world()
        flight = world["world_state"]["dated_flights"][flight_id]
        flight["capacity"] = 1
        world["world_state"]["schedule_definitions"][flight["schedule_id"]][
            "revisions"
        ][str(flight["schedule_revision"])]["capacity"] = 1
        arguments = allocation_arguments(world)
        result = prepare_daily_booking_allocation(world, **arguments)
        self.assertTrue(result.succeeded, result.issues)
        selected = sum(
            allocation.selected_passengers
            for market in result.market_results
            for group in market.desired_date_results
            for allocation in group.selected_offer_allocations
            if allocation.dated_flight_id == flight_id
        )
        self.assertEqual(selected, 1)
        self.assertGreater(result.outside_option_passengers, 0)
        self.assertGreater(result.insufficient_capacity_passengers, 0)

    def test_stale_missing_extra_and_boolean_inventory_expectations_reject_atomically(self):
        for mutate in (
            lambda value: value.update({next(iter(value)): 99}),
            lambda value: value.pop(next(iter(value))),
            lambda value: value.update({"dated-flight-999999999999": 0}),
            lambda value: value.update({next(iter(value)): True}),
        ):
            world, _market_id, _flight_id = schema3_world()
            arguments = allocation_arguments(world)
            mutate(arguments["expected_inventory_revisions"])
            before = deepcopy(world)
            result = prepare_daily_booking_allocation(world, **arguments)
            self.assertFalse(result.succeeded)
            self.assertIn(result.issues[0].code, {"STALE_REVISION", "INVALID_INVENTORY"})
            self.assertEqual(world, before)

    def test_noncanonical_inventory_containers_reject_structured_and_atomic(self):
        class WrappedMapping(Mapping):
            def __init__(self, value):
                self.value = value

            def __getitem__(self, key):
                return self.value[key]

            def __iter__(self):
                return iter(self.value)

            def __len__(self):
                return len(self.value)

        for replacement in ([], "0", WrappedMapping({})):
            with self.subTest(replacement=type(replacement).__name__):
                world, _market_id, _flight_id = schema3_world()
                arguments = allocation_arguments(world)
                arguments["expected_inventory_revisions"] = replacement
                before = deepcopy(world)
                result = prepare_daily_booking_allocation(world, **arguments)
                self.assertFalse(result.succeeded)
                self.assertEqual(result.issues[0].code, "INVALID_INVENTORY")
                self.assertEqual(world, before)

        world, _market_id, flight_id = schema3_world()
        arguments = allocation_arguments(world)
        cyclic = {}
        cyclic[flight_id] = cyclic
        arguments["expected_inventory_revisions"] = cyclic
        before = deepcopy(world)
        result = prepare_daily_booking_allocation(world, **arguments)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "INVALID_INVENTORY")
        self.assertEqual(world, before)

    def test_reused_marker_leaves_authority_byte_equivalent(self):
        world, _market_id, _flight_id = schema3_world()
        first = prepare_daily_booking_allocation(world, **allocation_arguments(world))
        self.assertTrue(first.succeeded, first.issues)
        before = deepcopy(world)
        second = prepare_daily_booking_allocation(world, **allocation_arguments(world))
        self.assertTrue(second.succeeded, second.issues)
        self.assertEqual(world, before)
        self.assertEqual(first, second)

    def test_inventory_is_reread_after_shopping_and_late_change_rejects_atomically(self):
        world, _market_id, flight_id = schema3_world()
        arguments = allocation_arguments(world)
        before = deepcopy(world)

        def shopping_then_change_inventory(candidate, **kwargs):
            result = prepare_daily_booking_shopping(candidate, **kwargs)
            candidate["world_state"]["dated_flights"][flight_id][
                "inventory_revision"
            ] += 1
            return result

        with patch(
            "game.booking.allocation.prepare_daily_booking_shopping",
            side_effect=shopping_then_change_inventory,
        ):
            result = prepare_daily_booking_allocation(world, **arguments)
        self.assertFalse(result.succeeded)
        self.assertIn(result.issues[0].code, {"STALE_REVISION", "INVALID_INVENTORY"})
        self.assertEqual(world, before)

    def test_broken_initial_deepcopy_returns_a_structured_issue(self):
        class BrokenCopy(dict):
            def __deepcopy__(self, memo):
                raise RuntimeError("copy failed")

        result = prepare_daily_booking_allocation(
            BrokenCopy(),
            expected_demand_revision=0,
            expected_market_pack_revision=0,
            expected_booking_configuration_revision=0,
            expected_booking_configuration_fingerprint="",
            expected_inventory_revisions={},
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "INVALID_WORLD_STATE")

    def test_late_result_validation_failure_rolls_back_new_marker(self):
        world, _market_id, _flight_id = schema3_world()
        before = deepcopy(world)
        with patch("game.booking.allocation._validate_result", return_value=False):
            result = prepare_daily_booking_allocation(
                world, **allocation_arguments(world)
            )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "RESULT_VALIDATION_FAILED")
        self.assertEqual(world, before)

    def test_broken_scoring_exception_is_structured_and_atomic(self):
        class BrokenMessage(Exception):
            def __str__(self):
                raise RuntimeError("broken exception text")

        world, _market_id, _flight_id = schema3_world()
        before = deepcopy(world)
        with patch(
            "game.booking.allocation.score_group_offers",
            side_effect=BrokenMessage(),
        ):
            result = prepare_daily_booking_allocation(
                world, **allocation_arguments(world)
            )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "BOOKING_ALLOCATION_FAILED")
        self.assertEqual(world, before)

    def test_final_candidate_validation_failure_rolls_back_new_marker(self):
        world, _market_id, _flight_id = schema3_world()
        before = deepcopy(world)
        invalid = SimpleNamespace(
            is_valid=False,
            errors=(
                SimpleNamespace(
                    code="invalid_world_state",
                    message="injected final candidate defect",
                    path="$",
                ),
            ),
        )
        with patch("game.booking.allocation.validate_world", return_value=invalid):
            result = prepare_daily_booking_allocation(
                world, **allocation_arguments(world)
            )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "invalid_world_state")
        self.assertEqual(world, before)

    def test_strict_booking_consumes_capacity_but_compatibility_wrapper_does_not(self):
        compatibility, _market_id, flight_id = schema3_world()
        flight = compatibility["world_state"]["dated_flights"][flight_id]
        flight["capacity"] = 5
        compatibility["world_state"]["schedule_definitions"][flight["schedule_id"]][
            "revisions"
        ][str(flight["schedule_revision"])]["capacity"] = 5
        compatibility_result = prepare_daily_booking_allocation(
            compatibility, **allocation_arguments(compatibility)
        )
        self.assertTrue(compatibility_result.succeeded, compatibility_result.issues)
        self.assertEqual(compatibility_result.selected_passengers, 5)

        strict, market_id, flight_id = schema3_world()
        flight = strict["world_state"]["dated_flights"][flight_id]
        flight["capacity"] = 5
        strict["world_state"]["schedule_definitions"][flight["schedule_id"]][
            "revisions"
        ][str(flight["schedule_revision"])]["capacity"] = 5
        marker = run_shopping(strict)
        self.assertTrue(marker.succeeded, marker.issues)
        add_strict_confirmed_booking(strict, market_id, flight_id, 3)
        strict_result = prepare_daily_booking_allocation(
            strict, **allocation_arguments(strict)
        )
        self.assertTrue(strict_result.succeeded, strict_result.issues)
        self.assertEqual(strict_result.selected_passengers, 2)

    def test_overflow_reprices_against_unsaturated_alternate_and_terminates(self):
        world, market_id, preferred_id = schema3_world()
        preferred = world["world_state"]["dated_flights"][preferred_id]
        preferred["capacity"] = 1
        preferred["fare_offer"]["amount_minor"] = 0
        preferred_revision = world["world_state"]["schedule_definitions"][
            preferred["schedule_id"]
        ]["revisions"][str(preferred["schedule_revision"])]
        preferred_revision["capacity"] = 1
        preferred_revision["fare_offer"]["amount_minor"] = 0
        alternate_id = add_same_day_competing_flight(
            world,
            market_id,
            preferred_id,
            registration="RP-ALT1",
            fare=10_000,
            capacity=1_000_000,
        )
        result = prepare_daily_booking_allocation(world, **allocation_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        selected = {
            item.dated_flight_id: item.selected_passengers
            for market in result.market_results
            for group in market.desired_date_results
            for item in group.selected_offer_allocations
        }
        self.assertEqual(selected[preferred_id], 1)
        self.assertGreater(selected[alternate_id], 1)
        self.assertEqual(result.insufficient_capacity_passengers, 0)
        self.assertGreaterEqual(result.contention_rounds, 2)
        self.assertTrue(
            any(
                score.dated_flight_id == alternate_id and score.fare_score == 0
                for market in result.market_results
                for group in market.desired_date_results
                for score in group.offer_scores
            )
        )

    def test_dictionary_insertion_order_does_not_change_the_plan(self):
        left, _market_id, _flight_id = schema3_world()
        right = deepcopy(left)
        state = right["world_state"]
        for field in (
            "airlines",
            "directional_markets",
            "connections",
            "schedule_definitions",
            "dated_flights",
            "itineraries",
            "bookings",
        ):
            state[field] = dict(reversed(tuple(state[field].items())))
        left_arguments = allocation_arguments(left)
        right_arguments = allocation_arguments(right)
        right_arguments["expected_inventory_revisions"] = dict(
            reversed(tuple(right_arguments["expected_inventory_revisions"].items()))
        )
        left_result = prepare_daily_booking_allocation(left, **left_arguments)
        right_result = prepare_daily_booking_allocation(right, **right_arguments)
        self.assertTrue(left_result.succeeded, left_result.issues)
        self.assertTrue(right_result.succeeded, right_result.issues)
        self.assertEqual(left_result, right_result)

    def test_multi_group_contention_is_exactly_proportional_and_not_sequential(self):
        world, market_id, flight_id = schema3_world()
        flight = world["world_state"]["dated_flights"][flight_id]
        flight["capacity"] = 7
        world["world_state"]["schedule_definitions"][flight["schedule_id"]][
            "revisions"
        ][str(flight["schedule_revision"])]["capacity"] = 7
        probe = deepcopy(world)
        shopping = run_shopping(probe)
        self.assertTrue(shopping.succeeded, shopping.issues)
        booking = world["simulation"]["configuration"]["booking"]
        seed = world["deterministic_state"]["world_seed"]
        requests = {}
        initial_outside = {}
        for plan in shopping.market_plans:
            for group in plan.desired_date_groups:
                matching = [
                    item for item in group.offers if item.dated_flight_id == flight_id
                ]
                if not matching:
                    continue
                score = score_group_offers(matching)[0]
                weights = {
                    flight_id: Fraction(score.composite_numerator, 10_000),
                    "__OUTSIDE_OPTION__": Fraction(2_500),
                }
                allocation = independent_largest_remainder(
                    group.requested_passengers,
                    weights,
                    lambda identity, desired=group.desired_travel_date: independent_rank(
                        CHOICE_RESIDUAL_RANK_PURPOSE,
                        seed,
                        shopping.cohort_date,
                        market_id,
                        desired,
                        identity,
                        booking["configuration_fingerprint"],
                    ),
                )
                requests[group.desired_travel_date] = allocation[flight_id]
                initial_outside[group.desired_travel_date] = allocation[
                    "__OUTSIDE_OPTION__"
                ]
        expected = independent_largest_remainder(
            7,
            {key: Fraction(value) for key, value in requests.items()},
            lambda desired: independent_rank(
                CAPACITY_RESIDUAL_RANK_PURPOSE,
                seed,
                shopping.cohort_date,
                market_id,
                desired,
                flight_id,
                booking["configuration_fingerprint"],
            ),
        )
        result = prepare_daily_booking_allocation(world, **allocation_arguments(world))
        self.assertTrue(result.succeeded, result.issues)
        actual = {
            group.desired_travel_date: sum(
                item.selected_passengers
                for item in group.selected_offer_allocations
                if item.dated_flight_id == flight_id
            )
            for market in result.market_results
            for group in market.desired_date_results
            if group.desired_travel_date in requests
        }
        actual_outside = {
            group.desired_travel_date: group.outside_option_passengers
            for market in result.market_results
            for group in market.desired_date_results
            if group.desired_travel_date in requests
        }
        self.assertEqual(actual, expected)
        self.assertEqual(actual_outside, initial_outside)
        self.assertEqual(sum(actual.values()), 7)


if __name__ == "__main__":
    unittest.main()
