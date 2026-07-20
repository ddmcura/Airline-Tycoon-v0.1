# game/utils/time_utils.py
from datetime import datetime, timedelta

from game.simulation.daily_tick import simulate_airline_day

# 🕒 Return formatted in-game time (HH:MM)
def get_formatted_time(game_state):
    full = game_state['game_time'].get("current_date", "")
    return full.split()[1] if " " in full else "??:??"



# 📆 Advance time by 1 in-game day



def advance_game_day(game_state, rng=None):
    date_str = game_state['game_time']['current_date']

    try:
        current_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        current_dt = datetime.strptime(date_str, "%Y-%m-%d")
        current_dt = current_dt.replace(hour=6)

    summary = simulate_airline_day(game_state, current_dt, rng=rng)
    new_dt = current_dt + timedelta(days=1)

    game_state['game_time']['current_date'] = new_dt.strftime("%Y-%m-%d %H:%M")
    return summary
