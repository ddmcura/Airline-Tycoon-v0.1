"""Phase 3B scoped Completion safety, including negative global dependencies."""
from copy import deepcopy
from contextlib import ExitStack
import unittest
import inspect
import sys
from unittest.mock import patch

from game.aircraft_operations import fulfilment
from game.simulation import kernel
from game.simulation.candidate_ownership import _LocalWriteTable
from game.simulation.resolver import resolve_until
from game.world_state import validate_world
from game.world_state.flight_proof_witness import protected_bytes
from game.world_state.validation import _container_alias_error
from tests import test_quarterly_backend as fixtures
from tests.resolution_oracle import canonical_world, save_reload
from tests.test_quarterly_booking_validation import reference_validation
from tests import scoped_completion_experiment as experiment


class ScopedCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = fixtures.QuarterlyBackendTests.fixture()[0]
        assert kernel.process_events_through(cls.source, '2027-01-02T01:00:00Z').succeeded
        cls.event = min(cls.source['world_state']['pending_events'].values(), key=kernel._event_key)
        assert cls.event['event_type'] == 'STAGE1_FLIGHT_COMPLETION'
        cls.fid = cls.event['owner_id']
        cls.operation = cls.source['world_state']['active_aircraft_operations'][cls.fid]
        selected = set(cls.operation['source_booking_ids'])
        cls.foreign = next(k for k in cls.source['world_state']['bookings'] if k not in selected)

    def owner(self):
        owner = experiment.ScopedCompletionOwner(self.source)
        self.addCleanup(owner.close)
        return owner

    def assert_unchanged(self, owner, before):
        self.assertEqual(protected_bytes(owner.snapshot()), before)

    def test_success_complete_world_and_independent_postings(self):
        owner = self.owner()
        before = owner.snapshot()
        expected = deepcopy(before)
        strict = kernel.process_next_event(expected)
        outcome = owner.complete()
        self.assertTrue(outcome.admitted)
        self.assertEqual(outcome.processing_result, strict)
        actual = owner.snapshot()
        self.assertEqual(protected_bytes(actual), protected_bytes(expected))
        self.assertTrue(reference_validation(actual).is_valid)
        self.assertIsNone(_container_alias_error(actual))
        old, new = before['world_state'], actual['world_state']
        f = old['dated_flights'][self.fid]
        bookings = [old['bookings'][bid] for bid in self.operation['source_booking_ids']]
        revenue = sum(b['total_fare_minor'] for b in bookings)
        passengers = sum(b['passenger_count'] for b in bookings)
        self.assertEqual(new['bookings'], old['bookings'])
        self.assertEqual(new['itineraries'], old['itineraries'])
        result = new['flight_results'][self.fid]
        self.assertEqual(result['carried_passenger_count'], passengers)
        self.assertEqual(result['recognized_revenue_minor'], revenue)
        from game.world_state.timestamps import parse_canonical_utc
        seconds = int((parse_canonical_utc(f['scheduled_in_block_utc']) -
                       parse_canonical_utc(f['scheduled_off_block_utc'])).total_seconds())
        config = before['simulation']['configuration']['flight_fulfilment']
        airline = old['airlines'][f['airline_id']]
        profile = config['revisions'][str(config['current_revision'])]['currency_profiles'][airline['base_currency']]
        numerator = f['capacity'] * ((seconds + 59)//60) * profile['seat_block_minute_rate_numerator'] * 100
        denom = profile['seat_block_minute_rate_denominator']
        base_cost = profile['fixed_flight_cost_minor'] + f['capacity']*profile['capacity_cost_minor_per_seat'] + (numerator+denom-1)//denom
        # Independent integer ceiling for frozen maintenance distance * rate/km.
        maintenance = (self.operation['maintenance_distance_m'] * self.operation['maintenance_factor_minor_per_km'] + 999)//1000
        cost = base_cost + maintenance
        self.assertEqual(result['operating_cost_minor'], cost)
        accounts = {a['code']: aid for aid,a in old['financial_accounts'].items()
                    if a['airline_id'] == f['airline_id']}
        for code, delta in dict(cash=-cost, unflown_tickets=-revenue,
                                passenger_revenue=revenue, operating_expenses=cost).items():
            aid = accounts[code]
            self.assertEqual(new['financial_accounts'][aid]['balance_minor'], old['financial_accounts'][aid]['balance_minor']+delta)
        journal = new['transactions'][result['settlement_transaction_id']]
        self.assertEqual(sum(e['amount_minor'] for e in journal['entries']), 0)
        self.assertEqual(journal['entries'], [
            {'account_id': accounts['unflown_tickets'], 'amount_minor': revenue},
            {'account_id': accounts['passenger_revenue'], 'amount_minor': -revenue},
            {'account_id': accounts['operating_expenses'], 'amount_minor': cost},
            {'account_id': accounts['cash'], 'amount_minor': -cost}])
        expected_allocator = deepcopy(before['deterministic_state'])
        expected_allocator['id_allocator']['next_by_type']['transaction'] += 1
        self.assertEqual(actual['deterministic_state'], expected_allocator)
        self.assertEqual(actual['simulation']['event_order_cursor'], before['simulation']['event_order_cursor'])
        self.assertEqual(new['dated_flights'][self.fid]['operation_revision'], f['operation_revision']+1)
        aircraft = new['aircraft'][self.operation['actual_aircraft_id']]
        self.assertEqual(aircraft['current_airport_id'], f['destination_airport_id'])
        self.assertEqual(aircraft['lifecycle']['lifetime_cycles'], old['aircraft'][aircraft['aircraft_id']]['lifecycle']['lifetime_cycles']+1)
        self.assertEqual(aircraft['lifecycle']['lifetime_flight_seconds'], old['aircraft'][aircraft['aircraft_id']]['lifecycle']['lifetime_flight_seconds']+seconds)
        self.assertEqual(new['event_history'][self.event['event_id']]['status'], 'COMPLETED')
        self.assertEqual(owner.counts['copied_existing_records'], 9)

    def test_rollback_at_boundaries_and_retry(self):
        for stage in ('before_handler', 'after_handler', 'before_validation', 'before_publish'):
            with self.subTest(stage=stage):
                owner = self.owner(); before = protected_bytes(owner.snapshot())
                def fail(current, capsule):
                    if current == stage: raise RuntimeError(stage)
                with patch.object(experiment, '_fault', fail):
                    result = owner.complete()
                self.assertFalse(result.processing_result.succeeded)
                self.assert_unchanged(owner, before)
                self.assertTrue(owner.complete().processing_result.succeeded)

    def test_rollback_after_allocator_and_record_writes(self):
        for table in ('transactions', 'flight_results'):
            with self.subTest(table=table):
                owner = self.owner(); before = protected_bytes(owner.snapshot())
                original = _LocalWriteTable.__setitem__
                reached = []
                def write(target, key, value):
                    original(target, key, value)
                    if target is active[0].envelope['world_state'][table]:
                        reached.append(table)
                        raise RuntimeError('after '+table)
                active = []
                def retain(stage, capsule):
                    if stage == 'before_handler': active.append(capsule)
                with patch.object(experiment, '_fault', retain), patch.object(_LocalWriteTable, '__setitem__', write):
                    result = owner.complete()
                self.assertEqual(reached, [table])
                self.assertFalse(result.processing_result.succeeded)
                self.assert_unchanged(owner, before)
        owner = self.owner(); before = protected_bytes(owner.snapshot())
        allocate = fulfilment.allocate_id
        def fail_allocate(*args):
            allocate(*args)
            raise RuntimeError('after allocator')
        expected = deepcopy(self.source)
        with patch.object(fulfilment, 'allocate_id', fail_allocate):
            actual = owner.complete().processing_result
            strict = kernel.process_next_event(expected)
        self.assertEqual(actual, strict)
        self.assert_unchanged(owner, before)

    def test_rollback_after_each_financial_and_lifecycle_write(self):
        source, first_line = inspect.getsourcelines(fulfilment._completion)
        markers = ('liability["balance_minor"] -=',
                   'accounts["passenger_revenue"]]["balance_minor"] +=',
                   'accounts["operating_expenses"]]["balance_minor"] +=',
                   'accounts["cash"]]["balance_minor"] -=',
                   'cairline["finance_revision"] +=',
                   'cflight["operation_revision"] +=',
                   'aircraft["status"] = "PARKED"',
                   'lifecycle["lifetime_cycles"] +=',
                   'del cworld["active_aircraft_operations"][flight_id]')
        for marker in markers:
            with self.subTest(marker=marker):
                owner = self.owner(); before = protected_bytes(owner.snapshot())
                line = first_line + next(i for i,text in enumerate(source) if marker in text)
                hit = []
                def trace(frame, event, arg):
                    if frame.f_code is fulfilment._completion.__code__ and event == 'line' and frame.f_lineno == line+1:
                        hit.append(marker)
                        raise RuntimeError('after '+marker)
                    return trace
                prior = sys.gettrace()
                try:
                    sys.settrace(trace)
                    result = owner.complete()
                finally:
                    sys.settrace(prior)
                self.assertEqual(hit, [marker], 'fault must reach the intended write')
                self.assertFalse(result.processing_result.succeeded)
                self.assert_unchanged(owner, before)

    def test_failed_full_validation_discards_successor(self):
        owner = self.owner(); before = protected_bytes(owner.snapshot())
        validate = experiment.validate_world
        def reject_successor(world):
            if self.fid in world['world_state']['flight_results']:
                # Produce real validation diagnostics on a private invalid successor.
                world['world_state']['flight_results'][self.fid]['carried_passenger_count'] += 1
            return validate(world)
        with patch.object(experiment, 'validate_world', reject_successor):
            result = owner.complete()
        self.assertEqual(result.processing_result.failure.code, 'RESULT_VALIDATION_FAILED')
        self.assert_unchanged(owner, before)

    def test_retained_references_protected_reads_and_output_detachment(self):
        owner = self.owner(); retained = []
        def retain(stage, capsule):
            if stage == 'before_handler':
                w = capsule.envelope['world_state']
                with self.assertRaises(ValueError):
                    w['bookings'][self.foreign]['status'] = 'BROKEN'
                bid = self.operation['source_booking_ids'][0]
                itinerary = self.source['world_state']['bookings'][bid]['itinerary_id']
                # Exact quarterly validators require plain lineage dictionaries;
                # these are detached read projections, never authority references.
                projection = w['itineraries'][itinerary]['quarterly_lineage']
                projection['revision'] = 77
                self.assertEqual(w['itineraries'][itinerary]['quarterly_lineage']['revision'], 1)
            if stage == 'after_handler':
                retained.extend([capsule.envelope, capsule.envelope['world_state']['flight_results'][self.fid]])
        with patch.object(experiment, '_fault', retain):
            self.assertTrue(owner.complete().processing_result.succeeded)
        before = protected_bytes(owner.snapshot())
        retained[1]['booking_witnesses'][0]['passenger_count'] = 999
        retained[0]['simulation']['time_utc'] = '1900-01-01T00:00:00Z'
        with self.assertRaises(ValueError):
            retained[0]['world_state']['bookings'][self.foreign]
        self.assert_unchanged(owner, before)
        exported = owner.snapshot(); exported['world_state']['bookings'][self.foreign]['status'] = 'BAD'
        self.assert_unchanged(owner, before)

    def test_nested_output_alias_rejected(self):
        owner = self.owner(); before = protected_bytes(owner.snapshot())
        def alias(stage, capsule):
            if stage == 'after_handler':
                w = capsule.envelope['world_state']; r = w['flight_results'][self.fid]
                original = protected_bytes(r)
                r['quarterly_lineage'] = w['dated_flights'][self.fid]['quarterly_lineage']
                self.assertEqual(protected_bytes(r), original)
        with patch.object(experiment, '_fault', alias):
            result = owner.complete().processing_result
            self.assertFalse(result.succeeded)
            self.assertIn('alias', result.failure.message)
        self.assert_unchanged(owner, before)

    def test_root_replacement_and_unapproved_insert_rejected(self):
        for damage in ('root', 'insert'):
            with self.subTest(damage=damage):
                owner = self.owner(); before = protected_bytes(owner.snapshot())
                def corrupt(stage, capsule):
                    if stage == 'after_handler':
                        if damage == 'root': capsule.envelope['world_state']['bookings'] = {}
                        else: dict.__setitem__(capsule.envelope['world_state']['transactions'], 'foreign', {})
                with patch.object(experiment, '_fault', corrupt):
                    self.assertFalse(owner.complete().processing_result.succeeded)
                self.assert_unchanged(owner, before)

    def test_equal_utc_priority_is_selected_before_completion(self):
        source = deepcopy(self.source)
        kernel.schedule_event(source, event_type='NO_OP', due_at_utc=self.event['due_at_utc'],
            owner_type='aircraft', owner_id=self.operation['actual_aircraft_id'],
            operation_revision=0, priority=99, payload={})
        self.assertTrue(validate_world(source).is_valid)
        owner = experiment.ScopedCompletionOwner(source); self.addCleanup(owner.close)
        self.assertFalse(owner.complete().admitted)
        # Resolve the equal-UTC group through the existing command: stopping
        # after only NO_OP leaves an arrived-but-uncompleted flight at that UTC.
        self.assertEqual(owner.strict_through(self.event['due_at_utc']),
                         kernel.process_events_through(source, self.event['due_at_utc']))
        self.assertEqual(protected_bytes(owner.snapshot()), protected_bytes(source))

    def test_reconciliation_repair_survives_failed_event_as_strict_prefix(self):
        source = deepcopy(self.source)
        eid = next(k for k,e in source['world_state']['pending_events'].items() if e['event_type']=='QUARTERLY_DISPATCH')
        del source['world_state']['pending_events'][eid]
        owner = experiment.ScopedCompletionOwner(source); self.addCleanup(owner.close)
        allocate = fulfilment.allocate_id
        def fail(*args):
            allocate(*args)
            raise RuntimeError('after transaction allocation')
        with patch.object(fulfilment, 'allocate_id', fail):
            actual = owner.complete().processing_result
            expected = kernel.process_next_event(source)
        self.assertFalse(actual.succeeded)
        self.assertEqual(actual, expected)
        self.assertEqual(protected_bytes(owner.snapshot()), protected_bytes(source))
        self.assertEqual(owner.complete().processing_result, kernel.process_next_event(source))
        self.assertEqual(protected_bytes(owner.snapshot()), protected_bytes(source))

    def test_private_roots_share_only_unchanged_records(self):
        owner = self.owner()
        # Test-only inspection; the public API exposes no borrowed root.
        before = owner._ScopedCompletionOwner__base
        self.assertIsNot(before['world_state']['bookings'][self.foreign], self.source['world_state']['bookings'][self.foreign])
        self.assertTrue(owner.complete().processing_result.succeeded)
        after = owner._ScopedCompletionOwner__base
        self.assertIsNot(before, after)
        self.assertIs(before['world_state']['bookings'], after['world_state']['bookings'])
        self.assertIs(before['world_state']['bookings'][self.foreign], after['world_state']['bookings'][self.foreign])
        self.assertIsNot(before['world_state']['dated_flights'][self.fid], after['world_state']['dated_flights'][self.fid])
        self.assertIsNot(before['world_state']['financial_accounts'], after['world_state']['financial_accounts'])

    def test_invalid_membership_unrelated_history_and_alias_rejected_at_entry(self):
        for kind in ('missing', 'additional', 'unrelated', 'alias'):
            with self.subTest(kind=kind):
                source = deepcopy(self.source); w = source['world_state']
                bid = self.operation['source_booking_ids'][0]
                iid = w['bookings'][bid]['itinerary_id']
                foreign = w['bookings'][self.foreign]['itinerary_id']
                if kind == 'missing': w['itineraries'][iid]['dated_flight_ids'] = []
                elif kind == 'additional': w['itineraries'][foreign]['dated_flight_ids'] = [self.fid]
                elif kind == 'unrelated': w['itineraries'][foreign]['quarterly_lineage']['revision'] = True
                else: w['itineraries'][foreign]['quarterly_lineage'] = w['itineraries'][iid]['quarterly_lineage']
                before = protected_bytes(source)
                self.assertFalse(reference_validation(source).is_valid)
                with self.assertRaises(ValueError): experiment.ScopedCompletionOwner(source)
                self.assertEqual(protected_bytes(source), before)

    def test_callbacks_registry_and_compatibility_objects_refused(self):
        called = []
        def callback(): called.append(1)
        with self.assertRaises(ValueError): experiment.ScopedCompletionOwner(self.source, callbacks=(callback,))
        with self.assertRaises(ValueError): experiment.ScopedCompletionOwner(self.source, registry=object())
        class Key(str):
            def __deepcopy__(self, memo): called.append(1); return self
        source = deepcopy(self.source); source[Key('extra')] = None
        with self.assertRaises(ValueError): experiment.ScopedCompletionOwner(source)
        self.assertEqual(called, [])

    def test_input_detachment_and_reusable_private_owner_two_completions(self):
        source = deepcopy(self.source); owner = experiment.ScopedCompletionOwner(source)
        self.addCleanup(owner.close)
        source['world_state']['bookings'][self.foreign]['status'] = 'BAD'
        reference = deepcopy(self.source)
        for index in range(2):
            self.assertEqual(owner.complete().processing_result, kernel.process_next_event(reference))
            self.assertEqual(protected_bytes(owner.snapshot()), protected_bytes(reference))
            if index == 0:
                boundary = min(reference['world_state']['pending_events'].values(), key=kernel._event_key)['due_at_utc']
                self.assertEqual(owner.strict_through(boundary), kernel.process_events_through(reference, boundary))
        self.assertEqual(owner.counts['ownership_world_clones'], 1)
        self.assertEqual(owner.counts['scoped_transactions'], 2)
        self.assertEqual(owner.counts['strict_fallbacks'], 1)

    def test_reconciliation_order_shared_facade_and_save_load(self):
        source = deepcopy(self.source)
        eid = next(k for k,e in source['world_state']['pending_events'].items() if e['event_type']=='QUARTERLY_DISPATCH')
        del source['world_state']['pending_events'][eid]
        self.assertTrue(validate_world(source).is_valid)
        owner = experiment.ScopedCompletionOwner(source); self.addCleanup(owner.close)
        reference = deepcopy(source)
        self.assertEqual(owner.complete().processing_result, kernel.process_next_event(reference))
        self.assertEqual(protected_bytes(owner.snapshot()), protected_bytes(reference))
        shared = deepcopy(self.source)
        self.assertTrue(resolve_until(shared, self.event['due_at_utc'], shared=True).succeeded)
        control = self.owner(); self.assertTrue(control.complete().processing_result.succeeded)
        self.assertEqual(canonical_world(control.snapshot()), canonical_world(shared))
        self.assertEqual(canonical_world(save_reload(control.snapshot())), canonical_world(control.snapshot()))

    def test_unsupported_and_stale_use_explicit_strict_fallback(self):
        owner = self.owner()
        self.assertTrue(owner.complete().processing_result.succeeded)
        before = owner.snapshot()
        attempt = owner.complete()
        self.assertFalse(attempt.admitted)
        reference = deepcopy(before)
        self.assertEqual(owner.strict_next(), kernel.process_next_event(reference))
        # A stale Completion is a valid source only with matching stale lifecycle
        # authority; the existing global validator rejects ad-hoc stale corruption.
        source = deepcopy(self.source)
        source['world_state']['pending_events'][self.event['event_id']]['operation_revision'] = 0
        if validate_world(source).is_valid:
            stale = experiment.ScopedCompletionOwner(source); self.addCleanup(stale.close)
            self.assertFalse(stale.complete().admitted)
            self.assertEqual(stale.strict_next(), kernel.process_next_event(source))
        else:
            with self.assertRaises(ValueError): experiment.ScopedCompletionOwner(source)

    def test_no_event_candidate_or_commit_world_clone_in_scoped_attempt(self):
        from game.scheduling import quarterly_backend, quarterly_boundary
        owner = self.owner()
        with ExitStack() as stack:
            clones = stack.enter_context(patch.object(kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world))
            exports = stack.enter_context(patch.object(experiment, '_clone_runtime_world', wraps=experiment._clone_runtime_world))
            backend = stack.enter_context(patch.object(quarterly_backend, 'deepcopy', wraps=deepcopy))
            publication = stack.enter_context(patch.object(quarterly_boundary, 'deepcopy', wraps=deepcopy))
            result = owner.complete()
        self.assertTrue(result.processing_result.succeeded)
        self.assertEqual(clones.call_count, 0)
        self.assertEqual(exports.call_count, 0)
        self.assertEqual(backend.call_count, 1)  # real retained reconciliation cost
        self.assertEqual(publication.call_count, 0)  # Candidate 1 retained
        self.assertEqual(len(result.copied_records), 9)


if __name__ == '__main__':
    unittest.main()
