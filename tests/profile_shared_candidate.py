"""Stage 3A infrastructure measurements, not flight-throughput certification.

python -B -m tests.profile_shared_candidate --repeats 5 --events 64
Setup/copy/equality/post-validation are outside timings. Counters use separate
instrumented runs. Only NO_OP and a strict synthetic presentation-free handler
are used. Fixtures and results are in memory; no production saves are touched.
"""

import argparse
from copy import deepcopy
import json
import platform
from statistics import median
from time import perf_counter
import tracemalloc
from unittest.mock import patch

from game.simulation import kernel
from game.simulation.resolver import resolve_until
from game.world_state import validate_world
from tests.resolution_oracle import canonical_world
from tests.test_shared_candidate import DUE, make_world, record, schedule


def measure(events, repeats, *, custom=False):
    base = make_world()
    registry = kernel.EventHandlerRegistry()
    registry.register('RECORD' if custom else 'NO_OP', record if custom else kernel._no_op)
    for index in range(events):
        schedule(base, DUE, event_type='RECORD' if custom else 'NO_OP',
                 payload={'label': str(index)})
    variants = {'strict': {}, 'shared': {}, 'shadow': {}}
    expected = None
    for name, settings in variants.items():
        samples = []
        for _ in range(repeats):
            world = deepcopy(base)
            started = perf_counter()
            result = resolve_until(world, DUE, registry=registry,
                shared=name != 'strict', shadow=name == 'shadow', max_batch_events=8)
            samples.append(perf_counter() - started)
            assert result.succeeded, result.failure
            assert validate_world(world).is_valid
            encoded = canonical_world(world)
            if expected is None:
                expected = encoded
            assert encoded == expected
        world = deepcopy(base)
        with patch.object(kernel, 'validate_world', wraps=kernel.validate_world) as validations, patch.object(
                kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones, patch.object(
                kernel, '_replace_envelope', wraps=kernel._replace_envelope) as commits, patch.object(
                kernel, '_event_contract_witness', wraps=kernel._event_contract_witness) as witnesses:
            result = resolve_until(world, DUE, registry=registry,
                shared=name != 'strict', shadow=name == 'shadow', max_batch_events=8)
        assert result.succeeded
        world = deepcopy(base)
        tracemalloc.start()
        resolve_until(world, DUE, registry=registry,
            shared=name != 'strict', shadow=name == 'shadow', max_batch_events=8)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        settings.update(median_seconds=median(samples), samples_seconds=samples,
            full_validations=validations.call_count, world_clones=clones.call_count,
            commits=commits.call_count, before_event_witnesses=witnesses.call_count,
            retained_bytes=retained, peak_bytes=peak)
    return variants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=64)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if min(args.events, args.repeats) < 1:
        parser.error('events and repeats must be positive')
    print(json.dumps(dict(python=platform.python_version(), platform=platform.platform(),
        events=args.events, repeats=args.repeats, batch_size=8,
        noop=measure(args.events, args.repeats),
        strict_custom_fallback=measure(args.events, args.repeats, custom=True)), indent=2))


if __name__ == '__main__':
    main()
