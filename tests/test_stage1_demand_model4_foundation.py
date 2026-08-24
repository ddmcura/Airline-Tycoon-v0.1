"""Milestone 4.5B-1 schema, wrapper, and migration foundation tests."""

from copy import deepcopy
import json
from types import MappingProxyType
import unittest

from game.demand import (
    calculate_world_demand,
    resolve_active_daily_cohorts,
    resolve_daily_cohort,
)
from game.world_state import (
    add_airport_reference,
    allocate_id,
    create_new_world,
    migrate_schema_1_to_2,
    validate_world,
)
from game.world_state.demand_fingerprint import (
    calculate_demand_cohort_fingerprint,
)
from game.world_state.schema import (
    MAX_ENTITY_ID_NUMBER,
    MODEL3_PROCESSED_COHORT_V1,
    MODEL4_TRAVEL_SCOPE_COHORT_V1,
)
from tests.test_stage1_compact_demand import _publish_direct_service
from tests.test_stage1_world_demand import make_demand_world


def airport(code, country, population, latitude, longitude):
    return {
        "reference_code": code,
        "iata": code,
        "icao": f"RP{code[:2]}",
        "name": code,
        "timezone": "Asia/Manila",
        "population": population,
        "coordinates": {"lat": latitude, "lon": longitude},
        "country_reference": country,
        "demand_destination_type": "NORMAL_CITY",
        "opened": "1950-01-01",
    }


def make_schema1_world():
    world = create_new_world(
        ceo_display_name="Avery Chen",
        airline_display_name="Meridian Air",
        starting_airport=airport("MNL", "PH", 10_000_000, 14.5, 121.0),
        difficulty="Normal",
        simulation_time_utc="2026-08-20T04:30:00Z",
        simulation_seed=8675309,
        starting_money="300000000.00",
    )
    add_airport_reference(world, airport("SIN", "SG", 6_000_000, 1.3, 103.8))
    return world


def foundation_snapshot(world):
    airports = world["world_state"]["airports"]
    country_by_reference = {
        "PH": "country-000000000001",
        "SG": "country-000000000002",
    }
    return {
        "snapshot_version": "stage1-test-countries-v1",
        "regions": {
            "region-000000000001": {
                "region_id": "region-000000000001",
                "external_reference_code": "SEA",
                "display_name": "Southeast Asia",
            }
        },
        "countries": {
            "country-000000000001": {
                "country_id": "country-000000000001",
                "region_id": "region-000000000001",
                "external_reference_code": "PH",
                "display_name": "Philippines",
                "effective_from_date": None,
                "effective_until_date": None,
                "demand_attractiveness_bps": 10_000,
                "relationship_weight_bps": 10_000,
            },
            "country-000000000002": {
                "country_id": "country-000000000002",
                "region_id": "region-000000000001",
                "external_reference_code": "SG",
                "display_name": "Singapore",
                "effective_from_date": None,
                "effective_until_date": None,
                "demand_attractiveness_bps": 10_000,
                "relationship_weight_bps": 10_000,
            },
        },
        "airport_country_ids": {
            airport_id: country_by_reference[record["country_reference"]]
            for airport_id, record in airports.items()
        },
        "airport_demand_allocation_members": {
            airport_id: True for airport_id in airports
        },
    }


def resolve_first(world, cohort_date="2026-08-20"):
    indexes = calculate_world_demand(world).indexes
    if indexes is None:
        raise AssertionError("test fixture did not build demand indexes")
    market_id = sorted(indexes.by_market)[0]
    resolution = resolve_daily_cohort(
        world, market_id, cohort_date, indexes=indexes
    )
    return market_id, resolution


def issue_codes(world):
    return {issue.code for issue in validate_world(world).errors}


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


class Stage1Model4FoundationMigrationTests(unittest.TestCase):
    def test_schema1_to_2_is_deterministic_and_preserves_v1_payload_and_fingerprint(self):
        source = make_schema1_world()
        market_id, old_resolution = resolve_first(source)
        key = f"{market_id}@2026-08-20"
        old_payload = deepcopy(source["world_state"]["demand_state"]["processed_cohorts"][key])
        old_fingerprint = old_payload["resolution_fingerprint"]
        old_input_fingerprint = source["world_state"]["demand_state"][
            "input_fingerprint"
        ]
        old_allocator = deepcopy(
            source["deterministic_state"]["id_allocator"]["next_by_type"]
        )
        self.assertEqual(
            calculate_demand_cohort_fingerprint(source, old_payload), old_fingerprint
        )
        left = deepcopy(source)
        right = deepcopy(source)

        left_result = migrate_schema_1_to_2(
            left, foundation_snapshot=foundation_snapshot(source)
        )
        right_result = migrate_schema_1_to_2(
            right, foundation_snapshot=foundation_snapshot(source)
        )

        self.assertTrue(left_result.succeeded, left_result.as_dict())
        self.assertTrue(right_result.succeeded, right_result.as_dict())
        self.assertEqual(left, right)
        self.assertTrue(validate_world(left).is_valid, validate_world(left).as_dict())
        wrapper = left["world_state"]["demand_state"]["processed_cohorts"][key]
        self.assertEqual(wrapper["contract"], MODEL3_PROCESSED_COHORT_V1)
        self.assertEqual(wrapper["payload"], old_payload)
        self.assertEqual(canonical_bytes(wrapper["payload"]), canonical_bytes(old_payload))
        self.assertEqual(
            left["world_state"]["demand_state"]["input_fingerprint"],
            old_input_fingerprint,
        )
        self.assertEqual(
            {
                key: value
                for key, value in left["deterministic_state"]["id_allocator"][
                    "next_by_type"
                ].items()
                if key not in {"region", "country"}
            },
            old_allocator,
        )
        for collection in (
            "airlines",
            "aircraft",
            "directional_markets",
            "connections",
            "schedule_definitions",
            "dated_flights",
            "bookings",
            "itineraries",
            "active_aircraft_operations",
            "pending_events",
            "event_history",
            "financial_accounts",
            "transactions",
            "history",
        ):
            self.assertEqual(
                left["world_state"][collection], source["world_state"][collection]
            )
        self.assertEqual(wrapper["payload"]["resolution_fingerprint"], old_fingerprint)
        self.assertEqual(
            calculate_demand_cohort_fingerprint(left, wrapper["payload"]),
            old_fingerprint,
        )
        repeated = resolve_daily_cohort(left, market_id, "2026-08-20")
        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.actual_daily_bookers, old_resolution.actual_daily_bookers)

    def test_new_model3_cohorts_in_schema2_use_the_wrapper(self):
        world = make_schema1_world()
        self.assertTrue(
            migrate_schema_1_to_2(
                world, foundation_snapshot=foundation_snapshot(world)
            ).succeeded
        )
        market_id, resolution = resolve_first(world, "2026-08-21")
        wrapper = world["world_state"]["demand_state"]["processed_cohorts"][
            f"{market_id}@2026-08-21"
        ]
        self.assertFalse(resolution.reused)
        self.assertEqual(set(wrapper), {"contract", "payload"})
        self.assertEqual(wrapper["contract"], MODEL3_PROCESSED_COHORT_V1)
        self.assertEqual(
            wrapper["payload"]["resolution_fingerprint"],
            calculate_demand_cohort_fingerprint(world, wrapper["payload"]),
        )

    def test_all_model3_resolution_paths_create_and_reuse_schema2_wrappers(self):
        world, ids = make_demand_world(("MNL", "DVO"), seed=2468)
        market_id, _flight_id = _publish_direct_service(world, ids, "DVO")
        preserved_collections = {
            name: deepcopy(world["world_state"][name])
            for name in (
                "airlines",
                "aircraft",
                "directional_markets",
                "connections",
                "schedule_definitions",
                "dated_flights",
                "bookings",
                "itineraries",
                "active_aircraft_operations",
                "pending_events",
                "event_history",
                "financial_accounts",
                "transactions",
                "history",
            )
        }
        snapshot = foundation_snapshot(world)
        result = migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
        self.assertTrue(result.succeeded, result.as_dict())
        for name, records in preserved_collections.items():
            self.assertEqual(world["world_state"][name], records, name)

        first = resolve_active_daily_cohorts(world, "2026-08-20")
        self.assertTrue(first.succeeded, first.issues)
        key = f"{market_id}@2026-08-20"
        wrapper = world["world_state"]["demand_state"]["processed_cohorts"][key]
        self.assertEqual(wrapper["contract"], MODEL3_PROCESSED_COHORT_V1)
        committed = deepcopy(world)

        repeated = resolve_active_daily_cohorts(
            world,
            "2026-08-20",
            multipliers_by_market={market_id: {"holiday": 1}},
        )
        self.assertTrue(repeated.succeeded, repeated.issues)
        self.assertTrue(all(cohort.reused for cohort in repeated.cohorts))
        self.assertEqual(world, committed)

    def test_schema1_and_schema2_new_model3_outcomes_are_identical(self):
        schema1 = make_schema1_world()
        schema2 = deepcopy(schema1)
        result = migrate_schema_1_to_2(
            schema2, foundation_snapshot=foundation_snapshot(schema1)
        )
        self.assertTrue(result.succeeded, result.as_dict())
        schema1_market, schema1_resolution = resolve_first(schema1, "2026-08-23")
        schema2_market, schema2_resolution = resolve_first(schema2, "2026-08-23")
        self.assertEqual(schema1_market, schema2_market)
        self.assertEqual(schema1_resolution, schema2_resolution)
        key = f"{schema1_market}@2026-08-23"
        self.assertEqual(
            schema1["world_state"]["demand_state"]["processed_cohorts"][key],
            schema2["world_state"]["demand_state"]["processed_cohorts"][key][
                "payload"
            ],
        )

    def test_every_migration_failure_leaves_source_unchanged(self):
        mutations = []
        world = make_schema1_world()
        bad_mapping = foundation_snapshot(world)
        bad_mapping["airport_country_ids"].pop(next(iter(bad_mapping["airport_country_ids"])))
        mutations.append(bad_mapping)
        bad_identity = foundation_snapshot(world)
        bad_identity["countries"]["country-000000000001"]["country_id"] = "country-000000000099"
        mutations.append(bad_identity)
        bad_reference = foundation_snapshot(world)
        bad_reference["countries"]["country-000000000001"]["external_reference_code"] = "XX"
        mutations.append(bad_reference)
        bad_candidate = foundation_snapshot(world)
        bad_candidate["countries"]["country-000000000001"]["demand_attractiveness_bps"] = -1
        mutations.append(bad_candidate)
        unknown_country = foundation_snapshot(world)
        first_airport = next(iter(unknown_country["airport_country_ids"]))
        unknown_country["airport_country_ids"][first_airport] = (
            "country-000000000999"
        )
        mutations.append(unknown_country)
        extra_mapping = foundation_snapshot(world)
        extra_mapping["airport_country_ids"]["airport-000000000999"] = (
            "country-000000000001"
        )
        extra_mapping["airport_demand_allocation_members"][
            "airport-000000000999"
        ] = True
        mutations.append(extra_mapping)
        duplicate_code = foundation_snapshot(world)
        duplicate_code["countries"]["country-000000000003"] = deepcopy(
            duplicate_code["countries"]["country-000000000001"]
        )
        duplicate_code["countries"]["country-000000000003"]["country_id"] = (
            "country-000000000003"
        )
        mutations.append(duplicate_code)
        for snapshot in mutations:
            with self.subTest(snapshot=snapshot):
                candidate = make_schema1_world()
                before = deepcopy(candidate)
                result = migrate_schema_1_to_2(
                    candidate, foundation_snapshot=snapshot
                )
                self.assertFalse(result.succeeded)
                self.assertTrue(result.issues)
                self.assertEqual(candidate, before)
                self.assertEqual(canonical_bytes(candidate), canonical_bytes(before))

    def test_malformed_source_and_repeated_migration_are_structured_and_atomic(self):
        malformed = make_schema1_world()
        malformed["metadata"] = []
        before = deepcopy(malformed)
        result = migrate_schema_1_to_2(
            malformed, foundation_snapshot=foundation_snapshot(make_schema1_world())
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "unsupported_migration_source")
        self.assertEqual(malformed, before)

        malformed_version = make_schema1_world()
        malformed_version["metadata"]["save_schema_version"] = []
        validation = validate_world(malformed_version)
        self.assertFalse(validation.is_valid)
        self.assertIn("unsupported_schema_version", issue_codes(malformed_version))
        before = deepcopy(malformed_version)
        result = migrate_schema_1_to_2(
            malformed_version,
            foundation_snapshot=foundation_snapshot(make_schema1_world()),
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(malformed_version, before)

        world = make_schema1_world()
        self.assertTrue(
            migrate_schema_1_to_2(
                world, foundation_snapshot=foundation_snapshot(world)
            ).succeeded
        )
        migrated = deepcopy(world)
        repeated = migrate_schema_1_to_2(
            world, foundation_snapshot=foundation_snapshot(make_schema1_world())
        )
        self.assertFalse(repeated.succeeded)
        self.assertEqual(repeated.issues[0].code, "unsupported_migration_source")
        self.assertEqual(world, migrated)

    def test_migration_is_order_independent_and_retains_no_caller_references(self):
        left = make_schema1_world()
        right = deepcopy(left)
        right["world_state"]["airports"] = dict(
            reversed(list(right["world_state"]["airports"].items()))
        )
        left_snapshot = foundation_snapshot(left)
        right_snapshot = foundation_snapshot(right)
        for field in (
            "regions",
            "countries",
            "airport_country_ids",
            "airport_demand_allocation_members",
        ):
            right_snapshot[field] = dict(
                reversed(list(right_snapshot[field].items()))
            )
        retained_airport = next(iter(left["world_state"]["airports"].values()))

        self.assertTrue(
            migrate_schema_1_to_2(left, foundation_snapshot=left_snapshot).succeeded
        )
        self.assertTrue(
            migrate_schema_1_to_2(right, foundation_snapshot=right_snapshot).succeeded
        )
        self.assertEqual(canonical_bytes(left), canonical_bytes(right))
        committed = deepcopy(left)

        left_snapshot["regions"]["region-000000000001"]["display_name"] = "changed"
        left_snapshot["countries"]["country-000000000001"]["display_name"] = "changed"
        left_snapshot["airport_country_ids"].clear()
        retained_airport["display_name"] = "changed"
        self.assertEqual(left, committed)

    def test_exhausted_region_and_country_namespaces_restore_without_collision(self):
        world = make_schema1_world()
        snapshot = foundation_snapshot(world)
        maximum_region_id = f"region-{MAX_ENTITY_ID_NUMBER:012d}"
        maximum_country_id = f"country-{MAX_ENTITY_ID_NUMBER:012d}"
        region = snapshot["regions"].pop("region-000000000001")
        region["region_id"] = maximum_region_id
        snapshot["regions"][maximum_region_id] = region
        country = snapshot["countries"].pop("country-000000000001")
        country["country_id"] = maximum_country_id
        country["region_id"] = maximum_region_id
        snapshot["countries"][maximum_country_id] = country
        snapshot["countries"]["country-000000000002"]["region_id"] = (
            maximum_region_id
        )
        for airport_id, country_id in snapshot["airport_country_ids"].items():
            if country_id == "country-000000000001":
                snapshot["airport_country_ids"][airport_id] = maximum_country_id

        result = migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
        self.assertTrue(result.succeeded, result.as_dict())
        next_by_type = world["deterministic_state"]["id_allocator"][
            "next_by_type"
        ]
        self.assertEqual(next_by_type["region"], MAX_ENTITY_ID_NUMBER + 1)
        self.assertEqual(next_by_type["country"], MAX_ENTITY_ID_NUMBER + 1)
        self.assertTrue(validate_world(world).is_valid)
        with self.assertRaises(ValueError):
            allocate_id(world, "region")
        with self.assertRaises(ValueError):
            allocate_id(world, "country")

    def test_corrupt_v1_marker_aborts_before_migration(self):
        world = make_schema1_world()
        market_id, _resolution = resolve_first(world)
        key = f"{market_id}@2026-08-20"
        world["world_state"]["demand_state"]["processed_cohorts"][key][
            "resolution_fingerprint"
        ] = "0" * 64
        before = deepcopy(world)

        result = migrate_schema_1_to_2(
            world, foundation_snapshot=foundation_snapshot(world)
        )

        self.assertFalse(result.succeeded)
        self.assertIn(
            "inconsistent_demand_cohort_fingerprint",
            {issue.code for issue in result.issues},
        )
        self.assertEqual(world, before)

    def test_non_json_and_cyclic_snapshot_values_are_structured_failures(self):
        world = make_schema1_world()
        for invalid_value in ({"not-json"}, float("nan")):
            with self.subTest(invalid_value=invalid_value):
                snapshot = foundation_snapshot(world)
                snapshot["countries"]["country-000000000001"][
                    "display_name"
                ] = invalid_value
                before = deepcopy(world)
                result = migrate_schema_1_to_2(
                    world, foundation_snapshot=snapshot
                )
                self.assertFalse(result.succeeded)
                self.assertEqual(world, before)
        cyclic = foundation_snapshot(world)
        cyclic["cycle"] = cyclic
        before = deepcopy(world)
        result = migrate_schema_1_to_2(world, foundation_snapshot=cyclic)
        self.assertFalse(result.succeeded)
        self.assertEqual(world, before)


class Stage1Model4FoundationValidationTests(unittest.TestCase):
    def setUp(self):
        self.world = make_schema1_world()
        result = migrate_schema_1_to_2(
            self.world, foundation_snapshot=foundation_snapshot(self.world)
        )
        self.assertTrue(result.succeeded, result.as_dict())

    def test_alpha_profile_and_neutral_country_defaults_are_valid(self):
        demand = self.world["simulation"]["configuration"]["demand"]
        self.assertEqual(
            demand["travel_scope_configuration"]["default_profile"],
            {
                "domestic_weight_bps": 6500,
                "home_region_international_weight_bps": 2500,
                "rest_of_world_international_weight_bps": 1000,
            },
        )
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertTrue(
            all(
                country["demand_attractiveness_bps"] == 10_000
                and country["relationship_weight_bps"] == 10_000
                for country in self.world["world_state"]["countries"].values()
            )
        )

    def test_schema2_airport_addition_requires_immutable_country_mapping(self):
        before = deepcopy(self.world)
        with self.assertRaises(ValueError):
            add_airport_reference(
                self.world,
                airport("CEB", "PH", 1_000_000, 10.3, 123.9),
            )
        self.assertEqual(self.world, before)

        record = airport("CEB", "PH", 1_000_000, 10.3, 123.9)
        record["country_id"] = "country-000000000001"
        with self.assertRaises(ValueError):
            add_airport_reference(self.world, record)
        self.assertEqual(self.world, before)

        record["demand_allocation_member"] = True
        airport_id = add_airport_reference(self.world, record)
        self.assertEqual(
            self.world["world_state"]["airports"][airport_id]["country_id"],
            "country-000000000001",
        )
        self.assertTrue(validate_world(self.world).is_valid)

    def test_malformed_profiles_and_overrides_are_rejected(self):
        cases = (
            {"domestic_weight_bps": 10_000},
            {
                "domestic_weight_bps": 6500,
                "home_region_international_weight_bps": 2500,
                "rest_of_world_international_weight_bps": 999,
            },
            {
                "domestic_weight_bps": True,
                "home_region_international_weight_bps": 0,
                "rest_of_world_international_weight_bps": 10_000,
            },
            {
                "domestic_weight_bps": 6500.0,
                "home_region_international_weight_bps": 2500,
                "rest_of_world_international_weight_bps": 1000,
            },
            {
                "domestic_weight_bps": [],
                "home_region_international_weight_bps": 0,
                "rest_of_world_international_weight_bps": 10_000,
            },
        )
        for profile in cases:
            with self.subTest(profile=profile):
                world = deepcopy(self.world)
                world["simulation"]["configuration"]["demand"][
                    "travel_scope_configuration"
                ]["default_profile"] = profile
                self.assertIn("invalid_travel_scope_profile", issue_codes(world))
        world = deepcopy(self.world)
        world["simulation"]["configuration"]["demand"][
            "travel_scope_configuration"
        ]["country_overrides"]["country-000000000999"] = {
            "domestic_weight_bps": 6500,
            "home_region_international_weight_bps": 2500,
            "rest_of_world_international_weight_bps": 1000,
        }
        self.assertIn("dangling_reference", issue_codes(world))
        world = deepcopy(self.world)
        world["simulation"]["configuration"]["demand"][
            "travel_scope_configuration"
        ]["country_overrides"]["country-000000000001"] = {
            "domestic_weight_bps": 10_000
        }
        self.assertIn("invalid_travel_scope_profile", issue_codes(world))

        world = deepcopy(self.world)
        world["simulation"]["configuration"]["demand"][
            "travel_scope_configuration"
        ]["default_profile"] = MappingProxyType(
            {
                "domestic_weight_bps": 6500,
                "home_region_international_weight_bps": 2500,
                "rest_of_world_international_weight_bps": 1000,
            }
        )
        self.assertIn("not_json_compatible", issue_codes(world))

    def test_market_pack_shape_cohort_version_and_payload_key_are_strict(self):
        world = deepcopy(self.world)
        world["simulation"]["configuration"]["demand"][
            "market_pack_configuration"
        ]["market_pack_ids"] = ["pack-1"]
        self.assertIn("premature_market_pack_activation", issue_codes(world))

        world = deepcopy(self.world)
        world["world_state"]["demand_state"][
            "processed_cohort_schema_version"
        ] = 1
        self.assertIn("invalid_processed_cohort_schema_version", issue_codes(world))

        world = deepcopy(self.world)
        market_id, _resolution = resolve_first(world)
        key = f"{market_id}@2026-08-20"
        world["world_state"]["demand_state"]["processed_cohorts"][key][
            "payload"
        ]["cohort_key"] = f"{market_id}@2026-08-21"
        self.assertIn("id_key_mismatch", issue_codes(world))

    def test_region_country_identity_allocator_and_airport_references_are_strict(self):
        cases = []
        duplicate = deepcopy(self.world)
        duplicate["world_state"]["countries"]["country-000000000002"][
            "external_reference_code"
        ] = "PH"
        cases.append((duplicate, "duplicate_external_reference_code"))
        dangling = deepcopy(self.world)
        dangling["world_state"]["countries"]["country-000000000001"][
            "region_id"
        ] = "region-000000000999"
        cases.append((dangling, "dangling_reference"))
        allocator = deepcopy(self.world)
        allocator["deterministic_state"]["id_allocator"]["next_by_type"][
            "country"
        ] = 2
        cases.append((allocator, "id_allocator_collision"))
        airport_world = deepcopy(self.world)
        next(iter(airport_world["world_state"]["airports"].values()))[
            "demand_allocation_member"
        ] = 1
        cases.append((airport_world, "invalid_demand_allocation_member"))
        non_neutral = deepcopy(self.world)
        non_neutral["world_state"]["countries"]["country-000000000001"][
            "demand_attractiveness_bps"
        ] = 9_999
        cases.append((non_neutral, "invalid_country_demand_field"))
        for world, code in cases:
            with self.subTest(code=code):
                self.assertIn(code, issue_codes(world))

    def test_unknown_wrapper_and_premature_model4_activation_are_rejected(self):
        market_id, _resolution = resolve_first(self.world)
        key = f"{market_id}@2026-08-20"
        self.world["world_state"]["demand_state"]["processed_cohorts"][key][
            "contract"
        ] = "UNKNOWN"
        self.assertIn("unknown_processed_cohort_contract", issue_codes(self.world))

        world = deepcopy(self.world)
        world["simulation"]["configuration"]["demand"]["model_version"] = 4
        self.assertIn("unsupported_demand_model", issue_codes(world))

        world = deepcopy(self.world)
        world["world_state"]["demand_state"]["model3_terminal_demand_revision"] = 1
        self.assertIn("premature_model4_activation", issue_codes(world))

    def test_malformed_model4_context_and_cohort_contract_do_not_crash(self):
        world = deepcopy(self.world)
        indexes = calculate_world_demand(world).indexes
        if indexes is None:
            self.fail("test fixture did not build demand indexes")
        market_id = sorted(indexes.by_market)[0]
        world["world_state"]["demand_state"]["model4_revision_contexts"][
            "context-1"
        ] = {"revision_context_id": "context-1", "demand_model_version": 4}
        self.assertIn("invalid_model4_revision_context", issue_codes(world))

        key = f"{market_id}@2026-08-22"
        world["world_state"]["demand_state"]["processed_cohorts"][key] = {
            "contract": MODEL4_TRAVEL_SCOPE_COHORT_V1,
            "payload": {"cohort_key": key},
        }
        codes = issue_codes(world)
        self.assertIn("invalid_demand_cohort", codes)
        self.assertIn("premature_model4_activation", codes)

    def test_dictionary_order_independence_and_complete_json_serializability(self):
        reordered = deepcopy(self.world)
        reordered["world_state"]["regions"] = dict(
            reversed(list(reordered["world_state"]["regions"].items()))
        )
        reordered["world_state"]["countries"] = dict(
            reversed(list(reordered["world_state"]["countries"].items()))
        )
        self.assertTrue(validate_world(reordered).is_valid)
        self.assertEqual(
            json.dumps(self.world, sort_keys=True, separators=(",", ":")),
            json.dumps(reordered, sort_keys=True, separators=(",", ":")),
        )


if __name__ == "__main__":
    unittest.main()
