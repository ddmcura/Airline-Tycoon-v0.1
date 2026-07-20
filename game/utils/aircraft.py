from game.game_state import get_active_airline

def add_aircraft_to_fleet(game_state, aircraft_data):
    """
    Adds a new aircraft to the active airline’s fleet.
    """
    reg_no = aircraft_data.get("reg_no")
    active_airline = get_active_airline(game_state)
    active_airline.setdefault("fleet", {})
    active_airline["fleet"][reg_no] = aircraft_data
    print(f"✅ Aircraft {reg_no} added to active airline's fleet.")