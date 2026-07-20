from game.scheduling.helpers import time_to_minutes, minutes_to_time


def inject_schedule_block(
    game_state,
    reg_no,
    day,
    route_id,
    start_time,
    origin,
    end_time,
    dest,
    service_type="passenger",
):
    airline = game_state["airline_list"][game_state["player_info"]["current_focus"]]
    if service_type != "deadhead":
        route_schedule = airline["routes"].setdefault(route_id, {}).setdefault("schedule", {})
        day_schedule = route_schedule.setdefault(day, {})
        ac_schedule = day_schedule.setdefault(reg_no, {})
        segment_id = f"{origin}-{dest}"
        ac_schedule.setdefault(segment_id, []).append({
            "start_time": start_time,
            "end_time": end_time,
        })

    # Also inject to aircraft side
    aircraft = airline["fleet"][reg_no]
    ac_day_sched = aircraft.setdefault("schedule", {}).setdefault(day, {})
    route_block = ac_day_sched.setdefault(route_id, [])
    route_block.append({
        "start_time": start_time,
        "start_airport": origin,
        "end_time": end_time,
        "end_airport": dest,
        "service_type": service_type,
    })


def inject_round_trip_if_possible(game_state, reg_no, day, original_block, flight_minutes):
    origin = original_block["start_airport"]
    dest = original_block["end_airport"]
    end_time = original_block["end_time"]

    turnaround = 30
    return_start_min = time_to_minutes(end_time) + turnaround
    return_end_min = return_start_min + flight_minutes

    return_block = {
        "aircraft_id": reg_no,
        "start_time": minutes_to_time(return_start_min),
        "start_airport": dest,
        "end_time": minutes_to_time(return_end_min),
        "end_airport": origin
    }

    reverse_route_id = f"{dest}-{origin}"
    inject_schedule_block(
        game_state,
        reg_no,
        day,
        reverse_route_id,
        return_block["start_time"],
        return_block["start_airport"],
        return_block["end_time"],
        return_block["end_airport"]
    )
