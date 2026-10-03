"""Opt-in displayed Kivy advancement smoke; all career files are temporary.
python -B -m tests.smoke_advancement --fixtures <benchmark-fixtures>
Use --mode new or load; --baseline permits comparison against the archived code.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time


def run(args):
    os.environ.setdefault('KIVY_NO_ARGS', '1')
    os.environ.setdefault('KIVY_NO_FILELOG', '1')
    from app.gui.app import AirlineTycoonApp
    from app.session import Stage1Session
    from game.scheduling.recurrence import publish_rolling_window
    from tests.profile_scheduling import definitions, identities, digest, memory
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.uix.button import Button

    with tempfile.TemporaryDirectory(prefix='at-advance-smoke-') as root:
        prepared = Stage1Session(save_root=root, runtime_clock=lambda:0)
        if args.mode == 'load':
            # Fixture is already valid; save through the real JSON save store.
            prepared.world = json.loads((args.fixtures/(args.case+'.json')).read_text(encoding='utf-8'))
            prepared.career_id = prepared.save_store.new_career_id()
            prepared.save_manual()
            career = prepared.career_id
        prepared.close()

        class Smoke(AirlineTycoonApp):
            def __init__(self):
                super().__init__(session_factory=lambda:Stage1Session(save_root=root,runtime_clock=lambda:0))
                self.stage=0
                self.failure=None
                self.renders=0
                self.render_seconds=0
                self.ticks=0
                self.longest_tick=0
                self.headers=0
                self.header_seconds=0
                original=self.session.header
                def header():
                    started=time.perf_counter()
                    try:
                        return original()
                    finally:
                        self.headers+=1
                        self.header_seconds+=time.perf_counter()-started
                self.session.header=header
            def _render_view(self):
                started=time.perf_counter()
                try:
                    return super()._render_view()
                finally:
                    self.renders+=1
                    self.render_seconds+=time.perf_counter()-started
            def tick(self, dt):
                started=time.perf_counter()
                try:
                    return super().tick(dt)
                finally:
                    if self.stage==1:
                        self.ticks+=1
                        self.longest_tick=max(self.longest_tick,time.perf_counter()-started)
            def _error(self,title,error):
                self.failure=f'{title}: {error}'
                self.stop()
            def on_start(self):
                super().on_start()
                Clock.schedule_once(self.start_case,.3)
                Clock.schedule_interval(self.check,.1)
            def click(self,root,text):
                next(w for w in root.walk() if isinstance(w,Button) and w.text==text).dispatch('on_release')
            def start_case(self,dt):
                try:
                    if args.mode=='new':
                        self.create_new_game('Smoke','Advance smoke','MNL')
                        owner,aircraft,_=identities(self.session.world)
                        definitions(self.session.world,aircraft,range(7),rolling=True)
                        result=publish_rolling_window(self.session.world,owner)
                        assert result.succeeded,result
                    else:
                        self.click(self.screens.get_screen('title'),'Load Game')
                        label=next(w.text for w in self._popup.content.walk() if isinstance(w,Button) and '2026-' in w.text)
                        self.click(self._popup.content,label)
                        self.click(self._popup.content,'Current manual save')
                        assert self.session.career_id==career
                    assert self.session.validate()
                    self.show_view(args.view)
                    self.before=deepcopy(self.session.world)
                    self.start_renders=self.renders
                    self.start_headers=self.headers
                    self.start_render_time=self.render_seconds
                    self.start_header_time=self.header_seconds
                    self.started=time.perf_counter()
                    self.stage=1
                    self._begin_seconds(args.days*86400)
                except Exception:
                    import traceback
                    self.failure=traceback.format_exc()
                    self.stop()
            def check(self,dt):
                if self.stage!=1:
                    return
                if self.session.advancing and time.perf_counter()-self.started<args.budget:
                    return
                try:
                    limited=self.session.advancing
                    if limited:
                        self.session.cancel_advance()
                    elapsed=time.perf_counter()-self.started
                    assert self.session.runtime.diagnostic is None
                    assert self.session.validate()
                    state=self.session.world['world_state']
                    records=[e for key,e in state['event_history'].items() if key not in self.before['world_state']['event_history']]
                    result={'mode':args.mode,'view':args.view,'days':args.days,'seconds':elapsed,
                        'status':'TIME_BUDGET' if limited else 'COMPLETED',
                        'window':list(Window.size),'events':len(records),
                        'event_types':dict(Counter(e['event_type'] for e in records)),
                        'renders':self.renders-self.start_renders,
                        'render_seconds':self.render_seconds-self.start_render_time,
                        'headers':self.headers-self.start_headers,
                        'header_seconds':self.header_seconds-self.start_header_time,
                        'ticks':self.ticks,'longest_tick':self.longest_tick,
                        'world_sha256':digest(self.session.world),'memory':memory()}
                    if not limited and not args.baseline:
                        assert result['renders']==1,result
                    self.session.save_manual()
                    exact=self.session.authoritative_bytes()
                    self.session.load_saved(self.session.career_id)
                    assert self.session.authoritative_bytes()==exact
                    result['save_reload_exact_paused']=True
                    for view in ('Fleet','Flights','Finance','Schedule'):
                        self.show_view(view)
                    assert self.session.validate()
                    print(json.dumps(result),flush=True)
                    self.stage=2
                    self.stop()
                except Exception:
                    import traceback
                    self.failure=traceback.format_exc()
                    self.stop()

        app=Smoke()
        app.run()
        if app.failure or app.stage!=2:
            raise RuntimeError(app.failure or 'smoke did not finish')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--case',default='observed-save')
    parser.add_argument('--mode',choices=('new','load'),default='load')
    parser.add_argument('--view',default='Flights')
    parser.add_argument('--days',type=int,default=2)
    parser.add_argument('--budget',type=float,default=120)
    parser.add_argument('--baseline',action='store_true')
    run(parser.parse_args())

if __name__=='__main__':
    main()
