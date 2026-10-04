"""Stage 3E.2 differential read-only predicates and complete runtime gates."""
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
import pickle
import random
import unittest
from unittest.mock import patch

from game.world_state import validation as v, booking_validation as booking
from game.world_state import booking_lineage_validation as graph
from tests import booking_validation_oracle as old
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import world_digest, save_reload


def reference(stack):
    stack.enter_context(patch.object(v, 'validate_schema3_booking_authority', old.validate_schema3_booking_authority))


class BookingLineageOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = flight_world(1)

    def compare(self, world, invalid=True):
        before = pickle.dumps(world, protocol=5)
        def outcome():
            try:
                return v.validate_world(world)
            except (TypeError, ValueError, KeyError) as exc:
                # Unusual malformed values may already raise in the frozen
                # diagnostic path. Preserve rejection and exact exception.
                return type(exc), str(exc)
        current = outcome()
        with ExitStack() as stack:
            reference(stack)
            original = outcome()
        self.assertEqual(current, original)
        self.assertEqual(before, pickle.dumps(world, protocol=5))
        if invalid:
            self.assertTrue(type(current) is tuple or not current.is_valid)
        return current

    def mutate(self, collection, field, value):
        world = deepcopy(self.base)
        record = next(iter(world['world_state'][collection].values()))
        record[field] = value
        return world

    def test_valid_graph_used_once_and_immutable_source_facts(self):
        with patch.object(graph, '_itinerary_graph', wraps=graph._itinerary_graph) as i, patch.object(graph, '_booking_graph', wraps=graph._booking_graph) as b:
            self.compare(self.base, False)
        self.assertEqual((i.call_count, b.call_count), (1, 1))
        state = self.base['world_state']
        rows = graph._itinerary_graph(state)
        facts = graph._booking_graph(state, rows)
        for mapping in (rows, facts):
            self.assertEqual(set(mapping), set(state['itineraries' if mapping is rows else 'bookings']))
            self.assertTrue(all(type(row) is tuple and all(type(value) in (str, int, type(None)) for value in row) for row in mapping.values()))

    def test_missing_itinerary(self):
        self.compare(self.mutate('bookings', 'itinerary_id', 'itinerary:missing'))

    def test_missing_flight(self):
        self.compare(self.mutate('itineraries', 'dated_flight_ids', ['dated_flight:missing']))

    def test_duplicate_booking_identity(self):
        world = deepcopy(self.base); rows = list(world['world_state']['bookings'].values())
        rows[1]['booking_id'] = rows[0]['booking_id']; self.compare(world)

    def test_duplicate_itinerary_identity(self):
        world = deepcopy(self.base); rows = list(world['world_state']['itineraries'].values())
        rows[1]['itinerary_id'] = rows[0]['itinerary_id']; self.compare(world)

    def test_malformed_flight_lists_and_containers(self):
        for value in (None, {}, 'flight', [], [1], [True], (), ['missing', 'missing']):
            with self.subTest(value=value): self.compare(self.mutate('itineraries', 'dated_flight_ids', value))

    def test_wrong_flight_lineage(self):
        world = deepcopy(self.base); rows = list(world['world_state']['itineraries'].values())
        other = next(r for r in rows if r['dated_flight_ids'] != rows[0]['dated_flight_ids'])
        rows[0]['dated_flight_ids'] = deepcopy(other['dated_flight_ids']); self.compare(world)

    def test_duplicate_itinerary_ownership_not_overwritten(self):
        world = deepcopy(self.base); rows = list(world['world_state']['bookings'].values())
        rows[1]['itinerary_id'] = rows[0]['itinerary_id']; self.compare(world)

    def test_invalid_status_relationship(self):
        for collection in ('bookings', 'itineraries'):
            self.compare(self.mutate(collection, 'status', 'CANCELLED'))

    def test_passengers_and_inventory(self):
        for value in (0, -1, True, 1.0, 9999999):
            self.compare(self.mutate('bookings', 'passenger_count', value))
        self.compare(self.mutate('bookings', 'inventory_revision_at_commit', 9999))

    def test_fares_currencies_and_paid_lineage(self):
        for value in (0, -1, True, 1.0, 9999):
            self.compare(self.mutate('bookings', 'total_fare_minor', value))
        self.compare(self.mutate('bookings', 'finance_transaction_id', None))
        self.compare(self.mutate('bookings', 'currency', 'EUR'))

    def test_nonhashable_date_reaches_diagnostics(self):
        self.compare(self.mutate('bookings', 'desired_travel_date', []))
        world = deepcopy(self.base)
        next(iter(world['world_state']['booking_state']['booking_checkpoints'].values()))['checkpoint_date'] = []
        self.compare(world)

    def test_state_changed_between_calls_is_not_cached(self):
        world = deepcopy(self.base); self.compare(world, False)
        next(iter(world['world_state']['bookings'].values()))['itinerary_id'] = 'missing'
        self.compare(world)
        restored = deepcopy(self.base); self.compare(restored, False)
        next(iter(restored['world_state']['itineraries'].values()))['schedule_lineage']['schedule_revision'] += 1
        self.compare(restored)

    def test_insertion_order_variations(self):
        rng = random.Random(3202)
        for _ in range(8):
            world = deepcopy(self.base)
            for name in ('bookings', 'itineraries', 'dated_flights', 'transactions'):
                items = list(world['world_state'][name].items()); rng.shuffle(items)
                world['world_state'][name] = dict(items)
            self.compare(world, False)

    def test_alias_checked_before_graph(self):
        world = deepcopy(self.base); rows = list(world['world_state']['itineraries'].values())
        rows[1]['dated_flight_ids'] = rows[0]['dated_flight_ids']
        with patch.object(graph, '_itinerary_graph', wraps=graph._itinerary_graph) as build:
            self.compare(world)
        self.assertEqual(build.call_count, 0)

    def test_nonjson_booking_value(self):
        self.compare(self.mutate('bookings', 'total_fare_minor', Decimal('1')))

    def test_missing_extra_and_wrong_type_every_record_field(self):
        # Mutation matrix covers every retained record field, not only selectors.
        for collection in ('bookings', 'itineraries'):
            original = next(iter(self.base['world_state'][collection].values()))
            for key in original:
                for mode in ('missing', 'wrong'):
                    world = deepcopy(self.base); row = next(iter(world['world_state'][collection].values()))
                    if mode == 'missing': del row[key]
                    else: row[key] = {'malformed': []}
                    with self.subTest(collection=collection, key=key, mode=mode): self.compare(world)
            world = self.mutate(collection, 'extra', 'unexpected'); self.compare(world)

    def test_checkpoint_result_and_journal_corruption(self):
        for kind in ('desired_duplicate', 'market_duplicate', 'wrong_date', 'missing_result', 'wrong_revision', 'wrong_cohort', 'wrong_transaction', 'wrong_entries', 'wrong_source_order'):
            world = deepcopy(self.base); state = world['world_state']; b_id, b = next(iter(state['bookings'].items()))
            checkpoint = state['booking_state']['booking_checkpoints'][b['booking_checkpoint_id']]
            result = next(r for r in checkpoint['market_results'].values() if b_id in r['booking_ids'])
            desired = result['desired_date_results'][b['desired_travel_date']]
            if kind == 'desired_duplicate': desired['booking_ids'].append(b_id)
            elif kind == 'market_duplicate': result['booking_ids'].append(b_id)
            elif kind == 'wrong_date': b['desired_travel_date'] = '2026-09-01'
            elif kind == 'missing_result': result['booking_ids'].remove(b_id)
            elif kind == 'wrong_revision': b['booking_revision'] += 1
            elif kind == 'wrong_cohort': b['cohort_key'] = 'missing'
            elif kind == 'wrong_transaction': b['finance_transaction_id'] = 'missing'
            elif kind == 'wrong_entries': state['transactions'][b['finance_transaction_id']]['entries'][0]['amount_minor'] += 1
            else: state['transactions'][b['finance_transaction_id']]['source_booking_ids'].reverse()
            with self.subTest(kind=kind): self.compare(world)

    def test_graph_anomaly_replays_original_suffix(self):
        world = self.mutate('bookings', 'status', 'CANCELLED')
        with patch.object(booking, '_validate_booking_relationships_detailed', wraps=booking._validate_booking_relationships_detailed) as fallback:
            self.compare(world)
        self.assertEqual(fallback.call_count, 1)

    def test_required_timestamps_compose_with_e1_graph_proof(self):
        for collection, field in (('bookings', 'booked_at_utc'), ('itineraries', 'scheduled_departure_utc')):
            for value in (None, 'not UTC', '2026-09-07T00:00:00.1Z'):
                self.compare(self.mutate(collection, field, value))

    def test_controlled_scaling_preserves_passengers_fare_and_other_dimensions(self):
        from tests.profile_booking_validation import split_aggregates
        state = self.base['world_state']
        total_passengers = sum(r['passenger_count'] for r in state['bookings'].values())
        total_fare = sum(r['total_fare_minor'] for r in state['bookings'].values())
        for factor in (2, 4):
            world = split_aggregates(self.base, factor); rows = world['world_state']
            self.compare(world, False)
            self.assertEqual(sum(r['passenger_count'] for r in rows['bookings'].values()), total_passengers)
            self.assertEqual(sum(r['total_fare_minor'] for r in rows['bookings'].values()), total_fare)
            for key in ('dated_flights', 'financial_accounts', 'pending_events', 'event_history', 'flight_results'):
                self.assertEqual(state[key], rows[key])
            self.assertGreater(len(rows['bookings']), len(state['bookings']))

    def test_internal_exact_fields_preserve_nonset_callers(self):
        for fields in ({'a'}, frozenset(('a',)), ['a'], ('a',), {'a': 0}):
            a = v._Validator({}); b = v._Validator({})
            self.assertEqual(booking._exact(a, {'a': 1}, fields, '$', 'test', 'test'), old._exact(b, {'a': 1}, fields, '$', 'test', 'test'))
            self.assertEqual(a.errors, b.errors)

    def test_runtime_reference_hash_and_save_continuation(self):
        from tests.profile_atomic_boundaries import measure
        target = window(deepcopy(self.base), 'round-trip')
        current = measure(self.base, target, instrument=True)
        with ExitStack() as stack:
            reference(stack); original = measure(self.base, target, instrument=True)
        self.assertEqual(current['world_hash'], original['world_hash'])
        self.assertEqual(current['calls']['complete_validation'], original['calls']['complete_validation'])
        self.assertEqual(current['calls']['candidate_clone'], original['calls']['candidate_clone'])
        self.assertEqual(current['calls']['commit_clone'], original['calls']['commit_clone'])
        restored = save_reload(deepcopy(self.base))
        self.compare(restored, False)
        self.assertEqual(world_digest(self.base), world_digest(restored))


if __name__ == '__main__': unittest.main()
