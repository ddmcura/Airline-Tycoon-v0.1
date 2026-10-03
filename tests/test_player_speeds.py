"""Player rate, legacy literal-save compatibility and complete-event invariants."""
from copy import deepcopy
from datetime import timedelta
import tempfile
import unittest

from app.session import Stage1Session
from game.simulation.pacing import RuntimeController, NANOSECOND
from game.simulation.speeds import PLAYER_SPEEDS, player_speed
from game.simulation.kernel import configure_clock_ratios, process_events_through
from game.world_state.timestamps import parse_canonical_utc, format_utc
from tests.test_stage1_event_kernel import make_world, schedule
from tests.test_stage1_runtime import Clock, drain


class PlayerSpeedTests(unittest.TestCase):
    def test_ratios_and_day_durations(self):
        self.assertEqual([s.relative_multiplier for s in PLAYER_SPEEDS], [1,7,30,60])
        self.assertEqual([s.ratio for s in PLAYER_SPEEDS], [30,210,900,1800])
        for speed, seconds in zip(PLAYER_SPEEDS, [2880,86400/210,96,48]):
            self.assertEqual(speed.real_seconds_per_game_day, seconds)

    def test_every_speed_matches_explicit_events_without_loss(self):
        for speed in PLAYER_SPEEDS:
            with self.subTest(speed=speed.name):
                world = make_world()
                start = parse_canonical_utc(world['simulation']['time_utc'])
                for seconds in (0,1,20):
                    schedule(world, format_utc(start+timedelta(seconds=seconds)))
                expected = deepcopy(world)
                configure_clock_ratios(expected, normal=speed.ratio)
                process_events_through(expected, format_utc(start+timedelta(seconds=speed.ratio)))
                clock = Clock()
                runtime = RuntimeController(world, clock=clock)
                runtime.resume(speed.name)
                clock.advance(NANOSECOND)
                drain(runtime)
                runtime.pause()
                self.assertEqual(world, expected)
                self.assertEqual(runtime.credit_ns, 0)

    def test_switch_running_samples_old_rate_and_retains_work(self):
        world = make_world()
        start = parse_canonical_utc(world['simulation']['time_utc'])
        schedule(world, format_utc(start))
        clock = Clock()
        runtime = RuntimeController(world, clock=clock)
        runtime.resume()
        clock.advance(NANOSECOND)
        runtime.pump()
        work = runtime.work
        clock.advance(NANOSECOND)
        runtime.resume('Ultra')
        self.assertIs(runtime.work, work)
        clock.advance(NANOSECOND)
        drain(runtime)
        self.assertEqual(world['simulation']['time_utc'],
                         format_utc(start+timedelta(seconds=60+1800)))
        self.assertEqual(runtime.credit_ns, 0)
        runtime.pause()
        clock.advance(100*NANOSECOND)
        runtime.select_speed('Fast')
        self.assertFalse(runtime.running)
        self.assertEqual(runtime.credit_ns, 0)
        runtime.resume()
        clock.advance(NANOSECOND)
        drain(runtime)
        self.assertEqual(world['simulation']['time_utc'],
                         format_utc(start+timedelta(seconds=60+1800+210)))

    def test_legacy_and_current_saves_remain_literal_and_load_paused(self):
        with tempfile.TemporaryDirectory() as root:
            session = Stage1Session(save_root=root, runtime_clock=lambda:0)
            session.new_game('CEO','Speed Air','MNL')
            for ratio in (1,7,30,210,900,1800):
                with self.subTest(saved_ratio=ratio):
                    configure_clock_ratios(session.world, normal=ratio)
                    session.save_manual()
                    session.load_saved(session.career_id)
                    self.assertEqual(session.runtime.ratio, ratio)
                    self.assertFalse(session.runtime.running)
                    self.assertEqual(session.runtime.selected_speed.name,'Normal Speed')
                    session.resume()
                    self.assertEqual(session.runtime.ratio,30)
                    session.pause()
            session.resume('Ultra')
            session.save_manual()
            session.load_saved(session.career_id)
            self.assertFalse(session.runtime.running)
            self.assertEqual(session.runtime.ratio,1800)
            self.assertEqual(session.runtime.credit_ns,0)
            session.resume()
            self.assertEqual(session.runtime.ratio,30)
            report=session.advance_seconds(60)
            self.assertTrue(report.result.succeeded)
            self.assertFalse(session.runtime.running)
            self.assertTrue(session.validate())
            encoded=session.authoritative_bytes()
            for field in (b'selected_speed',b'credit_ns',b'relative_multiplier'):
                self.assertNotIn(field,encoded)

    def test_invalid_speed_is_rejected(self):
        with self.assertRaises(ValueError):
            player_speed('7x')
        runtime=RuntimeController(make_world(),clock=lambda:0)
        before=deepcopy(runtime.world)
        with self.assertRaises(ValueError):
            runtime.select_speed('7x')
        self.assertEqual(before,runtime.world)
