"""Fresh native Kivy Load/speeds/cooperative pause/save/catch-up smoke, TEMP only."""
import argparse
from copy import deepcopy
import json
import os
import subprocess
import sys
import tempfile
import time


def prepare(root):
    from app.session import Stage1Session
    from tests.flight_fixtures import flight_world
    s=Stage1Session(save_root=root,runtime_clock=lambda:0); s.world=flight_world(1)
    s.career_id=s.save_store.new_career_id(); s.save_manual(); return s.career_id

def child(root,career):
    from app.gui.app import AirlineTycoonApp
    from app.session import Stage1Session
    from game.simulation.pacing import NANOSECOND
    from game.simulation import kernel
    from kivy.clock import Clock
    from kivy.uix.button import Button
    class Smoke(AirlineTycoonApp):
        def __init__(self):
            super().__init__(session_factory=lambda:Stage1Session(save_root=root))
            self.phase=0; self.speed=0; self.samples=[]; self.failure=None
            self.session.new_game=lambda *a,**k:(_ for _ in ()).throw(AssertionError('New Game forbidden'))
        def _error(self,title,error): self.failure=f'{title}: {error}'; self.stop()
        def tick(self,dt):
            if not self.session.active: return super().tick(dt)
            r=self.session.runtime; debt=r.credit_ns; before=time.perf_counter()
            super().tick(dt)
            self.samples.append(dict(seconds=time.perf_counter()-before,backlog_before=debt/NANOSECOND,backlog_after=r.credit_ns/NANOSECOND,events=(r.last_pump or {}).get('events',0),state=r.state))
        def click(self,root,text):
            next(w for w in root.walk() if isinstance(w,Button) and w.text==text).dispatch('on_release')
        def on_start(self):
            super().on_start(); Clock.schedule_interval(self.step,.2); Clock.schedule_once(self.timeout,120)
        def timeout(self,dt): self.failure='Smoke timed out'; self.stop()
        def step(self,dt):
            try:
                if self.phase==0:
                    self.click(self.screens.get_screen('title'),'Load Game')
                    label=self.session.list_careers()[0]['airline_name']+'  |'
                    button=next(w for w in self._popup.content.walk() if isinstance(w,Button) and w.text.startswith(label))
                    button.dispatch('on_release'); self.click(self._popup.content,'Current manual save')
                    assert self.session.career_id==career and self.session.runtime.state=='PAUSED'
                    self.resume('Normal Speed'); self.started=time.perf_counter(); self.phase=1
                elif self.phase==1:
                    if time.perf_counter()-self.started<3: return
                    self.speed+=1
                    if self.speed<4:
                        self.resume(['Normal Speed','Fast','Very Fast','Ultra'][self.speed]); self.started=time.perf_counter()
                    else: self.pause(); self.phase=2
                elif self.phase==2:
                    if self.session.runtime.draining: return
                    assert self.session.runtime.state=='PAUSED' and self.session.validate()
                    self.save_game(); self._dismiss(); self.before=self.session.authoritative_bytes(); self.session.load_saved(career)
                    assert self.before==self.session.authoritative_bytes() and self.session.runtime.credit_ns==0
                    assert self.session.runtime.state=='PAUSED'; self._enter_game()
                    # Controlled, clearly labelled overload stimulus; real events,
                    # not fake completed operations or mutated production data.
                    s=self.session; now=s.world['simulation']['time_utc']
                    for _ in range(20): kernel.schedule_event(s.world,event_type='NO_OP',due_at_utc=now,owner_type='airline',owner_id=s.airline_id)
                    s.runtime.management_changed(); s.runtime.overload_seconds=.01; s.runtime.grace_ns=0
                    self.resume(); s.runtime.credit_ns=300*NANOSECOND; self.phase=3
                elif self.phase==3:
                    if self.session.runtime.state!='RECOVERED': return
                    assert not self.session.runtime.running and self.session.validate()
                    assert self.session.runtime.credit_ns<NANOSECOND
                    self.save_game(); self._dismiss(); exact=self.session.authoritative_bytes(); self.session.load_saved(career)
                    assert exact==self.session.authoritative_bytes()
                    durations=sorted(row['seconds'] for row in self.samples)
                    print(json.dumps(dict(status='PASS',callbacks=len(durations),median_callback_seconds=durations[len(durations)//2],p95_callback_seconds=durations[int(.95*(len(durations)-1))] if len(durations)>=20 else None,max_callback_seconds=max(durations),samples=self.samples,save_reload_exact=True,overload_recovered=True,time_utc=self.session.world['simulation']['time_utc'])),flush=True)
                    self.phase=4; self.stop()
            except Exception:
                import traceback
                self.failure=traceback.format_exc(); self.stop()
    app=Smoke(); app.run()
    if app.failure or app.phase!=4: raise RuntimeError(app.failure or 'incomplete smoke')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root'); p.add_argument('--career'); a=p.parse_args()
    os.environ.setdefault('KIVY_NO_ARGS','1'); os.environ.setdefault('KIVY_NO_FILELOG','1')
    if a.root: child(a.root,a.career)
    else:
        with tempfile.TemporaryDirectory(prefix='at-cooperative-smoke-') as root:
            subprocess.run([sys.executable,'-B','-m','tests.smoke_cooperative_runtime','--root',root,'--career',prepare(root)],check=True,timeout=180)
if __name__=='__main__': main()
