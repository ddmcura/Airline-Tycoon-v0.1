# game/scheduling/booking_status.py

from game.utils.render import clear_screen

def view_booking_status(game_state):
    clear_screen()
    print("🔍 BOOKING STATUS")
    print("=" * 40)
    print("🚧 This feature is under construction.")
    print("In future versions, this section will show:")
    print("- Load factors per flight")
    print("- Ticket sales & revenue")
    print("- Demand and booking trends")
    print("- Refunds and no-shows (if applicable)")
    print("\nStay tuned for updates in v1.1!")
    input("\nPress Enter to return...")
