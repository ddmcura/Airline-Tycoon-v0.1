"""Milestone 4 authoritative world-demand tests."""

from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import random
from time import perf_counter
import unittest
from unittest.mock import patch

import game.demand.model as demand_model
from game.demand import (
    calculate_origin_daily_booking_pool,
    calculate_raw_pair_score,
    calculate_world_demand,
    compose_daily_multipliers,
    eligible_airport_ids,
    get_base_daily_bookers,
    rebuild_demand_indexes,
    recalculate_origin_demand,
    resolve_daily_cohort,
    resolve_world_daily_cohorts,
    revise_demand_model,
)
from game.economy.demand import calculate_directional_base_demand
from game.scheduling import create_schedule_definition, publish_occurrences_through
from game.world_state import (
    add_aircraft,
    add_airport_reference,
    add_connection,
    create_new_world,
    validate_world,
)
from game.world_state.demand_fingerprint import calculate_demand_input_fingerprint


AIRPORTS = {
    "MNL": {
        "population": 13_500_000,
        "coordinates": {"lat": 14.5086, "lon": 121.0198},
        "destination_type": "MEGA_GLOBAL_CITY",
        "opened": "1948-07-01",
    },
    "DVO": {
        "population": 1_230_000,
        "coordinates": {"lat": 7.1250, "lon": 125.6450},
        "destination_type": "CAPITAL_MAJOR_CITY",
        "opened": "1958-03-01",
    },
    "CEB": {
        "population": 1_000_000,
        "coordinates": {"lat": 10.3070, "lon": 123.9810},
        "destination_type": "CAPITAL_MAJOR_CITY",
        "opened": "1990-04-01",
    },
    "PPS": {
        "population": 307_000,
        "coordinates": {"lat": 9.7421, "lon": 118.7587},
        "destination_type": "NORMAL_CITY",
        "opened": "1950-01-01",
    },
}


def airport_reference(code, *, country="PH", **overrides):
    source = {**AIRPORTS.get(code, {}), **overrides}
    return {
        "reference_code": code,
        "iata": code if len(code) == 3 else None,
        "display_name": f"{code} Airport",
        "timezone": "Asia/Manila" if country == "PH" else "UTC",
        "population": source.get("population"),
        "coordinates": source.get("coordinates"),
        "country_reference": country,
        "demand_destination_type": source.get("destination_type"),
        "date_opened": source.get("opened"),
        "date_closed": source.get("closed"),
        "passenger_demand_eligible": source.get("eligible", True),
    }


def make_demand_world(codes=("MNL", "DVO", "CEB", "PPS"), *, seed=314159):
    world = create_new_world(
        ceo_display_name="Avery Chen",
        airline_display_name="Meridian Air",
        starting_airport=airport_reference(codes[0]),
        difficulty="Normal",
        simulation_time_utc="2026-08-20T00:00:00Z",
        simulation_seed=seed,
        starting_money="1000000.00",
    )
    ids = {codes[0]: next(iter(world["world_state"]["airports"]))}
    for code in codes[1:]:
        ids[code] = add_airport_reference(world, airport_reference(code))
    return world, ids


def issue_codes(world):
    return {issue.code for issue in validate_world(world).errors}


class Stage1DemandFormulaTests(unittest.TestCase):
    def test_directional_baselines_and_reverse_directions_are_independent(self):
        world, ids = make_demand_world()
        result = calculate_world_demand(world)

        outbound = result.indexes.pair(ids["MNL"], ids["DVO"])
        inbound = result.indexes.pair(ids["DVO"], ids["MNL"])

        self.assertNotEqual(outbound.base_daily_bookers, inbound.base_daily_bookers)
        self.assertNotEqual(
            outbound.destination_pair_share, inbound.destination_pair_share
        )

    def test_origin_pool_uses_population_and_configured_model3_rate(self):
        world, ids = make_demand_world()

        pool = calculate_origin_daily_booking_pool(world, ids["MNL"])

        self.assertEqual(pool, Decimal("54000"))

    def test_raw_pair_score_uses_approved_model3_factors(self):
        world, ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        pair = indexes.pair(ids["MNL"], ids["DVO"])
        expected = (
            (Decimal("1.23").sqrt())
            * (Decimal(1) / (Decimal(1) + pair.distance_km / Decimal(2000)))
            * Decimal("1.25")
            * Decimal("1.25")
            * Decimal("1.0")
        )

        self.assertAlmostEqual(
            calculate_raw_pair_score(world, ids["MNL"], ids["DVO"]),
            expected,
            places=25,
        )

    def test_every_origin_normalizes_across_complete_unserved_universe(self):
        world, ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes

        for origin_id in indexes.eligible_airport_ids:
            shares = [
                indexes.by_market[market_id].destination_pair_share
                for market_id in indexes.markets_by_origin[origin_id]
            ]
            self.assertEqual(sum(shares, Decimal(0)), Decimal(1))
        self.assertIsNotNone(indexes.pair(ids["MNL"], ids["PPS"]))
        self.assertEqual(world["world_state"]["connections"], {})

    def test_same_airport_pairs_are_absent(self):
        world, _ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes

        self.assertTrue(
            all(origin != destination for origin, destination in indexes.market_by_pair)
        )

    def test_legacy_102_is_characterized_but_not_authoritative_normalization(self):
        self.assertEqual(calculate_directional_base_demand(1_230_000, 1_000_000, 400), 102)
        world, ids = make_demand_world(("DVO", "CEB"))

        authoritative = get_base_daily_bookers(world, ids["DVO"], ids["CEB"])

        self.assertEqual(authoritative, Decimal("4920"))

    def test_missing_reference_inputs_are_explicitly_ineligible(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        incomplete = add_airport_reference(world, "BAD")

        self.assertNotIn(incomplete, eligible_airport_ids(world))
        self.assertTrue(validate_world(world).is_valid)

    def test_explicitly_eligible_missing_coordinates_or_population_is_rejected(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        before = deepcopy(world)

        with self.assertRaises(ValueError):
            add_airport_reference(
                world,
                {
                    "reference_code": "BAD",
                    "population": 1_000_000,
                    "country_reference": "PH",
                    "demand_destination_type": "NORMAL_CITY",
                    "passenger_demand_eligible": True,
                },
            )

        self.assertEqual(world, before)

    def test_not_yet_open_and_permanently_closed_airports_are_excluded(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        future = add_airport_reference(
            world,
            airport_reference(
                "FUT",
                population=500_000,
                coordinates={"lat": 12, "lon": 120},
                destination_type="NORMAL_CITY",
                opened="2030-01-01",
            ),
        )
        closed = add_airport_reference(
            world,
            airport_reference(
                "OLD",
                population=500_000,
                coordinates={"lat": 11, "lon": 120},
                destination_type="NORMAL_CITY",
                opened="1950-01-01",
                closed="2020-01-01",
            ),
        )

        indexes = calculate_world_demand(world).indexes

        self.assertNotIn(future, indexes.eligible_airport_ids)
        self.assertNotIn(closed, indexes.eligible_airport_ids)
        self.assertIsNotNone(indexes.pair(ids["MNL"], ids["DVO"]))

    def test_historical_boundary_changes_only_through_explicit_revision(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        future = add_airport_reference(
            world,
            airport_reference(
                "FUT",
                population=500_000,
                coordinates={"lat": 12, "lon": 120},
                destination_type="NORMAL_CITY",
                opened="2030-01-01",
            ),
        )
        before = calculate_world_demand(world).indexes

        revised = revise_demand_model(world, universe_date="2030-01-01")
        after = calculate_world_demand(world, indexes=before).indexes

        self.assertTrue(revised.succeeded)
        self.assertNotIn(future, before.eligible_airport_ids)
        self.assertIn(future, after.eligible_airport_ids)


class Stage1DemandIsolationTests(unittest.TestCase):
    def test_opening_and_closing_airline_service_do_not_change_baseline(self):
        world, ids = make_demand_world()
        first = calculate_world_demand(world).indexes
        market_id = first.market_by_pair[(ids["MNL"], ids["DVO"])]
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        before = first.by_market[market_id].base_daily_bookers

        connection_id = add_connection(world, airline_id, market_id, status="ACTIVE")
        opened = calculate_world_demand(world).indexes.by_market[market_id].base_daily_bookers
        world["world_state"]["connections"][connection_id]["status"] = "CLOSED"
        closed = calculate_world_demand(world).indexes.by_market[market_id].base_daily_bookers

        self.assertEqual((before, opened, closed), (before, before, before))

    def test_publishing_dated_flights_does_not_change_baseline(self):
        world, ids = make_demand_world()
        demand = calculate_world_demand(world).indexes
        market_id = demand.market_by_pair[(ids["MNL"], ids["DVO"])]
        baseline = demand.by_market[market_id].base_daily_bookers
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        connection_id = add_connection(world, airline_id, market_id, status="ACTIVE")
        aircraft_id = add_aircraft(
            world,
            airline_id,
            "RP-C4001",
            "A320",
            home_airport_id=ids["MNL"],
        )
        schedule = create_schedule_definition(
            world,
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
        self.assertTrue(schedule.succeeded, schedule.conflicts)

        publication = publish_occurrences_through(world, "2026-08-24T00:00:00Z")
        after = calculate_world_demand(world).indexes.by_market[
            market_id
        ].base_daily_bookers

        self.assertTrue(publication.succeeded, publication.conflicts)
        self.assertEqual(after, baseline)

    def test_no_route_owned_demand_becomes_authority(self):
        world, ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        connection_id = add_connection(world, airline_id, market_id, status="ACTIVE")

        self.assertNotIn("base_daily_demand", world["world_state"]["connections"][connection_id])
        self.assertNotIn("market_demand", world["world_state"]["demand_state"])

    def test_demand_does_not_call_booking_scheduling_finance_or_legacy_tick(self):
        world, _ids = make_demand_world()
        with patch(
            "game.simulation.daily_tick.simulate_airline_day",
            side_effect=AssertionError("legacy tick called"),
        ), patch(
            "game.scheduling.rebuild_dated_flight_indexes",
            side_effect=AssertionError("schedule scanned"),
        ):
            result = calculate_world_demand(world)
            cohorts = resolve_world_daily_cohorts(
                world, "2026-08-20", indexes=result.indexes
            )

        self.assertTrue(result.succeeded)
        self.assertTrue(cohorts.succeeded)


class Stage1DailyDemandTests(unittest.TestCase):
    def test_daily_modifiers_change_actual_not_baseline_and_detach_input(self):
        world, ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        baseline = indexes.by_market[market_id].base_daily_bookers
        modifiers = {"holiday": 15_000, "world": 8_000}

        cohort = resolve_daily_cohort(
            world,
            market_id,
            "2026-08-20",
            multipliers=modifiers,
            indexes=indexes,
        )
        modifiers["holiday"] = 0
        stored = world["world_state"]["demand_state"]["processed_cohorts"][
            f"{market_id}@2026-08-20"
        ]

        self.assertIn(cohort.actual_daily_bookers, {int(baseline * Decimal("1.2")), int(baseline * Decimal("1.2")) + 1})
        self.assertEqual(indexes.by_market[market_id].base_daily_bookers, baseline)
        self.assertEqual(stored["daily_multipliers_bps"]["holiday"], 15_000)

    def test_neutral_modifiers_preserve_integral_baseline_result(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]

        cohort = resolve_daily_cohort(
            world, market_id, "2026-08-20", multipliers={}, indexes=indexes
        )

        self.assertEqual(indexes.by_market[market_id].base_daily_bookers, 54_000)
        self.assertEqual(cohort.actual_daily_bookers, 54_000)

    def test_invalid_negative_float_and_unknown_modifiers_are_rejected_atomically(self):
        for modifiers in (
            {"holiday": -1},
            {"holiday": 1.5},
            {"price": 10_000},
            [],
        ):
            with self.subTest(modifiers=modifiers):
                world, ids = make_demand_world(("MNL", "DVO"))
                indexes = calculate_world_demand(world).indexes
                market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
                before = deepcopy(world)
                with self.assertRaises(ValueError):
                    resolve_daily_cohort(
                        world,
                        market_id,
                        "2026-08-20",
                        multipliers=modifiers,
                        indexes=indexes,
                    )
                self.assertEqual(world, before)

    def test_tiny_fractional_market_preserves_long_run_expectation(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        revision = revise_demand_model(
            world,
            configuration_updates={
                "configuration_version": "tiny-market-test-v1",
                "daily_booker_rate_ppm": 1,
            },
            airport_updates={ids["MNL"]: {"population": 100_000}},
        )
        self.assertTrue(revision.succeeded, revision.issues)
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        total = 0
        for day_number in range(1, 366):
            month = ((day_number - 1) // 28) + 1
            day = ((day_number - 1) % 28) + 1
            year = 2026 + ((month - 1) // 12)
            month = ((month - 1) % 12) + 1
            total += resolve_daily_cohort(
                world,
                market_id,
                f"{year:04d}-{month:02d}-{day:02d}",
                indexes=indexes,
            ).actual_daily_bookers

        self.assertEqual(total, 31)
        self.assertEqual(indexes.by_market[market_id].base_daily_bookers, Decimal("0.1"))

    def test_reprocessing_same_pair_date_is_idempotent_and_reload_equivalent(self):
        world, ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        first = resolve_daily_cohort(world, market_id, "2026-08-20", indexes=indexes)
        restored = deepcopy(world)

        repeated = resolve_daily_cohort(
            world, market_id, "2026-08-20", multipliers={"holiday": 0}, indexes=indexes
        )
        reloaded = resolve_daily_cohort(
            restored, market_id, "2026-08-20", indexes=indexes
        )

        self.assertFalse(first.reused)
        self.assertTrue(repeated.reused)
        self.assertTrue(reloaded.reused)
        self.assertEqual(first.actual_daily_bookers, repeated.actual_daily_bookers)
        self.assertEqual(world, restored)

    def test_processing_order_does_not_change_cohorts(self):
        world, _ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        forward = deepcopy(world)
        reverse = deepcopy(world)

        for market_id in sorted(indexes.by_market):
            resolve_daily_cohort(forward, market_id, "2026-08-20", indexes=indexes)
        for market_id in reversed(sorted(indexes.by_market)):
            resolve_daily_cohort(reverse, market_id, "2026-08-20", indexes=indexes)

        forward_records = forward["world_state"]["demand_state"]["processed_cohorts"]
        reverse_records = reverse["world_state"]["demand_state"]["processed_cohorts"]
        self.assertEqual(forward_records, reverse_records)

    def test_zero_cohort_invokes_no_later_booking_behavior(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        with patch(
            "game.simulation.daily_tick.simulate_airline_day",
            side_effect=AssertionError("booking behavior called"),
        ):
            cohort = resolve_daily_cohort(
                world,
                market_id,
                "2026-08-20",
                multipliers={"world": 0},
                indexes=indexes,
            )

        self.assertEqual(cohort.actual_daily_bookers, 0)
        self.assertEqual(world["world_state"]["bookings"], {})
        self.assertEqual(world["world_state"]["itineraries"], {})

    def test_each_date_is_a_new_cohort_without_carry_forward(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]

        first = resolve_daily_cohort(world, market_id, "2026-08-20", indexes=indexes)
        second = resolve_daily_cohort(world, market_id, "2026-08-21", indexes=indexes)

        self.assertEqual(first.actual_daily_bookers, second.actual_daily_bookers)
        self.assertEqual(
            len(world["world_state"]["demand_state"]["processed_cohorts"]), 2
        )

    def test_world_resolution_rejects_malformed_market_modifiers_atomically(self):
        world, _ids = make_demand_world()
        before = deepcopy(world)

        result = resolve_world_daily_cohorts(
            world,
            "2026-08-20",
            multipliers_by_market={"missing-market": {"holiday": 12_000}},
        )

        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)


class Stage1DemandRevisionValidationTests(unittest.TestCase):
    def test_same_inputs_and_dictionary_reordering_produce_identical_derivation(self):
        world, _ids = make_demand_world()
        first = calculate_world_demand(world).indexes
        reordered = deepcopy(world)
        reordered["world_state"]["airports"] = dict(
            reversed(list(reordered["world_state"]["airports"].items()))
        )
        reordered["world_state"]["directional_markets"] = dict(
            reversed(list(reordered["world_state"]["directional_markets"].items()))
        )

        second = rebuild_demand_indexes(reordered)

        self.assertEqual(first.by_market, second.by_market)
        self.assertEqual(first.market_by_pair, second.market_by_pair)

    def test_cache_reuse_and_revision_invalidation_affect_only_derived_state(self):
        world, ids = make_demand_world()
        first = calculate_world_demand(world)
        reused = calculate_world_demand(world, indexes=first.indexes)
        market_id = first.indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        resolve_daily_cohort(world, market_id, "2026-08-20", indexes=first.indexes)
        processed_before = deepcopy(
            world["world_state"]["demand_state"]["processed_cohorts"]
        )

        revised = revise_demand_model(
            world,
            configuration_updates={
                "configuration_version": "rate-change-v1",
                "daily_booker_rate_ppm": 3_000,
            },
            expected_revision=first.indexes.model_revision,
        )
        rebuilt = calculate_world_demand(world, indexes=first.indexes)

        self.assertTrue(reused.cache_reused)
        self.assertTrue(revised.succeeded)
        self.assertFalse(rebuilt.cache_reused)
        self.assertEqual(
            world["world_state"]["demand_state"]["processed_cohorts"],
            processed_before,
        )
        self.assertNotEqual(
            rebuilt.indexes.by_market[market_id].base_daily_bookers,
            first.indexes.by_market[market_id].base_daily_bookers,
        )

    def test_revision_failure_is_mutation_free_and_inputs_are_detached(self):
        world, ids = make_demand_world()
        before = deepcopy(world)
        invalid = revise_demand_model(
            world,
            airport_updates={ids["MNL"]: {"population": -1}},
        )
        self.assertFalse(invalid.succeeded)
        self.assertEqual(world, before)

        weights = deepcopy(
            world["simulation"]["configuration"]["demand"][
                "destination_type_weight_bps"
            ]
        )
        result = revise_demand_model(
            world,
            configuration_updates={
                "configuration_version": "detached-v1",
                "destination_type_weight_bps": weights,
            },
        )
        weights["MEGA_GLOBAL_CITY"] = 1
        self.assertTrue(result.succeeded)
        self.assertEqual(
            world["simulation"]["configuration"]["demand"][
                "destination_type_weight_bps"
            ]["MEGA_GLOBAL_CITY"],
            14_000,
        )

    def test_failure_during_recalculation_does_not_partially_create_markets(self):
        world, _ids = make_demand_world()
        world["simulation"]["configuration"]["demand"]["distance_scale_km"] = 0
        before = deepcopy(world)

        result = calculate_world_demand(world)

        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)

    def test_derived_cache_persistence_unknown_fields_and_revision_mismatch_rejected(self):
        world, _ids = make_demand_world()
        world["world_state"]["demand_state"]["base_daily_bookers"] = {}
        self.assertIn("derived_demand_cache_persisted", issue_codes(world))

        world, _ids = make_demand_world()
        world["world_state"]["demand_state"]["demand_model_revision"] += 1
        self.assertIn("inconsistent_demand_revision", issue_codes(world))

        world, _ids = make_demand_world()
        airport = next(iter(world["world_state"]["airports"].values()))
        airport["runtime_demand_index"] = 1
        self.assertIn("unknown_authoritative_field", issue_codes(world))

        world, _ids = make_demand_world()
        airport = next(iter(world["world_state"]["airports"].values()))
        airport["population"] += 1
        self.assertIn("inconsistent_demand_revision", issue_codes(world))

    def test_malformed_demand_structures_return_validation_errors_without_crashing(self):
        mutations = (
            lambda world: world["simulation"]["configuration"]["demand"].update(
                destination_type_weight_bps=[]
            ),
            lambda world: world["world_state"]["demand_state"].update(
                processed_cohorts=[]
            ),
            lambda world: world["world_state"]["demand_state"].update(
                rounding_policy=[]
            ),
        )
        for mutate in mutations:
            world, _ids = make_demand_world()
            mutate(world)
            result = validate_world(world)
            self.assertFalse(result.is_valid)
            self.assertTrue(result.errors)

    def test_rebuilt_cache_is_deterministic_and_side_effect_free(self):
        world, _ids = make_demand_world()
        calculate_world_demand(world)
        before = deepcopy(world)

        first = rebuild_demand_indexes(world)
        second = rebuild_demand_indexes(world)

        self.assertEqual(first, second)
        self.assertEqual(world, before)

    def test_origin_api_uses_full_world_not_only_requested_origin(self):
        world, ids = make_demand_world()
        result = recalculate_origin_demand(world, ids["MNL"])

        self.assertTrue(result.succeeded)
        self.assertEqual(len(result.indexes.market_by_pair), 12)
        self.assertEqual(
            sum(
                result.indexes.by_market[market_id].destination_pair_share
                for market_id in result.indexes.markets_by_origin[ids["MNL"]]
            ),
            1,
        )

    def test_processed_cohort_validation_covers_identity_multipliers_and_counts(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        resolve_daily_cohort(world, market_id, "2026-08-20", indexes=indexes)
        record = next(
            iter(world["world_state"]["demand_state"]["processed_cohorts"].values())
        )
        record["actual_daily_bookers"] = -1
        record["daily_multipliers_bps"]["holiday"] = -1

        codes = issue_codes(world)

        self.assertIn("invalid_demand_cohort", codes)
        self.assertIn("invalid_demand_multipliers", codes)


class Stage1DemandAdversarialReviewTests(unittest.TestCase):
    def test_empty_single_destination_and_origin_ineligibility_policies(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        single_destination = calculate_world_demand(world)
        self.assertEqual(
            single_destination.indexes.pair(
                ids["MNL"], ids["DVO"]
            ).destination_pair_share,
            Decimal(1),
        )

        closed = revise_demand_model(
            world,
            airport_updates={
                ids["MNL"]: {"passenger_demand_eligible": False},
                ids["DVO"]: {"passenger_demand_eligible": False},
            },
        )
        empty = calculate_world_demand(world)
        self.assertTrue(closed.succeeded)
        self.assertTrue(empty.succeeded)
        self.assertEqual(empty.indexes.eligible_airport_ids, ())
        self.assertEqual(empty.indexes.by_market, {})
        with self.assertRaises(ValueError):
            calculate_origin_daily_booking_pool(world, ids["MNL"])

    def test_boundary_coordinates_coincident_antipodal_and_enormous_population(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        revision = revise_demand_model(
            world,
            airport_updates={
                ids["MNL"]: {
                    "population": 10**100,
                    "latitude_microdegrees": 0,
                    "longitude_microdegrees": 0,
                },
                ids["DVO"]: {
                    "latitude_microdegrees": 0,
                    "longitude_microdegrees": 0,
                },
            },
        )
        coincident = calculate_world_demand(world).indexes.pair(
            ids["MNL"], ids["DVO"]
        )
        self.assertTrue(revision.succeeded)
        self.assertEqual(coincident.distance_km, Decimal("0.000"))
        self.assertTrue(coincident.raw_pair_score.is_finite())
        self.assertGreater(coincident.base_daily_bookers, 0)

        antipodal_revision = revise_demand_model(
            world,
            airport_updates={
                ids["DVO"]: {"longitude_microdegrees": 180_000_000},
            },
        )
        antipodal = calculate_world_demand(world).indexes.pair(
            ids["MNL"], ids["DVO"]
        )
        self.assertTrue(antipodal_revision.succeeded)
        self.assertEqual(antipodal.distance_km, Decimal("20015.087"))
        self.assertGreater(antipodal.raw_pair_score, 0)

    def test_exact_open_close_boundaries_and_reopening_reuse_pair_ids(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        initial = calculate_world_demand(world).indexes
        pair_ids = dict(initial.market_by_pair)

        closed = revise_demand_model(
            world,
            airport_updates={
                ids["DVO"]: {"active_until_date": "2026-08-20"},
            },
            universe_date="2026-08-20",
        )
        while_closed = calculate_world_demand(world).indexes
        reopened = revise_demand_model(
            world,
            airport_updates={
                ids["DVO"]: {"active_until_date": None},
            },
            universe_date="2026-08-21",
        )
        after = calculate_world_demand(world).indexes

        self.assertTrue(closed.succeeded)
        self.assertNotIn(ids["DVO"], while_closed.eligible_airport_ids)
        self.assertTrue(reopened.succeeded)
        self.assertEqual(after.market_by_pair, pair_ids)

    def test_large_reordered_universe_conserves_without_iteration_bias(self):
        codes = tuple(f"R{number:03d}" for number in range(20))
        world = create_new_world(
            ceo_display_name="Order",
            airline_display_name="Order Air",
            starting_airport=airport_reference(
                codes[0],
                population=100_000,
                coordinates={"lat": -30, "lon": -120},
                destination_type="NORMAL_CITY",
                opened="1950-01-01",
            ),
            difficulty="Normal",
            simulation_time_utc="2026-08-20T00:00:00Z",
            simulation_seed=11,
            starting_money=1,
        )
        for number, code in enumerate(codes[1:], 1):
            add_airport_reference(
                world,
                airport_reference(
                    code,
                    population=100_000 + number,
                    coordinates={"lat": -30 + number, "lon": -120 + number},
                    destination_type="NORMAL_CITY",
                    opened="1950-01-01",
                ),
            )
        original = calculate_world_demand(world).indexes
        expected = dict(original.by_market)

        for seed in range(5):
            reordered = deepcopy(world)
            rng = random.Random(seed)
            for field in ("airports", "directional_markets"):
                items = list(reordered["world_state"][field].items())
                rng.shuffle(items)
                reordered["world_state"][field] = dict(items)
            rebuilt = rebuild_demand_indexes(reordered)
            self.assertEqual(dict(rebuilt.by_market), expected)
            for market_ids in rebuilt.markets_by_origin.values():
                shares = [rebuilt.by_market[value].destination_pair_share for value in market_ids]
                with localcontext() as context:
                    context.prec = 60
                    self.assertEqual(sum(shares, Decimal(0)), Decimal(1))
                self.assertTrue(all(share >= 0 for share in shares))

    def test_fingerprint_detects_relevant_inputs_and_ignores_unrelated_state(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        original = calculate_demand_input_fingerprint(world)
        unrelated = deepcopy(world)
        unrelated["ui_state"]["selected_screen"] = "demand"
        airline_id = unrelated["world_state"]["player"]["primary_airline_id"]
        unrelated["world_state"]["airlines"][airline_id]["display_name"] = "Other"
        self.assertEqual(calculate_demand_input_fingerprint(unrelated), original)

        demand = calculate_world_demand(world).indexes
        market_id = demand.market_by_pair[(ids["MNL"], ids["DVO"])]
        add_connection(world, airline_id, market_id, status="ACTIVE")
        self.assertEqual(calculate_demand_input_fingerprint(world), original)

        relevant = deepcopy(world)
        relevant["world_state"]["airports"][ids["MNL"]]["population"] += 1
        self.assertNotEqual(calculate_demand_input_fingerprint(relevant), original)
        self.assertIn("inconsistent_demand_revision", issue_codes(relevant))

        reordered = deepcopy(world)
        weights = reordered["simulation"]["configuration"]["demand"][
            "destination_type_weight_bps"
        ]
        reordered["simulation"]["configuration"]["demand"][
            "destination_type_weight_bps"
        ] = dict(reversed(list(weights.items())))
        self.assertEqual(calculate_demand_input_fingerprint(reordered), original)

        airport_changes = {
            "population": 99,
            "latitude_microdegrees": 1,
            "longitude_microdegrees": 2,
            "country_reference": "XX",
            "demand_destination_type": "MINOR_CITY",
            "active_from_date": "1900-01-01",
            "active_until_date": "2100-01-01",
            "passenger_demand_eligible": False,
            "demand_input_revision": 99,
        }
        for field, value in airport_changes.items():
            changed = deepcopy(world)
            changed["world_state"]["airports"][ids["MNL"]][field] = value
            self.assertNotEqual(
                calculate_demand_input_fingerprint(changed), original, field
            )

        configuration_changes = {
            "model_version": 99,
            "configuration_version": "other",
            "revision": 99,
            "daily_booker_rate_ppm": 99,
            "distance_scale_km": 99,
            "same_country_weight_bps": 99,
            "international_weight_bps": 99,
            "relationship_weight_bps": 99,
            "daily_multiplier_min_bps": 99,
            "daily_multiplier_max_bps": 99,
        }
        for field, value in configuration_changes.items():
            changed = deepcopy(world)
            changed["simulation"]["configuration"]["demand"][field] = value
            self.assertNotEqual(
                calculate_demand_input_fingerprint(changed), original, field
            )

    def test_multiplier_composition_is_exact_before_one_decimal_division(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        factors = {
            "other": 45_678,
            "date_season": 12_345,
            "world": 34_567,
            "holiday": 23_456,
        }
        canonical, composed = compose_daily_multipliers(world, factors)
        numerator = 12_345 * 23_456 * 34_567 * 45_678
        self.assertEqual(tuple(canonical), ("date_season", "holiday", "world", "other"))
        self.assertEqual(composed, Decimal(numerator) / Decimal(10_000**4))
        self.assertEqual(compose_daily_multipliers(world, {"world": 0})[1], 0)
        with self.assertRaises(ValueError):
            compose_daily_multipliers(world, {"holiday": True})

    def test_stochastic_rounding_seed_contract_and_exact_thresholds(self):
        world, ids = make_demand_world(("MNL", "DVO"), seed=73)
        revision = revise_demand_model(
            world,
            configuration_updates={
                "configuration_version": "seed-contract-v1",
                "daily_booker_rate_ppm": 1,
            },
            airport_updates={ids["MNL"]: {"population": 100_001}},
        )
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        pair = indexes.by_market[market_id]
        cohort_date = "2026-08-20"
        canonical, composed = compose_daily_multipliers(world, {})
        expected_material = {
            "purpose": "KEYED_SHA256_FRACTION_V1",
            "world_seed": 73,
            "demand_model_version": 3,
            "demand_configuration_version": "seed-contract-v1",
            "market_id": market_id,
            "cohort_date": cohort_date,
            "daily_multipliers_bps": canonical,
        }
        material = json.dumps(
            expected_material,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected_value = pair.base_daily_bookers * composed
        floor = int(expected_value)
        fraction = Fraction(expected_value - Decimal(floor))
        draw = int.from_bytes(hashlib.sha256(material).digest(), "big")
        scale = 1 << 256
        acceptance_limit = scale - (scale % fraction.denominator)
        self.assertLess(draw, acceptance_limit)
        expected = floor + int(
            draw % fraction.denominator < fraction.numerator
        )
        seen_rounding_material = []
        real_sha256 = hashlib.sha256

        def capture_sha256(value):
            if b'"purpose":"KEYED_SHA256_FRACTION_V1"' in value:
                seen_rounding_material.append(value)
            return real_sha256(value)

        with patch("game.demand.model.hashlib.sha256", side_effect=capture_sha256):
            cohort = resolve_daily_cohort(
                world, market_id, cohort_date, indexes=indexes
            )
        self.assertEqual(cohort.actual_daily_bookers, expected)
        self.assertEqual(seen_rounding_material, [material])
        self.assertEqual(json.loads(seen_rounding_material[0]), expected_material)

        reverse_market_id = indexes.market_by_pair[(ids["DVO"], ids["MNL"])]
        reverse_material = []

        def capture_reverse(value):
            if b'"purpose":"KEYED_SHA256_FRACTION_V1"' in value:
                reverse_material.append(value)
            return real_sha256(value)

        with patch("game.demand.model.hashlib.sha256", side_effect=capture_reverse):
            resolve_daily_cohort(
                world, reverse_market_id, cohort_date, indexes=indexes
            )
        self.assertEqual(len(reverse_material), 1)
        self.assertNotEqual(material, reverse_material[0])
        self.assertNotEqual(
            real_sha256(material).digest(), real_sha256(reverse_material[0]).digest()
        )

        with patch("game.demand.model.hashlib.sha256", side_effect=AssertionError):
            self.assertEqual(demand_model._resolve_fraction(Decimal(7), b"unused"), 7)

        class Digest:
            def __init__(self, value):
                self.value = value

            def digest(self):
                return self.value

        with patch("game.demand.model.hashlib.sha256", return_value=Digest(bytes(32))):
            self.assertEqual(demand_model._resolve_fraction(Decimal("0.5"), b"x"), 1)
        with patch("game.demand.model.hashlib.sha256", return_value=Digest(bytes([255]) * 32)):
            self.assertEqual(demand_model._resolve_fraction(Decimal("0.5"), b"x"), 0)

    def test_malformed_existing_marker_is_rejected_before_idempotent_reuse(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        key = f"{market_id}@2026-08-20"
        world["world_state"]["demand_state"]["processed_cohorts"][key] = {
            "actual_daily_bookers": 999,
            "demand_model_revision": 1,
        }
        before = deepcopy(world)
        with self.assertRaises(ValueError):
            resolve_daily_cohort(world, market_id, "2026-08-20", indexes=indexes)
        self.assertEqual(world, before)

    def test_malformed_airport_demand_inputs_are_structured_rejections(self):
        mutations = (
            ("population", None),
            ("population", 0),
            ("population", -1),
            ("population", True),
            ("latitude_microdegrees", float("nan")),
            ("longitude_microdegrees", float("inf")),
            ("country_reference", None),
            ("demand_destination_type", []),
            ("passenger_demand_eligible", "yes"),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                world, _ids = make_demand_world(("MNL", "DVO"))
                first_airport = next(iter(world["world_state"]["airports"].values()))
                first_airport[field] = value
                validation = validate_world(world)
                build = calculate_world_demand(world)
                self.assertFalse(validation.is_valid)
                self.assertTrue(validation.errors)
                self.assertFalse(build.succeeded)

    def test_cohort_composite_and_directional_market_unknown_fields_are_rejected(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        resolve_daily_cohort(world, market_id, "2026-08-20", indexes=indexes)
        record = next(iter(world["world_state"]["demand_state"]["processed_cohorts"].values()))
        record["composite_multiplier_ppm"] += 1
        record["actual_daily_bookers"] += 100
        world["world_state"]["directional_markets"][market_id]["base_daily_bookers"] = 1
        codes = issue_codes(world)
        self.assertIn("inconsistent_demand_cohort", codes)
        self.assertIn("inconsistent_demand_cohort_fingerprint", codes)
        self.assertIn("unknown_authoritative_field", codes)

    def test_airport_addition_and_pair_allocation_failures_are_atomic(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        before = deepcopy(world)
        with self.assertRaises(ValueError):
            add_airport_reference(
                world,
                airport_reference(
                    "BIG",
                    population=10**5000,
                    coordinates={"lat": 1, "lon": 1},
                    destination_type="NORMAL_CITY",
                    opened="1950-01-01",
                ),
            )
        self.assertEqual(world, before)

        with patch("game.demand.model.allocate_id", side_effect=ValueError("injected")):
            result = calculate_world_demand(world)
        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)

        malformed = deepcopy(world)
        first_airport = next(iter(malformed["world_state"]["airports"].values()))
        first_airport["population"] = 10**5000
        self.assertIn("invalid_demand_fingerprint_input", issue_codes(malformed))

    def test_failure_after_partial_score_derivation_is_atomic(self):
        world, _ids = make_demand_world()
        before = deepcopy(world)
        original = demand_model._raw_pair_score
        calls = 0

        def fail_after_scores(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise ArithmeticError("injected score failure")
            return original(*args, **kwargs)

        with patch("game.demand.model._raw_pair_score", side_effect=fail_after_scores):
            result = calculate_world_demand(world)
        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)

    def test_whole_world_partial_failure_and_cyclic_revision_input_are_atomic(self):
        world, _ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        before = deepcopy(world)
        original = demand_model._cohort_record
        calls = 0

        def fail_after_one(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("injected halfway failure")
            return original(*args, **kwargs)

        with patch("game.demand.model._cohort_record", side_effect=fail_after_one):
            result = resolve_world_daily_cohorts(
                world, "2026-08-20", indexes=indexes
            )
        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)

        cyclic = {}
        cyclic["destination_type_weight_bps"] = cyclic
        revision = revise_demand_model(world, configuration_updates=cyclic)
        self.assertFalse(revision.succeeded)
        self.assertEqual(world, before)

    def test_historical_markers_survive_revision_and_dates_use_pinned_universe(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        old = resolve_daily_cohort(world, market_id, "1900-01-01", indexes=indexes)
        revision = revise_demand_model(
            world,
            configuration_updates={
                "configuration_version": "future-revision-v1",
                "daily_booker_rate_ppm": 3_000,
            },
        )
        new_indexes = calculate_world_demand(world, indexes=indexes).indexes
        repeated = resolve_daily_cohort(
            world, market_id, "1900-01-01", indexes=new_indexes
        )
        future = resolve_daily_cohort(
            world, market_id, "2100-01-01", indexes=new_indexes
        )
        self.assertTrue(revision.succeeded)
        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.actual_daily_bookers, old.actual_daily_bookers)
        self.assertEqual(repeated.demand_model_revision, old.demand_model_revision)
        self.assertEqual(future.demand_model_revision, revision.revision)

    def test_repeated_whole_world_resolution_does_not_duplicate_markers(self):
        world, _ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        first = resolve_world_daily_cohorts(
            world, "2026-08-20", indexes=indexes
        )
        marker_count = len(
            world["world_state"]["demand_state"]["processed_cohorts"]
        )
        second = resolve_world_daily_cohorts(
            world, "2026-08-20", indexes=indexes
        )
        self.assertTrue(first.succeeded)
        self.assertTrue(second.succeeded)
        self.assertEqual(len(second.cohorts), marker_count)
        self.assertTrue(all(cohort.reused for cohort in second.cohorts))
        self.assertEqual(
            len(world["world_state"]["demand_state"]["processed_cohorts"]),
            marker_count,
        )

    def test_duplicate_airport_reference_is_rejected_atomically(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        before = deepcopy(world)
        with self.assertRaises(ValueError):
            add_airport_reference(
                world,
                airport_reference(
                    "MNL",
                    population=1,
                    coordinates={"lat": 0, "lon": 0},
                    destination_type="MINOR_CITY",
                    opened="1950-01-01",
                ),
            )
        self.assertEqual(world, before)

    def test_invalid_cache_metadata_is_rebuilt_and_ineligible_addition_does_not_renormalize(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"))
        initial = calculate_world_demand(world)
        stale = demand_model.DemandIndexes(
            lineage_id=initial.indexes.lineage_id,
            model_version=initial.indexes.model_version,
            model_revision=initial.indexes.model_revision + 1,
            universe_date=initial.indexes.universe_date,
            source_fingerprint=initial.indexes.source_fingerprint,
            eligible_airport_ids=initial.indexes.eligible_airport_ids,
            by_market=initial.indexes.by_market,
            market_by_pair=initial.indexes.market_by_pair,
            markets_by_origin=initial.indexes.markets_by_origin,
        )
        rebuilt = calculate_world_demand(world, indexes=stale)
        self.assertFalse(rebuilt.cache_reused)

        before = {
            pair: demand.base_daily_bookers
            for pair, market_id in initial.indexes.market_by_pair.items()
            if (demand := initial.indexes.by_market.get(market_id)) is not None
        }
        add_airport_reference(world, "INELIGIBLE")
        after = calculate_world_demand(world).indexes
        for pair, baseline in before.items():
            self.assertEqual(after.pair(*pair).base_daily_bookers, baseline)
        self.assertNotIn(
            next(
                airport_id
                for airport_id, airport in world["world_state"]["airports"].items()
                if airport["reference_code"] == "INELIGIBLE"
            ),
            after.eligible_airport_ids,
        )


class Stage1DemandPerformanceTests(unittest.TestCase):
    def test_representative_universe_paths_have_separate_nonflaky_budgets(self):
        count = 50
        codes = tuple(f"A{number:03d}" for number in range(count))
        first_reference = airport_reference(
            codes[0],
            population=100_000,
            coordinates={"lat": -20, "lon": -100},
            destination_type="NORMAL_CITY",
            opened="1950-01-01",
        )
        world = create_new_world(
            ceo_display_name="Scale",
            airline_display_name="Scale Air",
            starting_airport=first_reference,
            difficulty="Normal",
            simulation_time_utc="2026-08-20T00:00:00Z",
            simulation_seed=9,
            starting_money=1,
        )
        for number, code in enumerate(codes[1:], 1):
            add_airport_reference(
                world,
                airport_reference(
                    code,
                    population=100_000 + number * 1_000,
                    coordinates={
                        "lat": -20 + (number % 20),
                        "lon": -100 + (number % 40),
                    },
                    destination_type="NORMAL_CITY",
                    opened="1950-01-01",
                ),
            )

        started = perf_counter()
        built = calculate_world_demand(world)
        build_seconds = perf_counter() - started
        started = perf_counter()
        reused = calculate_world_demand(world, indexes=built.indexes)
        reuse_seconds = perf_counter() - started
        started = perf_counter()
        cohorts = resolve_world_daily_cohorts(
            world, "2026-08-20", indexes=built.indexes
        )
        cohort_seconds = perf_counter() - started
        revised = revise_demand_model(
            world,
            configuration_updates={
                "configuration_version": "scale-revision-v1",
                "same_country_weight_bps": 12_000,
            },
        )
        started = perf_counter()
        rebuilt = calculate_world_demand(world, indexes=built.indexes)
        revision_seconds = perf_counter() - started

        self.assertTrue(built.succeeded)
        self.assertEqual(len(built.indexes.by_market), count * (count - 1))
        self.assertTrue(reused.cache_reused)
        self.assertTrue(cohorts.succeeded)
        self.assertTrue(revised.succeeded)
        self.assertTrue(rebuilt.succeeded)
        self.assertLess(build_seconds, 10.0)
        self.assertLess(reuse_seconds, 3.0)
        self.assertLess(cohort_seconds, 10.0)
        self.assertLess(revision_seconds, 10.0)


if __name__ == "__main__":
    unittest.main()
