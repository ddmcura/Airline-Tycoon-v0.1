def time_to_minutes(t):
    hr, mn = map(int, t.split(":"))
    return hr * 60 + mn

def minutes_to_time(mins):
    return f"{str(mins // 60 % 24).zfill(2)}:{str(mins % 60).zfill(2)}"

def get_primary_route_id(routes, origin, dest):
    """Returns the existing route_id if forward or reverse exists, and its direction."""
    forward = f"{origin}-{dest}"
    reverse = f"{dest}-{origin}"
    if forward in routes:
        return forward, "forward"
    elif reverse in routes:
        return reverse, "reverse"
    return None, None
