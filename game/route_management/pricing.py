from game.economy.currency import format_money
from game.game_state import get_active_airline
from game.utils.render import clear_screen


CABINS = ("Economy", "Business", "First")


def edit_route_prices(game_state):
    airline = get_active_airline(game_state)
    routes = airline.get("routes", {})
    if not routes:
        input("No routes available. Press Enter to return...")
        return

    route_items = list(routes.items())
    clear_screen()
    print("EDIT ROUTE PRICES")
    print("=" * 40)
    for index, (route_id, route) in enumerate(route_items, 1):
        fare = route.get("pricing", {}).get("Economy", 0)
        print(f"[{index}] {route_id} - {format_money(game_state, fare)} Economy")
    choice = input("\nSelect route or B to cancel: ").strip().lower()
    if choice == "b":
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(route_items):
        input("Invalid route. Press Enter to return...")
        return

    route_id, route = route_items[int(choice) - 1]
    pricing = route.setdefault("pricing", {})
    suggested = route.setdefault("suggested_pricing", pricing.copy())
    clear_screen()
    print(f"EDIT PRICES - {route_id}")
    print("Leave a value blank to keep the current fare. Values are entered in USD.\n")
    for cabin in CABINS:
        current = float(pricing.get(cabin, 0))
        recommended = float(suggested.get(cabin, current))
        value = input(
            f"{cabin} [current ${current:,.2f}, suggested ${recommended:,.2f}]: "
        ).strip()
        if not value:
            continue
        try:
            fare = float(value)
            if fare <= 0:
                raise ValueError
        except ValueError:
            input("Invalid fare. No prices were changed further. Press Enter...")
            return
        pricing[cabin] = round(fare, 2)
    input("Route prices updated. Press Enter to return...")
