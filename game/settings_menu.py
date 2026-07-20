from game.economy.currency import (
    available_currencies,
    format_money,
    get_display_currency,
    set_display_currency,
)
from game.utils.render import clear_screen


def enter_settings_menu(game_state):
    while True:
        clear_screen()
        current = get_display_currency(game_state)
        print("SETTINGS")
        print("=" * 40)
        print("Internal accounting currency: USD")
        print(f"Display currency: {current}")
        print(f"Example balance: {format_money(game_state, 1000)}")
        print("\n[1] Change Display Currency")
        print("[2] Back")
        choice = input("\nSelect an option: ").strip()

        if choice == "2":
            return
        if choice != "1":
            input("Invalid option. Press Enter to continue...")
            continue

        currencies = available_currencies()
        print()
        for index, currency in enumerate(currencies, 1):
            print(f"[{index}] {currency}")
        selected = input("Select display currency: ").strip()
        if not selected.isdigit() or not 1 <= int(selected) <= len(currencies):
            input("Invalid currency. Press Enter to continue...")
            continue
        set_display_currency(game_state, currencies[int(selected) - 1])
        input("Display currency updated. Press Enter to continue...")
