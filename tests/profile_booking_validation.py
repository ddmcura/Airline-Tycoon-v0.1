"""Stage 3E.2 frozen-world predicates, exclusive regions and exact visit counts.

Inputs and outputs belong in TEMP. Trace diagnostics are separate from latency.
"""
import argparse
import ast
from contextlib import ExitStack
import inspect
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
from unittest.mock import patch

from game.world_state import booking_validation as current, validation
from tests import booking_validation_oracle as reference
from tests.profile_atomic_boundaries import measure
from tests.profile_ph_runtime import memory_bytes
from tests.resolution_oracle import world_digest


def validator(world):
    v = validation._Validator(world)
    # Establish this invocation's structural proof, outside Booking timing.
    assert v.validate_root()
    return v


def counts(world):
    s = world['world_state']
    return dict(**{k: len(s[k]) for k in ('aircraft', 'bookings', 'itineraries',
        'dated_flights', 'flight_results', 'pending_events', 'event_history')},
        dated_flight_references=sum(len(r.get('dated_flight_ids', [])) for r in s['itineraries'].values()),
        completed_flights=sum(r['status'] == 'COMPLETED' for r in s['dated_flights'].values()),
        pending_flights=sum(r['status'] == 'PLANNED' for r in s['dated_flights'].values()))


def trace_regions(fn, v):
    """Test-only AST probes at phase boundaries; each interval charged once.

    Loop probes count actual visits, including empty-result traversal. Timing
    includes these small counters; quiet latency is measured separately.
    """
    tree = ast.parse(inspect.getsource(fn))
    offset = fn.__code__.co_firstlineno - 1
    regions = [(0, 'configuration'), (390, 'checkpoint_structure'),
        (604, 'checkpoint_event_topology'), (695, 'airline_flight_inventory'),
        (716, 'itinerary_structure_lineage'), (730, 'booking_structure_and_association'),
        (894, 'orphan_itinerary'), (911, 'checkpoint_booking_lineage'),
        (1100, 'orphan_booking_capacity')]
    times = {}; visits = {}; state = [None, None]
    def mark(label):
        now = perf_counter()
        if state[0] is not None:
            times[state[1]] = times.get(state[1], 0) + now - state[0]
        state[:] = [perf_counter(), label]
    def visit(label):
        visits[label] = visits.get(label, 0) + 1
    class Visits(ast.NodeTransformer):
        def visit_For(self, node):
            self.generic_visit(node)
            label = ast.unparse(node.target) + ' in ' + ast.unparse(node.iter)
            node.body.insert(0, ast.Expr(ast.Call(ast.Name('_visit', ast.Load()), [ast.Constant(label)], [])))
            return node
    tree = Visits().visit(tree)
    body = []
    for node in tree.body[0].body:
        label = next(label for start, label in reversed(regions) if offset + node.lineno >= start)
        body.extend([ast.Expr(ast.Call(ast.Name('_mark', ast.Load()), [ast.Constant(label)], [])), node])
    tree.body[0].body = body
    namespace = dict(fn.__globals__, _mark=mark, _visit=visit)
    exec(compile(ast.fix_missing_locations(tree), '<booking-predicate-probes>', 'exec'), namespace)
    probe = namespace[fn.__name__]
    def invoke(current_validator):
        try: return probe(current_validator)
        finally:
            mark('finished')
            state[0] = None
    with patch.object(validation, 'validate_schema3_booking_authority', invoke):
        start = perf_counter()
        result = validation.validate_world(v.envelope)
        full_seconds = perf_counter() - start
    assert result.is_valid, result.errors
    return dict(exclusive_seconds=times, loop_visits=visits, full_validation_seconds=full_seconds, percentage_of_full={k:100 * t / full_seconds for k,t in times.items()})


def optimized_profile(world):
    from game.world_state import booking_lineage_validation as g
    from tests.profile_atomic_boundaries import ExclusiveProfile
    profile = ExclusiveProfile(); visits = {}; graph_sizes = {}
    def visit(label): visits[label] = visits.get(label, 0) + 1
    class Probes(ast.NodeTransformer):
        def visit_For(self, node):
            self.generic_visit(node)
            label = ast.unparse(node.target) + ' in ' + ast.unparse(node.iter)
            node.body.insert(0, ast.Expr(ast.Call(ast.Name('_visit', ast.Load()), [ast.Constant(label)], [])))
            return node
    with ExitStack() as stack:
        for method in ('get', '__getitem__', 'add'):
            fn = getattr(g._ScalarRows, method)
            def counted(rows, *args, _fn=fn, _method=method, **kw):
                visit('scalar_rows_' + str(rows._width) + '_' + _method)
                return _fn(rows, *args, **kw)
            stack.enter_context(patch.object(g._ScalarRows, method, counted))
        for owner, name, category in ((g, '_itinerary_graph', 'itinerary_structure_lineage'),
                (g, '_booking_graph', 'booking_structure_and_association'),
                (g, '_result_lineage', 'checkpoint_booking_lineage'),
                (g, 'valid_booking_relationships', 'graph_dispatch_inventory'),
                (current, 'validate_booking_configuration', 'configuration'),
                (current, 'validate_schema3_booking_authority', 'checkpoint_prefix_dispatch')):
            fn = getattr(owner, name); tree = ast.parse(inspect.getsource(fn))
            tree = Probes().visit(tree)
            namespace = dict(fn.__globals__, _visit=visit)
            exec(compile(ast.fix_missing_locations(tree), '<validation-visits>', 'exec'), namespace)
            # Invoke in the real module globals so nested calls see probes too.
            import types
            probe = types.FunctionType(namespace[name].__code__, dict(fn.__globals__, _visit=visit), name, fn.__defaults__)
            probe.__kwdefaults__ = fn.__kwdefaults__
            def sizes_call(*args, _fn=probe, _name=name, **kw):
                rows = _fn(*args, **kw)
                if _name in ('_itinerary_graph', '_booking_graph') and rows is not None:
                    graph_sizes[_name] = dict(entries=len(rows), owned_bytes=sys.getsizeof(rows) + sys.getsizeof(rows._values) + sys.getsizeof(rows._offsets) + sum(sys.getsizeof(offset) for offset in rows._offsets.values()))
                return rows
            stack.enter_context(patch.object(owner, name, profile.wrap(sizes_call, category)))
        stack.enter_context(patch.object(validation, 'validate_schema3_booking_authority', current.validate_schema3_booking_authority))
        start = perf_counter()
        result = validation.validate_world(world)
        full_seconds = perf_counter() - start
        assert result.is_valid, result.errors
    return dict(exclusive_seconds=profile.seconds, calls=profile.calls, loop_visits=visits, graph_sizes=graph_sizes, full_validation_seconds=full_seconds, percentage_of_full={k:100*t/full_seconds for k,t in profile.seconds.items()})


def reference_gates(stack):
    stack.enter_context(patch.object(validation, 'validate_schema3_booking_authority', reference.validate_schema3_booking_authority))


def split_aggregates(base, factor):
    """Synthetic schema-valid scaling control, NOT a gameplay command.

    Split existing unflown passenger batches; preserve exact total passengers,
    fare, cash, inventory, checkpoint results and journal amounts. IDs/lineage
    expand coherently. Never change a live save, flown manifest or result.
    """
    from copy import deepcopy
    from game.world_state.ids import allocate_id
    w = deepcopy(base); state = w['world_state']
    assert not state['flight_results'] and not state['active_aircraft_operations']
    for booking_id, original in list(state['bookings'].items()):
        count = original['passenger_count']; parts = min(count, factor)
        if parts < 2: continue
        itinerary = state['itineraries'][original['itinerary_id']]
        unit_fare = itinerary['fare_offer_snapshot']['amount_minor']
        additions = []
        template = deepcopy(original)
        for part in range(parts):
            passengers = count // parts + (part < count % parts)
            if part == 0:
                r = original
            else:
                bid = allocate_id(w, 'booking'); iid = allocate_id(w, 'itinerary')
                r = deepcopy(template); i = deepcopy(itinerary)
                r['booking_id'] = bid; r['itinerary_id'] = iid; i['itinerary_id'] = iid
                state['bookings'][bid] = r; state['itineraries'][iid] = i
                additions.append(bid)
            r['passenger_count'] = passengers; r['total_fare_minor'] = passengers * unit_fare
        checkpoint = state['booking_state']['booking_checkpoints'][template['booking_checkpoint_id']]
        result = next(r for r in checkpoint['market_results'].values() if booking_id in r['booking_ids'])
        result['booking_ids'] = sorted(result['booking_ids'] + additions)
        desired = result['desired_date_results'][template['desired_travel_date']]
        desired['booking_ids'] = sorted(desired['booking_ids'] + additions)
        tx = template['finance_transaction_id']
        if tx is not None:
            state['transactions'][tx]['source_booking_ids'] = sorted(state['transactions'][tx]['source_booking_ids'] + additions)
    assert validation.validate_world(w).is_valid
    return w


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixtures', required=True, type=Path)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--runtime', action='store_true')
    p.add_argument('--trace', action='store_true')
    p.add_argument('--memory', action='store_true')
    p.add_argument('--cases', default='one-departure,representative-ten,aged-ten,dense-25,divine-next-departure')
    a = p.parse_args()
    if a.repeats < 1: p.error('positive repeats required')
    for name in a.cases.split(','):
        src = {'clock-small': 'one-completion', 'clock-divine': 'divine-next-departure'}.get(name, name)
        if name.startswith('split-'): src = 'representative-ten'
        fixture = json.loads((a.fixtures / (src + '.json')).read_text(encoding='utf-8'))
        w = fixture['world']
        if name.startswith('split-'): w = split_aggregates(w, int(name.split('-')[1]))
        original = world_digest(w)
        if a.runtime:
            if name.startswith('clock-'):
                from datetime import timedelta
                from game.world_state.timestamps import parse_canonical_utc, format_utc
                now = parse_canonical_utc(w['simulation']['time_utc'])
                due = min(parse_canonical_utc(e['due_at_utc']) for e in w['world_state']['pending_events'].values())
                fixture['target'] = format_utc(min(now + timedelta(seconds=30), due - timedelta(seconds=1)))
            modes = {key: [] for key in ('reference', 'optimized')}
            for repeat in range(a.repeats):
                for key in (('reference', 'optimized') if repeat % 2 == 0 else ('optimized', 'reference')):
                    with ExitStack() as stack:
                        if key == 'reference': reference_gates(stack)
                        modes[key].append(measure(w, fixture['target'], instrument=a.trace))
            assert len({r['world_hash'] for rows in modes.values() for r in rows}) == 1
            assert len({tuple((v['events'], v['commits']) for v in r['callbacks']) for rows in modes.values() for r in rows}) == 1
            print(json.dumps(dict(case=name, runtime=modes)), flush=True)
            continue
        result = dict(case=name, counts=counts(w), modes={})
        for key, fn in (('reference', reference.validate_schema3_booking_authority), ('optimized', current.validate_schema3_booking_authority)):
            booking_times = []; full_times = []
            for _ in range(a.repeats):
                v = validator(w); t = perf_counter(); fn(v); booking_times.append(perf_counter() - t)
                assert not v.errors, v.errors
                with ExitStack() as stack:
                    if key == 'reference': reference_gates(stack)
                    t = perf_counter(); r = validation.validate_world(w); full_times.append(perf_counter() - t)
                    assert r.is_valid, r.errors
            result['modes'][key] = dict(booking_seconds=median(booking_times), full_seconds=median(full_times))
        if a.trace:
            result['predicate_profile'] = trace_regions(reference.validate_schema3_booking_authority, validator(w))
            result['optimized_profile'] = optimized_profile(w)
        if a.memory:
            import tracemalloc
            measured = validator(w)
            tracemalloc.start()
            current.validate_schema3_booking_authority(measured)
            result['graph_peak_allocated_bytes'] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
        assert world_digest(w) == original, 'validation mutated authority'
        result['peak_process_bytes'] = memory_bytes()
        print(json.dumps(result), flush=True)


if __name__ == '__main__': main()
