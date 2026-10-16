"""Measurement guards; no engine optimization or alternate simulation oracle."""
from pathlib import Path
from collections import Counter
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch

from tests import benchmark_quarterly_catchup as benchmark


class CatchupBenchmarkTests(unittest.TestCase):
    def test_artifacts_cannot_use_repository_or_player_saves(self):
        repo = Path(__file__).resolve().parents[1]
        for root in (repo, repo/'Saves', repo/'Saves'/'test', repo/'tests'):
            with self.subTest(root=root), self.assertRaises(ValueError):
                benchmark.safe_root(root)
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(benchmark.safe_root(root), Path(root).resolve())

    def test_session_request_cannot_increase_safety_limits(self):
        with patch.object(benchmark, 'begin_resolution', return_value='request') as begin:
            result = benchmark.constrained_resolution({}, 'target', shared=True,
                        max_generated_events=10_000, max_events=100_000)
        self.assertEqual(result, 'request')
        self.assertEqual(begin.call_args.kwargs, dict(shared=True,
                        max_generated_events=100, max_events=10_000))

    def test_fixture_reconstruction_is_exact_and_paid(self):
        with tempfile.TemporaryDirectory() as root:
            first, _ = benchmark.existing.build(1, Path(root), 0,
                            source_only=True, start_time=benchmark.START)
            second, _ = benchmark.existing.build(1, Path(root), 0,
                            source_only=True, start_time=benchmark.START)
        self.assertEqual(benchmark.existing.digest(first), benchmark.existing.digest(second))
        state = first['world_state']
        self.assertEqual(len(state['aircraft']), 1)
        self.assertEqual(len(state['services']), 4)
        self.assertEqual(len(state['connections']), 10)
        self.assertEqual(Counter(t['source_type'] for t in state['transactions'].values()),
                         {'ROUTE_ESTABLISHMENT': 5})
        plan = next(iter(state['weekly_plans'].values()))['revisions']['1']
        self.assertEqual(plan['published_at_utc'], benchmark.START)
        self.assertTrue(all(s['weekdays'] == list(range(7)) for s in plan['slots']))
        benchmark.existing.valid(first)

    def test_budget_stop_preserves_prefix_without_retry(self):
        class Session:
            advancing = False
            requests = 0
            ticks = 0
            world = dict(simulation=dict(time_utc=benchmark.START),
                         world_state=dict(event_history={}, pending_events={}))
            def begin_advance_to(self, target):
                self.requests += 1
                self.advancing = True
            def advance_tick(self):
                self.ticks += 1
            def cancel_advance(self):
                self.advancing = False
        session = Session()
        result = benchmark.measure(session, 'target', 0)
        self.assertEqual(result['status'], 'MEASUREMENT_BUDGET')
        self.assertEqual((session.requests, session.ticks), (1, 0))
        self.assertFalse(session.advancing)
        self.assertEqual(result['events'], 0)
        self.assertEqual(result['retries'], 0)

    def test_real_completed_prefix_validation_and_save_load(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        world = QuarterlyBackendTests.fixture()[0]
        with tempfile.TemporaryDirectory() as root:
            session = benchmark.existing.session_for(world, root)
            self.addCleanup(session.close)
            target = '2027-01-02T08:00:00Z'
            result = benchmark.measure(session, target, None)
            self.assertEqual(result['status'], 'COMPLETED', result)
            self.assertEqual(result['reached'], target)
            checks = benchmark.correctness(session.world)
            self.assertGreater(checks['carried_passengers'], 0)
            self.assertGreater(checks['transactions']['FLIGHT_FULFILMENT'], 0)
            before = benchmark.existing.digest(session.world)
            session.save_manual()
            session.load_saved(session.career_id)
            self.assertEqual(benchmark.existing.digest(session.world), before)
            self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')

    def test_incomplete_warmup_never_becomes_operating_timing(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        world = QuarterlyBackendTests.fixture()[0]
        setup = dict(fleet=1, setup_s=0, audit=benchmark.existing.audit(world))
        with tempfile.TemporaryDirectory() as root, patch.object(
                benchmark.existing, 'build', return_value=(world, setup)), patch.object(
                benchmark, 'OPERATING_START', '2027-01-02T08:00:00Z'), patch('builtins.print'):
            result = benchmark.run(Path(root), 1, None, setup_budget=0)
            self.assertEqual(result['status'], 'NO_OPERATING_FIXTURE')
            self.assertFalse((Path(root)/'operating-source-1.json').exists())
            self.assertFalse((Path(root)/'quiet-1-0.json').exists())
            self.assertTrue(result['checkpoint']['save_load_exact_paused'])

    def test_operating_timing_starts_after_exact_warmup(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        world = QuarterlyBackendTests.fixture()[0]
        setup = dict(fleet=1, setup_s=0, audit=benchmark.existing.audit(world))
        start = '2027-01-02T08:00:00Z'
        with tempfile.TemporaryDirectory() as root, patch.object(
                benchmark.existing, 'build', return_value=(world, setup)), patch.object(
                benchmark, 'OPERATING_START', start), patch('builtins.print'):
            result = benchmark.run(Path(root), 1, 0, setup_budget=None)
            self.assertEqual(result['source_audit']['time'], start)
            self.assertGreater(result['source_audit']['counts']['bookings'], 0)
            self.assertGreater(result['source_audit']['counts']['flight_results'], 0)
            self.assertEqual(result['days'], 0)
            self.assertEqual(result['events'], 0)
            self.assertEqual(result['target'], '2027-04-02T08:00:00Z')
            self.assertTrue(result['checkpoint']['save_load_exact_paused'])

    def test_bounded_requests_sum_and_match_uninterrupted_world(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        world = QuarterlyBackendTests.fixture()[0]
        setup = dict(fleet=1, setup_s=0, audit=benchmark.existing.audit(world))
        start = '2027-01-02T00:00:00Z'
        end = '2027-01-02T07:00:00Z'
        def small_test_duration(*, days):
            return timedelta(hours=7 if days == 90 else 2)
        with tempfile.TemporaryDirectory() as root:
            with patch.object(benchmark.existing, 'build', return_value=(world, setup)), \
                    patch.object(benchmark, 'OPERATING_START', start), \
                    patch.object(benchmark, 'timedelta', small_test_duration), \
                    patch('builtins.print'):
                result = benchmark.run(Path(root), 1, None, setup_budget=None)
            self.assertEqual(result['status'], 'COMPLETED')
            self.assertGreater(result['requests'], 1)
            self.assertEqual(result['elapsed_s'], sum(r['elapsed_s'] for r in result['advancement_requests']))
            self.assertTrue(all(r['current_utc_fully_resolved'] for r in result['advancement_requests']))
            self.assertEqual(result['retries'], 0)
            control = benchmark.existing.session_for(world, root)
            try:
                benchmark.measure(control, start, None)
                self.assertEqual(benchmark.measure(control, end, None)['status'], 'COMPLETED')
                self.assertEqual(benchmark.existing.digest(control.world), result['audit']['hash'])
            finally:
                control.close()

    def test_real_quarter_boundary_publishes_before_equal_time_booking(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        # Explicit unpublished Q2 plan awaits genuine March 1 publication.
        world = QuarterlyBackendTests.fixture(start='2027-02-28T23:59:59Z',
                    quarter='2027-Q2', published=False)[0]
        with tempfile.TemporaryDirectory() as root:
            session = benchmark.existing.session_for(world, root)
            try:
                result = benchmark.measure(session, '2027-03-01T00:00:00Z', None)
                self.assertEqual(result['status'], 'COMPLETED')
                events = list(session.world['world_state']['event_history'].values())
                types = [e['event_type'] for e in events]
                self.assertLess(types.index('QUARTERLY_PUBLICATION'), types.index('DAILY_BOOKING_CHECKPOINT'))
                self.assertIn('2027-Q2', benchmark.existing.audit(session.world)['published'])
                self.assertEqual(len(result['publication_boundaries']), 1)
                benchmark.correctness(session.world)
            finally:
                session.close()


if __name__ == '__main__':
    unittest.main()
