"""Opt-in Stage 1 facade sanity timings; temporary fixtures, no GUI or saves.

python -B -m tests.profile_resolution --repeats 3
Measures strict/facade on identical worlds; fixture setup, copies, hashing and
post-validation are excluded. Alternate order to reduce warmup/order bias.
"""

import argparse
from copy import deepcopy
from datetime import timedelta
import json
from statistics import median
from time import perf_counter

from game.simulation.kernel import process_events_through
from game.simulation.resolver import resolve_until
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.profile_advancement import starting_world
from tests.resolution_oracle import canonical_world, world_digest


def measure(base, days, repeats):
    target = format_utc(parse_canonical_utc(base["simulation"]["time_utc"])
                        + timedelta(days=days))
    samples = {"strict": [], "facade": []}
    expected = None
    for index in range(repeats):
        order = ("strict", "facade") if index % 2 == 0 else ("facade", "strict")
        for name in order:
            world = deepcopy(base)
            run = process_events_through if name == "strict" else resolve_until
            start = perf_counter()
            result = run(world, target, max_generated_events=10000)
            samples[name].append(perf_counter() - start)
            assert result.succeeded, result.failure
            assert validate_world(world).is_valid
            encoded = canonical_world(world)
            if expected is None:
                expected = encoded
            assert encoded == expected
    return dict(days=days, samples_seconds=samples,
                median_seconds={key: median(values) for key, values in samples.items()},
                output_sha256=world_digest(world),
                events=len(result.completed_event_ids) + len(result.skipped_event_ids))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    quiet = create_stage1_new_game(scenario_id="stage1-philippines-v1",
        ceo_display_name="Profile", airline_display_name="Resolver profile",
        base_airport_reference_code="MNL")
    for name, base, days in (("quiet-seven-days", quiet, 7),
                             ("busy-starter-one-day", starting_world(1), 1)):
        print(json.dumps(dict(case=name, **measure(base, days, args.repeats))), flush=True)


if __name__ == "__main__":
    main()
