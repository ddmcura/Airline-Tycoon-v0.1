"""Native GUI pilot: closed reads, drain actions and binding invalidation."""
import os
os.environ.setdefault('KIVY_NO_ARGS', '1')
import tempfile
import unittest

from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from game.simulation import kernel
from tests.test_stage1_runtime import Clock


class ClosedGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.app = AirlineTycoonApp(session_factory=lambda:Stage1Session(
            closed_owner=True, runtime_clock=self.clock, save_root=self.temp.name))
        self.app.build(); self.app.create_new_game('CEO', 'Closed Air', 'MNL')

    def tearDown(self):
        self.app._dismiss(); self.app.on_stop(); self.temp.cleanup()

    def debt(self):
        s = self.app.session
        for _ in range(12):
            kernel.schedule_event(s._world, event_type='NO_OP',
                due_at_utc=s.simulation_time_utc, owner_type='airline', owner_id=s.airline_id)
        s.resume(); self.clock.advance(1_000_000_000)

    def test_tick_refresh_and_deferred_action_survives_commits(self):
        self.debt(); s = self.app.session; called = []
        self.app._after_runtime_pause(lambda:called.append('done'))
        binding = s.runtime_binding
        for _ in range(30):
            self.app.tick(0)
            if called: break
        self.assertEqual(called, ['done'])
        self.assertEqual(binding, s.runtime_binding)
        self.assertGreater(s.progression_revision, 0)
        self.assertEqual(s.ownership_counts()['full_world_exports'], 0)
        self.assertIn(s.simulation_time_utc, self.app.status.text)

    def test_rebind_revokes_deferred_action(self):
        self.debt(); called = []
        self.app._after_runtime_pause(lambda:called.append('stale'))
        self.app.session.new_game('CEO', 'Replacement', 'MNL')
        self.app.tick(0)
        self.assertEqual(called, [])
        self.assertIsNone(self.app._pending_runtime_action)

    def test_runtime_failure_suppresses_deferred_action(self):
        self.debt(); called = []
        self.app._after_runtime_pause(lambda:called.append('unsafe'))
        self.app.session._runtime._stop_error('injected failure')
        self.app.tick(0)
        self.assertEqual(called, [])
        self.assertIsNone(self.app._pending_runtime_action)


if __name__ == '__main__': unittest.main()
