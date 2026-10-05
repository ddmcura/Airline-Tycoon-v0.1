"""Route eligibility candidates, not availability or permission to publish."""
from game.world_state.planning_reference import planning_snapshot, _PlanningReferences


def compatible_aircraft(envelope, airline_id, origin_id, destination_id):
    world = envelope['world_state']
    if origin_id not in world['airports'] or destination_id not in world['airports'] or origin_id == destination_id:
        raise ValueError('choose two distinct authoritative airports')
    references = _PlanningReferences()
    result = []
    for key, aircraft in sorted(world['aircraft'].items()):
        if aircraft['airline_id'] != airline_id or aircraft['status'] not in {'PARKED', 'IN_FLIGHT'}: continue
        try:
            planning_snapshot(world, key, origin_id, destination_id, _references=references)
        except ValueError:
            continue
        result.append(key)
    return tuple(result)
