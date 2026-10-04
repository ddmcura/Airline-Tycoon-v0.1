"""Stage 3A infrastructure, intermediate validity and strict recovery gates."""

from copy import deepcopy
from functools import partial
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel
from game.simulation.execution_contracts import (
    ExecutionMode, HandlerExecutionContract, SharedExecutionState,
)
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import begin_resolution, resolve_until, ResolutionRequest
from game.simulation import shared_candidate as shared
from game.world_state import validate_world
from tests.resolution_oracle import assert_equivalent, canonical_world, save_reload
from tests.test_stage1_event_kernel import make_world, schedule
from tests.test_simulation_resolver import ph_world, published_pair


DUE = '2026-08-20T05:00:00Z'


def probe_registry(handler, event_type='PROBE'):
    """Private shadow fixture, NOT a production certification API."""
    registry = kernel.EventHandlerRegistry()
    registry.register('NO_OP', kernel._no_op)
    registry.register(event_type, handler)
    registry._execution_contracts[event_type] = HandlerExecutionContract(
        handler, ExecutionMode.SHARED, 'test-shadow-v1',
        'Synthetic deterministic fixture; full per-event validation required.',
        True, (1, 7), shadow_only=True)
    return registry


def record(context):
    context.envelope['world_state']['history']['operations'].append(context.payload['label'])


def drain(request):
    try:
        while not request.finished:
            request.step()
        return request.result
    finally:
        request.close()


class SharedCandidateTests(unittest.TestCase):
    def setUp(self):
        self.world = make_world()

    def test_all_eight_initial_contracts_and_callable_identity(self):
        registry = initialize_runtime_handlers()
        expected = {
            'NO_OP': ExecutionMode.SHARED,
            'DAILY_BOOKING_CHECKPOINT': ExecutionMode.FENCE,
            'STAGE1_WEEKLY_PUBLICATION': ExecutionMode.FENCE,
            'AIRCRAFT_CONTRACT_EXPIRY': ExecutionMode.FENCE,
            'AIRCRAFT_MARKET_ROTATION': ExecutionMode.STRICT,
            'AIRCRAFT_CONTRACT_PAYMENT': ExecutionMode.SHARED,
            'STAGE1_FLIGHT_DEPARTURE': ExecutionMode.SHARED,
            'STAGE1_FLIGHT_COMPLETION': ExecutionMode.SHARED,
        }
        for event_type, mode in expected.items():
            with self.subTest(event_type=event_type):
                contract = registry.execution_contract_for(event_type)
                self.assertIs(contract.handler, registry.handler_for(event_type))
                self.assertIs(contract.mode, mode)

    def test_strict_remains_default_and_stop_callbacks_force_strict(self):
        request = begin_resolution(self.world, DUE)
        self.assertIs(type(request), ResolutionRequest)
        request.close()
        request = begin_resolution(self.world, DUE, shared=True, stop_condition=lambda _: True)
        self.assertIs(type(request), ResolutionRequest)
        request.close()

    def test_batch_sizes_and_irregular_boundaries_exact_world(self):
        for index in range(65):
            schedule(self.world, DUE, priority=index % 3)
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, DUE)
        for size in (1, 2, 8, 64):
            with self.subTest(size=size):
                world = deepcopy(self.world)
                request = begin_resolution(world, DUE, shared=True, max_batch_events=size)
                turn = 0
                while not request.finished:
                    request.max_batch_events = (size, 1, 2)[turn % 3]
                    request.step()
                    self.assertTrue(validate_world(world).is_valid)
                    turn += 1
                self.assertEqual(canonical_world(world), canonical_world(expected))

    def test_shadow_compares_each_intermediate_transition(self):
        registry = probe_registry(record)
        for label in ('a', 'b', 'c'):
            schedule(self.world, DUE, event_type='PROBE', payload={'label': label})
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, DUE, registry=registry)
        with patch.object(kernel, 'process_next_event', wraps=kernel.process_next_event) as oracle:
            result = resolve_until(self.world, DUE, registry=registry, shared=True, shadow=True)
        self.assertTrue(result.succeeded)
        self.assertEqual(oracle.call_count, 3)
        self.assertEqual(self.world, expected)

    def test_shadow_only_probe_cannot_enable_normal_shared_execution(self):
        registry = probe_registry(record)
        schedule(self.world, DUE, event_type='PROBE', payload={'label': 'a'})
        with patch.object(shared, '_shared_transition', wraps=shared._shared_transition) as speculative:
            result = resolve_until(self.world, DUE, registry=registry, shared=True)
        self.assertTrue(result.succeeded)
        self.assertEqual(speculative.call_count, 0)

    def test_generated_same_time_priority_and_sequence(self):
        def generate(context):
            record(context)
            if context.payload.get('generate'):
                context.schedule_event(event_type='PROBE', due_at_utc=DUE,
                    owner_type='airline', owner_id=context.event['owner_id'], priority=0,
                    payload={'label': 'generated'})
        registry = probe_registry(generate)
        schedule(self.world, DUE, event_type='PROBE', priority=5,
                 payload={'label': 'first', 'generate': True})
        schedule(self.world, DUE, event_type='PROBE', priority=5, payload={'label': 'last'})
        result = resolve_until(self.world, DUE, shared=True, shadow=True, registry=registry)
        self.assertTrue(result.succeeded)
        self.assertEqual(self.world['world_state']['history']['operations'],
                         ['first', 'generated', 'last'])

    def test_fence_inside_equal_time_group_flushes_before_strict(self):
        registry = probe_registry(record)
        def fence(context):
            record(context)
        registry.register('FENCE', fence)
        registry._execution_contracts['FENCE'] = HandlerExecutionContract(fence, ExecutionMode.FENCE)
        first = schedule(self.world, DUE, event_type='PROBE', payload={'label': 'first'})
        barrier = schedule(self.world, DUE, event_type='FENCE', payload={'label': 'fence'})
        last = schedule(self.world, DUE, event_type='PROBE', payload={'label': 'last'})
        request = begin_resolution(self.world, DUE, shared=True, shadow=True, registry=registry)
        self.assertEqual(request.step().event_id, first)
        self.assertFalse(request.boundary().current_utc_fully_resolved)
        self.assertEqual(self.world['world_state']['history']['operations'], ['first'])
        self.assertEqual(request.step().event_id, barrier)
        self.assertEqual(request.step().event_id, last)
        self.assertTrue(request.boundary().current_utc_fully_resolved)
        self.assertTrue(drain(request).succeeded)

    def test_unknown_handler_preserves_preceding_shared_prefix(self):
        first = schedule(self.world, DUE)
        bad = schedule(self.world, DUE, event_type='UNKNOWN')
        request = begin_resolution(self.world, DUE, shared=True)
        request.step()
        prefix = deepcopy(self.world)
        result = request.step().processing_result
        self.assertEqual(result.failure.code, 'UNKNOWN_EVENT_TYPE')
        self.assertEqual(result.failure.event_id, bad)
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertEqual(self.world, prefix)

    def test_stale_unknown_handler_is_not_invoked(self):
        event = schedule(self.world, DUE, event_type='UNKNOWN')
        owner = self.world['world_state']['player']['primary_airline_id']
        kernel.set_operation_revision(self.world, owner, 1)
        expected = deepcopy(self.world)
        left = kernel.process_events_through(expected, DUE)
        right = resolve_until(self.world, DUE, shared=True)
        self.assertEqual(left, right)
        self.assertEqual(right.skipped_event_ids, (event,))
        self.assertEqual(self.world, expected)

    def test_custom_builtin_name_does_not_inherit_certification(self):
        registry = kernel.EventHandlerRegistry()
        registry.register('NO_OP', record)
        self.assertIs(registry.execution_contract_for('NO_OP').mode, ExecutionMode.STRICT)
        # Even stale metadata cannot authorize a replacement callable.
        registry._execution_contracts['NO_OP'] = HandlerExecutionContract(
            kernel._no_op, ExecutionMode.SHARED, 'wrong', 'wrong', True, (1,))
        self.assertIs(registry.execution_contract_for('NO_OP').mode, ExecutionMode.STRICT)
        schedule(self.world, DUE, payload={'label': 'custom'})
        with patch.object(shared, '_shared_transition', wraps=shared._shared_transition) as run:
            self.assertTrue(resolve_until(self.world, DUE, registry=registry, shared=True).succeeded)
        self.assertEqual(run.call_count, 0)

    def test_custom_retained_reference_is_detached_and_executes_once(self):
        references = []
        def retain(context):
            references.append(context.envelope)
        registry = kernel.EventHandlerRegistry()
        registry.register('RETAIN', retain)
        schedule(self.world, DUE, event_type='RETAIN')
        self.assertTrue(resolve_until(self.world, DUE, registry=registry,
                                      shared=True, shadow=True).succeeded)
        before = deepcopy(self.world)
        self.assertEqual(len(references), 1)
        references[0]['world_state']['history']['operations'].append('leak')
        self.assertEqual(self.world, before)

    def test_failed_first_middle_last_preserve_exact_strict_prefix(self):
        def fail(context):
            record(context)
            if context.payload['label'] == 'fail':
                raise ValueError('deterministic failure')
        registry = probe_registry(fail)
        for bad_index in (0, 1, 2):
            with self.subTest(bad_index=bad_index):
                world = make_world()
                ids = [schedule(world, DUE, event_type='PROBE', payload={
                    'label': 'fail' if i == bad_index else str(i)}) for i in range(3)]
                expected = deepcopy(world)
                strict = kernel.process_events_through(expected, DUE, registry=registry)
                actual = resolve_until(world, DUE, registry=registry, shared=True, shadow=True)
                self.assertEqual(actual, strict)
                self.assertEqual(world, expected)
                self.assertEqual(actual.completed_event_ids, tuple(ids[:bad_index]))
                self.assertIn(ids[bad_index], world['world_state']['pending_events'])

    def test_invalid_intermediate_state_cannot_be_repaired_later(self):
        def corrupt(context):
            owner = context.event['owner_id']
            context.envelope['world_state']['airlines'][owner]['finance_revision'] = context.payload['revision']
        registry = probe_registry(corrupt)
        first = schedule(self.world, DUE)
        bad = schedule(self.world, DUE, event_type='PROBE', payload={'revision': -1})
        repair = schedule(self.world, DUE, event_type='PROBE', payload={'revision': 0})
        result = resolve_until(self.world, DUE, registry=registry, shared=True, shadow=True)
        self.assertEqual(result.failure.code, 'RESULT_VALIDATION_FAILED')
        self.assertEqual(result.failure.event_id, bad)
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertIn(repair, self.world['world_state']['pending_events'])
        self.assertTrue(validate_world(self.world).is_valid)

    def test_before_event_witness_detects_protected_record_mutation(self):
        def corrupt(context):
            context.envelope['world_state']['pending_events'][context.event['event_id']]['payload']['changed'] = True
        registry = probe_registry(corrupt)
        schedule(self.world, DUE, event_type='PROBE')
        before = deepcopy(self.world)
        result = resolve_until(self.world, DUE, registry=registry, shared=True, shadow=True)
        self.assertEqual(result.failure.code, 'HANDLER_CONTRACT_VIOLATION')
        self.assertEqual(self.world, before)

    def test_final_validation_failure_replays_whole_segment_and_disables(self):
        for _ in range(3):
            schedule(self.world, DUE)
        expected = deepcopy(self.world)
        kernel.process_events_through(expected, DUE)
        invalid = validate_world({})
        state = SharedExecutionState()
        with patch.object(shared, '_validate_batch', return_value=invalid):
            result = resolve_until(self.world, DUE, shared=True, execution_state=state)
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertIsNone(result.failure.event_id)
        self.assertEqual(self.world, expected)
        self.assertFalse(state.enabled)
        self.assertIsNotNone(state.diagnostic)

    def test_shadow_divergence_preserves_strict_result_then_falls_back(self):
        registry = probe_registry(record)
        schedule(self.world, DUE, event_type='PROBE', payload={'label': 'a'})
        state = SharedExecutionState()
        original = shared._shared_transition
        def defective(candidate, *args):
            result = original(candidate, *args)
            candidate['world_state']['history']['operations'].append('optimizer defect')
            return result
        with patch.object(shared, '_shared_transition', side_effect=defective):
            result = resolve_until(self.world, DUE, registry=registry, shared=True,
                                   shadow=True, execution_state=state)
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertEqual(self.world['world_state']['history']['operations'], ['a'])
        schedule(self.world, DUE, event_type='PROBE', payload={'label': 'b'})
        with patch.object(shared, '_shared_transition', wraps=original) as speculative:
            result = resolve_until(self.world, DUE, registry=registry, shared=True,
                                   shadow=True, execution_state=state)
        self.assertTrue(result.succeeded)
        self.assertEqual(speculative.call_count, 0)
        self.assertEqual(self.world['world_state']['history']['operations'], ['a', 'b'])

    def test_event_ceiling_is_request_wide_across_flushes(self):
        for _ in range(8):
            schedule(self.world, DUE)
        expected = deepcopy(self.world)
        strict = kernel.process_events_through(expected, DUE, max_events=5)
        actual = resolve_until(self.world, DUE, shared=True, max_batch_events=2, max_events=5)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)

    def test_generated_ceiling_is_request_wide_across_flushes(self):
        def generate(context):
            context.schedule_event(event_type='PROBE', due_at_utc=DUE,
                owner_type='airline', owner_id=context.event['owner_id'])
        registry = probe_registry(generate)
        schedule(self.world, DUE, event_type='PROBE')
        expected = deepcopy(self.world)
        strict = kernel.process_events_through(expected, DUE, registry=registry, max_generated_events=3)
        actual = resolve_until(self.world, DUE, registry=registry, shared=True, shadow=True,
                               max_batch_events=2, max_generated_events=3)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)

    def test_requested_boundary_and_pause_preserve_committed_prefix(self):
        kernel.set_clock_mode(self.world, 'NORMAL')
        ids = [schedule(self.world, DUE) for _ in range(4)]
        request = begin_resolution(self.world, DUE, shared=True, max_batch_events=2)
        before = deepcopy(self.world)
        self.assertIsNone(request.step(boundary_requested=True).event_id)
        self.assertEqual(self.world, before)
        request.step()
        self.assertEqual(request._completed_ids, ids[:2])
        kernel.set_clock_mode(self.world, 'PAUSED')
        self.assertEqual(request.step(management_changed=True).status, 'STOPPED')
        self.assertEqual(set(self.world['world_state']['pending_events']), set(ids[2:]))

    def test_management_refresh_preserves_limits_and_updated_queue(self):
        first = schedule(self.world, DUE)
        request = begin_resolution(self.world, DUE, shared=True, max_batch_events=1, max_events=2)
        request.step()
        next_id = schedule(self.world, DUE, priority=1)
        last = schedule(self.world, DUE, priority=2)
        progress = request.step(management_changed=True)
        result = (progress.processing_result if progress.finished
                  else request.step().processing_result)
        self.assertEqual(result.completed_event_ids, (first, next_id))
        self.assertEqual(result.failure.event_id, last)

    def test_close_retains_no_candidate_and_does_not_undo_prefix(self):
        for _ in range(3):
            schedule(self.world, DUE)
        request = begin_resolution(self.world, DUE, shared=True, max_batch_events=2)
        request.step()
        self.assertNotIn('candidate', request.__dict__)
        prefix = deepcopy(self.world)
        request.close()
        self.assertEqual(self.world, prefix)
        self.assertEqual(len(self.world['world_state']['pending_events']), 1)

    def test_save_load_between_unresolved_equal_time_batches(self):
        self.world = ph_world()
        due = '2026-09-01T01:00:00Z'
        for _ in range(3):
            schedule(self.world, due)
        request = begin_resolution(self.world, due, shared=True, max_batch_events=2)
        request.step()
        restored = save_reload(self.world)
        self.assertEqual(restored, self.world)
        for name in ('candidate', 'execution_contracts', 'execution_state', 'max_batch_events'):
            self.assertNotIn(name, canonical_world(restored))
        self.assertTrue(drain(request).succeeded)
        self.assertTrue(resolve_until(restored, due, shared=True).succeeded)
        self.assertEqual(self.world, restored)

    def test_dictionary_order_does_not_change_result(self):
        for priority in (3, 0, 2, 1):
            schedule(self.world, DUE, priority=priority)
        reordered = deepcopy(self.world)
        pending = reordered['world_state']['pending_events']
        reordered['world_state']['pending_events'] = dict(reversed(tuple(pending.items())))
        resolve_until(self.world, DUE, shared=True, max_batch_events=2)
        resolve_until(reordered, DUE, shared=True, max_batch_events=8)
        self.assertEqual(canonical_world(self.world), canonical_world(reordered))

    def test_stage2_reads_never_see_candidate_and_rebind_after_commit(self):
        with tempfile.TemporaryDirectory() as root:
            session = Stage1Session(save_root=root)
            session.new_game('Owner', 'Candidate Air', 'MNL')
            due = session.world['simulation']['time_utc']
            for _ in range(2):
                schedule(session.world, due)
            session._management_changed()
            session.fleet()
            old_context = session._read_views
            before = deepcopy(session.world)
            original = shared._validate_batch
            def inspect(candidate):
                self.assertEqual(session.world, before)
                self.assertIs(session._read_views, old_context)
                session.fleet()
                self.assertIsNot(candidate, session.world)
                return original(candidate)
            with patch.object(shared, '_validate_batch', side_effect=inspect):
                request = begin_resolution(session.world, due, shared=True)
                request.step()
            self.assertFalse(old_context.matches(session.world, session.progression_revision))
            session._mark_progress()
            self.assertIsNot(session._read_views, old_context)
            self.assertTrue(session._read_views.matches(session.world, session.progression_revision))
            request.close()
            session.save_manual()
            session.load_saved(session.career_id)
            self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')

    def test_gameplay_equivalence_stays_strict_through_opt_in_request(self):
        base = published_pair(ph_world(), continuous=True)
        assert_equivalent(self, base, '2026-09-07T04:00:00Z',
            ['2026-09-06T16:00:00Z', '2026-09-07T00:00:00Z'],
            save_at='2026-09-07T00:00:01Z',
            resolver=partial(resolve_until, shared=True, shadow=True),
            request_factory=partial(begin_resolution, shared=True, shadow=True))

    def test_recovery_finds_first_invalid_transition_not_last(self):
        def corrupt(context):
            record(context)
            if context.payload['label'] == 'bad':
                context.envelope['world_state']['airlines'][context.event['owner_id']]['finance_revision'] = -1
        registry = probe_registry(corrupt)
        ids = [schedule(self.world, DUE, event_type='PROBE', payload={'label': label})
               for label in ('good', 'bad', 'last')]
        expected = deepcopy(self.world)
        strict = kernel.process_events_through(expected, DUE, registry=registry)
        # Deliberate optimizer defect, confined to this test: bypass its per-event
        # gate to exercise final-gate recovery. No such mode exists in the engine.
        def defective(candidate, event_id, handler):
            return kernel._apply_handler_candidate(kernel._event_contract_witness(candidate),
                                                    candidate, event_id, handler)
        with patch.object(shared, '_shared_transition', side_effect=defective):
            actual = resolve_until(self.world, DUE, registry=registry, shared=True, shadow=True)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)
        self.assertEqual(actual.completed_event_ids, (ids[0],))
        self.assertEqual(actual.failure.event_id, ids[1])

    def test_optimizer_exception_recovers_and_disables_without_losing_events(self):
        event = schedule(self.world, DUE)
        state = SharedExecutionState()
        with patch.object(shared, '_shared_transition', side_effect=RuntimeError('optimizer defect')):
            result = resolve_until(self.world, DUE, shared=True, execution_state=state)
        self.assertEqual(result.completed_event_ids, (event,))
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertFalse(state.enabled)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_normal_session_runtime_uses_bounded_shared_execution(self):
        with tempfile.TemporaryDirectory() as root:
            now = [0]
            session = Stage1Session(save_root=root, runtime_clock=lambda: now[0])
            session.new_game('Owner', 'Strict Runtime', 'MNL')
            due = session.world['simulation']['time_utc']
            ids = [schedule(session.world, due) for _ in range(3)]
            session.resume()
            now[0] = 1_000_000_000
            session.pump()
            self.assertIs(type(session.runtime.work), shared.SharedResolutionRequest)
            history = session.world['world_state']['event_history']
            self.assertEqual([event for event in ids if event in history], ids)
            session.close()

    def test_shadow_real_fallback_calls_have_unchanged_transaction_counts(self):
        registry = kernel.EventHandlerRegistry()
        registry.register('CUSTOM', record)
        for label in ('a', 'b'):
            schedule(self.world, DUE, event_type='CUSTOM', payload={'label': label})
        counts = []
        outputs = []
        for shared_enabled in (False, True):
            world = deepcopy(self.world)
            with patch.object(kernel, 'validate_world', wraps=kernel.validate_world) as validations, patch.object(
                    kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones:
                result = resolve_until(world, DUE, shared=shared_enabled, shadow=True, registry=registry)
            self.assertTrue(result.succeeded)
            counts.append((validations.call_count, clones.call_count))
            outputs.append(world)
        self.assertEqual(counts[0][1], counts[1][1])
        self.assertEqual(counts[0][1], 4)
        self.assertEqual(outputs[0], outputs[1])

    def test_forged_production_domain_certificate_is_ineligible_in_stage3a(self):
        registry = probe_registry(record)
        registry._execution_contracts['PROBE'] = HandlerExecutionContract(
            record, ExecutionMode.SHARED, 'forged', 'not approved', True, (1,))
        schedule(self.world, DUE, event_type='PROBE', payload={'label': 'strict'})
        with patch.object(shared, '_shared_transition', wraps=shared._shared_transition) as run:
            result = resolve_until(self.world, DUE, shared=True, shadow=True, registry=registry)
        self.assertTrue(result.succeeded)
        self.assertEqual(run.call_count, 0)

    def test_final_validation_recovery_stops_at_strict_failure_with_prefix(self):
        ids = [schedule(self.world, DUE) for _ in range(3)]
        original = kernel._execute_event
        def strict_fault(world, event_id, registry):
            if event_id == ids[1]:
                return None, kernel.EventFailure('HANDLER_FAILED', 'strict failure', event_id), ()
            return original(world, event_id, registry)
        expected = deepcopy(self.world)
        with patch.object(kernel, '_execute_event', side_effect=strict_fault):
            strict = kernel.process_events_through(expected, DUE)
            with patch.object(shared, '_validate_batch', return_value=validate_world({})):
                actual = resolve_until(self.world, DUE, shared=True)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)
        self.assertEqual(actual.completed_event_ids, (ids[0],))
        self.assertEqual(actual.failure.event_id, ids[1])

    def test_valid_handler_pause_flushes_without_processing_next_event(self):
        def pause(context):
            context.pause()
        registry = probe_registry(pause)
        kernel.set_clock_mode(self.world, 'NORMAL')
        first = schedule(self.world, DUE, event_type='PROBE')
        next_id = schedule(self.world, DUE)
        expected = deepcopy(self.world)
        strict = kernel.process_events_through(expected, DUE, registry=registry)
        actual = resolve_until(self.world, DUE, registry=registry, shared=True, shadow=True)
        self.assertEqual(actual, strict)
        self.assertEqual(self.world, expected)
        self.assertEqual(actual.completed_event_ids, (first,))
        self.assertIn(next_id, self.world['world_state']['pending_events'])

    def test_optimizer_failure_is_not_hidden_by_successful_strict_pause(self):
        def pause(context):
            context.pause()
        registry = probe_registry(pause)
        kernel.set_clock_mode(self.world, 'NORMAL')
        first = schedule(self.world, DUE, event_type='PROBE')
        state = SharedExecutionState()
        with patch.object(shared, '_shared_transition', side_effect=RuntimeError('optimizer defect')):
            result = resolve_until(self.world, DUE, registry=registry, shared=True,
                                   shadow=True, execution_state=state)
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertEqual(self.world['simulation']['clock_state'], 'PAUSED')
        self.assertFalse(state.enabled)

    def test_target_before_at_after_and_clock_only_boundary(self):
        for target in ('2026-08-20T04:59:59Z', DUE, '2026-08-20T05:00:01Z'):
            with self.subTest(target=target):
                world = make_world()
                schedule(world, DUE)
                expected = deepcopy(world)
                strict = kernel.process_events_through(expected, target)
                actual = resolve_until(world, target, shared=True)
                self.assertEqual(actual, strict)
                self.assertEqual(world, expected)
        request = begin_resolution(make_world(), DUE, shared=True)
        request.step()
        self.assertIsNone(request.boundary().last_committed_event_id)
        self.assertTrue(request.boundary().current_utc_fully_resolved)

    def test_shadow_reference_exception_recovers_without_leaking_candidate(self):
        first = schedule(self.world, DUE)
        state = SharedExecutionState()
        with patch.object(kernel, 'process_next_event', side_effect=RuntimeError('oracle defect')):
            result = resolve_until(self.world, DUE, shared=True, shadow=True, execution_state=state)
        self.assertEqual(result.completed_event_ids, (first,))
        self.assertEqual(result.failure.code, 'OPTIMIZER_DIVERGENCE')
        self.assertFalse(state.enabled)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_noop_callable_alias_does_not_inherit_builtin_classification(self):
        registry = kernel.EventHandlerRegistry()
        registry.register('CUSTOM_ALIAS', kernel._no_op)
        self.assertIs(registry.execution_contract_for('CUSTOM_ALIAS').mode, ExecutionMode.STRICT)
        schedule(self.world, DUE, event_type='CUSTOM_ALIAS')
        with patch.object(shared, '_shared_transition', wraps=shared._shared_transition) as run:
            result = resolve_until(self.world, DUE, registry=registry, shared=True)
        self.assertTrue(result.succeeded)
        self.assertEqual(run.call_count, 0)


if __name__ == '__main__':
    unittest.main()
