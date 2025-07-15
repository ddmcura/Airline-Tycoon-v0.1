# game/utils/time_utils.py
from datetime import datetime, timedelta

# 🕒 Return formatted in-game time (HH:MM)
def get_formatted_time(game_state):
    full = game_state['game_time'].get("current_date", "")
    return full.split()[1] if " " in full else "??:??"



# 📆 Advance time by 1 in-game day



def advance_game_day(game_state):
    date_str = game_state['game_time']['current_date']

    # Parse full datetime if time is included, else fallback
    try:
        current_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        current_dt = datetime.strptime(date_str, "%Y-%m-%d")
        current_dt = current_dt.replace(hour=6)  # default to 06:00 if time missing

    new_dt = current_dt + timedelta(days=1)  # You can also add hours if desired

    # Update full datetime string in format YYYY-MM-DD HH:MM
    game_state['game_time']['current_date'] = new_dt.strftime("%Y-%m-%d %H:%M")
