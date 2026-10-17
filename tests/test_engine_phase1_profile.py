"""Deterministic accounting checks for removable profiling instrumentation."""
import unittest
from unittest.mock import patch

from tests.profile_engine_phase1 import Profile


class ProfileAccountingTests(unittest.TestCase):
    def test_nested_intervals_are_subtracted_once(self):
        profile = Profile()
        child = profile.wrap(lambda: 7, 'child')
        parent = profile.wrap(child, 'parent')
        with patch('tests.profile_atomic_boundaries.perf_counter', side_effect=[0, 1, 3, 5]):
            self.assertEqual(parent(), 7)
        self.assertEqual(profile.inclusive, dict(child=2, parent=5))
        self.assertEqual(profile.seconds, dict(child=2, parent=3))
        self.assertEqual(profile.calls, dict(parent=1, child=1))
        self.assertEqual(profile.stack, [])

    def test_exception_is_preserved_and_stack_released(self):
        profile = Profile()
        failure = ValueError('sentinel')
        def reject():
            raise failure
        with self.assertRaises(ValueError) as caught:
            profile.wrap(reject, 'operation')()
        self.assertIs(caught.exception, failure)
        self.assertEqual(profile.stack, [])
        self.assertEqual(profile.calls, dict(operation=1))

    def test_copy_classification_preserves_arguments_and_return_identity(self):
        profile = Profile()
        world = dict(world_state={}, simulation={})
        wrapped = profile.wrap(lambda value: value, 'deepcopy')
        self.assertIs(wrapped(world), world)
        self.assertEqual(profile.calls, dict(whole_world_deepcopy=1))
        clone = profile.wrap(lambda value: value, 'world_clone')
        commit = profile.wrap(clone, 'detached_commit')
        self.assertIs(commit(world), world)
        self.assertEqual(profile.calls['commit_clone'], 1)


if __name__ == '__main__':
    unittest.main()
