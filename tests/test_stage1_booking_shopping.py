import math
import unittest
from copy import deepcopy
from decimal import ROUND_UP, getcontext

from game.booking import (
    NO_DEPARTURE_ON_DESIRED_DATE,
    NO_ELIGIBLE_SERVICE,
    SHOPPABLE,
    allocate_desired_travel_dates,
    calculate_booking_configuration_fingerprint,
    new_booking_configuration,
    prepare_daily_booking_shopping,
    rebuild_direct_flight_shopping_indexes,
)
from game.demand import resolve_daily_cohort, revise_demand_model
from game.scheduling import (
    DatedFlightIndexes,
    create_schedule_definition,
    publish_occurrences_through,
    rebuild_dated_flight_indexes,
)
from game.world_state import (
    add_aircraft,
    add_airline,
    add_connection,
    allocate_id,
    disable_country_pack,
    migrate_schema_2_to_3,
    validate_world,
)
from game.world_state.schema import (
    MODEL3_PROCESSED_COHORT_V1,
    MODEL4_TRAVEL_SCOPE_COHORT_V1,
)
from tests.test_stage1_booking_foundation import (
    make_schema2_with_flight_and_legacy_booking,
    migrate,
)
from tests.test_stage1_demand_model4 import model4_world
from tests.test_stage1_market_packs import materialized_world


def schema3_world():
    source, market_id, flight_id, *_ = (
        make_schema2_with_flight_and_legacy_booking()
    )
    return migrate(source), market_id, flight_id


def run_shopping(world, **overrides):
    demand = world["world_state"]["demand_state"]["demand_model_revision"]
    pack = world["simulation"]["configuration"]["demand"][
        "market_pack_configuration"
    ]["revision"]
    booking = world["simulation"]["configuration"]["booking"]
    arguments = {
        "expected_demand_revision": demand,
        "expected_market_pack_revision": pack,
        "expected_booking_configuration_revision": booking["revision"],
        "expected_booking_configuration_fingerprint": booking[
            "configuration_fingerprint"
        ],
    }
    arguments.update(overrides)
    return prepare_daily_booking_shopping(world, **arguments)


def offer_groups(result):
    return [
        group
        for plan in result.market_plans
        for group in plan.desired_date_groups
        if group.offers
    ]


class DesiredDateAllocationTests(unittest.TestCase):
    def allocate(self, count, *, seed=123):
        return allocate_desired_travel_dates(
            count,
            world_seed=seed,
            cohort_date="2026-08-20",
            market_id="market-000000000001",
            booking_configuration=new_booking_configuration(),
        )

    def test_zero_one_small_and_large_conserve_without_passenger_objects(self):
        self.assertEqual(self.allocate(0), ())
        for count in (1, 7, 54_000, 10**9):
            allocation = self.allocate(count)
            self.assertEqual(sum(value for _date, value in allocation), count)
            self.assertTrue(all(type(value) is int and value > 0 for _date, value in allocation))
            self.assertLessEqual(len(allocation), 366)

    def test_exact_bucket_totals_same_day_and_inclusive_final_horizon(self):
        divisor = math.lcm(1, 6, 23, 60, 276)
        count = 10_000 * divisor
        allocation = dict(self.allocate(count))
        ordered = sorted(allocation.items())
        totals = [
            sum(value for _day, value in ordered[0:1]),
            sum(value for _day, value in ordered[1:7]),
            sum(value for _day, value in ordered[7:30]),
            sum(value for _day, value in ordered[30:90]),
            sum(value for _day, value in ordered[90:366]),
        ]
        self.assertEqual(totals, [count * 500 // 10_000, count * 1500 // 10_000, count * 3500 // 10_000, count * 3000 // 10_000, count * 1500 // 10_000])
        self.assertIn("2026-08-20", allocation)
        self.assertIn("2027-08-20", allocation)
        self.assertNotIn("2027-08-21", allocation)

    def test_residual_ties_are_keyed_deterministic_and_decimal_independent(self):
        context = getcontext()
        old_precision, old_rounding = context.prec, context.rounding
        try:
            context.prec = 2
            context.rounding = ROUND_UP
            left = self.allocate(17, seed=77)
            right = self.allocate(17, seed=77)
            other = self.allocate(17, seed=78)
        finally:
            context.prec, context.rounding = old_precision, old_rounding
        self.assertEqual(left, right)
        self.assertNotEqual(left, other)

    def test_configuration_order_does_not_change_allocation(self):
        configuration = new_booking_configuration()
        reordered = {key: deepcopy(configuration[key]) for key in reversed(configuration)}
        left = allocate_desired_travel_dates(101, world_seed=9, cohort_date="2026-08-20", market_id="market-000000000001", booking_configuration=configuration)
        right = allocate_desired_travel_dates(101, world_seed=9, cohort_date="2026-08-20", market_id="market-000000000001", booking_configuration=reordered)
        self.assertEqual(left, right)


class DailyBookingShoppingTests(unittest.TestCase):
    def _add_current_timestamp_flight(self, world, market_id, reference_flight_id):
        reference = world["world_state"]["dated_flights"][reference_flight_id]
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
            "RP-NOW1",
            "A320",
            home_airport_id=reference["origin_airport_id"],
        )
        schedule = create_schedule_definition(
            world,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=reference["origin_airport_id"],
            destination_airport_id=reference["destination_airport_id"],
            weekdays=[3],
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            effective_from_local_date="2026-08-20",
            capacity=10,
            fare_offer={"currency": "USD", "amount_minor": 0},
        )
        self.assertTrue(schedule.succeeded, schedule.conflicts)
        published = publish_occurrences_through(world, "2026-08-20T00:00:00Z")
        self.assertTrue(published.succeeded, published.conflicts)
        return published.created_dated_flight_ids[-1]

    def test_current_day_v1_creation_reuse_and_historical_preservation(self):
        world, market_id, _flight_id = schema3_world()
        historical = resolve_daily_cohort(world, market_id, "2026-08-19")
        self.assertFalse(historical.reused)
        historical_marker = deepcopy(world["world_state"]["demand_state"]["processed_cohorts"])
        before_first = deepcopy(world)
        first = run_shopping(world)
        self.assertTrue(first.succeeded, first.issues)
        self.assertEqual(first.created_cohort_count, 1)
        self.assertEqual(first.market_plans[0].cohort_contract, MODEL3_PROCESSED_COHORT_V1)
        self.assertEqual(world["world_state"]["demand_state"]["processed_cohorts"][f"{market_id}@2026-08-19"], historical_marker[f"{market_id}@2026-08-19"])
        without_current = deepcopy(world)
        without_current["world_state"]["demand_state"]["processed_cohorts"].pop(
            f"{market_id}@2026-08-20"
        )
        self.assertEqual(without_current, before_first)
        after_first = deepcopy(world)
        second = run_shopping(world)
        self.assertTrue(second.succeeded, second.issues)
        self.assertEqual(second.created_cohort_count, 0)
        self.assertEqual(second.reused_cohort_count, 1)
        self.assertEqual(first.market_plans, second.market_plans)
        self.assertEqual(world, after_first)

    def test_offer_snapshot_tolerance_conservation_and_detachment(self):
        world, market_id, flight_id = schema3_world()
        before_booking = deepcopy(world["world_state"]["booking_state"])
        before_bookings = deepcopy(world["world_state"]["bookings"])
        before_itineraries = deepcopy(world["world_state"]["itineraries"])
        before_allocator = deepcopy(world["deterministic_state"]["id_allocator"])
        before_inventory = {
            flight_id: flight["inventory_revision"]
            for flight_id, flight in world["world_state"]["dated_flights"].items()
        }
        before_finance = {
            airline_id: airline["finance_revision"]
            for airline_id, airline in world["world_state"]["airlines"].items()
        }
        result = run_shopping(world)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.requested_passengers, result.shoppable_passengers + result.terminal_unsuccessful_passengers)
        groups = offer_groups(result)
        deviations = {offer.date_deviation_days for group in groups for offer in group.offers}
        self.assertIn(-3, deviations)
        self.assertIn(3, deviations)
        self.assertTrue(all(-3 <= deviation <= 3 for deviation in deviations))
        groups_by_date = {
            group.desired_travel_date: group
            for group in result.market_plans[0].desired_date_groups
        }
        self.assertEqual(groups_by_date["2026-08-21"].disposition, SHOPPABLE)
        self.assertEqual(
            groups_by_date["2026-08-20"].disposition,
            NO_DEPARTURE_ON_DESIRED_DATE,
        )
        self.assertEqual(groups_by_date["2026-08-27"].disposition, SHOPPABLE)
        self.assertEqual(
            groups_by_date["2026-08-28"].disposition,
            NO_DEPARTURE_ON_DESIRED_DATE,
        )
        offer = groups[0].offers[0]
        self.assertEqual(offer.dated_flight_id, flight_id)
        self.assertEqual(offer.cabin, "ECONOMY")
        self.assertEqual(offer.journey_duration_seconds, 7200)
        self.assertEqual(offer.observed_inventory_revision, 0)
        self.assertEqual(world["world_state"]["booking_state"], before_booking)
        self.assertEqual(world["world_state"]["bookings"], before_bookings)
        self.assertEqual(world["world_state"]["itineraries"], before_itineraries)
        self.assertEqual(world["deterministic_state"]["id_allocator"], before_allocator)
        self.assertEqual(
            {flight_id: flight["inventory_revision"] for flight_id, flight in world["world_state"]["dated_flights"].items()},
            before_inventory,
        )
        self.assertEqual(
            {airline_id: airline["finance_revision"] for airline_id, airline in world["world_state"]["airlines"].items()},
            before_finance,
        )
        detached = deepcopy(result)
        world["world_state"]["dated_flights"][flight_id]["fare_offer"]["amount_minor"] += 1
        self.assertEqual(result, detached)

    def test_full_flight_remains_shoppable_and_inventory_is_not_an_filter(self):
        world, market_id, flight_id = schema3_world()
        resolution = resolve_daily_cohort(world, market_id, "2026-08-20")
        self.assertFalse(resolution.reused)
        state = world["world_state"]
        flight = world["world_state"]["dated_flights"][flight_id]
        airline_id = flight["airline_id"]
        passenger_count = flight["capacity"]
        total_fare = passenger_count * flight["fare_offer"]["amount_minor"]
        itinerary_id = allocate_id(world, "itinerary")
        booking_id = allocate_id(world, "booking")
        transaction_id = allocate_id(world, "transaction")
        checkpoint_id = allocate_id(world, "booking_checkpoint")
        account_ids = state["airlines"][airline_id]["financial_account_ids"]
        state["transactions"][transaction_id] = {
            "transaction_id": transaction_id,
            "airline_id": airline_id,
            "occurred_at_utc": world["simulation"]["time_utc"],
            "description": "Exact-capacity 5B shopping fixture",
            "entries": [
                {"account_id": account_ids[0], "amount_minor": total_fare},
                {"account_id": account_ids[3], "amount_minor": -total_fare},
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
            "demand_model_revision": state["demand_state"][
                "demand_model_revision"
            ],
            "market_pack_revision": pack["revision"],
            "market_results": {
                market_id: {
                    "market_id": market_id,
                    "cohort_key": f"{market_id}@2026-08-20",
                    "desired_passenger_count": passenger_count,
                    "booked_passenger_count": passenger_count,
                    "outside_option_passenger_count": 0,
                    "booking_ids": [booking_id],
                }
            },
            "financial_transaction_ids": [transaction_id],
        }
        self.assertTrue(validate_world(world).is_valid)
        before = deepcopy(world)
        result = run_shopping(world)
        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(offer_groups(result))
        self.assertTrue(all(group.disposition == SHOPPABLE for group in offer_groups(result)))
        self.assertEqual(world, before)

    def test_existing_current_marker_classifies_no_service_after_cancellation(self):
        world, market_id, flight_id = schema3_world()
        first = run_shopping(world)
        self.assertTrue(first.succeeded)
        world["world_state"]["dated_flights"][flight_id]["status"] = "CANCELLED"
        result = run_shopping(
            world, multipliers_by_market={market_id: {"world": 0}}
        )
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.reused_cohort_count, 1)
        self.assertEqual(result.requested_passengers, first.requested_passengers)
        self.assertEqual(result.market_plans[0].market_id, market_id)
        self.assertTrue(result.market_plans[0].desired_date_groups)
        self.assertEqual(
            {group.disposition for group in result.market_plans[0].desired_date_groups},
            {NO_ELIGIBLE_SERVICE},
        )

    def test_no_departure_on_desired_date_is_terminal_not_choice_failure(self):
        world, _market_id, _flight_id = schema3_world()
        result = run_shopping(world)
        dispositions = {
            group.disposition
            for group in result.market_plans[0].desired_date_groups
        }
        self.assertEqual(dispositions, {SHOPPABLE, NO_DEPARTURE_ON_DESIRED_DATE})
        self.assertNotIn("INSUFFICIENT_CAPACITY", dispositions)
        self.assertNotIn("OUTSIDE_OPTION", dispositions)
        self.assertNotIn("PRICE_REJECTION", dispositions)

    def test_future_airport_closing_is_exclusive_for_actual_travel(self):
        world, _market_id, flight_id = schema3_world()
        destination = world["world_state"]["dated_flights"][flight_id]["destination_airport_id"]
        revision = world["world_state"]["demand_state"]["demand_model_revision"]
        revised = revise_demand_model(
            world,
            expected_revision=revision,
            airport_updates={destination: {"active_until_date": "2026-08-24"}},
        )
        self.assertTrue(revised.succeeded, revised.issues)
        self.assertTrue(validate_world(world).is_valid)
        result = run_shopping(world)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(
            {group.disposition for group in result.market_plans[0].desired_date_groups},
            {NO_ELIGIBLE_SERVICE},
        )

    def test_airport_opening_is_inclusive_on_actual_travel_date(self):
        world, _market_id, flight_id = schema3_world()
        self.assertTrue(run_shopping(world).succeeded)
        destination = world["world_state"]["dated_flights"][flight_id]["destination_airport_id"]
        revision = world["world_state"]["demand_state"]["demand_model_revision"]
        revised = revise_demand_model(
            world,
            expected_revision=revision,
            airport_updates={destination: {"active_from_date": "2026-08-24"}},
        )
        self.assertTrue(revised.succeeded, revised.issues)
        result = run_shopping(world)
        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(offer_groups(result))

    def test_exact_current_timestamp_is_included_and_one_second_before_is_not(self):
        world, market_id, reference_flight_id = schema3_world()
        current_flight_id = self._add_current_timestamp_flight(
            world, market_id, reference_flight_id
        )
        at_boundary = run_shopping(world)
        self.assertTrue(at_boundary.succeeded, at_boundary.issues)
        offered_ids = {
            offer.dated_flight_id
            for group in offer_groups(at_boundary)
            for offer in group.offers
        }
        self.assertIn(current_flight_id, offered_ids)
        world["simulation"]["time_utc"] = "2026-08-20T00:00:01Z"
        after_boundary = run_shopping(world)
        self.assertTrue(after_boundary.succeeded, after_boundary.issues)
        offered_ids = {
            offer.dated_flight_id
            for group in offer_groups(after_boundary)
            for offer in group.offers
        }
        self.assertNotIn(current_flight_id, offered_ids)

    def test_booking_horizon_final_date_is_inclusive_and_next_date_is_not(self):
        world, _market_id, flight_id = schema3_world()

        def install_configuration(horizon):
            configuration = new_booking_configuration()
            configuration["booking_horizon_days"] = horizon
            configuration["lead_time_buckets"] = [
                {
                    "minimum_lead_days": 0,
                    "maximum_lead_days": horizon,
                    "weight_bps": 10_000,
                }
            ]
            configuration["configuration_fingerprint"] = (
                calculate_booking_configuration_fingerprint(configuration)
            )
            world["simulation"]["configuration"]["booking"] = configuration

        install_configuration(4)
        self.assertTrue(validate_world(world).is_valid)
        at_final_date = run_shopping(world)
        self.assertTrue(at_final_date.succeeded, at_final_date.issues)
        self.assertIn(
            flight_id,
            {
                offer.dated_flight_id
                for group in offer_groups(at_final_date)
                for offer in group.offers
            },
        )

        install_configuration(3)
        self.assertTrue(validate_world(world).is_valid)
        after_horizon = run_shopping(world)
        self.assertTrue(after_horizon.succeeded, after_horizon.issues)
        self.assertFalse(offer_groups(after_horizon))
        self.assertEqual(
            {
                group.disposition
                for group in after_horizon.market_plans[0].desired_date_groups
            },
            {NO_ELIGIBLE_SERVICE},
        )

    def test_locked_retained_plan_is_eligible_but_retired_planned_is_not(self):
        locked, _market_id, flight_id = schema3_world()
        flight = locked["world_state"]["dated_flights"][flight_id]
        schedule = locked["world_state"]["schedule_definitions"][flight["schedule_id"]]
        flight["status"] = "OPERATIONALLY_LOCKED"
        schedule["status"] = "RETIRED"
        self.assertTrue(validate_world(locked).is_valid)
        self.assertTrue(offer_groups(run_shopping(locked)))

        planned, _market_id, flight_id = schema3_world()
        self.assertTrue(run_shopping(planned).succeeded)
        flight = planned["world_state"]["dated_flights"][flight_id]
        planned["world_state"]["schedule_definitions"][flight["schedule_id"]]["status"] = "RETIRED"
        result = run_shopping(planned)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(
            {group.disposition for group in result.market_plans[0].desired_date_groups},
            {NO_ELIGIBLE_SERVICE},
        )

    def test_locked_historical_revision_is_traceable_and_forgery_rejects(self):
        world, _market_id, flight_id = schema3_world()
        flight = world["world_state"]["dated_flights"][flight_id]
        flight["status"] = "OPERATIONALLY_LOCKED"
        schedule = world["world_state"]["schedule_definitions"][
            flight["schedule_id"]
        ]
        retained = schedule["revisions"]["1"]
        retained["effective_until_local_date"] = "2026-08-24"
        current = deepcopy(retained)
        current["revision"] = 2
        current["effective_from_local_date"] = "2026-08-25"
        current["effective_until_local_date"] = None
        schedule["revisions"]["2"] = current
        schedule["current_revision"] = 2
        world["simulation"]["operation_revisions"][flight["schedule_id"]] = 2
        self.assertTrue(validate_world(world).is_valid)

        valid = run_shopping(world)

        self.assertTrue(valid.succeeded, valid.issues)
        offered = [
            offer
            for group in offer_groups(valid)
            for offer in group.offers
            if offer.dated_flight_id == flight_id
        ]
        self.assertTrue(offered)
        self.assertEqual(offered[0].schedule_lineage.schedule_revision, 1)

        forged = deepcopy(world)
        forged_flight = forged["world_state"]["dated_flights"][flight_id]
        forged_flight["occurrence_key"] = "schedule-forged@2026-08-24"
        before = deepcopy(forged)
        rejected = run_shopping(forged)
        self.assertFalse(rejected.succeeded)
        self.assertEqual(forged, before)

    def test_zero_intent_active_market_has_empty_conserved_plan(self):
        world, market_id, _flight_id = schema3_world()
        result = run_shopping(
            world, multipliers_by_market={market_id: {"world": 0}}
        )
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.requested_passengers, 0)
        self.assertEqual(result.shoppable_passengers, 0)
        self.assertEqual(result.terminal_unsuccessful_passengers, 0)
        self.assertEqual(result.market_plans[0].desired_date_groups, ())

    def test_mixed_currency_rejects_atomically_after_cohort_derivation(self):
        world, market_id, flight_id = schema3_world()
        flight = world["world_state"]["dated_flights"][flight_id]
        origin = flight["origin_airport_id"]
        destination = flight["destination_airport_id"]
        airline_id = add_airline(world, "Peso Air", base_airport_id=origin, currency="PHP")
        connection_id = add_connection(world, airline_id, market_id, status="ACTIVE")
        aircraft_id = add_aircraft(world, airline_id, "RP-PHP1", "A320", home_airport_id=origin)
        schedule = create_schedule_definition(
            world,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=origin,
            destination_airport_id=destination,
            weekdays=[0],
            departure_local_time="09:00:00",
            arrival_local_time="11:00:00",
            effective_from_local_date="2026-08-24",
            capacity=100,
            fare_offer={"currency": "PHP", "amount_minor": 5_000},
        )
        self.assertTrue(schedule.succeeded)
        self.assertTrue(publish_occurrences_through(world, "2026-08-24T02:00:00Z").succeeded)
        before = deepcopy(world)
        result = run_shopping(world)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "UNSUPPORTED_FARE_CURRENCY")
        self.assertEqual(world, before)
        self.assertNotIn(f"{market_id}@2026-08-20", world["world_state"]["demand_state"]["processed_cohorts"])

    def test_malformed_fare_currency_is_not_classified_as_competition(self):
        world, _market_id, flight_id = schema3_world()
        flight = world["world_state"]["dated_flights"][flight_id]
        revision = world["world_state"]["schedule_definitions"][
            flight["schedule_id"]
        ]["revisions"][str(flight["schedule_revision"])]
        flight["fare_offer"]["currency"] = "PHP"
        revision["fare_offer"]["currency"] = "PHP"
        before = deepcopy(world)

        result = run_shopping(world)

        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "INVALID_FARE")
        self.assertNotEqual(result.issues[0].code, "UNSUPPORTED_FARE_CURRENCY")
        self.assertEqual(world, before)

    def test_different_currencies_without_group_competition_are_supported(self):
        world, market_id, flight_id = schema3_world()
        reference = world["world_state"]["dated_flights"][flight_id]
        origin = reference["origin_airport_id"]
        destination = reference["destination_airport_id"]
        reference["status"] = "OPERATIONALLY_LOCKED"
        world["world_state"]["schedule_definitions"][reference["schedule_id"]][
            "status"
        ] = "RETIRED"
        airline_id = add_airline(
            world, "Later Peso Air", base_airport_id=origin, currency="PHP"
        )
        connection_id = add_connection(
            world, airline_id, market_id, status="ACTIVE"
        )
        aircraft_id = add_aircraft(
            world,
            airline_id,
            "RP-LATE",
            "A320",
            home_airport_id=origin,
        )
        schedule = create_schedule_definition(
            world,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=origin,
            destination_airport_id=destination,
            weekdays=[0],
            departure_local_time="09:00:00",
            arrival_local_time="11:00:00",
            effective_from_local_date="2026-09-07",
            capacity=100,
            fare_offer={"currency": "PHP", "amount_minor": 5_000},
        )
        self.assertTrue(schedule.succeeded, schedule.conflicts)
        published = publish_occurrences_through(world, "2026-09-07T02:00:00Z")
        self.assertTrue(published.succeeded, published.conflicts)

        result = run_shopping(world)

        self.assertTrue(result.succeeded, result.issues)
        observed_currencies = {
            offer.fare_snapshot.currency
            for group in offer_groups(result)
            for offer in group.offers
        }
        self.assertEqual(observed_currencies, {"USD", "PHP"})
        self.assertTrue(
            all(
                len({offer.fare_snapshot.currency for offer in group.offers}) == 1
                for group in offer_groups(result)
            )
        )

    def test_stale_indexes_cannot_hide_or_resurrect_service(self):
        world, _market_id, flight_id = schema3_world()
        authoritative = rebuild_dated_flight_indexes(world)
        empty = DatedFlightIndexes({}, {}, {}, {}, {}, {}, {})
        visible = run_shopping(world, dated_flight_indexes=empty)
        self.assertTrue(visible.succeeded, visible.issues)
        self.assertTrue(offer_groups(visible))
        world["world_state"]["dated_flights"][flight_id]["status"] = "CANCELLED"
        resurrected = run_shopping(world, dated_flight_indexes=authoritative)
        self.assertTrue(resurrected.succeeded, resurrected.issues)
        self.assertFalse(offer_groups(resurrected))

    def test_forged_index_equality_cannot_hide_authoritative_service(self):
        world, _market_id, _flight_id = schema3_world()

        class ForgedIndex:
            direct_services_by_market = {}

            def __eq__(self, _other):
                return True

        result = run_shopping(world, dated_flight_indexes=ForgedIndex())

        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(offer_groups(result))

    def test_noniterable_provider_container_rejects_without_mutation(self):
        world, _market_id, _flight_id = schema3_world()
        before = deepcopy(world)

        result = run_shopping(world, activation_providers=True)

        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "UNAVAILABLE_BOOKING_MARKET")
        self.assertEqual(world, before)

        class UnprintableError(Exception):
            def __str__(self):
                raise RuntimeError("string conversion failed")

        class HostileProviderCollection:
            def __iter__(self):
                raise UnprintableError()

        hostile = run_shopping(
            world, activation_providers=HostileProviderCollection()
        )
        self.assertFalse(hostile.succeeded)
        self.assertEqual(
            hostile.issues[0].code, "UNAVAILABLE_BOOKING_MARKET"
        )
        self.assertEqual(world, before)

    def test_stale_revisions_and_provider_failures_leave_source_unchanged(self):
        world, market_id, _flight_id = schema3_world()
        before = deepcopy(world)
        stale = run_shopping(world, expected_demand_revision=-1)
        self.assertEqual(stale.status, "STALE_REVISION")
        self.assertEqual(world, before)

        class MutatingProvider:
            def active_market_ids(self, envelope, _window, **_kwargs):
                envelope["ui_state"]["current_focus"] = None
                return (market_id,)

        mutated = run_shopping(world, activation_providers=(MutatingProvider(),))
        self.assertFalse(mutated.succeeded)
        self.assertEqual(mutated.issues[0].code, "UNAVAILABLE_BOOKING_MARKET")
        self.assertEqual(world, before)

        class RaisingProvider:
            def active_market_ids(self, *_args, **_kwargs):
                raise RuntimeError("provider failure")

        raised = run_shopping(world, activation_providers=(RaisingProvider(),))
        self.assertFalse(raised.succeeded)
        self.assertEqual(world, before)

        class UnknownProvider:
            def active_market_ids(self, *_args, **_kwargs):
                return ("market-999999999999",)

        unknown = run_shopping(world, activation_providers=(UnknownProvider(),))
        self.assertFalse(unknown.succeeded)
        self.assertEqual(unknown.issues[0].code, "UNAVAILABLE_BOOKING_MARKET")
        self.assertEqual(world, before)

        class DuplicateProvider:
            def active_market_ids(self, *_args, **_kwargs):
                return (market_id, market_id)

        duplicate = run_shopping(world, activation_providers=(DuplicateProvider(),))
        self.assertFalse(duplicate.succeeded)
        self.assertEqual(world, before)

    def test_result_and_authority_are_insertion_order_independent(self):
        left, _market_id, _flight_id = schema3_world()
        right = deepcopy(left)
        for collection in ("airlines", "dated_flights", "connections", "schedule_definitions"):
            values = right["world_state"][collection]
            right["world_state"][collection] = dict(reversed(tuple(values.items())))
        left_result = run_shopping(left)
        right_result = run_shopping(right)
        self.assertEqual(left_result, right_result)
        self.assertEqual(left, right)

    def test_model4_creates_v2_only_through_prospective_active_path(self):
        source, ids, _old = model4_world()
        indexes = source["world_state"]["directional_markets"]
        market_id = next(
            market_id
            for market_id, market in indexes.items()
            if market["origin_airport_id"] == ids["MNL"]
            and market["destination_airport_id"] == ids["DVO"]
        )
        airline_id = source["world_state"]["player"]["primary_airline_id"]
        connection_id = add_connection(source, airline_id, market_id, status="ACTIVE")
        aircraft_id = add_aircraft(source, airline_id, "RP-M4B1", "A320", home_airport_id=ids["MNL"])
        schedule = create_schedule_definition(
            source,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=ids["MNL"],
            destination_airport_id=ids["DVO"],
            weekdays=[0],
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            effective_from_local_date="2026-08-24",
            capacity=180,
            fare_offer={"currency": "USD", "amount_minor": 10_000},
        )
        self.assertTrue(schedule.succeeded)
        self.assertTrue(publish_occurrences_through(source, "2026-08-24T00:00:00Z").succeeded)
        migration = migrate_schema_2_to_3(source)
        self.assertTrue(migration.succeeded, migration.issues)
        world = migration.migrated_world
        result = run_shopping(world)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.market_plans[0].cohort_contract, MODEL4_TRAVEL_SCOPE_COHORT_V1)
        self.assertEqual(result.created_cohort_count, 1)

    def test_model4_reuses_current_date_v1_compatibility_marker(self):
        source, ids, old = model4_world(model3_marker=True)
        market_id = old["payload"]["market_id"]
        airline_id = source["world_state"]["player"]["primary_airline_id"]
        connection_id = add_connection(source, airline_id, market_id, status="ACTIVE")
        aircraft_id = add_aircraft(source, airline_id, "RP-M4V1", "A320", home_airport_id=ids["MNL"])
        schedule = create_schedule_definition(
            source,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=ids["MNL"],
            destination_airport_id=ids["DVO"],
            weekdays=[0],
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            effective_from_local_date="2026-08-24",
            capacity=180,
            fare_offer={"currency": "USD", "amount_minor": 10_000},
        )
        self.assertTrue(schedule.succeeded)
        self.assertTrue(publish_occurrences_through(source, "2026-08-24T00:00:00Z").succeeded)
        migration = migrate_schema_2_to_3(source)
        self.assertTrue(migration.succeeded, migration.issues)
        world = migration.migrated_world
        result = run_shopping(world)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.created_cohort_count, 0)
        self.assertEqual(result.reused_cohort_count, 1)
        self.assertEqual(result.market_plans[0].cohort_contract, MODEL3_PROCESSED_COHORT_V1)

    def test_disabled_destination_creates_no_intent_and_future_disable_is_not_early(self):
        source, ids, country_id, materialized = materialized_world()
        source["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id = next(
            market_id
            for market_id, market in source["world_state"]["directional_markets"].items()
            if market["origin_airport_id"] == ids["MNL"]
            and market["destination_airport_id"] == ids["HAN"]
        )
        airline_id = source["world_state"]["player"]["primary_airline_id"]
        connection_id = add_connection(source, airline_id, market_id, status="ACTIVE")
        aircraft_id = add_aircraft(source, airline_id, "RP-PACK1", "A320", home_airport_id=ids["MNL"])
        schedule = create_schedule_definition(
            source,
            airline_id=airline_id,
            connection_id=connection_id,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=ids["MNL"],
            destination_airport_id=ids["HAN"],
            weekdays=[0],
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            effective_from_local_date="2026-08-24",
            capacity=180,
            fare_offer={"currency": "USD", "amount_minor": 10_000},
        )
        self.assertTrue(schedule.succeeded)
        self.assertTrue(publish_occurrences_through(source, "2026-08-24T01:00:00Z").succeeded)

        disabled_source = deepcopy(source)
        disabled = disable_country_pack(
            disabled_source,
            country_id,
            expected_pack_revision=materialized.pack_revision,
        )
        self.assertTrue(disabled.succeeded, disabled.issues)
        migration = migrate_schema_2_to_3(disabled_source)
        self.assertTrue(migration.succeeded, migration.issues)
        disabled_world = migration.migrated_world
        inactive = run_shopping(disabled_world)
        self.assertTrue(inactive.succeeded, inactive.issues)
        self.assertEqual(inactive.market_plans, ())
        self.assertNotIn(f"{market_id}@2026-08-24", disabled_world["world_state"]["demand_state"]["processed_cohorts"])

        future_source = deepcopy(source)
        future = disable_country_pack(
            future_source,
            country_id,
            expected_pack_revision=materialized.pack_revision,
            status_effective_date="2026-08-25",
        )
        self.assertTrue(future.succeeded, future.issues)
        migration = migrate_schema_2_to_3(future_source)
        self.assertTrue(migration.succeeded, migration.issues)
        future_world = migration.migrated_world
        active = run_shopping(future_world)
        self.assertTrue(active.succeeded, active.issues)
        self.assertEqual(active.created_cohort_count, 1)
        self.assertTrue(offer_groups(active))

    def test_current_day_activation_uses_simulation_date_not_v1_universe_date(self):
        world, market_id, flight_id = schema3_world()
        destination = world["world_state"]["dated_flights"][flight_id][
            "destination_airport_id"
        ]
        revision = world["world_state"]["demand_state"]["demand_model_revision"]
        revised = revise_demand_model(
            world,
            expected_revision=revision,
            airport_updates={destination: {"active_until_date": "2026-08-21"}},
        )
        self.assertTrue(revised.succeeded, revised.issues)
        world["simulation"]["time_utc"] = "2026-08-21T00:00:00Z"
        self.assertTrue(validate_world(world).is_valid)

        result = run_shopping(world)

        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.market_plans, ())
        self.assertNotIn(
            f"{market_id}@2026-08-21",
            world["world_state"]["demand_state"]["processed_cohorts"],
        )

    def test_runtime_index_is_detached_and_reports_single_candidate_pass(self):
        world, _market_id, flight_id = schema3_world()
        indexes = rebuild_direct_flight_shopping_indexes(world)
        self.assertEqual(indexes.indexed_flight_count, 1)
        self.assertIn(flight_id, indexes.by_dated_flight_id)
        before = indexes.by_dated_flight_id[flight_id]
        world["world_state"]["dated_flights"][flight_id]["fare_offer"]["amount_minor"] += 1
        self.assertEqual(indexes.by_dated_flight_id[flight_id], before)


if __name__ == "__main__":
    unittest.main()
