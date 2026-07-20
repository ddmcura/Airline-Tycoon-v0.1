# game/fleet_management/core.py

from game.game_state import get_active_airline

def get_aircraft_by_reg(game_state, reg_no):
    """
    Returns aircraft object from fleet by registration number.
    Returns None if not found.
    """
    active_airline = get_active_airline(game_state)
    return active_airline.get("fleet", {}).get(reg_no)

def remove_aircraft_by_reg(game_state, reg_no):
    """
    Safely removes aircraft from fleet.
    """
    active_airline = get_active_airline(game_state)
    if reg_no in active_airline.get("fleet", {}):
        del active_airline["fleet"][reg_no]
        return True
    return False
