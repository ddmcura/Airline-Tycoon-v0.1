"""Legacy hybrid-state cleanup; not an authoritative save migration."""

def legacy_cleanup(game_state):
    """LEGACY: remove obsolete hybrid roots before the current CLI starts."""
    # Remove old top-level keys that no longer belong in the hybrid structure
    for key in ["hubs", "fleet", "routes", "finances"]:
        if key in game_state:
            print(f"🗑️ Removing legacy key: {key}")
            del game_state[key]
