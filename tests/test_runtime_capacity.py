"""Stage 3F harness accounting/routing guards, no machine-speed assertions."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tests.certify_runtime_capacity import ServiceClock, measure, audit, running_metrics, fixture, equivalence
from tests.flight_fixtures import flight_world
from tests.resolution_oracle import world_digest
from game.simulation.speeds import PLAYER_SPEEDS


class CapacityHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world=flight_world(1)

    def test_setup_and_diagnostic_time_do_not_earn_credit(self):
        c=ServiceClock()
        with patch('time.perf_counter_ns', side_effect=[100,130,160]):
            c.begin();self.assertEqual(c(),30);c.finish()
        self.assertEqual(c(),60)
        c.idle(200)
        self.assertEqual(c(),260)

    def test_finite_input_cap_includes_engine_time_exactly(self):
        c=ServiceClock();c.limit=50
        with patch('time.perf_counter_ns', side_effect=[100,180]):
            c.begin();c.finish()
        self.assertEqual(c(),50)
        c.idle(200);self.assertEqual(c(),50)

    def test_actual_production_routing_and_exact_credit(self):
        before=world_digest(self.world)
        result=measure(self.world,seconds=61,mode='finite',budget=20)
        self.assertTrue(result['complete'])
        self.assertEqual(result['resolved_game_seconds'],61)
        self.assertLess(result['ending_backlog_seconds'],1)
        self.assertGreater(result['units'].get('shared',0),0)
        self.assertEqual(before,world_digest(self.world))
        self.assertGreater(result['event_count'],0)
        self.assertEqual(result['requested_game_seconds'],61)
        self.assertEqual(result['initial_credit_ns']+result['measured_accrued_credit_ns'],int(result['resolved_game_seconds']*1e9)+int(result['ending_backlog_seconds']*1e9))
        self.assertGreater(result['units']['detached_commits'],0)

    def test_cross_speed_complete_world_equivalence(self):
        results=[measure(self.world,speed=s.name,seconds=61,mode='finite',budget=20) for s in PLAYER_SPEEDS]
        self.assertTrue(all(r['complete'] for r in results))
        self.assertEqual(len({r['world_hash'] for r in results}),1)
        self.assertEqual(len({tuple((x['events'],x['commits']) for x in r['callbacks']) for r in results}),1)
        self.assertEqual([r['ratio'] for r in results],[30,210,900,1800])

    def test_cross_speed_reference_uses_independent_strict_kernel(self):
        result=equivalence(self.world,61,20)
        self.assertEqual(len(result['speeds']),4)
        self.assertGreater(len(result['event_vector']),0)
        self.assertEqual({r['hash'] for r in result['speeds']},{result['hash']})

    def test_instrumentation_preserves_certification_identity_and_routing(self):
        quiet=measure(self.world,seconds=61,mode='finite',budget=20)
        profiled=measure(self.world,seconds=61,mode='finite',budget=20,instrument=True)
        self.assertTrue(profiled['complete'])
        self.assertEqual(quiet['world_hash'],profiled['world_hash'])
        self.assertEqual(quiet['units'],profiled['units'])
        self.assertGreater(profiled['profile_calls']['transition_capture_subphase'],0)
        verified=measure(self.world,seconds=61,mode='finite',budget=20,instrument=True,save_reload=True)
        self.assertEqual(profiled['profile_calls'],verified['profile_calls'])

    def test_budgeted_partial_result_is_not_a_pass_and_retains_credit(self):
        r=measure(self.world,seconds=86400,mode='finite',budget=.0001)
        self.assertFalse(r['complete'])
        self.assertGreater(r['ending_backlog_seconds'],0)
        self.assertAlmostEqual(r['earned_game_seconds'],86400)
        self.assertGreater(r['full_day_service_upper_bound'],0)

    def test_actual_strict_booking_fence_is_not_bypassed(self):
        r=measure(self.world,seconds=86400,mode='finite',budget=30)
        self.assertTrue(r['complete'])
        self.assertIn('DAILY_BOOKING_CHECKPOINT',r['event_types'])
        self.assertTrue(any(f['event_type']=='DAILY_BOOKING_CHECKPOINT' and f['fence'] for f in r['fences']))

    def test_paused_exact_save_reload_resume_and_autosave_policy(self):
        r=measure(self.world,seconds=61,mode='finite',budget=20,save_reload=True)
        self.assertTrue(r['save_reload_passed'])
        self.assertTrue(r['persistence_check']['exact_save_reload'])
        self.assertTrue(r['persistence_check']['autosave_first'])
        self.assertFalse(r['persistence_check']['autosave_second'])
        self.assertTrue(all(call['phase']=='verification' for call in r['autosaves']))

    def test_live_input_accounted_separately_from_engine_and_drain(self):
        r=measure(self.world,seconds=360,mode='live',speed='Ultra',budget=20)
        self.assertTrue(r['complete'])
        self.assertGreaterEqual(r['pacing_input_seconds'],.2)
        self.assertGreaterEqual(r['engine_wall_seconds'],0)
        self.assertEqual(r['initial_credit_ns'],0)
        self.assertEqual(r['measured_accrued_credit_ns'],r['resolved_game_seconds']*1000000000+round(r['ending_backlog_seconds']*1000000000))
        self.assertIn('backlog_ns',r['pacing_window_end'])

    def test_explicit_advance_uses_facade_and_matches_finite_authority(self):
        advanced=measure(self.world,seconds=61,mode='advance',budget=20)
        finite=measure(self.world,seconds=61,mode='finite',budget=20)
        self.assertTrue(advanced['complete'])
        self.assertEqual(advanced['world_hash'],finite['world_hash'])
        self.assertIsNone(advanced['earned_game_seconds'])
        self.assertIsNone(advanced['earned_target_utc'])
        self.assertTrue(all(row['earned_game_seconds'] is None and row['target_utc']==advanced['requested_target_utc'] for row in advanced['callbacks']))
        self.assertGreater(advanced['units']['detached_commits'],0)

    def test_pause_drain_does_not_conceal_positive_running_slope(self):
        rows=[dict(state=state,pacing_input_seconds=t,backlog_ns=credit*1000000000,resolved_game_seconds=100)
            for state,t,credit in [('RUNNING',1,100),('RUNNING',2,200),('PLAYER_DRAIN',2,0)]]
        result=running_metrics(rows)
        self.assertEqual(result['slope'],100)
        self.assertAlmostEqual(result['service_ratio'],1/3)
        self.assertEqual(result['end'],rows[1])

    def test_fixture_has_real_bookings_cycles_and_rolling_publication(self):
        w=fixture(1);data=audit(w)
        self.assertEqual(data['aircraft'],1)
        self.assertEqual(data['flights_per_next_24h'],4)
        self.assertGreater(data['collection_sizes']['bookings'],0)
        self.assertGreater(data['collection_sizes']['flight_results'],0)
        self.assertIn('STAGE1_WEEKLY_PUBLICATION',data['next_events'])
        self.assertEqual(data['recurrence'],{'ROLLING_FOUR_WEEKS_V1':4})

    def test_audit_counts_complete_authority(self):
        r=audit(self.world)
        self.assertEqual(r['aircraft'],1)
        self.assertEqual(r['collection_sizes']['bookings'],len(self.world['world_state']['bookings']))
        self.assertEqual(r['hash'],world_digest(self.world))

    def test_invalid_horizon_is_rejected(self):
        for value in (0,-1,True,1.5):
            with self.assertRaises(ValueError): measure(self.world,seconds=value,mode='finite')

if __name__=='__main__': unittest.main()
