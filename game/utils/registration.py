# game/utils/registration.py
import random

def generate_registration_number(game_state):
    """
    Optimized: Caches all available RP-C#### numbers, picks randomly.
    Ensures uniqueness without looping retries.
    """
    airline = game_state["player_info"]["airline_name"]
    fleet = game_state["airline_list"][airline].get("fleet", {})

    used = set()
    for reg in fleet.keys():
        if reg.startswith("RP-C"):
            try:
                used.add(int(reg.replace("RP-C", "")))
            except ValueError:
                continue

    all_numbers = set(range(1, 10_000))
    available = list(all_numbers - used)

    if not available:
        raise ValueError("⚠️ No registration numbers left.")

    chosen = random.choice(available)
    return f"RP-C{str(chosen).zfill(4)}"

def is_valid_registration(game_state, registration):
    """
    Checks if the given registration is already in use.
    Returns True if valid (not used), False if already exists.
    """
    airline = game_state["player_info"]["airline_name"]
    fleet = game_state["airline_list"][airline].get("fleet", {})
    return registration not in fleet
