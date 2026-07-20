from game.game_state import get_active_airline

def add_route_to_airline(game_state, route_id, route_data):
    """
    Adds a new route to the active airline.
    """
    active_airline = get_active_airline(game_state)
    active_airline.setdefault("routes", {})
    active_airline["routes"][route_id] = route_data
    print(f"✅ Route {route_id} added to active airline's routes.")

def classify_demand(pop):
    if pop >= 5_000_000:
        return "High"
    elif pop >= 1_000_000:
        return "Moderate"
    elif pop >= 100_000:
        return "Low"
    else:
        return "None"