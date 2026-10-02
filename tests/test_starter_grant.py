"""Fresh PH starter grant and preserved saved-starter contracts."""

from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from app.session import Stage1Session
from game.aircraft_market.reference_catalog import load_aircraft_catalog
from game.aircraft_operations import project_airline_fleet
from game.scheduling import WeeklyDraft, create_weekly_round_trip_rotation
from game.scheduling.timing import timing_bounds
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.persistence import SaveStore
from game.world_state.timestamps import parse_canonical_utc
from tests.legacy_starter_fixture import with_legacy_starter


def fresh_world():
    return create_stage1_new_game(
        scenario_id="stage1-philippines-v1", ceo_display_name="Avery",
        airline_display_name="Meridian", base_airport_reference_code="MNL")


class StarterGrantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fresh_world()

    def test_schema_mirror_and_scenario_grant(self):
        root = Path(__file__).parents[1]
        for path in (root / "Docs/03 Technical/Stage 1 State Schema.md",
                     root / "Data/Templates/template_reference.txt"):
            self.assertIn("STARTER_GRANT", path.read_text(encoding="utf-8"))
        world = self.base
        self.assertTrue(validate_world(world).is_valid)
        state = world["world_state"]
        aircraft = next(iter(state["aircraft"].values()))
        view = load_aircraft_catalog(catalog_version="ph-aircraft-catalog-v1").model(
            aircraft["model_reference"])
        self.assertEqual(aircraft["model_reference"], "airbus-a320neo")
        self.assertEqual(aircraft["configuration"]["catalog_version"], view["catalog_version"])
        self.assertEqual(aircraft["configuration"]["economy_capacity"], view["model"]["max_economy_seats"])
        self.assertEqual(aircraft["lifecycle"]["acquisition_type"], "STARTER_GRANT")
        self.assertEqual(aircraft["lifecycle"]["ownership_status"], "OWNED")
        self.assertIsNone(aircraft["lifecycle"]["aircraft_contract_id"])
        self.assertFalse(aircraft["lifecycle"]["fixed_configuration"])
        self.assertEqual(state["transactions"], {})
        self.assertEqual(state["aircraft_contracts"], {})
        owner = state["player"]["primary_airline_id"]
        balances = {state["financial_accounts"][key]["code"]:
                    state["financial_accounts"][key]["balance_minor"]
                    for key in state["airlines"][owner]["financial_account_ids"]}
        self.assertEqual(balances["cash"], 30_000_000_000)
        self.assertEqual(balances["aircraft_assets"], 0)
        self.assertEqual(project_airline_fleet(world, owner)[0]["model_reference"], "airbus-a320neo")
        session = Stage1Session()
        session.new_game("Avery", "Meridian", "MNL")
        self.assertEqual(session.fleet()[0]["model_reference"], "airbus-a320neo")

    def test_malformed_grants_are_rejected(self):
        aircraft_id = next(iter(self.base["world_state"]["aircraft"]))
        mutations = (
            lambda w: w["world_state"]["aircraft"][aircraft_id].pop("configuration"),
            lambda w: w["world_state"]["aircraft"][aircraft_id]["lifecycle"].update(
                ownership_status="LESSOR_OWNED"),
            lambda w: w["world_state"]["aircraft"][aircraft_id]["lifecycle"].update(
                aircraft_contract_id="aircraft_contract-00000001"),
            lambda w: w["world_state"]["aircraft"][aircraft_id]["lifecycle"].update(
                source_listing_id="used_listing-00000001"),
            lambda w: w["world_state"]["aircraft"][aircraft_id]["lifecycle"].update(
                manufactured_date="2025-01-01"),
        )
        for mutate in mutations:
            candidate = deepcopy(self.base)
            mutate(candidate)
            self.assertFalse(validate_world(candidate).is_valid)

    def test_mnl_dvo_uses_catalog_timing_and_thirty_minute_turnaround(self):
        world = deepcopy(self.base)
        state = world["world_state"]
        aircraft_id = next(iter(state["aircraft"]))
        airport = {row["reference_code"]: key for key, row in state["airports"].items()}
        draft = WeeklyDraft(world, airline_id=state["player"]["primary_airline_id"],
                            aircraft_id=aircraft_id)
        draft.add(airport["MNL"], airport["DVO"], departure_utc="2026-09-07T00:00:00Z")
        outbound = draft.legs[0]
        self.assertEqual(outbound["planning_timing"]["contract"], "PH_SCHEDULING_TIMING_V2")
        self.assertEqual(timing_bounds(outbound["planning_timing"])[1], (1800, 6000, 0))
        arrival = parse_canonical_utc(outbound["departure_utc"]) + timedelta(seconds=6000)
        self.assertEqual(arrival.isoformat(), "2026-09-07T01:40:00+00:00")
        draft.add_return()
        self.assertEqual(draft.legs[1]["departure_utc"], "2026-09-07T02:10:00Z")
        self.assertTrue(draft.save(world).succeeded)
        self.assertTrue(validate_world(world).is_valid)

    def test_quick_rotation_is_not_a_new_starter_market_option(self):
        world = deepcopy(self.base)
        state = world["world_state"]
        result = create_weekly_round_trip_rotation(
            world, airline_id=state["player"]["primary_airline_id"],
            aircraft_id=next(iter(state["aircraft"])),
            destination_airport_reference_code="DVO", fare_minor=0,
            first_operating_date="2026-09-07")
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "STARTER_ONLY")
        self.assertTrue(validate_world(world).is_valid)

    def test_roundtrip_grant_and_legacy_saved_aircraft(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SaveStore(directory)
            for world, expected in ((self.base, "airbus-a320neo"),
                                    (with_legacy_starter(self.base), "A320-200")):
                career = store.new_career_id()
                store.save(career, "manual", world)
                loaded, _ = store.load(career)
                aircraft = next(iter(loaded["world_state"]["aircraft"].values()))
                self.assertEqual(aircraft["model_reference"], expected)
                self.assertEqual(loaded["simulation"]["clock_state"], "PAUSED")
                self.assertTrue(validate_world(loaded).is_valid)
                if expected == "A320-200":
                    self.assertNotIn("lifecycle", aircraft)
                else:
                    self.assertEqual(aircraft["lifecycle"]["acquisition_type"], "STARTER_GRANT")
