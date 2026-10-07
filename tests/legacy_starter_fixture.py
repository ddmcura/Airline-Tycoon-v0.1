"""Construct a valid saved-style A320-200 starter for compatibility tests."""

from copy import deepcopy

from game.world_state import validate_world


def with_legacy_starter(world):
    """Return a detached world with the pre-grant starter representation."""
    result = deepcopy(world)
    aircraft = next(iter(result["world_state"]["aircraft"].values()))
    aircraft["model_reference"] = "A320-200"
    aircraft.pop("configuration", None)
    aircraft.pop("lifecycle", None)
    validation = validate_world(result)
    if not validation.is_valid:
        raise AssertionError(validation.as_dict())
    return result


def strip_quarterly_foundation(candidate):
    """Fixture-only reconstruction of pre-schema-8 empty foundation state."""
    for name in ('services', 'service_numbering', 'weekly_plans'):
        if candidate['world_state'].get(name):
            raise AssertionError('cannot strip nonempty quarterly test authority')
        candidate['world_state'].pop(name, None)
    for name in ('service', 'weekly_plan'):
        cursor = candidate['deterministic_state']['id_allocator']['next_by_type'].pop(name, 1)
        if cursor != 1:
            raise AssertionError('cannot strip issued quarterly test identities')
