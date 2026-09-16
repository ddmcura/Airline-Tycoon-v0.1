"""Versioned aircraft performance/airport eligibility boundary.

PH_SCALAR_RANGE_V1 uses reference maximum range only. Runway support and
payload-range are intentionally absent, not presumed physically unrestricted.
"""

from game.world_state.acquisition_validation import validate_configuration


def check_eligibility(aircraft, distance_m):
    if type(distance_m) is not int or distance_m < 0:
        raise ValueError('invalid planning distance')
    view = validate_configuration(aircraft)
    if distance_m > view['model']['reference_range_km'] * 1000:
        raise ValueError('AIRCRAFT_RANGE_EXCEEDED: leg exceeds PH scalar maximum range')
    return view['model']


def installed_capacity(aircraft):
    if 'configuration' in aircraft:
        validate_configuration(aircraft)
        return aircraft['configuration']['economy_capacity']
    if aircraft['model_reference'] == 'A320-200':
        return 180  # Explicit unchanged starter compatibility contract.
    raise ValueError('no approved installed configuration for aircraft')
