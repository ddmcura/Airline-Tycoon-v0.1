"""Reusable exact-world oracle, deliberately independent of resolver dispatch.

All envelope fields are compared, including saved ui_state and metadata. Only
JSON dictionary insertion order is normalized. Save-file wrapper metadata lives
outside the envelope and is never part of this comparison.
"""

from copy import deepcopy
import hashlib
import json
import tempfile

from game.simulation import kernel
from game.simulation.resolver import begin_resolution, resolve_until
from game.world_state.persistence import SaveStore
from game.world_state.validation import validate_world


def canonical_world(world):
    return json.dumps(world, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def world_digest(world):
    return hashlib.sha256(canonical_world(world).encode("utf-8")).hexdigest()


def strict_until(world, target, *, registry=kernel.DEFAULT_EVENT_HANDLERS):
    """Unchanged kernel Next Event oracle, then resolve the final empty gap."""
    while any(event["due_at_utc"] <= target
              for event in world["world_state"]["pending_events"].values()):
        result = kernel.process_next_event(world, registry=registry)
        if not result.succeeded or result.status == "STOPPED":
            return result
    return kernel.process_events_through(world, target, registry=registry)


def save_reload(world):
    """Use validated production persistence, exclusively in a temporary root."""
    with tempfile.TemporaryDirectory(prefix="at-resolution-oracle-") as root:
        store = SaveStore(root)
        career = store.new_career_id()
        store.save(career, "manual", world)
        restored, _wrapper = store.load(career)
    return restored


def assert_equivalent(test, base, target, partitions, *,
                      registry=kernel.DEFAULT_EVENT_HANDLERS,
                      save_at=None, resolver=resolve_until,
                      request_factory=begin_resolution):
    """Compare strict, one-request, partitioned, cooperative and saved paths.

    Fixtures stay below the unchanged whole-request safety limits. Boundaries
    cannot legitimately bypass these limits by partitioning a blocked request.
    Save fixtures remain PAUSED so paused restoration needs no normalization.
    """
    test.assertTrue(validate_world(base).is_valid)
    expected = deepcopy(base)
    result = strict_until(expected, target, registry=registry)
    test.assertTrue(result.succeeded, result.failure)
    test.assertEqual(result.status, "COMPLETED")
    paths = {}
    single = deepcopy(base)
    test.assertTrue(resolver(single, target, registry=registry).succeeded)
    paths["single"] = single
    partitioned = deepcopy(base)
    for boundary in (*partitions, target):
        test.assertTrue(resolver(partitioned, boundary, registry=registry).succeeded)
    paths["partitioned"] = partitioned
    cooperative = deepcopy(base)
    request = request_factory(cooperative, target, registry=registry)
    try:
        while not request.finished:
            progress = request.step()
            test.assertTrue(validate_world(cooperative).is_valid)
        test.assertTrue(progress.processing_result.succeeded)
    finally:
        request.close()
    paths["cooperative"] = cooperative
    if save_at is not None:
        saved = deepcopy(base)
        test.assertTrue(resolver(saved, save_at, registry=registry).succeeded)
        restored = save_reload(saved)
        test.assertEqual(canonical_world(restored), canonical_world(saved))
        test.assertTrue(resolver(restored, target, registry=registry).succeeded)
        paths["save/load"] = restored
    for name, actual in paths.items():
        with test.subTest(strategy=name):
            test.assertTrue(validate_world(actual).is_valid)
            test.assertEqual(actual, expected)
            test.assertEqual(canonical_world(actual), canonical_world(expected))
    return expected
