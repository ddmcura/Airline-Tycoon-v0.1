# game/hub_management/core.py

from game.game_state import get_active_airline

def add_hub_to_airline(game_state, selected_airport, region, iso_code):
    """
    Injects the selected airport as a new hub under the active airline.
    """
    iata = selected_airport["iata"]
    hub_data = {
        **selected_airport,
        "region": region,
        "status": "active",
        "level": 1,
        "connected_routes": [],
        "routes": {},
        "owned": True
    }

    active_airline = get_active_airline(game_state)
    hubs_by_country = active_airline.setdefault("hubs", {})
    country_hubs = hubs_by_country.setdefault(iso_code, {})
    country_hubs[iata] = hub_data

    return hub_data  # Return it for confirmation/use

def get_all_owned_hubs(game_state):
    """
    Returns a dictionary of all hubs owned by the active airline,
    grouped by ISO country code.
    """
    active_airline = get_active_airline(game_state)
    return active_airline.get("hubs", {})

def remove_hub_from_airline(game_state, iso_code, iata_code):
    """
    Removes a hub from the active airline.
    Returns True if removed, False if not found.
    """
    active_airline = get_active_airline(game_state)
    country_hubs = active_airline.get("hubs", {}).get(iso_code.upper(), {})

    if iata_code.upper() in country_hubs:
        del country_hubs[iata_code.upper()]
        return True
    return False
