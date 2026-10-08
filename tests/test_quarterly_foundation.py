"""Quarter/calendar, stable service identity and additive authority regressions."""
from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
import json
import tempfile
import unittest
from unittest.mock import patch

from game.utils.quarters import Quarter, quarter_containing, normal_target_quarter, parse_quarter_id
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.quarterly_construction import (create_service, allocate_service_slot,
    retire_service, create_weekly_plan, append_weekly_plan_revision)
from game.world_state.quarterly_validation import validate_quarterly
from game.scheduling.service_identity import (flight_number, occurrence_identity,
    plan_lifecycle, plan_occurrence_identity)
from game.world_state.planning_reference import planning_snapshot
from game.scheduling.rotation import _connection
from game.world_state.persistence import SaveStore, SaveError, _migrated


def encoded(world):
    return json.dumps(world, sort_keys=True, separators=(',', ':'), allow_nan=False)


class QuarterTests(unittest.TestCase):
    def test_all_months_normal_target(self):
        expected = ('2028-Q2','2028-Q2','2028-Q3','2028-Q3','2028-Q3','2028-Q4',
                    '2028-Q4','2028-Q4','2029-Q1','2029-Q1','2029-Q1','2029-Q2')
        for month, target in enumerate(expected, 1):
            with self.subTest(month=month):
                text = f'2028-{month:02d}-01T00:00:00Z'
                self.assertEqual(quarter_containing(text), Quarter(2028, (month-1)//3+1))
                self.assertEqual(normal_target_quarter(text).quarter_id, target)

    def test_boundaries_leap_and_year_carry(self):
        q = Quarter(2028, 1)
        self.assertEqual(q.start_utc, datetime(2028,1,1,tzinfo=timezone.utc))
        self.assertEqual(q.end_exclusive_utc, datetime(2028,4,1,tzinfo=timezone.utc))
        self.assertEqual(quarter_containing(q.end_exclusive_utc-timedelta(seconds=1)),q)
        self.assertEqual(quarter_containing(q.end_exclusive_utc),q.shift())
        self.assertEqual(Quarter(2028,4).shift(),Quarter(2029,1))
        self.assertEqual(Quarter(2029,1).shift(-1),Quarter(2028,4))
        self.assertEqual(quarter_containing(date(2028,2,29)),q)

    def test_global_utc_not_input_zone(self):
        local = datetime(2028,4,1,0,tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(quarter_containing(local),Quarter(2028,1))
        self.assertEqual(normal_target_quarter(local),Quarter(2028,3))

    def test_invalid_calendar_inputs(self):
        for args in ((True,1),(2028,True),(0,1),(2028,0),(10000,1)):
            with self.subTest(args=args), self.assertRaises(ValueError):Quarter(*args)
        for text in ('2028-Q0','28-Q1','2028-q1','0000-Q1'):
            with self.subTest(text=text), self.assertRaises(ValueError):parse_quarter_id(text)
        for value in (datetime(2028,1,1),datetime(2028,1,1,microsecond=1,tzinfo=timezone.utc),True,'2028-1-1'):
            with self.subTest(value=value), self.assertRaises(ValueError):quarter_containing(value)
        with self.assertRaises(ValueError):Quarter(1,1).shift(-1)
        with self.assertRaises(ValueError):Quarter(2028,1).shift(True)


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='A',airline_display_name='Dabudhi',base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base); self.state = self.world['world_state']
        self.owner = self.state['player']['primary_airline_id']
        self.aircraft = next(iter(self.state['aircraft']))
        self.origin = self.state['aircraft'][self.aircraft]['current_airport_id']
        self.dest = next(k for k,a in self.state['airports'].items() if a['reference_code']=='DVO')
        self.connection = _connection(self.world,self.owner,self.origin,self.dest)

    def slot(self, service, number, **changes):
        row = dict(service_id=service,slot_number=number,weekdays=[0],departure_local_time='08:00:00',
            departure_local_fold=0,origin_airport_id=self.origin,destination_airport_id=self.dest,
            planned_aircraft_id=self.aircraft,connection_id=self.connection,service_type='PASSENGER',
            capacity=self.state['aircraft'][self.aircraft]['configuration']['economy_capacity'],
            fare_offer={'currency':'USD','amount_minor':10000},
            planning_timing=planning_snapshot(self.state,self.aircraft,self.origin,self.dest))
        row.update(changes);return row

    def service(self):
        sid=create_service(self.world,self.owner,flight_number_prefix='DAB')
        return sid,allocate_service_slot(self.world,sid)

    def plan(self, quarter='2028-Q2'):
        sid,n=self.service();row=self.slot(sid,n)
        pid=create_weekly_plan(self.world,self.owner,quarter,slots=[row])
        return pid,sid,n,row

    def test_new_game_empty_schema9_foundation(self):
        self.assertEqual(self.base['metadata']['save_schema_version'],9)
        for key in ('services','service_numbering','weekly_plans'):self.assertEqual(self.base['world_state'][key],{})
        self.assertTrue(validate_world(self.world).is_valid)

    def test_repeating_number_distinct_dates(self):
        pid,sid,n,row=self.plan()
        first=plan_occurrence_identity(self.world,pid,1,sid,n,'2028-04-03')
        second=plan_occurrence_identity(self.world,pid,1,sid,n,'2028-04-10')
        self.assertNotEqual(first,second);self.assertEqual(flight_number(self.state,sid),'DAB01')
        self.assertEqual(first,occurrence_identity(sid,n,'2028-04-03'))
        self.assertEqual(first,plan_occurrence_identity(self.world,pid,1,sid,n,'2028-04-03'))
        self.assertEqual(self.state['dated_flights'],{})

    def test_continuing_service_across_quarters_and_revisions(self):
        pid,sid,n,row=self.plan('2028-Q1')
        earlier=deepcopy(self.state['weekly_plans'][pid])
        q2=create_weekly_plan(self.world,self.owner,'2028-Q2',slots=[dict(row,departure_local_time='08:30:00')])
        append_weekly_plan_revision(self.world,q2,expected_revision=1,slots=[dict(row,departure_local_time='09:00:00')])
        self.assertEqual(self.state['weekly_plans'][pid],earlier)
        self.assertEqual(self.state['weekly_plans'][q2]['revisions']['1']['slots'][0]['departure_local_time'],'08:30:00')
        self.assertEqual(flight_number(self.state,sid),'DAB01')
        self.assertEqual(plan_occurrence_identity(self.world,q2,1,sid,n,'2028-04-03'),plan_occurrence_identity(self.world,q2,2,sid,n,'2028-04-03'))
        self.assertTrue(validate_world(self.world).is_valid)

    def test_same_day_frequencies_and_multiple_weekdays(self):
        sid,n=self.service();other=allocate_service_slot(self.world,sid)
        pid=create_weekly_plan(self.world,self.owner,'2028-Q2',slots=[self.slot(sid,n,weekdays=[0,2]),self.slot(sid,other,departure_local_time='12:00:00')])
        a=plan_occurrence_identity(self.world,pid,1,sid,n,'2028-04-03')
        b=plan_occurrence_identity(self.world,pid,1,sid,other,'2028-04-03')
        self.assertNotEqual(a,b);self.assertEqual(flight_number(self.state,sid),'DAB01')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_retirement_releases_number_and_keeps_versions(self):
        pid,sid,n,row=self.plan();old=deepcopy(self.state['weekly_plans'][pid])
        retire_service(self.world,sid);retire_service(self.world,sid)
        newer,_=self.service()
        self.assertNotEqual(sid,newer);self.assertEqual(flight_number(self.state,newer),'DAB01')
        self.assertEqual(flight_number(self.state,sid),'DAB01');self.assertEqual(self.state['weekly_plans'][pid],old)
        with self.assertRaises(ValueError):allocate_service_slot(self.world,sid)
        with self.assertRaises(ValueError):create_weekly_plan(self.world,self.owner,'2028-Q3',slots=[row])
        self.assertTrue(validate_world(self.world).is_valid)

    def test_numbering_grows_past_two_digits_without_table_scan(self):
        with patch('game.world_state.quarterly_construction.validate_slots',side_effect=AssertionError('not an allocation dependency')):
            for _ in range(101):sid=create_service(self.world,self.owner,flight_number_prefix='DAB')
        self.assertEqual(flight_number(self.state,sid),'DAB101')
        validate_quarterly(self.world)

    def test_rejection_preserves_candidate_and_allocators(self):
        pid,sid,n,row=self.plan();before=encoded(self.world)
        actions=[lambda:create_service(self.world,self.owner,flight_number_prefix='OTHER'),
            lambda:create_weekly_plan(self.world,self.owner,'2028-Q2'),
            lambda:append_weekly_plan_revision(self.world,pid,expected_revision=0,slots=[row]),
            lambda:append_weekly_plan_revision(self.world,pid,expected_revision=1,slots=[row,row]),
            lambda:create_weekly_plan(self.world,self.owner,'2028-Q3',slots=[dict(row,slot_number=999)])]
        for action in actions:
            with self.assertRaises(ValueError):action()
            self.assertEqual(encoded(self.world),before)

    def test_publication_lifecycle_is_derived_no_workflow(self):
        pid,sid,n,row=self.plan('2027-Q1');plan=self.state['weekly_plans'][pid]
        self.assertEqual(plan_lifecycle(plan,'2027-01-01T00:00:00Z'),'PLANNING')
        plan['revisions']['1']['published_at_utc']=self.world['simulation']['time_utc']
        for stamp,expected in [('2026-12-31T23:59:59Z','PUBLISHED'),('2027-01-01T00:00:00Z','ACTIVE'),('2027-04-01T00:00:00Z','HISTORICAL')]:
            self.assertEqual(plan_lifecycle(plan,stamp),expected)
        with self.assertRaises(ValueError):append_weekly_plan_revision(self.world,pid,expected_revision=1,slots=[row])
        self.assertTrue(validate_world(self.world).is_valid)

    def test_publication_future_or_noncurrent_rejects(self):
        pid,sid,n,row=self.plan();plan=self.state['weekly_plans'][pid]
        plan['revisions']['1']['published_at_utc']='2029-01-01T00:00:00Z'
        self.assertFalse(validate_world(self.world).is_valid)
        plan['revisions']['1']['published_at_utc']=None
        append_weekly_plan_revision(self.world,pid,expected_revision=1,slots=[row])
        plan['revisions']['1']['published_at_utc']=self.world['simulation']['time_utc']
        self.assertFalse(validate_world(self.world).is_valid)

    def test_authority_corruption_rejects(self):
        pid,sid,n,row=self.plan()
        mutations=[lambda w:w['services'][sid].update(flight_number_number=True),
            lambda w:w['service_numbering'][self.owner].update(next_number=1),
            lambda w:w['services'][sid].update(next_slot_number=1),
            lambda w:w['weekly_plans'][pid].update(quarter_id='2028-Q5'),
            lambda w:w['weekly_plans'][pid]['revisions']['1']['slots'][0].update(weekdays=[0,0]),
            lambda w:w['weekly_plans'][pid]['revisions']['1']['slots'][0].update(capacity=1),
            lambda w:w['weekly_plans'][pid].update(extra=True)]
        for mutate in mutations:
            candidate=deepcopy(self.world);mutate(candidate['world_state'])
            with self.subTest(mutate=mutate):self.assertFalse(validate_world(candidate).is_valid)

    def test_foreign_number_and_plan_uniqueness(self):
        pid,sid,n,row=self.plan();other,_=self.service()
        self.state['services'][other]['flight_number_number']=1
        self.assertFalse(validate_world(self.world).is_valid)
        self.state['services'][other]['flight_number_number']=2
        from game.world_state.ids import allocate_id
        duplicate=deepcopy(self.state['weekly_plans'][pid]);newid=allocate_id(self.world,'weekly_plan')
        duplicate['weekly_plan_id']=newid;self.state['weekly_plans'][newid]=duplicate
        self.assertFalse(validate_world(self.world).is_valid)

    def test_wrong_date_or_utc_quarter_rejects(self):
        pid,sid,n,row=self.plan()
        for day in ('2028-04-04','2028-07-03'):
            with self.assertRaises(ValueError):plan_occurrence_identity(self.world,pid,1,sid,n,day)
        with self.assertRaises(ValueError):occurrence_identity(sid,True,'2028-04-03')
        with self.assertRaises(ValueError):occurrence_identity(sid,n,'2028-4-3')
        # Airport-local April 1 00:00 is still UTC Q1, not Q2.
        pid2=create_weekly_plan(self.world,self.owner,'2028-Q1',slots=[dict(row,weekdays=[5],departure_local_time='00:00:00')])
        plan_occurrence_identity(self.world,pid2,1,sid,n,'2028-04-01')

    def test_exact_serialization_save_roundtrip_and_detachment(self):
        self.plan();expected=encoded(self.world)
        with tempfile.TemporaryDirectory() as root:
            store=SaveStore(root);career=store.new_career_id();store.save(career,'manual',self.world)
            loaded,_=store.load(career)
            self.assertEqual(encoded(loaded),expected)
            loaded['world_state']['services'].clear();self.assertEqual(encoded(self.world),expected)
        self.assertEqual(encoded(json.loads(expected)),expected)

    def test_equivalent_actions_allocate_identical_authority(self):
        left=deepcopy(self.world);right=deepcopy(self.world)
        for w in (left,right):
            sid=create_service(w,self.owner,flight_number_prefix='DAB');n=allocate_service_slot(w,sid)
            create_weekly_plan(w,self.owner,'2028-Q2',slots=[self.slot(sid,n)])
        self.assertEqual(encoded(left),encoded(right))

    def test_older_save_rejected_not_reinterpreted(self):
        old=deepcopy(self.world);old['metadata']['save_schema_version']=7;before=encoded(old)
        with self.assertRaises(SaveError) as caught:_migrated(old)
        self.assertEqual(caught.exception.code,'UNSUPPORTED_SCHEMA');self.assertEqual(encoded(old),before)

    def test_dormant_foundation_preserves_legacy_operations_and_booking(self):
        self.plan()
        from game.scheduling.weekly import WeeklyDraft
        from game.simulation import process_events_through
        def legacy_projection(w):
            result=deepcopy(w)
            for name in ('services','service_numbering','weekly_plans'):
                result['world_state'].pop(name)
            for name in ('service','weekly_plan'):
                result['deterministic_state']['id_allocator']['next_by_type'].pop(name)
            result['metadata']['save_schema_version']=7
            return result
        old=legacy_projection(self.world)
        for w in (self.world,old):
            draft=WeeklyDraft(w,airline_id=self.owner,aircraft_id=self.aircraft)
            draft.add(self.origin,self.dest,departure_utc='2026-09-07T00:00:00Z',fare_minor=10000)
            draft.add(self.dest,self.origin,departure_utc='2026-09-07T04:00:00Z',fare_minor=10000)
            self.assertTrue(draft.save(w).succeeded)
            self.assertTrue(process_events_through(w,'2026-09-07T07:00:00Z').succeeded)
        self.assertEqual(legacy_projection(self.world),old)
        self.assertEqual(len(self.state['services']),1)
        self.assertTrue(validate_world(self.world).is_valid)
