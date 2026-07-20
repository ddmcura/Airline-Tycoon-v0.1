# game/scheduling/main.py

from game.utils.render import clear_screen, slow_print
from game.scheduling.core import start_scheduling
from game.scheduling.view_flights import view_scheduled_flights
from game.scheduling.booking_status import view_booking_status



def enter_schedule_management(game_state):
    while True:
        clear_screen()
        print("📅 SCHEDULE MANAGEMENT")
        print("=" * 40)
        print("[1] 🛠 Start Scheduling")
        print("[2] 📋 View Scheduled Flights")
        print("[3] 🔍 View Booking Status (Coming Soon)")
        print("[0] ⬅️ Return to Dashboard")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            start_scheduling(game_state)
        elif choice == "2":
            view_scheduled_flights(game_state)
        elif choice == "3":
            view_booking_status(game_state)
        elif choice == "0":
            break
        else:
            print("\n❌ Invalid input. Please try again.")
            input("Press Enter to continue...")
