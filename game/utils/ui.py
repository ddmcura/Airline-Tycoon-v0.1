# game/utils/ui.py

def paginate(items, page_size=9, render_func=None, allow_cancel=True):
    """
    Displays paginated items in the terminal, allowing navigation and selection.
    
    Args:
        items (list): The list of items to paginate.
        page_size (int): Number of items per page.
        render_func (function, optional): A function that takes a list of items 
                                          and returns a formatted string for display.
        allow_cancel (bool): Whether to allow canceling with "C".

    Returns:
        The selected item from the list, "BACK" if the user chooses to go back,
        or "CANCEL" if the user chooses to cancel (when allow_cancel=True).
    """
    current_page = 0
    total_pages = (len(items) - 1) // page_size + 1

    while True:
        start = current_page * page_size
        end = start + page_size
        page_items = items[start:end]

        print(f"\n Page {current_page + 1}/{total_pages}")
        if render_func:
            print(render_func(page_items))
        else:
            for i, item in enumerate(page_items, 1):
                print(f"{i}. {item}")

        footer = "N: Next | P: Prev | B: Back"
        if allow_cancel:
            footer += " | C: Cancel"
        print(f"\n{footer}")

        choice = input("Input Choice: ").strip().lower()

        if choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "p" and current_page > 0:
            current_page -= 1
        elif choice == "b":
            return "BACK"
        elif choice == "c" and allow_cancel:
            return "CANCEL"
        elif choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(page_items):
                return page_items[index]
            else:
                print("Invalid choice. Try again.")
        else:
            print("Invalid Choice. Try Again.")
