"""Actual Kivy pilot refresh and deferred-action identity through scoped commit."""
import os
os.environ.setdefault('KIVY_NO_ARGS','1')
from copy import deepcopy
import tempfile
import unittest

from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from game.simulation import kernel
from game.simulation.pacing import NANOSECOND
from game.world_state.timestamps import parse_canonical_utc
from tests import test_scoped_completion_experiment as fixtures
from tests.test_stage1_runtime import Clock


class PilotGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.ScopedCompletionTests.setUpClass()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.clock=Clock()
        self.app=AirlineTycoonApp(closed_owner=True,scoped_completion=True,
            session_factory=lambda **options:Stage1Session(runtime_clock=self.clock,
                save_root=self.temp.name,**options))
        self.app.build(); self.app.create_new_game('CEO','Pilot GUI','MNL')
        self.app.session.world=fixtures.ScopedCompletionTests.source
        self.app.session._ensure_runtime(); self.app.session._reset_autosave_clocks()
        self.app.refresh(force=True)

    def tearDown(self):
        self.app._dismiss(); self.app.on_stop(); self.temp.cleanup()

    def test_next_event_refresh_uses_closed_projections_and_keeps_binding(self):
        s=self.app.session; binding=s.runtime_binding
        self.app._next_event(); self.app.tick(0)
        self.assertEqual(s.scoped_completion_status()['counts']['committed'],1)
        self.assertEqual(binding,s.runtime_binding)
        self.assertIn(s.simulation_time_utc,self.app.status.text)
        self.assertEqual(s.ownership_counts()['full_world_exports'],0)
        self.assertIsNone(self.app._popup)

    def test_deferred_action_survives_scoped_commit_and_runs_once(self):
        s=self.app.session; source=s._world
        kernel.schedule_event(source,event_type='NO_OP',due_at_utc=s.simulation_time_utc,
                              owner_type='airline',owner_id=s.airline_id)
        s._runtime.max_batch_events=1; s.resume()
        seconds=int((parse_canonical_utc(fixtures.ScopedCompletionTests.event['due_at_utc'])-
                     parse_canonical_utc(s.simulation_time_utc)).total_seconds())
        self.clock.advance((seconds//30+1)*NANOSECOND); s.pump()
        binding=s.runtime_binding; called=[]
        self.app._after_runtime_pause(lambda:called.append('done'))
        for _ in range(30):
            self.app.tick(0)
            if called: break
        self.assertEqual(called,['done']); self.assertEqual(binding,s.runtime_binding)
        self.assertEqual(s.scoped_completion_status()['counts']['committed'],1)
        self.assertEqual(s.ownership_counts()['full_world_exports'],0)


if __name__=='__main__': unittest.main()
