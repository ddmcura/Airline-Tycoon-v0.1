# game/aircraft_market/seat_configuration.py

from utils.render import clear_screen, slow_print
from game.utils.registration import generate_registration_number  # Future-proofed for v1.1+

# This function is the full seat and purchase flow (ready for upgrades in v1.1)
def configure_seats(game_state, aircraft):
    clear_screen()
    print("🪑 Configure Seat Layout")
    print("=" * 40)

    default_display_layout = aircraft["full_data"]["default_layout"]
    model = aircraft["model"]
    price = aircraft["full_data"]["purchase_price"]
    capacity = aircraft["full_data"]["capacity"]

    print(f"Default Cabin Layout for {model} (Display Only):")
    print(f"  First Class     : {default_display_layout['first_class']['seats']} seats")
    print(f"  Business Class  : {default_display_layout['business_class']['seats']} seats")
    print(f"  Economy Class   : {default_display_layout['economy']['seats']} seats\n")

    print(f"✈️ Aircraft Cost: ${price:,.0f}\n")

    choice = input("Would you like to configure the seats? (Y/N): ").strip().upper()
    if choice == "Y":
        print("Seat configuration is not yet available. (Coming in v1.1)")
        input("Press Enter to continue with default layout...")

    # ✅ Force full-economy layout for game logic
    assigned_layout = {
        "first_class": { "seat_type": "private_room", "seats": 0 },
        "business_class": { "seat_type": "lie_flat", "seats": 0 },
        "economy": { "seat_type": "standard", "seats": capacity }
    }

    # 🛫 Prompt for hub assignment
    airline = game_state["player_info"]["airline_name"]
    hubs = list(game_state["airline_list"][airline].get("hubs", {}).keys())

    if not hubs:
        print("\n❌ You do not have any hubs to assign this aircraft to.")
        input("Press Enter to return...")
        return

    print("\n📍 Choose a hub to assign these aircraft:")
    for idx, hub_code in enumerate(hubs, 1):
        print(f"[{idx}] {hub_code}")

    while True:
        try:
            hub_choice = int(input("Enter choice: "))
            if 1 <= hub_choice <= len(hubs):
                selected_hub = hubs[hub_choice - 1]
                break
            else:
                print("Invalid hub selection.")
        except ValueError:
            print("Please enter a valid number.")

    seat_summary = (
        f"{assigned_layout['first_class']['seats']}F-"
        f"{assigned_layout['business_class']['seats']}J-"
        f"{assigned_layout['economy']['seats']}Y"
    )

    clear_screen()
    print(f"✅ Layout Selected: {model} - {seat_summary} at hub {selected_hub}\n")

    while True:
        try:
            quantity = int(input("How many would you like to purchase? "))
            if quantity <= 0:
                print("Please enter a valid number.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    total_cost = quantity * price
    airline = game_state["player_info"]["airline_name"]
    finances = game_state["airline_list"][airline].setdefault("finances", {})
    player_money = finances.get("cash_on_hand", 0)

    if total_cost > player_money:
        print("\n❌ You do not have enough funds to complete this purchase.")
        input("Press Enter to return...")
        return

    # Proceed with purchase
    fleet = game_state["airline_list"][airline].setdefault("fleet", {})

    for i in range(quantity):
        reg = generate_registration_number(game_state)
        fleet[reg] = {
            "model": model,
            "layout": assigned_layout,
            "hub": selected_hub,
            "age": 0,
            "status": "active",
            "delivery_status": "delivered"
        }

    finances["cash_on_hand"] = player_money - total_cost


    clear_screen()
    print("✅ Purchase Complete!")
    print(f"Added {quantity} aircraft: {model} - {seat_summary}")
    print(f"Assigned to hub: {selected_hub}")
    print(f"Total Cost: ${total_cost:,.0f}")
    input("\nPress Enter to return to Orville Prime...")
