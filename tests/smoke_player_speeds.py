"""Opt-in displayed Kivy speed smoke; temporary saves and real active uptime.

python -B -m tests.smoke_player_speeds --seconds 8 [--fixture valid-world.json]
Each speed reloads the same busy PH starting state, so measurements are comparable.
Reports retained backlog rather than equating accounted credit with processed time.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time


def run(args):
    os.environ.setdefault('KIVY_NO_ARGS','1')
    os.environ.setdefault('KIVY_NO_FILELOG','1')
    from app.gui.app import AirlineTycoonApp
    from app.session import Stage1Session
    from game.simulation.speeds import PLAYER_SPEEDS
    from game.simulation.pacing import active_monotonic_ns, NANOSECOND
    from game.world_state.timestamps import parse_canonical_utc
    from kivy.clock import Clock
    from kivy.uix.button import Button
    from tests.profile_advancement import starting_world
    world = (json.loads(args.fixture.read_text(encoding='utf-8'))
             if args.fixture else starting_world(1))
    with tempfile.TemporaryDirectory(prefix='at-speed-smoke-') as root:
        prepared=Stage1Session(save_root=root, runtime_clock=lambda:0)
        prepared.world=world
        prepared.career_id=prepared.save_store.new_career_id()
        prepared.save_manual()
        career=prepared.career_id
        prepared.close()

        class Smoke(AirlineTycoonApp):
            def __init__(self):
                super().__init__(session_factory=lambda:Stage1Session(save_root=root))
                self.index=0
                self.phase='begin'
                self.results=[]
                self.failure=None
                self.longest=0
            def click(self, caption):
                next(w for w in self.screens.get_screen('game').walk()
                     if isinstance(w,Button) and w.text==caption).dispatch('on_release')
            def tick(self,dt):
                before=time.perf_counter()
                try:
                    super().tick(dt)
                finally:
                    self.longest=max(self.longest,time.perf_counter()-before)
            def _error(self,title,error):
                self.failure=f'{title}: {error}'
                self.stop()
            def on_start(self):
                super().on_start()
                Clock.schedule_interval(self.step,.1)
            def step(self,dt):
                try:
                    if self.phase=='begin':
                        self.session.load_saved(career)
                        self._enter_game()
                        assert self.session.validate()
                        self.speed=PLAYER_SPEEDS[self.index]
                        self.start=parse_canonical_utc(self.session.world['simulation']['time_utc'])
                        self.history=len(self.session.world['world_state']['event_history'])
                        self.longest=0
                        self.click(self.speed.name)
                        self.sample_start=self.session.runtime.last_ns
                        self.phase='measure'
                    elif self.phase=='measure':
                        if active_monotonic_ns()-self.sample_start < args.seconds*NANOSECOND:
                            return
                        self.click('Pause')
                        runtime=self.session.runtime
                        elapsed=(runtime.last_ns-self.sample_start)/NANOSECOND
                        simulated=(parse_canonical_utc(self.session.world['simulation']['time_utc'])-self.start).total_seconds()
                        backlog=runtime.credit_ns/NANOSECOND
                        assert self.session.validate()
                        self.results.append(dict(speed=self.speed.name,requested_ratio=self.speed.ratio,
                            active_seconds=elapsed,simulated_seconds=simulated,
                            achieved_ratio=simulated/elapsed,backlog_game_seconds=backlog,
                            backlog_real_seconds=backlog/self.speed.ratio,
                            accounted_ratio=(simulated+backlog)/elapsed,
                            longest_gui_tick_seconds=self.longest,
                            events=len(self.session.world['world_state']['event_history'])-self.history,
                            diagnostic=runtime.diagnostic))
                        print(json.dumps(self.results[-1]),flush=True)
                        self.index+=1
                        self.phase='begin' if self.index<len(PLAYER_SPEEDS) else 'finish'
                    elif self.phase=='finish':
                        # Resume retains Ultra in this open session; explicit Advance replaces pacing.
                        self.resume()
                        assert self.session.runtime.selected_speed.name=='Ultra'
                        self.pause()
                        self._begin_seconds(60)
                        self.phase='save'
                    elif self.phase=='save':
                        if self.session.advancing:
                            return
                        assert self.session.validate()
                        self.save_game()
                        self._dismiss()
                        before=self.session.authoritative_bytes()
                        self.session.load_saved(career)
                        assert self.session.authoritative_bytes()==before
                        assert not self.session.runtime.running
                        assert self.session.runtime.selected_speed.name=='Normal Speed'
                        self._enter_game()
                        print('KIVY SPEED/ADVANCE/SAVE/PAUSED RELOAD PASS',flush=True)
                        self.stop()
                except Exception as error:
                    self.failure=repr(error)
                    self.stop()
        app=Smoke()
        app.run()
        if app.failure:
            raise RuntimeError(app.failure)
        assert len(app.results)==4


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=float,default=8)
    parser.add_argument('--fixture',type=Path)
    run(parser.parse_args())
