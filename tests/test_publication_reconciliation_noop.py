"""No-op proof against unchanged detached publication reconstruction."""
from copy import deepcopy
from contextlib import nullcontext
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from game.simulation import kernel
from game.simulation.resolver import begin_resolution, resolve_until
from game.scheduling import quarterly_backend, quarterly_boundary as publication
from game.world_state import validate_world
from game.world_state.construction import add_airline
from game.world_state.persistence import SaveStore
from game.world_state.quarterly_construction import create_weekly_plan
from game.world_state.quarterly_boundary import enroll_candidate
from tests import test_quarterly_boundaries as fixtures
from tests.test_quarterly_foundation import encoded


def original_reconciliation():
    """Force the unchanged public transaction, including its no-op copy."""
    return patch.object(publication, '_publication_reconciliation_needed', return_value=True)


class PublicationReconciliationNoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.QuarterlyBoundaryTests.setUpClass.__func__(cls)

    def setUp(self):
        self.fixture = fixtures.QuarterlyBoundaryTests()
        self.fixture.base = self.base
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.enroll()
        self.world = self.fixture.world
        self.owner = self.fixture.owner
        self.due = self.fixture.due

    def compare_reconciliation(self, *, copies):
        report = validate_world(self.world)
        self.assertTrue(report.is_valid, report.errors[:3])
        expected = deepcopy(self.world)
        with original_reconciliation():
            kernel._reconcile_quarterly(expected)
        with patch.object(publication, 'deepcopy', wraps=deepcopy) as copied:
            kernel._reconcile_quarterly(self.world)
        self.assertEqual(copied.call_count, copies)
        self.assertEqual(encoded(self.world), encoded(expected))
        self.assertTrue(validate_world(self.world).is_valid)

    def compare_resolution(self, world, target, *, shared=False):
        expected = deepcopy(world)
        with original_reconciliation():
            left = resolve_until(expected, target, shared=shared)
        right = resolve_until(world, target, shared=shared)
        self.assertEqual(right, left)
        self.assertEqual(encoded(world), encoded(expected))
        return right

    def test_complete_queue_skips_only_publication_copy_and_preserves_identity(self):
        before = encoded(self.world)
        state = self.world['world_state']
        event = self.fixture.event()
        self.assertFalse(publication._publication_reconciliation_needed(self.world))
        with patch.object(publication, 'deepcopy', wraps=deepcopy) as publication_copy, \
                patch.object(quarterly_backend, 'deepcopy', wraps=deepcopy) as backend_copy, \
                patch.object(quarterly_backend, 'reconcile', wraps=quarterly_backend.reconcile) as backend, \
                patch.object(kernel, '_replace_envelope', wraps=kernel._replace_envelope) as commit:
            kernel._reconcile_quarterly(self.world)
        self.assertEqual(publication_copy.call_count, 0)
        self.assertEqual(backend.call_count, 1)
        # This boundary-only fixture is not enrolled in the operational backend.
        self.assertEqual(backend_copy.call_count, 0)
        self.assertEqual(commit.call_count, 0)
        self.assertIs(self.world['world_state'], state)
        self.assertIs(self.fixture.event(), event)
        self.assertEqual(encoded(self.world), before)

    def test_public_transaction_still_copies_complete_queue(self):
        before = encoded(self.world)
        with patch.object(publication, 'deepcopy', wraps=deepcopy) as copied:
            self.assertEqual(publication.reconcile(self.world), ())
        self.assertEqual(copied.call_count, 1)
        self.assertEqual(encoded(self.world), before)

    def test_missing_event_repairs_identical_ids_and_cursor(self):
        del self.world['world_state']['pending_events'][self.fixture.event()['event_id']]
        self.assertTrue(publication._publication_reconciliation_needed(self.world))
        self.compare_reconciliation(copies=1)

    def test_stale_only_event_does_not_satisfy_current_revision(self):
        kernel.set_operation_revision(self.world, self.owner, 1)
        self.assertTrue(publication._publication_reconciliation_needed(self.world))
        self.compare_reconciliation(copies=1)
        self.assertTrue(self.compare_resolution(self.world, self.due).succeeded)

    def test_wrong_quarter_does_not_satisfy_obligation(self):
        kernel.cancel_event(self.world, self.fixture.event()['event_id'])
        kernel.schedule_event(self.world, event_type=publication.EVENT_TYPE,
            due_at_utc=publication.boundary('2027-Q3'), owner_type='airline', owner_id=self.owner,
            priority=0, payload=dict(contract=publication.CONTRACT, quarter_id='2027-Q3'))
        self.assertTrue(publication._publication_reconciliation_needed(self.world))
        self.compare_reconciliation(copies=1)

    def test_duplicates_and_stale_plus_current_preserve_lifecycle_work(self):
        for revision in (0, 1):
            with self.subTest(revision=revision):
                world = deepcopy(self.world)
                kernel.set_operation_revision(world, self.owner, revision)
                kernel.schedule_event(world, event_type=publication.EVENT_TYPE,
                    due_at_utc=self.due, owner_type='airline', owner_id=self.owner,
                    operation_revision=revision, priority=0,
                    payload=dict(contract=publication.CONTRACT, quarter_id='2027-Q2'))
                self.assertFalse(publication._publication_reconciliation_needed(world))
                result = self.compare_resolution(world, self.due, shared=True)
                self.assertTrue(result.succeeded, result.failure)

    def test_mixed_owners_reconstruct_only_missing_in_owner_order(self):
        second = add_airline(self.world, 'Second')
        third = add_airline(self.world, 'Third')
        for owner in (second, third):
            create_weekly_plan(self.world, owner, '2027-Q2')
            publication.enable_quarterly_boundaries_for_testing(self.world, airline_id=owner)
        # Reverse pending insertion order; matching and generated IDs remain semantic.
        pending = self.world['world_state']['pending_events']
        for identity, event in tuple(pending.items()):
            if event['event_type'] == publication.EVENT_TYPE and event['owner_id'] != self.owner:
                del pending[identity]
        self.world['simulation']['quarterly_publication'] = dict(reversed(tuple(
            self.world['simulation']['quarterly_publication'].items())))
        self.compare_reconciliation(copies=1)

    def test_no_cached_answer_after_pending_event_changes(self):
        self.assertFalse(publication._publication_reconciliation_needed(self.world))
        del self.world['world_state']['pending_events'][self.fixture.event()['event_id']]
        self.assertTrue(publication._publication_reconciliation_needed(self.world))
        self.compare_reconciliation(copies=1)
        self.assertFalse(publication._publication_reconciliation_needed(self.world))

    def test_probe_observes_new_obligation_from_backend_reconciliation(self):
        second = add_airline(self.world, 'New backend owner')
        create_weekly_plan(self.world, second, '2027-Q2')
        self.assertFalse(publication._publication_reconciliation_needed(self.world))
        def enroll_new_owner(world):
            enroll_candidate(world, second)
        for reference in (True, False):
            world = deepcopy(self.world)
            with original_reconciliation() if reference else nullcontext():
                with patch.object(quarterly_backend, 'reconcile', side_effect=enroll_new_owner):
                    kernel._reconcile_quarterly(world)
            self.assertTrue(validate_world(world).is_valid)
            if reference:
                expected = encoded(world)
            else:
                self.assertEqual(encoded(world), expected)

    def test_read_only_predicate_never_copies_allocates_schedules_or_validates(self):
        before = encoded(self.world)
        with patch.object(publication, 'deepcopy', side_effect=AssertionError('copy')), \
                patch.object(publication, '_schedule', side_effect=AssertionError('schedule')), \
                patch.object(publication, 'validate_world', side_effect=AssertionError('validation')):
            self.assertIs(publication._publication_reconciliation_needed(self.world), False)
        self.assertEqual(encoded(self.world), before)

    def test_uncertain_shapes_require_original_transaction(self):
        for damage in (
                lambda w: w['world_state'].__setitem__('pending_events', None),
                lambda w: w['simulation'].__setitem__('quarterly_publication', None),
                lambda w: w['simulation']['quarterly_publication'][self.owner].clear(),
                lambda w: w['world_state']['pending_events'][self.fixture.event()['event_id']].clear()):
            world = deepcopy(self.world)
            damage(world)
            self.assertTrue(publication._publication_reconciliation_needed(world))

    def test_invalid_world_never_reaches_predicate_or_reconciliation(self):
        self.world['world_state']['airlines'][self.owner]['finance_revision'] = True
        with patch.object(publication, '_publication_reconciliation_needed',
                side_effect=AssertionError('unvalidated probe')):
            result = resolve_until(self.world, self.due, shared=True)
        self.assertFalse(result.succeeded)

    def test_valid_compatibility_key_keeps_original_copy_callback_and_exception(self):
        copied = []
        class CompatibilityKey(str):
            def __deepcopy__(self, memo):
                copied.append(str(self))
                raise RuntimeError('compatibility key copy')
        for reference in (True, False):
            with self.subTest(reference=reference):
                copied.clear()
                world = deepcopy(self.world)
                value = world['metadata'].pop('game_version')
                world['metadata'][CompatibilityKey('game_version')] = value
                report = validate_world(world)
                self.assertTrue(report.is_valid, report.errors[:3])
                before = encoded(world)
                with original_reconciliation() if reference else nullcontext():
                    with self.assertRaisesRegex(RuntimeError, 'compatibility key copy'):
                        kernel._reconcile_quarterly(world)
                self.assertEqual(copied, ['game_version'])
                self.assertEqual(encoded(world), before)

    def test_strict_shared_next_event_and_management_refresh_match_original(self):
        for shared in (False, True):
            with self.subTest(shared=shared):
                world = deepcopy(self.world)
                self.assertTrue(self.compare_resolution(world, self.due, shared=shared).succeeded)
        expected = deepcopy(self.world)
        with original_reconciliation():
            left = kernel.process_next_event(expected)
        right = kernel.process_next_event(self.world)
        self.assertEqual(right, left)
        self.assertEqual(encoded(self.world), encoded(expected))
        for reference in (True, False):
            world = deepcopy(self.fixture.world)
            with original_reconciliation() if reference else nullcontext():
                request = begin_resolution(world, self.due, shared=True)
                self.addCleanup(request.close)
                request.step(boundary_requested=True)
                event_id = next(k for k, e in world['world_state']['pending_events'].items()
                    if e['event_type'] == publication.EVENT_TYPE)
                del world['world_state']['pending_events'][event_id]
                request.step(management_changed=True, boundary_requested=True)
                while not request.finished:
                    request.step()
            if reference:
                expected = encoded(world)
            else:
                self.assertEqual(encoded(world), expected)

    def test_repair_failure_rolls_back_and_retry_matches_original(self):
        del self.world['world_state']['pending_events'][self.fixture.event()['event_id']]
        before = encoded(self.world)
        real_schedule = publication._schedule
        def fail_after_allocation(*args):
            real_schedule(*args)
            raise ValueError('injected after allocation')
        for reference in (True, False):
            world = deepcopy(self.world)
            with original_reconciliation() if reference else nullcontext():
                with patch.object(publication, '_schedule', side_effect=fail_after_allocation):
                    with self.assertRaisesRegex(ValueError, 'injected after allocation'):
                        kernel._reconcile_quarterly(world)
            self.assertEqual(encoded(world), before)
        self.compare_reconciliation(copies=1)

    def test_repair_validation_failure_discards_allocated_events(self):
        del self.world['world_state']['pending_events'][self.fixture.event()['event_id']]
        before = encoded(self.world)
        for reference in (True, False):
            world = deepcopy(self.world)
            with original_reconciliation() if reference else nullcontext():
                with patch.object(publication, 'validate_world',
                        return_value=SimpleNamespace(is_valid=False)):
                    with self.assertRaisesRegex(ValueError, 'reconciliation failed validation'):
                        kernel._reconcile_quarterly(world)
            self.assertEqual(encoded(world), before)
        self.compare_reconciliation(copies=1)

    def test_loaded_complete_and_missing_queue_resume_matches_original(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                world = deepcopy(self.world)
                if missing:
                    del world['world_state']['pending_events'][self.fixture.event()['event_id']]
                with tempfile.TemporaryDirectory() as root:
                    store = SaveStore(root)
                    career = store.new_career_id()
                    store.save(career, 'manual', world)
                    loaded, _ = store.load(career)
                self.assertEqual(encoded(loaded), encoded(world))
                self.assertEqual(loaded['simulation']['clock_state'], 'PAUSED')
                self.assertTrue(self.compare_resolution(loaded, self.due, shared=True).succeeded)

    def test_fenced_retries_and_loaded_missing_event_preserve_exact_world(self):
        # Build a genuine failure fence, then compare both entry paths on retries.
        self.fixture.world['world_state']['weekly_plans'][self.fixture.pid]['revisions']['1']['slots'].pop()
        result = self.compare_resolution(self.world, self.due, shared=True)
        self.assertEqual(result.failure.code, 'QUARTERLY_PUBLICATION_FAILED')
        for shared in (False, True):
            before = encoded(self.world)
            result = self.compare_resolution(self.world, self.due, shared=shared)
            self.assertEqual(result.failure.code, 'QUARTERLY_PUBLICATION_FAILED')
            self.assertEqual(encoded(self.world), before)
        kernel.cancel_event(self.world, self.fixture.event()['event_id'])
        with tempfile.TemporaryDirectory() as root:
            store = SaveStore(root)
            career = store.new_career_id()
            store.save(career, 'manual', self.world)
            loaded, _ = store.load(career)
        self.assertEqual(encoded(loaded), encoded(self.world))
        self.assertEqual(loaded['simulation']['clock_state'], 'PAUSED')
        result = self.compare_resolution(loaded, self.due, shared=True)
        self.assertEqual(result.failure.code, 'QUARTERLY_PUBLICATION_FAILED')


if __name__ == '__main__':
    unittest.main()
