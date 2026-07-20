from game.utils.render import clear_screen, slow_print
from game.utils.ui import paginate
from game.game_state import get_active_airline
from game.economy.demand import backfill_route_demand
from game.utils.airport_lookup import load_airport_index
import math

from game.scheduling.helpers import time_to_minutes, minutes_to_time, get_primary_route_id
from game.scheduling.validators import has_conflict, validate_aircraft_continuity
from game.scheduling.suggest import next_available_after, suggest_next_available
from game.scheduling.planning import format_direction_metrics, route_demand_metrics
from game.scheduling.deadhead import aircraft_position_before, plan_deadhead
from game.scheduling.render import render_aircraft_table, render_route_table, render_schedule_summary
from game.scheduling.render_planning import render_route_planning_table
from game.scheduling.serializers import inject_schedule_block, inject_round_trip_if_possible


def start_scheduling(game_state):
    clear_screen()
    print("🛠 START SCHEDULING")
    print("=" * 50)

    active_airline = get_active_airline(game_state)
    fleet = active_airline.get("fleet", {})
    routes = active_airline.get("routes", {})

    if not fleet:
        print("❌ You do not have any aircraft.")
        input("Press Enter to return...")
        return

    aircraft_list = [
        {"reg": reg, "model": ac.get("model", "Unknown"), "hub": ac.get("hub", "Unknown")} for reg, ac in fleet.items()
    ]

    selected_ac = paginate(aircraft_list, page_size=7, render_func=lambda page: render_aircraft_table(page, fleet))
    if selected_ac in ["BACK", "CANCEL"]:
        return

    reg_no = selected_ac["reg"]
    aircraft = fleet[reg_no]
    aircraft_hub = aircraft.get("hub")
    model_id = aircraft["model"]
    aircraft_ref = game_state.get("aircraft_reference", {})
    specs = aircraft_ref.get(model_id, {})
    cruise_speed = specs.get("cruise_speed_kph", 800)

    while True:
        clear_screen()
        print(f"📍 Scheduling for Aircraft: {reg_no} ({aircraft['model']})")
        print(f"Assigned Hub: {aircraft_hub}\n")

        network_routes = []
        for rid, route in routes.items():
            backfill_route_demand(route, route_id=rid)

        demand_metrics = route_demand_metrics(game_state, routes)
        seen_pairs = set()
        for rid, route in routes.items():
            origin_iata = route.get("origin_iata")
            destination_iata = route.get("destination_iata")
            dist = route.get("distance_km", 0)
            if not origin_iata or not destination_iata or dist <= 0:
                continue
            pair_id = route.get("route_pair_id") or "-".join(
                sorted((origin_iata, destination_iata))
            )
            if pair_id in seen_pairs:
                continue
            seen_pairs.add(pair_id)
            reverse_id = route.get(
                "reverse_route_id", f"{destination_iata}-{origin_iata}"
            )
            raw_minutes = (dist / cruise_speed) * 60
            flight_minutes = int(math.ceil(raw_minutes / 5) * 5)
            block_minutes = flight_minutes + 30
            network_routes.append({
                "id": rid,
                "label": f"{origin_iata} <-> {destination_iata}",
                "from": origin_iata,
                "to": destination_iata,
                "duration": flight_minutes,
                "block_minutes": block_minutes,
                "demand_summary": "\n".join((
                    format_direction_metrics(rid, demand_metrics),
                    format_direction_metrics(reverse_id, demand_metrics),
                )),
            })

        selected_route = paginate(
            network_routes, page_size=7, render_func=render_route_planning_table
        )
        if selected_route in ["BACK", "CANCEL"]:
            return

        route_id = selected_route["id"]
        flight_minutes = selected_route["duration"]
        block_minutes = selected_route["block_minutes"]
        origin, dest = selected_route["from"], selected_route["to"]

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        aircraft_schedule = aircraft.setdefault("schedule", {})
        for day in days:
            aircraft_schedule.setdefault(day, {}).setdefault(route_id, [])

        schedule_by_day = {}
        for day in days:
            schedule_by_day[day] = []
            for route_flights in aircraft_schedule[day].values():
                schedule_by_day[day].extend(route_flights)

        suggestion = suggest_next_available(
            schedule_by_day["Mon"], block_minutes
        )
        if suggestion != "No available slot":
            print(f"💡 Suggested next available time: {suggestion}")
        else:
            print("⚠️ No available slot found this week without overlap.")

        while True:
            print(f"\n🕑 Input start time for flight {route_id} (HH:MM):")
            start_time = input("> ").strip()
            try:
                new_start = time_to_minutes(start_time)
                new_end = new_start + block_minutes
                break
            except:
                print("❌ Invalid format. Try HH:MM (24-hour)")

        conflicting_days = [
            day
            for day in days
            if has_conflict(schedule_by_day[day], new_start, new_end)
        ]
        if conflicting_days:
            alternatives = [
                next_available_after(schedule_by_day[day], new_start, block_minutes)
                for day in conflicting_days
            ]
            alternatives = [value for value in alternatives if value is not None]
            if not alternatives:
                print("This flight conflicts and no later opening fits today.")
                input("Press Enter to try again...")
                continue
            proposed_start = max(alternatives)
            proposed_time = minutes_to_time(proposed_start)
            print(
                "This flight interferes with the current planned schedule. "
                f"The next available time is {proposed_time}."
            )
            accept = input(f"Schedule it at {proposed_time}? (Y/N): ").strip().lower()
            if accept != "y":
                continue
            start_time = proposed_time
            new_start = proposed_start
            new_end = new_start + block_minutes

        if any(
            has_conflict(schedule_by_day[day], new_start, new_end) for day in days
        ):
            print("❌ Conflict detected with existing schedule. Try a different time.")
            input("Press Enter to try again...")
            continue

        is_one_way = input("Is this a one-way flight? (Y/N): ").strip().lower() == "y"
        is_round = not is_one_way

        reverse_route_id, _ = get_primary_route_id(routes, dest, origin)
        reverse_exists = reverse_route_id is not None

        scheduled_locations = {
            aircraft_position_before(
                schedule_by_day[day], new_start, aircraft_hub
            )[0]
            for day in days
        }
        current_location = next(iter(scheduled_locations))
        direction_inferred = len(scheduled_locations) == 1
        if direction_inferred and current_location == dest and reverse_exists:
            route_id = reverse_route_id
            origin, dest = dest, origin

        if is_one_way and current_location not in (origin, dest):
            print("\n🛫 Choose direction:")
            print(f"[1] {origin} → {dest}")
            print(f"[2] {dest} → {origin}")
            direction_choice = input("Enter choice [1/2]: ").strip()

            if direction_choice == "2":
                if not reverse_exists:
                    print(f"⚠️ Route {dest}-{origin} not found. Cannot proceed.")
                    input("Press Enter to try a different route...")
                    continue
                # Flip everything
                route_id = reverse_route_id
                origin, dest = dest, origin

        airport_index = load_airport_index()
        deadhead_plans = {}
        for day in days:
            plan = plan_deadhead(
                schedule_by_day[day],
                new_start,
                origin,
                aircraft_hub,
                cruise_speed,
                airport_index,
                specs.get("range_km"),
            )
            if plan:
                deadhead_plans[day] = plan

        errors = [
            plan["error"] for plan in deadhead_plans.values() if plan.get("error")
        ]
        if errors:
            print(f"Cannot position aircraft: {errors[0]}")
            input("Press Enter to try again...")
            continue

        if deadhead_plans:
            passenger_start = max(
                plan["passenger_start"] for plan in deadhead_plans.values()
            )
            example = next(iter(deadhead_plans.values()))
            deadhead_start = minutes_to_time(example["start"])
            deadhead_end = minutes_to_time(example["end"])
            passenger_time = minutes_to_time(passenger_start)
            print("\nWARNING: Aircraft positioning required.")
            print(
                f"The aircraft is not at {origin}. A deadhead flight "
                f"{example['origin']} -> {example['destination']} will be scheduled "
                f"from {deadhead_start} to {deadhead_end}."
            )
            print("This positioning flight carries no passengers and earns no revenue.")
            print(f"The passenger service will depart at {passenger_time}.")
            confirm_deadhead = input(
                "Schedule the deadhead and passenger flight? (Y/N): "
            ).strip().lower()
            if confirm_deadhead != "y":
                continue

            new_start = passenger_start
            start_time = passenger_time
            new_end = new_start + block_minutes

            deadhead_conflict = False
            for day, plan in deadhead_plans.items():
                if has_conflict(
                    schedule_by_day[day], plan["start"], plan["end"]
                ):
                    print(f"Cannot schedule {day}: deadhead conflicts with a flight.")
                    deadhead_conflict = True
                    break
            if deadhead_conflict:
                input("Press Enter to try again...")
                continue

        operation_end = new_start + block_minutes
        final_destination = dest
        if is_round:
            operation_end += flight_minutes + 30
            final_destination = origin

        schedule_valid = True
        for day in days:
            validation_schedule = list(schedule_by_day[day])
            plan = deadhead_plans.get(day)
            if plan:
                validation_schedule.append({
                    "start_time": minutes_to_time(plan["start"]),
                    "end_time": minutes_to_time(plan["end"]),
                    "start_airport": plan["origin"],
                    "end_airport": plan["destination"],
                    "service_type": "deadhead",
                })
            if has_conflict(schedule_by_day[day], new_start, operation_end):
                print(f"Cannot schedule {day}: conflicts with an existing flight.")
                schedule_valid = False
                break

            valid, reason = validate_aircraft_continuity(
                validation_schedule,
                new_start,
                operation_end,
                origin,
                final_destination,
                aircraft_hub,
            )
            if not valid:
                print(f"Cannot schedule {day}: {reason}")
                schedule_valid = False
                break

        if not schedule_valid:
            input("Press Enter to try again...")
            continue


        for day in days:
            plan = deadhead_plans.get(day)
            if plan:
                inject_schedule_block(
                    game_state,
                    reg_no,
                    day,
                    plan["route_id"],
                    minutes_to_time(plan["start"]),
                    plan["origin"],
                    minutes_to_time(plan["end"]),
                    plan["destination"],
                    service_type="deadhead",
                )

            # Calculate end_time based on start + flight_minutes
            start_min = time_to_minutes(start_time)
            end_min = start_min + flight_minutes
            end_time = minutes_to_time(end_min)

            inject_schedule_block(
                game_state,
                reg_no,
                day,
                route_id,
                start_time,
                origin,
                end_time,
                dest
            )

            if is_round and reverse_exists:
                original_block = {
                    "start_time": start_time,
                    "start_airport": origin,
                    "end_time": end_time,
                    "end_airport": dest
                }
                inject_round_trip_if_possible(game_state, reg_no, day, original_block, flight_minutes)

        again = input("\nAdd another time for this route? (Y/N): ").strip().lower()
        if again != "y":
            more = input("Schedule another route? (Y/N): ").strip().lower()
            if more != "y":
                break

    clear_screen()
    print(f"✅ Schedule for {reg_no} ({aircraft['model']})")
    print("=" * 50)
    print(render_schedule_summary(aircraft.get("schedule", {})))
    input("\nPress Enter to return to Schedule Menu...")
