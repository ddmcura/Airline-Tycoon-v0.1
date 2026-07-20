# game/utils/airports.py
import json
import copy
from game.game_state import get_active_airline

def extract_airport_for_game_state(airport_data: dict, region: str) -> dict:
    """
    Extracts and prepares a full airport object from airport_data
    using the template_reference_with_rules.json schema.
    Injects Airline Tycoon-specific fields for game_state.
    """
    # Start with a deep copy of airport_data to avoid modifying original
    hub_data = copy.deepcopy(airport_data)

    # Inject game-specific fields
    hub_data["region"] = region
    hub_data["status"] = "active"            # Default hub status
    hub_data["level"] = 1                     # Default hub level
    hub_data["connected_routes"] = []         # Routes connected to this hub
    hub_data["routes"] = {}                    # Routes originating from this hub

    return hub_data

def add_hub_to_game_state(game_state, airport_data, region, iso_code):
    """
    Extracts airport details and adds a new hub to the active airline
    under the correct ISO country code and IATA structure.
    """
    hub_data = extract_airport_for_game_state(airport_data, region)
    iata = hub_data["iata"]

    active_airline = get_active_airline(game_state)

    # Create nested structure if needed
    active_airline.setdefault("hubs", {})
    active_airline["hubs"].setdefault(iso_code, {})
    active_airline["hubs"][iso_code][iata] = hub_data

    print(f"✅ Hub {iata} added under {iso_code} in active airline.")
    print("🛠️ DEBUG inside add_hub_to_game_state:")
    print(json.dumps(active_airline["hubs"], indent=2))
