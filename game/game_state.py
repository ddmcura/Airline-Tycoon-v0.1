# game/game_state.py
import json
import os
from datetime import datetime
import re

# 🧠 Default state structure
def default_game_state():
    return {
        "player_info": {
            "ceo_name": "",
            "airline_name": ""
        },
        "settings": {
            "difficulty": "",
            "starting_money": 0
        },
        "finances": {
            "cash_on_hand": 0,
            "debt": 0
        },
        "game_time": {
            "current_date": ""
        },
        "hubs": {}
    }

# 🎮 Active game state in memory
game_state = default_game_state()
# 📁 Track last saved file
last_saved_filename = None

# 🔄 Reset to default state
def reset_game_state():
    global game_state
    game_state = default_game_state()

# 🔧 Recursive merge of nested dicts
def deep_update(source, overrides):
    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and key in source
            and isinstance(source[key], dict)
        ):
            deep_update(source[key], value)
        else:
            source[key] = value

# 🛠️ Update memory state
def update_game_state(data: dict):
    global game_state
    print("\n🧠 DEBUG - data being passed to update_game_state():")
    print(json.dumps(data, indent=2))
    deep_update(game_state, data)

# 📁 File path generator
def get_save_file_path(ceo_name, airline_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ceo_name}_{airline_name}_{timestamp}.json".replace(" ", "_")
    return os.path.join("Saves", filename)

# 💾 Save game (new or overwrite)
def save_game(state=None, filename=None, is_new=False):
    global game_state, last_saved_filename
    if state is None:
        state = game_state

    if is_new or not filename:
        ceo = state["player_info"].get("ceo_name", "unknown_ceo")
        airline = state["player_info"].get("airline_name", "unknown_airline")
        filename = get_save_file_path(ceo, airline)

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    print("🧠 DEBUG - Saving to:", filename)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)
    print("✅ Game saved to", filename)

    last_saved_filename = filename

# 💾 Autosave using current CEO/Airline (limit 5)
import re  # Make sure this is at the top of your file if not already imported

def autosave():
    ceo = game_state.get("player_info", {}).get("ceo_name", "unknown_ceo")
    airline = game_state.get("player_info", {}).get("airline_name", "unknown_airline")
    autosave_dir = "Saves"
    prefix = f"{ceo}_{airline}_autosave_"

    # Filter autosaves for this ceo/airline
    existing_autosaves = sorted([
        f for f in os.listdir(autosave_dir)
        if f.startswith(prefix) and re.match(rf"{re.escape(prefix)}\d{{8}}_\d{{6}}\.json", f)
    ])

    # Delete oldest if more than 4 exist (we want to keep last 4, and this one will be the 5th)
    if len(existing_autosaves) >= 5:
        oldest = existing_autosaves[0]
        os.remove(os.path.join(autosave_dir, oldest))
        print(f"🗑️ Deleted oldest autosave: {oldest}")

    # New autosave file path with consistent naming
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ceo}_{airline}_autosave_{timestamp}.json".replace(" ", "_")
    autosave_path = os.path.join(autosave_dir, filename)

    os.makedirs(os.path.dirname(autosave_path), exist_ok=True)
    with open(autosave_path, "w", encoding="utf-8") as f:
        json.dump(game_state, f, indent=4)

    print(f"✅ Autosave complete → {autosave_path}")


# 📂 Load from file
def load_game(filename):
    global game_state, last_saved_filename
    reset_game_state()

    file_path = os.path.join("Saves", filename)

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        deep_update(game_state, loaded_data)
        last_saved_filename = file_path
        print("📂 Game loaded from", file_path)
    else:
        print("⚠️ No Save File Found at", file_path)
