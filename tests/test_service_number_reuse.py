"""Schema 9 sequential reuse, protected reservations and cold reconstruction."""
from copy import deepcopy
import json
import tempfile
import unittest
from unittest.mock import patch

from tests import test_quarterly_foundation as foundation
encoded = foundation.encoded
from game.utils.quarters import quarter_containing
from game.world_state import validate_world
from game.world_state.quarterly_construction import (
    create_service, create_weekly_plan, append_weekly_plan_revision, retire_service)
from game.world_state.service_numbers import eligible_retired_numbers, protected_number_holders
from game.world_state.persistence import SaveStore, _migrated, SaveError
from game.world_state.quarterly_validation import validate_quarterly
from game.scheduling.service_identity import flight_number, occurrence_identity
from game.scheduling.quarterly_reads import PlanReadRequest, resolve_quarterly_reads


class NumberReuseTests(unittest.TestCase):
    setUpClass = classmethod(foundation.FoundationTests.setUpClass.__func__)
    setUp = foundation.FoundationTests.setUp
    slot = foundation.FoundationTests.slot
    service = foundation.FoundationTests.service
    plan = foundation.FoundationTests.plan

    def numbers(self):
        return eligible_retired_numbers(self.world, self.owner)

    def publish_fixture(self, quarter):
        pid, sid, n, row = self.plan(quarter.quarter_id)
        self.state['weekly_plans'][pid]['revisions']['1']['published_at_utc'] = (
            quarter.start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
            if quarter == quarter_containing(self.world['simulation']['time_utc'])
            else self.world['simulation']['time_utc'])
        return pid, sid, n, row

    def test_new_schema9_and_old_schema8_clean_rejection(self):
        self.assertEqual(self.world['metadata']['save_schema_version'], 9)
        old = deepcopy(self.world); old['metadata']['save_schema_version'] = 8
        before = encoded(old)
        with self.assertRaises(SaveError) as caught: _migrated(old)
        self.assertEqual(caught.exception.code, 'UNSUPPORTED_SCHEMA')
        self.assertEqual(encoded(old), before)

    def test_retired_history_reused_with_distinct_service_identity(self):
        pid, old, n, row = self.plan()
        retire_service(self.world, old)
        new, _ = self.service()
        self.assertNotEqual(old, new)
        self.assertEqual(flight_number(self.state, old), flight_number(self.state, new))
        self.assertNotEqual(occurrence_identity(old,n,'2028-04-03'), occurrence_identity(new,n,'2028-04-03'))
        self.assertTrue(validate_world(self.world).is_valid)

    def test_lowest_multiple_eligible_first_and_no_survivor_renumber(self):
        ids = [self.service()[0] for _ in range(5)]
        retire_service(self.world, ids[3]); retire_service(self.world, ids[1])
        self.assertEqual(self.numbers(), (2,4))
        first, _ = self.service(); second, _ = self.service()
        self.assertEqual([flight_number(self.state,s) for s in (first, second, ids[2])], ['DAB02','DAB04','DAB03'])
        self.assertEqual(self.state['service_numbering'][self.owner]['next_number'], 6)

    def test_no_eligible_uses_monotonic_and_grows_beyond_two_digits(self):
        sid, _ = self.service()
        self.state['service_numbering'][self.owner]['next_number'] = 147
        new, _ = self.service()
        self.assertEqual(flight_number(self.state,new), 'DAB147')
        self.assertEqual(flight_number(self.state,sid), 'DAB01')
        self.assertEqual(self.state['service_numbering'][self.owner]['next_number'],148)

    def test_low_reuse_never_rewinds_or_advances_fresh_cursor(self):
        old, _ = self.service(); retire_service(self.world,old)
        self.state['service_numbering'][self.owner]['next_number'] = 147
        reused, _ = self.service(); fresh, _ = self.service()
        self.assertEqual(flight_number(self.state,reused),'DAB01')
        self.assertEqual(flight_number(self.state,fresh),'DAB147')
        self.assertEqual(self.state['service_numbering'][self.owner]['next_number'],148)

    def test_draft_unbound_reservation_prevents_reuse(self):
        old, _ = self.service(); retire_service(self.world,old)
        first = create_service(self.world,self.owner,flight_number_prefix='DAB')
        second = create_service(self.world,self.owner,flight_number_prefix='DAB')
        self.assertEqual(flight_number(self.state,first),'DAB01')
        self.assertEqual(flight_number(self.state,second),'DAB02')
        self.assertEqual(self.numbers(),())

    def test_plan_removal_does_not_retire_service(self):
        pid, sid, n, row = self.plan()
        append_weekly_plan_revision(self.world,pid,expected_revision=1,slots=[])
        self.assertEqual(self.numbers(),())
        self.assertIsNone(self.state['services'][sid]['retired_at_utc'])
        self.assertEqual(flight_number(self.state,self.service()[0]),'DAB02')

    def test_retired_active_published_holder_still_protects(self):
        q = quarter_containing(self.world['simulation']['time_utc'])
        pid, sid, n, row = self.publish_fixture(q)
        retire_service(self.world,sid)
        self.assertEqual(self.numbers(),())
        self.assertEqual(flight_number(self.state,self.service()[0]),'DAB02')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_retired_future_committed_holder_still_protects(self):
        q = quarter_containing(self.world['simulation']['time_utc']).shift(2)
        pid, sid, n, row = self.publish_fixture(q)
        retire_service(self.world,sid)
        self.assertEqual(self.numbers(),())
        self.assertEqual(flight_number(self.state,self.service()[0]),'DAB02')
        self.assertTrue(validate_world(self.world).is_valid)

    def test_exact_end_boundary_releases_only_retired_holder(self):
        q = quarter_containing(self.world['simulation']['time_utc'])
        pid, sid, n, row = self.publish_fixture(q)
        retire_service(self.world,sid)
        self.world['simulation']['time_utc'] = q.end_exclusive_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        before = encoded(self.world)
        self.assertEqual(self.numbers(),(1,))
        self.assertEqual(encoded(self.world),before)
        self.state['services'][sid]['retired_at_utc'] = None
        self.assertEqual(self.numbers(),())

    def test_retained_unpublished_revisions_alone_do_not_protect_retired(self):
        pid,sid,n,row = self.plan()
        append_weekly_plan_revision(self.world,pid,expected_revision=1,slots=[])
        retire_service(self.world,sid)
        self.assertEqual(self.numbers(),(1,))
        self.assertEqual(self.state['weekly_plans'][pid]['revisions']['1']['slots'],[row])

    def test_duplicate_protected_draft_collision_rejects_and_allocation_unchanged(self):
        first,_=self.service(); second,_=self.service()
        self.state['services'][second]['flight_number_number']=1
        before=encoded(self.world)
        self.assertFalse(validate_world(self.world).is_valid)
        with self.assertRaises(ValueError):self.service()
        self.assertEqual(encoded(self.world),before)

    def test_committed_retired_collision_rejects(self):
        q=quarter_containing(self.world['simulation']['time_utc']).shift()
        pid,old,n,row=self.publish_fixture(q);retire_service(self.world,old)
        new,_=self.service();self.state['services'][new]['flight_number_number']=1
        self.assertFalse(validate_world(self.world).is_valid)

    def test_repeated_historical_holders_produce_one_pool_candidate(self):
        old,_=self.service();retire_service(self.world,old)
        new,_=self.service();retire_service(self.world,new)
        self.assertEqual(self.numbers(),(1,))
        validate_quarterly(self.world)

    def test_failure_before_id_allocation_does_not_consume_pool(self):
        old,_=self.service();retire_service(self.world,old);before=encoded(self.world)
        with patch('game.world_state.quarterly_construction.allocate_id',side_effect=ValueError('allocator failure')):
            with self.assertRaises(ValueError):self.service()
        self.assertEqual(encoded(self.world),before);self.assertEqual(self.numbers(),(1,))

    def test_malformed_cursor_prefix_and_future_retirement_reject_without_consumption(self):
        sid,_=self.service()
        for change in ('cursor','prefix','retirement'):
            w=deepcopy(self.world)
            if change=='cursor':w['world_state']['service_numbering'][self.owner]['next_number']=1
            elif change=='prefix':w['world_state']['service_numbering'][self.owner]['flight_number_prefix']='bad'
            else:w['world_state']['services'][sid]['retired_at_utc']='2030-01-01T00:00:00Z'
            before=encoded(w)
            with self.subTest(change=change),self.assertRaises(ValueError):create_service(w,self.owner,flight_number_prefix='DAB')
            self.assertEqual(encoded(w),before);self.assertFalse(validate_world(w).is_valid)

    def test_cold_reconstruction_and_equivalent_allocation_are_deterministic(self):
        ids=[self.service()[0] for _ in range(4)]
        for sid in (ids[2],ids[0]):retire_service(self.world,sid)
        cold=json.loads(encoded(self.world))
        self.assertEqual(eligible_retired_numbers(cold,self.owner),self.numbers())
        self.assertEqual(protected_number_holders(cold),protected_number_holders(self.world))
        cold['world_state']['services']=dict(reversed(list(cold['world_state']['services'].items())))
        self.assertEqual(create_service(cold,self.owner,flight_number_prefix='DAB'),self.service()[0])
        # Slot allocation is separate; align only the explicit additional test action.
        last=max(self.state['services']);cold['world_state']['services'][last]['next_slot_number']=2
        self.assertEqual(encoded(cold),encoded(self.world))

    def test_reused_history_roundtrip_and_detached_reads(self):
        pid,old,n,row=self.plan();retire_service(self.world,old)
        new,nn=self.service();pid2=create_weekly_plan(self.world,self.owner,'2028-Q3',slots=[self.slot(new,nn)])
        requests=(PlanReadRequest(pid,1),PlanReadRequest(pid2,1))
        before=encoded(self.world)
        expected=resolve_quarterly_reads(self.world,airline_id=self.owner,selections=requests)
        self.assertTrue(expected.succeeded)
        self.assertEqual([p.slots[0].flight_number for p in expected.plans],['DAB01','DAB01'])
        with tempfile.TemporaryDirectory() as root:
            store=SaveStore(root);career=store.new_career_id();store.save(career,'manual',self.world);cold,_=store.load(career)
        self.assertEqual(encoded(cold),before)
        self.assertEqual(resolve_quarterly_reads(cold,airline_id=self.owner,selections=requests),expected)
        with self.assertRaises(TypeError):expected.plans[0].slots[0].facts['fare_offer']['amount_minor']=0
        self.assertEqual(encoded(self.world),before)

    def test_endpoint_change_rejects_before_plan_allocation_or_revision(self):
        pid,sid,n,row=self.plan()
        changed=dict(row,origin_airport_id=self.dest,destination_airport_id=self.origin,
            service_type='DEADHEAD',connection_id=None,capacity=0,fare_offer={'currency':'USD','amount_minor':0})
        from game.world_state.planning_reference import planning_snapshot
        changed['planning_timing']=planning_snapshot(self.state,self.aircraft,self.dest,self.origin)
        before=encoded(self.world)
        for action in (lambda:create_weekly_plan(self.world,self.owner,'2028-Q3',slots=[changed]),
                       lambda:append_weekly_plan_revision(self.world,pid,expected_revision=1,slots=[changed])):
            with self.assertRaisesRegex(ValueError,'endpoint'):action()
            self.assertEqual(encoded(self.world),before)

    def test_endpoint_corruption_rejected_at_global_schema9_gate(self):
        pid,sid,n,row=self.plan();pid2=create_weekly_plan(self.world,self.owner,'2028-Q3',slots=[row])
        self.state['weekly_plans'][pid2]['revisions']['1']['slots'][0]['destination_airport_id']=self.origin
        self.assertFalse(validate_world(self.world).is_valid)

    def test_new_service_reused_number_can_bind_distinct_endpoints(self):
        pid,old,n,row=self.plan();retire_service(self.world,old)
        new,nn=self.service()
        from game.world_state.planning_reference import planning_snapshot
        reverse=self.slot(new,nn,origin_airport_id=self.dest,destination_airport_id=self.origin,
            service_type='DEADHEAD',connection_id=None,capacity=0,fare_offer={'currency':'USD','amount_minor':0},
            planning_timing=planning_snapshot(self.state,self.aircraft,self.dest,self.origin))
        create_weekly_plan(self.world,self.owner,'2028-Q3',slots=[reverse])
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertNotEqual(old,new)
        self.assertEqual(flight_number(self.state,old),flight_number(self.state,new))

    def test_published_dangling_or_cross_owner_reference_fails_closed(self):
        q=quarter_containing(self.world['simulation']['time_utc']).shift()
        pid,sid,n,row=self.publish_fixture(q)
        for owner in (None, 'airline-999999999999'):
            bad=deepcopy(self.world)
            if owner is None:del bad['world_state']['services'][sid]
            else:bad['world_state']['services'][sid]['airline_id']=owner
            before=encoded(bad)
            with self.subTest(owner=owner),self.assertRaises(ValueError):
                create_service(bad,self.owner,flight_number_prefix='DAB')
            self.assertFalse(validate_world(bad).is_valid)
            self.assertEqual(encoded(bad),before)

    def test_schema8_historical_fixture_keeps_lifetime_uniqueness(self):
        old,_=self.service();retire_service(self.world,old);self.service()
        self.assertTrue(validate_world(self.world).is_valid)
        legacy=deepcopy(self.world);legacy['metadata']['save_schema_version']=8
        self.assertFalse(validate_world(legacy).is_valid)

    def test_read_and_reuse_touch_no_operational_supply_events_or_finance(self):
        before={k:encoded(self.world[k]) for k in ('simulation',)}
        legacy={k:deepcopy(v) for k,v in self.state.items() if k not in ('services','service_numbering','weekly_plans')}
        old,_=self.service();retire_service(self.world,old);self.service();self.numbers()
        self.assertEqual(before['simulation'],encoded(self.world['simulation']))
        self.assertEqual(legacy,{k:v for k,v in self.state.items() if k not in ('services','service_numbering','weekly_plans')})
