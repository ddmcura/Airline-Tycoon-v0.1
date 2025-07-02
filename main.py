#Main menu

def show_main_menu():
    print("Welcome to Airline Tycoon")
    print("1. New Game")
    print("2. Load Game")
    print("3. Tutorial")
    print("4. Settings")
    print("5. Exit")

def main():
    while True:
        show_main_menu()
        choice = input("Enter Your Choice: ")
        #NEW GAME
        if choice == "1":
            print("Starting a New Game!\n")

        elif choice == "2":
            print("Choose a save file from the list below:\n")

        elif choice == "3":
            print("Welcome to the Tutorial!\n")
        
        elif choice == "4":
            print("Settings:\n")

        elif choice == "5":
            print("Thank you for playing! Good Bye!\n")
            break
        

main()
