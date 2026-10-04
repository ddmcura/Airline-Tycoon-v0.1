"""Fresh native Load, flight/fence, speeds and exact save; TEMP only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def prepare(root, fixture):
    from app.session import Stage1Session
    from tests.flight_fixtures import flight_world
    world=json.loads(Path(fixture).read_text(encoding='utf-8'))['world'] if fixture else flight_world(1)
    s=Stage1Session(save_root=root); s.world=world
    s.career_id=s.save_store.new_career_id(); s.save_manual()
    return s.career_id


def child(root, career, divine):
    from app.gui.app import AirlineTycoonApp
    from app.session import Stage1Session
    from game.simulation.pacing import NANOSECOND
    from game.world_state.timestamps import parse_canonical_utc
    from kivy.clock import Clock
    from kivy.uix.button import Button
    class Smoke(AirlineTycoonApp):
        def __init__(self):
            super().__init__(session_factory=lambda:Stage1Session(save_root=root))
            self.phase=0; self.samples=[]; self.failure=None; self.speed=0
            self.session.new_game=lambda *a,**k: (_ for _ in ()).throw(AssertionError('New Game forbidden'))
        def _error(self,title,error): self.failure=f'{title}: {error}'; self.stop()
        def tick(self,dt):
            if not self.session.active: return super().tick(dt)
            before=time.perf_counter(); prior=len(self.session.world['world_state']['event_history'])
            engine=[0.0]; presentation=[0.0]
            from unittest.mock import patch
            original_pump=self.session.pump; original_refresh=self.refresh
            def pump():
                start=time.perf_counter()
                try: return original_pump()
                finally: engine[0]+=time.perf_counter()-start
            def refresh(**kw):
                start=time.perf_counter()
                try: return original_refresh(**kw)
                finally: presentation[0]+=time.perf_counter()-start
            with patch.object(self.session,'pump',pump),patch.object(self,'refresh',refresh): super().tick(dt)
            self.samples.append(dict(seconds=time.perf_counter()-before,engine_seconds=engine[0],presentation_seconds=presentation[0],events=len(self.session.world['world_state']['event_history'])-prior))
        def click(self,root,text):
            next(w for w in root.walk() if isinstance(w,Button) and w.text==text).dispatch('on_release')
        def on_start(self):
            super().on_start(); Clock.schedule_interval(self.step,.2); Clock.schedule_once(self.timeout,240)
        def timeout(self,dt): self.failure='Smoke timed out'; self.stop()
        def step(self,dt):
            try:
                if self.phase==0:
                    self.click(self.screens.get_screen('title'),'Load Game')
                    label=self.session.list_careers()[0]['airline_name']+'  |'
                    next(w for w in self._popup.content.walk() if isinstance(w,Button) and w.text.startswith(label)).dispatch('on_release')
                    self.click(self._popup.content,'Current manual save')
                    s=self.session; assert s.career_id==career and s.runtime.state=='PAUSED' and s.runtime.credit_ns==0
                    self.initial=set(s.world['world_state']['event_history'])
                    # Controlled finite earned-credit stimulus avoids hours of
                    # wall waiting. Actual registered handlers/production pump.
                    kind='STAGE1_FLIGHT_DEPARTURE' if divine else 'DAILY_BOOKING_CHECKPOINT'
                    target=min(e['due_at_utc'] for e in s.world['world_state']['pending_events'].values() if e['event_type']==kind)
                    self.target=target
                    self.resume('Normal Speed')
                    s.runtime.credit_ns=int((parse_canonical_utc(target)-parse_canonical_utc(s.world['simulation']['time_utc'])).total_seconds())*NANOSECOND
                    self.phase=1
                elif self.phase==1:
                    s=self.session
                    if s.world['simulation']['time_utc']<self.target: return
                    types={e['event_type'] for k,e in s.world['world_state']['event_history'].items() if k not in self.initial}
                    if 'STAGE1_FLIGHT_DEPARTURE' not in types: return
                    if not divine and 'DAILY_BOOKING_CHECKPOINT' not in types: return
                    self.event_types=sorted(types); self.pause(); self.phase=2
                elif self.phase==2:
                    if self.session.runtime.draining: return
                    if self.speed<4:
                        self.resume(['Normal Speed','Fast','Very Fast','Ultra'][self.speed]); self.started=time.perf_counter(); self.phase=3
                    else: self.phase=4
                elif self.phase==3:
                    if time.perf_counter()-self.started<.5: return
                    self.pause(); self.speed+=1; self.phase=2
                elif self.phase==4:
                    s=self.session; assert s.runtime.state=='PAUSED' and s.validate()
                    self.save_game(); self._dismiss(); exact=s.authoritative_bytes(); utc=s.world['simulation']['time_utc']
                    s.load_saved(career); assert exact==s.authoritative_bytes() and s.runtime.credit_ns==0
                    assert s.runtime.state=='PAUSED'; time.sleep(.05); s.pump()
                    assert s.world['simulation']['time_utc']==utc
                    self._enter_game(); self.refresh(force=True)
                    durations=sorted(r['seconds'] for r in self.samples)
                    print(json.dumps(dict(status='PASS',divine=divine,direct_load=True,event_types=self.event_types,speeds=4,save_reload_exact=True,no_offline_progress=True,callbacks=len(durations),median_callback_seconds=durations[len(durations)//2],p95_callback_seconds=durations[int(.95*(len(durations)-1))],max_callback_seconds=max(durations),samples=self.samples)),flush=True)
                    self.phase=5; self.stop()
            except Exception:
                import traceback
                self.failure=traceback.format_exc(); self.stop()
    app=Smoke(); app.run()
    if app.failure or app.phase!=5: raise RuntimeError(app.failure or 'incomplete smoke')


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture');p.add_argument('--root');p.add_argument('--career');p.add_argument('--divine',action='store_true');a=p.parse_args()
    os.environ.setdefault('KIVY_NO_ARGS','1');os.environ.setdefault('KIVY_NO_FILELOG','1')
    if a.root: child(a.root,a.career,a.divine)
    else:
        with tempfile.TemporaryDirectory(prefix='at-atomic-native-') as root:
            cmd=[sys.executable,'-B','-m','tests.smoke_atomic_boundaries','--root',root,'--career',prepare(root,a.fixture)]
            if a.fixture: cmd.append('--divine')
            subprocess.run(cmd,check=True,timeout=300)
if __name__=='__main__': main()
