"""Opt-in displayed Kivy scheduling smoke; all careers/artifacts are temporary.

python -B -m tests.smoke_scheduling_performance
Measures event-loop stalls, not a human usability judgement or frame-time SLA.
"""
import argparse
import json
from pathlib import Path
import tempfile
import time

from kivy.clock import Clock
from kivy.core.window import Window

from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from game.world_state import validate_world
from tests.profile_scheduling import definitions, identities


class SchedulingSmoke(AirlineTycoonApp):
    def __init__(self, session, output, **kwargs):
        super().__init__(session_factory=lambda: session, **kwargs)
        self.output = output
        self.steps, self.measurements, self.gaps = [], [], []
        self.failure = None
        self.last_heartbeat = None
        self.waiting = False

    def _error(self, title, error):
        raise RuntimeError(f'{title}: {error}')

    def on_start(self):
        super().on_start()
        self.steps = [('Daily outbound', self.daily), ('Publish Daily', self.publish_daily),
                      ('Daily + Return', self.daily_return), ('Publish recurring', self.publish_pair),
                      ('Start large career', self.large)]
        self.steps += [(f'Daily pair {minute // 60:02d}:{minute % 60:02d}',
                        lambda minute=minute: self.large_pair(minute))
                       for minute in range(30, 30 + 10 * 140, 140)]
        self.steps += [('Publish 560', self.publish_large), ('Navigate timeline', self.navigate),
                       ('Capture settled timeline', self.capture_timeline),
                       ('Begin rolling extension', self.begin_extension),
                       ('Verify extension and save/load', self.verify_extension),
                       ('Advance actual first pair', self.advance_pair),
                       ('Inspect actual operations', self.verify_operations)]
        Clock.schedule_interval(self.heartbeat, .05)
        Clock.schedule_once(self.step, .25)

    def heartbeat(self, _dt):
        now = time.perf_counter()
        if self.last_heartbeat is not None:
            self.gaps.append(now - self.last_heartbeat)
        self.last_heartbeat = now

    def prepare_builder(self, destination, departure, returns):
        self._enter_game()
        self.show_view('Schedule')
        self.start_schedule(identities(self.session.world)[1])
        self.change_schedule_week(1)
        self._builder_origin = identities(self.session.world)[2]['MNL']
        self._builder_destination = identities(self.session.world)[2][destination]
        self._builder_time, self._builder_fare = departure, '116'
        self._builder_return, self._builder_weekdays = returns, set(range(7))

    def daily(self):
        # A repeated outbound-only service needs a legal complementary return
        # chain. Author these unpublished definitions via the public domain API.
        definitions(self.session.world, identities(self.session.world)[1], range(7), only_return=True)
        self.prepare_builder('DVO', '08:00', False)
        assert self.add_builder_flights() == 7
        assert len(self._draft.week_rows('2026-09-07')) == 14

    def _save_schedule(self, repeat, *, continuous=False):
        start = time.perf_counter()
        super()._save_schedule(repeat, continuous=continuous)
        value = {'step': 'Publication domain + GUI command',
                 'seconds': time.perf_counter()-start,
                 'retained_flights': len(self.session.world['world_state']['dated_flights'])}
        self.measurements.append(value)
        print(json.dumps(value), flush=True)

    def publish_daily(self):
        self._save_schedule(None)
        self._dismiss()
        # One-off publication stops at the last outbound's departure. The
        # complementary Sunday return remains a virtual plan until extension.
        assert len(self.session.world['world_state']['dated_flights']) == 13

    def daily_return(self):
        self.prepare_builder('DVO', '14:00', True)
        assert self.add_builder_flights() == 14
        rows = self._draft.week_rows('2026-09-07')
        assert sum(row['draft_index'] is not None for row in rows) == 14
        for index in range(0, 14, 2):
            assert self._draft.legs[index+1]['departure_utc'][11:16] == '08:10'

    def publish_pair(self):
        self._save_schedule(None, continuous=True)
        self._dismiss()
        assert len(self.session.world['world_state']['dated_flights']) == 70

    def large(self):
        self.session.new_game('Smoke CEO', 'Large Schedule Smoke', 'MNL')
        self.prepare_builder('CRK', '00:30', True)

    def large_pair(self, minute):
        self._builder_time = f'{minute // 60:02d}:{minute % 60:02d}'
        assert self.add_builder_flights() == 14

    def publish_large(self):
        assert len(self._draft.legs) == 140
        self._queue_schedule_publication('2026-11-01')

    def navigate(self):
        assert len(self.session.world['world_state']['dated_flights']) == 560
        assert validate_world(self.session.world).is_valid
        self._dismiss()
        self.show_view('Overview')
        self.show_view('Schedule')
        self.start_schedule(identities(self.session.world)[1])
        self.change_schedule_week(1)
        rows = self._draft.week_rows('2026-09-07')
        assert len(rows) == 140 and all(row['published'] for row in rows)
        self.select_schedule_day('2026-09-09')
        self.select_schedule_block(rows[0])  # Published details; remains protected.
        self._dismiss()
        self.content.parent.scroll_y = .1
        self._schedule_scroll_x = .3
        self.refresh(force=True)
        print(json.dumps({'window_size': list(Window.size), 'fullscreen': Window.fullscreen,
                          'published_visible_week_blocks': len(rows)}), flush=True)

    def capture_timeline(self):
        # Run on a later frame: new widgets must finish layout/draw first.
        image = Window.screenshot(name=str(self.output / 'scheduling-native-%04d.png'))
        print(json.dumps({'native_screenshot': image}), flush=True)

    def begin_extension(self):
        self.extension_start = time.perf_counter()
        self.session.begin_advance_to('2026-09-06T16:00:00Z')
        self.waiting = True  # Existing Kivy tick pumps ONE complete event.

    def verify_extension(self):
        world = self.session.world
        assert len(world['world_state']['dated_flights']) == 700
        assert validate_world(world).is_valid
        assert any(event['event_type'] == 'STAGE1_WEEKLY_PUBLICATION'
                   and event['status'] == 'COMPLETED'
                   for event in world['world_state']['event_history'].values())
        before = self.session.authoritative_bytes()
        career = self.session.save_manual()
        self.session.load_saved(career)
        assert self.session.authoritative_bytes() == before
        assert self.session.world['simulation']['clock_state'] == 'PAUSED'
        self.show_view('Schedule')
        self.start_schedule(identities(self.session.world)[1])
        self.refresh(force=True)
        print(json.dumps({'rolling_extension_wall_seconds': time.perf_counter()-self.extension_start,
                          'retained_flights': len(world['world_state']['dated_flights']),
                          'bookings': len(world['world_state']['bookings']), 'validated': True,
                          'save_load_equal': True}), flush=True)

    def advance_pair(self):
        self.session.begin_advance_to('2026-09-06T18:20:00Z')
        self.waiting = True

    def verify_operations(self):
        assert len(self.session.world['world_state']['flight_results']) == 2
        assert validate_world(self.session.world).is_valid
        for view in ('Fleet', 'Flights', 'Finance', 'Schedule'):
            self.show_view(view)
        self.start_schedule(identities(self.session.world)[1])
        career = self.session.save_manual()
        before = self.session.authoritative_bytes()
        self.session.load_saved(career)
        assert self.session.authoritative_bytes() == before
        assert self.session.validate()
        print(json.dumps({'real_completed_results': 2, 'post_operations_save_load_equal': True}), flush=True)

    def step(self, _dt):
        try:
            if self._schedule_publication_pending is not None:
                Clock.schedule_once(self.step, .1)
                return
            if self.waiting:
                if self.session.advancing:
                    Clock.schedule_once(self.step, .1)
                    return
                self.waiting = False
            if not self.steps:
                print(json.dumps({'smoke': 'PASS', 'steps': self.measurements,
                    'heartbeat_max_gap_seconds': max(self.gaps, default=0),
                    'heartbeat_samples': len(self.gaps),
                    'limitation': 'Programmatic native-window smoke; human responsiveness not proven.'}), flush=True)
                self.stop()
                return
            title, call = self.steps.pop(0)
            started = time.perf_counter()
            call()
            value = {'step': title, 'seconds': time.perf_counter()-started}
            self.measurements.append(value)
            print(json.dumps(value), flush=True)
            Clock.schedule_once(self.step, .2)
        except Exception as exc:
            import traceback
            self.failure = traceback.format_exc()
            print(json.dumps({'smoke': 'FAIL', 'error': self.failure}), flush=True)
            self.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='at-scheduling-smoke-') as directory:
        output = args.output or Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        session = Stage1Session(save_root=Path(directory) / 'careers', runtime_clock=lambda: 0)
        session.new_game('Smoke CEO', 'Schedule Smoke', 'MNL')
        app = SchedulingSmoke(session, output)
        app.run()
        if app.failure:
            raise SystemExit(app.failure)
