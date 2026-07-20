# game/route_management/route_calculators.py

from math import radians, cos, sin, asin, sqrt

def calculate_distance(origin_coords, dest_coords):
    """
    Calculate great-circle distance between two coordinates using the Haversine formula.
    Args:
        origin_coords (dict): {"lat": float, "lon": float}
        dest_coords (dict): {"lat": float, "lon": float}
    Returns:
        float: Distance in kilometers rounded to 1 decimal
    """
    lat1, lon1 = origin_coords["lat"], origin_coords["lon"]
    lat2, lon2 = dest_coords["lat"], dest_coords["lon"]

    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return round(km, 1)

def calculate_base_fare(distance_km, class_type="Economy"):
    """
    Calculate base fare per ticket based on class and distance.
    Args:
        distance_km (float): Distance in kilometers
        class_type (str): One of ["Economy", "Business", "First"]
    Returns:
        float: Calculated fare
    """
    base_rate_per_km = 0.12
    multipliers = {
        "Economy": 1.0,
        "Business": 2.2,
        "First": 5.0
    }
    return round(distance_km * base_rate_per_km * multipliers.get(class_type, 1.0), 2)
