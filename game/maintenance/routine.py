"""Deterministic per-completion routine maintenance cost."""
from game.utils.geo_distance import distance_km
from game.world_state.maintenance_reference import class_for_model

def departure_distance(world, flight):
    revision = world["schedule_definitions"][flight["schedule_id"]]["revisions"][str(flight["schedule_revision"])]
    snapshot = revision.get("planning_timing")
    if snapshot is not None:
        source = snapshot["contract"]
        if source not in ("PH_SCHEDULING_TIMING_V1", "PH_SCHEDULING_TIMING_V2"):
            raise ValueError("unsupported planning timing version")
        return snapshot["distance_m"], source.replace("PH_SCHEDULING_TIMING", "PLANNING_TIMING")
    origin = world["airports"][flight["origin_airport_id"]]
    destination = world["airports"][flight["destination_airport_id"]]
    return int(distance_km(origin, destination) * 1000), "AIRPORT_COORDINATE_FALLBACK_V1"

def maintenance_expense_minor(distance_m, factor_minor_per_km):
    if (type(distance_m) is not int or distance_m < 0
            or type(factor_minor_per_km) is not int or factor_minor_per_km < 0):
        raise ValueError("maintenance inputs must be nonnegative integers")
    return (distance_m * factor_minor_per_km + 999) // 1000

def departure_witness(world, flight, aircraft, configuration):
    distance, source = departure_distance(world, flight)
    klass = class_for_model(aircraft["model_reference"])
    return {
        "maintenance_distance_m": distance,
        "maintenance_distance_source": source,
        "maintenance_classification_version": configuration["classification_version"],
        "maintenance_class": klass,
        "maintenance_factor_minor_per_km": configuration["factor_minor_per_km_by_class"][klass],
        "maintenance_configuration_fingerprint": configuration["configuration_fingerprint"],
    }
