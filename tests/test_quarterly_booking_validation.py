"""B2.1 current-data graph proof versus the retained ordered diagnostic path."""
from copy import deepcopy
import pickle
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from game.world_state import validation
from game.world_state import booking_validation, booking_lineage_validation as graph
from game.world_state.persistence import SaveStore, SaveError, _digest
from game.aircraft_operations.fulfilment import _build_confirmed_carriage_manifest
from app.session import Stage1Session
from game.simulation.resolver import begin_resolution, resolve_until
from tests import test_quarterly_backend as fixtures
from tests.resolution_oracle import save_reload, canonical_world
from tests.test_stage1_event_kernel import make_world, schedule


def reference_validation(world):
    # B2 rejects quarterly rows from this predicate and runs this same unchanged
    # detailed suffix. Force that predecessor path without touching other gates.
    with patch.object(graph, 'valid_booking_relationships', return_value=False):
        return validation.validate_world(world)


class QuarterlyBookingValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fixtures.QuarterlyBackendTests.fixture()[0]
        result = resolve_until(cls.base, '2027-01-02T00:00:00Z', shared=False)
        assert result.succeeded, result
        assert cls.base['world_state']['bookings']

    def compare(self, world, *, invalid=True):
        before = pickle.dumps(world, protocol=5)
        def outcome(reference=False):
            try:
                return reference_validation(world) if reference else validation.validate_world(world)
            except (TypeError, ValueError, KeyError, OverflowError) as exc:
                return type(exc), str(exc)
        current = outcome()
        original = outcome(True)
        self.assertEqual(current, original)
        self.assertEqual(before, pickle.dumps(world, protocol=5))
        if invalid:
            self.assertTrue(type(current) is tuple or not current.is_valid)
        else:
            self.assertTrue(current.is_valid)

    def test_current_quarterly_graph_and_scalar_facts_are_used(self):
        with patch.object(booking_validation, '_validate_booking_relationships_detailed',
                side_effect=AssertionError('valid quarterly relationships must use the graph')):
            self.assertTrue(validation.validate_world(self.base).is_valid)
        state = self.base['world_state']
        rows = graph._itinerary_graph(state, quarterly=True)
        bookings = graph._booking_graph(state, rows)
        for lookup, collection in ((rows, 'itineraries'), (bookings, 'bookings')):
            self.assertEqual(set(lookup), set(state[collection]))
            self.assertTrue(all(type(row) is tuple and all(type(v) in (str, int, type(None))
                for v in row) for row in lookup.values()))
        self.compare(self.base, invalid=False)

    def test_every_booking_and_itinerary_field_matches_original_diagnostics(self):
        for collection in ('bookings', 'itineraries'):
            original = next(iter(self.base['world_state'][collection].values()))
            for key in original:
                for missing in (False, True):
                    with self.subTest(collection=collection, key=key, missing=missing):
                        world = deepcopy(self.base)
                        row = next(iter(world['world_state'][collection].values()))
                        if missing:
                            del row[key]
                        else:
                            row[key] = {'invalid': []}
                        self.compare(world)
            world = deepcopy(self.base)
            next(iter(world['world_state'][collection].values()))['extra'] = 1
            self.compare(world)

    def test_every_quarterly_lineage_component_is_compared(self):
        source = next(iter(self.base['world_state']['itineraries'].values()))['quarterly_lineage']
        for key in source:
            for value in (None, True, 'wrong', {'invalid': []}):
                with self.subTest(key=key, value=value):
                    world = deepcopy(self.base)
                    next(iter(world['world_state']['itineraries'].values()))['quarterly_lineage'][key] = value
                    self.compare(world)

    def test_exact_integer_lineage_on_itinerary_flight_and_both(self):
        for field in ('revision', 'slot_number'):
            for value in (True, False, 0, -1, 10**30, 1.0, '1', None):
                for side in ('itinerary', 'flight', 'both'):
                    with self.subTest(field=field, value=value, side=side):
                        world = deepcopy(self.base)
                        row = next(iter(world['world_state']['itineraries'].values()))
                        flight = world['world_state']['dated_flights'][row['dated_flight_ids'][0]]
                        if side != 'flight':
                            row['quarterly_lineage'][field] = value
                        if side != 'itinerary':
                            flight['quarterly_lineage'][field] = value
                        self.compare(world)
        self.compare(deepcopy(self.base), invalid=False)

    def test_exact_lineage_shape_and_text_fields_on_both_sides(self):
        for side in ('itinerary', 'flight', 'both'):
            for field in next(iter(self.base['world_state']['itineraries'].values()))['quarterly_lineage']:
                for value in ('missing', None, False, ''):
                    with self.subTest(side=side, field=field, value=value):
                        world = deepcopy(self.base)
                        row = next(iter(world['world_state']['itineraries'].values()))
                        flight = world['world_state']['dated_flights'][row['dated_flight_ids'][0]]
                        for owner in ([row] if side == 'itinerary' else [flight] if side == 'flight' else [row, flight]):
                            if value == 'missing':
                                del owner['quarterly_lineage'][field]
                            else:
                                owner['quarterly_lineage'][field] = value
                        self.compare(world)
            world = deepcopy(self.base)
            row = next(iter(world['world_state']['itineraries'].values()))
            flight = world['world_state']['dated_flights'][row['dated_flight_ids'][0]]
            for owner in ([row] if side == 'itinerary' else [flight] if side == 'flight' else [row, flight]):
                owner['quarterly_lineage']['extra'] = 1
            self.compare(world)

    def test_manifest_does_not_accept_boolean_itinerary_lineage(self):
        for field in ('revision', 'slot_number'):
            world = deepcopy(self.base)
            row = next(iter(world['world_state']['itineraries'].values()))
            row['quarterly_lineage'][field] = True
            before = pickle.dumps(world, protocol=5)
            manifest = _build_confirmed_carriage_manifest(world, row['dated_flight_ids'][0])
            self.assertFalse(manifest.succeeded)
            self.assertEqual(manifest.issues[0].code, 'INVALID_BOOKING_AUTHORITY')
            self.assertEqual(before, pickle.dumps(world, protocol=5))

    def test_terminal_result_and_booking_witness_lineage_are_typed(self):
        completed = deepcopy(self.base)
        arrival = min(r['scheduled_arrival_utc'] for r in completed['world_state']['itineraries'].values())
        self.assertTrue(resolve_until(completed, arrival, shared=False).succeeded)
        for field in ('revision', 'slot_number'):
            for target in ('result', 'witness'):
                with self.subTest(field=field, target=target):
                    world = deepcopy(completed)
                    result = next(r for r in world['world_state']['flight_results'].values() if r['booking_witnesses'])
                    owner = result if target == 'result' else result['booking_witnesses'][0]
                    # Retain the original fingerprint: dict equality alone can
                    # otherwise accept this boolean witness as integer 1.
                    owner['quarterly_lineage'][field] = True
                    self.compare(world)

    def test_flight_event_lineage_cannot_use_numeric_lookalikes(self):
        for table in ('pending_events', 'event_history'):
            for field in ('revision', 'slot_number'):
                for value in (True, False, 1.0, '1', 0, -1, 10**30, None):
                    with self.subTest(table=table, field=field, value=value):
                        world = deepcopy(self.base)
                        event = next(e for e in world['world_state'][table].values()
                            if e['event_type'] in ('STAGE1_FLIGHT_DEPARTURE', 'STAGE1_FLIGHT_COMPLETION'))
                        event['payload']['quarterly_lineage'][field] = value
                        self.compare(world)

    def test_active_operation_and_booking_witness_lineage_are_typed(self):
        active = deepcopy(self.base)
        departure = min(i['scheduled_departure_utc'] for i in active['world_state']['itineraries'].values())
        self.assertTrue(resolve_until(active, departure, shared=False).succeeded)
        for field in ('revision', 'slot_number'):
            for target in ('operation', 'witness'):
                with self.subTest(field=field, target=target):
                    world = deepcopy(active)
                    operation = next(o for o in world['world_state']['active_aircraft_operations'].values()
                        if o['booking_witnesses'])
                    owner = operation if target == 'operation' else operation['booking_witnesses'][0]
                    owner['quarterly_lineage'][field] = True
                    self.compare(world)

    def test_valid_later_revision_slot_and_zero_inventory_are_preserved(self):
        from game.world_state.quarterly_construction import append_weekly_plan_revision, commit_weekly_plan_publication
        # Build the draft first, then enroll through the real boundary after
        # publishing revision 2; current-quarter unpublished enrollment rejects.
        with patch.object(fixtures, 'enable_quarterly_backend_for_testing'):
            world, pid, sid, *_ = fixtures.QuarterlyBackendTests.fixture(published=False)
        state = world['world_state']
        slots = deepcopy(state['weekly_plans'][pid]['revisions']['1']['slots'])
        slots[0]['slot_number'] = 2
        state['services'][sid]['next_slot_number'] = 3
        append_weekly_plan_revision(world, pid, expected_revision=1, slots=slots)
        commit_weekly_plan_publication(world, pid, expected_revision=2)
        fixtures.enable_quarterly_backend_for_testing(world)
        self.assertTrue(validation.validate_world(world).is_valid)
        self.assertTrue(resolve_until(world, '2027-01-02T00:00:00Z', shared=False).succeeded)
        self.compare(world, invalid=False)
        # Rebind after resolver detached commits; never assert against stale rows.
        state = world['world_state']
        self.assertTrue(all(i['quarterly_lineage']['revision'] == 2 for i in state['itineraries'].values()))
        self.assertTrue(any(i['quarterly_lineage']['service_id'] == sid
            and i['quarterly_lineage']['slot_number'] == 2 for i in state['itineraries'].values()))
        self.assertTrue(all(type(f['inventory_revision']) is int and f['inventory_revision'] >= 0
            for f in state['dated_flights'].values()))
        self.assertTrue(any(f['inventory_revision'] == 0 for f in state['dated_flights'].values()))

    def test_malformed_load_diagnostic_preserves_active_world_and_files(self):
        for previous in ('absent', 'malformed', 'valid'):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as directory:
                store = SaveStore(directory)
                career = store.new_career_id()
                store.save(career, 'manual', self.base)
                if previous != 'absent':
                    store.save(career, 'manual', self.base)
                path = store._path(career, 'manual')
                def corrupt(p):
                    data = json.loads(p.read_text(encoding='utf-8'))
                    next(iter(data['world']['world_state']['itineraries'].values()))['quarterly_lineage']['revision'] = True
                    data['integrity_sha256'] = _digest({k: v for k, v in data.items() if k != 'integrity_sha256'})
                    p.write_text(json.dumps(data), encoding='utf-8')
                corrupt(path)
                if previous == 'malformed':
                    corrupt(path.with_suffix('.previous'))
                snapshots = {p: p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
                session = Stage1Session(save_root=directory)
                session.world = deepcopy(self.base)
                active = session.world
                before = canonical_world(active)
                if previous == 'valid':
                    data = session.load_saved(career)
                    self.assertTrue(data['_recovered_from_previous'])
                    self.assertEqual(canonical_world(session.world), before)
                    self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')
                else:
                    with self.assertRaises(SaveError) as caught:
                        session.load_saved(career)
                    self.assertEqual(caught.exception.code, 'INVALID_WORLD')
                    self.assertIn('quarterly_lineage', str(caught.exception))
                    self.assertIs(session.world, active)
                    self.assertEqual(canonical_world(active), before)
                self.assertEqual(snapshots, {p: p.read_bytes() for p in snapshots})

    def test_rejected_source_then_explicit_strict_shared_retry_is_exact(self):
        target = '2027-01-02T15:00:00Z'
        expected = deepcopy(self.base)
        self.assertTrue(resolve_until(expected, target, shared=False).succeeded)
        for shared in (False, True):
            world = deepcopy(self.base)
            row = next(iter(world['world_state']['itineraries'].values()))
            original = row['quarterly_lineage']['slot_number']
            row['quarterly_lineage']['slot_number'] = True
            before = canonical_world(world)
            self.assertFalse(resolve_until(world, target, shared=shared).succeeded)
            self.assertEqual(canonical_world(world), before)
            row['quarterly_lineage']['slot_number'] = original
            self.assertTrue(resolve_until(world, target, shared=shared).succeeded)
            self.assertEqual(canonical_world(world), canonical_world(expected))

    def test_legacy_lineage_and_missing_career_marker_are_rejected(self):
        world = deepcopy(self.base)
        row = next(iter(world['world_state']['itineraries'].values()))
        row['schedule_lineage'] = {'schedule_id': 'missing', 'schedule_revision': 1, 'occurrence_key': 'wrong'}
        self.compare(world)
        del world['simulation']['operational_authority']
        self.compare(world)

    def test_current_fares_inventory_and_owner_facts_are_not_cached(self):
        world = deepcopy(self.base)
        self.compare(world, invalid=False)
        row = next(iter(world['world_state']['itineraries'].values()))
        flight = world['world_state']['dated_flights'][row['dated_flight_ids'][0]]
        for owner, key, value in ((row['fare_offer_snapshot'], 'amount_minor', 0),
                (row['fare_offer_snapshot'], 'currency', 'EUR'),
                (row['quarterly_lineage'], 'revision', 999),
                (flight, 'inventory_revision', 0),
                (flight, 'airline_id', 'airline-missing')):
            original = owner[key]
            owner[key] = value
            self.compare(world)
            owner[key] = original
            self.compare(world, invalid=False)

    def test_alias_precedes_graph_and_source_is_never_repaired(self):
        world = deepcopy(self.base)
        rows = list(world['world_state']['itineraries'].values())
        rows[1]['quarterly_lineage'] = rows[0]['quarterly_lineage']
        with patch.object(graph, '_itinerary_graph', wraps=graph._itinerary_graph) as build:
            self.compare(world)
        self.assertEqual(build.call_count, 0)

    def test_duplicate_orphan_and_wrong_flight_relationships(self):
        for mode in ('duplicate', 'orphan', 'wrong-flight'):
            world = deepcopy(self.base)
            state = world['world_state']
            rows = list(state['bookings'].values())
            if mode == 'duplicate':
                rows[1]['itinerary_id'] = rows[0]['itinerary_id']
            elif mode == 'orphan':
                del state['bookings'][rows[0]['booking_id']]
            else:
                itineraries = list(state['itineraries'].values())
                other = next(i for i in itineraries if i['dated_flight_ids'] != itineraries[0]['dated_flight_ids'])
                itineraries[0]['dated_flight_ids'] = deepcopy(other['dated_flight_ids'])
            self.compare(world)

    def test_checkpoint_and_paid_journal_coverage_corruption(self):
        for mode in ('booking-list', 'desired-total', 'journal-source', 'journal-amount'):
            world = deepcopy(self.base)
            state = world['world_state']
            booking = next(iter(state['bookings'].values()))
            checkpoint = state['booking_state']['booking_checkpoints'][booking['booking_checkpoint_id']]
            result = next(r for r in checkpoint['market_results'].values() if booking['booking_id'] in r['booking_ids'])
            if mode == 'booking-list':
                result['booking_ids'].append(booking['booking_id'])
            elif mode == 'desired-total':
                result['desired_date_results'][booking['desired_travel_date']]['booked_passenger_count'] += 1
            else:
                transaction = state['transactions'][booking['finance_transaction_id']]
                if mode == 'journal-source':
                    transaction['source_booking_ids'].pop()
                else:
                    transaction['entries'][0]['amount_minor'] += 1
                    transaction['entries'][1]['amount_minor'] -= 1
            self.compare(world)

    def test_reversed_collections_and_load_rebuild_exactly(self):
        world = deepcopy(self.base)
        for collection in ('bookings', 'itineraries', 'dated_flights', 'transactions'):
            world['world_state'][collection] = dict(reversed(list(world['world_state'][collection].items())))
        self.compare(world, invalid=False)
        restored = save_reload(world)
        self.assertEqual(canonical_world(restored), canonical_world(world))
        self.compare(restored, invalid=False)

    def test_complete_strict_shared_and_predecessor_worlds_match(self):
        target = '2027-01-02T15:00:00Z'
        expected = deepcopy(self.base)
        with patch.object(graph, 'valid_booking_relationships', return_value=False):
            reference = resolve_until(expected, target, shared=False)
        self.assertTrue(reference.succeeded, reference)
        for shared, cap in ((False, 1), (True, 1), (True, 2), (True, 8)):
            with self.subTest(shared=shared, cap=cap):
                world = deepcopy(self.base)
                actual = resolve_until(world, target, shared=shared, max_batch_events=cap)
                self.assertEqual(actual, reference)
                self.assertEqual(canonical_world(world), canonical_world(expected))

    def test_budget_stop_saved_prefix_and_explicit_retry_match_control(self):
        target = '2027-01-02T15:00:00Z'
        expected = deepcopy(self.base)
        self.assertTrue(resolve_until(expected, target, shared=False).succeeded)
        for shared in (False, True):
            world = deepcopy(self.base)
            request = begin_resolution(world, target, shared=shared, max_events=2)
            while not request.finished:
                progress = request.step()
            self.assertEqual(progress.processing_result.failure.code, 'EVENT_LIMIT_REACHED')
            self.assertEqual(progress.completed_event_count, 2)
            self.assertEqual(progress.unresolved_target_utc, target)
            self.assertTrue(world['world_state']['pending_events'])
            prefix = canonical_world(world)
            request.close()
            self.assertEqual(canonical_world(world), prefix)
            restored = save_reload(world)
            self.assertEqual(canonical_world(restored), prefix)
            # An explicit new command; no callback silently renews the budget.
            result = resolve_until(restored, target, shared=shared)
            self.assertTrue(result.succeeded, result)
            self.assertEqual(canonical_world(restored), canonical_world(expected))

    def test_actual_default_10000_limit_is_work_budget_not_runaway(self):
        # Pre-existing finite NO_OP work: no child generation or airline-capacity
        # claim. Exercise the real default limit without changing a constant.
        world = make_world()
        target = '2026-08-20T05:00:00Z'
        ids = [schedule(world, target) for _ in range(10001)]
        request = begin_resolution(world, target, shared=False)
        while not request.finished:
            progress = request.step()
        self.assertEqual(progress.processing_result.failure.code, 'EVENT_LIMIT_REACHED')
        self.assertEqual(progress.completed_event_count, 10000)
        self.assertFalse(request.boundary().current_utc_fully_resolved)
        self.assertEqual(tuple(world['world_state']['pending_events']), (ids[-1],))
        request.close()
        retry = resolve_until(world, target, shared=False)
        self.assertTrue(retry.succeeded, retry)
        self.assertEqual(retry.completed_event_ids, (ids[-1],))
        self.assertEqual(tuple(world['world_state']['event_history']), tuple(ids))
        self.assertTrue(validation.validate_world(world).is_valid)


if __name__ == '__main__':
    unittest.main()
