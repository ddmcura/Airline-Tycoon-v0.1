"""Milestone 3 authoritative schedule and dated-flight publication tests."""

from copy import deepcopy
from importlib.metadata import version
from time import perf_counter
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from game.scheduling import (
    configured_publication_horizon_utc,
    create_schedule_definition,
    extend_publication_window,
    publish_configured_window,
    publish_occurrences_through,
    rebuild_dated_flight_indexes,
    revise_future_schedule,
    validate_schedule_definition,
)
from game.simulation import process_next_event, schedule_event
from game.world_state import (
    add_aircraft,
    add_airline,
    add_airport_reference,
    add_connection,
    add_directional_market,
    create_new_world,
    validate_world,
)
from game.world_state.ids import allocate_id
from game.world_state.timezones import load_named_timezone
from tests.test_stage1_world_state import make_world


def primary_ids(world):
    state = world["world_state"]
    return state["player"]["primary_airline_id"], next(iter(state["airports"]))


def add_market_connection(world, airline_id, origin_id, destination_id):
    market_id = add_directional_market(world, origin_id, destination_id)
    return add_connection(world, airline_id, market_id, status="ACTIVE")


def create_leg(
    world,
    *,
    airline_id,
    aircraft_id,
    origin_id,
    destination_id,
    connection_id,
    departure="08:00:00",
    arrival="09:30:00",
    weekdays=(0,),
    effective="2026-08-24",
    arrival_day_offset=0,
    departure_fold=0,
    arrival_fold=0,
    capacity=180,
    fare_offer=None,
    service_type="PASSENGER",
    classification=None,
):
    if fare_offer is None:
        fare_offer = {"currency": "USD", "amount_minor": 7_500}
    if classification is None:
        classification = "NON_PASSENGER" if service_type == "DEADHEAD" else "ECONOMY"
    return create_schedule_definition(
        world,
        airline_id=airline_id,
        connection_id=connection_id,
        planned_aircraft_id=aircraft_id,
        origin_airport_id=origin_id,
        destination_airport_id=destination_id,
        weekdays=list(weekdays),
        departure_local_time=departure,
        arrival_local_time=arrival,
        arrival_day_offset=arrival_day_offset,
        departure_local_fold=departure_fold,
        arrival_local_fold=arrival_fold,
        effective_from_local_date=effective,
        capacity=capacity,
        fare_offer=fare_offer,
        service_type=service_type,
        passenger_service_classification=classification,
    )


def make_round_trip_world(*, horizon_days=30):
    world = make_world()
    airline_id, origin_id = primary_ids(world)
    destination_id = add_airport_reference(
        world,
        {
            "reference_code": "RPVM",
            "iata": "CEB",
            "display_name": "Mactan-Cebu",
            "timezone": "Asia/Manila",
        },
    )
    aircraft_id = add_aircraft(
        world,
        airline_id,
        "RP-C3001",
        "A320-200",
        home_airport_id=origin_id,
    )
    outbound_connection = add_market_connection(
        world, airline_id, origin_id, destination_id
    )
    inbound_connection = add_market_connection(
        world, airline_id, destination_id, origin_id
    )
    outbound = create_leg(
        world,
        airline_id=airline_id,
        aircraft_id=aircraft_id,
        origin_id=origin_id,
        destination_id=destination_id,
        connection_id=outbound_connection,
    )
    inbound = create_leg(
        world,
        airline_id=airline_id,
        aircraft_id=aircraft_id,
        origin_id=destination_id,
        destination_id=origin_id,
        connection_id=inbound_connection,
        departure="10:30:00",
        arrival="12:00:00",
    )
    assert outbound.succeeded and inbound.succeeded
    world["simulation"]["configuration"]["scheduling"][
        "publication_horizon_days"
    ] = horizon_days
    return world, {
        "airline": airline_id,
        "origin": origin_id,
        "destination": destination_id,
        "aircraft": aircraft_id,
        "outbound": outbound.schedule_id,
        "inbound": inbound.schedule_id,
    }


class Stage1PublicationTests(unittest.TestCase):
    def test_valid_weekly_schedule_publishes_identified_traceable_flights(self):
        world, ids = make_round_trip_world()

        result = publish_configured_window(world)

        self.assertTrue(result.succeeded, result.conflicts)
        outbound = [
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
        ]
        self.assertEqual(len(outbound), 4)
        self.assertTrue(all(flight["schedule_revision"] == 1 for flight in outbound))
        self.assertTrue(
            all(flight["dated_flight_id"] != flight["schedule_id"] for flight in outbound)
        )
        self.assertTrue(all(flight["airline_id"] == ids["airline"] for flight in outbound))
        self.assertTrue(all(flight["planned_aircraft_id"] == ids["aircraft"] for flight in outbound))
        self.assertTrue(all(flight["capacity"] == 180 for flight in outbound))
        self.assertTrue(all(flight["fare_offer"]["amount_minor"] == 7_500 for flight in outbound))
        self.assertTrue(
            all(flight["passenger_service_classification"] == "ECONOMY" for flight in outbound)
        )
        self.assertTrue(validate_world(world).is_valid)

    def test_repeated_and_overlapping_publication_is_idempotent(self):
        world, _ids = make_round_trip_world()
        first = publish_occurrences_through(world, "2026-09-10T04:30:00Z")
        snapshot = deepcopy(world)
        repeated = publish_occurrences_through(world, "2026-09-10T04:30:00Z")
        self.assertEqual(world, snapshot)
        overlapping = publish_configured_window(world)

        self.assertTrue(first.created_dated_flight_ids)
        self.assertEqual(repeated.created_dated_flight_ids, ())
        self.assertEqual(repeated.updated_dated_flight_ids, ())
        self.assertTrue(overlapping.succeeded)
        occurrence_keys = [
            flight["occurrence_key"]
            for flight in world["world_state"]["dated_flights"].values()
        ]
        self.assertEqual(len(occurrence_keys), len(set(occurrence_keys)))

    def test_extension_creates_only_newly_exposed_occurrences_and_stays_bounded(self):
        world, _ids = make_round_trip_world(horizon_days=14)
        first = publish_configured_window(world)
        old_ids = set(world["world_state"]["dated_flights"])

        extended = extend_publication_window(world, 35)

        self.assertTrue(extended.succeeded, extended.conflicts)
        self.assertTrue(set(extended.created_dated_flight_ids).isdisjoint(old_ids))
        self.assertEqual(
            set(world["world_state"]["dated_flights"]) - old_ids,
            set(extended.created_dated_flight_ids),
        )
        horizon = configured_publication_horizon_utc(world)
        self.assertTrue(
            all(
                flight["scheduled_off_block_utc"] <= horizon
                for flight in world["world_state"]["dated_flights"].values()
            )
        )
        beyond = publish_occurrences_through(world, "2026-10-01T04:30:01Z")
        self.assertEqual(beyond.status, "REJECTED")
        self.assertEqual(first.status, "COMPLETED")

    def test_local_midnight_and_date_boundary_intent_becomes_exact_utc(self):
        world = make_world()
        airline_id, mnl = primary_ids(world)
        tokyo = add_airport_reference(
            world, {"reference_code": "RJTT", "timezone": "Asia/Tokyo"}
        )
        aircraft = add_aircraft(world, airline_id, "RP-NIGHT", "A320", home_airport_id=mnl)
        outbound_connection = add_market_connection(world, airline_id, mnl, tokyo)
        inbound_connection = add_market_connection(world, airline_id, tokyo, mnl)
        outbound = create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=mnl,
            destination_id=tokyo,
            connection_id=outbound_connection,
            departure="23:30:00",
            arrival="02:00:00",
            arrival_day_offset=1,
        )
        create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=tokyo,
            destination_id=mnl,
            connection_id=inbound_connection,
            departure="03:00:00",
            arrival="06:00:00",
            weekdays=(1,),
            effective="2026-08-25",
        )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 7

        result = publish_configured_window(world)
        flight = next(
            item
            for item in world["world_state"]["dated_flights"].values()
            if item["schedule_id"] == outbound.schedule_id
        )

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(flight["scheduled_off_block_utc"], "2026-08-24T15:30:00Z")
        self.assertEqual(flight["scheduled_in_block_utc"], "2026-08-24T17:00:00Z")
        self.assertEqual(flight["scheduled_departure_local_date"], "2026-08-24")

    def test_weekly_recurrence_tracks_daylight_saving_transition(self):
        world = create_new_world(
            ceo_display_name="DST Tester",
            airline_display_name="Eastern Test",
            starting_airport={"reference_code": "KJFK", "timezone": "America/New_York"},
            difficulty="Normal",
            simulation_time_utc="2026-02-25T12:00:00Z",
            simulation_seed=1,
            starting_money="1000000.00",
        )
        airline_id, jfk = primary_ids(world)
        lax = add_airport_reference(
            world, {"reference_code": "KLAX", "timezone": "America/Los_Angeles"}
        )
        aircraft = add_aircraft(world, airline_id, "N-DST", "A320", home_airport_id=jfk)
        outbound_connection = add_market_connection(world, airline_id, jfk, lax)
        inbound_connection = add_market_connection(world, airline_id, lax, jfk)
        outbound = create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=jfk,
            destination_id=lax,
            connection_id=outbound_connection,
            departure="08:00:00",
            arrival="11:00:00",
            weekdays=(6,),
            effective="2026-03-01",
        )
        create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=lax,
            destination_id=jfk,
            connection_id=inbound_connection,
            departure="12:00:00",
            arrival="20:00:00",
            weekdays=(6,),
            effective="2026-03-01",
        )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 15

        result = publish_configured_window(world)
        departures = sorted(
            flight["scheduled_off_block_utc"]
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == outbound.schedule_id
        )

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(
            departures,
            ["2026-03-01T13:00:00Z", "2026-03-08T12:00:00Z"],
        )

    def test_date_line_crossing_preserves_local_dates_and_negative_arrival_offset(self):
        world = create_new_world(
            ceo_display_name="Date Line Tester",
            airline_display_name="Pacific Test",
            starting_airport={"reference_code": "PHNL", "timezone": "Pacific/Honolulu"},
            difficulty="Normal",
            simulation_time_utc="2026-08-20T00:00:00Z",
            simulation_seed=2,
            starting_money="1000000.00",
        )
        airline_id, hnl = primary_ids(world)
        akl = add_airport_reference(
            world, {"reference_code": "NZAA", "timezone": "Pacific/Auckland"}
        )
        aircraft = add_aircraft(world, airline_id, "N-DATE", "B787", home_airport_id=hnl)
        outbound_connection = add_market_connection(world, airline_id, hnl, akl)
        inbound_connection = add_market_connection(world, airline_id, akl, hnl)
        outbound = create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=hnl,
            destination_id=akl,
            connection_id=outbound_connection,
            departure="22:00:00",
            arrival="08:00:00",
            arrival_day_offset=2,
        )
        inbound = create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=akl,
            destination_id=hnl,
            connection_id=inbound_connection,
            departure="10:00:00",
            arrival="18:00:00",
            weekdays=(2,),
            effective="2026-08-26",
            arrival_day_offset=-1,
        )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 7

        result = publish_configured_window(world)
        records = {
            flight["schedule_id"]: flight
            for flight in world["world_state"]["dated_flights"].values()
        }

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(records[outbound.schedule_id]["scheduled_departure_local_date"], "2026-08-24")
        self.assertEqual(records[outbound.schedule_id]["scheduled_off_block_utc"], "2026-08-25T08:00:00Z")
        self.assertEqual(records[outbound.schedule_id]["scheduled_in_block_utc"], "2026-08-25T20:00:00Z")
        self.assertEqual(records[inbound.schedule_id]["scheduled_off_block_utc"], "2026-08-25T22:00:00Z")
        self.assertEqual(records[inbound.schedule_id]["scheduled_in_block_utc"], "2026-08-26T04:00:00Z")

    def test_nonexistent_dst_local_time_is_rejected_deterministically(self):
        world = create_new_world(
            ceo_display_name="DST Tester",
            airline_display_name="Gap Test",
            starting_airport={"reference_code": "KJFK", "timezone": "America/New_York"},
            difficulty="Normal",
            simulation_time_utc="2026-03-07T12:00:00Z",
            simulation_seed=1,
            starting_money="1000000.00",
        )
        airline_id, jfk = primary_ids(world)
        bos = add_airport_reference(
            world, {"reference_code": "KBOS", "timezone": "America/New_York"}
        )
        aircraft = add_aircraft(world, airline_id, "N-GAP", "A320", home_airport_id=jfk)
        connection = add_market_connection(world, airline_id, jfk, bos)
        schedule = create_leg(
            world,
            airline_id=airline_id,
            aircraft_id=aircraft,
            origin_id=jfk,
            destination_id=bos,
            connection_id=connection,
            departure="02:30:00",
            arrival="04:30:00",
            weekdays=(6,),
            effective="2026-03-08",
        )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 2

        conflicts = validate_schedule_definition(world, schedule.schedule_id)

        self.assertIn("INVALID_LOCAL_OCCURRENCE", {item.code for item in conflicts})
        self.assertEqual(world["world_state"]["dated_flights"], {})

    def test_ambiguous_time_uses_both_explicit_folds_and_rejects_fold_one_elsewhere(self):
        departures = []
        for fold in (0, 1):
            world = create_new_world(
                ceo_display_name="Fold Tester",
                airline_display_name="Fold Test",
                starting_airport={"reference_code": "KJFK", "timezone": "America/New_York"},
                difficulty="Normal",
                simulation_time_utc="2026-10-31T00:00:00Z",
                simulation_seed=fold,
                starting_money="1000000.00",
            )
            airline, jfk = primary_ids(world)
            bos = add_airport_reference(
                world, {"reference_code": "KBOS", "timezone": "America/New_York"}
            )
            aircraft = add_aircraft(world, airline, f"N-FOLD-{fold}", "A320", home_airport_id=jfk)
            connection = add_market_connection(world, airline, jfk, bos)
            schedule = create_leg(
                world,
                airline_id=airline,
                aircraft_id=aircraft,
                origin_id=jfk,
                destination_id=bos,
                connection_id=connection,
                departure="01:30:00",
                arrival="03:00:00",
                weekdays=(6,),
                effective="2026-11-01",
                departure_fold=fold,
            )
            world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 2
            result = publish_configured_window(world)
            self.assertTrue(result.succeeded, result.conflicts)
            departures.append(
                next(
                    flight["scheduled_off_block_utc"]
                    for flight in world["world_state"]["dated_flights"].values()
                    if flight["schedule_id"] == schedule.schedule_id
                )
            )
        self.assertEqual(departures, ["2026-11-01T05:30:00Z", "2026-11-01T06:30:00Z"])

        invalid, ids = make_round_trip_world(horizon_days=7)
        invalid_schedule = invalid["world_state"]["schedule_definitions"][ids["outbound"]]
        invalid_schedule["revisions"]["1"]["recurrence"]["departure_local_fold"] = 1
        self.assertIn(
            "INVALID_LOCAL_OCCURRENCE",
            {
                conflict.code
                for conflict in validate_schedule_definition(invalid, ids["outbound"])
            },
        )

    def test_named_zones_cover_fractional_offsets_and_non_hour_dst(self):
        world = create_new_world(
            ceo_display_name="Offset Tester",
            airline_display_name="Offset Test",
            starting_airport={"reference_code": "VNKT", "timezone": "Asia/Kathmandu"},
            difficulty="Normal",
            simulation_time_utc="2026-08-23T00:00:00Z",
            simulation_seed=1,
            starting_money="1000000.00",
        )
        airline, kathmandu = primary_ids(world)
        kolkata = add_airport_reference(
            world, {"reference_code": "VECC", "timezone": "Asia/Kolkata"}
        )
        aircraft = add_aircraft(world, airline, "9N-OFFSET", "A320", home_airport_id=kathmandu)
        connection = add_market_connection(world, airline, kathmandu, kolkata)
        leg = create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=kathmandu,
            destination_id=kolkata,
            connection_id=connection,
            departure="08:00:00",
            arrival="09:00:00",
            effective="2026-08-24",
        )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 2
        self.assertTrue(publish_configured_window(world).succeeded)
        flight = next(
            item
            for item in world["world_state"]["dated_flights"].values()
            if item["schedule_id"] == leg.schedule_id
        )
        self.assertEqual(flight["scheduled_off_block_utc"], "2026-08-24T02:15:00Z")
        self.assertEqual(flight["scheduled_in_block_utc"], "2026-08-24T03:30:00Z")

        lord_howe = load_named_timezone("Australia/Lord_Howe")
        before = lord_howe.utcoffset(__import__("datetime").datetime(2026, 9, 27, 8))
        after = lord_howe.utcoffset(__import__("datetime").datetime(2026, 10, 4, 8))
        self.assertEqual(int((after - before).total_seconds()), 1800)

        dst_world = create_new_world(
            ceo_display_name="Half DST Tester",
            airline_display_name="Half DST Test",
            starting_airport={"reference_code": "YLHI", "timezone": "Australia/Lord_Howe"},
            difficulty="Normal",
            simulation_time_utc="2026-09-25T00:00:00Z",
            simulation_seed=2,
            starting_money="1000000.00",
        )
        dst_airline, island = primary_ids(dst_world)
        sydney = add_airport_reference(
            dst_world, {"reference_code": "YSSY", "timezone": "Australia/Sydney"}
        )
        dst_aircraft = add_aircraft(
            dst_world, dst_airline, "VH-HALF", "A320", home_airport_id=island
        )
        outbound_connection = add_market_connection(dst_world, dst_airline, island, sydney)
        inbound_connection = add_market_connection(dst_world, dst_airline, sydney, island)
        outbound = create_leg(
            dst_world,
            airline_id=dst_airline,
            aircraft_id=dst_aircraft,
            origin_id=island,
            destination_id=sydney,
            connection_id=outbound_connection,
            departure="08:00:00",
            arrival="09:30:00",
            weekdays=(6,),
            effective="2026-09-27",
        )
        create_leg(
            dst_world,
            airline_id=dst_airline,
            aircraft_id=dst_aircraft,
            origin_id=sydney,
            destination_id=island,
            connection_id=inbound_connection,
            departure="11:00:00",
            arrival="12:30:00",
            weekdays=(6,),
            effective="2026-09-27",
        )
        dst_world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 12
        dst_result = publish_configured_window(dst_world)
        self.assertTrue(dst_result.succeeded, dst_result.conflicts)
        dst_departures = sorted(
            flight["scheduled_off_block_utc"]
            for flight in dst_world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == outbound.schedule_id
        )
        self.assertEqual(
            dst_departures,
            ["2026-09-26T21:30:00Z", "2026-10-03T21:00:00Z"],
        )

    def test_pinned_tzdata_is_required_and_host_database_is_never_a_fallback(self):
        self.assertEqual(version("tzdata"), "2026.3")
        load_named_timezone.cache_clear()
        try:
            with patch(
                "game.world_state.timezones.files",
                side_effect=ModuleNotFoundError("tzdata unavailable"),
            ):
                with self.assertRaises(ZoneInfoNotFoundError):
                    load_named_timezone("Etc/UTC")
        finally:
            load_named_timezone.cache_clear()

    def test_historical_zone_gap_and_calendar_boundaries_are_deterministic(self):
        apia_world = create_new_world(
            ceo_display_name="History Tester",
            airline_display_name="History Test",
            starting_airport={"reference_code": "NSFA", "timezone": "Pacific/Apia"},
            difficulty="Normal",
            simulation_time_utc="2011-12-29T00:00:00Z",
            simulation_seed=1,
            starting_money="1000000.00",
        )
        airline, apia = primary_ids(apia_world)
        apia_peer = add_airport_reference(
            apia_world, {"reference_code": "NSFI", "timezone": "Pacific/Apia"}
        )
        aircraft = add_aircraft(apia_world, airline, "5W-HISTORY", "A320", home_airport_id=apia)
        connection = add_market_connection(apia_world, airline, apia, apia_peer)
        skipped = create_leg(
            apia_world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=apia,
            destination_id=apia_peer,
            connection_id=connection,
            departure="10:00:00",
            arrival="12:00:00",
            weekdays=(4,),
            effective="2011-12-30",
        )
        apia_world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 3
        self.assertIn(
            "INVALID_LOCAL_OCCURRENCE",
            {
                conflict.code
                for conflict in validate_schedule_definition(
                    apia_world, skipped.schedule_id
                )
            },
        )

        kathmandu = load_named_timezone("Asia/Kathmandu")
        datetime_module = __import__("datetime")
        old_offset = kathmandu.utcoffset(datetime_module.datetime(1985, 1, 1, 12))
        new_offset = kathmandu.utcoffset(datetime_module.datetime(1987, 1, 1, 12))
        self.assertEqual(int((new_offset - old_offset).total_seconds()), 900)

        for simulation_time, effective, weekday in (
            ("2026-12-30T00:00:00Z", "2026-12-31", 3),
            ("2028-02-28T00:00:00Z", "2028-02-29", 1),
        ):
            with self.subTest(effective=effective):
                calendar_world = create_new_world(
                    ceo_display_name="Calendar Tester",
                    airline_display_name="Calendar Test",
                    starting_airport={"reference_code": f"UTC{weekday}", "timezone": "Etc/UTC"},
                    difficulty="Normal",
                    simulation_time_utc=simulation_time,
                    simulation_seed=weekday,
                    starting_money="1000000.00",
                )
                calendar_airline, origin = primary_ids(calendar_world)
                destination = add_airport_reference(
                    calendar_world,
                    {"reference_code": f"DST{weekday}", "timezone": "Etc/UTC"},
                )
                calendar_aircraft = add_aircraft(
                    calendar_world,
                    calendar_airline,
                    f"CAL-{weekday}",
                    "A320",
                    home_airport_id=origin,
                )
                calendar_connection = add_market_connection(
                    calendar_world, calendar_airline, origin, destination
                )
                create_leg(
                    calendar_world,
                    airline_id=calendar_airline,
                    aircraft_id=calendar_aircraft,
                    origin_id=origin,
                    destination_id=destination,
                    connection_id=calendar_connection,
                    departure="23:30:00",
                    arrival="01:00:00",
                    arrival_day_offset=1,
                    weekdays=(weekday,),
                    effective=effective,
                )
                calendar_world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 2
                result = publish_configured_window(calendar_world)
                self.assertTrue(result.succeeded, result.conflicts)
                flight = next(iter(calendar_world["world_state"]["dated_flights"].values()))
                self.assertEqual(flight["scheduled_departure_local_date"], effective)

    def test_invalid_or_missing_airport_timezones_are_structured_validation_errors(self):
        for timezone_value in (None, "Not/A_Zone", [], "../UTC"):
            with self.subTest(timezone=timezone_value):
                world = make_world()
                airport_id = next(iter(world["world_state"]["airports"]))
                world["world_state"]["airports"][airport_id]["timezone"] = timezone_value
                result = validate_world(world)
                self.assertFalse(result.is_valid)
                self.assertTrue(result.errors)

    def test_publication_boundary_is_inclusive_and_horizon_shrink_does_not_delete(self):
        world, _ids = make_round_trip_world(horizon_days=30)
        before_boundary = publish_occurrences_through(world, "2026-08-23T23:59:59Z")
        self.assertTrue(before_boundary.succeeded)
        self.assertEqual(before_boundary.created_dated_flight_ids, ())
        at_boundary = publish_occurrences_through(world, "2026-08-24T00:00:00Z")
        self.assertEqual(len(at_boundary.created_dated_flight_ids), 1)
        publish_configured_window(world)
        flights_before = deepcopy(world["world_state"]["dated_flights"])
        allocator_before = world["deterministic_state"]["id_allocator"]["next_by_type"]["dated_flight"]

        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 14
        shrunk = publish_configured_window(world)

        self.assertTrue(shrunk.succeeded, shrunk.conflicts)
        self.assertEqual(world["world_state"]["dated_flights"], flights_before)
        self.assertEqual(
            world["deterministic_state"]["id_allocator"]["next_by_type"]["dated_flight"],
            allocator_before,
        )

    def test_allocation_failure_rolls_back_and_retry_matches_clean_world(self):
        world, _ids = make_round_trip_world()
        clean = deepcopy(world)
        before = deepcopy(world)
        calls = 0

        def fail_after_one(candidate, entity_type):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("injected allocation failure")
            return allocate_id(candidate, entity_type)

        with patch("game.scheduling.publication.allocate_id", side_effect=fail_after_one):
            failed = publish_configured_window(world)

        self.assertEqual(failed.status, "REJECTED")
        self.assertEqual(failed.conflicts[0].code, "ID_ALLOCATION_FAILED")
        self.assertEqual(world, before)
        retry = publish_configured_window(world)
        clean_result = publish_configured_window(clean)
        self.assertEqual(retry, clean_result)
        self.assertEqual(world, clean)

    def test_identical_flight_details_from_distinct_schedules_do_not_collide(self):
        world = make_world()
        airline, origin = primary_ids(world)
        destination = add_airport_reference(
            world, {"reference_code": "RPVM", "timezone": "Asia/Manila"}
        )
        connection = add_market_connection(world, airline, origin, destination)
        for number in range(2):
            aircraft = add_aircraft(
                world, airline, f"RP-SAME-{number}", "A320", home_airport_id=origin
            )
            self.assertTrue(
                create_leg(
                    world,
                    airline_id=airline,
                    aircraft_id=aircraft,
                    origin_id=origin,
                    destination_id=destination,
                    connection_id=connection,
                ).succeeded
            )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 7

        result = publish_configured_window(world)
        flights = tuple(world["world_state"]["dated_flights"].values())

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(len(flights), 2)
        self.assertEqual(len({flight["occurrence_key"] for flight in flights}), 2)
        self.assertEqual(len({flight["dated_flight_id"] for flight in flights}), 2)


class Stage1SchedulingConflictTests(unittest.TestCase):
    def _conflict_world(self):
        world = make_world()
        airline_id, origin = primary_ids(world)
        destination = add_airport_reference(
            world, {"reference_code": "RPVM", "timezone": "Asia/Manila"}
        )
        aircraft = add_aircraft(world, airline_id, "RP-CONFLICT", "A320", home_airport_id=origin)
        outbound_connection = add_market_connection(world, airline_id, origin, destination)
        inbound_connection = add_market_connection(world, airline_id, destination, origin)
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 7
        return world, airline_id, origin, destination, aircraft, outbound_connection, inbound_connection

    def test_same_aircraft_overlap_is_rejected_atomically(self):
        world, airline, origin, destination, aircraft, outbound, inbound = self._conflict_world()
        create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound, departure="08:00:00", arrival="10:00:00")
        create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=destination, destination_id=origin, connection_id=inbound, departure="09:00:00", arrival="11:00:00")

        result = publish_configured_window(world)

        self.assertIn("AIRCRAFT_OVERLAP", {item.code for item in result.conflicts})
        self.assertEqual(world["world_state"]["dated_flights"], {})

    def test_insufficient_turnaround_is_rejected(self):
        world, airline, origin, destination, aircraft, outbound, inbound = self._conflict_world()
        create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound, arrival="09:30:00")
        create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=destination, destination_id=origin, connection_id=inbound, departure="09:45:00", arrival="11:00:00")

        result = publish_configured_window(world)

        self.assertIn("INSUFFICIENT_TURNAROUND", {item.code for item in result.conflicts})

    def test_discontinuity_requires_explicit_repositioning_and_never_teleports(self):
        world, airline, origin, destination, aircraft, outbound, _inbound = self._conflict_world()
        third = add_airport_reference(
            world, {"reference_code": "RPMD", "timezone": "Asia/Manila"}
        )
        origin_to_third = add_market_connection(world, airline, origin, third)
        create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound)
        second = create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=third, connection_id=origin_to_third, departure="10:30:00", arrival="12:00:00")

        result = publish_configured_window(world)
        reposition = [item for item in result.conflicts if item.requires_repositioning]

        self.assertTrue(reposition)
        self.assertEqual(reposition[0].actual_airport_id, destination)
        self.assertEqual(reposition[0].required_origin_airport_id, origin)
        self.assertEqual(world["world_state"]["dated_flights"], {})
        self.assertNotEqual(second.schedule_id, "deadhead")

    def test_explicit_deadhead_is_the_only_repositioning_path(self):
        world, airline, origin, destination, aircraft, outbound, _inbound = self._conflict_world()
        create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound, arrival="09:00:00")
        deadhead = create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=destination,
            destination_id=origin,
            connection_id=None,
            departure="10:00:00",
            arrival="11:00:00",
            capacity=0,
            fare_offer={"currency": "USD", "amount_minor": 0},
            service_type="DEADHEAD",
        )

        result = publish_configured_window(world)

        self.assertTrue(deadhead.succeeded)
        self.assertTrue(result.succeeded, result.conflicts)
        record = next(
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == deadhead.schedule_id
        )
        self.assertEqual(record["service_type"], "DEADHEAD")
        self.assertEqual(record["capacity"], 0)

    def test_aircraft_ownership_is_enforced(self):
        world, airline, origin, destination, _aircraft, outbound, _inbound = self._conflict_world()
        other_airline = add_airline(
            world,
            "Other",
            base_airport_id=origin,
            starting_money="1000.00",
        )
        other_aircraft = add_aircraft(world, other_airline, "OTHER-1", "A320", home_airport_id=origin)

        result = create_leg(world, airline_id=airline, aircraft_id=other_aircraft, origin_id=origin, destination_id=destination, connection_id=outbound)

        self.assertFalse(result.succeeded)
        self.assertIn("INVALID_OWNERSHIP", {item.code for item in result.conflicts})

    def test_invalid_entity_references_and_same_endpoints_are_rejected(self):
        world, airline, origin, destination, aircraft, outbound, _inbound = self._conflict_world()
        missing = create_leg(world, airline_id=airline, aircraft_id="aircraft-000000000999", origin_id=origin, destination_id=destination, connection_id=outbound)
        same = create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=origin, connection_id=outbound)

        self.assertIn("DANGLING_REFERENCE", {item.code for item in missing.conflicts})
        self.assertIn("INVALID_SCHEDULE_ENDPOINTS", {item.code for item in same.conflicts})

    def test_departure_must_precede_arrival_in_utc(self):
        world, airline, origin, destination, aircraft, outbound, _inbound = self._conflict_world()
        schedule = create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound, departure="12:00:00", arrival="11:00:00")

        conflicts = validate_schedule_definition(world, schedule.schedule_id)

        self.assertIn("INVALID_LOCAL_OCCURRENCE", {item.code for item in conflicts})

    def test_invalid_capacity_and_fare_offers_are_rejected(self):
        cases = (
            {"capacity": 0},
            {"capacity": True},
            {"fare_offer": {"currency": "USD", "amount_minor": -1}},
            {"fare_offer": {"currency": "PHP", "amount_minor": 100}},
            {"fare_offer": {"currency": "USD", "amount_minor": 1.5}},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                world, airline, origin, destination, aircraft, outbound, _inbound = self._conflict_world()
                result = create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound, **changes)
                self.assertFalse(result.succeeded)

        world, airline, origin, destination, aircraft, _outbound, _inbound = self._conflict_world()
        invalid_deadhead = create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=origin,
            destination_id=destination,
            connection_id=None,
            service_type="DEADHEAD",
            capacity=1,
            fare_offer={"currency": "USD", "amount_minor": 1},
        )
        self.assertIn("INVALID_DEADHEAD_SERVICE", {item.code for item in invalid_deadhead.conflicts})

    def test_turnaround_boundary_accepts_equal_and_above_but_rejects_one_second_below(self):
        for gap, minimum, expected_code in (
            (0, 0, None),
            (1799, 1800, "INSUFFICIENT_TURNAROUND"),
            (1800, 1800, None),
            (1801, 1800, None),
        ):
            with self.subTest(gap=gap, minimum=minimum):
                world, airline, origin, destination, aircraft, outbound, inbound = self._conflict_world()
                world["simulation"]["configuration"]["scheduling"]["minimum_turnaround_seconds"] = minimum
                create_leg(
                    world,
                    airline_id=airline,
                    aircraft_id=aircraft,
                    origin_id=origin,
                    destination_id=destination,
                    connection_id=outbound,
                    arrival="09:30:00",
                )
                second = 9 * 3600 + 30 * 60 + gap
                departure = f"{second // 3600:02d}:{(second % 3600) // 60:02d}:{second % 60:02d}"
                create_leg(
                    world,
                    airline_id=airline,
                    aircraft_id=aircraft,
                    origin_id=destination,
                    destination_id=origin,
                    connection_id=inbound,
                    departure=departure,
                    arrival="12:30:00",
                )

                result = publish_configured_window(world)

                if expected_code:
                    self.assertIn(expected_code, {item.code for item in result.conflicts})
                else:
                    self.assertTrue(result.succeeded, result.conflicts)

    def test_conflict_reporting_order_is_stable_under_dictionary_reordering(self):
        left, airline, origin, destination, aircraft, outbound, inbound = self._conflict_world()
        create_leg(
            left,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=origin,
            destination_id=destination,
            connection_id=outbound,
            arrival="10:00:00",
        )
        create_leg(
            left,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=destination,
            destination_id=origin,
            connection_id=inbound,
            departure="09:00:00",
            arrival="11:00:00",
        )
        right = deepcopy(left)
        schedules = right["world_state"]["schedule_definitions"]
        right["world_state"]["schedule_definitions"] = {
            key: schedules[key] for key in reversed(tuple(schedules))
        }

        left_result = publish_configured_window(left)
        right_result = publish_configured_window(right)

        self.assertEqual(left_result.conflicts, right_result.conflicts)
        self.assertEqual(left, right)

    def test_unknown_aircraft_location_requires_explicit_repositioning(self):
        world, _airline, _origin, _destination, aircraft, _outbound, _inbound = self._conflict_world()
        world["world_state"]["aircraft"][aircraft]["current_airport_id"] = None
        airline, origin = primary_ids(world)
        destination = next(key for key in world["world_state"]["airports"] if key != origin)
        connection = next(iter(world["world_state"]["connections"]))
        create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=origin,
            destination_id=destination,
            connection_id=connection,
        )

        before = deepcopy(world)
        result = publish_configured_window(world)

        self.assertIn("REPOSITIONING_REQUIRED", {item.code for item in result.conflicts})
        self.assertEqual(world, before)

    def test_revision_conflict_with_locked_occurrence_is_atomic(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        locked = next(
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["scheduled_departure_local_date"] == "2026-08-31"
        )
        locked["status"] = "OPERATIONALLY_LOCKED"
        before = deepcopy(world)

        result = revise_future_schedule(
            world,
            ids["inbound"],
            effective_from_local_date="2026-08-31",
            departure_local_time="08:30:00",
            arrival_local_time="10:30:00",
        )

        self.assertIn("AIRCRAFT_OVERLAP", {item.code for item in result.conflicts})
        self.assertEqual(world, before)


class Stage1ScheduleRevisionTests(unittest.TestCase):
    def test_revision_updates_only_future_unlocked_occurrences_in_place(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        flights = world["world_state"]["dated_flights"]
        before = {
            flight["scheduled_departure_local_date"]: flight["dated_flight_id"]
            for flight in flights.values()
            if flight["schedule_id"] == ids["outbound"]
        }

        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            expected_revision=1,
            departure_local_time="08:15:00",
        )

        self.assertTrue(result.succeeded, result.conflicts)
        outbound = {
            flight["scheduled_departure_local_date"]: flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
        }
        self.assertEqual(outbound["2026-08-24"]["schedule_revision"], 1)
        self.assertEqual(outbound["2026-08-31"]["schedule_revision"], 2)
        self.assertEqual(outbound["2026-08-31"]["dated_flight_id"], before["2026-08-31"])
        schedule = world["world_state"]["schedule_definitions"][ids["outbound"]]
        self.assertEqual(schedule["current_revision"], 2)
        self.assertEqual(schedule["revisions"]["1"]["effective_until_local_date"], "2026-08-30")
        self.assertEqual(world["simulation"]["operation_revisions"][ids["outbound"]], 2)

    def test_stale_revision_cannot_republish_superseded_work(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            expected_revision=1,
            departure_local_time="08:15:00",
        )
        before = deepcopy(world)

        stale = publish_configured_window(
            world, expected_schedule_revisions={ids["outbound"]: 1}
        )

        self.assertEqual(stale.status, "STALE_REVISION")
        self.assertEqual(stale.stale_schedule_ids, (ids["outbound"],))
        self.assertEqual(world, before)

    def test_locked_occurrence_is_not_rewritten(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        locked = next(
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["scheduled_departure_local_date"] == "2026-09-07"
        )
        locked["status"] = "OPERATIONALLY_LOCKED"
        before = deepcopy(locked)

        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            departure_local_time="08:15:00",
        )

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(locked, before)
        persisted = world["world_state"]["dated_flights"][before["dated_flight_id"]]
        self.assertEqual(persisted, before)
        self.assertEqual(persisted["schedule_revision"], 1)

    def test_revision_makes_schedule_owned_kernel_work_stale(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        event_id = schedule_event(
            world,
            event_type="NO_OP",
            due_at_utc="2026-08-21T04:30:00Z",
            owner_type="schedule",
            owner_id=ids["outbound"],
            operation_revision=1,
        )
        revised = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            departure_local_time="08:15:00",
        )

        processed = process_next_event(world)

        self.assertTrue(revised.succeeded, revised.conflicts)
        self.assertEqual(processed.skipped_event_ids, (event_id,))
        self.assertEqual(world["world_state"]["event_history"][event_id]["status"], "STALE")

    def test_retired_future_plans_are_explicitly_superseded(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        world["world_state"]["schedule_definitions"][ids["outbound"]]["status"] = "RETIRED"
        world["world_state"]["schedule_definitions"][ids["inbound"]]["status"] = "RETIRED"

        result = publish_configured_window(world)

        self.assertTrue(result.succeeded, result.conflicts)
        superseded = [
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["status"] == "SUPERSEDED"
        ]
        self.assertTrue(superseded)
        self.assertTrue(all(flight["superseded_by_schedule_revision"] == 1 for flight in superseded))
        self.assertFalse(result.created_dated_flight_ids)

    def test_identical_revision_has_explicit_success_and_preserves_occurrence_identity(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        before = {
            flight["scheduled_departure_local_date"]: flight["dated_flight_id"]
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
        }

        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            expected_revision=1,
        )

        self.assertTrue(result.succeeded, result.conflicts)
        revised = {
            flight["scheduled_departure_local_date"]: flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
        }
        self.assertEqual(revised["2026-08-31"]["dated_flight_id"], before["2026-08-31"])
        self.assertEqual(revised["2026-08-31"]["schedule_revision"], 2)
        snapshot = deepcopy(world)
        duplicate_boundary = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
        )
        self.assertEqual(duplicate_boundary.status, "REJECTED")
        self.assertEqual(world, snapshot)

    def test_removed_weekday_supersedes_old_work_and_creates_new_dates(self):
        world, ids = make_round_trip_world(horizon_days=14)
        publish_configured_window(world)
        replacement_aircraft = add_aircraft(
            world,
            ids["airline"],
            "RP-REVISED-DAY",
            "A320",
            home_airport_id=ids["origin"],
        )
        world["world_state"]["schedule_definitions"][ids["inbound"]]["status"] = "RETIRED"

        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            weekdays=[1],
            planned_aircraft_id=replacement_aircraft,
        )

        self.assertTrue(result.succeeded, result.conflicts)
        old_mondays = [
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["scheduled_departure_local_date"] >= "2026-08-31"
            and flight["scheduled_departure_local_date"] == "2026-08-31"
        ]
        self.assertTrue(all(flight["status"] == "SUPERSEDED" for flight in old_mondays))
        self.assertTrue(
            any(
                flight["schedule_id"] == ids["outbound"]
                and flight["scheduled_departure_local_date"] == "2026-09-01"
                and flight["status"] == "PLANNED"
                for flight in world["world_state"]["dated_flights"].values()
            )
        )

    def test_revision_rejects_operation_revision_drift_without_repair(self):
        world, ids = make_round_trip_world()
        world["simulation"]["operation_revisions"][ids["outbound"]] = 0
        before = deepcopy(world)

        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            departure_local_time="08:15:00",
        )

        self.assertEqual(result.status, "REJECTED")
        self.assertIn("INVALID_REVISION", {item.code for item in result.conflicts})
        self.assertEqual(world, before)

    def test_earliest_future_revision_and_publication_boundary_are_explicit(self):
        world, ids = make_round_trip_world()
        for schedule in world["world_state"]["schedule_definitions"].values():
            schedule["revisions"]["1"]["effective_from_local_date"] = "2026-08-17"

        boundary = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-24",
            departure_local_time="08:15:00",
        )

        self.assertTrue(boundary.succeeded, boundary.conflicts)
        first = next(
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["scheduled_departure_local_date"] == "2026-08-24"
        )
        self.assertEqual(first["schedule_revision"], 2)
        self.assertEqual(first["scheduled_off_block_utc"], "2026-08-24T00:15:00Z")

        fresh, fresh_ids = make_round_trip_world()
        earliest = revise_future_schedule(
            fresh,
            fresh_ids["outbound"],
            effective_from_local_date="2026-08-25",
            fare_offer={"currency": "USD", "amount_minor": 7_501},
        )
        self.assertTrue(earliest.succeeded, earliest.conflicts)
        snapshot = deepcopy(fresh)
        retroactive = revise_future_schedule(
            fresh,
            fresh_ids["outbound"],
            effective_from_local_date="2026-08-19",
        )
        self.assertEqual(retroactive.status, "REJECTED")
        self.assertEqual(fresh, snapshot)

    def test_revision_sequence_validation_rejects_gaps_inversions_and_duplicate_numbers(self):
        world, ids = make_round_trip_world()
        schedule = world["world_state"]["schedule_definitions"][ids["outbound"]]
        revision_two = deepcopy(schedule["revisions"]["1"])
        revision_two.update(
            revision=2,
            effective_from_local_date="2026-08-31",
            effective_until_local_date=None,
        )
        schedule["revisions"]["1"]["effective_until_local_date"] = "2026-08-29"
        schedule["revisions"]["2"] = revision_two
        schedule["current_revision"] = 2
        world["simulation"]["operation_revisions"][ids["outbound"]] = 2
        self.assertIn(
            "invalid_revision_sequence", {issue.code for issue in validate_world(world).errors}
        )

        inversion, inversion_ids = make_round_trip_world()
        inverted = inversion["world_state"]["schedule_definitions"][inversion_ids["outbound"]]
        second = deepcopy(inverted["revisions"]["1"])
        second.update(
            revision=1,
            effective_from_local_date="2026-08-20",
            effective_until_local_date=None,
        )
        inverted["revisions"]["1"]["effective_until_local_date"] = "2026-08-19"
        inverted["revisions"]["2"] = second
        inverted["current_revision"] = 2
        inversion["simulation"]["operation_revisions"][inversion_ids["outbound"]] = 2
        codes = {issue.code for issue in validate_world(inversion).errors}
        self.assertIn("invalid_revision", codes)
        self.assertIn("invalid_revision_sequence", codes)

    def test_cross_midnight_revision_updates_both_utc_instants_in_place(self):
        world = make_world()
        airline, mnl = primary_ids(world)
        tokyo = add_airport_reference(
            world, {"reference_code": "RJTT", "timezone": "Asia/Tokyo"}
        )
        aircraft = add_aircraft(world, airline, "RP-REV-NIGHT", "A320", home_airport_id=mnl)
        outbound_connection = add_market_connection(world, airline, mnl, tokyo)
        inbound_connection = add_market_connection(world, airline, tokyo, mnl)
        outbound = create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=mnl,
            destination_id=tokyo,
            connection_id=outbound_connection,
            departure="23:30:00",
            arrival="02:00:00",
            arrival_day_offset=1,
            weekdays=(6,),
            effective="2026-08-23",
        )
        create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=tokyo,
            destination_id=mnl,
            connection_id=inbound_connection,
            departure="03:00:00",
            arrival="06:00:00",
            weekdays=(0,),
            effective="2026-08-24",
        )
        world["simulation"]["configuration"]["scheduling"]["publication_horizon_days"] = 20
        self.assertTrue(publish_configured_window(world).succeeded)
        original = next(
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == outbound.schedule_id
            and flight["scheduled_departure_local_date"] == "2026-08-30"
        )
        original_id = original["dated_flight_id"]

        result = revise_future_schedule(
            world,
            outbound.schedule_id,
            effective_from_local_date="2026-08-30",
            departure_local_time="22:30:00",
            arrival_local_time="01:30:00",
        )
        revised = world["world_state"]["dated_flights"][original_id]

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(revised["scheduled_off_block_utc"], "2026-08-30T14:30:00Z")
        self.assertEqual(revised["scheduled_in_block_utc"], "2026-08-30T16:30:00Z")
        self.assertEqual(revised["schedule_revision"], 2)

    def test_completed_cancelled_and_locked_history_are_never_rewritten(self):
        world, ids = make_round_trip_world(horizon_days=42)
        publish_configured_window(world)
        status_by_date = {
            "2026-08-31": "COMPLETED",
            "2026-09-07": "CANCELLED",
            "2026-09-14": "OPERATIONALLY_LOCKED",
        }
        protected = {}
        for flight in world["world_state"]["dated_flights"].values():
            status = status_by_date.get(flight["scheduled_departure_local_date"])
            if status:
                flight["status"] = status
                protected[flight["dated_flight_id"]] = deepcopy(flight)
        operation_locked = next(
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["scheduled_departure_local_date"] == "2026-09-21"
        )
        world["world_state"]["active_aircraft_operations"][operation_locked["dated_flight_id"]] = {
            "dated_flight_id": operation_locked["dated_flight_id"],
            "aircraft_id": ids["aircraft"],
            "state": "PLANNED",
            "revision": 0,
        }
        protected[operation_locked["dated_flight_id"]] = deepcopy(operation_locked)

        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            fare_offer={"currency": "USD", "amount_minor": 8_000},
        )

        self.assertTrue(result.succeeded, result.conflicts)
        for flight_id, snapshot in protected.items():
            self.assertEqual(world["world_state"]["dated_flights"][flight_id], snapshot)
        mutable = [
            flight
            for flight in world["world_state"]["dated_flights"].values()
            if flight["schedule_id"] == ids["outbound"]
            and flight["scheduled_departure_local_date"] >= "2026-09-28"
        ]
        self.assertTrue(mutable)
        self.assertTrue(all(flight["fare_offer"]["amount_minor"] == 8_000 for flight in mutable))


class Stage1PublicationDeterminismTests(unittest.TestCase):
    def test_indexes_rebuild_deterministically_and_are_not_persisted(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)

        left = rebuild_dated_flight_indexes(world)
        right = rebuild_dated_flight_indexes(deepcopy(world))

        self.assertEqual(left, right)
        self.assertEqual(len(left.by_schedule[ids["outbound"]]), 4)
        self.assertEqual(len(left.by_aircraft[ids["aircraft"]]), 8)
        self.assertEqual(
            len(
                left.direct_services(
                    ids["origin"],
                    ids["destination"],
                    "2026-08-20T04:30:00Z",
                    "2026-09-19T04:30:00Z",
                )
            ),
            4,
        )
        self.assertNotIn("dated_flight_indexes", world["world_state"])

    def test_world_validation_rejects_utc_that_no_longer_matches_local_intent(self):
        world, _ids = make_round_trip_world()
        publish_configured_window(world)
        flight = next(iter(world["world_state"]["dated_flights"].values()))
        flight["scheduled_off_block_utc"] = "2026-08-24T00:00:01Z"

        codes = {issue.code for issue in validate_world(world).errors}

        self.assertIn("inconsistent_schedule_time", codes)

    def test_validation_reports_unhashable_schedule_values_without_crashing(self):
        world, ids = make_round_trip_world()
        cases = (
            ("schedule", "service_type"),
            ("schedule", "passenger_service_classification"),
            ("flight", "status"),
            ("flight", "service_type"),
            ("flight", "passenger_service_classification"),
        )
        publish_configured_window(world)
        for location, field in cases:
            with self.subTest(location=location, field=field):
                malformed = deepcopy(world)
                if location == "schedule":
                    malformed["world_state"]["schedule_definitions"][ids["outbound"]]["revisions"]["1"][field] = []
                else:
                    flight = next(iter(malformed["world_state"]["dated_flights"].values()))
                    flight[field] = []
                result = validate_world(malformed)
                self.assertFalse(result.is_valid)
                self.assertTrue(result.errors)

    def test_malformed_occurrence_identity_trace_and_schema_are_rejected_atomically(self):
        world, _ids = make_round_trip_world()
        publish_configured_window(world)
        flight_id, flight = next(iter(world["world_state"]["dated_flights"].items()))
        mutations = (
            ("invalid_occurrence_key", lambda item: item.update(occurrence_key="bad")),
            ("dangling_revision", lambda item: item.update(schedule_revision=999)),
            ("invalid_timestamp", lambda item: item.update(scheduled_off_block_utc="2026-08-24T00:00:00+00:00")),
            ("unknown_authoritative_field", lambda item: item.update(runtime_index={})),
        )
        for expected, mutate in mutations:
            with self.subTest(expected=expected):
                malformed = deepcopy(world)
                mutate(malformed["world_state"]["dated_flights"][flight_id])
                result = validate_world(malformed)
                self.assertIn(expected, {issue.code for issue in result.errors})
                before = deepcopy(malformed)
                publication = publish_configured_window(malformed)
                self.assertEqual(publication.status, "REJECTED")
                self.assertEqual(malformed, before)

        duplicate = deepcopy(world)
        duplicate_id = allocate_id(duplicate, "dated_flight")
        duplicate_record = deepcopy(flight)
        duplicate_record["dated_flight_id"] = duplicate_id
        duplicate["world_state"]["dated_flights"][duplicate_id] = duplicate_record
        self.assertIn("duplicate_occurrence", {issue.code for issue in validate_world(duplicate).errors})

        derived = deepcopy(world)
        derived["world_state"]["dated_flight_indexes"] = {}
        self.assertIn("unknown_world_root", {issue.code for issue in validate_world(derived).errors})

        equal_times = deepcopy(world)
        equal_flight = equal_times["world_state"]["dated_flights"][flight_id]
        equal_flight["scheduled_in_block_utc"] = equal_flight["scheduled_off_block_utc"]
        self.assertIn(
            "invalid_timestamp_order",
            {issue.code for issue in validate_world(equal_times).errors},
        )

        mixed_keys = deepcopy(world)
        mixed_keys["world_state"]["schedule_definitions"][1] = {}
        mixed_result = validate_world(mixed_keys)
        self.assertFalse(mixed_result.is_valid)
        self.assertTrue(mixed_result.errors)

        overflowing_date = deepcopy(world)
        overflow_flight = overflowing_date["world_state"]["dated_flights"][flight_id]
        overflow_flight["scheduled_departure_local_date"] = "9999-12-31"
        overflow_flight["occurrence_key"] = (
            f"{overflow_flight['schedule_id']}@9999-12-31"
        )
        overflow_schedule = overflowing_date["world_state"]["schedule_definitions"][
            overflow_flight["schedule_id"]
        ]
        overflow_schedule["revisions"]["1"]["recurrence"]["arrival_day_offset"] = 1
        overflow_result = validate_world(overflowing_date)
        self.assertFalse(overflow_result.is_valid)
        self.assertTrue(overflow_result.errors)

    def test_cyclic_and_nonfinite_fares_return_structured_errors_without_aliasing(self):
        for amount in (float("nan"), float("inf"), -1, True, 10**100):
            with self.subTest(amount=amount):
                world, ids = make_round_trip_world()
                before = deepcopy(world)
                result = revise_future_schedule(
                    world,
                    ids["outbound"],
                    effective_from_local_date="2026-08-31",
                    fare_offer={"currency": "USD", "amount_minor": amount},
                )
                if amount == 10**100:
                    self.assertTrue(result.succeeded, result.conflicts)
                else:
                    self.assertEqual(result.status, "REJECTED")
                    self.assertEqual(world, before)

        world, ids = make_round_trip_world()
        cyclic = {"currency": "USD", "amount_minor": 1}
        cyclic["cycle"] = cyclic
        before = deepcopy(world)
        result = revise_future_schedule(
            world,
            ids["outbound"],
            effective_from_local_date="2026-08-31",
            fare_offer=cyclic,
        )
        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(world, before)

    def test_public_schedule_commands_reject_unhashable_ids_without_mutation(self):
        world, ids = make_round_trip_world()
        before = deepcopy(world)

        validation_conflicts = validate_schedule_definition(world, [])
        revision = revise_future_schedule(
            world, [], effective_from_local_date="2026-08-31"
        )
        created = create_schedule_definition(
            world,
            airline_id=[],
            connection_id=None,
            planned_aircraft_id=ids["aircraft"],
            origin_airport_id=ids["origin"],
            destination_airport_id=ids["destination"],
            weekdays=[0],
            departure_local_time="08:00:00",
            arrival_local_time="09:00:00",
            effective_from_local_date="2026-08-24",
            capacity=1,
            fare_offer={"currency": "USD", "amount_minor": 1},
        )

        self.assertEqual(validation_conflicts[0].code, "MISSING_SCHEDULE")
        self.assertEqual(revision.status, "REJECTED")
        self.assertEqual(created.status, "REJECTED")
        self.assertEqual(world, before)

    def test_indexes_treat_statuses_and_ranges_consistently_and_reject_duplicates(self):
        world, ids = make_round_trip_world()
        publish_configured_window(world)
        outbound = sorted(
            (
                flight
                for flight in world["world_state"]["dated_flights"].values()
                if flight["schedule_id"] == ids["outbound"]
            ),
            key=lambda flight: flight["scheduled_off_block_utc"],
        )
        for flight, status in zip(
            outbound,
            ("PLANNED", "OPERATIONALLY_LOCKED", "COMPLETED", "CANCELLED"),
        ):
            flight["status"] = status

        indexes = rebuild_dated_flight_indexes(world)
        all_origin = indexes.departures_from(
            ids["origin"], "2026-08-20T04:30:00Z", "2026-09-19T04:30:00Z"
        )
        active_market = indexes.direct_services(
            ids["origin"],
            ids["destination"],
            "2026-08-20T04:30:00Z",
            "2026-09-19T04:30:00Z",
        )
        self.assertTrue({flight["dated_flight_id"] for flight in outbound}.issubset(all_origin))
        self.assertEqual(active_market, tuple(flight["dated_flight_id"] for flight in outbound[:2]))
        with self.assertRaises(ValueError):
            indexes.departures_from(
                ids["origin"], "2026-09-01T00:00:00Z", "2026-08-01T00:00:00Z"
            )

        duplicate = deepcopy(world)
        duplicate_id = "dated_flight-999999999999"
        duplicate_record = deepcopy(outbound[0])
        duplicate_record["dated_flight_id"] = duplicate_id
        duplicate["world_state"]["dated_flights"][duplicate_id] = duplicate_record
        with self.assertRaisesRegex(ValueError, "duplicate occurrence key"):
            rebuild_dated_flight_indexes(duplicate)

    def test_caller_owned_fare_data_is_detached_from_authority(self):
        world = make_world()
        airline, origin = primary_ids(world)
        destination = add_airport_reference(
            world, {"reference_code": "RPVM", "timezone": "Asia/Manila"}
        )
        aircraft = add_aircraft(world, airline, "RP-ALIAS", "A320", home_airport_id=origin)
        connection = add_market_connection(world, airline, origin, destination)
        fare = {"currency": "USD", "amount_minor": 7_500}
        result = create_leg(
            world,
            airline_id=airline,
            aircraft_id=aircraft,
            origin_id=origin,
            destination_id=destination,
            connection_id=connection,
            fare_offer=fare,
        )
        fare["amount_minor"] = 1

        stored = world["world_state"]["schedule_definitions"][result.schedule_id]["revisions"]["1"]
        self.assertEqual(stored["fare_offer"]["amount_minor"], 7_500)

    def test_dictionary_insertion_order_does_not_change_publication(self):
        left, _ids = make_round_trip_world()
        right = deepcopy(left)
        schedules = right["world_state"]["schedule_definitions"]
        right["world_state"]["schedule_definitions"] = {
            key: schedules[key] for key in reversed(tuple(schedules))
        }

        publish_configured_window(left)
        publish_configured_window(right)

        self.assertEqual(left, right)

    def test_identical_worlds_and_commands_produce_identical_authority(self):
        left, ids = make_round_trip_world()
        right = deepcopy(left)

        left_result = publish_configured_window(left)
        right_result = publish_configured_window(right)

        self.assertEqual(left_result, right_result)
        self.assertEqual(left, right)
        self.assertEqual(
            left["world_state"]["schedule_definitions"][ids["outbound"]],
            right["world_state"]["schedule_definitions"][ids["outbound"]],
        )

    def test_publication_invokes_no_demand_booking_operations_or_legacy_authority(self):
        world, _ids = make_round_trip_world()
        before = {
            "demand": deepcopy(world["world_state"]["demand_state"]),
            "bookings": deepcopy(world["world_state"]["bookings"]),
            "operations": deepcopy(world["world_state"]["active_aircraft_operations"]),
            "events": deepcopy(world["world_state"]["pending_events"]),
            "transactions": deepcopy(world["world_state"]["transactions"]),
        }

        with (
            patch("game.simulation.daily_tick.simulate_airline_day", side_effect=AssertionError("daily tick called")),
            patch("game.scheduling.serializers.inject_schedule_block", side_effect=AssertionError("legacy weekly authority called")),
            patch("game.economy.demand.calculate_adjusted_daily_demand", side_effect=AssertionError("demand called")),
        ):
            result = publish_configured_window(world)

        self.assertTrue(result.succeeded, result.conflicts)
        self.assertEqual(world["world_state"]["demand_state"], before["demand"])
        self.assertEqual(world["world_state"]["bookings"], before["bookings"])
        self.assertEqual(world["world_state"]["active_aircraft_operations"], before["operations"])
        self.assertEqual(world["world_state"]["pending_events"], before["events"])
        self.assertEqual(world["world_state"]["transactions"], before["transactions"])

    def test_repeated_publication_and_extension_have_practical_linear_scale(self):
        world = make_world()
        airline, origin = primary_ids(world)
        destination = add_airport_reference(
            world, {"reference_code": "RPVM", "timezone": "Asia/Manila"}
        )
        outbound = add_market_connection(world, airline, origin, destination)
        inbound = add_market_connection(world, airline, destination, origin)
        for number in range(30):
            aircraft = add_aircraft(
                world,
                airline,
                f"RP-PERF-{number:03d}",
                "A320",
                home_airport_id=origin,
            )
            self.assertTrue(
                create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=origin, destination_id=destination, connection_id=outbound).succeeded
            )
            self.assertTrue(
                create_leg(world, airline_id=airline, aircraft_id=aircraft, origin_id=destination, destination_id=origin, connection_id=inbound, departure="10:30:00", arrival="12:00:00").succeeded
            )

        started = perf_counter()
        first = publish_configured_window(world)
        repeated = publish_configured_window(world)
        extended = extend_publication_window(world, 180)
        elapsed = perf_counter() - started

        self.assertTrue(first.succeeded, first.conflicts)
        self.assertTrue(repeated.succeeded, repeated.conflicts)
        self.assertEqual(repeated.created_dated_flight_ids, ())
        self.assertTrue(extended.succeeded, extended.conflicts)
        self.assertGreaterEqual(len(world["world_state"]["dated_flights"]), 1_500)
        self.assertLess(elapsed, 15.0, f"publication scale scenario took {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
