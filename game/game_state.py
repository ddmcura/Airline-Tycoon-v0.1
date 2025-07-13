#GAME STATE FILE! root/game/game_state.py
import json
import os

SAVE_FILE_PATH = "Saves/game_state.json"

#MASTER GAME STATE DICTIONARY

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
        "hubs": {

    }
}

game_state = default_game_state()

def reset_game_state():
    global game_state
    game_state = default_game_state()

def save_game(state=None):
    if state is None:
        state = game_state
    os.makedirs(os.path.dirname(SAVE_FILE_PATH), exist_ok=True)
    print("🧠 DEBUG - game_state being saved:")
    print(json.dumps(state, indent=2))
    with open(SAVE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)
    print("Game saved to", SAVE_FILE_PATH)

def load_game():
    global game_state
    reset_game_state()
    
    if os.path.exists(SAVE_FILE_PATH):
        with open(SAVE_FILE_PATH, "r") as f:
            game_state = json.load(f)
        print("Game loaded from", SAVE_FILE_PATH)
    else:
        print("No Save File Found.")
        
def update_game_state(data: dict):
    global game_state
    game_state.update(data)