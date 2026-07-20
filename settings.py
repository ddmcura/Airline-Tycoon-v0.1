from tabulate import tabulate
from datetime import datetime

DEV_MODE = True

def set_difficulty():
    print("\n🎯 Game Setup Parameters\n")
    print("Select your starting difficulty:")

    difficulty_table = [
        [1, "Easy",    "₱500,000,000", "High demand\nCheap expenses"],
        [2, "Normal",  "₱300,000,000", "Normal demand\nNormal expenses"],
        [3, "Hard",    "₱100,000,000", "Lower demand\nHigher expenses"],
        [4, "Extreme", "None", "Very low demand\nVery high expenses\n+ ₱300M Outstanding Loan 💀"],
        [5, "Sandbox", "Unlimited 💸", "Coming soon..."]
    ]
    for row in difficulty_table:
        row[2] = str(row[2]).replace("\u20b1", "$")
        row[3] = str(row[3]).replace("\u20b1", "$").replace("\U0001f480", "")


    print(tabulate(difficulty_table, headers=["#", "Difficulty", "Starting Money", "Conditions"], tablefmt="fancy_grid"))

    choices = {
        "1": ("Easy", 500_000_000, 0),
        "2": ("Normal", 300_000_000, 0),
        "3": ("Hard", 100_000_000, 0),
        "4": ("Extreme", 0, 300_000_000)
    }

    choice = ""
    while choice not in choices:
        choice = input("Enter your choice (1-4): ").strip()
        if choice == "5":
            print("\n🧪 Sandbox mode is not available yet — stay tuned!\n")

    difficulty, initial_money, debt = choices[choice]

    return initial_money, difficulty, debt

def set_starting_date():
    default = datetime.now().strftime("%m-%d-%Y")  # 👈 Format: MM-DD-YYYY
    while True:
        user_input = input(f"Enter your starting date (MM-DD-YYYY) [default: {default}]: ").strip()
        if not user_input:
            return datetime.now().strftime("%Y-%m-%d")  # 👈 Internally store as YYYY-MM-DD

        try:
            parsed_date = datetime.strptime(user_input, "%m-%d-%Y")
            return parsed_date.strftime("%Y-%m-%d")  # 👈 Convert to standard ISO format
        except ValueError:
            print("❌ Invalid format. Please use MM-DD-YYYY.")
