from game.economy.currency import format_money
from game.economy.demand import (
    backfill_route_demand,
    calculate_adjusted_daily_demand,
)
from game.game_state import get_active_airline
from game.utils.render import clear_screen


def _percent(numerator, denominator):
    if not denominator:
        return 0.0
    return numerator / denominator * 100


def show_latest_daily_report(game_state):
    clear_screen()
    airline = get_active_airline(game_state)
    finances = airline.get("finances", {})
    history = finances.get("daily_history", [])
    if not history:
        print("No daily reports yet. Advance a game day first.")
        input("\nPress Enter to return...")
        return

    report = history[-1]
    load_factor = _percent(report.get("passengers", 0), report.get("available_seats", 0))
    print(f"DAILY REPORT - {report.get('date', 'Unknown')}")
    print("=" * 50)
    print(f"Flights operated:      {report.get('flights', 0):,}")
    print(f"Passengers carried:    {report.get('passengers', 0):,}")
    print(f"Available seats:       {report.get('available_seats', 0):,}")
    print(f"Average load factor:   {load_factor:.1f}%")
    print()
    print(f"Passenger revenue:     {format_money(game_state, report.get('revenue', 0))}")
    print(f"Fuel expense:          {format_money(game_state, report.get('fuel_expenses', 0))}")
    print(f"Other operating cost:  {format_money(game_state, report.get('non_fuel_expenses', 0))}")
    print(f"Total expenses:        {format_money(game_state, report.get('expenses', 0))}")
    print(f"Net profit:            {format_money(game_state, report.get('profit', 0))}")
    print(f"Closing cash:          {format_money(game_state, report.get('closing_cash', finances.get('cash_on_hand', 0)))}")
    input("\nPress Enter to return...")


def _select_route(routes):
    route_items = list(routes.items())
    if not route_items:
        return None
    for index, (route_id, route) in enumerate(route_items, 1):
        print(
            f"[{index}] {route_id}: "
            f"{route.get('origin_iata', '---')} -> {route.get('destination_iata', '---')}"
        )
    choice = input("\nSelect route or B to go back: ").strip().lower()
    if choice == "b":
        return None
    if not choice.isdigit() or not 1 <= int(choice) <= len(route_items):
        return "INVALID"
    return route_items[int(choice) - 1]


def show_route_report(game_state):
    airline = get_active_airline(game_state)
    routes = airline.get("routes", {})
    while True:
        clear_screen()
        print("PER-ROUTE REPORT")
        print("=" * 50)
        selected = _select_route(routes)
        if selected is None:
            return
        if selected == "INVALID":
            input("Invalid route. Press Enter to continue...")
            continue

        route_id, route = selected
        backfill_route_demand(route, route_id=route_id)
        stats = route.get("statistics", {})
        available_seats = stats.get("available_seats", 0)
        load_factor = _percent(stats.get("passengers", 0), available_seats)
        difficulty = game_state.get("settings", {}).get("difficulty", "Normal")
        adjusted_demand = calculate_adjusted_daily_demand(route, difficulty)
        pricing = route.get("pricing", {})
        suggested = route.get("suggested_pricing", pricing)

        clear_screen()
        print(f"ROUTE REPORT - {route_id}")
        print("=" * 50)
        print(f"Direction:             {route.get('origin_iata', '---')} -> {route.get('destination_iata', '---')}")
        print(f"Paired route:          {route.get('reverse_route_id', 'None')}")
        print(f"Base daily demand:     {route.get('base_daily_demand', 0):,}")
        print(f"Adjusted daily demand: {adjusted_demand:,}")
        print(f"Suggested economy:     {format_money(game_state, suggested.get('Economy', 0))}")
        print(f"Current economy:       {format_money(game_state, pricing.get('Economy', 0))}")
        print()
        print(f"Flights operated:      {stats.get('flights', 0):,}")
        print(f"Passengers carried:    {stats.get('passengers', 0):,}")
        print(f"Available seats:       {available_seats:,}")
        print(f"Average load factor:   {load_factor:.1f}%")
        print(f"Revenue:               {format_money(game_state, stats.get('revenue', 0))}")
        print(f"Expenses:              {format_money(game_state, stats.get('expenses', 0))}")
        print(f"Net profit:            {format_money(game_state, stats.get('profit', 0))}")
        flights = stats.get("flights", 0)
        profit_per_flight = stats.get("profit", 0) / flights if flights else 0
        print(f"Profit per flight:     {format_money(game_state, profit_per_flight)}")
        input("\nPress Enter to return...")


def enter_financial_reports(game_state):
    while True:
        clear_screen()
        print("FINANCIAL REPORTS")
        print("=" * 40)
        print("[1] Latest Daily Report")
        print("[2] Per-Route Report")
        print("[3] Back")
        choice = input("\nSelect an option: ").strip()
        if choice == "1":
            show_latest_daily_report(game_state)
        elif choice == "2":
            show_route_report(game_state)
        elif choice == "3":
            return
        else:
            input("Invalid option. Press Enter to continue...")
