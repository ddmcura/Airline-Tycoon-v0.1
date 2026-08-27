"""Milestone 4.5B-3 market-pack lifecycle and activation tests."""

import json
import unittest
from copy import deepcopy
from decimal import Decimal, localcontext

from game.demand import project_model4_origin, project_model4_pair, resolve_active_daily_cohorts
from game.demand import resolve_daily_cohort
from game.demand.model4 import _source_fingerprint as model4_source_fingerprint
from game.world_state import (
    add_airport_reference,
    disable_country_pack,
    enable_country_pack,
    materialize_country_pack,
    migrate_schema_1_to_2,
    validate_world,
)
from game.world_state.demand_fingerprint import (
    calculate_market_pack_fingerprint,
    calculate_model4_input_fingerprint,
    calculate_model4_revision_context_fingerprint,
)
from game.world_state.schema import (
    LEGACY_MARKET_PACK_CONFIGURATION_VERSION,
    MARKET_PACK_CONFIGURATION_VERSION,
    MAX_ENTITY_ID_NUMBER,
)
from tests.test_stage1_compact_demand import _publish_direct_service
from tests.test_stage1_demand_model4 import model4_world
from tests.test_stage1_demand_model4_foundation import foundation_snapshot, make_schema1_world


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def vietnam_catalog():
    return [
        {
            "catalog_airport_id": "VN-SGN",
            "reference_code": "SGN",
            "display_name": "Ho Chi Minh City",
            "timezone": "Asia/Ho_Chi_Minh",
            "population": 9_000_000,
            "latitude_microdegrees": 10_823_000,
            "longitude_microdegrees": 106_630_000,
            "demand_destination_type": "MEGA_GLOBAL_CITY",
        },
        {
            "catalog_airport_id": "VN-HAN",
            "reference_code": "HAN",
            "display_name": "Hanoi",
            "timezone": "Asia/Ho_Chi_Minh",
            "population": 8_000_000,
            "latitude_microdegrees": 21_027_000,
            "longitude_microdegrees": 105_834_000,
            "demand_destination_type": "CAPITAL_MAJOR_CITY",
        },
    ]


def materialized_world(catalog=None):
    world, ids, _old = model4_world()
    country_id = next(
        key
        for key, country in world["world_state"]["countries"].items()
        if country["external_reference_code"] == "VN"
    )
    pack_revision = world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"]
    demand_revision = world["world_state"]["demand_state"]["demand_model_revision"]
    result = materialize_country_pack(
        world,
        country_id,
        "test-southeast-asia-vn",
        "2026.1",
        vietnam_catalog() if catalog is None else catalog,
        expected_pack_revision=pack_revision,
        expected_demand_revision=demand_revision,
    )
    if not result.succeeded:
        raise AssertionError(result.issues)
    ids.update(
        (airport["reference_code"], airport_id)
        for airport_id, airport in world["world_state"]["airports"].items()
    )
    return world, ids, country_id, result


def as_committed_legacy_pack_world(world):
    """Project a current fixture to the exact committed pre-4.5B-3 authority."""
    candidate = deepcopy(world)
    configuration = candidate["simulation"]["configuration"]["demand"]
    pack_revision = configuration["market_pack_configuration"]["revision"]
    configuration["market_pack_configuration"] = {
        "contract": "MARKET_PACK_CONFIGURATION_V1",
        "configuration_version": LEGACY_MARKET_PACK_CONFIGURATION_VERSION,
        "revision": pack_revision,
        "market_pack_ids": [],
    }
    for country in candidate["world_state"]["countries"].values():
        country.pop("airport_allocation_revision")
    demand = candidate["world_state"]["demand_state"]
    demand["input_fingerprint"] = calculate_model4_input_fingerprint(candidate)
    current = next(
        context
        for context in demand["model4_revision_contexts"].values()
        if context["demand_model_revision"] == demand["demand_model_revision"]
    )
    current["market_pack_configuration_version"] = LEGACY_MARKET_PACK_CONFIGURATION_VERSION
    current["market_pack_revision"] = pack_revision
    current["model4_input_fingerprint"] = demand["input_fingerprint"]
    current["context_fingerprint"] = calculate_model4_revision_context_fingerprint(current)
    return candidate


class MarketPackMaterializationTests(unittest.TestCase):
    def test_deterministic_materialization_allocates_sorted_catalog_then_pairs(self):
        left, left_ids, country_id, left_result = materialized_world()
        right, right_ids, _country_id, right_result = materialized_world(list(reversed(vietnam_catalog())))
        self.assertEqual(left_result.airport_ids, right_result.airport_ids)
        self.assertEqual(left_result.market_ids, right_result.market_ids)
        self.assertLess(left_ids["HAN"], left_ids["SGN"])
        pairs = [
            (
                left["world_state"]["directional_markets"][market_id]["origin_airport_id"],
                left["world_state"]["directional_markets"][market_id]["destination_airport_id"],
            )
            for market_id in left_result.market_ids
        ]
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual(canonical_bytes(left), canonical_bytes(right))
        pack = left["simulation"]["configuration"]["demand"]["market_pack_configuration"]["market_packs"][country_id]
        self.assertEqual(pack["catalog_airport_ids"], ["VN-HAN", "VN-SGN"])
        self.assertEqual(pack["airport_id_by_catalog_id"]["VN-HAN"], left_ids["HAN"])
        self.assertTrue(validate_world(left).is_valid)

        existing_count = len(left["world_state"]["airports"]) - len(left_result.airport_ids)
        new_count = len(left_result.airport_ids)
        expected_count = 2 * existing_count * new_count + new_count * (new_count - 1)
        self.assertEqual(len(left_result.market_ids), expected_count)
        new_ids = set(left_result.airport_ids)
        new_pairs = {
            (
                left["world_state"]["directional_markets"][market_id]["origin_airport_id"],
                left["world_state"]["directional_markets"][market_id]["destination_airport_id"],
            )
            for market_id in left_result.market_ids
        }
        self.assertEqual(
            sum((origin in new_ids) != (destination in new_ids) for origin, destination in new_pairs),
            2 * existing_count * new_count,
        )
        self.assertEqual(
            sum(origin in new_ids and destination in new_ids for origin, destination in new_pairs),
            new_count * (new_count - 1),
        )
        airport_numbers = [int(airport_id.rsplit("-", 1)[1]) for airport_id in left_result.airport_ids]
        market_numbers = [int(market_id.rsplit("-", 1)[1]) for market_id in left_result.market_ids]
        self.assertEqual(airport_numbers, list(range(airport_numbers[0], airport_numbers[0] + new_count)))
        self.assertEqual(market_numbers, list(range(market_numbers[0], market_numbers[0] + expected_count)))
        self.assertEqual(
            left["deterministic_state"]["id_allocator"]["next_by_type"]["airport"],
            airport_numbers[-1] + 1,
        )
        self.assertEqual(
            left["deterministic_state"]["id_allocator"]["next_by_type"]["market"],
            market_numbers[-1] + 1,
        )

    def test_materialization_is_independent_of_decimal_context(self):
        world, _ids, _old = model4_world()
        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "VN"
        )
        demand_revision = world["world_state"]["demand_state"]["demand_model_revision"]
        with localcontext() as context:
            context.prec = 2
            result = materialize_country_pack(
                world,
                country_id,
                "test-vn",
                "1",
                vietnam_catalog(),
                expected_pack_revision=1,
                expected_demand_revision=demand_revision,
            )
        self.assertTrue(result.succeeded, result.issues)
        coordinates = {
            airport["reference_code"]: (
                airport["latitude_microdegrees"],
                airport["longitude_microdegrees"],
            )
            for airport in world["world_state"]["airports"].values()
            if airport["airport_id"] in result.airport_ids
        }
        self.assertEqual(coordinates["HAN"], (21_027_000, 105_834_000))
        self.assertEqual(coordinates["SGN"], (10_823_000, 106_630_000))

    def test_country_with_existing_allocation_airports_is_not_latent(self):
        world, _ids, _old = model4_world()
        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "PH"
        )
        before = canonical_bytes(world)
        result = materialize_country_pack(
            world,
            country_id,
            "duplicate-ph",
            "1",
            vietnam_catalog(),
            expected_pack_revision=1,
            expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"],
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "PACK_ALREADY_MATERIALIZED")
        self.assertEqual(canonical_bytes(world), before)

    def test_legacy_single_airport_addition_cannot_bypass_model4_pack_authority(self):
        world, _ids, _old = model4_world()
        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "VN"
        )
        supplied = deepcopy(vietnam_catalog()[0])
        supplied.pop("catalog_airport_id")
        supplied["country_id"] = country_id
        supplied["country_reference"] = "VN"
        supplied["demand_allocation_member"] = True
        supplied["latitude"] = Decimal(supplied.pop("latitude_microdegrees")) / Decimal(1_000_000)
        supplied["longitude"] = Decimal(supplied.pop("longitude_microdegrees")) / Decimal(1_000_000)
        before = canonical_bytes(world)
        with self.assertRaisesRegex(ValueError, "country-pack materialization"):
            add_airport_reference(world, supplied)
        self.assertEqual(canonical_bytes(world), before)

    def test_committed_legacy_pack_authority_upgrades_atomically_on_materialization(self):
        current, ids, _old = model4_world()
        world = as_committed_legacy_pack_world(current)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).errors)
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        historical_market_id, _flight_id = _publish_direct_service(world, ids, "DVO")
        created = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertIn(historical_market_id, created.active_market_ids)
        historical_key = f"{historical_market_id}@2026-08-24"
        historical = deepcopy(world["world_state"]["demand_state"]["processed_cohorts"][historical_key])
        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "VN"
        )
        result = materialize_country_pack(
            world,
            country_id,
            "test-vn",
            "1",
            vietnam_catalog(),
            expected_pack_revision=1,
            expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"],
        )
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(
            world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["configuration_version"],
            MARKET_PACK_CONFIGURATION_VERSION,
        )
        self.assertTrue(
            all(
                isinstance(country["airport_allocation_revision"], int)
                for country in world["world_state"]["countries"].values()
            )
        )
        self.assertEqual(
            world["world_state"]["demand_state"]["processed_cohorts"][historical_key],
            historical,
        )
        reused = resolve_daily_cohort(world, historical_market_id, "2026-08-24")
        self.assertTrue(reused.reused)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).errors)

    def test_committed_schema2_model3_legacy_pack_authority_remains_valid(self):
        world = make_schema1_world()
        migration = migrate_schema_1_to_2(
            world,
            foundation_snapshot=foundation_snapshot(world),
        )
        self.assertTrue(migration.succeeded, migration.issues)
        configuration = world["simulation"]["configuration"]["demand"]
        revision = configuration["market_pack_configuration"]["revision"]
        configuration["market_pack_configuration"] = {
            "contract": "MARKET_PACK_CONFIGURATION_V1",
            "configuration_version": LEGACY_MARKET_PACK_CONFIGURATION_VERSION,
            "revision": revision,
            "market_pack_ids": [],
        }
        for country in world["world_state"]["countries"].values():
            country.pop("airport_allocation_revision")
        self.assertTrue(validate_world(world).is_valid, validate_world(world).errors)

    def test_materialization_preserves_existing_identity_and_mathematical_stability(self):
        world, ids, _old = model4_world(model3_marker=True)
        country_id = next(key for key, value in world["world_state"]["countries"].items() if value["external_reference_code"] == "VN")
        before_ids = {
            collection: tuple(world["world_state"][collection])
            for collection in (
                "airports", "directional_markets", "pending_events", "event_history",
                "financial_accounts", "transactions", "schedule_definitions",
            )
        }
        before_history = deepcopy(world["world_state"]["history"])
        before_cohorts = deepcopy(world["world_state"]["demand_state"]["processed_cohorts"])
        preexisting_airport_ids = tuple(world["world_state"]["airports"])
        before_projections = {
            origin_id: project_model4_origin(world, origin_id)
            for origin_id in preexisting_airport_ids
        }
        before_origin = project_model4_origin(world, ids["MNL"])
        vietnam_amount = before_origin["country_amounts"][country_id]
        ph_pairs = {
            destination: project_model4_pair(world, ids["MNL"], destination)["base_daily_bookers"]
            for destination, airport in world["world_state"]["airports"].items()
            if destination != ids["MNL"]
            and airport["country_id"] == world["world_state"]["airports"][ids["MNL"]]["country_id"]
        }
        previous_demand = world["world_state"]["demand_state"]["demand_model_revision"]
        previous_country_revision = world["world_state"]["countries"][country_id]["airport_allocation_revision"]
        result = materialize_country_pack(
            world, country_id, "test-vn", "1", vietnam_catalog(),
            expected_pack_revision=1, expected_demand_revision=previous_demand,
        )
        self.assertTrue(result.succeeded, result.issues)
        for collection, keys in before_ids.items():
            self.assertEqual(tuple(world["world_state"][collection])[: len(keys)], keys)
        self.assertEqual(world["world_state"]["history"], before_history)
        self.assertEqual(world["world_state"]["demand_state"]["processed_cohorts"], before_cohorts)
        after_origin = project_model4_origin(world, ids["MNL"])
        self.assertEqual(after_origin["country_amounts"][country_id], vietnam_amount)
        for origin_id in preexisting_airport_ids:
            before_projection = before_projections[origin_id]
            after_projection = project_model4_origin(world, origin_id)
            self.assertEqual(after_projection["scope_amounts"], before_projection["scope_amounts"])
            self.assertEqual(after_projection["country_amounts"], before_projection["country_amounts"])
            origin_country = world["world_state"]["airports"][origin_id]["country_id"]
            for destination_id in preexisting_airport_ids:
                if (
                    destination_id != origin_id
                    and world["world_state"]["airports"][destination_id]["country_id"] == origin_country
                ):
                    self.assertEqual(
                        project_model4_pair(world, origin_id, destination_id)["base_daily_bookers"],
                        before_projection["airport_leaf_amounts"][destination_id],
                    )
        with localcontext() as context:
            context.prec = 80
            vietnam_leaf_total = sum(
                (after_origin["airport_leaf_amounts"][airport_id] for airport_id in result.airport_ids),
                Decimal(0),
            )
        self.assertEqual(vietnam_leaf_total, vietnam_amount)
        for origin_id in result.airport_ids:
            projection = project_model4_origin(world, origin_id)
            self.assertEqual(projection["conservation_total"], projection["origin_daily_booking_pool"])
            self.assertEqual(
                sum(
                    (
                        projection["airport_leaf_amounts"][destination_id]
                        for destination_id in result.airport_ids
                        if destination_id != origin_id
                    ),
                    Decimal(0),
                ),
                projection["country_amounts"][country_id],
            )
            expected_regions = {}
            for destination_country_id, amount in projection["country_amounts"].items():
                region_id = world["world_state"]["countries"][destination_country_id]["region_id"]
                expected_regions[region_id] = expected_regions.get(region_id, Decimal(0)) + amount
            self.assertEqual(projection["region_amounts"], expected_regions)
        for destination, baseline in ph_pairs.items():
            self.assertEqual(project_model4_pair(world, ids["MNL"], destination)["base_daily_bookers"], baseline)
        self.assertEqual(result.demand_revision, previous_demand + 1)
        self.assertEqual(world["world_state"]["countries"][country_id]["airport_allocation_revision"], previous_country_revision + 1)

    def test_revision_context_and_fingerprint_ownership(self):
        world, _ids, _old = model4_world()
        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "VN"
        )
        demand = world["world_state"]["demand_state"]
        configuration = world["simulation"]["configuration"]["demand"]
        packs = configuration["market_pack_configuration"]
        before_demand_revision = demand["demand_model_revision"]
        before_pack_revision = packs["revision"]
        before_terminal = demand["model3_terminal_demand_revision"]
        before_contexts = deepcopy(demand["model4_revision_contexts"])
        before_country_revisions = {
            key: country["airport_allocation_revision"]
            for key, country in world["world_state"]["countries"].items()
        }
        before_demand_fingerprint = demand["input_fingerprint"]
        before_pack_fingerprint = packs["configuration_fingerprint"]
        before_source_fingerprint = model4_source_fingerprint(world)

        result = materialize_country_pack(
            world,
            country_id,
            "test-vn",
            "1",
            vietnam_catalog(),
            expected_pack_revision=before_pack_revision,
            expected_demand_revision=before_demand_revision,
        )
        self.assertTrue(result.succeeded, result.issues)
        demand = world["world_state"]["demand_state"]
        configuration = world["simulation"]["configuration"]["demand"]
        packs = configuration["market_pack_configuration"]
        self.assertEqual(result.pack_revision, before_pack_revision + 1)
        self.assertEqual(result.demand_revision, before_demand_revision + 1)
        self.assertEqual(demand["model3_terminal_demand_revision"], before_terminal)
        self.assertNotEqual(demand["input_fingerprint"], before_demand_fingerprint)
        self.assertNotEqual(packs["configuration_fingerprint"], before_pack_fingerprint)
        self.assertNotEqual(model4_source_fingerprint(world), before_source_fingerprint)
        self.assertEqual(packs["configuration_fingerprint"], calculate_market_pack_fingerprint(world))
        self.assertEqual(
            sorted(context["demand_model_revision"] for context in demand["model4_revision_contexts"].values()),
            list(range(before_terminal + 1, result.demand_revision + 1)),
        )
        self.assertEqual(len(demand["model4_revision_contexts"]), len(before_contexts) + 1)
        current = next(
            context
            for context in demand["model4_revision_contexts"].values()
            if context["demand_model_revision"] == result.demand_revision
        )
        self.assertEqual(current["model4_input_fingerprint"], demand["input_fingerprint"])
        for key, previous in before_country_revisions.items():
            expected = previous + 1 if key == country_id else previous
            self.assertEqual(world["world_state"]["countries"][key]["airport_allocation_revision"], expected)

        before_disable_demand = deepcopy(demand)
        before_disable_source = model4_source_fingerprint(world)
        before_disable_pack_fingerprint = packs["configuration_fingerprint"]
        disabled = disable_country_pack(
            world,
            country_id,
            expected_pack_revision=result.pack_revision,
        )
        self.assertTrue(disabled.succeeded, disabled.issues)
        demand = world["world_state"]["demand_state"]
        packs = world["simulation"]["configuration"]["demand"]["market_pack_configuration"]
        self.assertEqual(demand, before_disable_demand)
        self.assertEqual(model4_source_fingerprint(world), before_disable_source)
        self.assertNotEqual(packs["configuration_fingerprint"], before_disable_pack_fingerprint)

    def test_malformed_stale_exhaustion_and_duplicate_failures_are_atomic(self):
        cases = []
        duplicate = vietnam_catalog()
        duplicate[1]["catalog_airport_id"] = duplicate[0]["catalog_airport_id"]
        cases.append((duplicate, 1, None, "INVALID_AIRPORT_CATALOG"))
        aliased = vietnam_catalog()
        aliased[0]["catalog_airport_id"] = " VN-HAN "
        cases.append((aliased, 1, None, "INVALID_AIRPORT_CATALOG"))
        wrong_country = vietnam_catalog()
        wrong_country[0]["country_id"] = "country-000000000001"
        cases.append((wrong_country, 1, None, "PACK_COUNTRY_MISMATCH"))
        missing = vietnam_catalog()
        del missing[0]["timezone"]
        cases.append((missing, 1, None, "INVALID_AIRPORT_CATALOG"))
        extra = vietnam_catalog()
        extra[0]["coordinates"] = {"lat": 21.027, "lon": 105.834}
        cases.append((extra, 1, None, "INVALID_AIRPORT_CATALOG"))
        malformed_text = vietnam_catalog()
        malformed_text[0]["display_name"] = ["Hanoi"]
        cases.append((malformed_text, 1, None, "INVALID_AIRPORT_CATALOG"))
        cyclic = vietnam_catalog()
        cyclic[0]["extra"] = cyclic[0]
        cases.append((cyclic, 1, None, "INVALID_AIRPORT_CATALOG"))
        for catalog, pack_revision, demand_revision, code in cases:
            world, _ids, _old = model4_world()
            country_id = next(key for key, value in world["world_state"]["countries"].items() if value["external_reference_code"] == "VN")
            demand_revision = demand_revision or world["world_state"]["demand_state"]["demand_model_revision"]
            before = canonical_bytes(world)
            result = materialize_country_pack(world, country_id, "test-vn", "1", catalog, expected_pack_revision=pack_revision, expected_demand_revision=demand_revision)
            self.assertFalse(result.succeeded)
            self.assertEqual(result.issues[0].code, code)
            self.assertEqual(canonical_bytes(world), before)
        world, _ids, _old = model4_world()
        country_id = next(key for key, value in world["world_state"]["countries"].items() if value["external_reference_code"] == "VN")
        before = canonical_bytes(world)
        stale = materialize_country_pack(world, country_id, "test-vn", "1", vietnam_catalog(), expected_pack_revision=2, expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"])
        self.assertEqual(stale.status, "STALE_REVISION")
        self.assertEqual(canonical_bytes(world), before)
        world["deterministic_state"]["id_allocator"]["next_by_type"]["airport"] = MAX_ENTITY_ID_NUMBER
        before = canonical_bytes(world)
        exhausted = materialize_country_pack(world, country_id, "test-vn", "1", vietnam_catalog(), expected_pack_revision=1, expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"])
        self.assertEqual(exhausted.issues[0].code, "DEMAND_ALLOCATION_FAILED")
        self.assertEqual(canonical_bytes(world), before)

        world, _ids, _old = model4_world()
        country_id = next(key for key, value in world["world_state"]["countries"].items() if value["external_reference_code"] == "VN")
        world["deterministic_state"]["id_allocator"]["next_by_type"]["market"] = MAX_ENTITY_ID_NUMBER - 5
        before = canonical_bytes(world)
        exhausted = materialize_country_pack(world, country_id, "test-vn", "1", vietnam_catalog(), expected_pack_revision=1, expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"])
        self.assertEqual(exhausted.issues[0].code, "DEMAND_ALLOCATION_FAILED")
        self.assertEqual(canonical_bytes(world), before)

    def test_allocator_near_boundary_succeeds_with_exact_remaining_capacity(self):
        world, _ids, _old = model4_world()
        country_id = next(key for key, value in world["world_state"]["countries"].items() if value["external_reference_code"] == "VN")
        existing_count = len(world["world_state"]["airports"])
        expected_markets = 2 * existing_count * 2 + 2
        allocator = world["deterministic_state"]["id_allocator"]["next_by_type"]
        allocator["airport"] = MAX_ENTITY_ID_NUMBER - 1
        allocator["market"] = MAX_ENTITY_ID_NUMBER - expected_markets + 1
        result = materialize_country_pack(
            world,
            country_id,
            "test-vn",
            "1",
            vietnam_catalog(),
            expected_pack_revision=1,
            expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"],
        )
        self.assertTrue(result.succeeded, result.issues)
        allocator = world["deterministic_state"]["id_allocator"]["next_by_type"]
        self.assertEqual(allocator["airport"], MAX_ENTITY_ID_NUMBER + 1)
        self.assertEqual(allocator["market"], MAX_ENTITY_ID_NUMBER + 1)

    def test_caller_catalog_and_result_are_detached(self):
        catalog = vietnam_catalog()
        world, ids, _country_id, result = materialized_world(catalog)
        catalog[0]["display_name"] = "mutated"
        catalog.append({})
        self.assertNotEqual(world["world_state"]["airports"][ids["SGN"]]["display_name"], "mutated")
        self.assertIsInstance(result.airport_ids, tuple)


class MarketPackTransitionAndActivationTests(unittest.TestCase):
    def test_malformed_pack_authority_and_revision_inputs_reject_structurally(self):
        world, _ids, country_id, materialized = materialized_world()
        pack_configuration = world["simulation"]["configuration"]["demand"]["market_pack_configuration"]
        pack = pack_configuration["market_packs"][country_id]
        mutations = (
            lambda candidate: candidate["simulation"]["configuration"]["demand"]["market_pack_configuration"]["market_packs"][country_id].__setitem__("status", []),
            lambda candidate: candidate["simulation"]["configuration"]["demand"]["market_pack_configuration"]["market_packs"][country_id].__setitem__("country_id", []),
            lambda candidate: candidate["simulation"]["configuration"]["demand"]["market_pack_configuration"]["market_packs"][country_id]["airport_id_by_catalog_id"].__setitem__("VN-HAN", []),
            lambda candidate: candidate["simulation"]["configuration"]["demand"]["market_pack_configuration"].__setitem__("market_pack_ids", [["unhashable"]]),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                malformed = deepcopy(world)
                mutate(malformed)
                validation = validate_world(malformed)
                self.assertFalse(validation.is_valid)
                before = canonical_bytes(malformed)
                result = disable_country_pack(
                    malformed,
                    country_id,
                    expected_pack_revision=materialized.pack_revision,
                )
                self.assertFalse(result.succeeded)
                self.assertEqual(canonical_bytes(malformed), before)

        for malformed_revision in (True, -1, "1", [], {}):
            with self.subTest(revision=repr(malformed_revision)):
                before = canonical_bytes(world)
                result = disable_country_pack(
                    world,
                    country_id,
                    expected_pack_revision=malformed_revision,
                )
                self.assertFalse(result.succeeded)
                self.assertEqual(result.status, "STALE_REVISION")
                self.assertEqual(canonical_bytes(world), before)

        for malformed_date in (True, "2026-8-24", [], {}):
            with self.subTest(status_effective_date=repr(malformed_date)):
                before = canonical_bytes(world)
                result = disable_country_pack(
                    world,
                    country_id,
                    expected_pack_revision=materialized.pack_revision,
                    status_effective_date=malformed_date,
                )
                self.assertFalse(result.succeeded)
                self.assertEqual(canonical_bytes(world), before)

        forged_pack = deepcopy(world)
        forged_pack["simulation"]["configuration"]["demand"]["market_pack_configuration"]["configuration_fingerprint"] = "0" * 64
        before = canonical_bytes(forged_pack)
        result = disable_country_pack(
            forged_pack,
            country_id,
            expected_pack_revision=materialized.pack_revision,
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "INCONSISTENT_PACK_FINGERPRINT")
        self.assertEqual(canonical_bytes(forged_pack), before)

        unmaterialized, _ids, _old = model4_world()
        unmaterialized["world_state"]["demand_state"]["input_fingerprint"] = "0" * 64
        before = canonical_bytes(unmaterialized)
        result = materialize_country_pack(
            unmaterialized,
            country_id,
            "test-vn",
            "1",
            vietnam_catalog(),
            expected_pack_revision=1,
            expected_demand_revision=unmaterialized["world_state"]["demand_state"]["demand_model_revision"],
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "INCONSISTENT_DEMAND_FINGERPRINT")
        self.assertEqual(canonical_bytes(unmaterialized), before)

    def test_disable_and_reenable_change_only_pack_witness_and_preserve_authority(self):
        world, ids, country_id, materialized = materialized_world()
        demand_revision = world["world_state"]["demand_state"]["demand_model_revision"]
        demand_fingerprint = world["world_state"]["demand_state"]["input_fingerprint"]
        pack_fingerprint = world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["configuration_fingerprint"]
        authority = deepcopy(world["world_state"])
        disabled = disable_country_pack(world, country_id, expected_pack_revision=materialized.pack_revision)
        self.assertTrue(disabled.succeeded, disabled.issues)
        self.assertEqual(disabled.demand_revision, demand_revision)
        self.assertEqual(world["world_state"]["demand_state"]["input_fingerprint"], demand_fingerprint)
        self.assertNotEqual(world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["configuration_fingerprint"], pack_fingerprint)
        for collection in world["world_state"]:
            if collection != "demand_state":
                self.assertEqual(world["world_state"][collection], authority[collection])
        before_repeat = canonical_bytes(world)
        repeated = disable_country_pack(world, country_id, expected_pack_revision=disabled.pack_revision)
        self.assertEqual(repeated.issues[0].code, "INVALID_PACK_TRANSITION")
        self.assertEqual(canonical_bytes(world), before_repeat)
        enabled = enable_country_pack(world, country_id, expected_pack_revision=disabled.pack_revision, pack_reference="test-southeast-asia-vn", pack_version="2026.1")
        self.assertTrue(enabled.succeeded, enabled.issues)
        self.assertEqual(enabled.demand_revision, demand_revision)
        self.assertEqual(world["world_state"]["demand_state"]["input_fingerprint"], demand_fingerprint)
        self.assertEqual(ids["HAN"], world["simulation"]["configuration"]["demand"]["market_pack_configuration"]["market_packs"][country_id]["airport_id_by_catalog_id"]["VN-HAN"])

    def test_disabled_destination_and_origin_are_prospectively_inactive_without_backlog(self):
        world, ids, country_id, materialized = materialized_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids, "HAN")
        disabled = disable_country_pack(world, country_id, expected_pack_revision=materialized.pack_revision)
        inactive = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertTrue(inactive.succeeded, inactive.issues)
        self.assertNotIn(market_id, inactive.active_market_ids)
        self.assertNotIn(f"{market_id}@2026-08-24", world["world_state"]["demand_state"]["processed_cohorts"])
        enabled = enable_country_pack(
            world,
            country_id,
            expected_pack_revision=disabled.pack_revision,
            pack_reference="test-southeast-asia-vn",
            pack_version="2026.1",
        )
        active = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertTrue(active.succeeded, active.issues)
        self.assertIn(market_id, active.active_market_ids)
        self.assertEqual(len([key for key in world["world_state"]["demand_state"]["processed_cohorts"] if key.startswith(f"{market_id}@")]), 1)
        self.assertEqual(enabled.demand_revision, materialized.demand_revision)

    def test_future_disable_does_not_apply_before_its_effective_date(self):
        world, ids, country_id, materialized = materialized_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids, "HAN")
        disabled = disable_country_pack(
            world,
            country_id,
            expected_pack_revision=materialized.pack_revision,
            status_effective_date="2026-08-25",
        )
        self.assertTrue(disabled.succeeded, disabled.issues)
        result = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertTrue(result.succeeded, result.issues)
        self.assertIn(market_id, result.active_market_ids)

    def test_disabled_origin_cannot_generate_outbound_demand(self):
        world, ids, country_id, materialized = materialized_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        _forward_market_id, flight_id = _publish_direct_service(world, ids, "HAN")
        state = world["world_state"]
        flight = state["dated_flights"][flight_id]
        connection = state["connections"][flight["connection_id"]]
        reverse_market_id = next(
            market_id
            for market_id, market in state["directional_markets"].items()
            if market["origin_airport_id"] == ids["HAN"]
            and market["destination_airport_id"] == ids["MNL"]
        )
        connection["market_id"] = reverse_market_id
        flight["origin_airport_id"] = ids["HAN"]
        flight["destination_airport_id"] = ids["MNL"]
        aircraft = state["aircraft"][flight["planned_aircraft_id"]]
        aircraft["home_airport_id"] = ids["HAN"]
        aircraft["current_airport_id"] = ids["HAN"]
        revision = state["schedule_definitions"][flight["schedule_id"]]["revisions"]["1"]
        revision["origin_airport_id"] = ids["HAN"]
        revision["destination_airport_id"] = ids["MNL"]
        revision["recurrence"]["departure_local_time"] = "07:00:00"
        revision["recurrence"]["arrival_local_time"] = "11:00:00"
        self.assertTrue(validate_world(world).is_valid, validate_world(world).errors)

        disabled = disable_country_pack(
            world,
            country_id,
            expected_pack_revision=materialized.pack_revision,
        )
        self.assertTrue(disabled.succeeded, disabled.issues)
        result = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertTrue(result.succeeded, result.issues)
        self.assertNotIn(reverse_market_id, result.active_market_ids)
        self.assertNotIn(
            f"{reverse_market_id}@2026-08-24",
            world["world_state"]["demand_state"]["processed_cohorts"],
        )

    def test_closed_airport_retains_leaf_and_reopens_without_fingerprint_change(self):
        world, ids, _country_id, _materialized = materialized_world()
        before = project_model4_pair(world, ids["MNL"], ids["HAN"])["base_daily_bookers"]
        fingerprint = world["world_state"]["demand_state"]["input_fingerprint"]
        world["world_state"]["airports"][ids["HAN"]]["active_until_date"] = "2026-08-20"
        self.assertTrue(validate_world(world).is_valid)
        closed = project_model4_origin(world, ids["MNL"])
        self.assertGreater(closed["latent"]["unavailable_airport_leaf_amount"], 0)
        self.assertEqual(project_model4_pair(world, ids["MNL"], ids["HAN"])["base_daily_bookers"], before)
        self.assertEqual(world["world_state"]["demand_state"]["input_fingerprint"], fingerprint)
        world["world_state"]["airports"][ids["HAN"]]["active_until_date"] = None
        self.assertTrue(validate_world(world).is_valid)
        self.assertEqual(project_model4_pair(world, ids["MNL"], ids["HAN"])["base_daily_bookers"], before)

    def test_airport_opening_is_inclusive_and_closing_is_exclusive(self):
        for field, expected_active in (
            ("active_from_date", True),
            ("active_until_date", False),
        ):
            with self.subTest(field=field):
                world, ids, _country_id, _materialized = materialized_world()
                world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
                market_id, _flight_id = _publish_direct_service(world, ids, "HAN")
                world["world_state"]["airports"][ids["HAN"]][field] = "2026-08-24"
                self.assertTrue(validate_world(world).is_valid, validate_world(world).errors)
                result = resolve_active_daily_cohorts(world, "2026-08-24")
                self.assertTrue(result.succeeded, result.issues)
                self.assertEqual(market_id in result.active_market_ids, expected_active)

    def test_custom_provider_mutation_unknown_and_multi_market_failure_are_atomic(self):
        world, ids, _country_id, _materialized = materialized_world()
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids, "HAN")

        class MutatingProvider:
            def active_market_ids(self, candidate, *_args, **_kwargs):
                candidate["ui_state"]["selected_screen"] = "mutated"
                return (market_id,)

        before = canonical_bytes(world)
        mutated = resolve_active_daily_cohorts(world, "2026-08-24", activation_providers=(MutatingProvider(),))
        self.assertFalse(mutated.succeeded)
        self.assertEqual(canonical_bytes(world), before)

        class UnknownProvider:
            def active_market_ids(self, *_args, **_kwargs):
                return (market_id, "market-unknown")

        unknown = resolve_active_daily_cohorts(world, "2026-08-24", activation_providers=(UnknownProvider(),))
        self.assertEqual(unknown.issues[0].code, "UNAVAILABLE_DEMAND_MARKET")
        self.assertEqual(canonical_bytes(world), before)

        multi, multi_ids, _country_id, _materialized = materialized_world()
        multi["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        first_market, _first_flight = _publish_direct_service(multi, multi_ids, "HAN")
        second_market, _second_flight = _publish_direct_service(
            multi,
            multi_ids,
            "SGN",
            registration="RP-C4502",
        )
        ordered = sorted((first_market, second_market))
        before_multi = canonical_bytes(multi)
        failed = resolve_active_daily_cohorts(
            multi,
            "2026-08-24",
            multipliers_by_market={ordered[1]: {"world": []}},
        )
        self.assertFalse(failed.succeeded)
        self.assertEqual(canonical_bytes(multi), before_multi)

        retained = []

        class RetainingProvider:
            def active_market_ids(self, candidate, *_args, **_kwargs):
                retained.append(candidate)
                return tuple(ordered)

        succeeded = resolve_active_daily_cohorts(
            multi,
            "2026-08-24",
            activation_providers=(RetainingProvider(),),
        )
        self.assertTrue(succeeded.succeeded, succeeded.issues)
        after_success = canonical_bytes(multi)
        retained[0]["ui_state"]["selected_screen"] = "late mutation"
        self.assertEqual(canonical_bytes(multi), after_success)

    def test_disabled_packs_preserve_historical_v1_and_v2_reuse(self):
        world, ids, old_v1 = model4_world(model3_marker=True)
        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "VN"
        )
        materialized = materialize_country_pack(
            world,
            country_id,
            "test-vn",
            "1",
            vietnam_catalog(),
            expected_pack_revision=1,
            expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"],
        )
        self.assertTrue(materialized.succeeded, materialized.issues)
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(world, ids | {
            airport["reference_code"]: airport_id
            for airport_id, airport in world["world_state"]["airports"].items()
        }, "HAN")
        created = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertIn(market_id, created.active_market_ids)
        disabled = disable_country_pack(
            world,
            country_id,
            expected_pack_revision=materialized.pack_revision,
        )
        self.assertTrue(disabled.succeeded, disabled.issues)
        before = canonical_bytes(world)

        v2 = resolve_daily_cohort(
            world,
            market_id,
            "2026-08-24",
            multipliers={"world": 1},
        )
        self.assertTrue(v2.reused)
        old_payload = old_v1["payload"]
        v1 = resolve_daily_cohort(
            world,
            old_payload["market_id"],
            old_payload["cohort_date"],
            multipliers={"world": 1},
        )
        self.assertTrue(v1.reused)
        self.assertEqual(canonical_bytes(world), before)


if __name__ == "__main__":
    unittest.main()
