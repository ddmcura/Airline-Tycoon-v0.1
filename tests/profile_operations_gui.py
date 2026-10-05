"""Native Patch 3 SDL2 smoke, production session/runtime; all artifacts TEMP."""
import gc
import json
import os
import tempfile
import time
os.environ.setdefault('KIVY_NO_ARGS','1');os.environ.setdefault('KIVY_NO_FILELOG','1')
from kivy.clock import Clock
from kivy.core.window import Window
from app.gui.app import AirlineTycoonApp
from app.gui.operations_pages import FlightsPage, BookingsPage
from app.session import Stage1Session
from tests.test_gui_foundation import FakeClock


class Smoke(AirlineTycoonApp):
    def __init__(self,session,clock):
        super().__init__(session_factory=lambda:session)
        self.input_clock=clock;self.index=0;self.error=None;self.finite_checks=0
        self.sequence=['Flights','Bookings','Schedule','Fleet','Research','Flights','Bookings','Overview']*10
        self.navigation=[];self.timings={'Flights':[],'Bookings':[]};self.entries={'Flights':[],'Bookings':[]};self.counts=[];self.states=set()
        self.first_flight=next(iter(session.world['world_state']['dated_flights']))
    def on_start(self):
        super().on_start();self._enter_game();self.resume('Normal Speed');Clock.schedule_once(self.step,.2)
    def _error(self,title,error):raise RuntimeError(f'{title}: {error}')
    def step(self,dt):
        try:
            if self.index==len(self.sequence):self.finish();return
            view=self.sequence[self.index];started=time.perf_counter();self.show_view(view)
            elapsed=time.perf_counter()-started
            self.navigation.append(elapsed)
            if view in self.entries:self.entries[view].append(elapsed)
            assert len(self.page_host.children)==1
            self.input_clock.advance(.5);self.tick(0)
            self.states.add(self.session.world['world_state']['dated_flights'][self.first_flight]['status'])
            page=self.content
            if isinstance(page,(FlightsPage,BookingsPage)):
                assert self.session.runtime.running
                controls=page.controls;viewport=page.viewport
                if isinstance(page,FlightsPage):
                    page.shift(-1);page.today();page.shift(1);page.today()
                else:
                    page.market_selector.text='DVO -> MNL';page.market_selector.text='MNL -> DVO'
                    page.shift(-1);page.current();page.shift(1);page.current()
                page.viewport.scroll_x=.4;page.viewport.scroll_y=.5
                page.viewport.effect_y.velocity=120;page.viewport.effect_y.update_velocity(4)
                started=time.perf_counter();self.refresh(force=True);self.timings[view].append(time.perf_counter()-started)
                assert page.controls is controls and page.viewport is viewport and page.body.children and page.finite()
                self.finite_checks+=1
            if view=='Overview':
                gc.collect();self.counts.append(len(list(self.screens.walk())))
                self.resume(('Normal Speed','Fast','Very Fast')[self.index//8%3])
            self.index+=1;Clock.schedule_once(self.step,.1)
        except Exception:
            import traceback
            self.error=traceback.format_exc();print(self.error,flush=True);self.stop()
    def finish(self):
        self.show_view('Bookings');page=self.content;controls=page.controls;viewport=page.viewport
        page.market_selector.text='MNL -> DVO';page.viewport.scroll_x=.4
        # Cross a real Booking fence and several flight completions through the
        # existing explicit resolver, then refresh the same visible matrix.
        self.session.advance_to('2026-09-03T00:00:00Z');self.resume('Fast');self.refresh(force=True)
        assert page is self.content and page.controls is controls and page.viewport is viewport
        assert page.finite() and page.body.children
        assert len(self.session.world['world_state']['booking_state']['booking_checkpoints'])>=2
        assert self.session.world['world_state']['flight_results']
        assert self.session.validate()
        Window.restore();Window.size=(1200,900)
        Clock.schedule_once(self.capture,.2)
    def capture(self,dt):
        try:
            booking=Window.screenshot(name=os.path.join(tempfile.gettempdir(),'at-operations-bookings.png'))
            self.show_view('Flights');self.content.day_picker.select('2026-09-02')
            Clock.schedule_once(lambda dt:self.final_capture(booking),.2)
        except Exception:
            import traceback
            self.error=traceback.format_exc();print(self.error,flush=True);self.stop()
    def final_capture(self,booking):
        try:
            flight=Window.screenshot(name=os.path.join(tempfile.gettempdir(),'at-operations-flights.png'))
            self.session.hard_pause();self.session.save_manual();expected=self.session.authoritative_bytes()
            self.session.load_saved(self.session.career_id);assert self.session.authoritative_bytes()==expected
            assert not self.session.runtime.running
            metrics=lambda values:{'median_s':sorted(values)[len(values)//2],'max_s':max(values)}
            print(json.dumps({'native_smoke':'PASS','navigation':metrics(self.navigation),'entry':{k:metrics(v) for k,v in self.entries.items()},'refresh':{k:metrics(v) for k,v in self.timings.items()},
                'navigations':len(self.sequence),'finite_checks':self.finite_checks,'overview_widget_counts':self.counts,
                'page_refresh_timers':0,'app_ticker':int(self._ticker is not None),'flight_states_observed':sorted(self.states),
                'save_reload_exact':True,'screenshots':[booking,flight]}),flush=True)
            self.stop()
        except Exception:
            import traceback
            self.error=traceback.format_exc();print(self.error,flush=True);self.stop()


def main():
    with tempfile.TemporaryDirectory(prefix='at-operations-smoke-') as root:
        clock=FakeClock();session=Stage1Session(save_root=root,runtime_clock=clock)
        session.new_game('CEO','Operations Smoke','MNL')
        ports={r['reference_code']:r['airport_id'] for r in session.airports()}
        session.purchase(session.preview_purchase('airbus-a320neo',ports['MNL']))
        for aircraft in session.fleet():
            draft=session.begin_scheduling(aircraft['aircraft_id'])
            for day in (2,3):
                for hour,minute in ((0,30),(5,0),(9,30),(15,0)):
                    draft.add(ports['MNL'],ports['DVO'],departure_utc=f'2026-09-{day:02d}T{hour:02d}:{minute:02d}:00Z',fare_minor=11600)
                    draft.add_return(fare_minor=11600)
            session.save_scheduling(draft)
        session.advance_to('2026-09-02T00:00:00Z')
        app=Smoke(session,clock);app.run()
        if app.error:raise RuntimeError(app.error)

if __name__=='__main__':main()
