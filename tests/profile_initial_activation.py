"""Repeatable partial-week Add/publication measurements; no production saves."""

from collections import Counter
from contextlib import ExitStack
import json
import statistics
import time
from unittest.mock import patch

from game.scheduling import WeeklyDraft, publication
from game.world_state import create_stage1_new_game
from tests.test_scheduling_activation import PATTERN


def run(case):
    world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
        ceo_display_name='Profile', airline_display_name='Partial Week',
        base_airport_reference_code='MNL')
    state = world['world_state']
    aircraft = next(iter(state['aircraft']))
    ports = {r['reference_code']: k for k, r in state['airports'].items()}
    draft = WeeklyDraft(world, airline_id=state['player']['primary_airline_id'], aircraft_id=aircraft)
    counts = Counter()
    with ExitStack() as hooks:
        for name in ('_expand_schedule', '_occurrence_record', 'timing_bounds', '_continuity_conflicts'):
            original = getattr(publication, name)
            def counted(*args, _name=name, _original=original, **kwargs):
                counts[_name] += 1
                if _name == '_occurrence_record' and counts[_name] > 5000:
                    raise RuntimeError('bounded diagnostic stop: recurrence did not progress')
                result = _original(*args, **kwargs)
                if _name == '_expand_schedule':
                    counts['expanded_occurrences'] += len(result[0])
                return result
            hooks.enter_context(patch.object(publication, name, counted))
        started = time.perf_counter()
        error = None
        phase = 'add'
        try:
            if case == 'preparation-boundary':
                draft.add_weekdays(ports['MNL'], ports['DVO'], ['2026-09-01'],
                                   '08:00', return_flight=True, fare_minor=11600)
            else:
                for origin, destination, departure in PATTERN:
                    draft.add_weekdays(ports[origin], ports[destination], ['2026-09-01'],
                                      departure, fare_minor=11600)
            add_seconds = time.perf_counter() - started
            add_counts = dict(counts)
            counts.clear()
            started = time.perf_counter()
            phase = 'publication'
            draft.save_current(world, continuous=True)
            publish_seconds = time.perf_counter() - started
        except (ValueError, RuntimeError) as exc:
            error = str(exc)
            if phase == 'add':
                add_seconds = time.perf_counter() - started
                add_counts = dict(counts)
                publish_seconds = None
            else:
                publish_seconds = time.perf_counter() - started
        return dict(case=case, start_utc=world['simulation']['time_utc'],
            pattern_legs=2 if case == 'preparation-boundary' else len(PATTERN),
            add_seconds=add_seconds, publication_seconds=publish_seconds,
            add_counts=add_counts, publication_counts=None if phase == 'add' else dict(counts),
            configured_horizon_days=world['simulation']['configuration']['scheduling']['publication_horizon_days'],
            created_flights=len(world['world_state']['dated_flights']), error=error)


if __name__ == '__main__':
    for case in ('preparation-boundary', 'partial-chain'):
        samples = [run(case) for _ in range(3)]
        print(json.dumps(dict(case=case, samples=samples,
            median_add_seconds=statistics.median(row['add_seconds'] for row in samples),
            median_publication_seconds=statistics.median(row['publication_seconds'] for row in samples)
                if all(row['publication_seconds'] is not None for row in samples) else None)), flush=True)
