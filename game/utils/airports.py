# Airports Module (game/utils/airports.py)
import json


def extract_airport_for_game_state(airport_data: dict, region: str, country: str) -> dict:
    return {
        "iata": airport_data.get("iata", ""),
        "icao": airport_data.get("icao", ""),
        "name": airport_data.get("name", ""),
        "city": airport_data.get("city", ""),
        "country": country,
        "region": region,
        "timezone": airport_data.get("timezone", ""),
        "coordinates": {
            "lat": airport_data.get("coordinates", {}).get("lat", 0.0),
            "lon": airport_data.get("coordinates", {}).get("lon", 0.0)
        },
        "airport_class": airport_data.get("airport_class", ""),
        "airport_size": airport_data.get("airport_size", ""),
        "runway_length": airport_data.get("runway_length_m", 0),
        "runways": airport_data.get("runways", 0),
        "runway_names": airport_data.get("runway_names", []),
        "total_pax_stands": airport_data.get("total_pax_stands", 0),
        "total_cargo_stands": airport_data.get("total_cargo_stands", 0),
        "number_of_terminals_pax": airport_data.get("number_of_terminals_pax", 0),
        "number_of_terminals_cargo": airport_data.get("number_of_terminals_cargo", 0),
        "has_cargo_terminal": airport_data.get("has_cargo_terminal", False),
        "max_aircraft_class": airport_data.get("max_aircraft_class", ""),
        "slots": airport_data.get("slots", 0),
        "avg_taxi_time_min": airport_data.get("avg_taxi_time_min", 0),
        "population": airport_data.get("population", 0),
        "cargo_volume_tonnes": airport_data.get("cargo_volume_tonnes", 0),
        "date_opened": airport_data.get("date_opened", ""),
        "fees": airport_data.get("fees", {}),
        "status": "active",   # custom game logic
        "level": 1,           # game mechanic: level up airport?
        "connected_routes": [],  # route tracking
        "routes": {}             # route data
    }

def add_hub_to_game_state(game_state, airport_data, region, country):
    """
    Extracts and adds a new hub to the game_state dictionary
    under the correct country and IATA structure.
    
    Args:
        airport_data (dict): Raw airport dictionary from .json file
        region (str): The region (e.g., 'Asia', 'Europe')
        country (str): The country name (e.g., 'Philippines')
    """
    # Extract the formatted airport data using the extractor
    hub_data = extract_airport_for_game_state(airport_data, region, country)
    iata = hub_data["iata"]

    # Ensure the nested structure exists
    game_state.setdefault("hubs", {})
    game_state["hubs"].setdefault(country, {})

    # Insert the hub
    game_state["hubs"][country][iata] = hub_data

    print(f"✅ Hub {iata} added under {country} in game_state.")
    print("🛠️ DEBUG inside add_hub_to_game_state:")
    print(json.dumps(game_state["hubs"], indent=2))


