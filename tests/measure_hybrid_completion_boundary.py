"""Opt-in B3D whole-command control for a rejected local admission shell.

No fast transaction is admitted. Report fallback costs honestly. Inputs, strict
oracle worlds, detailed validation, Save/Load and instrumentation are separate.
Usage: python -m tests.measure_hybrid_completion_boundary --source PATH --output PATH
"""
import argparse
from copy import deepcopy
from contextlib import ExitStack
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

import game.world_state
from game.world_state import validate_world
from game.simulation import kernel
from game.scheduling import quarterly_backend, quarterly_boundary
from tests import test_quarterly_backend as fixtures
from tests.hybrid_completion_boundary import attempt_completion, selected_inputs
from tests.resolution_oracle import canonical_world, save_reload
from tests.test_quarterly_booking_validation import reference_validation


def build_source(kind, path=None):
    started = time.perf_counter()
    if kind == 'heavy':
        with open(path, encoding='utf-8') as stream:
            world = json.load(stream)
        assert validate_world(world).is_valid
        events = 0
        while min(world['world_state']['pending_events'].values(), key=kernel._event_key)['event_type'] != 'STAGE1_FLIGHT_COMPLETION':
            assert events < 12, 'retained source unexpectedly far from Completion'
            # One ordinary request resolves the due dispatch/departure pair;
            # repeated Next Event reconciliation can reintroduce a dispatch
            # while its same-UTC departure remains PLANNED.
            due = min(world['world_state']['pending_events'].values(), key=kernel._event_key)['due_at_utc']
            result = kernel.process_events_through(world, due)
            assert result.succeeded, result
            events += len(result.completed_event_ids) + len(result.skipped_event_ids)
    else:
        world = fixtures.QuarterlyBackendTests.fixture()[0]
        if kind == 'minimal':
            from game.demand import revise_demand_model
            result = revise_demand_model(world, configuration_updates={
                'daily_booker_rate_ppm': 0,
                'configuration_version': 'b3d-zero-demand-control-v1'})
            assert result.succeeded, result
        assert kernel.process_events_through(world, '2027-01-02T01:00:00Z').succeeded
        events = None
    assert validate_world(world).is_valid
    event = min(world['world_state']['pending_events'].values(), key=kernel._event_key)
    assert event['event_type'] == 'STAGE1_FLIGHT_COMPLETION'
    return world, dict(setup_seconds=time.perf_counter()-started,
                       preparatory_strict_events=events)


def command(world, mode):
    return (kernel.process_next_event(world) if mode == 'strict'
            else attempt_completion(world).processing_result)


def measured_run(kind, path, mode, instrument=False):
    source, report = build_source(kind, path)
    frame, selected_count = selected_inputs(source)
    report.update(bookings=len(source['world_state']['bookings']),
        selected_records=selected_count,
        selected_bookings=len(frame['bookings']),
        top_level_keyed_records=sum(len(v) for v in source['world_state'].values() if type(v) is dict),
        input_pending_rows=len(source['world_state']['pending_events']))
    del frame
    # Existing input fixture is retained by the harness outside command timing;
    # no detached input/preparation required by the command is excluded.
    working = deepcopy(source)
    before_peak = peak_working_set()
    counts = dict(runtime_world_copies=0, reconciliation_world_copies=0, full_gates=0)
    with ExitStack() as stack:
        if instrument:
            for module, name, key in ((kernel, '_clone_runtime_world', 'runtime_world_copies'),
                (kernel, 'validate_world', 'full_gates'),
                (quarterly_backend, 'deepcopy', 'reconciliation_world_copies'),
                (quarterly_boundary, 'deepcopy', 'reconciliation_world_copies')):
                original = getattr(module, name)
                def wrapper(*args, _original=original, _key=key, **kwargs):
                    counts[_key] += 1
                    return _original(*args, **kwargs)
                stack.enter_context(patch.object(module, name, wrapper))
        started = time.perf_counter()
        result = command(working, mode)
        report['command_seconds'] = time.perf_counter()-started
    assert result.succeeded, result
    report.update(mode=mode, instrumented=instrument, counts=counts if instrument else None,
                  process_peak_bytes=peak_working_set(), process_peak_before_command_bytes=before_peak)
    if instrument:
        report['minimum_full_gate_keyed_entry_exposures'] = counts['full_gates'] * report['top_level_keyed_records']
    started = time.perf_counter()
    expected = deepcopy(source)
    reference_result = kernel.process_next_event(expected)
    report['strict_oracle_construction_seconds'] = time.perf_counter()-started
    started = time.perf_counter()
    assert result == reference_result
    assert canonical_world(working) == canonical_world(expected)
    assert reference_validation(working).is_valid
    report['full_oracle_seconds'] = time.perf_counter()-started
    report['complete_world_equivalent'] = True
    if instrument:
        started = time.perf_counter()
        assert canonical_world(save_reload(working)) == canonical_world(save_reload(expected))
        report['save_load_seconds'] = time.perf_counter()-started
        # Actual failure/retry commands, not a timed local helper.
        failed = deepcopy(source)
        before = canonical_world(failed)
        with patch('game.aircraft_operations.fulfilment.settlement_records',
                   side_effect=RuntimeError('B3D timed failure')):
            started = time.perf_counter()
            failure = command(failed, mode)
            report['failed_command_seconds'] = time.perf_counter()-started
        assert not failure.succeeded
        assert canonical_world(failed) == before
        started = time.perf_counter()
        assert command(failed, mode).succeeded
        report['retry_command_seconds'] = time.perf_counter()-started
        assert canonical_world(failed) == canonical_world(expected)
        report['failure_source_preserved'] = True
    return report


def peak_working_set():
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
             'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
             'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    info = Counters()
    info.cb = ctypes.sizeof(info)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = wintypes.HANDLE
    memory = ctypes.windll.psapi.GetProcessMemoryInfo
    memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    memory.restype = wintypes.BOOL
    handle = current()
    if not memory(handle, ctypes.byref(info), info.cb):
        raise ctypes.WinError()
    return info.PeakWorkingSetSize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source')
    parser.add_argument('--output', required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--kind', choices=('minimal', 'controlled', 'heavy'))
    parser.add_argument('--mode', choices=('strict', 'attempt'))
    parser.add_argument('--instrument', action='store_true')
    args = parser.parse_args()
    if args.worker:
        report = measured_run(args.kind, args.source, args.mode, args.instrument)
        Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for kind in ((args.kind,) if args.kind else ('minimal', 'controlled', 'heavy')):
        if kind == 'heavy' and not args.source:
            continue
        for index in range(3):
            for mode in (('strict', 'attempt') if index % 2 == 0 else ('attempt', 'strict')):
                target = output / f'{kind}-{index}-{mode}.json'
                call = [sys.executable, '-B', '-m', 'tests.measure_hybrid_completion_boundary', '--worker', '--kind', kind,
                        '--mode', mode, '--output', str(target)]
                if args.source:
                    call += ['--source', args.source]
                subprocess.run(call, check=True, stdout=subprocess.DEVNULL)
        for mode in ('strict', 'attempt'):
            target = output / f'{kind}-instrumented-{mode}.json'
            call = [sys.executable, '-B', '-m', 'tests.measure_hybrid_completion_boundary',
                    '--worker', '--kind', kind, '--mode', mode, '--instrument', '--output', str(target)]
            if args.source:
                call += ['--source', args.source]
            subprocess.run(call, check=True, stdout=subprocess.DEVNULL)
        summaries = {}
        for mode in ('strict', 'attempt'):
            values = [json.loads((output / f'{kind}-{index}-{mode}.json').read_text())['command_seconds'] for index in range(3)]
            summaries[mode] = dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
        print(kind, json.dumps(summaries), flush=True)


if __name__ == '__main__':
    main()
