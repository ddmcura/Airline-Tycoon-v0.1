"""Fresh native Kivy Patch 4 workflow; authoritative side-effect witnesses TEMP."""
from copy import deepcopy
from datetime import date
import json,os,tempfile,time
os.environ.setdefault('KIVY_NO_ARGS','1');os.environ.setdefault('KIVY_NO_FILELOG','1')
from kivy.clock import Clock
from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session

class Smoke(AirlineTycoonApp):
    def on_start(self):
        super().on_start();Clock.schedule_once(self.exercise,.2)
    def _error(self,title,error):
        self.errors.append((title,str(error)))
    def exercise(self,dt):
        try:
            self.errors=[];self.create_new_game('CEO','Reposition Smoke','MNL')
            ports={r['reference_code']:r['airport_id'] for r in self.session.airports()}
            aircraft=self.session.fleet()[0]['aircraft_id'];before=self.session.authoritative_bytes()
            def planner(origin,destination):
                self.show_view('Schedule');self.start_schedule(aircraft)
                self._schedule_week=date(2026,9,7);self.refresh(force=True)
                self._builder_origin=ports[origin];self._builder_destination=ports[destination]
                self._builder_time='08:00';self._builder_return=False;self._builder_earliest=False
                self.refresh(force=True)
            planner('DVO','MNL');self._builder_day_picker.apply_preset('Daily')
            start=time.perf_counter();assert self.add_builder_flights()==7;daily=time.perf_counter()-start
            assert len(self._draft.legs)==7 and self.session.authoritative_bytes()==before
            self._save_schedule(None,continuous=True)
            assert self.errors and 'actual positioning' in self.errors[-1][1]
            assert len(self._draft.legs)==7 and self.session.authoritative_bytes()==before
            planner('DVO','MNL');self._builder_day_picker.apply_preset('MWF')
            assert self.add_builder_flights()==3
            self._builder_origin=ports['MNL'];self._builder_destination=ports['CEB'];self._builder_time='15:00'
            assert self.add_builder_flights(target_dates=('2026-09-07',))==1
            # An insertion that leaves no time before Wednesday's DVO obligation.
            self._builder_origin=ports['CEB'];self._builder_destination=ports['MNL'];self._builder_time='05:00'
            valid=deepcopy(self._draft.legs)
            assert self.add_builder_flights(target_dates=('2026-09-09',)) is None
            assert self._draft.legs==valid and 'REPOSITIONING_INFEASIBLE' in self.errors[-1][1]
            planner('DVO','MNL');self._builder_earliest=True
            assert self.add_builder_flights(target_dates=('2026-09-01',))==1
            assert self._draft.legs[0]['departure_utc']=='2026-09-01T02:40:00Z'
            assert self.session.authoritative_bytes()==before
            planner('MNL','DVO');self._builder_return=True
            assert self.add_builder_flights(target_dates=('2026-09-07',))==2
            assert self._draft.legs[1]['departure_utc']=='2026-09-07T02:10:00Z'
            self._save_schedule(None)
            assert len(self.session.world['world_state']['dated_flights'])==2
            self.session.save_manual();expected=self.session.authoritative_bytes()
            self.session.load_saved(self.session.career_id)
            assert self.session.authoritative_bytes()==expected and not self.session.runtime.running
            assert self.session.validate()
            print(json.dumps({'native_smoke':'PASS','daily_builder_s':daily,'daily':7,'mwf':3,'valid_gap_insert':True,'invalid_insert_atomic':True,'earliest_utc':'2026-09-01T02:40:00Z','return_utc':'2026-09-07T02:10:00Z','implicit_publication_rejected':True,'real_pair_published':2,'save_reload_exact':True}),flush=True)
        except Exception:
            import traceback
            self.error=traceback.format_exc();print(self.error,flush=True)
        finally:self.stop()

def main():
    with tempfile.TemporaryDirectory(prefix='at-reposition-smoke-') as root:
        app=Smoke(session_factory=lambda:Stage1Session(save_root=root,runtime_clock=lambda:0));app.error=None;app.run()
        if app.error:raise RuntimeError(app.error)

if __name__=='__main__':main()
