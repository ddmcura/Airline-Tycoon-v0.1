"""Repeatable Stage 3B payments, setup excluded; never uses production saves."""
import argparse
from copy import deepcopy
import json
from statistics import median
from time import perf_counter
from unittest.mock import patch

from game.simulation import kernel
from game.simulation.resolver import resolve_until
from game.world_state import aircraft_market_validation
from tests.payment_fixtures import payment_world
from tests.resolution_oracle import world_digest


def measure(base, target, repeats, shared):
    samples = []
    digest = None
    for _ in range(repeats):
        world = deepcopy(base)
        start = perf_counter()
        result = resolve_until(world, target, shared=shared, max_batch_events=64)
        samples.append(perf_counter() - start)
        assert result.succeeded, result.failure
        actual = world_digest(world)
        assert digest is None or digest == actual
        digest = actual
    timing = {'market_validation_seconds': 0.0, 'transition_proof_seconds': 0.0,
              'proof_capture_seconds': 0.0}
    def timed(function, key):
        def call(*args, **kwargs):
            start = perf_counter()
            try: return function(*args, **kwargs)
            finally: timing[key] += perf_counter() - start
        return call
    from contextlib import ExitStack
    with ExitStack() as stack:
        validations = stack.enter_context(patch.object(kernel, 'validate_world', wraps=kernel.validate_world))
        clones = stack.enter_context(patch.object(kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world))
        commits = stack.enter_context(patch.object(kernel, '_replace_envelope', wraps=kernel._replace_envelope))
        stack.enter_context(patch.object(aircraft_market_validation, 'validate_aircraft_market',
            side_effect=timed(aircraft_market_validation.validate_aircraft_market, 'market_validation_seconds')))
        try:
            from game.world_state import payment_validation
        except ImportError:
            payment_validation = None
        if payment_validation is not None:
            for name, key in (('capture_payment_transition', 'proof_capture_seconds'),
                              ('validate_payment_transition', 'transition_proof_seconds')):
                stack.enter_context(patch.object(payment_validation, name,
                    side_effect=timed(getattr(payment_validation, name), key)))
        # Bind instrumented proof callables to their identity-bound certificate.
        from game.simulation.handlers import initialize_runtime_handlers
        initialize_runtime_handlers()
        world = deepcopy(base)
        result = resolve_until(world, target, shared=shared, max_batch_events=64)
        assert result.succeeded, result.failure
    initialize_runtime_handlers()
    payment_count = sum(world['world_state']['aircraft_contracts'][key]['paid_installments']
                        - row['paid_installments']
                        for key, row in base['world_state']['aircraft_contracts'].items())
    return dict(median_seconds=median(samples), samples_seconds=samples,
        full_validations=validations.call_count, physical_clones=clones.call_count,
        commits=commits.call_count, payments=payment_count,
        events=len(result.completed_event_ids), world_hash=digest, **timing)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--mode', choices=('strict', 'shared', 'both'), default='both')
    parser.add_argument('--case', default='all', choices=('all', 'one', 'sequential-eight', 'dense-64', 'expiry-two', 'aged-eight', 'same-contract-three'))
    args = parser.parse_args()
    if args.repeats < 1: parser.error('repeats must be positive')
    cases = [('one', dict(count=1)), ('sequential-eight', dict(count=8, near=True)),
             ('dense-64', dict(count=64)), ('expiry-two', dict(count=2, final=True)),
             ('aged-eight', dict(count=8, history=1000)), ('same-contract-three', dict(count=1))]
    report = {}
    for name, options in cases:
        if args.case != 'all' and args.case != name: continue
        base, target = payment_world(**options)
        if name == 'same-contract-three':
            from game.aircraft_market.step5 import _add_months
            from game.world_state.timestamps import format_utc, parse_canonical_utc
            target = format_utc(_add_months(parse_canonical_utc(target), 2))
        modes = (False, True) if args.mode == 'both' else (args.mode == 'shared',)
        report[name] = {}
        for shared in modes:
            report[name]['shared' if shared else 'strict'] = measure(base, target, args.repeats, shared)
        print(json.dumps({name: report[name]}), flush=True)
        if len(modes) == 2:
            assert report[name]['strict']['world_hash'] == report[name]['shared']['world_hash']


if __name__ == '__main__':
    main()
