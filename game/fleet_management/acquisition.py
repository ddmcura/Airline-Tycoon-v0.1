"""Individual fleet entry and deterministic display registration allocation."""

from hashlib import sha256

from game.world_state.construction import add_aircraft


def delivery_locations(world, airline_id):
    airline = world['airlines'][airline_id]
    return tuple(sorted(set(airline['base_airport_ids'] + airline['hub_airport_ids'])))


def enter_purchased_aircraft(candidate, airline_id, delivery_airport_id, view):
    """Mutate only the caller's isolated purchase candidate."""
    world = candidate['world_state']
    if delivery_airport_id not in delivery_locations(world, airline_id):
        raise ValueError('delivery must be an existing airline base or hub')
    bases = world['airlines'][airline_id]['base_airport_ids']
    if not bases:
        raise ValueError('an existing home base is required')
    home = sorted(bases)[0]
    country_id = world['airports'][home]['country_id']
    country = world['countries'][country_id]['external_reference_code']
    if country != 'PH':
        raise ValueError('no approved registration convention for home country')
    aircraft_id = add_aircraft(candidate, airline_id, 'PENDING',
        view['model']['model_id'], home_airport_id=home,
        current_airport_id=delivery_airport_id, configuration={
            'contract': 'PH_MAX_ECONOMY_V1', 'catalog_version': view['catalog_version'],
            'economy_capacity': view['model']['max_economy_seats'],
            'performance_contract': 'PH_SCALAR_RANGE_V1',
        })
    used = {a['display_registration'] for a in world['aircraft'].values()}
    seed = candidate['deterministic_state']['world_seed']
    # A seed-keyed start with deterministic linear collision probing guarantees
    # progress without a preallocated finite pool or uncontrolled RNG state.
    material = f'PH_REGISTRATION_V1|{seed}|{aircraft_id}|{country_id}'
    start = int.from_bytes(sha256(material.encode('utf-8')).digest(), 'big') % 10**12
    for attempt in range(len(used) + 1):
        registration = f'RP-C{(start + attempt) % 10**12:012d}'
        if registration not in used:
            break
    else:
        raise ValueError('registration namespace exhausted')
    aircraft = world['aircraft'][aircraft_id]
    aircraft['display_registration'] = registration
    return aircraft_id
