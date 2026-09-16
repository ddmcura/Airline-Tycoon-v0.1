"""Validated construction of immutable planning input snapshots."""

from copy import deepcopy
import json
from pathlib import Path

from game.utils.geo_distance import distance_km
from .planning_validation import validate_timing

_PATH = Path(__file__).resolve().parents[2] / 'Data' / 'Stage1' / 'scheduling_v1.json'


def planning_snapshot(world, aircraft_id, origin_id, destination_id):
    profile = json.loads(_PATH.read_text(encoding='utf-8'))
    if type(profile) is not dict or set(profile) != {'profile_version', 'models', 'airports'}:
        raise ValueError('invalid scheduling reference profile')
    aircraft = world['aircraft'][aircraft_id]
    origin, destination = world['airports'][origin_id], world['airports'][destination_id]
    if 'configuration' in aircraft:
        from game.scheduling.eligibility import check_eligibility
        numerator, denominator = distance_km(origin, destination).as_integer_ratio()
        distance_m = (numerator * 1000 + denominator - 1) // denominator
        model = check_eligibility(aircraft, distance_m)
        try:
            origin_taxi = profile['airports'][origin['catalog_airport_id']]
            destination_taxi = profile['airports'][destination['catalog_airport_id']]
        except KeyError as exc:
            raise ValueError('no approved scheduling profile for airport') from exc
        snapshot = {
            'contract': 'PH_SCHEDULING_TIMING_V2',
            'profile_version': 'ph-acquisition-timing-v1',
            'model_reference': aircraft['model_reference'],
            'catalog_version': aircraft['configuration']['catalog_version'],
            'performance_contract': aircraft['configuration']['performance_contract'],
            'distance_m': distance_m, 'cruise_speed_kph': model['cruise_speed_kph'],
            'turnaround_seconds': 2700 if model['aircraft_category'] == 'WIDEBODY' else 1800,
            'taxi_out_seconds': deepcopy(origin_taxi['taxi_out_seconds']),
            'taxi_in_seconds': deepcopy(destination_taxi['taxi_in_seconds']),
        }
        validate_timing(snapshot)
        return snapshot
    try:
        model = profile['models'][aircraft['model_reference']]
        origin_taxi = profile['airports'][origin['catalog_airport_id']]
        destination_taxi = profile['airports'][destination['catalog_airport_id']]
    except KeyError as exc:
        raise ValueError('no approved scheduling profile for aircraft or airport') from exc
    numerator, denominator = distance_km(origin, destination).as_integer_ratio()
    snapshot = {
        'contract': 'PH_SCHEDULING_TIMING_V1',
        'profile_version': profile['profile_version'],
        'model_reference': aircraft['model_reference'],
        'distance_m': numerator * 1000 // denominator,
        **deepcopy(model),
        'taxi_to_stand_seconds': deepcopy(origin_taxi['taxi_to_stand_seconds']),
        'taxi_out_seconds': deepcopy(origin_taxi['taxi_out_seconds']),
        'taxi_in_seconds': deepcopy(destination_taxi['taxi_in_seconds']),
    }
    validate_timing(snapshot)
    return snapshot
