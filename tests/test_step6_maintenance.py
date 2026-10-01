"""PH 1.0 Step 6 deterministic maintenance regressions."""
from copy import deepcopy
import json
import unittest

from game.aircraft_operations import (
    process_flight_departure, process_flight_completion, project_flight_fulfilment,
)
from game.maintenance.routine import maintenance_expense_minor
from game.simulation import process_events_through, process_next_event, advance_by_real_seconds
from game.world_state import validate_world
from game.world_state.migration import migrate_schema_6_to_7
from game.world_state.maintenance_reference import (
    FACTORS, class_for_model, class_for_wingspan, load_classification,
    new_maintenance_configuration, validate_classification,
)
from tests.test_stage1_terminal_harness import planned_world, new_world
from tests.test_stage1_flight_fulfilment import departure_witnesses, completion_witnesses


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def schema6(world):
    candidate = deepcopy(world)
    candidate["metadata"]["save_schema_version"] = 6
    del candidate["simulation"]["configuration"]["maintenance"]
    assert validate_world(candidate).is_valid, validate_world(candidate).as_dict()
    return candidate


class ClassificationTests(unittest.TestCase):
    def test_complete_catalog_and_boundaries(self):
        pack = load_classification()
        self.assertEqual(len(pack["models"]), 21)
        self.assertEqual(set(FACTORS), set("ABCDEFG"))
        self.assertEqual([(v, class_for_wingspan(v)) for v in
                          (14999, 15000, 23999, 24000, 35999, 36000,
                           51999, 52000, 64999, 65000, 79999, 80000)],
                         [(14999, "A"), (15000, "B"), (23999, "B"),
                          (24000, "C"), (35999, "C"), (36000, "D"),
                          (51999, "D"), (52000, "E"), (64999, "E"),
                          (65000, "F"), (79999, "F"), (80000, "G")])
        self.assertEqual(pack["models"]["embraer-e175"]["aerodrome_class"], "C")
        self.assertEqual(pack["models"]["A320-200"]["aerodrome_class"], "C")
        pack["models"]["A320-200"]["aerodrome_class"] = "G"
        self.assertEqual(class_for_model("A320-200"), "C")
        with self.assertRaises(TypeError):
            FACTORS["C"] = 999

    def test_reference_and_configuration_reject_mutation(self):
        pack = deepcopy(load_classification())
        pack["classification_version"] = "wrong"
        with self.assertRaises(ValueError):
            validate_classification(pack, set(pack["models"]) - {"A320-200"})
        world = new_world()
        world["simulation"]["configuration"]["maintenance"]["factor_minor_per_km_by_class"]["C"] += 1
        self.assertFalse(validate_world(world).is_valid)
        self.assertEqual(new_maintenance_configuration()["factor_minor_per_km_by_class"], FACTORS)

    def test_exact_integer_rounding(self):
        for factor in FACTORS.values():
            self.assertEqual(maintenance_expense_minor(1000, factor), factor)
            self.assertEqual(maintenance_expense_minor(1, factor), 1)
            self.assertEqual(maintenance_expense_minor(1001, factor), factor + 1)
        self.assertEqual(maintenance_expense_minor(0, 80), 0)
        with self.assertRaises(ValueError):
            maintenance_expense_minor(1.0, 80)


class SettlementTests(unittest.TestCase):
    def test_completion_components_reconcile_and_replay(self):
        world, airline_id, aircraft_id, schedule = planned_world()
        before_seconds = world["world_state"]["aircraft"][aircraft_id].get("lifecycle", {}).get("lifetime_flight_seconds", 0)
        processed = process_events_through(world, "2026-09-07T06:00:00Z")
        self.assertTrue(processed.succeeded, processed.failure)
        for flight_id in schedule.dated_flight_ids:
            result = world["world_state"]["flight_results"][flight_id]
            self.assertEqual(result["result_version"], 2)
            self.assertEqual(result["maintenance_distance_source"], "AIRPORT_COORDINATE_FALLBACK_V1")
            self.assertEqual(result["operating_cost_minor"],
                             result["base_operating_cost_minor"] + result["maintenance_expense_minor"])
            self.assertEqual(result["base_operating_cost_minor"], 669000)
            self.assertEqual(result["maintenance_expense_minor"], 45359)
            journal = world["world_state"]["transactions"][result["settlement_transaction_id"]]
            self.assertEqual(journal["entries"][-2]["amount_minor"], result["operating_cost_minor"])
            self.assertEqual(journal["entries"][-1]["amount_minor"], -result["operating_cost_minor"])
            projection = project_flight_fulfilment(world, flight_id)
            self.assertEqual(projection["maintenance_expense_minor"], result["maintenance_expense_minor"])
        self.assertNotIn("lifecycle", world["world_state"]["aircraft"][aircraft_id])  # legacy starter stays legacy
        snapshot = encoded(world)
        self.assertTrue(process_flight_completion(world, schedule.dated_flight_ids[0],
                        **completion_witnesses(world, schedule.dated_flight_ids[0])).reused)
        self.assertEqual(encoded(world), snapshot)

    def test_migration_preserves_historical_v1_and_inflight(self):
        world, airline_id, aircraft_id, schedule = planned_world()
        old = schema6(world)
        first = process_events_through(old, "2026-09-07T06:00:00Z")
        self.assertTrue(first.succeeded, first.failure)
        history = deepcopy(old["world_state"]["flight_results"])
        journals = deepcopy(old["world_state"]["transactions"])
        migrated = migrate_schema_6_to_7(old)
        self.assertTrue(migrated.succeeded, migrated.as_dict())
        self.assertEqual(migrated.world["world_state"]["flight_results"], history)
        self.assertEqual(migrated.world["world_state"]["transactions"], journals)
        self.assertTrue(all(result["result_version"] == 1 for result in history.values()))
        self.assertTrue(validate_world(migrated.world).is_valid)
        inflight = schema6(world)
        departure = process_events_through(inflight, "2026-09-07T00:00:00Z")
        self.assertTrue(departure.succeeded, departure.failure)
        locked_id = schedule.dated_flight_ids[0]
        frozen = deepcopy(inflight["world_state"]["active_aircraft_operations"][locked_id])
        migrated = migrate_schema_6_to_7(inflight)
        self.assertTrue(migrated.succeeded, migrated.as_dict())
        self.assertEqual(migrated.world["world_state"]["active_aircraft_operations"][locked_id], frozen)
        finished = process_events_through(migrated.world, "2026-09-07T06:00:00Z")
        self.assertTrue(finished.succeeded, finished.failure)
        self.assertEqual(migrated.world["world_state"]["flight_results"][locked_id]["result_version"], 1)
        self.assertEqual(migrated.world["world_state"]["flight_results"][locked_id], history[locked_id])
        self.assertEqual(migrated.world["world_state"]["flight_results"][schedule.dated_flight_ids[1]]["result_version"], 2)

    def test_no_charge_before_completion_and_event_step_equivalence(self):
        source, airline_id, aircraft_id, schedule = planned_world()
        bulk = deepcopy(source)
        step = deepcopy(source)
        arrival = "2026-09-07T06:00:00Z"
        result = process_events_through(bulk, arrival)
        self.assertTrue(result.succeeded, result.failure)
        while step["simulation"]["time_utc"] < arrival:
            result = process_next_event(step)
            self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(encoded(step["world_state"]["flight_results"]),
                         encoded(bulk["world_state"]["flight_results"]))
        self.assertEqual(encoded(step["world_state"]["transactions"]),
                         encoded(bulk["world_state"]["transactions"]))


    def test_seven_x_pacing_matches_bulk_authority(self):
        source, _, _, _ = planned_world()
        bulk = deepcopy(source)
        paced = deepcopy(source)
        bulk["simulation"]["clock_state"] = "NORMAL"
        paced["simulation"]["clock_state"] = "NORMAL"
        bulk["simulation"]["configuration"]["clock_ratios"]["NORMAL"] = 7
        paced["simulation"]["configuration"]["clock_ratios"]["NORMAL"] = 7
        target = "2026-09-07T06:00:01Z"
        self.assertTrue(process_events_through(bulk, target).succeeded)
        self.assertTrue(advance_by_real_seconds(paced, 77_143).succeeded)
        self.assertEqual(encoded(paced), encoded(bulk))

    def test_substitution_uses_actual_model_class(self):
        from game.world_state import add_aircraft
        world, airline_id, starter_id, schedule = planned_world()
        inbound_id = schedule.dated_flight_ids[1]
        inbound = world["world_state"]["dated_flights"][inbound_id]
        substitute = add_aircraft(
            world, airline_id, "TEST-SUB", "boeing-787-9",
            home_airport_id=inbound["origin_airport_id"],
            current_airport_id=inbound["origin_airport_id"],
        )
        self.assertTrue(process_events_through(world, "2026-09-07T03:59:59Z").succeeded)
        world["simulation"]["time_utc"] = inbound["scheduled_off_block_utc"]
        departed = process_flight_departure(
            world, inbound_id, actual_aircraft_id=substitute,
            **departure_witnesses(world, inbound_id),
        )
        self.assertTrue(departed.succeeded, departed.issues)
        operation = world["world_state"]["active_aircraft_operations"][inbound_id]
        self.assertEqual(operation["actual_aircraft_id"], substitute)
        self.assertEqual(operation["maintenance_class"], "E")
        self.assertTrue(process_events_through(world, "2026-09-07T06:00:00Z").succeeded)
        result = world["world_state"]["flight_results"][inbound_id]
        self.assertEqual(result["actual_aircraft_id"], substitute)
        self.assertEqual(result["maintenance_class"], "E")
        self.assertEqual(result["maintenance_factor_minor_per_km"], 200)
        self.assertEqual(result["maintenance_expense_minor"],
                         maintenance_expense_minor(result["maintenance_distance_m"], 200))
        self.assertTrue(validate_world(world).is_valid)

    def test_failed_departure_never_charges_maintenance(self):
        world, airline_id, aircraft_id, schedule = planned_world(fare=0)
        world["world_state"]["aircraft"][aircraft_id]["model_reference"] = "unknown-model"
        self.assertTrue(validate_world(world).is_valid)
        expense_before = sum(
            account["balance_minor"] for account in world["world_state"]["financial_accounts"].values()
            if account["code"] == "operating_expenses"
        )
        outcome = process_events_through(world, "2026-09-07T00:00:00Z")
        self.assertFalse(outcome.succeeded)
        self.assertNotIn(schedule.dated_flight_ids[0], world["world_state"]["flight_results"])
        self.assertEqual(expense_before, sum(
            account["balance_minor"] for account in world["world_state"]["financial_accounts"].values()
            if account["code"] == "operating_expenses"
        ))

    def test_negative_cash_allowed_with_single_direct_posting(self):
        world, airline_id, aircraft_id, schedule = planned_world(fare=0)
        airline = world["world_state"]["airlines"][airline_id]
        cash_id = next(account_id for account_id in airline["financial_account_ids"]
                       if world["world_state"]["financial_accounts"][account_id]["code"] == "cash")
        world["world_state"]["financial_accounts"][cash_id]["balance_minor"] = 0
        self.assertTrue(validate_world(world).is_valid)
        outcome = process_events_through(world, "2026-09-07T06:00:00Z")
        self.assertTrue(outcome.succeeded, outcome.failure)
        total = sum(result["operating_cost_minor"]
                    for result in world["world_state"]["flight_results"].values())
        self.assertEqual(world["world_state"]["financial_accounts"][cash_id]["balance_minor"], -total)
        self.assertTrue(validate_world(world).is_valid)

if __name__ == "__main__":
    unittest.main()
