"""Patch 4 physical planning only; operational publication remains exact."""
from copy import deepcopy
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch
from game.scheduling import WeeklyDraft
from game.scheduling.planning_feasibility import PlanningFeasibility
from game.scheduling.timing import timing_bounds
from game.scheduling.local_time import local_departure
from game.world_state import create_stage1_new_game,validate_world
from game.world_state.timestamps import format_utc,parse_canonical_utc
from app.session import Stage1Session


class RepositionPlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=create_stage1_new_game(scenario_id='stage1-philippines-v1',ceo_display_name='CEO',airline_display_name='Plan',base_airport_reference_code='MNL')
    def setUp(self):
        self.world=deepcopy(self.base);w=self.world['world_state']
        self.owner=w['player']['primary_airline_id'];self.plane=next(iter(w['aircraft']))
        self.ports={r['reference_code']:k for k,r in w['airports'].items()}
        self.draft=WeeklyDraft(self.world,airline_id=self.owner,aircraft_id=self.plane)
    def add(self,origin,destination,day,time):
        return self.draft.add_weekdays(self.ports[origin],self.ports[destination],[day],time,fare_minor=11600)
    def daily(self):
        return self.draft.add_weekdays(self.ports['DVO'],self.ports['MNL'],[f'2026-09-{n:02d}' for n in range(7,14)],'08:00',fare_minor=11600)
    def test_daily_one_way_is_transient_and_feasible(self):
        before=deepcopy(self.world);self.assertEqual(self.daily(),7)
        self.assertEqual(len(self.draft.validate_planning(continuous=True)),85)
        self.assertEqual(self.world,before)
        self.assertTrue(all(r['service_type']=='PASSENGER' for r in self.draft.legs))
        self.assertFalse(self.world['world_state']['dated_flights'])
    def test_multi_day_and_presets_one_way(self):
        for indices in ((7,9,11),(8,10,12),(7,9,11,13)):
            with self.subTest(indices=indices):
                d=WeeklyDraft(self.world,airline_id=self.owner,aircraft_id=self.plane)
                self.assertEqual(d.add_weekdays(self.ports['DVO'],self.ports['MNL'],[f'2026-09-{n:02d}' for n in indices],'08:00'),len(indices))
                d.validate_planning(repeat_until='2026-10-01')
    def test_anchor_uses_actual_location_and_exact_ready(self):
        self.assertEqual(self.draft.earliest(self.ports['DVO'],self.ports['MNL']),'2026-09-01T02:40:00Z')
        self.add('DVO','MNL','2026-09-01','10:40')
        self.assertEqual(self.world,self.base)
        self.assertEqual(self.world['world_state']['aircraft'][self.plane]['current_airport_id'],self.ports['MNL'])
    def test_exact_two_turnaround_boundaries_not_double_counted(self):
        self.add('DVO','MNL','2026-09-07','08:00')
        self.assertEqual(timing_bounds(self.draft.legs[0]['planning_timing'])[1],(1800,6000,0))
        earliest=self.draft.earliest(self.ports['DVO'],self.ports['MNL'],not_before='2026-09-07T00:00:00Z')
        self.assertEqual(earliest,'2026-09-07T04:20:00Z') # 12:20 PH
        before=self.draft.legs
        with self.assertRaisesRegex(ValueError,'REPOSITIONING_INFEASIBLE.*gap'):
            self.add('DVO','MNL','2026-09-07','12:19:59')
        self.assertEqual(self.draft.legs,before)
        self.add('DVO','MNL','2026-09-07','12:20')
    def test_incremental_fill_gap_rejects_only_new_edit(self):
        self.add('DVO','MNL','2026-09-07','08:00');self.add('DVO','MNL','2026-09-08','08:00')
        self.add('MNL','CEB','2026-09-07','15:00')
        self.add('CEB','MNL','2026-09-08','03:00')
        before=self.draft.legs;undo=deepcopy(self.draft._undo_stack)
        with self.assertRaisesRegex(ValueError,'REPOSITIONING_INFEASIBLE'):
            self.draft.reschedule(3,'2026-09-08','05:00')
        self.assertEqual(self.draft.legs,before);self.assertEqual(self.draft._undo_stack,undo)
        self.draft.reschedule(3,'2026-09-08','02:00');self.draft.delete_selection([3])
        self.assertEqual(len(self.draft.legs),3);self.draft.undo();self.assertEqual(len(self.draft.legs),4)
    def test_multi_day_one_bad_gap_is_atomic(self):
        self.add('MNL','CEB','2026-09-09','06:00');before=self.draft.legs
        with self.assertRaisesRegex(ValueError,'REPOSITIONING_INFEASIBLE'):
            self.draft.add_weekdays(self.ports['DVO'],self.ports['MNL'],['2026-09-07','2026-09-09','2026-09-11'],'08:00')
        self.assertEqual(self.draft.legs,before)
    def test_same_day_different_origin_physical_gap(self):
        self.add('DVO','MNL','2026-09-07','08:00')
        self.add('CEB','DVO','2026-09-07','15:00')
        self.assertEqual(len(self.draft.legs),2)
        bad=WeeklyDraft(self.world,airline_id=self.owner,aircraft_id=self.plane)
        bad.add_weekdays(self.ports['DVO'],self.ports['MNL'],['2026-09-07'],'08:00')
        with self.assertRaisesRegex(ValueError,'REPOSITIONING_INFEASIBLE'):
            bad.add_weekdays(self.ports['CEB'],self.ports['DVO'],['2026-09-07'],'11:00')
    def test_cross_week_recurrence_gap_checked(self):
        self.add('DVO','MNL','2026-09-07','08:00')
        self.add('CEB','MNL','2026-09-13','23:00')
        before=self.draft.legs
        # Change Monday to 02:00: Sunday arrival leaves too little for MNL>DVO.
        self.draft.reschedule(0,'2026-09-07','02:00')
        with self.assertRaisesRegex(ValueError,'REPOSITIONING_INFEASIBLE'):
            self.draft.validate_planning(continuous=True)
        self.assertEqual(len(self.draft.legs),len(before))
    def test_repeat_until_and_continuous_queries_deterministic(self):
        self.daily();before=deepcopy(self.draft.__dict__)
        a=self.draft.validate_planning(repeat_until='2026-10-01')
        b=self.draft.validate_planning(repeat_until='2026-10-01')
        self.assertEqual(a,b);self.assertEqual(self.draft.__dict__,before)
        self.assertGreater(len(self.draft.validate_planning(continuous=True)),len(a))
    def test_publication_rejects_without_fake_movement_or_any_effect(self):
        self.daily();before=deepcopy(self.world);legs=self.draft.legs
        with self.assertRaisesRegex(ValueError,'publication requires actual positioning'):
            self.draft.save_current(self.world,continuous=True)
        self.assertEqual(self.world,before);self.assertEqual(self.draft.legs,legs)
        self.assertTrue(validate_world(self.world).is_valid)
    def test_return_uses_same_airport_and_publishes_normally(self):
        self.draft.add_weekdays(self.ports['MNL'],self.ports['DVO'],['2026-09-07'],'08:00',return_flight=True)
        self.assertEqual(self.draft.legs[1]['departure_utc'],'2026-09-07T02:10:00Z')
        self.draft.save_current(self.world);self.assertEqual(len(self.world['world_state']['dated_flights']),2)
    def test_initial_prefix_can_skip_impossible_not_past_phantom(self):
        self.add('MNL','CEB','2026-09-01','06:00')
        self.add('CEB','DVO','2026-09-01','08:30')
        self.add('MNL','DVO','2026-09-01','09:00')
        self.assertEqual(self.draft.earliest(self.ports['DVO'],self.ports['MNL']),'2026-09-01T03:10:00Z')
        self.assertEqual(self.world,self.base)
    def test_earliest_exact_seconds_and_equivalent_manual_intent(self):
        self.add('DVO','MNL','2026-09-07','08:00:01')
        result=self.draft.earliest(self.ports['DVO'],self.ports['MNL'],not_before='2026-09-07T01:00:00Z')
        self.assertEqual(result,'2026-09-07T04:20:01Z')
        a=deepcopy(self.draft);a.add(self.ports['DVO'],self.ports['MNL'],departure_utc=result,fare_minor=11600)
        self.add('DVO','MNL','2026-09-07','12:20:01');self.assertEqual(self.draft.legs,a.legs)
    def test_existing_published_future_obligations_block_insertion(self):
        self.draft.add_weekdays(self.ports['MNL'],self.ports['DVO'],['2026-09-07'],'08:00',return_flight=True)
        self.draft.save_current(self.world)
        d=WeeklyDraft(self.world,airline_id=self.owner,aircraft_id=self.plane)
        with self.assertRaisesRegex(ValueError,'overlap|TURNAROUND'):
            d.add_weekdays(self.ports['CEB'],self.ports['MNL'],['2026-09-07'],'09:00')
        self.assertEqual(d.legs,[])
    def test_real_airborne_projected_arrival_anchors_plan(self):
        from game.simulation import process_events_through
        self.add('MNL','DVO','2026-09-01','09:00');self.draft.save_current(self.world)
        self.assertTrue(process_events_through(self.world,'2026-09-01T01:10:00Z').succeeded)
        d=WeeklyDraft(self.world,airline_id=self.owner,aircraft_id=self.plane)
        self.assertEqual(d.earliest(self.ports['MNL'],self.ports['CEB']),'2026-09-01T05:20:00Z')
    def test_airport_profile_failure_and_range_failure_propagate(self):
        self.add('DVO','MNL','2026-09-07','08:00')
        original=self.draft._snapshot
        for error in ('AIRCRAFT_RANGE_EXCEEDED','no approved scheduling profile for airport'):
            def restricted(origin,destination):
                if (origin,destination)==(self.ports['MNL'],self.ports['DVO']):raise ValueError(error)
                return original(origin,destination)
            with patch.object(self.draft,'_snapshot',side_effect=restricted):
                with self.assertRaisesRegex(ValueError,error):self.add('DVO','MNL','2026-09-08','08:00')
        self.assertEqual(len(self.draft.legs),1)
    def test_real_scalar_range_rejects_reposition_not_supported_flight(self):
        with tempfile.TemporaryDirectory() as root:
            s=Stage1Session(save_root=root);s.new_game('CEO','Range','MNL')
            result=s.purchase(s.preview_purchase('dhc-twin-otter-300-g',self.ports['MNL']))
            aircraft=next(r['aircraft_id'] for r in s.fleet() if r['model_reference']=='dhc-twin-otter-300-g')
            d=s.begin_scheduling(aircraft)
            d.add_weekdays(self.ports['MNL'],self.ports['TWT'],['2026-09-07'],'08:00')
            with self.assertRaisesRegex(ValueError,'AIRCRAFT_RANGE_EXCEEDED'):
                d.add_weekdays(self.ports['BSO'],self.ports['MNL'],['2026-09-08'],'08:00')
    def test_deletion_paste_and_undo_keep_plan_atomic(self):
        self.add('DVO','MNL','2026-09-07','08:00')
        clip=self.draft.copy_selection([0]);self.draft.paste_weekdays(clip,['2026-09-08','2026-09-09'],'08:00')
        self.assertEqual(len(self.draft.legs),3);self.draft.undo();self.assertEqual(len(self.draft.legs),1)
        self.assertEqual(self.world,self.base)

if __name__=='__main__':unittest.main()
