# game/aircraft_market/seat_configuration.py

from utils.render import clear_screen
from tabulate import tabulate
import time

def configure_seats(game_state, aircraft_data):
    clear_screen()
    model = aircraft_data["model"]
    layout = aircraft_data["full_data"].get("default_layout", {})
    layout_price = aircraft_data["full_data"].get("default_layout_price", 0)
    purchase_price = aircraft_data["full_data"].get("purchase_price", aircraft_data["base_price"])

    print(f"✈️  Seat Configuration for {model}\n")
    print("🪑 Default Cabin Layout:")

    rows = []
    for cabin, details in layout.items():
        rows.append([
            cabin.replace("_", " ").title(),
            details.get("seat_type", "Standard"),
            details.get("seats", 0)
        ])

    print(tabulate(rows, headers=["Cabin", "Seat Type", "Seats"], tablefmt="fancy_grid"))

    print(f"\n💰 Layout Cost: ₱{layout_price:,.0f}")
    print(f"🛒 Aircraft Price: ₱{purchase_price:,.0f}")
    print(f"💵 Total Order: ₱{purchase_price + layout_price:,.0f}\n")

    choice = input("Confirm order with this layout? (y/n): ").strip().lower()
    if choice == "y":
        register_order(game_state, aircraft_data)
        print("✅ Order placed! You’ll receive your plane in a few days.")
        input("Press Enter to continue...")
    else:
        print("❌ Order canceled.")
        input("Press Enter to return...")

def register_order(game_state, aircraft_data):
    """Adds the aircraft to a 'pending_orders' list with a delivery ETA."""
    pending_orders = game_state.setdefault("pending_orders", [])
    delivery_days = 3  # Can scale later by aircraft size, etc.

    order = {
        "model": aircraft_data["model"],
        "family": aircraft_data["family"],
        "manufacturer": aircraft_data["full_data"]["manufacturer"],
        "price_paid": aircraft_data["full_data"].get("purchase_price", aircraft_data["base_price"]),
        "layout_price": aircraft_data["full_data"].get("default_layout_price", 0),
        "order_date": game_state["game_time"]["current_date"],
        "delivery_days_remaining": delivery_days,
        "layout": aircraft_data["full_data"].get("default_layout", {})
    }

    pending_orders.append(order)
