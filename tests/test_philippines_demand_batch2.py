"""Tagged suitability, calibration, compatibility and preservation proofs."""

import ast
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN, localcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from game.demand import (
    project_model4_origin, project_model4_pair, rebuild_model4_indexes,
    resolve_daily_cohort, revise_demand_model,
)
from game.demand.air_suitability import interpolate_air_suitability
from game.demand.model import _distance_km
from game.demand.model4 import _airport_raw_score, _conserved_allocations
from game.simulation import process_events_through
from game.world_state import load_stage1_scenario, validate_world, Stage1BootstrapError
from game.world_state.air_suitability_validation import (
    validate_air_suitability_configuration,
)
from game.world_state.demand_fingerprint import calculate_model4_input_fingerprint
from tests.test_philippines_v1_recovery import (
    EXPECTED_ACTIVE_CODES, encoded, new_world, publish_mnl_mbt,
)


def configuration(world):
    return world["simulation"]["configuration"]["demand"]


def ids(world):
    return {a["reference_code"]: key for key, a in world["world_state"]["airports"].items()}


def revise_policy(world, policy, *, airport_updates=None):
    return revise_demand_model(
        world,
        configuration_updates={
            "configuration_version": "ph-demand-batch2-test-revision",
            "air_suitability_configuration": policy,
        },
        airport_updates=airport_updates,
        expected_revision=world["world_state"]["demand_state"]["demand_model_revision"],
    )


class PhilippinesSuitabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = new_world()
        cls.airport_ids = ids(cls.world)
        cls.indexes = rebuild_model4_indexes(cls.world)
        cls.policy = configuration(cls.world)["air_suitability_configuration"]

    def pair(self, origin, destination):
        return project_model4_pair(
            self.world, self.airport_ids[origin], self.airport_ids[destination],
            indexes=self.indexes,
        )["base_daily_bookers"]

    def test_membership_and_calibration(self):
        self.assertEqual(tuple(sorted(self.airport_ids)), EXPECTED_ACTIVE_CODES)
        self.assertEqual(len(self.airport_ids), 43)
        self.assertEqual(len(self.world["world_state"]["directional_markets"]), 1806)
        self.assertNotIn("LGP", self.airport_ids)
        self.assertIn("DRP", self.airport_ids)
        expected = dict(MNL=13500000, CRK=1500000, CEB=3000000, DVO=2500000,
                        ILO=1500000, TAG=1100000, WNP=800000, MPH=100000, KLO=400000)
        for code, population in expected.items():
            self.assertEqual(self.world["world_state"]["airports"][self.airport_ids[code]]["population"], population)

    def test_mnl_crk_both_directions_are_exact_zero(self):
        self.assertEqual(self.pair("MNL", "CRK"), 0)
        self.assertEqual(self.pair("CRK", "MNL"), 0)

    def test_same_network_threshold_fractional_interpolation_and_hold_last(self):
        endpoint = {"ground_network_id": "SAME"}
        evaluate = lambda d: interpolate_air_suitability(self.policy, endpoint, endpoint, d)
        self.assertEqual(evaluate(250000), 0)
        self.assertEqual(evaluate(250001), Decimal("0.24"))
        self.assertGreater(evaluate(Decimal("250000.001")), 0)
        self.assertEqual(evaluate(275000), 6000)
        self.assertEqual(evaluate(350000), 9000)
        self.assertEqual(evaluate(3000000), 10000)
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.rounding = ROUND_DOWN
            self.assertEqual(evaluate(250001), Decimal("0.24"))

    def test_short_geography_and_wnp_remain_positive(self):
        airports = self.world["world_state"]["airports"]
        for origin, destination, same in (("MNL", "WNP", True), ("CEB", "BCD", False), ("MNL", "SJI", False)):
            a, b = airports[self.airport_ids[origin]], airports[self.airport_ids[destination]]
            self.assertEqual(a["ground_network_id"] == b["ground_network_id"], same)
            self.assertGreater(self.pair(origin, destination), 0)
            self.assertGreater(self.pair(destination, origin), 0)
            if not same:
                self.assertLess(_distance_km(a, b), 250)

    def test_cebu_ranks_above_davao(self):
        self.assertGreater(self.pair("MNL", "CEB"), self.pair("MNL", "DVO"))

    def test_tourism_attraction_and_unchanged_origin_pool(self):
        world = deepcopy(self.world)
        mph = self.airport_ids["MPH"]
        before = project_model4_origin(world, mph)
        result = revise_demand_model(world, airport_updates={mph: {"tourism_pull_ppm": 0}})
        self.assertTrue(result.succeeded, result.issues)
        off = project_model4_pair(world, self.airport_ids["MNL"], mph)["base_daily_bookers"]
        self.assertGreater(self.pair("MNL", "MPH"), off)
        after = project_model4_origin(world, mph)
        self.assertEqual(before, after)
        self.assertEqual(after["origin_daily_booking_pool"], 400)

    def test_scoring_order_and_no_second_suitability_factor(self):
        origin = {"ground_network_id": "a", "latitude_microdegrees": 0, "longitude_microdegrees": 0}
        destination = dict(origin, population=4000000, tourism_pull_ppm=1000000,
                           demand_destination_type="MAJOR_CITY", ground_network_id="b")
        policy = deepcopy(self.policy)
        policy["separated_ground_network_points"] = [
            {"distance_m": 0, "suitability_bps": 2500},
            {"distance_m": 1, "suitability_bps": 2500},
        ]
        config = {"air_suitability_configuration": policy,
                  "destination_type_weight_bps": {"MAJOR_CITY": 20000}}
        self.assertEqual(_airport_raw_score(config, origin, destination), Decimal("1.25"))
        projection = project_model4_origin(self.world, self.airport_ids["MNL"], indexes=self.indexes)
        self.assertEqual(projection["conservation_total"], 54000)
        self.assertEqual(projection["scope_amounts"]["DOMESTIC"], 35100)
        self.assertEqual(projection["materialized_leaf_total"], 35100)

    def test_adding_zero_leaf_preserves_positive_allocations(self):
        before, _ = _conserved_allocations(Decimal(17), ("a", "b"),
                                          (Decimal(2), Decimal(3)), residual_key=str)
        after, normalization = _conserved_allocations(
            Decimal(17), ("a", "b", "z"), (Decimal(2), Decimal(3), Decimal(0)), residual_key=str,
        )
        self.assertEqual({k: after[k] for k in before}, before)
        self.assertEqual(after["z"], 0)
        self.assertEqual(normalization.normalization_denominator, 5)

    def test_all_zero_revision_is_precise_and_atomic(self):
        world = deepcopy(self.world)
        policy = deepcopy(self.policy)
        for field in ("same_ground_network_points", "separated_ground_network_points"):
            for point in policy[field]:
                point["suitability_bps"] = 0
        before = encoded(world)
        result = revise_policy(world, policy)
        self.assertFalse(result.succeeded)
        self.assertIn("AIR_SUITABILITY_ZERO_ALLOCATION", result.issues[0].message)
        self.assertIn("destination country", result.issues[0].message)
        self.assertEqual(encoded(world), before)

    def test_curve_and_airport_revision_preserves_real_processed_history(self):
        world = deepcopy(self.world)
        publish_mnl_mbt(world)
        run = process_events_through(world, "2026-09-02T00:00:00Z")
        self.assertTrue(run.succeeded, run.failure)
        state = world["world_state"]
        self.assertTrue(state["bookings"])
        protected = ("bookings", "itineraries", "dated_flights", "financial_accounts",
                     "transactions", "booking_state", "pending_events", "event_history")
        frozen = {key: encoded(state[key]) for key in protected}
        cohorts = deepcopy(state["demand_state"]["processed_cohorts"])
        contexts = deepcopy(state["demand_state"]["model4_revision_contexts"])
        before_pair = project_model4_pair(world, self.airport_ids["MNL"], self.airport_ids["MPH"])
        policy = deepcopy(self.policy)
        policy["configuration_version"] = "ph-air-suitability-test-v2"
        policy["separated_ground_network_points"][3]["suitability_bps"] += 100
        result = revise_policy(world, policy, airport_updates={self.airport_ids["MPH"]: {"tourism_pull_ppm": 0}})
        self.assertTrue(result.succeeded, result.issues)
        state = world["world_state"]
        self.assertEqual(encoded(state["demand_state"]["processed_cohorts"]), encoded(cohorts))
        for key in protected:
            self.assertEqual(encoded(state[key]), frozen[key], key)
        for key, context in contexts.items():
            self.assertEqual(encoded(state["demand_state"]["model4_revision_contexts"][key]), encoded(context))
        for wrapper in cohorts.values():
            payload = wrapper["payload"]
            reused = resolve_daily_cohort(world, payload["market_id"], payload["cohort_date"])
            self.assertTrue(reused.reused)
        pair = project_model4_pair(world, self.airport_ids["MNL"], self.airport_ids["MPH"])
        self.assertNotEqual(pair["base_daily_bookers"], before_pair["base_daily_bookers"])
        advanced = process_events_through(world, "2026-09-03T00:00:00Z")
        self.assertTrue(advanced.succeeded, advanced.failure)
        state = world["world_state"]
        future = [wrapper["payload"] for wrapper in state["demand_state"]["processed_cohorts"].values()
                  if wrapper["payload"]["cohort_date"] == "2026-09-03"]
        self.assertTrue(future)
        self.assertTrue(all(p["demand_model_revision"] == state["demand_state"]["demand_model_revision"] for p in future))
        self.assertTrue(validate_world(world).is_valid)

    def test_v2_fingerprint_covers_every_new_input_and_existing_allocation_inputs(self):
        before = calculate_model4_input_fingerprint(self.world)
        for field in ("contract", "configuration_version", "interpolation_policy", "right_boundary_policy"):
            world = deepcopy(self.world)
            configuration(world)["air_suitability_configuration"][field] += "-changed"
            self.assertNotEqual(calculate_model4_input_fingerprint(world), before, field)
        for curve in ("same_ground_network_points", "separated_ground_network_points"):
            for index in range(len(self.policy[curve])):
                for field in ("distance_m", "suitability_bps"):
                    world = deepcopy(self.world)
                    configuration(world)["air_suitability_configuration"][curve][index][field] += 1
                    self.assertNotEqual(calculate_model4_input_fingerprint(world), before)
        for field, value in (("ground_network_id", "OTHER"), ("tourism_pull_ppm", 1),
                             ("population", 999), ("demand_input_revision", 999)):
            world = deepcopy(self.world)
            world["world_state"]["airports"][self.airport_ids["MNL"]][field] = value
            self.assertNotEqual(calculate_model4_input_fingerprint(world), before, field)
        world = deepcopy(self.world)
        next(iter(world["world_state"]["countries"].values()))["population"] += 1
        self.assertNotEqual(calculate_model4_input_fingerprint(world), before)
        world = deepcopy(self.world)
        configuration(world)["travel_scope_configuration"]["revision"] += 1
        self.assertNotEqual(calculate_model4_input_fingerprint(world), before)
        world = deepcopy(self.world)
        next(iter(world["world_state"]["directional_markets"].values()))["destination_airport_id"] = self.airport_ids["MNL"]
        self.assertNotEqual(calculate_model4_input_fingerprint(world), before)

    def test_service_fares_availability_and_ui_are_excluded_from_v2_fingerprint(self):
        world = deepcopy(self.world)
        before = calculate_model4_input_fingerprint(world)
        publish_mnl_mbt(world)
        self.assertEqual(calculate_model4_input_fingerprint(world), before)
        next(iter(world["world_state"]["dated_flights"].values()))["fare_offer"]["amount_minor"] += 1
        self.assertEqual(calculate_model4_input_fingerprint(world), before)
        airport = world["world_state"]["airports"][self.airport_ids["CEB"]]
        airport.update(passenger_demand_eligible=False, active_until_date="2026-09-02")
        world["ui_state"].update(selected_screen="market-browser", filters={"display_currency": "PHP"})
        self.assertEqual(calculate_model4_input_fingerprint(world), before)
        from app.terminal.session import Stage1Session
        session = Stage1Session()
        session.world = deepcopy(self.world)
        authority = session.authoritative_bytes()
        for currency in ("PHP", "EUR", "USD"):
            session.set_display_currency(currency)
            self.assertEqual(session.authoritative_bytes(), authority)
            self.assertEqual(calculate_model4_input_fingerprint(session.world), before)
        self.assertTrue(all(a["currency"] == "USD" for a in session.world["world_state"]["financial_accounts"].values()))

    def test_no_airport_code_literals_in_production_demand_logic(self):
        root = Path(__file__).resolve().parents[1] / "game" / "demand"
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            codes = [node.value for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str)
                     and node.value in EXPECTED_ACTIVE_CODES]
            self.assertEqual(codes, [], path.name)

    def test_reordered_dictionaries_and_hash_seeds(self):
        def reorder(value):
            if type(value) is dict:
                return {key: reorder(value[key]) for key in reversed(tuple(value))}
            if type(value) is list:
                return [reorder(item) for item in value]
            return value
        world = reorder(self.world)
        self.assertEqual(calculate_model4_input_fingerprint(world), calculate_model4_input_fingerprint(self.world))
        self.assertEqual(project_model4_origin(world, self.airport_ids["MNL"]),
                         project_model4_origin(self.world, self.airport_ids["MNL"], indexes=self.indexes))
        code = (
            "from tests.test_philippines_v1_recovery import new_world; "
            "from game.demand import project_model4_origin; "
            "w=new_world(); a=next(k for k,v in w['world_state']['airports'].items() if v['reference_code']=='MNL'); "
            "print(w['world_state']['demand_state']['input_fingerprint']); "
            "print(project_model4_origin(w,a))"
        )
        outputs = [subprocess.check_output([sys.executable, "-c", code], env=dict(os.environ, PYTHONHASHSEED=seed))
                   for seed in ("0", "1", "42")]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])


class SuitabilityValidationAndLegacyTests(unittest.TestCase):
    def test_legacy_pack_fingerprint_branch_and_numeric_witness_remain_exact(self):
        from tests.test_stage1_demand_model4 import model4_world
        from tests.test_stage1_market_packs import as_committed_legacy_pack_world
        world, airport_ids, _ = model4_world()
        world = as_committed_legacy_pack_world(world)
        self.assertEqual(calculate_model4_input_fingerprint(world),
                         "34ba771d2fa81ed98e874a57021e5236c31c3f3eda30a2ea804e30e6ec57122c")
        self.assertEqual(project_model4_pair(world, airport_ids["MNL"], airport_ids["SIN"])["base_daily_bookers"],
                         Decimal("1645.5363742061811891787116049065433669655018456752"))

    def test_bootstrap_rejects_all_zero_allocation(self):
        from game.world_state import create_stage1_new_game, STAGE1_SCENARIO_ID
        pack = load_stage1_scenario()
        for curve in ("same_ground_network_points", "separated_ground_network_points"):
            for point in pack["air_suitability_configuration"][curve]:
                point["suitability_bps"] = 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "all-zero.json"
            path.write_text(json.dumps(pack), encoding="utf-8")
            with self.assertRaisesRegex(Stage1BootstrapError, "AIR_SUITABILITY_ZERO_ALLOCATION"):
                create_stage1_new_game(
                    scenario_id=STAGE1_SCENARIO_ID, ceo_display_name="Test",
                    airline_display_name="Test", base_airport_reference_code="MNL",
                    reference_path=path,
                )

    def test_strict_policy_validation(self):
        policy = load_stage1_scenario()["air_suitability_configuration"]
        mutations = [
            lambda p: p.update(contract="UNKNOWN"),
            lambda p: p.update(configuration_version=" "),
            lambda p: p.update(interpolation_policy="UNKNOWN"),
            lambda p: p.update(right_boundary_policy="UNKNOWN"),
            lambda p: p.update(extra=True),
        ]
        for curve in ("same_ground_network_points", "separated_ground_network_points"):
            mutations.extend([
                lambda p, c=curve: p.update({c: []}),
                lambda p, c=curve: p.update({c: p[c][:1]}),
                lambda p, c=curve: p[c][0].update(distance_m=1),
                lambda p, c=curve: p[c][1].update(distance_m=0),
                lambda p, c=curve: p[c][1].update(distance_m=-1),
                lambda p, c=curve: p[c][1].update(distance_m=True),
                lambda p, c=curve: p[c][1].update(distance_m=25000.0),
                lambda p, c=curve: p[c][1].update(suitability_bps=True),
                lambda p, c=curve: p[c][1].update(suitability_bps=-1),
                lambda p, c=curve: p[c][1].update(suitability_bps=10001),
                lambda p, c=curve: p[c][1].update(suitability_bps=1.5),
                lambda p, c=curve: p[c][1].update(extra=1),
            ])
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                candidate = deepcopy(policy)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    validate_air_suitability_configuration(candidate)
        for invalid in (None, [], True):
            with self.assertRaises(ValueError):
                validate_air_suitability_configuration(invalid)

    def test_required_airport_inputs_validate_at_pack_and_world_boundaries(self):
        world = new_world()
        for field, values in (("ground_network_id", (None, "", " ", " LUZON", True)),
                              ("tourism_pull_ppm", (None, True, -1, 5000001, 1.5))):
            for value in values:
                with self.subTest(field=field, value=value):
                    candidate = deepcopy(world)
                    next(iter(candidate["world_state"]["airports"].values()))[field] = value
                    self.assertIn("invalid_air_suitability_airport", {e.code for e in validate_world(candidate).errors})
                    pack = load_stage1_scenario()
                    next(r for r in pack["airport_pack"]["records"] if r["active"])[field] = value
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / "invalid.json"
                        path.write_text(json.dumps(pack), encoding="utf-8")
                        with self.assertRaises(Stage1BootstrapError):
                            load_stage1_scenario(reference_path=path)
            candidate = deepcopy(world)
            next(iter(candidate["world_state"]["airports"].values())).pop(field)
            self.assertIn("invalid_air_suitability_airport", {e.code for e in validate_world(candidate).errors})

    def test_legacy_model3_and_model4_exact_witnesses(self):
        from tests.test_stage1_demand_model4 import model4_world
        world, airport_ids, old = model4_world(model3_marker=True)
        self.assertNotIn("air_suitability_configuration", configuration(world))
        self.assertEqual(calculate_model4_input_fingerprint(world),
                         "4b57a841058c38714bfba6ea045ea16cdbb5305d2faa6a72d5209fa93c9cf4f5")
        self.assertEqual(project_model4_pair(world, airport_ids["MNL"], airport_ids["DVO"])["base_daily_bookers"], Decimal(26000))
        self.assertEqual(old["payload"]["resolution_fingerprint"],
                         "3836905db953bd7d4e7210d9ecefc4f6bd93dc4f060bc6bcc6cce44e0325af01")
        reused = resolve_daily_cohort(world, old["payload"]["market_id"], old["payload"]["cohort_date"])
        self.assertTrue(reused.reused)


if __name__ == "__main__":
    unittest.main()
