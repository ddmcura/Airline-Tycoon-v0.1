"""GUI status and deferred committed-boundary save/exit regressions."""
import os
os.environ.setdefault('KIVY_NO_ARGS','1')
import tempfile
import unittest
from unittest.mock import patch
from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from game.simulation.pacing import NANOSECOND
from game.simulation import kernel
from kivy.uix.button import Button
from tests.test_stage1_runtime import Clock

class CooperativeGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.clock=Clock()
        self.app=AirlineTycoonApp(session_factory=lambda:Stage1Session(runtime_clock=self.clock,save_root=self.temp.name))
        self.app.build(); self.app.create_new_game('CEO','Cooperative Air','MNL')
    def tearDown(self):
        self.app._dismiss(); self.app.on_stop(); self.temp.cleanup()
    def debt(self):
        s=self.app.session; s.resume(); now=s.world['simulation']['time_utc']
        for _ in range(20): kernel.schedule_event(s.world,event_type='NO_OP',due_at_utc=now,owner_type='airline',owner_id=s.airline_id)
        s.runtime.management_changed(); self.clock.advance(NANOSECOND)
    def drain(self):
        for _ in range(30):
            self.app.tick(0)
            if not self.app.session.runtime.draining: return
        self.fail('GUI drain did not finish')
    def test_manual_save_waits_for_drain_then_saves_once(self):
        self.debt(); s=self.app.session
        with patch.object(s.save_store,'save',wraps=s.save_store.save) as save:
            self.app.save_game(); self.assertIsNotNone(self.app._pending_runtime_action)
            self.assertEqual(save.call_count,0); self.drain(); self.assertEqual(save.call_count,1)
        self.assertEqual(s.runtime.state,'PAUSED'); self.assertFalse(s.unsaved_progress)
        self.assertIsNone(self.app._pending_runtime_action)
    def test_return_waits_before_unsaved_dialog_and_discard_closes_runtime(self):
        self.debt(); old=self.app.session.runtime; self.app.return_to_title()
        self.assertIsNotNone(self.app._pending_runtime_action); self.drain()
        next(w for w in self.app._popup.content.children if isinstance(w,Button) and w.text=='Leave without saving').dispatch('on_release')
        self.assertEqual(self.app.screens.current,'title'); self.assertTrue(old.closed)
        self.clock.advance(100*NANOSECOND); old.pump(); self.assertIsNone(old.work)
    def test_catchup_and_recovered_status_never_display_target_as_clock(self):
        self.debt(); r=self.app.session.runtime; r.overload_seconds=.01; r.grace_ns=0
        self.app.tick(0); self.assertEqual(r.state,'OVERLOAD_DRAIN')
        self.assertIn('Catching up',self.app.status.text)
        self.assertIn(self.app.session.world['simulation']['time_utc'],self.app.status.text)
        self.assertIn('Earned target:',self.app.status.text)
        self.app.status.texture_update()
        self.assertGreaterEqual(self.app.status.height,self.app.status.texture_size[1])
        self.drain()
        self.assertIn('Overload recovered',self.app.status.text); self.assertFalse(r.running)
    def test_management_action_rejects_until_pause_barrier_finishes(self):
        self.debt(); self.assertFalse(self.app._management_ready())
        self.assertEqual(self.app.session.runtime.state,'PLAYER_DRAIN'); self.drain()
        self.assertTrue(self.app._management_ready())
    def test_pending_action_does_not_run_after_runtime_failure(self):
        self.debt(); s=self.app.session; called=[]
        self.app._after_runtime_pause(lambda:called.append('bad'))
        s.runtime._stop_error('injected failure')
        self.app.tick(0); self.assertEqual(called,[]); self.assertIsNone(self.app._pending_runtime_action)
    def test_session_replacement_revokes_old_deferred_action(self):
        self.debt(); called=[]
        self.app._after_runtime_pause(lambda:called.append('old world'))
        old=self.app.session.runtime
        self.app.session.new_game('CEO','Replacement Air','MNL')
        self.app.tick(0)
        self.assertTrue(old.closed); self.assertEqual(called,[])
        self.assertIsNone(self.app._pending_runtime_action)
    def test_exit_close_discards_only_after_explicit_unsaved_choice(self):
        self.debt(); self.app.request_exit(); self.drain()
        with patch.object(self.app,'stop') as stop:
            self.app._resolve_departure('cancel',self.app.stop); stop.assert_not_called()
            next(w for w in self.app._popup.content.children if isinstance(w,Button) and w.text=='Leave without saving').dispatch('on_release')
            stop.assert_called_once()

if __name__=='__main__': unittest.main()
