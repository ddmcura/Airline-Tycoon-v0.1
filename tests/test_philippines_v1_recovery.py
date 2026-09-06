"""Focused Philippines v1 recovery-pack, projection, and terminal proofs."""

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.terminal.main import run_terminal
from game.demand import (
    project_market_opportunities,
    project_model4_pair,
)
from game.demand.model4 import resolve_model4_active_daily_cohorts
from game.scheduling import create_weekly_round_trip_rotation
from game.simulation import process_events_through
from game.world_state import (
    PHILIPPINES_ACTIVE_AIRPORT_COUNT,
    PHILIPPINES_AIRPORT_PACK_REFERENCE_DATE,
    PHILIPPINES_AIRPORT_PACK_VERSION,
    PHILIPPINES_DIRECTIONAL_MARKET_COUNT,
    STAGE1_SCENARIO_ID,
    Stage1BootstrapError,
    active_stage1_airports,
    create_stage1_new_game,
    load_stage1_scenario,
    materialize_country_pack,
    validate_world,
)


EXPECTED_ACTIVE_CODES = (
    "BCD", "BPA", "BSO", "BXU", "CBO", "CEB", "CGM", "CGY", "CRK",
    "CRM", "CYP", "CYZ", "DGT", "DPL", "DRP", "DVO", "ENI", "EUQ",
    "GES", "IAO", "ILO", "IQR", "KLO", "LAO", "MBT", "MNL", "MPH",
    "OZC", "PAG", "PPS", "RXS", "SJI", "SUG", "SWL", "TAC", "TAG",
    "TBH", "TUG", "TWT", "USU", "VRC", "WNP", "ZAM",
)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def new_world(base="MNL"):
    return create_stage1_new_game(
        scenario_id=STAGE1_SCENARIO_ID,
        ceo_display_name="Avery Chen",
        airline_display_name="Meridian Air",
        base_airport_reference_code=base,
    )


def publish_mnl_mbt(world):
    state = world["world_state"]
    result = create_weekly_round_trip_rotation(
        world,
        airline_id=state["player"]["primary_airline_id"],
        aircraft_id=next(iter(state["aircraft"])),
        destination_airport_reference_code="MBT",
        fare_minor=10_000,
        first_operating_date="2026-09-07",
    )
    if not result.succeeded:
        raise AssertionError(result)
    return result


class PhilippinesV1PackTests(unittest.TestCase):
    def test_exact_membership_counts_markets_and_lgp_drp_treatment(self):
        pack = load_stage1_scenario()["airport_pack"]
        active = active_stage1_airports()
        self.assertEqual(PHILIPPINES_ACTIVE_AIRPORT_COUNT, 43)
        self.assertEqual(tuple(item["reference_code"] for item in active), EXPECTED_ACTIVE_CODES)
        self.assertEqual(pack["pack_version"], PHILIPPINES_AIRPORT_PACK_VERSION)
        self.assertEqual(pack["reference_date"], PHILIPPINES_AIRPORT_PACK_REFERENCE_DATE)
        inactive = [item for item in pack["records"] if not item["active"]]
        self.assertEqual([item["reference_code"] for item in inactive], ["LGP"])
        world = new_world("IQR")
        self.assertEqual(len(world["world_state"]["airports"]), 43)
        self.assertEqual(len(world["world_state"]["directional_markets"]), PHILIPPINES_DIRECTIONAL_MARKET_COUNT)
        codes = {item["reference_code"] for item in world["world_state"]["airports"].values()}
        self.assertIn("DRP", codes)
        self.assertNotIn("LGP", codes)
        self.assertTrue(all(
            world["world_state"]["airports"][market["origin_airport_id"]]["reference_code"] != "LGP"
            and world["world_state"]["airports"][market["destination_airport_id"]]["reference_code"] != "LGP"
            for market in world["world_state"]["directional_markets"].values()
        ))

    def test_every_active_member_is_a_valid_home_base(self):
        for code in EXPECTED_ACTIVE_CODES:
            with self.subTest(code=code):
                world = new_world(code)
                state = world["world_state"]
                airline = state["airlines"][state["player"]["primary_airline_id"]]
                base = state["airports"][airline["base_airport_ids"][0]]
                self.assertEqual(base["reference_code"], code)
                self.assertTrue(validate_world(world).is_valid)

    def test_bootstrap_is_deterministic_and_dictionary_order_independent(self):
        canonical = load_stage1_scenario()
        reordered = {key: deepcopy(canonical[key]) for key in reversed(tuple(canonical))}
        airport_pack = reordered["airport_pack"]
        airport_pack["records"] = [
            {key: value for key, value in reversed(tuple(record.items()))}
            for record in reversed(airport_pack["records"])
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reordered.json"
            path.write_text(json.dumps(reordered), encoding="utf-8")
            from_reordered = create_stage1_new_game(
                scenario_id=STAGE1_SCENARIO_ID,
                ceo_display_name="Avery Chen",
                airline_display_name="Meridian Air",
                base_airport_reference_code="MNL",
                reference_path=path,
            )
        self.assertEqual(encoded(new_world("MNL")), encoded(from_reordered))

    def test_pack_rejects_required_malformed_and_conflicting_data(self):
        mutations = {
            "duplicate catalog ID": lambda p: p["airport_pack"]["records"][1].__setitem__("catalog_airport_id", p["airport_pack"]["records"][0]["catalog_airport_id"]),
            "duplicate IATA": lambda p: p["airport_pack"]["records"][1].__setitem__("iata", p["airport_pack"]["records"][0]["iata"]),
            "duplicate ICAO": lambda p: p["airport_pack"]["records"][1].__setitem__("icao", p["airport_pack"]["records"][0]["icao"]),
            "invalid coordinates": lambda p: p["airport_pack"]["records"][0].__setitem__("latitude_microdegrees", 90_000_001),
            "invalid timezone": lambda p: p["airport_pack"]["records"][0].__setitem__("timezone", "GMT+8"),
            "invalid population": lambda p: p["airport_pack"]["records"][0].__setitem__("population", 0),
            "missing destination type": lambda p: p["airport_pack"]["records"][0].__setitem__("demand_destination_type", ""),
            "membership contradiction": lambda p: p["airport_pack"]["records"][0].__setitem__("active", False),
            "unsupported country": lambda p: p["airport_pack"]["records"][0].__setitem__("country_reference", "XX"),
            "malformed version": lambda p: p["airport_pack"].__setitem__("pack_version", "latest"),
            "malformed date": lambda p: p["airport_pack"].__setitem__("reference_date", "09/01/2026"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                candidate = load_stage1_scenario()
                mutate(candidate)
                path = Path(directory) / "invalid.json"
                path.write_text(json.dumps(candidate), encoding="utf-8")
                with self.assertRaises(Stage1BootstrapError):
                    load_stage1_scenario(reference_path=path)

    def test_loaded_pack_and_active_projection_are_detached(self):
        pack = load_stage1_scenario()
        active = active_stage1_airports(pack)
        active[0]["city"] = "Changed"
        self.assertNotEqual(
            active[0]["city"], active_stage1_airports(pack)[0]["city"]
        )
        pack["airport_pack"]["records"][0]["city"] = "Caller mutation"
        self.assertNotEqual(
            pack["airport_pack"]["records"][0]["city"],
            load_stage1_scenario()["airport_pack"]["records"][0]["city"],
        )


class PhilippinesDemandAndResearchTests(unittest.TestCase):
    def test_same_country_membership_cannot_expand_after_materialization(self):
        world = new_world()
        before = encoded(world)
        state = world["world_state"]
        country_id = next(iter(state["countries"]))
        demand = world["simulation"]["configuration"]["demand"]
        result = materialize_country_pack(
            world,
            country_id,
            "silent-ph-expansion",
            "2",
            [{
                "catalog_airport_id": "ph-forged-rpzz",
                "reference_code": "ZZZ",
                "display_name": "Forged Airport",
                "timezone": "Asia/Manila",
                "population": 1,
                "latitude_microdegrees": 0,
                "longitude_microdegrees": 0,
                "demand_destination_type": "MINOR_CITY",
            }],
            expected_pack_revision=demand["market_pack_configuration"]["revision"],
            expected_demand_revision=state["demand_state"]["demand_model_revision"],
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "PACK_ALREADY_MATERIALIZED")
        self.assertEqual(encoded(world), before)

    def test_processed_cohorts_reuse_without_reroll(self):
        world = new_world()
        publish_mnl_mbt(world)
        first = resolve_model4_active_daily_cohorts(world, "2026-09-01")
        self.assertTrue(first.succeeded, first.issues)
        snapshot = encoded(world)
        second = resolve_model4_active_daily_cohorts(world, "2026-09-01")
        self.assertTrue(second.succeeded, second.issues)
        self.assertTrue(all(item.reused for item in second.cohorts))
        self.assertEqual(encoded(world), snapshot)

    def test_booking_checkpoint_scales_only_to_service_markets(self):
        world = new_world()
        publish_mnl_mbt(world)
        result = process_events_through(world, "2026-09-02T00:00:00Z")
        self.assertTrue(result.succeeded, result.failure)
        checkpoints = world["world_state"]["booking_state"]["booking_checkpoints"]
        current = next(
            item for item in checkpoints.values()
            if item["checkpoint_date"] == "2026-09-02"
        )
        self.assertEqual(len(current["market_results"]), 2)
        self.assertEqual(len(world["world_state"]["directional_markets"]), 1_806)

    def test_projection_is_pre_service_deterministic_detached_and_validates_once(self):
        world = new_world("IQR")
        before = encoded(world)
        with patch("game.demand.model4.validate_world", wraps=validate_world) as observed:
            rows = project_market_opportunities(
                world, origin_airport_id="IQR", limit=100
            )
        self.assertEqual(observed.call_count, 1)
        self.assertEqual(len(rows), 42)
        self.assertEqual([row["market_id"] for row in rows], sorted(row["market_id"] for row in rows))
        self.assertTrue(all(not row["qualifying_player_service_exists"] for row in rows))
        self.assertTrue(all(row["player_published_capacity"] == 0 for row in rows))
        self.assertEqual(world["world_state"]["demand_state"]["processed_cohorts"], {})
        self.assertEqual(encoded(world), before)
        rows[0]["origin_airport_name"] = "Changed"
        rows[0]["qualifying_player_dated_flight_ids"] += ("forged",)
        self.assertEqual(encoded(world), before)
        self.assertEqual(
            project_market_opportunities(world, origin_airport_id="IQR", limit=100),
            project_market_opportunities(deepcopy(world), origin_airport_id="IQR", limit=100),
        )

    def test_projection_limit_zero_returns_empty(self):
        self.assertEqual(project_market_opportunities(new_world(), limit=0), [])

    def test_projection_limit_one_returns_exactly_one_market(self):
        rows = project_market_opportunities(new_world(), limit=1)
        self.assertEqual(len(rows), 1)

    def test_projection_positive_limit_preserves_order_and_truncation(self):
        world = new_world("IQR")
        all_rows = project_market_opportunities(
            world, origin_airport_id="IQR", limit=100
        )
        limited_rows = project_market_opportunities(
            world, origin_airport_id="IQR", limit=5
        )
        self.assertEqual(limited_rows, all_rows[:5])
        self.assertEqual(
            [row["market_id"] for row in limited_rows],
            sorted(row["market_id"] for row in limited_rows),
        )

    def test_projection_exposes_current_player_service_without_creating_more(self):
        world = new_world()
        publish_mnl_mbt(world)
        before = encoded(world)
        row = next(
            item for item in project_market_opportunities(
                world, origin_airport_id="MNL", limit=100
            )
            if item["destination_airport_reference_code"] == "MBT"
        )
        self.assertTrue(row["qualifying_player_service_exists"])
        self.assertEqual(row["player_published_capacity"], 180)
        self.assertEqual(row["player_fare_minor"], 10_000)
        self.assertEqual(row["current_confirmed_bookings"], 0)
        self.assertGreater(row["base_daily_directional_bookers"], 0)
        self.assertEqual(encoded(world), before)

    def test_foreign_pack_regression_preserves_existing_philippine_pairs(self):
        # The generic lifecycle proof uses a PH foundation and a latent VN pack;
        # assert its before/after pair witness here as Philippines recovery scope.
        from tests.test_stage1_market_packs import model4_world, vietnam_catalog

        world, ids, _old = model4_world(model3_marker=True)
        ph_before = project_model4_pair(world, ids["MNL"], ids["DVO"])[
            "base_daily_bookers"
        ]
        country_id = next(
            key for key, value in world["world_state"]["countries"].items()
            if value["external_reference_code"] == "VN"
        )
        demand = world["simulation"]["configuration"]["demand"]
        result = materialize_country_pack(
            world,
            country_id,
            "test-vn",
            "1",
            vietnam_catalog(),
            expected_pack_revision=demand["market_pack_configuration"]["revision"],
            expected_demand_revision=world["world_state"]["demand_state"]["demand_model_revision"],
        )
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(
            project_model4_pair(world, ids["MNL"], ids["DVO"])["base_daily_bookers"],
            ph_before,
        )


class _ObservedOutput(StringIO):
    def __init__(self):
        super().__init__()
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1
        return super().flush()


class _FlushCheckingInput(StringIO):
    def __init__(self, value, output):
        super().__init__(value)
        self.output = output
        self.read_count = 0

    def readline(self, *args, **kwargs):
        self.read_count += 1
        if self.output.flush_count < self.read_count:
            raise AssertionError("prompt was not flushed before input")
        return super().readline(*args, **kwargs)


class PhilippinesTerminalTests(unittest.TestCase):
    def test_prompt_flushes_before_every_read_and_invalid_base_reprompts(self):
        output = _ObservedOutput()
        script = "\n".join(("1", "Ada", "Recovery Air", "x", "22", "0", "y", ""))
        status = run_terminal(_FlushCheckingInput(script, output), output)
        self.assertEqual(status, 0)
        transcript = output.getvalue()
        self.assertIn("Invalid base selection", transcript)
        self.assertIn("Created Recovery Air at IQR", transcript)
        self.assertIn("CEO display name (or back):\n> ", transcript)
        self.assertIn("Airline display name (or back):\n> ", transcript)

    def test_market_browser_shows_pre_service_demand_without_internal_jargon(self):
        script = "\n".join((
            "1", "Ada", "Research Air", "26",
            "9", "", "", "1", "", "0",
            "0", "y", "",
        ))
        output = StringIO()
        self.assertEqual(run_terminal(StringIO(script), output), 0)
        transcript = output.getvalue()
        self.assertIn("MARKET RESEARCH - FROM METRO MANILA (MNL)", transcript)
        self.assertGreaterEqual(transcript.count("Base daily market demand:"), 5)
        self.assertIn("Your scheduled seats: 0", transcript)
        self.assertIn("Your service: None", transcript)
        self.assertIn("It does not guarantee that every passenger will choose your airline", transcript)
        for internal in ("fingerprint", "revision_context", "market-000", "cohort"):
            self.assertNotIn(internal, transcript.lower())


if __name__ == "__main__":
    unittest.main()
