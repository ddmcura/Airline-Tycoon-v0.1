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
