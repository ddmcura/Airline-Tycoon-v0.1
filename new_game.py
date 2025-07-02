def start_new_game():
    print("Hello there! You must be the new CEO? Please tell me your name?\n")
    while True:
        ceo_name = input("Input Your Name: ").strip()
        confirm = input(f"{ceo_name}? Is that correct? (Y/N): ").strip()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")

    print(f"Yes! {ceo_name}. I am Billie, your assistant, let's get started! As the new CEO of this company, what do you want to call your Airline?")
    while True:
        airline_name = input("Input Airline Name: ").strip()
        confirm = input(f"{airline_name}? Is that correct? (Y/N): ").strip()
        if confirm == "y":
            break
        elif confirm == "n":
            print("Let's try that again.")
    print(f"{airline_name} is such a cool name! Ok! Moving on, We will need to set up ")



start_new_game() 