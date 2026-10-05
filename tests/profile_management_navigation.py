"""Opt-in native Windows/Kivy Patch 2 smoke; all saves/artifacts are TEMP.

Run python -m tests.profile_management_navigation. Programmatic observations do
not establish human smoothness or Stage 3F runtime capacity.
"""
import gc
import json
import os
import tempfile
import time
import weakref
os.environ.setdefault('KIVY_NO_FILELOG','1')
os.environ.setdefault('KIVY_NO_ARGS','1')
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.button import Button
from app.gui.app import AirlineTycoonApp
from app.gui.management_table import ManagementTable
from app.session import Stage1Session


class ClockInput:
    def __init__(self): self.ns=0
    def __call__(self): return self.ns


class Smoke(AirlineTycoonApp):
    def __init__(self, session, clock, root):
        super().__init__(session_factory=lambda:session)
        self.clock_input=clock;self.root_dir=root;self.index=0;self.error=None
        self.refs=[];self.counts=[];self.latencies=[];self.table_checks=0
        self.sequence=['Fleet','Aircraft Details','Fleet','Research','Schedule','Research','Fleet','Overview']*10
        self.aircraft=session.fleet()[0]['aircraft_id']
        self.ports={r['reference_code']:r['airport_id'] for r in session.airports()}
    def _error(self,title,error): raise RuntimeError(f'{title}: {error}')
    def on_start(self):
        super().on_start();self._enter_game();self.resume('Normal Speed')
        Clock.schedule_once(self.step,.2)
    def step(self,dt):
        try:
            if self.index >= len(self.sequence):
                self.finish();return
            view=self.sequence[self.index];start=time.perf_counter()
            if view=='Aircraft Details':self.open_aircraft_details(self.aircraft)
            else:self.show_view(view)
            assert len(self.page_host.children)==1
            page=self._active_page;self.refs.append(weakref.ref(page))
            if isinstance(page,ManagementTable):
                self.clock_input.ns+=300000000;self.tick(0)
                page.viewport.scroll_x=.35;page.viewport.scroll_y=.4
                page.viewport.effect_y.velocity=120;page.viewport.effect_y.update_velocity(4)
                page.search.text='no such record';assert not page.visible_rows
                page.reset();page.sort_by(page.columns[1][0]);self.refresh(force=True)
                assert page.finite() and page.body.children
                self.table_checks+=1
                if view=='Fleet':
                    page.filter_widgets['hub'][0].text='MNL';page.reset()
                if view=='Research':
                    assert page.destination.search('Davao')[0]['airport_id']==self.ports['DVO']
                    page.search.text='DVO';assert len(page.visible_rows)==1;page.reset()
            if view=='Schedule':
                # Real multiple-compatible chooser, then the single existing builder.
                self.show_view('Research');self.research_add_flight(self.ports['MNL'],self.ports['DVO'])
                assert self._popup is not None
                registration=self.session.scheduling_aircraft(self.aircraft)['display_registration']
                next(w for w in self._popup.content.walk() if isinstance(w,Button) and registration in w.text).dispatch('on_release')
                assert self.current_view=='Schedule' and self._draft.aircraft_id==self.aircraft
                assert self._builder_origin==self.ports['MNL'] and self._builder_destination==self.ports['DVO']
                assert self._draft.legs==[]
                self.resume(('Normal Speed','Fast','Very Fast')[self.index//8%3])
            self.latencies.append(time.perf_counter()-start)
            if view=='Overview':
                gc.collect();self.counts.append(len(list(self.screens.walk())))
            self.index+=1;Clock.schedule_once(self.step,.1)
        except Exception:
            import traceback
            self.error=traceback.format_exc();print(self.error,flush=True);self.stop()
    def finish(self):
        self.session.hard_pause();assert self.session.validate()
        self.session.save_manual();expected=self.session.authoritative_bytes();self.session.load_saved(self.session.career_id)
        assert self.session.authoritative_bytes()==expected
        self.show_view('Research');self.refresh(force=True)
        Clock.schedule_once(self.capture,.2)
    def capture(self,dt):
        try:
            assert self.content.finite()
            shot=Window.screenshot(name=os.path.join(tempfile.gettempdir(),'at-management-research.png'))
            self.show_view('Fleet');Clock.schedule_once(lambda dt:self.capture_fleet(shot),.2)
        except Exception:
            import traceback
            self.error=traceback.format_exc();print(self.error,flush=True);self.stop()
    def capture_fleet(self,shot):
        assert self.content.finite()
        fleet_shot=Window.screenshot(name=os.path.join(tempfile.gettempdir(),'at-management-fleet.png'))
        gc.collect()
        print(json.dumps({'native_smoke':'PASS','navigations':len(self.sequence),
              'overview_widget_counts':self.counts,'retained_page_refs':sum(r() is not None for r in self.refs),
              'retained_page_types':sorted({type(r()).__name__ for r in self.refs if r() is not None}),
              'retained_distinct_pages':len({id(r()) for r in self.refs if r() is not None}),
              'page_refresh_timers':0,'application_ticker':int(self._ticker is not None),
              'finite_table_checks':self.table_checks,'median_navigation_s':sorted(self.latencies)[len(self.latencies)//2],
              'max_navigation_s':max(self.latencies),'window_size':list(Window.size),
              'save_reload_exact':True,'screenshots':[shot,fleet_shot]}),flush=True)
        self.stop()


def main():
    with tempfile.TemporaryDirectory(prefix='at-management-smoke-') as root:
        clock=ClockInput();session=Stage1Session(save_root=root,runtime_clock=clock)
        session.new_game('CEO','Management Smoke','MNL')
        ports={r['reference_code']:r['airport_id'] for r in session.airports()}
        session.purchase(session.preview_purchase('airbus-a320neo',ports['MNL']))
        draft=session.begin_scheduling(session.fleet()[0]['aircraft_id'])
        draft.add(ports['MNL'],ports['DVO'],departure_utc='2026-09-01T00:30:00Z',fare_minor=11600)
        draft.add_return(fare_minor=11600);session.save_scheduling(draft)
        app=Smoke(session,clock,root);app.run()
        if app.error:raise RuntimeError(app.error)

if __name__=='__main__':main()
