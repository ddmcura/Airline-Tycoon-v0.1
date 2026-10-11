"""Small reproducible Stage 3F measurements; temporary careers, no real Saves.

Run: python -m tests.profile_quarterly_gui. Times exclude fixture preparation.
No throughput, before/after optimization or large-fleet claim is implied.
"""
import os
os.environ.setdefault('KIVY_NO_ARGS','1')
from copy import deepcopy
import json
import statistics
import tempfile
from time import perf_counter

from app.session import Stage1Session
from app.quarterly_planning import QuarterlyPlanningController
from tests import test_quarterly_backend as fixtures


def main():
    from app.gui.app import AirlineTycoonApp
    base,pid,_,_,_,_=fixtures.QuarterlyBackendTests.fixture(quarter='2027-Q2',published=False)
    measurements={}
    with tempfile.TemporaryDirectory() as temporary:
        session=Stage1Session(save_root=temporary,runtime_clock=lambda:0)
        app=AirlineTycoonApp(session_factory=lambda:session,quarterly_development=True)
        app.build()
        def reset():
            session.cancel_advance()
            if session.runtime:session.runtime.cancel_work();session.runtime.closed=True
            session.world=deepcopy(base);session.runtime=None
            session.career_id=session.save_store.new_career_id()
            session._ensure_runtime();session._bind_owned_reads()
            controller=QuarterlyPlanningController(session);controller.refresh()
            return controller
        def published():
            controller=reset();preparation=controller.prepare_publication()
            assert preparation.succeeded,preparation.issues
            result=controller.confirm_publication();assert result.succeeded,result.issues
            return controller
        def measure(name,setup,action):
            values=[];sizes=[]
            for _ in range(3):
                controller=setup()
                world=session.world['world_state']
                sizes.append(dict(aircraft=len(world['aircraft']),plans=len(world['weekly_plans']),
                    frequencies=sum(len(p['revisions'][str(p['current_revision'])]['slots']) for p in world['weekly_plans'].values()),
                    dated_flights=len(world['dated_flights']),bookings=len(world['bookings']),
                    world_bytes=len(json.dumps(session.world,sort_keys=True,separators=(',',':')).encode())))
                start=perf_counter();action(controller);values.append(perf_counter()-start)
            measurements[name]=dict(median_s=statistics.median(values),min_s=min(values),max_s=max(values),fixtures=sizes)
        def opening_setup():
            controller=reset();app._enter_game();return controller
        def opening(_):app.show_view('Schedule')
        def cold_list_setup():
            controller=reset();session._bind_owned_reads();return controller
        def edit(controller):
            row=controller.page['rows'][0];controller.select_slot((row['service_id'],row['slot_number']))
            result=controller.fare(12345);assert result.succeeded,result.issues
            app.quarterly_controller=controller
            if app.current_view=='Schedule':app._leave_page()
            app.refresh(force=True)
        def publish(controller):
            prepared=controller.prepare_publication();assert prepared.succeeded,prepared.issues
            result=controller.confirm_publication();assert result.succeeded,result.issues
        def load_setup():
            controller=published();session.save_manual();return controller
        try:
            measure('open_native_planning',opening_setup,opening)
            measure('cold_service_page',cold_list_setup,lambda _:session.quarterly_planning_page())
            measure('readiness',reset,lambda c:c.inspect())
            measure('published_day_2_references',published,lambda _:session.quarterly_published_day(pid,'2027-04-02'))
            measure('fare_edit_and_native_refresh',reset,edit)
            measure('manual_prepare_and_confirm',reset,publish)
            measure('load_and_controller_refresh',load_setup,lambda c:(session.load_saved(session.career_id),c.refresh()))
        finally:
            app._dismiss();app.on_stop()
    print(json.dumps(measurements,indent=2))


if __name__=='__main__':main()
