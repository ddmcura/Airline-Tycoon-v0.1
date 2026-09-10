"""Focused Milestone 7 bootstrap, adapter, projection, and transcript tests."""

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from app.terminal.formatting import (
    format_minor_units,
    format_money,
    parse_duration_seconds,
    parse_usd_fare,
    parse_utc_timestamp,
    round_ratio_half_even,
)
from app.terminal.main import run_terminal
from app.terminal.session import Stage1Session
from game.aircraft_operations import (
    project_airline_fleet,
    project_airline_flights,
    project_recent_flight_results,
)
from game.booking import (
    prepare_daily_booking_checkpoint,
    process_daily_booking_checkpoint,
)
from game.scheduling import (
    create_weekly_round_trip_rotation,
    publish_next_rotation,
)
from game.simulation import process_events_through, process_next_event
from game.world_state import (
    STAGE1_SCENARIO_ID,
    Stage1BootstrapError,
    create_stage1_new_game,
    load_stage1_scenario,
    validate_world,
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


def planned_world(*, fare=10_000):
    world = new_world()
    airline_id = world["world_state"]["player"]["primary_airline_id"]
    aircraft_id = next(iter(world["world_state"]["aircraft"]))
    result = create_weekly_round_trip_rotation(
        world,
        airline_id=airline_id,
        aircraft_id=aircraft_id,
        destination_airport_reference_code="CEB",
        fare_minor=fare,
        first_operating_date="2026-09-07",
    )
    if not result.succeeded:
        raise AssertionError(result)
    return world, airline_id, aircraft_id, result


class Stage1BootstrapTests(unittest.TestCase):
    def test_bootstrap_is_deterministic_valid_latest_schema_and_detached(self):
        left = new_world("DVO")
        right = new_world("DVO")
        self.assertEqual(encoded(left), encoded(right))
        self.assertTrue(validate_world(left).is_valid, validate_world(left).as_dict())
        self.assertEqual(left["metadata"]["save_schema_version"], 4)
        right["world_state"]["player"]["ceo_display_name"] = "Changed"
        self.assertEqual(left["world_state"]["player"]["ceo_display_name"], "Avery Chen")

    def test_bootstrap_installs_model4_booking_fulfilment_and_checkpoint(self):
        world = new_world()
        configuration = world["simulation"]["configuration"]
        self.assertEqual(configuration["demand"]["model_version"], 4)
        self.assertEqual(configuration["booking"]["revision"], 2)
        self.assertEqual(configuration["flight_fulfilment"]["current_revision"], 1)
        self.assertEqual(len(world["world_state"]["directional_markets"]), 1_806)
        checkpoints = world["world_state"]["booking_state"]["booking_checkpoints"]
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(next(iter(checkpoints.values()))["checkpoint_date"], "2026-09-01")
        events = list(world["world_state"]["pending_events"].values())
        self.assertEqual([(item["event_type"], item["due_at_utc"]) for item in events], [
            ("DAILY_BOOKING_CHECKPOINT", "2026-09-02T00:00:00Z")
        ])

    def test_bootstrap_has_usd_accounts_and_free_parked_starter_aircraft(self):
        world = new_world("CEB")
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        airline = state["airlines"][airline_id]
        accounts = {
            state["financial_accounts"][account_id]["code"]:
            state["financial_accounts"][account_id]
            for account_id in airline["financial_account_ids"]
        }
        self.assertEqual(set(accounts), {
            "cash", "aircraft_assets", "debt", "unflown_tickets",
            "passenger_revenue", "operating_expenses",
        })
        self.assertTrue(all(item["currency"] == "USD" for item in accounts.values()))
        self.assertEqual(accounts["cash"]["balance_minor"], 100_000_000)
        self.assertEqual(accounts["debt"]["balance_minor"], 0)
        aircraft = next(iter(state["aircraft"].values()))
        base_id = airline["base_airport_ids"][0]
        self.assertEqual(
            (aircraft["display_registration"], aircraft["model_reference"], aircraft["status"]),
            ("RP-C0001", "A320-200", "PARKED"),
        )
        self.assertEqual(aircraft["current_airport_id"], base_id)
        self.assertEqual(state["transactions"], {})

    def test_bootstrap_rejects_bad_inputs_and_never_returns_partial_authority(self):
        cases = (
            dict(scenario_id="other", ceo_display_name="C", airline_display_name="A", base_airport_reference_code="MNL"),
            dict(scenario_id=STAGE1_SCENARIO_ID, ceo_display_name=" ", airline_display_name="A", base_airport_reference_code="MNL"),
            dict(scenario_id=STAGE1_SCENARIO_ID, ceo_display_name="C", airline_display_name="", base_airport_reference_code="MNL"),
            dict(scenario_id=STAGE1_SCENARIO_ID, ceo_display_name="C", airline_display_name="A", base_airport_reference_code="SIN"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(Stage1BootstrapError):
                    create_stage1_new_game(**arguments)

    def test_malformed_reference_pack_is_rejected_and_loaded_pack_is_detached(self):
        pack = load_stage1_scenario()
        other = load_stage1_scenario()
        pack["airport_pack"]["records"][0]["display_name"] = "Changed"
        self.assertNotEqual(pack, other)
        other["authoritative_currency"] = "EUR"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(other), encoding="utf-8")
            with self.assertRaises(Stage1BootstrapError) as caught:
                load_stage1_scenario(reference_path=path)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_CURRENCY")


class Stage1CurrencyAndParsingTests(unittest.TestCase):
    def test_fare_grammar_accepts_exact_forms(self):
        self.assertEqual(parse_usd_fare("0"), 0)
        self.assertEqual(parse_usd_fare("0.00"), 0)
        self.assertEqual(parse_usd_fare("12"), 1200)
        self.assertEqual(parse_usd_fare("12.3"), 1230)
        self.assertEqual(parse_usd_fare("12.34"), 1234)

    def test_fare_grammar_rejects_malformed_and_enormous_inputs(self):
        for value in ("", "-1", "+1", "1,000", "1e2", "True", "1.234", ".50", "0" * 40):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_usd_fare(value)

    def test_duration_and_timestamp_grammars(self):
        self.assertEqual(parse_duration_seconds("30m"), 1800)
        self.assertEqual(parse_duration_seconds("6h"), 21600)
        self.assertEqual(parse_duration_seconds("1d"), 86400)
        for value in ("0m", "1.5h", "-1d", "6", "h"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_duration_seconds(value)
        self.assertEqual(parse_utc_timestamp("2026-09-01T00:00:00Z"), "2026-09-01T00:00:00Z")
        with self.assertRaises(ValueError):
            parse_utc_timestamp("2026-09-01 00:00:00")

    def test_display_conversion_is_integer_half_even_and_keeps_usd_visible(self):
        rates = load_stage1_scenario()["display_currencies"]
        self.assertEqual(round_ratio_half_even(1, 1, 2), 0)
        self.assertEqual(round_ratio_half_even(3, 1, 2), 2)
        self.assertEqual(round_ratio_half_even(-3, 1, 2), -2)
        self.assertEqual(format_minor_units(-123, symbol="$", code="USD"), "-$1.23 USD")
        converted = format_money(10_000, "PHP", rates)
        self.assertIn("$100.00 USD", converted)
        self.assertIn("PHP 5,800.00 PHP display", converted)

    def test_display_currency_preference_does_not_mutate_authority_or_dirty_flag(self):
        session = Stage1Session()
        session.new_game("C", "A", "MNL")
        before = session.authoritative_bytes()
        changed = session.changed
        session.set_display_currency("EUR")
        self.assertEqual(session.authoritative_bytes(), before)
        self.assertEqual(session.changed, changed)


class Stage1RotationBookingAndProjectionTests(unittest.TestCase):
    def test_rotation_is_atomic_and_publishes_exactly_two_continuous_occurrences(self):
        world, airline_id, aircraft_id, result = planned_world(fare=0)
        self.assertEqual(len(result.schedule_ids), 2)
        self.assertEqual(len(result.dated_flight_ids), 2)
        flights = [world["world_state"]["dated_flights"][item] for item in result.dated_flight_ids]
        self.assertEqual(flights[0]["destination_airport_id"], flights[1]["origin_airport_id"])
        self.assertEqual(flights[1]["destination_airport_id"], world["world_state"]["aircraft"][aircraft_id]["current_airport_id"])
        self.assertTrue(all(item["fare_offer"] == {"currency": "USD", "amount_minor": 0} for item in flights))
        self.assertTrue(validate_world(world).is_valid)

    def test_rotation_rejections_leave_world_byte_identical(self):
        world = new_world()
        state = world["world_state"]
        airline_id = state["player"]["primary_airline_id"]
        aircraft_id = next(iter(state["aircraft"]))
        before = encoded(world)
        origin_id = state["aircraft"][aircraft_id]["current_airport_id"]
        origin = state["airports"][origin_id]["reference_code"]
        result = create_weekly_round_trip_rotation(
            world, airline_id=airline_id, aircraft_id=aircraft_id,
            destination_airport_reference_code=origin, fare_minor=100,
            first_operating_date="2026-09-07",
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, "SAME_ENDPOINT")
        self.assertEqual(encoded(world), before)
        malformed = create_weekly_round_trip_rotation(
            world, airline_id=airline_id, aircraft_id=aircraft_id,
            destination_airport_reference_code="CEB", fare_minor=-1,
            first_operating_date="not-a-date",
        )
        self.assertFalse(malformed.succeeded)
        self.assertEqual(encoded(world), before)

    def test_prepare_checkpoint_is_detached_and_stale_witness_rejects(self):
        world, _airline_id, _aircraft_id, _result = planned_world()
        # Observe the exact event-boundary candidate before the due event runs.
        world["simulation"]["time_utc"] = "2026-09-02T00:00:00Z"
        self.assertTrue(validate_world(world).is_valid, validate_world(world).as_dict())
        before = encoded(world)
        prepared = prepare_daily_booking_checkpoint(world)
        self.assertTrue(prepared.succeeded, prepared.issues)
        self.assertEqual(encoded(world), before)
        arguments = prepared.as_kwargs()
        arguments["expected_booking_revision"] += 1
        rejected = process_daily_booking_checkpoint(world, **arguments)
        self.assertFalse(rejected.succeeded)
        self.assertEqual(rejected.status, "STALE_REVISION")
        self.assertEqual(encoded(world), before)

    def test_flight_projection_exposes_booked_capacity_and_is_detached(self):
        world, airline_id, _aircraft_id, result = planned_world()
        processed = process_events_through(world, "2026-09-07T00:00:00Z")
        self.assertTrue(processed.succeeded, processed.failure)
        rows = project_airline_flights(world, airline_id)
        outbound = rows[0]
        self.assertEqual(outbound["booked_passenger_count"], 180)
        self.assertEqual(outbound["remaining_capacity"], 0)
        self.assertEqual(outbound["booked_load_factor_basis_points"], 10_000)
        self.assertEqual(outbound["status"], "OPERATIONALLY_LOCKED")
        snapshot = encoded(world)
        outbound["next_lifecycle_event"] = {"changed": True}
        rows.append({"changed": True})
        self.assertEqual(encoded(world), snapshot)
        self.assertEqual(result.dated_flight_ids[0], outbound["dated_flight_id"])

    def test_lifecycle_finance_and_publish_next_rotation(self):
        world, airline_id, aircraft_id, _result = planned_world()
        processed = process_events_through(world, "2026-09-07T06:00:00Z")
        self.assertTrue(processed.succeeded, processed.failure)
        rows = project_airline_flights(world, airline_id)
        self.assertEqual([row["status"] for row in rows], ["COMPLETED", "COMPLETED"])
        self.assertEqual([row["carried_passenger_count"] for row in rows], [180, 180])
        self.assertTrue(all(row["result_identity"] is not None for row in rows))
        aircraft = world["world_state"]["aircraft"][aircraft_id]
        self.assertEqual(aircraft["status"], "PARKED")
        finance = project_recent_flight_results(world, airline_id)
        self.assertEqual(finance["cumulative_revenue_minor"], 3_600_000)
        self.assertEqual(finance["cumulative_cost_minor"], 1_338_000)
        self.assertEqual(finance["cumulative_profit_minor"], 2_262_000)
        self.assertLessEqual(len(finance["recent_results"]), 10)
        self.assertLessEqual(len(finance["recent_transactions"]), 10)
        nested = deepcopy(finance)
        nested["recent_transactions"][0]["entries"][0]["amount_minor"] = 999
        self.assertNotEqual(nested, project_recent_flight_results(world, airline_id))
        following = publish_next_rotation(world, airline_id=airline_id)
        self.assertTrue(following.succeeded, following.issues)
        self.assertEqual(len(following.dated_flight_ids), 2)
        self.assertEqual(following.first_operating_date, "2026-09-14")

    def test_next_event_advances_only_one_boundary(self):
        world = new_world()
        before = len(world["world_state"]["event_history"])
        result = process_next_event(world)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(result.completed_event_ids), 1)
        self.assertEqual(len(world["world_state"]["event_history"]), before + 1)
        self.assertEqual(world["simulation"]["time_utc"], "2026-09-02T00:00:00Z")


class Stage1TerminalTranscriptTests(unittest.TestCase):
    def test_complete_scripted_transcript_and_temporary_exit_warning(self):
        script = "\n".join((
            "1", "Ada", "Deterministic Air", "26",
            "10", "1", "6", "100.00", "", "y",
            "5", "4", "2026-09-07T06:00:00Z", "0",
            "4", "6", "7", "0", "y", "",
        ))
        output = StringIO()
        status = run_terminal(StringIO(script), output)
        transcript = output.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("Published rotation with 2 flights", transcript)
        self.assertIn("DAILY_BOOKING_CHECKPOINT", transcript)
        self.assertIn("STAGE1_FLIGHT_DEPARTURE", transcript)
        self.assertIn("STAGE1_FLIGHT_COMPLETION", transcript)
        self.assertIn("Carried 180 (100.00%)", transcript)
        self.assertIn("Cumulative operating contribution: $22,620.00 USD", transcript)
        self.assertIn("Published 2 next weekly occurrence(s) for 2026-09-14", transcript)
        self.assertIn("This temporary session will be lost. Exit? [y/N]", transcript)
        self.assertNotIn("Save", transcript)
        self.assertNotIn("Load", transcript)

    def test_invalid_menu_recovery_back_and_eof(self):
        output = StringIO()
        status = run_terminal(StringIO("x\n1\nback\n0\n"), output)
        self.assertEqual(status, 0)
        self.assertIn("Invalid selection", output.getvalue())
        eof_output = StringIO()
        self.assertEqual(run_terminal(StringIO(""), eof_output), 0)

    def test_terminal_source_boundaries_exclude_legacy_and_background_paths(self):
        root = Path(__file__).parents[1]
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((root / "app" / "terminal").glob("*.py"))
        )
        for forbidden in (
            "save_utils", "daily_tick", "aircraft_market", "threading",
            "random.", "requests", "urllib", "tests.", "individual passenger",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
