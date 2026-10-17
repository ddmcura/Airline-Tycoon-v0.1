"""Bounded Phase 3F atomicity, retained-request and identity proof."""
from contextlib import ExitStack
from copy import deepcopy
import inspect
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.simulation import kernel
from game.scheduling import quarterly_backend, quarterly_boundary
from game.world_state import validate_world
from game.world_state.flight_proof_witness import protected_bytes
from tests import scoped_completion_experiment as scoped
from tests import stable_root_publication_experiment as proof
from tests import test_scoped_completion_experiment as scoped_tests
from tests.test_stage1_runtime import Clock
from tests.test_closed_session import mutable_ids


class StableRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scoped_tests.ScopedCompletionTests.setUpClass()
        cls.source = scoped_tests.ScopedCompletionTests.source
        cls.event = scoped_tests.ScopedCompletionTests.event
        cls.fid = scoped_tests.ScopedCompletionTests.fid
        cls.foreign = scoped_tests.ScopedCompletionTests.foreign

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.session = self.make(self.clock)
        self.bridge = proof.StableRootBridge(self.session)

    def make(self, clock):
        session = Stage1Session(closed_owner=True, save_root=self.temp.name, runtime_clock=clock)
        session.world = self.source
        session._ensure_runtime()
        session.career_id = session._save_store.new_career_id()
        session._reset_autosave_clocks()
        return session

    def assert_original(self, values, roots):
        self.assertEqual(protected_bytes(self.session._world), values)
        self.assertTrue(proof._same_roots(self.session._world, roots))

    def test_success_stable_root_exact_strict_world_and_private_sharing(self):
        s = self.session; base = s._world; runtime = s._runtime
        binding = s.binding_revision; runtime_binding = s.runtime_binding
        old = dict(base); views = s._owned_reads(); page = s.fleet()
        unchanged = base['world_state']['bookings'][self.foreign]
        changed = base['world_state']['dated_flights'][self.fid]
        expected = deepcopy(base); strict = kernel.process_next_event(expected)
        prepared = self.bridge.prepare()
        successor = prepared._successor
        self.assertIs(successor['world_state']['bookings'][self.foreign], unchanged)
        self.assertIsNot(successor['world_state']['dated_flights'][self.fid], changed)
        self.assertFalse(mutable_ids(changed) & mutable_ids(successor['world_state']['dated_flights'][self.fid]))
        outcome = self.bridge.publish(prepared)
        self.assertTrue(outcome.committed, outcome)
        self.assertEqual(outcome.attempt.processing_result, strict)
        self.assertEqual(protected_bytes(base), protected_bytes(expected))
        self.assertIs(s._world, base); self.assertIs(runtime.world, base)
        self.assertIs(s._runtime, runtime)
        self.assertEqual(binding, s.binding_revision); self.assertEqual(runtime_binding, s.runtime_binding)
        self.assertFalse(views.matches(base, s.progression_revision))
        self.assertIsNot(s._owned_reads(), views)
        self.assertFalse(mutable_ids(page) & mutable_ids(base))
        self.assertIs(base['world_state']['bookings'][self.foreign], unchanged)
        changed['status'] = 'RETAINED_OLD_RECORD'
        self.assertEqual(base['world_state']['dated_flights'][self.fid]['status'], 'COMPLETED')
        self.assertIsNot(old['world_state'], base['world_state'])

    def test_all_precommit_stage_faults_preserve_exact_world_and_retry(self):
        for stage in ('before_successor_preparation','during_output_detachment',
                      'during_successor_validation','during_publication_preparation',
                      'immediately_before_installation'):
            with self.subTest(stage=stage):
                before = protected_bytes(self.session._world); roots = dict(self.session._world)
                reached = []
                def fail(current):
                    if current == stage:
                        reached.append(current)
                        raise RuntimeError(stage)
                with patch.object(proof, '_fault', fail):
                    outcome = self.bridge.complete()
                self.assertFalse(outcome.committed); self.assertEqual(reached, [stage])
                self.assert_original(before, roots)
        self.assertTrue(self.bridge.complete().committed)

    def test_partial_installation_each_changed_root_restores_without_world_copy(self):
        from itertools import permutations
        roots_to_change = ('simulation','deterministic_state','world_state')
        for changed_roots in (*permutations(roots_to_change, 1), *permutations(roots_to_change, 2)):
            with self.subTest(roots=changed_roots):
                before = protected_bytes(self.session._world); roots = dict(self.session._world)
                prepared = self.bridge.prepare(); touched = []
                def partial(target, successor):
                    for root in changed_roots:
                        target[root] = successor[root]
                        touched.append(root)
                    raise RuntimeError('partial installation')
                with patch.object(proof, '_install', partial), patch.object(
                        kernel, '_clone_runtime_world', side_effect=AssertionError('no world rollback copy')):
                    result = self.bridge.publish(prepared)
                self.assertEqual(touched, list(changed_roots)); self.assertEqual(result.state, 'ROLLED_BACK')
                self.assert_original(before, roots)
                self.assertIs(self.bridge.publish(prepared), result)
        expected = deepcopy(self.session._world); strict = kernel.process_next_event(expected)
        actual = self.bridge.complete()
        self.assertTrue(actual.committed)
        self.assertEqual(actual.attempt.processing_result, strict)
        self.assertEqual(protected_bytes(self.session._world), protected_bytes(expected))

    def test_complete_install_then_exception_is_committed_and_never_replayed(self):
        prepared = self.bridge.prepare()
        expected = deepcopy(self.session._world); kernel.process_next_event(expected)
        def installed_then_fail(target, successor):
            dict.update(target, successor)
            raise KeyboardInterrupt('installed before return')
        with patch.object(proof, '_install', installed_then_fail):
            receipt = self.bridge.publish(prepared)
        self.assertTrue(receipt.committed); self.assertIn('KeyboardInterrupt', receipt.diagnostic)
        self.assertEqual(protected_bytes(self.session._world), protected_bytes(expected))
        for _ in range(3): self.assertIs(self.bridge.publish(prepared), receipt)
        self.assertEqual(self.bridge.counts['installations'], 1)
        self.assertEqual(self.bridge.counts['committed'], 1)

    def test_silent_partial_install_is_detected_and_restored(self):
        prepared = self.bridge.prepare(); before = protected_bytes(self.session._world)
        roots = dict(self.session._world)
        def incomplete(target, successor):
            target['world_state'] = successor['world_state']
        with patch.object(proof, '_install', incomplete): receipt = self.bridge.publish(prepared)
        self.assertEqual(receipt.state, 'ROLLED_BACK')
        self.assert_original(before, roots)

    def test_postcommit_faults_and_notification_failure_remain_committed(self):
        for stage in ('after_installation_before_marker','after_commit_marker',
                      'after_notification_before_return'):
            with self.subTest(stage=stage):
                s = self.make(Clock()); bridge = proof.StableRootBridge(s)
                expected = deepcopy(s._world); kernel.process_next_event(expected)
                reached = []
                def fail(current):
                    if current == stage: reached.append(current); raise RuntimeError(stage)
                with patch.object(proof, '_fault', fail): result = bridge.complete()
                self.assertEqual(reached, [stage]); self.assertTrue(result.committed)
                self.assertEqual(protected_bytes(s._world), protected_bytes(expected))
        with patch.object(self.bridge, '_notify_commit', side_effect=RuntimeError('observer failed')):
            receipt = self.bridge.complete()
        self.assertTrue(receipt.committed); self.assertIsNone(self.session._read_views)

    def test_line_trace_fault_after_marker_is_not_precommit_failure(self):
        lines, start = inspect.getsourcelines(proof.StableRootBridge._publish)
        line = start + next(i for i, text in enumerate(lines) if 'self._epoch += 1' in text)
        reached = []
        def trace(frame, event, arg):
            if frame.f_code is proof.StableRootBridge._publish.__code__ and event == 'line' and frame.f_lineno == line:
                reached.append(line); raise RuntimeError('post-install bookkeeping')
            return trace
        prior = sys.gettrace()
        try:
            sys.settrace(trace); result = self.bridge.complete()
        finally: sys.settrace(prior)
        self.assertEqual(reached, [line]); self.assertTrue(result.committed, result)
        self.assertIn(self.fid, self.session._world['world_state']['flight_results'])

    def test_return_boundary_interruption_recovers_receipt_without_replay(self):
        prepared = self.bridge.prepare(); reached = []
        def trace(frame, event, arg):
            if frame.f_code is proof.StableRootBridge.publish.__code__ and event == 'return':
                reached.append('return'); raise KeyboardInterrupt('return boundary')
            return trace
        prior = sys.gettrace()
        try:
            sys.settrace(trace)
            try:
                self.bridge.publish(prepared)
            except KeyboardInterrupt:
                receipt = self.bridge.status(prepared)
        finally: sys.settrace(prior)
        self.assertEqual(reached, ['return']); self.assertTrue(receipt.committed)
        self.assertIs(self.bridge.publish(prepared), receipt)
        self.assertEqual(self.bridge.counts['committed'], 1)
        self.assertEqual(self.bridge.counts['installations'], 1)

    def test_retained_speculative_refs_expire_and_changed_outputs_detach(self):
        retained = []
        def hold(stage, capsule):
            if stage == 'after_handler':
                retained.extend((capsule, capsule.envelope['world_state']['flight_results'][self.fid]))
        with patch.object(scoped, '_fault', hold): prepared = self.bridge.prepare()
        self.assertTrue(self.bridge.publish(prepared).committed)
        before = protected_bytes(self.session._world)
        retained[1]['booking_witnesses'][0]['passenger_count'] = 999
        retained[0].envelope['simulation']['time_utc'] = '1900-01-01T00:00:00Z'
        with self.assertRaises(ValueError): retained[0].envelope['world_state']['bookings'][self.foreign]
        self.assertEqual(before, protected_bytes(self.session._world))

    def test_nested_equal_valued_alias_rejects_before_publication(self):
        before = protected_bytes(self.session._world)
        def alias(stage, capsule):
            if stage == 'after_handler':
                world = capsule.envelope['world_state']; row = world['flight_results'][self.fid]
                old = protected_bytes(row)
                self.assertIsNot(row['quarterly_lineage'], world['dated_flights'][self.fid]['quarterly_lineage'])
                row['quarterly_lineage'] = world['dated_flights'][self.fid]['quarterly_lineage']
                self.assertEqual(old, protected_bytes(row))
        with patch.object(scoped, '_fault', alias): result = self.bridge.complete()
        self.assertFalse(result.committed)
        self.assertEqual(before, protected_bytes(self.session._world))

    def test_broken_detachment_cannot_publish_retained_writable_outputs(self):
        real = scoped.deepcopy
        def borrowed(value):
            if type(value) is dict and value.keys() == {'simulation','allocator','records'}:
                return value
            return real(value)
        before = protected_bytes(self.session._world)
        with patch.object(scoped, 'deepcopy', borrowed): result = self.bridge.complete()
        self.assertFalse(result.committed)
        self.assertIn('retained writable', result.diagnostic)
        self.assertEqual(before, protected_bytes(self.session._world))

    def test_stale_duplicate_and_foreign_preparations(self):
        first = self.bridge.prepare(); stale = self.bridge.prepare()
        foreign = proof.StableRootBridge(self.session)
        with self.assertRaises(ValueError): foreign.publish(first)
        receipt = self.bridge.publish(first); self.assertTrue(receipt.committed)
        with self.assertRaisesRegex(ValueError, 'stale'): self.bridge.publish(stale)
        self.assertIs(self.bridge.publish(first), receipt)

    def test_rebind_and_close_expire_preparations(self):
        prepared = self.bridge.prepare()
        self.session.world = self.source
        with self.assertRaisesRegex(ValueError, 'stale'): self.bridge.publish(prepared)
        bridge = proof.StableRootBridge(self.session); prepared = bridge.prepare()
        self.session._ensure_runtime(); self.session.close()
        with self.assertRaisesRegex(ValueError, 'closed'): bridge.publish(prepared)

    def test_advancement_begin_expires_preparation_without_career_rebind(self):
        prepared = self.bridge.prepare(); binding = self.session.binding_revision
        self.session.begin_advance_to(self.event['due_at_utc'])
        with self.assertRaisesRegex(ValueError, 'stale'): self.bridge.publish(prepared)
        self.session.cancel_advance()
        self.assertEqual(binding, self.session.binding_revision)

    def test_reconciliation_prefix_survives_precommit_failure_and_retry(self):
        source = deepcopy(self.source)
        dispatch = next(key for key, event in source['world_state']['pending_events'].items()
                        if event['event_type'] == 'QUARTERLY_DISPATCH')
        del source['world_state']['pending_events'][dispatch]
        self.session.world = source; bridge = proof.StableRootBridge(self.session)
        expected = deepcopy(source)
        from game.aircraft_operations import fulfilment
        allocate = fulfilment.allocate_id
        def fail(*args):
            allocate(*args)
            raise RuntimeError('after allocation')
        with patch.object(fulfilment, 'allocate_id', fail):
            actual = bridge.complete(); strict = kernel.process_next_event(expected)
        self.assertFalse(actual.committed); self.assertFalse(strict.succeeded)
        self.assertEqual(protected_bytes(self.session._world), protected_bytes(expected))
        actual = bridge.complete(); strict = kernel.process_next_event(expected)
        self.assertTrue(actual.committed, actual)
        self.assertEqual(actual.attempt.processing_result, strict)
        self.assertEqual(protected_bytes(self.session._world), protected_bytes(expected))

    def test_two_completions_strict_interleaving_prefix_and_save_load(self):
        expected = deepcopy(self.session._world); base = self.session._world
        acquisitions = self.session.ownership_counts()['acquisitions']
        for index in range(2):
            actual = self.bridge.complete(); strict = kernel.process_next_event(expected)
            self.assertTrue(actual.committed, actual)
            self.assertEqual(actual.attempt.processing_result, strict)
            self.assertEqual(protected_bytes(base), protected_bytes(expected))
            if index == 0:
                target = min(expected['world_state']['pending_events'].values(), key=kernel._event_key)['due_at_utc']
                strict = kernel.process_events_through(expected, target)
                report = self.session.advance_to(target)
                self.assertEqual(report.result, strict)
                self.assertEqual(protected_bytes(base), protected_bytes(expected))
        self.assertIs(base, self.session._world)
        self.assertEqual(acquisitions, self.session.ownership_counts()['acquisitions'])
        career = self.session.save_manual(); self.session.load_saved(career)
        self.assertTrue(validate_world(self.session._world).is_valid)
        self.assertEqual(self.session._world['simulation']['clock_state'], 'PAUSED')
        self.assertEqual(protected_bytes(self.session._world), protected_bytes(expected))

    def test_copy_accounting_zero_world_copies_during_publication(self):
        prepared = self.bridge.prepare()
        before_counts = self.session.ownership_counts()
        with patch.object(kernel, '_clone_runtime_world', side_effect=AssertionError('world copy')), patch.object(
                scoped, 'deepcopy', side_effect=AssertionError('publication must not deepcopy')):
            receipt = self.bridge.publish(prepared)
        self.assertTrue(receipt.committed)
        self.assertEqual(before_counts, self.session.ownership_counts())
        self.assertEqual(self.bridge.counts['validation_calls'], 2)
        self.assertEqual(self.bridge.counts['scoped_output_detachments'], 1)
        self.assertEqual(self.bridge.counts['shallow_collection_tables'], 9)
        self.assertEqual(self.bridge._proof_owner.counts['copied_existing_records'], 9)
        self.assertEqual(self.bridge._proof_owner.counts['detached_output_records'], 10)

    def test_actual_retained_runtime_request_counts_event_once_and_keeps_identity(self):
        from game.simulation.pacing import NANOSECOND
        from game.world_state.timestamps import parse_canonical_utc
        controls = []
        for use_bridge in (False, True):
            clock = Clock(); s = self.make(clock); base = s._world
            kernel.schedule_event(base, event_type='NO_OP', due_at_utc=base['simulation']['time_utc'],
                owner_type='airline', owner_id=s.airline_id)
            s._runtime.max_batch_events = 1
            s.resume()
            seconds = int((parse_canonical_utc(self.event['due_at_utc']) -
                           parse_canonical_utc(s.simulation_time_utc)).total_seconds())
            clock.advance((seconds // 30 + 1) * NANOSECOND)
            s.pump()  # First genuine yield leaves runtime/work alive after NO_OP.
            runtime = s._runtime; request = runtime.work
            self.assertIsNotNone(request); self.assertEqual(request._completed, 1)
            bridge = proof.StableRootBridge(s)
            execute = kernel._execute_event; receipts = []
            def intercepted(world, event_id, registry):
                if use_bridge and event_id == self.event['event_id']:
                    self.assertIs(request._world, base); self.assertIs(runtime.world, base)
                    # Session.pump performs the real commit notification after
                    # request accounting; avoid a duplicate test-harness notice.
                    def postcommit_fault(stage):
                        if stage == 'after_installation_before_marker':
                            raise RuntimeError('postcommit while request retained')
                    with patch.object(bridge, '_notify_commit', return_value=None), patch.object(
                            proof, '_fault', postcommit_fault):
                        result = bridge.complete()
                    receipts.append(result); self.assertTrue(result.committed, result)
                    return 'COMPLETED', None, ()
                return execute(world, event_id, registry)
            with patch.object(kernel, '_execute_event', intercepted):
                for _ in range(30):
                    s.pump()
                    if runtime.work is None: break
            self.assertIs(s._world, base); self.assertIs(runtime.world, base)
            self.assertIs(request._world, base); self.assertTrue(request.finished)
            self.assertEqual(request._completed, 2)
            if use_bridge: self.assertEqual(len(receipts), 1)
            s.pause()
            controls.append((protected_bytes(base), runtime.last_result))
        self.assertEqual(controls[0], controls[1])


if __name__ == '__main__': unittest.main()
