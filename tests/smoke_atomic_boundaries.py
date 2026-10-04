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


def child(root, career, divine, booking_fence=False, ultra_seconds=.5):
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
            self.logged_phase=None
            self.session.new_game=lambda *a,**k: (_ for _ in ()).throw(AssertionError('New Game forbidden'))
        def _error(self,title,error): self.failure=f'{title}: {error}'; self.stop()
        def tick(self,dt):
            if not self.session.active: return super().tick(dt)
            before=time.perf_counter(); prior=len(self.session.world['world_state']['event_history'])
            engine=[0.0]; presentation=[0.0]
            from unittest.mock import patch
            original_pump=self.session.pump; original_refresh=self.refresh
            from game.simulation.shared_candidate import SharedResolutionRequest
            shared=SharedResolutionRequest._shared_batch; strict=SharedResolutionRequest._strict_one
            units={'shared':0,'strict':0}
            def shared_unit(request):
                units['shared']+=1
                return shared(request)
            def strict_unit(request):
                units['strict']+=1
                return strict(request)
            def pump():
                start=time.perf_counter()
                try: return original_pump()
                finally: engine[0]+=time.perf_counter()-start
            def refresh(**kw):
                start=time.perf_counter()
                try: return original_refresh(**kw)
                finally: presentation[0]+=time.perf_counter()-start
            with patch.object(self.session,'pump',pump),patch.object(self,'refresh',refresh), patch.object(SharedResolutionRequest,'_shared_batch',shared_unit), patch.object(SharedResolutionRequest,'_strict_one',strict_unit): super().tick(dt)
            self.samples.append(dict(seconds=time.perf_counter()-before,engine_seconds=engine[0],presentation_seconds=presentation[0],events=len(self.session.world['world_state']['event_history'])-prior,units=units,ratio=self.session.runtime.ratio,pacing=self.session.runtime.last_pump,state=self.session.runtime.state,phase=self.phase))
        def click(self,root,text):
            next(w for w in root.walk() if isinstance(w,Button) and w.text==text).dispatch('on_release')
        def on_start(self):
            super().on_start(); Clock.schedule_interval(self.step,.2); Clock.schedule_once(self.timeout,600 if ultra_seconds>.5 else 240)
        def timeout(self,dt): self.failure='Smoke timed out'; self.stop()
        def finish(self):
            durations=sorted(r['seconds'] for r in self.samples)
            print(json.dumps(dict(status='PASS',divine=divine,direct_load=True,event_types=self.event_types,speeds=4,save_reload_exact=True,no_offline_progress=True,callbacks=len(durations),median_callback_seconds=durations[len(durations)//2],p95_callback_seconds=durations[int(.95*(len(durations)-1))],max_callback_seconds=max(durations),units={key:sum(r['units'][key] for r in self.samples) for key in ('shared','strict')},max_gui_refresh_seconds=max(r['presentation_seconds'] for r in self.samples),booking_fence_requested=booking_fence,ultra_observation_requested_seconds=ultra_seconds,resumed_after_reload=ultra_seconds>.5,samples=self.samples)),flush=True)
            self.phase=5; self.stop()
        def step(self,dt):
            try:
                if self.session.active:
                    s=self.session
                    if s.runtime.blocked or s.runtime.state=='ERROR':
                        raise RuntimeError(s.runtime.diagnostic)
                    if self.logged_phase!=self.phase:
                        print(json.dumps(dict(native_progress=self.phase,utc=s.world['simulation']['time_utc'],state=s.runtime.state,credit_ns=s.runtime.credit_ns,speed_step=self.speed)),flush=True)
                        self.logged_phase=self.phase
                if self.phase==0:
                    self.click(self.screens.get_screen('title'),'Load Game')
                    label=self.session.list_careers()[0]['airline_name']+'  |'
                    next(w for w in self._popup.content.walk() if isinstance(w,Button) and w.text.startswith(label)).dispatch('on_release')
                    self.click(self._popup.content,'Current manual save')
                    s=self.session; assert s.career_id==career and s.runtime.state=='PAUSED' and s.runtime.credit_ns==0
                    self.initial=set(s.world['world_state']['event_history'])
                    # Controlled finite earned-credit stimulus avoids hours of
                    # wall waiting. Actual registered handlers/production pump.
                    kind='STAGE1_FLIGHT_DEPARTURE' if divine and not booking_fence else 'DAILY_BOOKING_CHECKPOINT'
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
                    if (not divine or booking_fence) and 'DAILY_BOOKING_CHECKPOINT' not in types: return
                    self.event_types=sorted(types); self.pause(); self.phase=2
                elif self.phase==2:
                    if self.session.runtime.draining: return
                    if self.speed<4:
                        self.resume(['Normal Speed','Fast','Very Fast','Ultra'][self.speed]); self.started=time.perf_counter(); self.phase=3
                    else: self.phase=4
                elif self.phase==3:
                    if time.perf_counter()-self.started< (ultra_seconds if self.speed==3 else .5): return
                    self.pause(); self.speed+=1; self.phase=2
                elif self.phase==4:
                    s=self.session
                    assert s.runtime.state in ('PAUSED','RECOVERED'), (s.runtime.state,s.runtime.diagnostic)
                    assert s.validate(), 'committed native world failed full validation'
                    self.save_game(); self._dismiss(); exact=s.authoritative_bytes(); utc=s.world['simulation']['time_utc']
                    s.load_saved(career); assert exact==s.authoritative_bytes() and s.runtime.credit_ns==0
                    assert s.runtime.state=='PAUSED'; time.sleep(.05); s.pump()
                    assert s.world['simulation']['time_utc']==utc
                    self._enter_game(); self.refresh(force=True)
                    if ultra_seconds>.5:
                        for view in ('Fleet','Flights','Finance','Overview'):
                            self.show_view(view)
                            assert s.world['simulation']['time_utc'] in self.status.text
                        self.resume('Normal Speed');self.started=time.perf_counter();self.phase=6
                    else: self.finish()
                elif self.phase==6:
                    if time.perf_counter()-self.started<.5: return
                    self.pause();self.phase=7
                elif self.phase==7:
                    if self.session.runtime.draining: return
                    assert self.session.runtime.state=='PAUSED' and self.session.validate()
                    self.finish()
            except Exception:
                import traceback
                self.failure=traceback.format_exc(); self.stop()
    app=Smoke(); app.run()
    if app.failure or app.phase!=5:
        print(json.dumps(dict(status='FAIL',phase=app.phase,error=app.failure or 'incomplete smoke',samples=app.samples)),flush=True)
        raise RuntimeError(app.failure or 'incomplete smoke')


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture');p.add_argument('--root');p.add_argument('--career');p.add_argument('--divine',action='store_true');p.add_argument('--booking-fence',action='store_true');p.add_argument('--ultra-seconds',type=float,default=.5);a=p.parse_args()
    import math
    if not math.isfinite(a.ultra_seconds) or a.ultra_seconds<=0:
        p.error('--ultra-seconds must be finite and positive')
    os.environ.setdefault('KIVY_NO_ARGS','1');os.environ.setdefault('KIVY_NO_FILELOG','1')
    if a.root: child(a.root,a.career,a.divine,a.booking_fence,a.ultra_seconds)
    else:
        with tempfile.TemporaryDirectory(prefix='at-atomic-native-') as root:
            cmd=[sys.executable,'-B','-m','tests.smoke_atomic_boundaries','--root',root,'--career',prepare(root,a.fixture)]
            if a.fixture: cmd.append('--divine')
            if a.booking_fence: cmd.append('--booking-fence')
            cmd.extend(['--ultra-seconds',str(a.ultra_seconds)])
            subprocess.run(cmd,check=True,timeout=900 if a.ultra_seconds>.5 else 300)
if __name__=='__main__': main()
