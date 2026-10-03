"""Stage 3B transition proof and exact-world certification gates."""
from copy import deepcopy
from functools import partial
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel, shared_candidate
from game.simulation.execution_contracts import ExecutionMode, SharedExecutionState
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution, resolve_until
from game.world_state import validate_world, payment_validation as proof
from tests.payment_fixtures import payment_world
from tests.resolution_oracle import assert_equivalent, canonical_world, save_reload


def payment_ids(world):
    return [e['event_id'] for e in sorted(world['world_state']['pending_events'].values(),
        key=kernel._event_key) if e['event_type'] == 'AIRCRAFT_CONTRACT_PAYMENT']


class PaymentProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.target = payment_world(3)

    def setUp(self):
        self.world = deepcopy(self.base)
        initialize_runtime_handlers()

    def transition(self):
        event_id = payment_ids(self.world)[0]
        before = kernel._event_contract_witness(self.world)
        witness = proof.capture_payment_transition(self.world, event_id, before)
        handler = kernel.DEFAULT_EVENT_HANDLERS.handler_for('AIRCRAFT_CONTRACT_PAYMENT')
        outcome, failure, generated = kernel._apply_handler_candidate(before, self.world, event_id, handler)
        self.assertIsNone(failure)
        self.assertEqual(outcome, 'COMPLETED')
        return witness, event_id, generated

    def test_proof_matches_fully_validated_successor(self):
        for _ in range(3):
            witness, event_id, generated = self.transition()
            proof.validate_payment_transition(witness, self.world, event_id, generated)
            self.assertTrue(validate_world(self.world).is_valid)

    def test_each_permitted_record_and_unrelated_structure_is_protected(self):
        witness, event_id, generated = self.transition()
        good = deepcopy(self.world)
        contract_id = witness['event']['owner_id']
        airline_id = witness['contract']['airline_id']
        tx_id = witness['transaction']['transaction_id']
        account_id = witness['transaction']['entries'][0]['account_id']
        next_id = generated[0]
        paths = [
            ('world_state', 'aircraft_contracts', contract_id, 'paid_installments'),
            ('world_state', 'aircraft_contracts', contract_id, 'principal_paid_minor'),
            ('world_state', 'aircraft_contracts', contract_id, 'financing_paid_minor'),
            ('world_state', 'aircraft_contracts', contract_id, 'airline_id'),
            ('world_state', 'aircraft_contracts', contract_id, 'status'),
            ('world_state', 'aircraft_contracts', contract_id, 'expires_at_utc'),
            ('world_state', 'airlines', airline_id, 'finance_revision'),
            ('world_state', 'airlines', airline_id, 'display_name'),
            ('world_state', 'financial_accounts', account_id, 'balance_minor'),
            ('world_state', 'transactions', tx_id, 'source_id'),
            ('world_state', 'transactions', tx_id, 'occurred_at_utc'),
            ('world_state', 'pending_events', next_id, 'payload'),
            ('world_state', 'pending_events', next_id, 'order_key'),
            ('world_state', 'event_history', event_id, 'status'),
            ('simulation', 'event_order_cursor'),
            ('simulation', 'operation_revisions', contract_id),
            ('deterministic_state', 'id_allocator', 'next_by_type', 'transaction'),
            ('deterministic_state', 'id_allocator', 'next_by_type', 'aircraft'),
            ('metadata', 'world_created_at_utc'),
            ('ui_state', 'current_focus'),
        ]
        for path in paths:
            with self.subTest(path=path):
                world = deepcopy(good)
                parent = world
                for key in path[:-1]: parent = parent[key]
                parent[path[-1]] = 'wrong'
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    proof.validate_payment_transition(witness, world, event_id, generated)

    def test_boolean_and_float_cannot_impersonate_exact_minor_units_or_revisions(self):
        witness, event_id, generated = self.transition()
        for value in (True, 1.0):
            with self.subTest(value=value):
                world = deepcopy(self.world)
                world['world_state']['aircraft_contracts'][witness['event']['owner_id']]['paid_installments'] = value
                with self.assertRaises(ValueError):
                    proof.validate_payment_transition(witness, world, event_id, generated)

    def test_repaired_later_transition_cannot_hide_first_invalid_payment(self):
        witness, event_id, generated = self.transition()
        contract = self.world['world_state']['aircraft_contracts'][witness['event']['owner_id']]
        expected = contract['principal_paid_minor']
        contract['principal_paid_minor'] += 1
        with self.assertRaisesRegex(ValueError, 'contract/progress'):
            proof.validate_payment_transition(witness, self.world, event_id, generated)
        contract['principal_paid_minor'] = expected
        self.assertTrue(validate_world(self.world).is_valid)

    def test_existing_journal_pending_and_history_records_are_immutable(self):
        self.transition()
        witness, event_id, generated = self.transition()
        for name in ('transactions', 'pending_events', 'event_history'):
            with self.subTest(collection=name):
                world = deepcopy(self.world)
                key = next(key for key in world['world_state'][name]
                    if key not in {event_id, generated[0], witness['transaction']['transaction_id']})
                world['world_state'][name][key]['extra'] = 'unauthorized'
                with self.assertRaisesRegex(ValueError, 'protected structure'):
                    proof.validate_payment_transition(witness, world, event_id, generated)

    def test_approved_financing_cent_remainder_witnesses(self):
        from game.aircraft_market.step5 import payment_terms
        contract = deepcopy(next(iter(self.base['world_state']['aircraft_contracts'].values())))
        # Existing approved USD 100m / two-year worked example, integer cents.
        contract.update(contract_type='LEASE_TO_OWN', aircraft_value_minor=10_000_000_000,
            term_years=2, total_installments=24, principal_base_minor=416_666_666,
            principal_remainder_installments=16, monthly_financing_minor=85_000_000,
            monthly_rent_minor=0)
        for paid, principal in ((0, 416_666_667), (15, 416_666_667),
                                (16, 416_666_666), (23, 416_666_666)):
            with self.subTest(paid=paid):
                contract['paid_installments'] = paid
                terms = payment_terms(contract)
                self.assertEqual(terms['principal'], principal)
                self.assertEqual(terms['financing'], 85_000_000)
                self.assertEqual(terms['entries'], (('aircraft_assets', principal),
                    ('operating_expenses', 85_000_000), ('cash', -(principal + 85_000_000))))
                self.assertEqual(terms['next_due'] is None, paid == 23)


class PaymentSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.target = payment_world(3)

    def setUp(self):
        initialize_runtime_handlers()
        self.world = deepcopy(self.base)

    def test_certificate_is_exact_callable_version_and_proof_bound(self):
        registry = initialize_runtime_handlers()
        contract = registry.execution_contract_for('AIRCRAFT_CONTRACT_PAYMENT')
        self.assertIs(contract.mode, ExecutionMode.SHARED)
        self.assertTrue(proof.is_payment_certificate(contract))
        self.assertEqual(contract.version, proof.VERSION)
        custom = kernel.EventHandlerRegistry()
        custom.register('AIRCRAFT_CONTRACT_PAYMENT', lambda context: None)
        custom._execution_contracts['AIRCRAFT_CONTRACT_PAYMENT'] = contract
        self.assertIs(custom.execution_contract_for('AIRCRAFT_CONTRACT_PAYMENT').mode, ExecutionMode.STRICT)

    def test_other_handlers_keep_classification(self):
        registry = initialize_runtime_handlers()
        for name in ('STAGE1_FLIGHT_DEPARTURE', 'STAGE1_FLIGHT_COMPLETION', 'AIRCRAFT_MARKET_ROTATION'):
            self.assertIs(registry.execution_contract_for(name).mode, ExecutionMode.STRICT)
        for name in ('DAILY_BOOKING_CHECKPOINT', 'STAGE1_WEEKLY_PUBLICATION', 'AIRCRAFT_CONTRACT_EXPIRY'):
            self.assertIs(registry.execution_contract_for(name).mode, ExecutionMode.FENCE)

    def test_batch_sizes_shadow_irregular_boundaries_and_complete_world(self):
        expected = deepcopy(self.world)
        strict = kernel.process_events_through(expected, self.target)
        for shadow in (False, True):
            for size in (1, 2, 8, 64):
                with self.subTest(shadow=shadow, size=size):
                    world = deepcopy(self.world)
                    request = begin_resolution(world, self.target, shared=True, shadow=shadow, max_batch_events=size)
                    turn = 0
                    while not request.finished:
                        request.max_batch_events = (size, 1, 2)[turn % 3]
                        request.step()
                        self.assertTrue(validate_world(world).is_valid)
                        turn += 1
                    self.assertEqual(request.result, strict)
                    self.assertEqual(canonical_world(world), canonical_world(expected))

    def test_single_candidate_reduces_validation_and_clone_counts(self):
        with patch.object(kernel, 'validate_world', wraps=kernel.validate_world) as validations, patch.object(
                kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones:
            result = resolve_until(self.world, self.target, shared=True)
        self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(validations.call_count, 3)
        self.assertEqual(clones.call_count, 2)
        self.assertEqual(len(result.completed_event_ids), 3)

    def test_full_oracle_partitions_and_saved_continuation(self):
        assert_equivalent(self, self.world, self.target, [self.world['simulation']['time_utc']],
            save_at=self.target, resolver=partial(resolve_until, shared=True, shadow=True),
            request_factory=partial(begin_resolution, shared=True, shadow=True))

    def test_save_after_partial_equal_time_prefix_has_no_runtime_state(self):
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, self.target)
        request = begin_resolution(self.world, self.target, shared=True, max_batch_events=1)
        request.step()
        self.assertFalse(request.boundary().current_utc_fully_resolved)
        restored = save_reload(self.world)
        self.assertEqual(restored, self.world)
        request.close()
        self.assertTrue(resolve_until(restored, self.target, shared=True).succeeded)
        self.assertEqual(restored, expected)
        for field in ('protected', 'execution_contracts', 'capture_transition', 'candidate_heap'):
            self.assertNotIn(field, canonical_world(restored))

    def test_custom_payment_handler_executes_once_strict(self):
        calls = []
        from game.aircraft_market.step5 import _payment_handler
        def custom(context):
            calls.append(context.event['event_id'])
            _payment_handler(context)
        registry = kernel.EventHandlerRegistry()
        registry.register('AIRCRAFT_CONTRACT_PAYMENT', custom)
        result = resolve_until(self.world, self.target, registry=registry, shared=True, shadow=True)
        self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(calls, list(result.completed_event_ids))

    def test_unsupported_payload_stays_strict_without_false_divergence(self):
        event = self.world['world_state']['pending_events'][payment_ids(self.world)[0]]
        event['payload'] = {'historical': 'payment handler ignores this'}
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertFalse(proof.supports_payment_transition(self.world, event))
        expected = deepcopy(self.world)
        strict = kernel.process_events_through(expected, self.target)
        actual = resolve_until(self.world, self.target, shared=True)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)

    def test_first_middle_final_real_payment_failure_preserves_prefix(self):
        from game.aircraft_market import step5
        posting = step5.post_aircraft_market_transaction
        ids = payment_ids(self.world)
        for bad in ids:
            with self.subTest(bad=bad):
                world = deepcopy(self.world)
                owner = world['world_state']['pending_events'][bad]['owner_id']
                def fail(candidate, **kwargs):
                    if kwargs['source_id'] == owner: raise ValueError('deliberate payment failure')
                    return posting(candidate, **kwargs)
                expected = deepcopy(world)
                with patch.object(step5, 'post_aircraft_market_transaction', side_effect=fail):
                    strict = kernel.process_events_through(expected, self.target)
                    actual = resolve_until(world, self.target, shared=True, shadow=True)
                self.assertEqual(actual, strict)
                self.assertEqual(world, expected)
                self.assertIn(bad, world['world_state']['pending_events'])

    def test_transition_proof_failure_replays_once_then_disables(self):
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, self.target)
        state = SharedExecutionState()
        with patch.object(proof, 'validate_payment_transition', side_effect=ValueError('proof defect')):
            initialize_runtime_handlers()
            result = resolve_until(self.world, self.target, shared=True, execution_state=state)
        initialize_runtime_handlers()
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertIsNone(result.failure.event_id)
        self.assertFalse(state.enabled)
        # Only the first attempted payment was replayed; complete remaining work strictly.
        self.assertEqual(len(result.completed_event_ids), 1)
        self.assertTrue(resolve_until(self.world, self.target, shared=True, execution_state=state).succeeded)
        self.assertEqual(self.world, expected)

    def test_final_gate_failure_replays_every_payment_without_duplicate_effects(self):
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, self.target)
        state = SharedExecutionState()
        with patch.object(shared_candidate, '_validate_batch', return_value=validate_world({})):
            result = resolve_until(self.world, self.target, shared=True, execution_state=state)
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertFalse(state.enabled)
        self.assertEqual(self.world, expected)
        self.assertEqual(len(result.completed_event_ids), 3)

    def test_first_invalid_transition_cannot_wait_for_a_later_repair(self):
        primitive = kernel._apply_handler_candidate
        ids = payment_ids(self.world)
        touched = []
        def defect(before, candidate, event_id, handler):
            outcome = primitive(before, candidate, event_id, handler)
            if event_id == ids[1]:
                owner = candidate['world_state']['event_history'][event_id]['owner_id']
                candidate['world_state']['aircraft_contracts'][owner]['principal_paid_minor'] += 1
                touched.append(event_id)
            elif event_id == ids[2]:
                # A forbidden later transition would repair the earlier invalid OP progress.
                owner = candidate['world_state']['event_history'][ids[1]]['owner_id']
                candidate['world_state']['aircraft_contracts'][owner]['principal_paid_minor'] = 0
                touched.append(event_id)
            return outcome
        # Demonstrate why validate-at-end is insufficient: without the proof,
        # the deliberately faulty third transition repairs the second and the
        # final complete world looks valid. This bypass exists only in this test.
        speculative = deepcopy(self.world)
        handler = kernel.DEFAULT_EVENT_HANDLERS.handler_for('AIRCRAFT_CONTRACT_PAYMENT')
        for event_id in ids:
            outcome, failure, _ = defect(kernel._event_contract_witness(speculative),
                                         speculative, event_id, handler)
            self.assertIsNone(failure)
        self.assertTrue(validate_world(speculative).is_valid)
        touched.clear()
        expected = deepcopy(self.world)
        with patch.object(kernel, '_apply_handler_candidate', side_effect=defect):
            strict = kernel.process_events_through(expected, self.target)
            actual = resolve_until(self.world, self.target, shared=True)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)
        self.assertEqual(actual.completed_event_ids, (ids[0],))
        self.assertEqual(actual.failure.event_id, ids[1])
        self.assertIn(ids[2], self.world['world_state']['pending_events'])
        self.assertNotIn(ids[2], touched)

    def test_stage2_finance_never_publishes_candidate_and_rebinds_after_commit(self):
        with tempfile.TemporaryDirectory() as root:
            session = Stage1Session(save_root=root)
            session.world = deepcopy(self.world)
            session.finances()
            old = session._read_views
            before = deepcopy(session.world)
            final_gate = shared_candidate._validate_batch
            def inspect(candidate):
                self.assertEqual(session.world, before)
                session.finances()
                self.assertIs(session._read_views, old)
                return final_gate(candidate)
            with patch.object(shared_candidate, '_validate_batch', side_effect=inspect):
                request = begin_resolution(session.world, self.target, shared=True)
                request.step()
            self.assertFalse(old.matches(session.world, session.progression_revision))
            session._mark_progress()
            self.assertIsNot(session._read_views, old)
            self.assertTrue(session._read_views.matches(session.world, session.progression_revision))
            self.assertNotEqual(session.world, before)
            session.finances()
            request.close()

    def test_negative_cash_is_exact_and_allowed(self):
        from game.economy.acquisition import purchase_accounts
        airline = self.world['world_state']['player']['primary_airline_id']
        purchase_accounts(self.world['world_state'], airline)['cash']['balance_minor'] = 0
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, self.target)
        self.assertTrue(resolve_until(self.world, self.target, shared=True, shadow=True).succeeded)
        self.assertEqual(self.world, expected)
        self.assertLess(purchase_accounts(self.world['world_state'], airline)['cash']['balance_minor'], 0)

    def test_schema6_compatibility_uses_same_proof(self):
        self.world['metadata']['save_schema_version'] = 6
        self.world['simulation']['configuration'].pop('maintenance')
        self.assertTrue(validate_world(self.world).is_valid)
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, self.target)
        self.assertTrue(resolve_until(self.world, self.target, shared=True, shadow=True).succeeded)
        self.assertEqual(self.world, expected)

    def test_final_gate_recovery_returns_strict_failure_with_real_payment_prefix(self):
        ids = payment_ids(self.world)
        execute = kernel._execute_event
        def strict_failure(world, event_id, registry):
            if event_id == ids[1]:
                return None, kernel.EventFailure('HANDLER_FAILED', 'strict recovery failure', event_id), ()
            return execute(world, event_id, registry)
        expected = deepcopy(self.world)
        with patch.object(kernel, '_execute_event', side_effect=strict_failure):
            strict = kernel.process_events_through(expected, self.target)
            with patch.object(shared_candidate, '_validate_batch', return_value=validate_world({})):
                actual = resolve_until(self.world, self.target, shared=True)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)
        self.assertEqual(actual.completed_event_ids, (ids[0],))

    def test_shadow_disagreement_returns_only_valid_strict_payment(self):
        state = SharedExecutionState()
        transition = shared_candidate._shared_transition
        def defective(candidate, *args, **kwargs):
            outcome = transition(candidate, *args, **kwargs)
            owner = candidate['world_state']['player']['primary_airline_id']
            candidate['world_state']['airlines'][owner]['display_name'] += '?'
            return outcome
        expected = deepcopy(self.world)
        kernel.process_next_event(expected)
        with patch.object(shared_candidate, '_shared_transition', side_effect=defective):
            result = resolve_until(self.world, self.target, shared=True, shadow=True, execution_state=state)
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertEqual(self.world, expected)
        self.assertFalse(state.enabled)

    def test_equal_looking_custom_callable_or_proof_cannot_spoof_identity(self):
        from dataclasses import replace
        certificate = initialize_runtime_handlers().execution_contract_for('AIRCRAFT_CONTRACT_PAYMENT')
        class EqualCallable:
            def __call__(self, context): pass
            def __eq__(self, other): return True
        for forged in (replace(certificate, handler=EqualCallable()),
                       replace(certificate, validate_transition=lambda *args: None)):
            self.assertFalse(proof.is_payment_certificate(forged))


class PaymentBoundaryTests(unittest.TestCase):
    def test_actual_final_payment_expiry_fence_equal_time_and_ownership(self):
        world, target = payment_world(2, final=True)
        expected = deepcopy(world)
        strict = kernel.process_events_through(expected, target)
        request = begin_resolution(world, target, shared=True, shadow=True)
        first = request.step()
        self.assertEqual(first.completed_event_count, 2)
        self.assertFalse(request.boundary().current_utc_fully_resolved)
        self.assertEqual({e['event_type'] for e in world['world_state']['pending_events'].values()
            if e['due_at_utc'] <= target}, {'AIRCRAFT_CONTRACT_EXPIRY'})
        self.assertTrue(all(row['next_payment_at_utc'] is None for row in world['world_state']['aircraft_contracts'].values()))
        while not request.finished: request.step()
        self.assertEqual(request.result, strict)
        self.assertEqual(world, expected)
        contracts = world['world_state']['aircraft_contracts'].values()
        self.assertEqual({row['status'] for row in contracts}, {'COMPLETED', 'RETURNED'})

    def test_dense_64_payments_one_detached_batch_exact_oracle(self):
        world, target = payment_world(64)
        expected = deepcopy(world)
        kernel.process_events_through(expected, target)
        with patch.object(kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones:
            request = begin_resolution(world, target, shared=True, max_batch_events=64)
            progress = request.step()
        self.assertEqual(progress.completed_event_count, 64)
        self.assertEqual(clones.call_count, 2)
        while not request.finished: request.step()
        self.assertEqual(world, expected)
        self.assertTrue(validate_world(world).is_valid)

    def test_same_contract_multiple_anniversaries_and_target_partitions(self):
        from game.world_state.timestamps import format_utc, parse_canonical_utc
        from game.aircraft_market.step5 import _add_months
        world, target = payment_world(1)
        expected = deepcopy(world)
        first = parse_canonical_utc(target)
        for offset in range(3):
            target = format_utc(_add_months(first, offset))
            self.assertTrue(kernel.process_events_through(expected, target).succeeded)
            self.assertTrue(resolve_until(world, target, shared=True, shadow=True).succeeded)
            self.assertEqual(world, expected)
        row = next(iter(world['world_state']['aircraft_contracts'].values()))
        self.assertEqual(row['paid_installments'], 3)

    def test_near_time_partitions_and_saved_payment_prefix_exact_oracle(self):
        from datetime import timedelta
        from game.world_state.timestamps import format_utc, parse_canonical_utc
        world, target = payment_world(4, near=True)
        end = parse_canonical_utc(target)
        first_boundary = format_utc(end - timedelta(seconds=2))
        assert_equivalent(self, world, target,
            [first_boundary, format_utc(end - timedelta(seconds=1))], save_at=first_boundary,
            resolver=partial(resolve_until, shared=True, shadow=True),
            request_factory=partial(begin_resolution, shared=True, shadow=True))


if __name__ == '__main__':
    unittest.main()
