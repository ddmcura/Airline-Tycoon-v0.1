import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from game.booking import (
    calculate_booking_configuration_fingerprint,
    new_booking_configuration,
    rebuild_booking_indexes,
)
from game.demand import calculate_world_demand, resolve_daily_cohort
from game.world_state import (
    allocate_id,
    migrate_schema_1_to_2,
    migrate_schema_2_to_3,
    validate_world,
)
from game.world_state.schema import (
    DEFAULT_BOOKING_CONFIGURATION,
    SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT,
    SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT,
)
from game.scheduling import publish_occurrences_through
from tests.test_stage1_compact_demand import _publish_direct_service
from tests.test_stage1_demand_model4_foundation import (
    foundation_snapshot,
    make_schema1_world,
    resolve_first,
)
from tests.test_stage1_world_demand import make_demand_world


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def make_schema2_world():
    world = make_schema1_world()
    result = migrate_schema_1_to_2(
        world, foundation_snapshot=foundation_snapshot(world)
    )
    if not result.succeeded:
        raise AssertionError(result.as_dict())
    return world


def migrate(world):
    result = migrate_schema_2_to_3(world)
    if not result.succeeded:
        raise AssertionError(result.as_dict())
    return result.migrated_world


def issue_codes(world):
    return {issue.code for issue in validate_world(world).errors}


def changed_leaf_paths(before, after, path="$"):
    """Return deterministic structural leaf changes for migration allowlisting."""
    if type(before) is not type(after):
        return {path}
    if type(before) is dict:
        changed = set()
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before or key not in after:
                changed.add(child)
            else:
                changed.update(changed_leaf_paths(before[key], after[key], child))
        return changed
    if type(before) is list:
        return set() if before == after else {path}
    return set() if before == after else {path}


def make_schema2_with_flight_and_legacy_booking(*, passenger_count=12):
    world, ids = make_demand_world(("MNL", "DVO"))
    market_id, flight_id = _publish_direct_service(world, ids, "DVO")
    result = migrate_schema_1_to_2(
        world, foundation_snapshot=foundation_snapshot(world)
    )
    if not result.succeeded:
        raise AssertionError(result.as_dict())
    airline_id = world["world_state"]["player"]["primary_airline_id"]
    itinerary_id = allocate_id(world, "itinerary")
    world["world_state"]["itineraries"][itinerary_id] = {
        "itinerary_id": itinerary_id,
        "airline_id": airline_id,
        "dated_flight_ids": [flight_id],
    }
    booking_id = allocate_id(world, "booking")
    world["world_state"]["bookings"][booking_id] = {
        "booking_id": booking_id,
        "airline_id": airline_id,
        "itinerary_id": itinerary_id,
        "passenger_count": passenger_count,
        "booked_at_utc": world["simulation"]["time_utc"],
        "total_fare_minor": passenger_count * 10_000,
        "currency": "USD",
        "status": "CONFIRMED",
    }
    if not validate_world(world).is_valid:
        raise AssertionError(validate_world(world).as_dict())
    return world, market_id, flight_id, itinerary_id, booking_id


class BookingConfigurationTests(unittest.TestCase):
    def test_approved_default_is_detached_complete_and_stable(self):
        left = new_booking_configuration()
        right = new_booking_configuration()
        self.assertEqual(left, right)
        self.assertIsNot(left, right)
        self.assertEqual(left["booking_horizon_days"], 365)
        self.assertEqual(left["desired_date_tolerance_days"], 3)
        self.assertEqual(sum(item["weight_bps"] for item in left["lead_time_buckets"]), 10_000)
        covered = [
            day
            for bucket in left["lead_time_buckets"]
            for day in range(bucket["minimum_lead_days"], bucket["maximum_lead_days"] + 1)
        ]
        self.assertEqual(covered, list(range(366)))
        self.assertEqual(
            left["configuration_fingerprint"],
            calculate_booking_configuration_fingerprint(left),
        )
        self.assertEqual(DEFAULT_BOOKING_CONFIGURATION["configuration_fingerprint"], "")

    def test_fingerprint_is_dictionary_order_independent_and_booking_owned(self):
        world = migrate(make_schema2_world())
        expected = calculate_booking_configuration_fingerprint(world)
        configuration = world["simulation"]["configuration"]["booking"]
        configuration.clear()
        configuration.update(reversed(list(new_booking_configuration().items())))
        self.assertEqual(calculate_booking_configuration_fingerprint(world), expected)
        for mutate in (
            lambda value: value["world_state"]["airlines"].update({}),
            lambda value: value["ui_state"].update({"selected_screen": "BOOKING"}),
            lambda value: value["world_state"]["demand_state"].update({"unused": "not fingerprint input"}),
        ):
            candidate = deepcopy(world)
            mutate(candidate)
            self.assertEqual(calculate_booking_configuration_fingerprint(candidate), expected)

    def test_every_nonbooking_authority_family_is_outside_fingerprint(self):
        world, _market, flight_id, _itinerary, _booking = (
            make_schema2_with_flight_and_legacy_booking()
        )
        world = migrate(world)
        expected = calculate_booking_configuration_fingerprint(world)
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        account_id = state["airlines"][airline_id]["financial_account_ids"][0]
        mutations = (
            lambda value: value["simulation"]["configuration"]["demand"].update(
                daily_booker_rate_ppm=123
            ),
            lambda value: value["world_state"]["demand_state"].update(
                demand_model_revision=999
            ),
            lambda value: value["simulation"]["configuration"]["demand"][
                "market_pack_configuration"
            ].update(revision=999),
            lambda value: next(
                iter(value["world_state"]["airports"].values())
            ).update(display_name="Changed"),
            lambda value: next(
                iter(value["world_state"]["directional_markets"].values())
            ).update(origin_airport_id="airport-other"),
            lambda value: next(
                iter(value["world_state"]["schedule_definitions"].values())
            ).update(status="RETIRED"),
            lambda value: value["world_state"]["dated_flights"][flight_id].update(
                capacity=1, inventory_revision=7
            ),
            lambda value: value["world_state"]["dated_flights"][flight_id][
                "fare_offer"
            ].update(amount_minor=1),
            lambda value: value["world_state"]["airlines"][airline_id].update(
                display_name="Changed", finance_revision=7
            ),
            lambda value: value["world_state"]["financial_accounts"][
                account_id
            ].update(balance_minor=1),
            lambda value: value["world_state"]["transactions"].update(
                arbitrary={}
            ),
            lambda value: value["ui_state"].update(
                selected_screen="BOOKING", current_focus_airline_id=None
            ),
        )
        for mutate in mutations:
            candidate = deepcopy(world)
            mutate(candidate)
            self.assertEqual(
                calculate_booking_configuration_fingerprint(candidate),
                expected,
            )

    def test_every_owned_field_changes_fingerprint(self):
        base = new_booking_configuration()
        mutations = {
            "contract": lambda value: value.update(contract="OTHER"),
            "configuration_version": lambda value: value.update(configuration_version="v2"),
            "revision": lambda value: value.update(revision=2),
            "booking_horizon_days": lambda value: value.update(booking_horizon_days=364),
            "desired_date_policy": lambda value: value.update(desired_date_policy="OTHER"),
            "lead_time_buckets": lambda value: value["lead_time_buckets"][0].update(weight_bps=499),
            "desired_date_tolerance_days": lambda value: value.update(desired_date_tolerance_days=2),
            "choice_policy": lambda value: value["choice_policy"].update(currency_policy="OTHER"),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                changed = deepcopy(base)
                mutate(changed)
                self.assertNotEqual(
                    calculate_booking_configuration_fingerprint(changed),
                    base["configuration_fingerprint"],
                )

    def test_bucket_shape_ranges_total_horizon_tolerance_and_booleans_reject(self):
        base = migrate(make_schema2_world())
        cases = []
        for mutation in (
            lambda c: c["lead_time_buckets"][0].update(extra=1),
            lambda c: c["lead_time_buckets"][1].update(minimum_lead_days=2),
            lambda c: c["lead_time_buckets"][1].update(minimum_lead_days=0),
            lambda c: c["lead_time_buckets"].reverse(),
            lambda c: c["lead_time_buckets"].append(deepcopy(c["lead_time_buckets"][-1])),
            lambda c: c.update(booking_horizon_days=366),
            lambda c: c.update(desired_date_tolerance_days=366),
            lambda c: c.update(revision=True),
            lambda c: c["choice_policy"].update(unknown=True),
        ):
            candidate = deepcopy(base)
            configuration = candidate["simulation"]["configuration"]["booking"]
            mutation(configuration)
            configuration["configuration_fingerprint"] = calculate_booking_configuration_fingerprint(configuration)
            cases.append(candidate)
        for candidate in cases:
            with self.subTest(candidate=candidate["simulation"]["configuration"]["booking"]):
                self.assertIn("invalid_booking_configuration", issue_codes(candidate))

    def test_forged_fingerprint_and_mixed_currency_policy_reject(self):
        world = migrate(make_schema2_world())
        configuration = world["simulation"]["configuration"]["booking"]
        configuration["configuration_fingerprint"] = "0" * 64
        self.assertIn("inconsistent_booking_configuration_fingerprint", issue_codes(world))
        configuration = new_booking_configuration()
        configuration["choice_policy"]["currency_policy"] = "MIXED_CURRENCY"
        configuration["configuration_fingerprint"] = calculate_booking_configuration_fingerprint(configuration)
        world["simulation"]["configuration"]["booking"] = configuration
        self.assertIn("invalid_booking_configuration", issue_codes(world))

    def test_fingerprint_rejects_malformed_keys_through_value_error_boundary(self):
        malformed = new_booking_configuration()
        malformed[1] = "not a canonical field"
        with self.assertRaises(ValueError):
            calculate_booking_configuration_fingerprint(malformed)


class BookingMigrationTests(unittest.TestCase):
    def test_migration_structural_diff_uses_explicit_5a_allowlist(self):
        source, _market, flight_id, itinerary_id, booking_id = (
            make_schema2_with_flight_and_legacy_booking()
        )
        candidate = migrate(source)
        paths = changed_leaf_paths(source, candidate)
        exact = {
            "$.metadata.save_schema_version",
            "$.simulation.configuration.booking",
            "$.world_state.booking_state",
            "$.deterministic_state.id_allocator.next_by_type.booking_checkpoint",
        }
        prefixes = {
            f"$.world_state.airlines.{airline_id}.finance_revision"
            for airline_id in source["world_state"]["airlines"]
        } | {
            f"$.world_state.dated_flights.{dated_flight_id}.inventory_revision"
            for dated_flight_id in source["world_state"]["dated_flights"]
        } | {
            f"$.world_state.itineraries.{itinerary_id}",
            f"$.world_state.bookings.{booking_id}",
        }
        unexpected = {
            path
            for path in paths
            if path not in exact
            and not any(
                path == prefix or path.startswith(f"{prefix}.")
                for prefix in prefixes
            )
        }
        self.assertEqual(unexpected, set())
        self.assertTrue(exact <= paths)
        self.assertIn(
            f"$.world_state.dated_flights.{flight_id}.inventory_revision",
            paths,
        )

    def test_candidate_construction_and_final_validation_fail_atomically(self):
        source = make_schema2_world()
        before = deepcopy(source)
        with patch(
            "game.world_state.migration.new_booking_configuration",
            side_effect=ValueError("injected configuration failure"),
        ):
            result = migrate_schema_2_to_3(source)
        self.assertFalse(result.succeeded)
        self.assertEqual(source, before)

        from game.world_state.validation import ValidationIssue, ValidationResult

        real_validate = validate_world
        calls = 0

        def fail_final(candidate):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_validate(candidate)
            return ValidationResult(
                (
                    ValidationIssue(
                        "injected_final_validation",
                        "$",
                        "injected final validation failure",
                    ),
                )
            )

        with patch("game.world_state.migration.validate_world", side_effect=fail_final):
            result = migrate_schema_2_to_3(source)
        self.assertFalse(result.succeeded)
        self.assertEqual(source, before)

    def test_valid_schema2_aliases_are_detached_during_migration(self):
        source = make_schema2_world()
        shared = []
        source["world_state"]["history"]["operations"] = shared
        source["world_state"]["history"]["financial"] = shared
        self.assertTrue(validate_world(source).is_valid)
        before = canonical_bytes(source)
        result = migrate_schema_2_to_3(source)
        self.assertTrue(result.succeeded, result.as_dict())
        self.assertEqual(canonical_bytes(source), before)
        history = result.migrated_world["world_state"]["history"]
        self.assertIsNot(history["operations"], history["financial"])

    def test_empty_migration_is_deterministic_detached_and_preserves_authority(self):
        source = make_schema2_world()
        resolve_first(source)
        before = deepcopy(source)
        left_result = migrate_schema_2_to_3(source)
        right_result = migrate_schema_2_to_3(deepcopy(source))
        self.assertTrue(left_result.succeeded, left_result.as_dict())
        self.assertEqual(canonical_bytes(left_result.migrated_world), canonical_bytes(right_result.migrated_world))
        self.assertEqual(source, before)
        candidate = left_result.migrated_world
        self.assertEqual(candidate["metadata"]["save_schema_version"], 3)
        self.assertEqual(candidate["world_state"]["booking_state"], {"booking_revision": 0, "booking_checkpoints": {}})
        self.assertEqual(candidate["deterministic_state"]["id_allocator"]["next_by_type"]["booking_checkpoint"], 1)
        self.assertTrue(validate_world(candidate).is_valid, validate_world(candidate).as_dict())
        preserved = (
            "regions", "countries", "airports", "aircraft", "directional_markets",
            "connections", "schedule_definitions", "pending_events", "event_history",
            "financial_accounts", "transactions", "history", "demand_state",
        )
        for field in preserved:
            self.assertEqual(candidate["world_state"][field], before["world_state"][field], field)
        candidate["world_state"]["history"]["operations"].append("changed")
        self.assertEqual(source, before)

    def test_revisions_and_allocator_boundaries_are_added_without_other_allocation(self):
        source, _market, flight_id, _itinerary, _booking = make_schema2_with_flight_and_legacy_booking()
        old_allocators = deepcopy(source["deterministic_state"]["id_allocator"]["next_by_type"])
        candidate = migrate(source)
        self.assertEqual(candidate["world_state"]["dated_flights"][flight_id]["inventory_revision"], 0)
        self.assertTrue(all(airline["finance_revision"] == 0 for airline in candidate["world_state"]["airlines"].values()))
        allocators = candidate["deterministic_state"]["id_allocator"]["next_by_type"]
        self.assertEqual({key: value for key, value in allocators.items() if key != "booking_checkpoint"}, old_allocators)
        self.assertEqual(allocators["booking_checkpoint"], 1)
        self.assertEqual(candidate["world_state"]["transactions"], source["world_state"]["transactions"])

    def test_nonempty_placeholders_are_wrapped_byte_exact_and_indexed(self):
        source, _market, flight_id, itinerary_id, booking_id = make_schema2_with_flight_and_legacy_booking(passenger_count=17)
        old_itinerary = deepcopy(source["world_state"]["itineraries"][itinerary_id])
        old_booking = deepcopy(source["world_state"]["bookings"][booking_id])
        candidate = migrate(source)
        itinerary = candidate["world_state"]["itineraries"][itinerary_id]
        booking = candidate["world_state"]["bookings"][booking_id]
        self.assertEqual(itinerary["contract"], SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT)
        self.assertEqual(booking["contract"], SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT)
        self.assertEqual(canonical_bytes(itinerary["payload"]), canonical_bytes(old_itinerary))
        self.assertEqual(canonical_bytes(booking["payload"]), canonical_bytes(old_booking))
        indexes = rebuild_booking_indexes(candidate)
        self.assertEqual(dict(indexes.booked_passenger_count_by_dated_flight_id), {})
        self.assertEqual(indexes.booking_ids_by_dated_flight_id[flight_id], (booking_id,))

    def test_legacy_status_has_no_confirmed_capacity_semantics(self):
        source, _market, flight_id, _itinerary, booking_id = make_schema2_with_flight_and_legacy_booking()
        source["world_state"]["bookings"][booking_id]["passenger_count"] = 181
        source["world_state"]["bookings"][booking_id]["total_fare_minor"] = 1_810_000
        self.assertTrue(validate_world(source).is_valid)
        before = deepcopy(source)
        result = migrate_schema_2_to_3(source)
        self.assertTrue(result.succeeded, result.as_dict())
        self.assertEqual(source, before)
        indexes = rebuild_booking_indexes(result.migrated_world)
        self.assertEqual(
            dict(indexes.booked_passenger_count_by_dated_flight_id), {}
        )
        self.assertEqual(
            indexes.booking_ids_by_dated_flight_id[flight_id], (booking_id,)
        )

        alternate = deepcopy(source)
        alternate["world_state"]["bookings"][booking_id]["status"] = "HELD"
        alternate_result = migrate_schema_2_to_3(alternate)
        self.assertTrue(alternate_result.succeeded, alternate_result.as_dict())

    def test_malformed_repeated_and_future_sources_reject_without_mutation(self):
        malformed = make_schema2_world()
        malformed["world_state"]["airlines"] = []
        before = deepcopy(malformed)
        result = migrate_schema_2_to_3(malformed)
        self.assertFalse(result.succeeded)
        self.assertEqual(malformed, before)
        schema3 = migrate(make_schema2_world())
        repeated_before = deepcopy(schema3)
        repeated = migrate_schema_2_to_3(schema3)
        self.assertFalse(repeated.succeeded)
        self.assertEqual(schema3, repeated_before)
        future = deepcopy(schema3)
        future["metadata"]["save_schema_version"] = 4
        self.assertFalse(migrate_schema_2_to_3(future).succeeded)

    def test_model4_authority_and_future_outcomes_are_unchanged(self):
        from tests.test_stage1_demand_model4 import model4_world
        from game.demand.model4 import _source_fingerprint
        from game.world_state.demand_fingerprint import (
            calculate_market_pack_fingerprint,
            calculate_model4_input_fingerprint,
        )

        source, _ids, _old = model4_world(model3_marker=True)
        demand_before = deepcopy(source["world_state"]["demand_state"])
        fingerprints_before = (
            calculate_model4_input_fingerprint(source),
            _source_fingerprint(source),
            calculate_market_pack_fingerprint(source),
        )
        candidate = migrate(source)
        self.assertEqual(candidate["world_state"]["demand_state"], demand_before)
        self.assertEqual(
            (
                calculate_model4_input_fingerprint(candidate),
                _source_fingerprint(candidate),
                calculate_market_pack_fingerprint(candidate),
            ),
            fingerprints_before,
        )
        self.assertTrue(validate_world(candidate).is_valid, validate_world(candidate).as_dict())
        left = calculate_world_demand(source)
        right = calculate_world_demand(candidate)
        self.assertEqual(left.issues, right.issues)
        self.assertEqual(left.indexes, right.indexes)

    def test_model3_and_model4_cohort_bytes_survive_together(self):
        from game.demand import resolve_active_daily_cohorts
        from tests.test_stage1_demand_model4 import model4_world

        source, ids, _old = model4_world(model3_marker=True)
        source["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, _flight_id = _publish_direct_service(source, ids, "DVO")
        resolved = resolve_active_daily_cohorts(source, "2026-08-24")
        self.assertTrue(resolved.succeeded, resolved.issues)
        demand_before = canonical_bytes(source["world_state"]["demand_state"])
        candidate = migrate(source)
        self.assertEqual(
            canonical_bytes(candidate["world_state"]["demand_state"]),
            demand_before,
        )
        contracts = {
            record["contract"]
            for record in candidate["world_state"]["demand_state"][
                "processed_cohorts"
            ].values()
        }
        self.assertEqual(
            contracts,
            {"MODEL3_PROCESSED_COHORT_V1", "MODEL4_TRAVEL_SCOPE_COHORT_V1"},
        )

    def test_schema3_model4_pack_demand_and_scheduling_commands_preserve_5a(self):
        from game.demand import activate_model4, resolve_active_daily_cohorts
        from game.world_state import (
            disable_country_pack,
            enable_country_pack,
            materialize_country_pack,
        )
        from tests.test_stage1_demand_model4 import model4_world
        from tests.test_stage1_market_packs import vietnam_catalog

        captured = {}

        def capture_pre_activation(world, **_kwargs):
            captured["world"] = deepcopy(world)
            return SimpleNamespace(succeeded=True, issues=())

        with patch(
            "tests.test_stage1_demand_model4.activate_model4",
            side_effect=capture_pre_activation,
        ):
            model4_world()
        world = migrate(captured["world"])
        existing_airline_id = world["world_state"]["player"][
            "primary_airline_id"
        ]
        world["world_state"]["airlines"][existing_airline_id][
            "finance_revision"
        ] = 7
        expected_finance_revisions = {
            airline_id: airline["finance_revision"]
            for airline_id, airline in world["world_state"]["airlines"].items()
        }
        booking_before = canonical_bytes(
            (
                world["simulation"]["configuration"]["booking"],
                world["world_state"]["booking_state"],
            )
        )
        activation = activate_model4(
            world,
            expected_revision=world["world_state"]["demand_state"][
                "demand_model_revision"
            ],
        )
        self.assertTrue(activation.succeeded, activation.issues)
        self.assertEqual(
            canonical_bytes(
                (
                    world["simulation"]["configuration"]["booking"],
                    world["world_state"]["booking_state"],
                )
            ),
            booking_before,
        )

        country_id = next(
            key
            for key, country in world["world_state"]["countries"].items()
            if country["external_reference_code"] == "VN"
        )
        pack = world["simulation"]["configuration"]["demand"][
            "market_pack_configuration"
        ]
        materialized = materialize_country_pack(
            world,
            country_id,
            "test-southeast-asia-vn",
            "2026.1",
            vietnam_catalog(),
            expected_pack_revision=pack["revision"],
            expected_demand_revision=world["world_state"]["demand_state"][
                "demand_model_revision"
            ],
        )
        self.assertTrue(materialized.succeeded, materialized.issues)
        disabled = disable_country_pack(
            world,
            country_id,
            expected_pack_revision=materialized.pack_revision,
        )
        self.assertTrue(disabled.succeeded, disabled.issues)
        enabled = enable_country_pack(
            world,
            country_id,
            expected_pack_revision=disabled.pack_revision,
            pack_reference="test-southeast-asia-vn",
            pack_version="2026.1",
        )
        self.assertTrue(enabled.succeeded, enabled.issues)

        ids = {
            airport["reference_code"]: airport_id
            for airport_id, airport in world["world_state"]["airports"].items()
        }
        world["simulation"]["time_utc"] = "2026-08-24T00:00:00Z"
        market_id, flight_id = _publish_direct_service(world, ids, "DVO")
        resolved = resolve_active_daily_cohorts(world, "2026-08-24")
        self.assertTrue(resolved.succeeded, resolved.issues)
        self.assertIn(market_id, resolved.active_market_ids)
        self.assertEqual(
            world["world_state"]["dated_flights"][flight_id][
                "inventory_revision"
            ],
            0,
        )
        self.assertEqual(
            {
                airline_id: airline["finance_revision"]
                for airline_id, airline in world["world_state"][
                    "airlines"
                ].items()
            },
            expected_finance_revisions,
        )
        self.assertEqual(
            canonical_bytes(
                (
                    world["simulation"]["configuration"]["booking"],
                    world["world_state"]["booking_state"],
                )
            ),
            booking_before,
        )

        from game.world_state import add_airline

        added_airline_id = add_airline(world, "Schema 3 Construction Test")
        self.assertEqual(
            world["world_state"]["airlines"][added_airline_id][
                "finance_revision"
            ],
            0,
        )
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())


class BookingSchemaValidationTests(unittest.TestCase):
    def test_runtime_indexes_have_deterministic_safe_exception_boundary(self):
        with self.assertRaises(ValueError):
            rebuild_booking_indexes({"world_state": []})

    def test_schema2_rejects_schema3_authority(self):
        world = make_schema2_world()
        world["simulation"]["configuration"]["booking"] = (
            new_booking_configuration()
        )
        self.assertFalse(validate_world(world).is_valid)

        world = make_schema2_world()
        next(iter(world["world_state"]["airlines"].values()))[
            "finance_revision"
        ] = 0
        self.assertFalse(validate_world(world).is_valid)

        world = make_schema2_world()
        world["world_state"]["booking_state"] = {
            "booking_revision": 0,
            "booking_checkpoints": {},
        }
        world["deterministic_state"]["id_allocator"]["next_by_type"][
            "booking_checkpoint"
        ] = 1
        with self.assertRaises(ValueError):
            allocate_id(world, "booking_checkpoint")

    def test_hostile_schema3_records_return_issues_instead_of_crashing(self):
        base = migrate(make_schema2_world())
        mutations = (
            lambda value: value["world_state"]["airlines"].update(
                {next(iter(value["world_state"]["airlines"])): []}
            ),
            lambda value: value["world_state"]["itineraries"].update(
                {"itinerary-000000000001": []}
            ),
            lambda value: value["world_state"]["bookings"].update(
                {"booking-000000000001": []}
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                candidate = deepcopy(base)
                mutate(candidate)
                self.assertFalse(validate_world(candidate).is_valid)

    def test_empty_schema3_and_revision_tokens_are_strict(self):
        world = migrate(make_schema2_world())
        self.assertTrue(validate_world(world).is_valid)
        cases = (
            (lambda value: value["world_state"]["booking_state"].update(booking_revision=True), "invalid_booking_state"),
            (lambda value: next(iter(value["world_state"]["airlines"].values())).update(finance_revision=True), "invalid_finance_revision"),
            (lambda value: value["deterministic_state"]["id_allocator"]["next_by_type"].update(booking_checkpoint=True), "invalid_id_allocator"),
            (lambda value: value["world_state"]["booking_state"].update(runtime_index={}), "invalid_booking_state"),
        )
        for mutate, code in cases:
            candidate = deepcopy(world)
            mutate(candidate)
            self.assertIn(code, issue_codes(candidate))

    def test_schema3_republication_preserves_inventory_tokens(self):
        source, _market, first_flight_id, _itinerary, _booking = (
            make_schema2_with_flight_and_legacy_booking()
        )
        world = migrate(source)
        world["world_state"]["dated_flights"][first_flight_id]["inventory_revision"] = 7
        result = publish_occurrences_through(world, "2026-08-24T00:00:00Z")
        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(world["world_state"]["dated_flights"][first_flight_id]["inventory_revision"], 7)
        self.assertFalse(result.created_dated_flight_ids)
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())

    def test_pending_checkpoint_shape_and_allocator_are_strict(self):
        world = migrate(make_schema2_world())
        checkpoint_id = allocate_id(world, "booking_checkpoint")
        configuration = world["simulation"]["configuration"]["booking"]
        demand = world["world_state"]["demand_state"]
        pack = world["simulation"]["configuration"]["demand"]["market_pack_configuration"]
        world["world_state"]["booking_state"]["booking_checkpoints"][checkpoint_id] = {
            "booking_checkpoint_id": checkpoint_id,
            "checkpoint_date": "2026-08-20",
            "due_at_utc": "2026-08-20T00:00:00Z",
            "status": "PENDING",
            "processed_at_utc": None,
            "booking_revision": 0,
            "booking_configuration_revision": configuration["revision"],
            "booking_configuration_fingerprint": configuration["configuration_fingerprint"],
            "demand_model_revision": demand["demand_model_revision"],
            "market_pack_revision": pack["revision"],
            "market_results": {},
            "financial_transaction_ids": [],
        }
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())
        stale = deepcopy(world)
        stale["world_state"]["booking_state"]["booking_revision"] = 1
        self.assertIn("inconsistent_booking_revision", issue_codes(stale))
        malformed = deepcopy(world)
        malformed["world_state"]["booking_state"]["booking_checkpoints"][checkpoint_id]["extra"] = None
        self.assertIn("invalid_booking_checkpoint", issue_codes(malformed))
        nonempty = deepcopy(world)
        nonempty["world_state"]["booking_state"]["booking_checkpoints"][checkpoint_id]["financial_transaction_ids"] = ["transaction-000000000001"]
        self.assertIn("invalid_booking_checkpoint", issue_codes(nonempty))

    def test_contracts_unknown_fields_cycles_aliases_and_runtime_capacity_reject(self):
        world, _market, flight_id, itinerary_id, booking_id = make_schema2_with_flight_and_legacy_booking()
        world = migrate(world)
        world["world_state"]["dated_flights"][flight_id]["remaining_capacity"] = 1
        self.assertIn("invalid_inventory", issue_codes(world))
        world = migrate(make_schema2_with_flight_and_legacy_booking()[0])
        world["world_state"]["itineraries"][itinerary_id]["extra"] = None
        self.assertIn("invalid_itinerary", issue_codes(world))
        world = migrate(make_schema2_with_flight_and_legacy_booking()[0])
        world["world_state"]["bookings"][booking_id]["contract"] = "UNKNOWN"
        self.assertIn("invalid_booking", issue_codes(world))
        cyclic = migrate(make_schema2_world())
        cyclic["world_state"]["booking_state"]["cycle"] = cyclic["world_state"]["booking_state"]
        self.assertFalse(validate_world(cyclic).is_valid)
        aliased = migrate(make_schema2_world())
        buckets = aliased["simulation"]["configuration"]["booking"]["lead_time_buckets"]
        buckets[1] = buckets[0]
        self.assertIn("invalid_world_state", issue_codes(aliased))

    def test_strict_future_direct_itinerary_booking_and_result_topology(self):
        source, market_id, flight_id, _legacy_itinerary, _legacy_booking = (
            make_schema2_with_flight_and_legacy_booking()
        )
        resolution = resolve_daily_cohort(source, market_id, "2026-08-20")
        self.assertGreaterEqual(resolution.actual_daily_bookers, 0)
        world = migrate(source)
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        flight = state["dated_flights"][flight_id]
        itinerary_id = allocate_id(world, "itinerary")
        booking_id = allocate_id(world, "booking")
        transaction_id = allocate_id(world, "transaction")
        checkpoint_id = allocate_id(world, "booking_checkpoint")
        account_ids = state["airlines"][airline_id]["financial_account_ids"]
        state["transactions"][transaction_id] = {
            "transaction_id": transaction_id,
            "airline_id": airline_id,
            "occurred_at_utc": world["simulation"]["time_utc"],
            "description": "Future Booking contract fixture",
            "entries": [
                {"account_id": account_ids[0], "amount_minor": 30_000},
                {"account_id": account_ids[3], "amount_minor": -30_000},
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
        cohort_key = f"{market_id}@2026-08-20"
        state["booking_state"]["booking_revision"] = 1
        state["bookings"][booking_id] = {
            "booking_id": booking_id,
            "contract": "STAGE1_AGGREGATE_BOOKING_V1",
            "booking_checkpoint_id": checkpoint_id,
            "cohort_key": cohort_key,
            "desired_travel_date": flight["scheduled_departure_local_date"],
            "airline_id": airline_id,
            "itinerary_id": itinerary_id,
            "passenger_count": 3,
            "booked_at_utc": world["simulation"]["time_utc"],
            "total_fare_minor": 30_000,
            "currency": "USD",
            "inventory_revision_at_commit": 0,
            "finance_transaction_id": transaction_id,
            "booking_revision": 1,
            "status": "CONFIRMED",
        }
        booking_configuration = world["simulation"]["configuration"]["booking"]
        demand = state["demand_state"]
        pack = world["simulation"]["configuration"]["demand"]["market_pack_configuration"]
        state["booking_state"]["booking_checkpoints"][checkpoint_id] = {
            "booking_checkpoint_id": checkpoint_id,
            "checkpoint_date": "2026-08-20",
            "due_at_utc": "2026-08-20T00:00:00Z",
            "status": "COMPLETED",
            "processed_at_utc": world["simulation"]["time_utc"],
            "booking_revision": 1,
            "booking_configuration_revision": booking_configuration["revision"],
            "booking_configuration_fingerprint": booking_configuration["configuration_fingerprint"],
            "demand_model_revision": demand["demand_model_revision"],
            "market_pack_revision": pack["revision"],
            "market_results": {
                market_id: {
                    "market_id": market_id,
                    "cohort_key": cohort_key,
                    "desired_passenger_count": 3,
                    "booked_passenger_count": 3,
                    "outside_option_passenger_count": 0,
                    "booking_ids": [booking_id],
                }
            },
            "financial_transaction_ids": [transaction_id],
        }
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())
        indexes = rebuild_booking_indexes(world)
        self.assertEqual(
            indexes.checkpoint_id_by_date["2026-08-20"], checkpoint_id
        )
        self.assertEqual(
            indexes.booked_passenger_count_by_dated_flight_id[flight_id], 3
        )
        self.assertEqual(
            indexes.booking_ids_by_checkpoint_id[checkpoint_id], (booking_id,)
        )
        self.assertIn(
            _legacy_booking,
            indexes.booking_ids_by_dated_flight_id[flight_id],
        )
        indexed_ids = indexes.booking_ids_by_dated_flight_id[flight_id]
        world["world_state"]["bookings"][booking_id]["passenger_count"] = 4
        self.assertEqual(
            indexes.booking_ids_by_dated_flight_id[flight_id], indexed_ids
        )
        world["world_state"]["bookings"][booking_id]["passenger_count"] = 3
        exact_capacity = deepcopy(world)
        exact_booking = exact_capacity["world_state"]["bookings"][booking_id]
        exact_booking["passenger_count"] = 180
        exact_booking["total_fare_minor"] = 1_800_000
        exact_result = exact_capacity["world_state"]["booking_state"][
            "booking_checkpoints"
        ][checkpoint_id]["market_results"][market_id]
        exact_result["desired_passenger_count"] = 180
        exact_result["booked_passenger_count"] = 180
        self.assertTrue(
            validate_world(exact_capacity).is_valid,
            validate_world(exact_capacity).as_dict(),
        )
        oversold = deepcopy(exact_capacity)
        oversold_booking = oversold["world_state"]["bookings"][booking_id]
        oversold_booking["passenger_count"] = 181
        oversold_booking["total_fare_minor"] = 1_810_000
        oversold_result = oversold["world_state"]["booking_state"][
            "booking_checkpoints"
        ][checkpoint_id]["market_results"][market_id]
        oversold_result["desired_passenger_count"] = 181
        oversold_result["booked_passenger_count"] = 181
        self.assertIn("invalid_inventory", issue_codes(oversold))
        bad_fare = deepcopy(world)
        bad_fare["world_state"]["bookings"][booking_id]["total_fare_minor"] += 1
        self.assertIn("invalid_booking", issue_codes(bad_fare))
        bad_result = deepcopy(world)
        bad_result["world_state"]["booking_state"]["booking_checkpoints"][checkpoint_id]["market_results"][market_id]["extra"] = None
        self.assertIn("result_validation_failed", issue_codes(bad_result))
        stale_checkpoint = deepcopy(world)
        stale_checkpoint["world_state"]["booking_state"]["booking_checkpoints"][
            checkpoint_id
        ]["booking_revision"] = 0
        self.assertIn(
            "inconsistent_booking_revision", issue_codes(stale_checkpoint)
        )
        unsorted_transactions = deepcopy(world)
        second_transaction_id = allocate_id(
            unsorted_transactions, "transaction"
        )
        second_transaction = deepcopy(
            unsorted_transactions["world_state"]["transactions"][transaction_id]
        )
        second_transaction["transaction_id"] = second_transaction_id
        unsorted_transactions["world_state"]["transactions"][
            second_transaction_id
        ] = second_transaction
        unsorted_transactions["world_state"]["booking_state"][
            "booking_checkpoints"
        ][checkpoint_id]["financial_transaction_ids"] = [
            second_transaction_id,
            transaction_id,
        ]
        self.assertIn(
            "invalid_booking_checkpoint", issue_codes(unsorted_transactions)
        )
        future_inventory = deepcopy(world)
        future_inventory["world_state"]["bookings"][booking_id][
            "inventory_revision_at_commit"
        ] = 1
        self.assertIn("invalid_booking", issue_codes(future_inventory))
        orphan = deepcopy(world)
        orphan_itinerary_id = allocate_id(orphan, "itinerary")
        orphan_record = deepcopy(orphan["world_state"]["itineraries"][itinerary_id])
        orphan_record["itinerary_id"] = orphan_itinerary_id
        orphan["world_state"]["itineraries"][orphan_itinerary_id] = orphan_record
        self.assertIn("invalid_itinerary", issue_codes(orphan))
        malformed_values = (
            lambda value: value["world_state"]["itineraries"][itinerary_id].update(market_id=[]),
            lambda value: value["world_state"]["itineraries"][itinerary_id].update(airline_id=[]),
            lambda value: value["world_state"]["bookings"][booking_id].update(booking_checkpoint_id=[]),
            lambda value: value["world_state"]["bookings"][booking_id].update(cohort_key=[]),
            lambda value: value["world_state"]["bookings"][booking_id].update(itinerary_id=[]),
            lambda value: value["world_state"]["booking_state"]["booking_checkpoints"][checkpoint_id].update(status=[]),
            lambda value: value["world_state"].pop("directional_markets"),
            lambda value: value["world_state"].update(directional_markets=None),
            lambda value: value["world_state"]["itineraries"].update(
                {itinerary_id: []}
            ),
            lambda value: value["world_state"]["booking_state"][
                "booking_checkpoints"
            ][checkpoint_id].update(financial_transaction_ids=[[]]),
        )
        for mutate in malformed_values:
            malformed = deepcopy(world)
            mutate(malformed)
            self.assertFalse(validate_world(malformed).is_valid)


if __name__ == "__main__":
    unittest.main()
