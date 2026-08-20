"""Milestone 4.5A compact derivation and direct activation tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import sys
from time import perf_counter
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

import game.demand.model as demand_model
from game.demand import (
    DirectPublishedServiceActivationProvider,
    calculate_pair_demand,
    calculate_world_demand,
    discover_active_market_ids,
    resolve_active_daily_cohorts,
    resolve_world_daily_cohorts,
    revise_demand_model,
)
from game.scheduling import (
    create_schedule_definition,
    publish_occurrences_through,
    rebuild_dated_flight_indexes,
)
from game.world_state import (
    add_aircraft,
    add_connection,
    create_new_world,
    validate_world,
)
from game.world_state.demand_fingerprint import calculate_demand_input_fingerprint
from game.world_state.timezones import load_named_timezone
from tests.test_stage1_world_demand import airport_reference, make_demand_world


def _rich_model3_reference(world):
    """The committed Milestone 4 rich derivation, retained only as a test oracle."""
    airports = world["world_state"]["airports"]
    eligible = demand_model._eligible_airport_ids(world)
    configuration = world["simulation"]["configuration"]["demand"]
    market_by_pair = {
        (market["origin_airport_id"], market["destination_airport_id"]): market_id
        for market_id, market in world["world_state"]["directional_markets"].items()
    }
    reference = {}
    residual_destinations = {}
    denominators = {}
    with localcontext() as context:
        context.prec = demand_model._SCORE_PRECISION
        for origin_id in eligible:
            destinations = tuple(value for value in eligible if value != origin_id)
            if not destinations:
                continue
            distances = [
                demand_model._distance_km(airports[origin_id], airports[destination_id])
                for destination_id in destinations
            ]
            raw_scores = [
                demand_model._raw_pair_score(
                    configuration,
                    airports[origin_id],
                    airports[destination_id],
                    distance=distance,
                )
                for destination_id, distance in zip(destinations, distances)
            ]
            denominator = sum(raw_scores, Decimal(0))
            shares = [score / denominator for score in raw_scores]
            residual_index = max(
                range(len(destinations)),
                key=lambda index: (raw_scores[index], destinations[index]),
            )
            with localcontext() as conservation_context:
                conservation_context.prec = (
                    demand_model._SCORE_PRECISION + len(str(len(shares))) + 2
                )
                other_total = sum(
                    (
                        share
                        for index, share in enumerate(shares)
                        if index != residual_index
                    ),
                    Decimal(0),
                )
                shares[residual_index] = Decimal(1) - other_total
            pool = (
                Decimal(airports[origin_id]["population"])
                * Decimal(configuration["daily_booker_rate_ppm"])
                / demand_model._PPM
            )
            residual_destinations[origin_id] = destinations[residual_index]
            denominators[origin_id] = denominator
            for destination_id, distance, score, share in zip(
                destinations, distances, raw_scores, shares
            ):
                market_id = market_by_pair[(origin_id, destination_id)]
                reference[market_id] = demand_model.PairDemand(
                    market_id,
                    origin_id,
                    destination_id,
                    pool,
                    distance,
                    score,
                    share,
                    pool * share,
                )
    return reference, residual_destinations, denominators


def _count_retained_instances(value, target_type, seen=None):
    """Inspect retained fields without invoking lazy mapping projections."""
    seen = set() if seen is None else seen
    marker = id(value)
    if marker in seen:
        return 0
    seen.add(marker)
    count = int(isinstance(value, target_type))
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, dict):
        return count + sum(
            _count_retained_instances(key, target_type, seen)
            + _count_retained_instances(item, target_type, seen)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list, set, frozenset)):
        return count + sum(
            _count_retained_instances(item, target_type, seen) for item in value
        )
    if hasattr(value, "__dict__"):
        return count + _count_retained_instances(vars(value), target_type, seen)
    return count


def _publish_direct_service(world, ids, destination_code, *, registration="RP-C4501"):
    indexes = calculate_world_demand(world).indexes
    airline_id = world["world_state"]["player"]["primary_airline_id"]
    market_id = indexes.market_by_pair[(ids["MNL"], ids[destination_code])]
    connection_id = add_connection(world, airline_id, market_id, status="ACTIVE")
    aircraft_id = add_aircraft(
        world,
        airline_id,
        registration,
        "A320",
        home_airport_id=ids["MNL"],
    )
    schedule = create_schedule_definition(
        world,
        airline_id=airline_id,
        connection_id=connection_id,
        planned_aircraft_id=aircraft_id,
        origin_airport_id=ids["MNL"],
        destination_airport_id=ids[destination_code],
        weekdays=[0],
        departure_local_time="08:00:00",
        arrival_local_time="10:00:00",
        effective_from_local_date="2026-08-24",
        capacity=180,
        fare_offer={"currency": "USD", "amount_minor": 10_000},
    )
    if not schedule.succeeded:
        raise AssertionError(schedule.conflicts)
    publication = publish_occurrences_through(world, "2026-08-24T00:00:00Z")
    if not publication.succeeded:
        raise AssertionError(publication.conflicts)
    flight_id = publication.created_dated_flight_ids[-1]
    return market_id, flight_id


class CompactDemandEquivalenceTests(unittest.TestCase):
    def test_every_rich_value_and_residual_is_exactly_equal(self):
        world, ids = make_demand_world()
        compact = calculate_world_demand(world).indexes
        rich, residuals, denominators = _rich_model3_reference(world)

        self.assertEqual(dict(compact.by_market), rich)
        for origin_id, normalization in compact.normalization_by_origin.items():
            self.assertEqual(
                normalization.residual_destination_airport_id,
                residuals[origin_id],
            )
            self.assertEqual(
                normalization.normalization_denominator,
                denominators[origin_id],
            )
            shares = [
                compact.by_market[market_id].destination_pair_share
                for market_id in compact.markets_by_origin[origin_id]
            ]
            with localcontext() as context:
                context.prec = 70
                self.assertEqual(sum(shares, Decimal(0)), Decimal(1))
        self.assertEqual(
            calculate_pair_demand(world, ids["MNL"], ids["DVO"], indexes=compact),
            rich[compact.market_by_pair[(ids["MNL"], ids["DVO"])]],
        )

        market_id = compact.market_by_pair[(ids["MNL"], ids["DVO"])]
        expected_pair = rich[market_id]
        for caller_precision in (3, 5, 10, 28, 50):
            with self.subTest(caller_precision=caller_precision):
                with localcontext() as context:
                    context.prec = caller_precision
                    actual_pair = compact.by_market[market_id]
                self.assertEqual(actual_pair, expected_pair)

    def test_compact_actual_cohorts_match_rich_reference_and_are_byte_stable(self):
        world, _ids = make_demand_world(seed=991)
        indexes = calculate_world_demand(world).indexes
        rich, _residuals, _denominators = _rich_model3_reference(world)
        expected = {}
        canonical = {
            "date_season": 10_000,
            "holiday": 12_345,
            "world": 9_876,
            "other": 10_000,
        }
        rich_indexes = SimpleNamespace(
            by_market=rich,
            model_version=indexes.model_version,
            model_revision=indexes.model_revision,
        )
        for market_id, pair in rich.items():
            expected[market_id] = demand_model._cohort_record(
                world,
                rich_indexes,
                market_id,
                "2026-08-20",
                canonical,
            )["actual_daily_bookers"]

        left = deepcopy(world)
        right = deepcopy(world)
        left_result = resolve_world_daily_cohorts(
            left,
            "2026-08-20",
            indexes=indexes,
            multipliers_by_market={market_id: canonical for market_id in rich},
        )
        right_result = resolve_world_daily_cohorts(
            right,
            "2026-08-20",
            indexes=indexes,
            multipliers_by_market=dict(
                reversed([(market_id, canonical) for market_id in rich])
            ),
        )
        self.assertEqual(
            {item.market_id: item.actual_daily_bookers for item in left_result.cohorts},
            expected,
        )
        self.assertEqual(left, right)
        self.assertEqual(
            json.dumps(left, sort_keys=True, separators=(",", ":")).encode(),
            json.dumps(right, sort_keys=True, separators=(",", ":")).encode(),
        )

    def test_unserved_airport_stays_in_denominator_without_rich_pair_storage(self):
        world, ids = make_demand_world()
        indexes = calculate_world_demand(world).indexes
        before = indexes.pair(ids["MNL"], ids["DVO"])
        rich_pair_count = _count_retained_instances(
            indexes, demand_model.PairDemand
        )

        self.assertIn((ids["MNL"], ids["PPS"]), indexes.market_by_pair)
        self.assertEqual(world["world_state"]["connections"], {})
        self.assertEqual(rich_pair_count, 0)
        self.assertEqual(
            before.destination_pair_share,
            indexes.pair(ids["MNL"], ids["DVO"]).destination_pair_share,
        )

    def test_malformed_or_aliased_compact_cache_is_rebuilt(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"))
        indexes = calculate_world_demand(world).indexes
        origin_id = ids["MNL"]
        corrupted = replace(
            indexes.normalization_by_origin[origin_id],
            residual_destination_airport_id="missing-airport",
        )
        normalizations = dict(indexes.normalization_by_origin)
        normalizations[origin_id] = corrupted
        malformed_caches = (
            replace(indexes, normalization_by_origin=normalizations),
            replace(indexes, by_market={}),
            replace(indexes, markets_by_origin={}),
        )

        for malformed in malformed_caches:
            with self.subTest(field_types=tuple(type(value) for value in vars(malformed).values())):
                rebuilt = calculate_world_demand(world, indexes=malformed)
                self.assertTrue(rebuilt.succeeded, rebuilt.issues)
                self.assertFalse(rebuilt.cache_reused)
                self.assertEqual(
                    rebuilt.indexes.pair(ids["MNL"], ids["DVO"]),
                    indexes.pair(ids["MNL"], ids["DVO"]),
                )

    def test_equal_largest_scores_commit_immutable_id_residual(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"))
        source = world["world_state"]["airports"][ids["DVO"]]
        tied_fields = {
            field: source[field]
            for field in (
                "population",
                "latitude_microdegrees",
                "longitude_microdegrees",
                "country_reference",
                "demand_destination_type",
            )
        }
        revised = revise_demand_model(
            world,
            airport_updates={ids["CEB"]: tied_fields},
            universe_date="2026-08-20",
        )
        self.assertTrue(revised.succeeded, revised.issues)

        compact = calculate_world_demand(world).indexes
        rich, residuals, _denominators = _rich_model3_reference(world)
        expected_residual = max(ids["DVO"], ids["CEB"])
        self.assertEqual(residuals[ids["MNL"]], expected_residual)
        self.assertEqual(
            compact.normalization_by_origin[
                ids["MNL"]
            ].residual_destination_airport_id,
            expected_residual,
        )
        self.assertEqual(dict(compact.by_market), rich)


class DirectDemandActivationTests(unittest.TestCase):
    def test_rights_or_connections_alone_do_not_activate_or_create_work(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        market_id = indexes.market_by_pair[(ids["MNL"], ids["DVO"])]
        add_connection(world, airline_id, market_id, status="ACTIVE")

        active = discover_active_market_ids(world)
        resolved = resolve_active_daily_cohorts(
            world, "2026-08-20", indexes=indexes
        )

        self.assertEqual(active, ())
        self.assertTrue(resolved.succeeded)
        self.assertEqual(resolved.cohorts, ())
        self.assertEqual(
            world["world_state"]["demand_state"]["processed_cohorts"], {}
        )

    def test_published_direct_service_activates_in_stable_market_id_order(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"))
        dvo_market, _ = _publish_direct_service(world, ids, "DVO")
        ceb_market, _ = _publish_direct_service(
            world, ids, "CEB", registration="RP-C4502"
        )
        reordered = deepcopy(world)
        for field in ("directional_markets", "dated_flights"):
            reordered["world_state"][field] = dict(
                reversed(list(reordered["world_state"][field].items()))
            )

        expected = tuple(sorted((dvo_market, ceb_market)))
        self.assertEqual(discover_active_market_ids(world), expected)
        self.assertEqual(discover_active_market_ids(reordered), expected)

    def test_activation_window_is_inclusive_and_daily_date_is_simulation_utc(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        market_id, flight_id = _publish_direct_service(world, ids, "DVO")
        departure = world["world_state"]["dated_flights"][flight_id][
            "scheduled_off_block_utc"
        ]

        self.assertEqual(
            discover_active_market_ids(
                world, start_utc=departure, end_utc=departure
            ),
            (market_id,),
        )
        self.assertEqual(
            discover_active_market_ids(
                world,
                start_utc="2026-08-24T00:00:01Z",
                end_utc="2026-08-25T00:00:00Z",
            ),
            (),
        )
        world["simulation"]["time_utc"] = "2026-08-23T23:59:59Z"
        local_next_day = resolve_active_daily_cohorts(world, "2026-08-24")
        utc_current_day = resolve_active_daily_cohorts(world, "2026-08-23")
        self.assertFalse(local_next_day.succeeded)
        self.assertTrue(utc_current_day.succeeded, utc_current_day.issues)
        self.assertEqual(
            tuple(item.market_id for item in utc_current_day.cohorts),
            (market_id,),
        )

    def test_stale_dated_flight_indexes_never_hide_or_reactivate_service(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        calculate_world_demand(world)
        before_publication = rebuild_dated_flight_indexes(world)
        market_id, flight_id = _publish_direct_service(world, ids, "DVO")

        self.assertEqual(
            discover_active_market_ids(
                world, dated_flight_indexes=before_publication
            ),
            (market_id,),
        )
        published = rebuild_dated_flight_indexes(world)
        world["world_state"]["dated_flights"][flight_id]["status"] = "CANCELLED"
        self.assertEqual(
            discover_active_market_ids(world, dated_flight_indexes=published), ()
        )

    def test_valid_published_deadhead_does_not_activate_passenger_demand(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        calculate_world_demand(world)
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        aircraft_id = add_aircraft(
            world,
            airline_id,
            "RP-DH451",
            "A320",
            home_airport_id=ids["MNL"],
        )
        schedule = create_schedule_definition(
            world,
            airline_id=airline_id,
            connection_id=None,
            planned_aircraft_id=aircraft_id,
            origin_airport_id=ids["MNL"],
            destination_airport_id=ids["DVO"],
            weekdays=[0],
            departure_local_time="08:00:00",
            arrival_local_time="10:00:00",
            effective_from_local_date="2026-08-24",
            capacity=0,
            fare_offer={"currency": "USD", "amount_minor": 0},
            service_type="DEADHEAD",
            passenger_service_classification="NON_PASSENGER",
        )
        publication = publish_occurrences_through(
            world, "2026-08-24T00:00:00Z"
        )

        self.assertTrue(schedule.succeeded, schedule.conflicts)
        self.assertTrue(publication.succeeded, publication.conflicts)
        self.assertEqual(discover_active_market_ids(world), ())

    def test_activation_window_is_explicit_and_provider_results_can_be_combined(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"))
        dvo_market, _ = _publish_direct_service(world, ids, "DVO")
        indexes = calculate_world_demand(world).indexes
        ceb_market = indexes.market_by_pair[(ids["MNL"], ids["CEB"])]

        self.assertEqual(
            discover_active_market_ids(
                world,
                start_utc="2026-08-20T00:00:00Z",
                end_utc="2026-08-23T23:59:59Z",
            ),
            (),
        )

        class AdditionalRuntimeProvider:
            def active_market_ids(
                self, envelope, window, *, dated_flight_indexes=None
            ):
                return (ceb_market,)

        combined = discover_active_market_ids(
            world,
            providers=(
                DirectPublishedServiceActivationProvider(),
                AdditionalRuntimeProvider(),
            ),
        )
        self.assertEqual(combined, tuple(sorted((dvo_market, ceb_market))))

    def test_deadhead_cancelled_superseded_and_malformed_service_do_not_activate(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        market_id, flight_id = _publish_direct_service(world, ids, "DVO")
        self.assertEqual(discover_active_market_ids(world), (market_id,))

        for mutation in (
            lambda flight: flight.update(status="CANCELLED"),
            lambda flight: flight.update(status="SUPERSEDED"),
            lambda flight: flight.update(service_type="DEADHEAD"),
            lambda flight: flight.pop("fare_offer"),
            lambda flight: flight.update(capacity=0),
            lambda flight: flight.update(scheduled_off_block_utc="not-a-time"),
        ):
            with self.subTest(mutation=mutation):
                changed = deepcopy(world)
                mutation(changed["world_state"]["dated_flights"][flight_id])
                self.assertEqual(discover_active_market_ids(changed), ())

        flight = world["world_state"]["dated_flights"][flight_id]
        malformed_records = (
            ("connections", flight["connection_id"]),
            ("schedule_definitions", flight["schedule_id"]),
            ("aircraft", flight["planned_aircraft_id"]),
            ("directional_markets", market_id),
            ("airports", flight["destination_airport_id"]),
        )
        for collection, record_id in malformed_records:
            with self.subTest(collection=collection):
                changed = deepcopy(world)
                changed["world_state"][collection][record_id] = []
                self.assertEqual(discover_active_market_ids(changed), ())

    def test_schedule_snapshot_identity_and_duplicate_occurrences_are_required(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        _market_id, flight_id = _publish_direct_service(world, ids, "DVO")
        flight = world["world_state"]["dated_flights"][flight_id]
        identity_mutations = (
            lambda changed, item: item["fare_offer"].update(
                amount_minor=item["fare_offer"]["amount_minor"] + 1
            ),
            lambda changed, item: item.update(
                occurrence_key="wrong-schedule@2026-08-24"
            ),
            lambda changed, item: item.update(
                scheduled_off_block_utc="2026-08-24T00:00:01Z"
            ),
            lambda changed, item: item.update(
                superseded_by_schedule_revision=item["schedule_revision"]
            ),
            lambda changed, item: changed["world_state"]["connections"][
                item["connection_id"]
            ].update(connection_id="wrong-connection"),
            lambda changed, item: changed["world_state"]["schedule_definitions"][
                item["schedule_id"]
            ].update(schedule_id="wrong-schedule"),
            lambda changed, item: changed["world_state"]["schedule_definitions"][
                item["schedule_id"]
            ].update(status="RETIRED"),
            lambda changed, item: changed["world_state"]["aircraft"][
                item["planned_aircraft_id"]
            ].update(aircraft_id="wrong-aircraft"),
            lambda changed, item: changed["world_state"]["airports"][
                item["destination_airport_id"]
            ].update(airport_id="wrong-airport"),
        )
        for mutation in identity_mutations:
            with self.subTest(mutation=mutation):
                changed = deepcopy(world)
                changed_flight = changed["world_state"]["dated_flights"][flight_id]
                mutation(changed, changed_flight)
                self.assertEqual(discover_active_market_ids(changed), ())

        duplicated = deepcopy(world)
        duplicate = deepcopy(flight)
        duplicate["dated_flight_id"] = "dated_flight-duplicate"
        duplicated["world_state"]["dated_flights"][
            "dated_flight-duplicate"
        ] = duplicate
        self.assertEqual(discover_active_market_ids(duplicated), ())

    def test_remaining_capacity_is_not_an_activation_input(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        market_id, flight_id = _publish_direct_service(world, ids, "DVO")
        runtime_decorated = deepcopy(world)
        runtime_decorated["world_state"]["dated_flights"][flight_id][
            "remaining_capacity"
        ] = 0

        self.assertEqual(
            discover_active_market_ids(runtime_decorated), (market_id,)
        )

    def test_ineligible_or_closed_airport_service_is_not_active_demand_work(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        _market_id, _flight_id = _publish_direct_service(world, ids, "DVO")

        revised = revise_demand_model(
            world,
            airport_updates={
                ids["DVO"]: {"active_until_date": "2026-08-20"},
            },
            universe_date="2026-08-20",
        )

        self.assertTrue(revised.succeeded, revised.issues)
        self.assertEqual(discover_active_market_ids(world), ())

    def test_window_opening_creates_no_backlog_and_deactivation_is_future_only(self):
        world, ids = make_demand_world(("MNL", "DVO"))
        indexes = calculate_world_demand(world).indexes
        market_id, flight_id = _publish_direct_service(world, ids, "DVO")
        before_baseline = indexes.by_market[market_id].base_daily_bookers
        opened_indexes = calculate_world_demand(world, indexes=indexes).indexes

        historical = resolve_active_daily_cohorts(
            world, "2026-08-19", indexes=indexes
        )
        current = resolve_active_daily_cohorts(
            world, "2026-08-20", indexes=indexes
        )
        stored = deepcopy(
            world["world_state"]["demand_state"]["processed_cohorts"]
        )
        world["simulation"]["time_utc"] = "2026-08-21T00:00:00Z"
        world["world_state"]["dated_flights"][flight_id]["status"] = "CANCELLED"
        future = resolve_active_daily_cohorts(world, "2026-08-21")

        self.assertFalse(historical.succeeded)
        self.assertEqual(
            opened_indexes.normalization_by_origin,
            indexes.normalization_by_origin,
        )
        self.assertEqual(opened_indexes.source_fingerprint, indexes.source_fingerprint)
        self.assertTrue(current.succeeded)
        self.assertEqual(tuple(item.market_id for item in current.cohorts), (market_id,))
        self.assertFalse(any(key.endswith("@2026-08-19") for key in stored))
        self.assertTrue(future.succeeded)
        self.assertEqual(future.cohorts, ())
        self.assertEqual(
            world["world_state"]["demand_state"]["processed_cohorts"], stored
        )
        self.assertEqual(
            calculate_world_demand(world).indexes.by_market[market_id].base_daily_bookers,
            before_baseline,
        )

    def test_activation_never_rerolls_other_markets_or_creates_booking_state(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"), seed=72)
        dvo_market, dvo_flight = _publish_direct_service(world, ids, "DVO")
        ceb_market, _ = _publish_direct_service(
            world, ids, "CEB", registration="RP-C4512"
        )
        both = deepcopy(world)
        one = deepcopy(world)
        one["world_state"]["dated_flights"][dvo_flight]["status"] = "CANCELLED"

        both_result = resolve_active_daily_cohorts(both, "2026-08-20")
        one_result = resolve_active_daily_cohorts(one, "2026-08-20")
        both_record = both["world_state"]["demand_state"]["processed_cohorts"][
            f"{ceb_market}@2026-08-20"
        ]
        one_record = one["world_state"]["demand_state"]["processed_cohorts"][
            f"{ceb_market}@2026-08-20"
        ]

        self.assertEqual(
            tuple(item.market_id for item in both_result.cohorts),
            tuple(sorted((dvo_market, ceb_market))),
        )
        self.assertEqual(tuple(item.market_id for item in one_result.cohorts), (ceb_market,))
        self.assertEqual(both_record, one_record)
        self.assertEqual(one["world_state"]["bookings"], {})
        self.assertEqual(one["world_state"]["itineraries"], {})

    def test_active_resolution_is_atomic_detached_and_idempotent(self):
        world, ids = make_demand_world(("MNL", "DVO", "CEB"), seed=91)
        dvo_market, _ = _publish_direct_service(world, ids, "DVO")
        _publish_direct_service(world, ids, "CEB", registration="RP-C4591")
        before_failure = deepcopy(world)
        original = demand_model._cohort_record
        calls = 0

        def fail_after_one(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ArithmeticError("injected active-resolution failure")
            return original(*args, **kwargs)

        with patch("game.demand.model._cohort_record", side_effect=fail_after_one):
            failed = resolve_active_daily_cohorts(world, "2026-08-20")
        self.assertFalse(failed.succeeded)
        self.assertEqual(world, before_failure)

        multipliers = {dvo_market: {"holiday": 12_000}}
        first = resolve_active_daily_cohorts(
            world, "2026-08-20", multipliers_by_market=multipliers
        )
        committed = deepcopy(world)
        multipliers[dvo_market]["holiday"] = 1
        second = resolve_active_daily_cohorts(
            world,
            "2026-08-20",
            multipliers_by_market={dvo_market: {"holiday": 1}},
        )

        self.assertTrue(first.succeeded, first.issues)
        self.assertTrue(second.succeeded, second.issues)
        self.assertTrue(all(item.reused for item in second.cohorts))
        self.assertEqual(world, committed)
        stored = world["world_state"]["demand_state"]["processed_cohorts"][
            f"{dvo_market}@2026-08-20"
        ]
        self.assertEqual(stored["daily_multipliers_bps"]["holiday"], 12_000)
        with self.assertRaises(FrozenInstanceError):
            second.cohorts[0].actual_daily_bookers = -1

    def test_provider_failures_and_mutations_cannot_change_authority(self):
        world, _ids = make_demand_world(("MNL", "DVO"))
        calculate_world_demand(world)

        class MutatingProvider:
            def active_market_ids(
                self, envelope, window, *, dated_flight_indexes=None
            ):
                envelope["ui_state"]["selected_screen"] = "provider-mutation"
                return ()

        clean_before = deepcopy(world)
        clean = resolve_active_daily_cohorts(
            world,
            "2026-08-20",
            activation_providers=(MutatingProvider(),),
        )
        self.assertTrue(clean.succeeded, clean.issues)
        self.assertEqual(world, clean_before)

        class FailingProvider:
            def active_market_ids(self, *args, **kwargs):
                raise RuntimeError("provider failed")

        failed_before = deepcopy(world)
        failed = resolve_active_daily_cohorts(
            world,
            "2026-08-20",
            activation_providers=(FailingProvider(),),
        )
        self.assertFalse(failed.succeeded)
        self.assertEqual(world, failed_before)

        malformed = deepcopy(world)
        malformed["simulation"]["time_utc"] = None
        malformed_before = deepcopy(malformed)
        rejected = resolve_active_daily_cohorts(malformed, "2026-08-20")
        self.assertFalse(rejected.succeeded)
        self.assertEqual(malformed, malformed_before)

    def test_processed_cohort_compatibility_command_remains_available(self):
        world, _ids = make_demand_world(("MNL", "DVO", "CEB"))
        indexes = calculate_world_demand(world).indexes

        result = resolve_world_daily_cohorts(
            world, "2026-08-20", indexes=indexes
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(len(result.cohorts), 6)
        self.assertEqual(
            len(world["world_state"]["demand_state"]["processed_cohorts"]), 6
        )


def _scale_world(airport_count):
    world = create_new_world(
        ceo_display_name="Scale",
        airline_display_name="Scale Air",
        starting_airport=airport_reference(
            "A000",
            population=100_000,
            coordinates={"lat": -45, "lon": -170},
            destination_type="NORMAL_CITY",
            opened="1950-01-01",
        ),
        difficulty="Normal",
        simulation_time_utc="2026-08-20T00:00:00Z",
        simulation_seed=123,
        starting_money=1,
    )
    airports = world["world_state"]["airports"]
    template = deepcopy(next(iter(airports.values())))
    for number in range(1, airport_count):
        airport_id = f"airport-{number + 1:012d}"
        airport = deepcopy(template)
        airport.update(
            airport_id=airport_id,
            reference_code=f"A{number:04d}",
            display_name=f"Scale Airport {number}",
            iata_code=None,
            icao_code=None,
            population=100_000 + number,
            latitude_microdegrees=-45_000_000 + (number % 90) * 1_000_000,
            longitude_microdegrees=-170_000_000 + (number % 170) * 2_000_000,
        )
        airports[airport_id] = airport
    world["deterministic_state"]["id_allocator"]["next_by_type"]["airport"] = (
        airport_count + 1
    )
    world["world_state"]["demand_state"]["input_fingerprint"] = (
        calculate_demand_input_fingerprint(world)
    )
    return world


def _deep_size(value, seen=None):
    seen = set() if seen is None else seen
    marker = id(value)
    if marker in seen:
        return 0
    seen.add(marker)
    total = sys.getsizeof(value)
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, dict):
        return total + sum(
            _deep_size(key, seen) + _deep_size(item, seen)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list, set, frozenset)):
        return total + sum(_deep_size(item, seen) for item in value)
    if hasattr(value, "__dict__"):
        return total + _deep_size(vars(value), seen)
    return total


def measure_compact_scale(airport_count):
    world = _scale_world(airport_count)
    started = perf_counter()
    validation = validate_world(world)
    validation_seconds = perf_counter() - started
    started = perf_counter()
    fingerprint = calculate_demand_input_fingerprint(world)
    fingerprint_seconds = perf_counter() - started
    started = perf_counter()
    demand_model._source_fingerprint(world)
    empty_source_fingerprint_seconds = perf_counter() - started
    started = perf_counter()
    normalizations = demand_model._derive_origin_normalizations(world)
    initialization_seconds = perf_counter() - started
    compact_bytes = _deep_size(normalizations)

    airports = world["world_state"]["airports"]
    configuration = world["simulation"]["configuration"]["demand"]
    airport_ids = tuple(sorted(airports))
    samples = min(100, airport_count - 1)
    started = perf_counter()
    for offset in range(1, samples + 1):
        demand_model._pair_demand_from_compact_derivation(
            market_id=f"market-{offset:012d}",
            origin_airport_id=airport_ids[0],
            destination_airport_id=airport_ids[offset],
            airports=airports,
            configuration=configuration,
            normalization_by_origin=normalizations,
        )
    pair_seconds = perf_counter() - started

    airline_id = world["world_state"]["player"]["primary_airline_id"]
    pair_count = airport_count * (airport_count - 1)
    sampled_market_count = min(10_000, pair_count)
    market_number = 0
    for origin_id in airport_ids:
        for destination_id in airport_ids:
            if origin_id == destination_id:
                continue
            market_number += 1
            market_id = f"market-{market_number:012d}"
            world["world_state"]["directional_markets"][market_id] = {
                "market_id": market_id,
                "origin_airport_id": origin_id,
                "destination_airport_id": destination_id,
            }
            if market_number == sampled_market_count:
                break
        if market_number == sampled_market_count:
            break
    world["deterministic_state"]["id_allocator"]["next_by_type"]["market"] = (
        sampled_market_count + 1
    )
    started = perf_counter()
    sampled_validation = validate_world(world)
    sampled_market_validation_seconds = perf_counter() - started
    started = perf_counter()
    demand_model._source_fingerprint(world)
    sampled_source_fingerprint_seconds = perf_counter() - started
    scale = pair_count / sampled_market_count
    estimated_full_validation_seconds = validation_seconds + max(
        0.0, sampled_market_validation_seconds - validation_seconds
    ) * scale
    estimated_full_source_fingerprint_seconds = empty_source_fingerprint_seconds + max(
        0.0,
        sampled_source_fingerprint_seconds - empty_source_fingerprint_seconds,
    ) * scale

    active_count = min(100, airport_count - 1)
    for offset in range(1, active_count + 1):
        market_id = f"market-{offset:012d}"
        connection_id = f"connection-{offset:012d}"
        aircraft_id = f"aircraft-{offset:012d}"
        schedule_id = f"schedule-{offset:012d}"
        flight_id = f"dated_flight-{offset:012d}"
        destination_id = airport_ids[offset]
        world["world_state"]["directional_markets"][market_id] = {
            "market_id": market_id,
            "origin_airport_id": airport_ids[0],
            "destination_airport_id": destination_id,
        }
        world["world_state"]["connections"][connection_id] = {
            "connection_id": connection_id,
            "airline_id": airline_id,
            "market_id": market_id,
            "status": "ACTIVE",
        }
        world["world_state"]["aircraft"][aircraft_id] = {
            "aircraft_id": aircraft_id,
            "airline_id": airline_id,
        }
        departure = datetime(2026, 8, 21, tzinfo=timezone.utc) + timedelta(
            seconds=offset
        )
        arrival = departure + timedelta(hours=1)
        origin_zone = load_named_timezone(airports[airport_ids[0]]["timezone"])
        destination_zone = load_named_timezone(airports[destination_id]["timezone"])
        departure_local = departure.astimezone(origin_zone)
        arrival_local = arrival.astimezone(destination_zone)
        revision = {
            "revision": 1,
            "connection_id": connection_id,
            "planned_aircraft_id": aircraft_id,
            "origin_airport_id": airport_ids[0],
            "destination_airport_id": destination_id,
            "service_type": "PASSENGER",
            "capacity": 1,
            "fare_offer": {"currency": "USD", "amount_minor": 1},
            "passenger_service_classification": "ECONOMY",
            "recurrence": {
                "frequency": "WEEKLY",
                "weekdays": [arrival_local.weekday()],
                "departure_local_time": departure_local.strftime("%H:%M:%S"),
                "departure_local_fold": departure_local.fold,
                "arrival_local_time": arrival_local.strftime("%H:%M:%S"),
                "arrival_local_fold": arrival_local.fold,
                "arrival_day_offset": (
                    arrival_local.date() - departure_local.date()
                ).days,
            },
            "effective_from_local_date": departure_local.date().isoformat(),
            "effective_until_local_date": None,
        }
        world["world_state"]["schedule_definitions"][schedule_id] = {
            "schedule_id": schedule_id,
            "airline_id": airline_id,
            "status": "ACTIVE",
            "current_revision": 1,
            "revisions": {"1": revision},
        }
        world["world_state"]["dated_flights"][flight_id] = {
            "dated_flight_id": flight_id,
            "occurrence_key": (
                f"{schedule_id}@{departure_local.date().isoformat()}"
            ),
            "schedule_id": schedule_id,
            "schedule_revision": 1,
            "airline_id": airline_id,
            "connection_id": connection_id,
            "planned_aircraft_id": aircraft_id,
            "origin_airport_id": airport_ids[0],
            "destination_airport_id": destination_id,
            "service_type": "PASSENGER",
            "passenger_service_classification": "ECONOMY",
            "scheduled_departure_local_date": departure_local.date().isoformat(),
            "scheduled_off_block_utc": departure.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scheduled_in_block_utc": arrival.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "capacity": 1,
            "fare_offer": {"currency": "USD", "amount_minor": 1},
            "status": "PLANNED",
            "published_at_utc": "2026-08-20T00:00:00Z",
            "superseded_by_schedule_revision": None,
        }
    started = perf_counter()
    active = DirectPublishedServiceActivationProvider().active_market_ids(
        world,
        demand_model_activation_window(),
    )
    discovery_seconds = perf_counter() - started
    sample_pair = demand_model._pair_demand_from_compact_derivation(
        market_id="sample",
        origin_airport_id=airport_ids[0],
        destination_airport_id=airport_ids[1],
        airports=airports,
        configuration=configuration,
        normalization_by_origin=normalizations,
    )
    rich_pair_estimate_bytes = _deep_size(sample_pair) * airport_count * (
        airport_count - 1
    )
    return {
        "airports": airport_count,
        "directional_pairs": pair_count,
        "compact_normalization_bytes": compact_bytes,
        "estimated_rich_pair_bytes": rich_pair_estimate_bytes,
        "initialization_seconds": initialization_seconds,
        "on_demand_100_pairs_seconds": pair_seconds,
        "sparse_100_market_discovery_seconds": discovery_seconds,
        "validation_seconds": validation_seconds,
        "input_fingerprint_seconds": fingerprint_seconds,
        "sampled_market_count": sampled_market_count,
        "sampled_market_validation_seconds": sampled_market_validation_seconds,
        "sampled_source_fingerprint_seconds": sampled_source_fingerprint_seconds,
        "estimated_full_market_validation_seconds": estimated_full_validation_seconds,
        "estimated_full_source_fingerprint_seconds": (
            estimated_full_source_fingerprint_seconds
        ),
        "active_pairs": len(active),
        "fingerprint": fingerprint,
        "valid": validation.is_valid,
        "sampled_market_world_valid": sampled_validation.is_valid,
    }


def demand_model_activation_window():
    from game.demand import ActivationWindow

    return ActivationWindow("2026-08-20T00:00:00Z", "2026-08-30T00:00:00Z")


class CompactDemandScaleTests(unittest.TestCase):
    def test_250_airport_full_authority_cost_is_measured_directly(self):
        world = _scale_world(250)
        started = perf_counter()
        built = calculate_world_demand(world)
        build_seconds = perf_counter() - started
        started = perf_counter()
        validation = validate_world(world)
        validation_seconds = perf_counter() - started
        started = perf_counter()
        demand_model._source_fingerprint(world)
        fingerprint_seconds = perf_counter() - started
        actual_market_bytes = _deep_size(
            world["world_state"]["directional_markets"]
        )
        compact_bytes = _deep_size(built.indexes.normalization_by_origin)

        self.assertTrue(built.succeeded, built.issues)
        self.assertTrue(validation.is_valid, validation.errors)
        self.assertEqual(
            len(world["world_state"]["directional_markets"]), 250 * 249
        )
        self.assertGreater(actual_market_bytes, compact_bytes * 20)
        self.assertLess(build_seconds, 30.0)
        self.assertLess(validation_seconds, 10.0)
        self.assertLess(fingerprint_seconds, 10.0)

    def test_250_500_and_1000_airport_compact_scale_gates(self):
        for count in (250, 500, 1_000):
            with self.subTest(airports=count):
                diagnostics = measure_compact_scale(count)
                self.assertTrue(diagnostics["valid"])
                self.assertTrue(diagnostics["sampled_market_world_valid"])
                self.assertEqual(diagnostics["active_pairs"], 100)
                self.assertLess(
                    diagnostics["compact_normalization_bytes"],
                    diagnostics["estimated_rich_pair_bytes"] // 20,
                )
                self.assertLess(diagnostics["initialization_seconds"], 120.0)
                self.assertLess(diagnostics["on_demand_100_pairs_seconds"], 10.0)
                self.assertLess(
                    diagnostics["sparse_100_market_discovery_seconds"], 10.0
                )
                self.assertLess(diagnostics["validation_seconds"], 20.0)
                self.assertLess(diagnostics["input_fingerprint_seconds"], 20.0)
                self.assertLess(
                    diagnostics["estimated_full_market_validation_seconds"], 120.0
                )
                self.assertLess(
                    diagnostics["estimated_full_source_fingerprint_seconds"],
                    120.0,
                )
                self.assertEqual(len(diagnostics["fingerprint"]), 64)


if __name__ == "__main__":
    unittest.main()
