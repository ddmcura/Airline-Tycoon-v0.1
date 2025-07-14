# GAME STATE FILE! root/game/game_state.py
import json
import os

SAVE_FILE_PATH = "Saves/game_state.json"

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
        "hubs": {}
    }

# 🎮 Active game state in memory
game_state = default_game_state()

# 🔄 Reset to default state
def reset_game_state():
    global game_state
    game_state = default_game_state()

# 💾 Save to file
def save_game(state=None):
    global game_state
    if state is None:
        state = game_state

    print("🧠 LIVE snapshot before saving:")
    print(json.dumps(game_state, indent=2))

    os.makedirs(os.path.dirname(SAVE_FILE_PATH), exist_ok=True)
    
    print("🧠 DEBUG - game_state being saved:")
    print(json.dumps(state, indent=2))

    with open(SAVE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

    print("✅ Game saved to", SAVE_FILE_PATH)

# 📂 Load from file
def load_game():
    global game_state
    reset_game_state()

    if os.path.exists(SAVE_FILE_PATH):
        with open(SAVE_FILE_PATH, "r", encoding="utf-8") as f:
            game_state = json.load(f)
        print("📂 Game loaded from", SAVE_FILE_PATH)
    else:
        print("⚠️ No Save File Found.")

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
    print("🧠 DEBUG - data being passed to update_game_state():")
    print(json.dumps(data, indent=2))
    deep_update(game_state, data)
