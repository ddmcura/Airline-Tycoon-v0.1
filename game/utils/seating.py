# game/utils/seating.py

def assign_seat_layout(capacity: int, mode="economy_only") -> dict:
    """
    Returns a default seat layout dictionary based on mode.
    Currently supports only full-economy layout for v1.0.

    Args:
        capacity (int): Total aircraft capacity
        mode (str): Layout mode ("economy_only" default)

    Returns:
        dict: Seat layout
    """
    if mode == "economy_only":
        layout = {
            "first_class": {"seat_type": "private_room", "seats": 0},
            "business_class": {"seat_type": "lie_flat", "seats": 0},
            "economy": {"seat_type": "standard", "seats": capacity}
        }

        print("\n🪑 Assigned Layout Preview")
        print("============================")
        print(f"First Class     : {layout['first_class']['seats']} seats")
        print(f"Business Class  : {layout['business_class']['seats']} seats")
        print(f"Economy Class   : {layout['economy']['seats']} seats")
        print("============================\n")

        return layout

    else:
        raise ValueError(f"Unsupported layout mode: {mode}")
