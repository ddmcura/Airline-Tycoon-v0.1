import json
import statistics
import time
import unittest
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, ROUND_DOWN, localcontext
from pathlib import Path
from types import MappingProxyType

from game.demand import (
    activate_model4,
    calculate_world_demand,
    project_model4_origin,
    project_model4_pair,
    rebuild_model4_indexes,
    recalculate_origin_demand,
    resolve_active_daily_cohorts,
    resolve_daily_cohort,
    resolve_world_daily_cohorts,
    revise_demand_model,
)
from game.world_state import add_airport_reference, migrate_schema_1_to_2, validate_world
from game.world_state import create_new_world
from game.world_state.schema import (
    MODEL3_PROCESSED_COHORT_V1,
    MODEL4_TRAVEL_SCOPE_COHORT_V1,
)
from game.world_state.demand_fingerprint import (
    calculate_model4_cohort_fingerprint,
    calculate_model4_input_fingerprint,
    calculate_model4_revision_context_fingerprint,
)
from tests.test_stage1_demand_model4_foundation import (
    airport,
    foundation_snapshot,
    make_schema1_world,
)
from tests.test_stage1_compact_demand import _publish_direct_service
from tests.test_stage1_compact_demand import _deep_size, _scale_world
from game.demand.model4 import _conserved_allocations, _country_raw_score, _source_fingerprint as _model4_source_fingerprint
from game.demand.model import _distance_km


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def nearest_rank_percentile(values, percentile):
    """Return the deterministic nearest-rank percentile from sorted values."""
    if not values or not 1 <= percentile <= 100:
        raise ValueError("nearest-rank percentile requires values and 1..100")
    ordered = sorted(values)
    rank = max(1, (len(ordered) * percentile + 99) // 100)
    return ordered[rank - 1]


def model4_world(*, profile=None, model3_marker=False, empty_rest=False):
    world = make_schema1_world()
    add_airport_reference(world, airport("DVO", "PH", 1_230_000, 7.1255, 125.6458))
    snapshot = foundation_snapshot(world)
    snapshot["regions"]["region-000000000002"] = {
        "region_id": "region-000000000002",
        "external_reference_code": "NAM",
        "display_name": "North America",
    }
    snapshot["countries"]["country-000000000001"].update(
        population=115_000_000,
        centroid_latitude_microdegrees=13_000_000,
        centroid_longitude_microdegrees=122_000_000,
    )
    snapshot["countries"]["country-000000000002"].update(
        population=6_000_000,
        centroid_latitude_microdegrees=1_350_000,
        centroid_longitude_microdegrees=103_820_000,
    )
    snapshot["countries"]["country-000000000003"] = {
        "country_id": "country-000000000003",
        "region_id": "region-000000000001",
        "external_reference_code": "VN",
        "display_name": "Vietnam",
        "effective_from_date": None,
        "effective_until_date": None,
        "demand_attractiveness_bps": 10_000,
        "relationship_weight_bps": 10_000,
        "population": 101_000_000,
        "centroid_latitude_microdegrees": 16_000_000,
        "centroid_longitude_microdegrees": 108_000_000,
    }
    if not empty_rest:
        snapshot["countries"]["country-000000000004"] = {
            "country_id": "country-000000000004",
            "region_id": "region-000000000002",
            "external_reference_code": "US",
            "display_name": "United States",
            "effective_from_date": None,
            "effective_until_date": None,
            "demand_attractiveness_bps": 10_000,
            "relationship_weight_bps": 10_000,
            "population": 340_000_000,
            "centroid_latitude_microdegrees": 39_828_300,
            "centroid_longitude_microdegrees": -98_579_500,
        }
    migration = migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
    if not migration.succeeded:
        raise AssertionError(migration.issues)
    if profile is not None:
        world["simulation"]["configuration"]["demand"]["travel_scope_configuration"]["country_overrides"]["country-000000000001"] = profile
    build = calculate_world_demand(world)
    if not build.succeeded:
        raise AssertionError(build.issues)
    old = None
    if model3_marker:
        market_id = build.indexes.market_by_pair[(
            next(key for key, value in world["world_state"]["airports"].items() if value["reference_code"] == "MNL"),
            next(key for key, value in world["world_state"]["airports"].items() if value["reference_code"] == "DVO"),
        )]
        resolve_daily_cohort(world, market_id, "2026-08-20", multipliers={"world": 12_000})
        old = deepcopy(world["world_state"]["demand_state"]["processed_cohorts"][f"{market_id}@2026-08-20"])
    revision = world["world_state"]["demand_state"]["demand_model_revision"]
    result = activate_model4(world, expected_revision=revision)
    if not result.succeeded:
        raise AssertionError(result.issues)
    ids = {record["reference_code"]: airport_id for airport_id, record in world["world_state"]["airports"].items()}
    return world, ids, old


def measure_model4_scale(airport_count, *, full_authority=False, active_markets=0):
    world = _scale_world(airport_count)
    if full_authority:
        calculate_world_demand(world)
    airports = world["world_state"]["airports"]
    snapshot = {
        "snapshot_version": "model4-scale-v1",
        "regions": {"region-000000000001": {"region_id": "region-000000000001", "external_reference_code": "SCALE", "display_name": "Scale"}},
        "countries": {"country-000000000001": {"country_id": "country-000000000001", "region_id": "region-000000000001", "external_reference_code": "PH", "display_name": "Scale Country", "effective_from_date": None, "effective_until_date": None, "demand_attractiveness_bps": 10_000, "relationship_weight_bps": 10_000, "population": 1_000_000_000, "centroid_latitude_microdegrees": 0, "centroid_longitude_microdegrees": 0}},
        "airport_country_ids": {airport_id: "country-000000000001" for airport_id in airports},
        "airport_demand_allocation_members": {airport_id: True for airport_id in airports},
    }
    migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
    revision = world["world_state"]["demand_state"]["demand_model_revision"]
    started = time.perf_counter()
    activation = activate_model4(world, expected_revision=revision)
    activation_seconds = time.perf_counter() - started
    if not activation.succeeded:
        raise AssertionError(activation.issues)
    started = time.perf_counter()
    validation = validate_world(world)
    validation_seconds = time.perf_counter() - started
    started = time.perf_counter()
    calculate_model4_input_fingerprint(world)
    fingerprint_seconds = time.perf_counter() - started
    started = time.perf_counter()
    _model4_source_fingerprint(world)
    source_fingerprint_seconds = time.perf_counter() - started
    started = time.perf_counter()
    indexes = rebuild_model4_indexes(world)
    derivation_seconds = time.perf_counter() - started
    resolution_seconds = None
    if active_markets:
        market_ids = tuple(sorted(world["world_state"]["directional_markets"]))[:active_markets]

        class Provider:
            def active_market_ids(self, *_args, **_kwargs):
                return market_ids

        started = time.perf_counter()
        result = resolve_active_daily_cohorts(
            world,
            "2026-08-20",
            indexes=indexes,
            activation_providers=(Provider(),),
        )
        resolution_seconds = time.perf_counter() - started
        if not result.succeeded:
            raise AssertionError(result.issues)
    markets = world["world_state"]["directional_markets"]
    return {
        "airports": airport_count,
        "markets": len(markets),
        "activation_seconds": activation_seconds,
        "derivation_seconds": derivation_seconds,
        "validation_seconds": validation_seconds,
        "fingerprint_seconds": fingerprint_seconds,
        "source_fingerprint_seconds": source_fingerprint_seconds,
        "compact_bytes": _deep_size(indexes),
        "authoritative_market_object_bytes": _deep_size(markets),
        "authoritative_market_json_bytes": len(
            json.dumps(markets, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "world_json_bytes": len(canonical_bytes(world)),
        "active_resolution_seconds": resolution_seconds,
        "validation_valid": validation.is_valid,
    }


def measure_philippines_calibration():
    source = json.loads((Path(__file__).parents[1] / "Data" / "Airports" / "Asia" / "PH.json").read_text(encoding="utf-8"))["PH"]["airports"]
    references = []
    for record in source:
        reference = deepcopy(record)
        reference["timezone"] = "Asia/Manila"
        reference["country_reference"] = "PH"
        references.append(reference)
    world = create_new_world(ceo_display_name="Calibration", airline_display_name="Calibration Air", starting_airport=references[0], difficulty="Normal", simulation_time_utc="2026-08-20T00:00:00Z", simulation_seed=44, starting_money="1000000.00")
    for reference in references[1:]:
        add_airport_reference(world, reference)
    airports = world["world_state"]["airports"]
    snapshot = {
        "snapshot_version": "ph-alpha-calibration-v1",
        "regions": {"region-000000000001": {"region_id": "region-000000000001", "external_reference_code": "SEA", "display_name": "Southeast Asia"}},
        "countries": {
            "country-000000000001": {"country_id": "country-000000000001", "region_id": "region-000000000001", "external_reference_code": "PH", "display_name": "Philippines", "effective_from_date": None, "effective_until_date": None, "demand_attractiveness_bps": 10_000, "relationship_weight_bps": 10_000, "population": 115_000_000, "centroid_latitude_microdegrees": 13_000_000, "centroid_longitude_microdegrees": 122_000_000},
            "country-000000000002": {"country_id": "country-000000000002", "region_id": "region-000000000001", "external_reference_code": "VN", "display_name": "Vietnam", "effective_from_date": None, "effective_until_date": None, "demand_attractiveness_bps": 10_000, "relationship_weight_bps": 10_000, "population": 101_000_000, "centroid_latitude_microdegrees": 16_000_000, "centroid_longitude_microdegrees": 108_000_000},
        },
        "airport_country_ids": {airport_id: "country-000000000001" for airport_id in airports},
        "airport_demand_allocation_members": {airport_id: True for airport_id in airports},
    }
    migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
    calculate_world_demand(world)
    revision = world["world_state"]["demand_state"]["demand_model_revision"]
    started = time.perf_counter()
    activate_model4(world, expected_revision=revision)
    activation_seconds = time.perf_counter() - started
    ids = {record["reference_code"]: airport_id for airport_id, record in world["world_state"]["airports"].items()}
    projection = project_model4_origin(world, ids["MNL"])
    values = sorted(projection["airport_leaf_amounts"].values())
    selected = {code: project_model4_pair(world, ids["MNL"], ids[code])["base_daily_bookers"] for code in ("CEB", "DVO", "CRK")}
    selected["MNL_origin_pool"] = projection["origin_daily_booking_pool"]
    origin_pools = {}
    selected_distributions = {}
    for code, airport_id in sorted(ids.items()):
        origin_projection = project_model4_origin(world, airport_id)
        origin_pools[code] = str(origin_projection["origin_daily_booking_pool"])
        if code in {"MNL", "CEB", "DVO", "CRK"}:
            outgoing = sorted(origin_projection["airport_leaf_amounts"].values())
            selected_distributions[code] = {
                "median": str(statistics.median(outgoing)),
                "lower_percentile": str(nearest_rank_percentile(outgoing, 10)),
                "lower_percentile_method": "nearest-rank P10",
                "domestic_total": str(sum(outgoing, Decimal(0))),
            }
    return {
        "airport_count": len(ids),
        "activation_seconds": activation_seconds,
        "origin_pool": str(projection["origin_daily_booking_pool"]),
        "domestic_envelope": str(projection["scope_amounts"]["DOMESTIC"]),
        "median_pair": str(statistics.median(values)),
        "lower_percentile_pair": str(nearest_rank_percentile(values, 10)),
        "lower_percentile_method": "nearest-rank P10",
        "selected": {key: str(value) for key, value in selected.items()},
        "origin_pools": origin_pools,
        "selected_origin_distributions": selected_distributions,
        "latent_vietnam": str(projection["country_amounts"]["country-000000000002"]),
        "conservation_total": str(projection["conservation_total"]),
    }


class Model4ActivationTests(unittest.TestCase):
    def test_atomic_activation_revision_context_and_terminal_revision(self):
        world, _ids, _old = model4_world()
        demand = world["world_state"]["demand_state"]
        self.assertEqual(demand["model3_terminal_demand_revision"], demand["demand_model_revision"] - 1)
        self.assertEqual(world["simulation"]["configuration"]["demand"]["model_version"], 4)
        context = next(iter(demand["model4_revision_contexts"].values()))
        self.assertEqual(context["demand_model_revision"], demand["demand_model_revision"])
        self.assertEqual(context["model4_input_fingerprint"], demand["input_fingerprint"])
        self.assertTrue(validate_world(world).is_valid)

    def test_stale_repeated_and_provider_failure_are_atomic(self):
        world = make_schema1_world()
        snapshot = foundation_snapshot(world)
        for country in snapshot["countries"].values():
            country.update(population=1_000_000, centroid_latitude_microdegrees=0, centroid_longitude_microdegrees=0)
        migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
        calculate_world_demand(world)
        before = canonical_bytes(world)
        stale = activate_model4(world, expected_revision=0)
        self.assertEqual(stale.issues[0].code, "STALE_REVISION")
        self.assertEqual(canonical_bytes(world), before)

        def failing_provider(candidate):
            candidate["ui_state"].clear()
            raise RuntimeError("phase failure")

        failed = activate_model4(
            world,
            expected_revision=world["world_state"]["demand_state"]["demand_model_revision"],
            activation_provider=failing_provider,
        )
        self.assertEqual(failed.issues[0].code, "DEMAND_ALLOCATION_FAILED")
        self.assertEqual(canonical_bytes(world), before)

        malformed = activate_model4(
            world,
            expected_revision=world["world_state"]["demand_state"]["demand_model_revision"],
            activation_provider=lambda _candidate: {},
        )
        self.assertFalse(malformed.succeeded)
        self.assertEqual(canonical_bytes(world), before)

        build = calculate_world_demand(world)
        market_id = next(iter(build.indexes.by_market))
        resolve_daily_cohort(world, market_id, "2026-08-20")
        with_marker = canonical_bytes(world)

        def deleting_provider(candidate):
            candidate["world_state"]["demand_state"]["processed_cohorts"].clear()

        deleted = activate_model4(
            world,
            expected_revision=world["world_state"]["demand_state"]["demand_model_revision"],
            activation_provider=deleting_provider,
        )
        self.assertFalse(deleted.succeeded)
        self.assertEqual(canonical_bytes(world), with_marker)

    def test_missing_country_inputs_reject_without_inference(self):
        world = make_schema1_world()
        migrate_schema_1_to_2(world, foundation_snapshot=foundation_snapshot(world))
        calculate_world_demand(world)
        before = canonical_bytes(world)
        result = activate_model4(world, expected_revision=world["world_state"]["demand_state"]["demand_model_revision"])
        self.assertEqual(result.issues[0].code, "INVALID_COUNTRY_INPUT")
        self.assertEqual(canonical_bytes(world), before)


class Model4FormulaTests(unittest.TestCase):
    def test_empty_international_scope_remains_fully_latent(self):
        world, ids, _old = model4_world(empty_rest=True)
        projection = project_model4_origin(world, ids["MNL"])
        self.assertEqual(
            projection["latent"]["empty_scope_amounts"]["REST_OF_WORLD_INTERNATIONAL"],
            projection["scope_amounts"]["REST_OF_WORLD_INTERNATIONAL"],
        )
        self.assertEqual(projection["conservation_total"], projection["origin_daily_booking_pool"])

    def test_distance_quantization_extremes_and_residual_ties(self):
        coincident = {"latitude_microdegrees": 0, "longitude_microdegrees": 0}
        antipodal = {"latitude_microdegrees": 0, "longitude_microdegrees": 180_000_000}
        self.assertEqual(_distance_km(coincident, coincident), Decimal("0.000"))
        self.assertEqual(_distance_km(coincident, antipodal), Decimal("20015.087"))
        allocations, normalization = _conserved_allocations(
            Decimal("1"),
            ("country-000000000001", "country-000000000002"),
            (Decimal("1"), Decimal("1")),
            residual_key=lambda identity: identity,
        )
        self.assertEqual(normalization.residual_id, "country-000000000002")
        self.assertEqual(sum(allocations.values(), Decimal(0)), Decimal("1"))
        airport_allocations, airport_normalization = _conserved_allocations(
            Decimal("1"),
            ("airport-000000000001", "airport-000000000002"),
            (Decimal("1"), Decimal("1")),
            residual_key=lambda identity: identity,
        )
        self.assertEqual(airport_normalization.residual_id, "airport-000000000002")
        self.assertEqual(sum(airport_allocations.values(), Decimal(0)), Decimal("1"))

    def test_country_score_neutral_coincident_and_extreme_population(self):
        configuration = {"distance_scale_km": 2000}
        origin = {"centroid_latitude_microdegrees": 0, "centroid_longitude_microdegrees": 0}
        destination = {
            "population": 10**80,
            "centroid_latitude_microdegrees": 0,
            "centroid_longitude_microdegrees": 0,
            "demand_attractiveness_bps": 10_000,
            "relationship_weight_bps": 10_000,
        }
        with localcontext() as context:
            context.prec = 5
            score = _country_raw_score(configuration, origin, destination)
        self.assertTrue(score.is_finite())
        self.assertGreater(score, 0)
    def test_default_scope_country_region_and_leaf_conservation(self):
        world, ids, _old = model4_world()
        projection = project_model4_origin(world, ids["MNL"])
        self.assertEqual(projection["origin_daily_booking_pool"], Decimal("40000"))
        self.assertEqual(projection["scope_amounts"], {
            "DOMESTIC": Decimal("26000"),
            "HOME_REGION_INTERNATIONAL": Decimal("10000"),
            "REST_OF_WORLD_INTERNATIONAL": Decimal("4000"),
        })
        self.assertEqual(projection["country_amounts"]["country-000000000001"], Decimal("26000"))
        self.assertGreater(projection["country_amounts"]["country-000000000003"], 0)
        self.assertEqual(
            projection["region_amounts"]["region-000000000001"],
            sum((value for country_id, value in projection["country_amounts"].items() if country_id != "country-000000000004"), Decimal(0)),
        )
        self.assertEqual(projection["conservation_total"], projection["origin_daily_booking_pool"])
        self.assertGreater(projection["latent"]["unmaterialized_country_amounts"]["country-000000000003"], 0)
        self.assertEqual(
            projection["materialized_leaf_total"]
            + projection["latent"]["airport_leaf_amount"]
            + sum(projection["latent"]["unmaterialized_country_amounts"].values(), Decimal(0))
            + sum(projection["latent"]["empty_scope_amounts"].values(), Decimal(0)),
            projection["origin_daily_booking_pool"],
        )

    def test_profile_fixtures_and_scope_residual_conserve(self):
        for profile, expected in (
            ({"domestic_weight_bps": 6000, "home_region_international_weight_bps": 3000, "rest_of_world_international_weight_bps": 1000}, (24000, 12000, 4000)),
            ({"domestic_weight_bps": 7000, "home_region_international_weight_bps": 2000, "rest_of_world_international_weight_bps": 1000}, (28000, 8000, 4000)),
        ):
            with self.subTest(profile=profile):
                world, ids, _old = model4_world(profile=profile)
                amounts = project_model4_origin(world, ids["MNL"])["scope_amounts"]
                self.assertEqual(tuple(amounts.values()), tuple(map(Decimal, expected)))
                self.assertEqual(sum(amounts.values(), Decimal(0)), Decimal("40000"))

    def test_pair_baseline_is_leaf_and_projection_is_detached(self):
        world, ids, _old = model4_world()
        origin = project_model4_origin(world, ids["MNL"])
        pair = project_model4_pair(world, ids["MNL"], ids["DVO"])
        self.assertEqual(pair["base_daily_bookers"], origin["airport_leaf_amounts"][ids["DVO"]])
        self.assertEqual(pair["diagnostic_pair_share"], pair["base_daily_bookers"] / origin["origin_daily_booking_pool"])
        origin["scope_amounts"].clear()
        self.assertTrue(project_model4_origin(world, ids["MNL"])["scope_amounts"])

    def test_dictionary_order_and_low_decimal_precision_are_exact(self):
        left, ids, _old = model4_world()
        right = deepcopy(left)
        right["world_state"]["countries"] = dict(reversed(tuple(right["world_state"]["countries"].items())))
        right["world_state"]["regions"] = dict(reversed(tuple(right["world_state"]["regions"].items())))
        expected = project_model4_origin(left, ids["MNL"])
        with localcontext() as context:
            context.prec = 6
            context.rounding = ROUND_DOWN
            context.Emin = -2
            context.Emax = 2
            left_projection = project_model4_origin(left, ids["MNL"])
            right_projection = project_model4_origin(right, ids["MNL"])
        self.assertEqual(left_projection, expected)
        self.assertEqual(left_projection, right_projection)

    def test_model4_origin_recalculation_uses_model4_origin_ids(self):
        world, ids, _old = model4_world()
        result = recalculate_origin_demand(world, ids["MNL"])
        self.assertTrue(result.succeeded)
        self.assertIn(ids["MNL"], result.indexes.origin_airport_ids)

    def test_closed_leaf_is_latent_without_redistribution_and_reopens_exactly(self):
        world, ids, _old = model4_world()
        before = project_model4_pair(world, ids["MNL"], ids["DVO"])["base_daily_bookers"]
        revision = world["world_state"]["demand_state"]["demand_model_revision"]
        closed = revise_demand_model(world, expected_revision=revision, airport_updates={ids["DVO"]: {"active_until_date": "2026-08-20"}})
        self.assertTrue(closed.succeeded, closed.issues)
        closed_projection = project_model4_origin(world, ids["MNL"])
        self.assertEqual(project_model4_pair(world, ids["MNL"], ids["DVO"])["base_daily_bookers"], before)
        self.assertGreater(closed_projection["latent"]["unavailable_airport_leaf_amount"], 0)
        self.assertGreater(closed_projection["latent"]["airport_leaf_amount"], 0)
        self.assertEqual(
            closed_projection["materialized_leaf_total"]
            + closed_projection["latent"]["airport_leaf_amount"]
            + sum(closed_projection["latent"]["unmaterialized_country_amounts"].values(), Decimal(0))
            + sum(closed_projection["latent"]["empty_scope_amounts"].values(), Decimal(0)),
            closed_projection["origin_daily_booking_pool"],
        )
        reopened = revise_demand_model(world, expected_revision=closed.revision, airport_updates={ids["DVO"]: {"active_until_date": None}})
        self.assertTrue(reopened.succeeded, reopened.issues)
        self.assertEqual(project_model4_pair(world, ids["MNL"], ids["DVO"])["base_daily_bookers"], before)


class Model4CohortTests(unittest.TestCase):
    def test_active_day_result_exposes_future_booking_boundary_inputs(self):
        world, ids, _old = model4_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids, "DVO")
        result = resolve_active_daily_cohorts(world, "2026-08-24", multipliers_by_market={market_id: {"world": 12_000}})
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.active_market_ids, (market_id,))
        self.assertEqual(result.expected_demand_revision, world["world_state"]["demand_state"]["demand_model_revision"])
        self.assertEqual(result.intents[0].daily_multipliers_bps["world"], 12_000)
        self.assertEqual(result.intents[0].resolved_integer_intent, result.cohorts[0].actual_daily_bookers)

    def test_mixed_model3_reuse_never_replaces_payload(self):
        world, ids, old = model4_world(model3_marker=True)
        market_id = next(market_id for market_id, market in world["world_state"]["directional_markets"].items() if market["origin_airport_id"] == ids["MNL"] and market["destination_airport_id"] == ids["DVO"])
        result = resolve_daily_cohort(world, market_id, "2026-08-20", multipliers={"world": 50_000})
        self.assertTrue(result.reused)
        self.assertEqual(world["world_state"]["demand_state"]["processed_cohorts"][f"{market_id}@2026-08-20"], old)
        self.assertEqual(old["contract"], MODEL3_PROCESSED_COHORT_V1)

    def test_new_v2_marker_reuses_zero_and_detects_corruption(self):
        world, ids, _old = model4_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids, "DVO")
        active = resolve_active_daily_cohorts(world, "2026-08-24", multipliers_by_market={market_id: {"world": 0}})
        first = active.cohorts[0]
        second = resolve_daily_cohort(world, market_id, "2026-08-24", multipliers={"world": 10_000})
        self.assertEqual(first.actual_daily_bookers, 0)
        self.assertTrue(second.reused)
        wrapper = world["world_state"]["demand_state"]["processed_cohorts"][f"{market_id}@2026-08-24"]
        self.assertEqual(wrapper["contract"], MODEL4_TRAVEL_SCOPE_COHORT_V1)
        malformed_world = deepcopy(world)
        malformed_wrapper = malformed_world["world_state"]["demand_state"]["processed_cohorts"][f"{market_id}@2026-08-24"]
        malformed_wrapper["payload"]["daily_multipliers_bps"]["world"] = "invalid"
        malformed_wrapper["payload"]["resolution_fingerprint"] = calculate_model4_cohort_fingerprint(malformed_world, malformed_wrapper)
        self.assertIn("invalid_demand_multipliers", {issue.code for issue in validate_world(malformed_world).errors})
        wrapper["payload"]["actual_daily_bookers"] = 1
        self.assertIn("inconsistent_demand_cohort_fingerprint", {issue.code for issue in validate_world(world).errors})

    def test_context_corruption_missing_context_and_independent_bytes(self):
        left, left_ids, _old = model4_world()
        right, right_ids, _old = model4_world()
        left["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        right["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        left_market, _flight = _publish_direct_service(left, left_ids, "DVO")
        right_market, _flight = _publish_direct_service(right, right_ids, "DVO")
        resolve_active_daily_cohorts(left, "2026-08-24")
        resolve_active_daily_cohorts(right, "2026-08-24")
        self.assertEqual(canonical_bytes(left), canonical_bytes(right))
        extra_context_world = deepcopy(right)
        contexts = extra_context_world["world_state"]["demand_state"]["model4_revision_contexts"]
        extra_context = deepcopy(next(iter(contexts.values())))
        extra_context["revision_context_id"] = "model4-demand-revision-extra"
        extra_context["demand_model_revision"] += 1
        extra_context["context_fingerprint"] = calculate_model4_revision_context_fingerprint(extra_context)
        contexts[extra_context["revision_context_id"]] = extra_context
        self.assertIn("invalid_model4_revision_context", {issue.code for issue in validate_world(extra_context_world).errors})
        context_id = next(iter(left["world_state"]["demand_state"]["model4_revision_contexts"]))
        left["world_state"]["demand_state"]["model4_revision_contexts"][context_id]["context_fingerprint"] = "0" * 64
        self.assertIn("inconsistent_model4_revision_context_fingerprint", {issue.code for issue in validate_world(left).errors})
        right["world_state"]["demand_state"]["model4_revision_contexts"].clear()
        codes = {issue.code for issue in validate_world(right).errors}
        self.assertTrue({"invalid_model4_revision_context", "dangling_reference"} & codes)

    def test_whole_world_compatibility_command_is_rejected_atomically(self):
        world, _ids, _old = model4_world()
        before = canonical_bytes(world)
        result = resolve_world_daily_cohorts(world, "2026-08-20")
        self.assertEqual(result.issues[0].code, "UNSUPPORTED_COMPATIBILITY_COMMAND")
        self.assertEqual(canonical_bytes(world), before)

    def test_unserved_single_pair_cannot_create_model4_marker(self):
        world, ids, _old = model4_world()
        market_id = next(market_id for market_id, market in world["world_state"]["directional_markets"].items() if market["origin_airport_id"] == ids["MNL"] and market["destination_airport_id"] == ids["DVO"])
        before = canonical_bytes(world)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_COMPATIBILITY_COMMAND"):
            resolve_daily_cohort(world, market_id, "2026-08-20")
        self.assertEqual(canonical_bytes(world), before)

    def test_rejected_active_processing_is_atomic(self):
        world, ids, _old = model4_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids, "DVO")
        before = canonical_bytes(world)
        result = resolve_active_daily_cohorts(world, "2026-08-24", multipliers_by_market={"market-unknown": {"world": 10_000}})
        self.assertFalse(result.succeeded)
        self.assertEqual(canonical_bytes(world), before)

    def test_malformed_cache_is_not_reused(self):
        world, _ids, _old = model4_world()
        indexes = rebuild_model4_indexes(world)
        self.assertIs(rebuild_model4_indexes(world, indexes=indexes), indexes)
        altered = deepcopy(world)
        altered["ui_state"]["selected_screen"] = "routes"
        self.assertIs(rebuild_model4_indexes(altered, indexes=indexes), indexes)
        forged_pairs = dict(indexes.market_by_pair)
        first_pair = next(iter(forged_pairs))
        forged_pairs[first_pair] = "market-forged"
        forged = replace(indexes, market_by_pair=MappingProxyType(forged_pairs))
        self.assertIsNot(rebuild_model4_indexes(world, indexes=forged), forged)
        normalization = next(
            iter(next(iter(indexes.normalization_by_origin.values())).airport_normalization_by_country.values())
        )
        object.__setattr__(
            normalization,
            "normalization_denominator",
            normalization.normalization_denominator + Decimal(1),
        )
        self.assertIsNot(rebuild_model4_indexes(world, indexes=indexes), indexes)
        indexes = rebuild_model4_indexes(world)
        first_origin = next(iter(indexes.normalization_by_origin.values()))
        object.__setattr__(first_origin, "origin_daily_booking_pool", Decimal("-1"))
        self.assertIsNot(rebuild_model4_indexes(world, indexes=indexes), indexes)


class Model4CalibrationAndPerformanceTests(unittest.TestCase):
    def test_complete_24_airport_philippines_alpha_calibration_fixture(self):
        source = json.loads((Path(__file__).parents[1] / "Data" / "Airports" / "Asia" / "PH.json").read_text(encoding="utf-8"))["PH"]["airports"]
        references = []
        for record in source:
            reference = deepcopy(record)
            reference["timezone"] = "Asia/Manila"
            reference["country_reference"] = "PH"
            references.append(reference)
        world = create_new_world(
            ceo_display_name="Calibration",
            airline_display_name="Calibration Air",
            starting_airport=references[0],
            difficulty="Normal",
            simulation_time_utc="2026-08-20T00:00:00Z",
            simulation_seed=44,
            starting_money="1000000.00",
        )
        for reference in references[1:]:
            add_airport_reference(world, reference)
        airports = world["world_state"]["airports"]
        snapshot = {
            "snapshot_version": "ph-alpha-calibration-v1",
            "regions": {"region-000000000001": {"region_id": "region-000000000001", "external_reference_code": "SEA", "display_name": "Southeast Asia"}},
            "countries": {
                "country-000000000001": {"country_id": "country-000000000001", "region_id": "region-000000000001", "external_reference_code": "PH", "display_name": "Philippines", "effective_from_date": None, "effective_until_date": None, "demand_attractiveness_bps": 10_000, "relationship_weight_bps": 10_000, "population": 115_000_000, "centroid_latitude_microdegrees": 13_000_000, "centroid_longitude_microdegrees": 122_000_000},
                "country-000000000002": {"country_id": "country-000000000002", "region_id": "region-000000000001", "external_reference_code": "VN", "display_name": "Vietnam", "effective_from_date": None, "effective_until_date": None, "demand_attractiveness_bps": 10_000, "relationship_weight_bps": 10_000, "population": 101_000_000, "centroid_latitude_microdegrees": 16_000_000, "centroid_longitude_microdegrees": 108_000_000},
            },
            "airport_country_ids": {airport_id: "country-000000000001" for airport_id in airports},
            "airport_demand_allocation_members": {airport_id: True for airport_id in airports},
        }
        self.assertTrue(migrate_schema_1_to_2(world, foundation_snapshot=snapshot).succeeded)
        self.assertTrue(calculate_world_demand(world).succeeded)
        revision = world["world_state"]["demand_state"]["demand_model_revision"]
        self.assertTrue(activate_model4(world, expected_revision=revision).succeeded)
        ids = {record["reference_code"]: airport_id for airport_id, record in airports.items()}
        projection = project_model4_origin(world, ids["MNL"])
        domestic_values = sorted(projection["airport_leaf_amounts"].values())
        self.assertEqual(len(source), 24)
        self.assertEqual(len(airports), 24)
        self.assertEqual(len(ids), 24)
        self.assertTrue({"MNL", "CEB", "DVO", "CRK"} <= set(ids))
        self.assertNotIn(ids["MNL"], projection["airport_leaf_amounts"])
        self.assertEqual(projection["origin_daily_booking_pool"], Decimal("54000"))
        self.assertEqual(
            tuple(projection["scope_amounts"].values()),
            (Decimal("35100"), Decimal("13500"), Decimal("5400")),
        )
        self.assertEqual(sum(domestic_values, Decimal(0)), Decimal("35100"))
        self.assertEqual(projection["country_amounts"]["country-000000000002"], Decimal("13500"))
        self.assertEqual(
            projection["latent"]["empty_scope_amounts"]["REST_OF_WORLD_INTERNATIONAL"],
            Decimal("5400"),
        )
        self.assertEqual(projection["conservation_total"], projection["origin_daily_booking_pool"])
        self.assertGreater(statistics.median(domestic_values), 0)
        self.assertGreater(nearest_rank_percentile(domestic_values, 10), 0)

    def test_deterministic_fixture_diagnostics_and_representative_timing(self):
        started = time.perf_counter()
        world, ids, _old = model4_world()
        projection = project_model4_origin(world, ids["MNL"])
        pair_values = sorted(projection["airport_leaf_amounts"].values())
        elapsed = time.perf_counter() - started
        diagnostics = {
            "origin_pool": projection["origin_daily_booking_pool"],
            "domestic_envelope": projection["scope_amounts"]["DOMESTIC"],
            "median_pair": statistics.median(pair_values),
            "lower_pair": pair_values[0],
            "latent_vietnam": projection["country_amounts"]["country-000000000003"],
            "conservation": projection["conservation_total"],
        }
        self.assertGreater(diagnostics["latent_vietnam"], 0)
        self.assertEqual(diagnostics["conservation"], diagnostics["origin_pool"])
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
