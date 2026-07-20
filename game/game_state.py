# game/game_state.py
import json
import os
from datetime import datetime
import re

# 🧠 Default state structure (Hybrid Design - Future Proofed for Subsidiaries)
def default_game_state():
    return {
        "player_info": {
            "ceo_name": "",
            "airline_name": "",
            "level": 1,
            "current_focus": ""
        },
        "airline_list": {
            # Example placeholder; actual airline added at game start
            # "Dabudhi Air": {
            #     "hubs": {},
            #     "routes": {},
            #     "fleet": {},
            #     "finances": {"money": 0}
            # }
        },
        "settings": {
            "difficulty": "",
            "starting_money": 0,
            "base_currency": "USD",
            "display_currency": "USD"
        },
        "game_time": {
            "current_date": ""
        }
    }


# 🎮 Active game state in memory
game_state = default_game_state()
# 📁 Track last saved file
last_saved_filename = None

# 🔄 Reset to default state
def reset_game_state():
    global game_state
    display_currency = game_state.get("settings", {}).get(
        "display_currency", "USD"
    )
    game_state = default_game_state()
    game_state["settings"]["display_currency"] = display_currency

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
    safe_ceo = re.sub(r"[^a-zA-Z0-9_-]", "_", ceo_name)
    safe_airline = re.sub(r"[^a-zA-Z0-9_-]", "_", airline_name)
    filename = f"{safe_ceo}_{safe_airline}_{timestamp}.json"
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
def autosave():
    ceo = game_state.get("player_info", {}).get("ceo_name", "unknown_ceo")
    airline = game_state.get("player_info", {}).get("airline_name", "unknown_airline")
    safe_ceo = re.sub(r"[^a-zA-Z0-9_-]", "_", ceo)
    safe_airline = re.sub(r"[^a-zA-Z0-9_-]", "_", airline)
    autosave_dir = "Saves"
    prefix = f"{safe_ceo}_{safe_airline}_autosave_"

    existing_autosaves = sorted([
        f for f in os.listdir(autosave_dir)
        if f.startswith(prefix) and re.match(rf"{re.escape(prefix)}\d{{8}}_\d{{6}}\.json", f)
    ])

    if len(existing_autosaves) >= 5:
        oldest = existing_autosaves[0]
        os.remove(os.path.join(autosave_dir, oldest))
        print(f"🗑️ Deleted oldest autosave: {oldest}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_ceo}_{safe_airline}_autosave_{timestamp}.json"
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

        # 🩹 Check for legacy save (no airline_list)
        if "airline_list" not in loaded_data:
            print("⚠️ Legacy save detected. Converting to hybrid structure...")
            legacy_airline_name = loaded_data.get("player_info", {}).get("airline_name", "Legacy Airline")
            loaded_data = {
                **default_game_state(),
                "player_info": loaded_data.get("player_info", {}),
                "airline_list": {
                    legacy_airline_name: {
                        "hubs": loaded_data.get("hubs", {}),
                        "routes": loaded_data.get("routes", {}),
                        "fleet": loaded_data.get("fleet", {}),
                        "finances": loaded_data.get("finances", {})
                    }
                },
                "settings": loaded_data.get("settings", {}),
                "game_time": loaded_data.get("game_time", {})
            }

        deep_update(game_state, loaded_data)
        last_saved_filename = file_path
        print("📂 Game loaded from", file_path)
    else:
        print("⚠️ No Save File Found at", file_path)

# ✈️ Helper: Get active airline
def get_active_airline(game_state):
    current_focus = game_state["player_info"].get("current_focus", "")
    return game_state["airline_list"].get(current_focus, {})

# ✈️ Helper: Set active airline
def set_active_airline(game_state, airline_name):
    if airline_name in game_state["airline_list"]:
        game_state["player_info"]["current_focus"] = airline_name
        print(f"✅ Active airline switched to: {airline_name}")
    else:
        print(f"❌ Airline '{airline_name}' not found in airline_list.")
