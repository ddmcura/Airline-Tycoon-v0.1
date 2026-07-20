# game/aircraft_market/core_purchase.py

from game.utils.seating import assign_seat_layout
from game.utils.registration import generate_registration_number
from game.economy.currency import format_money

def purchase_aircraft(game_state, model_name, model_data, selected_hub_iata, quantity):

    """
    Handles the logic of purchasing aircraft and adding them to the game_state.

    Args:
        game_state (dict): The full game state.
        model_data (dict): The selected aircraft's full_data block.
        selected_hub_iata (str): Hub IATA code where the aircraft will be assigned.
        quantity (int): Number of aircraft to purchase.

    Returns:
        tuple: (success (bool), message or summary dict)
    """
    model = model_name
    price = model_data["purchase_price"]
    capacity = model_data["capacity"]
    total_cost = price * quantity

    airline = game_state["player_info"]["airline_name"]
    finances = game_state["airline_list"][airline].setdefault("finances", {})
    current_money = finances.get("cash_on_hand", 0)

    if current_money < total_cost:
        return False, (
            f"Insufficient funds: {format_money(game_state, current_money, 0)} < "
            f"{format_money(game_state, total_cost, 0)}"
        )

    layout = assign_seat_layout(capacity)

    # Inject into aircraft reference if not already present
    aircraft_ref = game_state.setdefault("aircraft_reference", {})
    if model not in aircraft_ref:
        aircraft_ref[model] = model_data.copy()

    fleet = game_state["airline_list"][airline].setdefault("fleet", {})

    for _ in range(quantity):
        reg = generate_registration_number(game_state)
        fleet[reg] = {
            "model": model,
            "layout": layout,
            "hub": selected_hub_iata,
            "age": 0,
            "status": "active",
            "delivery_status": "delivered"
        }

    finances["cash_on_hand"] = current_money - total_cost

    summary = {
        "model": model,
        "layout": layout,
        "quantity": quantity,
        "hub": selected_hub_iata,
        "total_cost": total_cost
    }

    return True, summary
