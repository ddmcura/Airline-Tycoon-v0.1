from game.game_state import get_active_airline

def adjust_funds(game_state, amount):
    """
    Adjusts the active airline’s cash_on_hand by amount.
    """
    active_airline = get_active_airline(game_state)
    finances = active_airline.setdefault("finances", {})
    finances["cash_on_hand"] = finances.get("cash_on_hand", 0) + amount
    print(f"💵 Funds adjusted by ₱{amount:,.2f}. New balance: ₱{finances['cash_on_hand']:,.2f}")