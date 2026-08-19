"""Milestones 0-1 tests for the authoritative world-state foundation."""

from copy import deepcopy
from decimal import Decimal
import unittest
from unittest.mock import patch

from game.game_state import get_active_airline
from game.world_state import (
    add_aircraft,
    add_airline,
    add_airport_reference,
    add_connection,
    add_directional_market,
    allocate_id,
    build_legacy_read_projection,
    create_new_world,
    major_to_minor,
    validate_world,
)


def make_world():
    return create_new_world(
        ceo_display_name="Avery Chen",
        airline_display_name="Meridian Air",
        starting_airport={
            "reference_code": "RPLL",
            "iata": "MNL",
            "icao": "RPLL",
            "name": "Ninoy Aquino International Airport",
            "timezone": "Asia/Manila",
        },
        difficulty="Normal",
        simulation_time_utc="2026-08-20T04:30:00Z",
        simulation_seed=8675309,
        starting_money="300000000.00",
        starting_debt=0,
    )


def issue_codes(world):
    return {issue.code for issue in validate_world(world).errors}


class Stage1WorldConstructionTests(unittest.TestCase):
    def test_valid_stage_1_world_can_be_constructed_and_validated(self):
        world = make_world()

        result = validate_world(world)

        self.assertTrue(result.is_valid, result.as_dict())

        self.assertEqual(world["metadata"]["save_schema_version"], 1)
        self.assertEqual(world["simulation"]["clock_state"], "PAUSED")

    def test_initialization_is_deterministic_for_same_supplied_inputs(self):
        self.assertEqual(make_world(), make_world())

    def test_airline_id_is_not_name_and_rename_preserves_references(self):
        world = make_world()
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        account_owners = {
            account["airline_id"] for account in world["world_state"]["financial_accounts"].values()
        }

        world["world_state"]["airlines"][airline_id]["display_name"] = "Renamed Meridian"

        self.assertNotEqual(airline_id, "Meridian Air")
        self.assertEqual(account_owners, {airline_id})
        self.assertTrue(validate_world(world).is_valid)

    def test_aircraft_id_is_not_registration_and_registration_is_mutable_display(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        airport_id = next(iter(state["airports"]))
        aircraft_id = add_aircraft(
            world,
            airline_id,
            "RP-C1001",
            "A320-200",
            home_airport_id=airport_id,
        )

        state["aircraft"][aircraft_id]["display_registration"] = "RP-C2002"

        self.assertNotEqual(aircraft_id, "RP-C1001")
        self.assertEqual(state["aircraft"][aircraft_id]["airline_id"], airline_id)
        self.assertTrue(validate_world(world).is_valid)

    def test_multiple_airlines_coexist_with_explicit_control(self):
        world = make_world()
        state = world["world_state"]
        airport_id = next(iter(state["airports"]))

        ai_id = add_airline(
            world,
            "Archipelago Connect",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
            starting_money="50000000.00",
        )

        self.assertEqual(len(state["airlines"]), 2)
        self.assertEqual(state["airlines"][ai_id]["control_type"], "AI")
        self.assertTrue(validate_world(world).is_valid)

    def test_ui_focus_does_not_change_world_ownership_or_scope(self):
        world = make_world()
        state = world["world_state"]
        player_airline_id = state["player"]["primary_airline_id"]
        airport_id = next(iter(state["airports"]))
        ai_id = add_airline(
            world,
            "Archipelago Connect",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
        )
        ownership_before = deepcopy(state["airlines"])

        world["ui_state"]["current_focus_airline_id"] = ai_id

        self.assertEqual(state["player"]["primary_airline_id"], player_airline_id)
        self.assertEqual(state["airlines"], ownership_before)
        self.assertEqual(set(state["airlines"]), {player_airline_id, ai_id})
        self.assertTrue(validate_world(world).is_valid)

    def test_later_milestone_collections_are_empty_but_structurally_valid(self):
        world = make_world()
        state = world["world_state"]

        for collection in (
            "aircraft",
            "directional_markets",
            "connections",
            "schedule_definitions",
            "dated_flights",
            "bookings",
            "itineraries",
            "active_aircraft_operations",
            "pending_events",
            "transactions",
        ):
            self.assertEqual(state[collection], {})
        self.assertTrue(validate_world(world).is_valid)

    def test_new_world_construction_does_not_call_legacy_daily_tick(self):
        with patch(
            "game.simulation.daily_tick.simulate_airline_day",
            side_effect=AssertionError("legacy tick was called"),
        ):
            world = make_world()

        self.assertTrue(validate_world(world).is_valid)

    def test_legacy_focus_lookup_remains_characterized_and_separate(self):
        legacy = {
            "player_info": {"current_focus": "Legacy Air"},
            "airline_list": {"Legacy Air": {"finances": {"cash_on_hand": 10}}},
        }

        self.assertEqual(get_active_airline(legacy)["finances"]["cash_on_hand"], 10)


class Stage1IdentityAndMoneyTests(unittest.TestCase):
    def test_allocator_state_survives_restore_without_collision(self):
        world = make_world()
        first = allocate_id(world, "booking")
        restored = deepcopy(world)

        next_original = allocate_id(world, "booking")
        next_restored = allocate_id(restored, "booking")

        self.assertNotEqual(first, next_original)
        self.assertEqual(next_original, next_restored)

    def test_allocator_collision_state_is_rejected(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        state["airlines"][airline_id]["airline_id"] = airline_id
        world["deterministic_state"]["id_allocator"]["next_by_type"]["airline"] = 1

        self.assertIn("id_allocator_collision", issue_codes(world))

    def test_allocator_refuses_collision_and_exhaustion(self):
        world = make_world()
        world["deterministic_state"]["id_allocator"]["next_by_type"]["airline"] = 1
        with self.assertRaises(ValueError):
            allocate_id(world, "airline")

        world = make_world()
        world["deterministic_state"]["id_allocator"]["next_by_type"]["booking"] = 1_000_000_000_000
        self.assertTrue(validate_world(world).is_valid)
        with self.assertRaises(ValueError):
            allocate_id(world, "booking")

    def test_duplicate_primary_ids_are_rejected(self):
        world = make_world()
        airlines = world["world_state"]["airlines"]
        airline_id = next(iter(airlines))
        duplicate = deepcopy(airlines[airline_id])
        airlines["airline-000000000999"] = duplicate

        self.assertIn("duplicate_id", issue_codes(world))

    def test_mutating_an_immutable_id_is_detected(self):
        world = make_world()
        airlines = world["world_state"]["airlines"]
        airline_id = next(iter(airlines))
        airlines[airline_id]["airline_id"] = "airline-000000000777"

        self.assertIn("id_key_mismatch", issue_codes(world))

    def test_money_uses_integer_minor_units_and_explicit_categories(self):
        world = make_world()
        accounts = world["world_state"]["financial_accounts"].values()
        by_code = {account["code"]: account for account in accounts}

        self.assertEqual(by_code["cash"]["balance_minor"], 30_000_000_000)
        self.assertEqual(
            {account["category"] for account in accounts},
            {"CASH", "ASSET", "LIABILITY", "REVENUE", "EXPENSE"},
        )
        self.assertTrue(all(type(account["balance_minor"]) is int for account in accounts))

    def test_exact_decimal_money_conversion(self):
        self.assertEqual(major_to_minor(Decimal("12.34")), 1234)
        self.assertEqual(major_to_minor("0.01"), 1)
        with self.assertRaises(ValueError):
            major_to_minor("0.001")
        with self.assertRaises(ValueError):
            major_to_minor(0.1)
        with self.assertRaises(ValueError):
            major_to_minor(True)
        with self.assertRaises(ValueError):
            major_to_minor("NaN")

    def test_invalid_starting_money_and_debt_are_rejected(self):
        kwargs = dict(
            ceo_display_name="A",
            airline_display_name="B",
            starting_airport="MNL",
            difficulty="Normal",
            simulation_time_utc="2026-01-01T00:00:00Z",
            simulation_seed=1,
            starting_money=1,
        )
        with self.assertRaises(ValueError):
            create_new_world(**{**kwargs, "starting_money": 1.5})
        with self.assertRaises(ValueError):
            create_new_world(**{**kwargs, "starting_debt": "-1.00"})


class Stage1ValidationTests(unittest.TestCase):
    def test_boolean_schema_version_and_unknown_roots_are_rejected(self):
        world = make_world()
        world["metadata"]["save_schema_version"] = True
        world["legacy_state"] = {}
        world["world_state"]["routes"] = {}

        codes = issue_codes(world)

        self.assertIn("unsupported_schema_version", codes)
        self.assertIn("unknown_root", codes)
        self.assertIn("unknown_world_root", codes)

    def test_missing_root_collection_is_rejected_without_repair(self):
        world = make_world()
        del world["world_state"]["bookings"]

        result = validate_world(world)

        self.assertIn("missing_collection", {error.code for error in result.errors})
        self.assertNotIn("bookings", world["world_state"])

    def test_dangling_aircraft_owner_reference_is_rejected(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        airport_id = next(iter(state["airports"]))
        aircraft_id = add_aircraft(world, airline_id, "RP-C1", "A320", home_airport_id=airport_id)
        state["aircraft"][aircraft_id]["airline_id"] = "airline-000000000999"

        self.assertIn("dangling_reference", issue_codes(world))

    def test_invalid_account_ownership_is_rejected(self):
        world = make_world()
        state = world["world_state"]
        airport_id = next(iter(state["airports"]))
        ai_id = add_airline(
            world,
            "AI Air",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
        )
        player_id = state["player"]["primary_airline_id"]
        foreign_account = state["airlines"][ai_id]["financial_account_ids"][0]
        state["airlines"][player_id]["financial_account_ids"].append(foreign_account)

        self.assertIn("invalid_ownership", issue_codes(world))

    def test_invalid_timestamp_is_rejected(self):
        world = make_world()
        world["simulation"]["time_utc"] = "08/20/2026 12:30"

        self.assertIn("invalid_timestamp", issue_codes(world))

    def test_non_integer_authoritative_money_is_rejected(self):
        world = make_world()
        account = next(iter(world["world_state"]["financial_accounts"].values()))
        account["balance_minor"] = 10.5

        self.assertIn("invalid_money", issue_codes(world))

        account["balance_minor"] = True
        self.assertIn("invalid_money", issue_codes(world))

    def test_base_currency_and_minimal_account_invariants_are_validated(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        airline = state["airlines"][airline_id]
        cash_id, asset_id = airline["financial_account_ids"][:2]
        airline["base_currency"] = "usd"
        state["financial_accounts"][asset_id]["code"] = "cash"
        state["financial_accounts"][cash_id]["currency"] = "EUR"

        codes = issue_codes(world)

        self.assertIn("invalid_currency", codes)
        self.assertIn("duplicate_account_code", codes)
        self.assertIn("missing_financial_account", codes)

    def test_currency_codes_must_be_ascii(self):
        world = make_world()
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        world["world_state"]["airlines"][airline_id]["base_currency"] = "ÜSD"

        self.assertIn("invalid_currency", issue_codes(world))
        with self.assertRaises(ValueError):
            create_new_world(
                ceo_display_name="Ari Santos",
                airline_display_name="Pacific Meridian",
                starting_airport="MNL",
                difficulty="normal",
                simulation_time_utc="2026-08-20T00:00:00Z",
                simulation_seed=7,
                starting_money="300000000.00",
                currency="ÜSD",
            )

    def test_airline_ownership_cycles_are_rejected(self):
        world = make_world()
        state = world["world_state"]
        airport_id = next(iter(state["airports"]))
        first = add_airline(
            world,
            "First AI",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
        )
        second = add_airline(
            world,
            "Second AI",
            control_type="AI",
            owner_type="AIRLINE",
            owner_id=first,
            base_airport_id=airport_id,
        )
        state["airlines"][first]["owner_type"] = "AIRLINE"
        state["airlines"][first]["owner_id"] = second

        self.assertIn("ownership_cycle", issue_codes(world))

    def test_primary_airline_must_be_directly_player_owned(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        state["airlines"][airline_id]["owner_type"] = "INDEPENDENT"
        state["airlines"][airline_id]["owner_id"] = None

        self.assertIn("invalid_ownership", issue_codes(world))

    def test_duplicate_airport_market_and_connection_semantics_are_rejected(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        origin_id = next(iter(state["airports"]))
        destination_id = add_airport_reference(world, "CEB")
        with self.assertRaises(ValueError):
            add_airport_reference(world, "CEB")
        duplicate_airport_id = allocate_id(world, "airport")
        state["airports"][duplicate_airport_id] = {
            **deepcopy(state["airports"][destination_id]),
            "airport_id": duplicate_airport_id,
        }
        market_id = add_directional_market(world, origin_id, destination_id)
        with self.assertRaises(ValueError):
            add_directional_market(world, origin_id, destination_id)
        duplicate_market_id = allocate_id(world, "market")
        state["directional_markets"][duplicate_market_id] = {
            **deepcopy(state["directional_markets"][market_id]),
            "market_id": duplicate_market_id,
        }
        connection_id = add_connection(world, airline_id, market_id)
        with self.assertRaises(ValueError):
            add_connection(world, airline_id, market_id)
        duplicate_connection_id = allocate_id(world, "connection")
        state["connections"][duplicate_connection_id] = {
            **deepcopy(state["connections"][connection_id]),
            "connection_id": duplicate_connection_id,
        }

        codes = issue_codes(world)

        self.assertIn("duplicate_airport_reference", codes)
        self.assertIn("duplicate_market", codes)
        self.assertIn("duplicate_connection", codes)

    def test_constructor_normalizes_offset_but_validator_requires_canonical_utc(self):
        world = create_new_world(
            ceo_display_name="A",
            airline_display_name="B",
            starting_airport="MNL",
            difficulty="Normal",
            simulation_time_utc="2026-08-20T12:30:00+08:00",
            simulation_seed=1,
            starting_money=1,
        )
        self.assertEqual(world["simulation"]["time_utc"], "2026-08-20T04:30:00Z")
        world["simulation"]["time_utc"] = "2026-08-20T04:30:00+00:00"
        self.assertIn("invalid_timestamp", issue_codes(world))

        with self.assertRaises(ValueError):
            create_new_world(
                ceo_display_name="A",
                airline_display_name="B",
                starting_airport="MNL",
                difficulty="Normal",
                simulation_time_utc="2026-08-20T04:30:00",
                simulation_seed=1,
                starting_money=1,
            )

    def test_name_based_authoritative_reference_is_rejected(self):
        world = make_world()
        airline = next(iter(world["world_state"]["airlines"].values()))
        airline["airline_name"] = "Mutable foreign key"

        self.assertIn("name_based_authoritative_reference", issue_codes(world))

    def test_invalid_ui_focus_is_rejected_but_not_used_as_world_scope(self):
        world = make_world()
        original_airlines = deepcopy(world["world_state"]["airlines"])
        world["ui_state"]["current_focus_airline_id"] = "airline-000000000999"

        self.assertIn("dangling_reference", issue_codes(world))
        self.assertEqual(world["world_state"]["airlines"], original_airlines)

    def test_populated_cross_domain_references_validate(self):
        world = make_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        origin_id = next(iter(state["airports"]))
        destination_id = add_airport_reference(
            world,
            {"reference_code": "RPVM", "iata": "CEB", "name": "Mactan-Cebu", "timezone": "Asia/Manila"},
        )
        aircraft_id = add_aircraft(world, airline_id, "RP-C1001", "A320", home_airport_id=origin_id)
        market_id = add_directional_market(world, origin_id, destination_id)
        connection_id = add_connection(world, airline_id, market_id)

        schedule_id = allocate_id(world, "schedule")
        state["schedule_definitions"][schedule_id] = {
            "schedule_id": schedule_id,
            "airline_id": airline_id,
            "connection_id": connection_id,
            "planned_aircraft_id": aircraft_id,
            "status": "ACTIVE",
            "recurrence": {"kind": "ONCE"},
            "effective_from_utc": "2026-08-21T00:00:00Z",
            "effective_until_utc": None,
        }
        flight_id = allocate_id(world, "dated_flight")
        state["dated_flights"][flight_id] = {
            "dated_flight_id": flight_id,
            "schedule_id": schedule_id,
            "airline_id": airline_id,
            "connection_id": connection_id,
            "planned_aircraft_id": aircraft_id,
            "scheduled_off_block_utc": "2026-08-21T01:00:00Z",
            "scheduled_in_block_utc": "2026-08-21T02:30:00Z",
            "status": "PLANNED",
        }
        itinerary_id = allocate_id(world, "itinerary")
        state["itineraries"][itinerary_id] = {
            "itinerary_id": itinerary_id,
            "airline_id": airline_id,
            "dated_flight_ids": [flight_id],
        }
        booking_id = allocate_id(world, "booking")
        state["bookings"][booking_id] = {
            "booking_id": booking_id,
            "airline_id": airline_id,
            "itinerary_id": itinerary_id,
            "passenger_count": 2,
            "booked_at_utc": "2026-08-20T05:00:00Z",
            "total_fare_minor": 25_000,
            "currency": "USD",
            "status": "CONFIRMED",
        }
        cash_id, asset_id = state["airlines"][airline_id]["financial_account_ids"][:2]
        transaction_id = allocate_id(world, "transaction")
        state["transactions"][transaction_id] = {
            "transaction_id": transaction_id,
            "airline_id": airline_id,
            "occurred_at_utc": "2026-08-20T05:00:00Z",
            "description": "Schema validation fixture",
            "entries": [
                {"account_id": cash_id, "amount_minor": -100},
                {"account_id": asset_id, "amount_minor": 100},
            ],
        }
        event_id = allocate_id(world, "event")
        state["pending_events"][event_id] = {
            "event_id": event_id,
            "event_type": "TEST_ONLY",
            "due_at_utc": "2026-08-21T00:30:00Z",
            "owner_type": "dated_flight",
            "owner_id": flight_id,
            "operation_revision": 0,
            "order_key": [0, event_id],
            "payload": {},
        }
        state["active_aircraft_operations"][flight_id] = {
            "dated_flight_id": flight_id,
            "aircraft_id": aircraft_id,
            "state": "PLANNED",
            "revision": 0,
        }

        result = validate_world(world)

        self.assertTrue(result.is_valid, result.as_dict())

        invalid_window = deepcopy(world)
        invalid_window["world_state"]["schedule_definitions"][schedule_id][
            "effective_until_utc"
        ] = "2026-08-20T23:59:59Z"
        self.assertIn("invalid_timestamp_order", issue_codes(invalid_window))

        inconsistent = deepcopy(world)
        other_airport_id = add_airport_reference(inconsistent, "DVO")
        other_market_id = add_directional_market(inconsistent, origin_id, other_airport_id)
        other_connection_id = add_connection(inconsistent, airline_id, other_market_id)
        inconsistent["world_state"]["dated_flights"][flight_id][
            "connection_id"
        ] = other_connection_id
        self.assertIn("inconsistent_reference", issue_codes(inconsistent))

    def test_dangling_schedule_and_event_references_are_rejected(self):
        world = make_world()
        schedule_id = allocate_id(world, "schedule")
        world["world_state"]["schedule_definitions"][schedule_id] = {
            "schedule_id": schedule_id,
            "airline_id": "airline-000000000999",
            "connection_id": "connection-000000000999",
            "planned_aircraft_id": None,
            "status": "ACTIVE",
            "recurrence": {},
            "effective_from_utc": "2026-08-21T00:00:00Z",
            "effective_until_utc": None,
        }
        event_id = allocate_id(world, "event")
        world["world_state"]["pending_events"][event_id] = {
            "event_id": event_id,
            "event_type": "TEST_ONLY",
            "due_at_utc": "2026-08-21T00:00:00Z",
            "owner_type": "aircraft",
            "owner_id": "aircraft-000000000999",
            "operation_revision": 0,
            "order_key": [0],
            "payload": {},
        }

        self.assertIn("dangling_reference", issue_codes(world))

    def test_malformed_unhashable_references_report_errors_without_crashing(self):
        mutations = (
            lambda world: world["world_state"]["airlines"][
                world["world_state"]["player"]["primary_airline_id"]
            ].update(owner_type="AIRLINE", owner_id=[]),
            lambda world: world["world_state"]["airlines"][
                world["world_state"]["player"]["primary_airline_id"]
            ].update(financial_account_ids=[{}]),
            lambda world: world["ui_state"].update(current_focus_airline_id=[]),
        )

        for mutate in mutations:
            with self.subTest(mutation=mutate):
                world = make_world()
                mutate(world)
                self.assertFalse(validate_world(world).is_valid)


class Stage1CompatibilityProjectionTests(unittest.TestCase):
    def test_projection_is_detached_and_cannot_mutate_authoritative_world(self):
        world = make_world()
        airline_id = world["world_state"]["player"]["primary_airline_id"]
        authoritative_name = world["world_state"]["airlines"][airline_id]["display_name"]
        projection = build_legacy_read_projection(world)

        projection["airline_list"][authoritative_name]["finances"]["cash_on_hand"] = -999
        projection["player_info"]["airline_name"] = "Projection Rename"

        self.assertEqual(world["world_state"]["airlines"][airline_id]["display_name"], authoritative_name)
        cash_account_id = world["world_state"]["airlines"][airline_id]["financial_account_ids"][0]
        self.assertEqual(world["world_state"]["financial_accounts"][cash_account_id]["balance_minor"], 30_000_000_000)
        self.assertTrue(validate_world(world).is_valid)

    def test_projection_focus_changes_only_derived_current_focus(self):
        world = make_world()
        state = world["world_state"]
        airport_id = next(iter(state["airports"]))
        ai_id = add_airline(
            world,
            "AI Air",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
            currency="EUR",
        )
        before = build_legacy_read_projection(world)
        world["ui_state"]["current_focus_airline_id"] = ai_id

        after = build_legacy_read_projection(world)

        self.assertEqual(after["player_info"]["current_focus"], "AI Air")
        before["player_info"].pop("current_focus")
        after["player_info"].pop("current_focus")
        self.assertEqual(after, before)
        self.assertEqual(state["player"]["primary_airline_id"], next(iter(state["airlines"])))

    def test_projection_is_independent_of_authoritative_dictionary_order(self):
        world = make_world()
        state = world["world_state"]
        airport_id = next(iter(state["airports"]))
        ai_id = add_airline(
            world,
            "Meridian Air",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
            currency="EUR",
        )
        world["ui_state"]["current_focus_airline_id"] = ai_id
        expected = build_legacy_read_projection(world)
        reordered = deepcopy(world)
        for collection in ("airlines", "financial_accounts"):
            reordered["world_state"][collection] = dict(
                reversed(list(reordered["world_state"][collection].items()))
            )

        actual = build_legacy_read_projection(reordered)

        self.assertEqual(actual, expected)
        self.assertEqual(actual["settings"]["base_currency"], "USD")

    def test_projection_keys_remain_unique_when_names_mimic_fallbacks(self):
        world = make_world()
        state = world["world_state"]
        airport_id = next(iter(state["airports"]))
        second_id = add_airline(
            world,
            "Duplicate Air [airline-000000000003]",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
        )
        third_id = add_airline(
            world,
            "Duplicate Air",
            control_type="AI",
            owner_type="INDEPENDENT",
            base_airport_id=airport_id,
        )
        first_id = state["player"]["primary_airline_id"]
        state["airlines"][first_id]["display_name"] = "Duplicate Air"
        self.assertEqual(third_id, "airline-000000000003")

        projection = build_legacy_read_projection(world)

        self.assertEqual(len(projection["airline_list"]), 3)
        self.assertEqual(
            {item["airline_id"] for item in projection["airline_list"].values()},
            {first_id, second_id, third_id},
        )


if __name__ == "__main__":
    unittest.main()
