"""Opt-in native Kivy fresh-process Load Game smoke using temporary saves.

python -B -m tests.smoke_runtime_startup
The parent prepares an existing save; only a separate child launches the GUI.
No New Game or unrelated management-screen visits occur in the GUI process.
"""
import argparse
import json
import subprocess
import sys
import tempfile


def prepare(root):
    from app.session import Stage1Session
    from game.scheduling import WeeklyDraft
    session = Stage1Session(save_root=root, runtime_clock=lambda: 0)
    session.new_game('CEO', 'Startup Smoke Air', 'MNL')
    state = session.world['world_state']
    airports = {a['reference_code']: key for key,a in state['airports'].items()}
    draft = WeeklyDraft(session.world, airline_id=session.airline_id,
                        aircraft_id=next(iter(state['aircraft'])))
    draft.add_weekdays(airports['MNL'], airports['DVO'], ('2026-09-07',),
                      '08:00', return_flight=True, fare_minor=11600)
    draft.save_current(session.world)
    session.save_manual()
    return session.career_id


def run_child(root, career):
    assert 'game.booking.checkpoint' not in sys.modules
    from app.gui.app import AirlineTycoonApp
    from app.session import Stage1Session
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.uix.button import Button
    # GUI import alone must not mask the fresh startup condition.
    assert 'game.booking.checkpoint' not in sys.modules

    class LoadSmoke(AirlineTycoonApp):
        def __init__(self):
            self.now = 0
            self.stage = 0
            self.failure = None
            self.result = None
            self.before = None
            super().__init__(session_factory=lambda: Stage1Session(
                save_root=root, runtime_clock=lambda: self.now))
            self.session.new_game = lambda *a, **k: self.forbidden_new()

        def forbidden_new(self):
            raise AssertionError('New Game must never run in the GUI smoke process')

        def _error(self, title, error):
            self.failure = f'{title}: {error}'
            self.stop()

        def on_start(self):
            super().on_start()
            Clock.schedule_interval(self.step, .2)
            Clock.schedule_once(self.timeout, 60)

        def timeout(self, _dt):
            if self.result is None and self.failure is None:
                self.failure = 'smoke timed out'
                self.stop()

        def click(self, root, caption):
            next(w for w in root.walk() if isinstance(w, Button)
                 and w.text == caption).dispatch('on_release')

        def load_from_title(self):
            self.click(self.screens.get_screen('title'), 'Load Game')
            self.click(self._popup.content,
                next(w.text for w in self._popup.content.walk()
                     if isinstance(w, Button) and 'Startup Smoke Air' in w.text))
            self.click(self._popup.content, 'Current manual save')
            assert self.session.career_id == career
            assert self.screens.current == 'game'
            assert self.session.world['simulation']['clock_state'] == 'PAUSED'

        def step(self, _dt):
            try:
                if self.stage == 0:
                    self.load_from_title()
                    self.event = min((e for e in self.session.world['world_state']['pending_events'].values()
                        if e['event_type'] == 'DAILY_BOOKING_CHECKPOINT'), key=lambda e:e['due_at_utc'])
                    self.stage = 1
                elif self.stage == 1:
                    self.click(self.screens.get_screen('game'), 'Normal Speed')
                    self.now += 1000000000
                    self.tick(0)
                    self.click(self.screens.get_screen('game'), 'Pause')
                    assert self.session.runtime.diagnostic is None
                    self.show_advance()
                    self.click(self._popup.content, 'One day')
                    self.stage = 2
                elif self.stage == 2:
                    if self.session.advancing:
                        return
                    state = self.session.world['world_state']
                    assert state['event_history'][self.event['event_id']]['status'] == 'COMPLETED'
                    assert any(c['checkpoint_date'] == self.event['payload']['checkpoint_date']
                               and c['status'] == 'COMPLETED'
                               for c in state['booking_state']['booking_checkpoints'].values())
                    assert self.session.runtime.diagnostic is None
                    assert self.session.validate()
                    self.before = self.session.authoritative_bytes()
                    self.result = {'status':'PASS', 'checkpoint':self.event['payload']['checkpoint_date'],
                        'completed_checkpoints':len(state['booking_state']['booking_checkpoints']),
                        'bookings':len(state['bookings']), 'window':list(Window.size),
                        'time_utc':self.session.world['simulation']['time_utc']}
                    self.save_game()
                    self._dismiss()
                    self.return_to_title()
                    self.stage = 3
                elif self.stage == 3:
                    self.load_from_title()
                    assert self.session.validate()
                    assert self.session.authoritative_bytes() == self.before
                    self.result['save_reload_exact_paused'] = True
                    print(json.dumps(self.result), flush=True)
                    self.stage = 4
                    self.stop()
            except Exception:
                import traceback
                self.failure = traceback.format_exc()
                self.stop()

    app = LoadSmoke()
    app.run()
    if app.failure or app.stage != 4:
        raise RuntimeError(app.failure or 'smoke did not complete')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--load')
    parser.add_argument('--career')
    args = parser.parse_args()
    if args.load:
        run_child(args.load, args.career)
    else:
        with tempfile.TemporaryDirectory(prefix='at-startup-smoke-') as root:
            career = prepare(root)
            subprocess.run([sys.executable, '-B', '-m', 'tests.smoke_runtime_startup',
                            '--load', root, '--career', career], check=True, timeout=120)


if __name__ == '__main__':
    main()
