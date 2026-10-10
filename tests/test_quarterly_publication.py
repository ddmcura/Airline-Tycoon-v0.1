"""Shared dormant publication, exact rejection/retry and independent witnesses."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.scheduling import quarterly_commands as commands
from game.scheduling.quarterly_publication import PublishQuarterlyPlan
from game.scheduling.quarterly_indexes import QuarterlyDependencyIndex
from game.scheduling.quarterly_occurrences import (
    QuarterlyOccurrenceReference, OccurrenceReadRequest, resolve_quarterly_occurrences,
)
from game.world_state import validate_world
from game.world_state.quarterly_construction import (
    create_weekly_plan, append_weekly_plan_revision, retire_service,
)
from game.world_state.timestamps import format_utc
from game.utils.quarters import normal_target_quarter
from tests import test_quarterly_foundation as foundation
from tests import test_quarterly_readiness as readiness


def operational(world):
    value = deepcopy(world)
    for key in ('services','service_numbering','weekly_plans'):
        value['world_state'].pop(key)
    for key in ('service','weekly_plan'):
        value['deterministic_state']['id_allocator']['next_by_type'].pop(key)
    return foundation.encoded(value)


class QuarterlyPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.FoundationTests.setUpClass.__func__(cls)

    def setUp(self):
        self.owner = self.base['world_state']['player']['primary_airline_id']
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.world, self.pid, self.f = self.at('2027-01-15T00:00:00Z', '2027-Q2')
        self.closed_pattern(self.world, self.pid)

    at = readiness.PublicationReadinessTests.at
    closed_pattern = readiness.PublicationReadinessTests.closed_pattern

    def session(self, world=None):
        session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        session.world = deepcopy(self.world if world is None else world)
        session.career_id = session.save_store.new_career_id()
        session.save_manual(); session.load_saved(session.career_id)
        return session

    def request(self, *, mode='MANUAL', quarter='2027-Q2', pid=None, revision=1, absent=False):
        return PublishQuarterlyPlan(mode, quarter, None if absent else self.pid if pid is None else pid,
                                    0 if absent else revision)

    def prepare(self, session, request=None):
        before = foundation.encoded(session.world)
        result = session.prepare_quarterly_command(self.request() if request is None else request)
        self.assertEqual(foundation.encoded(session.world), before)
        self.assertTrue(result.succeeded, result.issues)
        return result.prepared

    def apply(self, session, request=None):
        prepared = self.prepare(session, request)
        before = operational(session.world)
        result = session.apply_quarterly_command(prepared)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(operational(session.world), before)
        return result

    def fixture_publish(self, world, pid, stamp=None):
        state = world['world_state']; p = state['weekly_plans'][pid]
        p['revisions'][str(p['current_revision'])]['published_at_utc'] = (
            world['simulation']['time_utc'] if stamp is None else stamp)
        result = validate_world(world); self.assertTrue(result.is_valid, result.errors[:2])

    def test_manual_early_commit_retains_dates_ids_revisions_and_advances(self):
        session = self.session(); state = session.world['world_state']
        plan = deepcopy(state['weekly_plans'][self.pid]); ids = deepcopy(session.world['deterministic_state'])
        result = self.apply(session)
        self.assertEqual(result.planning_quarter_id, '2027-Q3')
        self.assertEqual(result.revision, 1)
        self.assertEqual(result.read.plans[0].quarter_id, '2027-Q2')
        self.assertEqual(result.read.plans[0].published_at_utc, '2027-01-15T00:00:00Z')
        self.assertEqual(commands._plain(result.read.plans[0].slots[0].facts), plan['revisions']['1']['slots'][0])
        self.assertEqual(session.world['deterministic_state'], ids)
        rejected = session.prepare_quarterly_command(commands.ReviseQuarterlyFare(self.pid,1,
            result.read.plans[0].slots[0].service_id,1,{'currency':'USD','amount_minor':12000}))
        self.assertEqual(rejected.issues[0].code, 'PUBLISHED_PLAN')

    def test_manual_recommit_and_arbitrary_future_reject(self):
        session = self.session(); self.apply(session)
        self.assertEqual(session.prepare_quarterly_command(self.request()).issues[0].code, 'PUBLISHED_PLAN')
        request = PublishQuarterlyPlan('MANUAL','2028-Q1',None,0)
        self.assertEqual(session.prepare_quarterly_command(request).issues[0].code, 'CLOSED_TARGET')

    def test_automatic_exact_seconds_and_leap_boundary(self):
        boundary = datetime(2028,3,1,tzinfo=timezone.utc)
        for seconds in (-1,0,1):
            world,pid,_ = self.at(format_utc(boundary+timedelta(seconds=seconds)), '2028-Q2')
            self.closed_pattern(world,pid)
            session = self.session(world)
            request = self.request(mode='AUTOMATIC',quarter='2028-Q2',pid=pid)
            if seconds:
                self.assertEqual(session.prepare_quarterly_command(request).issues[0].code, 'CLOSED_TARGET')
            else:
                self.assertEqual(self.apply(session,request).read.plans[0].published_at_utc, '2028-03-01T00:00:00Z')

    def test_month_three_manual_initial_target_after_next(self):
        world,pid,_ = self.at('2027-03-01T00:00:00Z','2027-Q3'); self.closed_pattern(world,pid)
        result = self.apply(self.session(world),self.request(quarter='2027-Q3',pid=pid))
        self.assertEqual(result.planning_quarter_id,'2027-Q4')
        self.assertEqual(result.read.plans[0].quarter_id,'2027-Q3')

    def test_auto_after_manual_skip_changes_no_epoch_world_or_unsaved_flags(self):
        world,pid,_ = self.at('2027-03-01T00:00:00Z','2027-Q2'); self.closed_pattern(world,pid)
        self.fixture_publish(world,pid,'2027-01-15T00:00:00Z')
        session = self.session(world)
        prepared = self.prepare(session,self.request(mode='AUTOMATIC',pid=pid))
        index = session._quarterly_indexes.current; before = foundation.encoded(session.world)
        root = session.world['world_state']; dirty = session.unsaved_progress
        result = session.apply_quarterly_command(prepared)
        self.assertTrue(result.succeeded,result.issues); self.assertTrue(result.skipped)
        self.assertEqual(result.read.plans[0].published_at_utc,'2027-01-15T00:00:00Z')
        self.assertEqual(result.planning_quarter_id,'2027-Q3')
        self.assertIs(session._quarterly_indexes.current,index)
        self.assertIs(session.world['world_state'],root)
        self.assertEqual(foundation.encoded(session.world),before)
        self.assertEqual(session.unsaved_progress,dirty)

    def test_skip_does_not_regress_multiple_early_commitments(self):
        world,pid,_ = self.at('2027-03-01T00:00:00Z','2027-Q2'); self.closed_pattern(world,pid)
        self.fixture_publish(world,pid,'2027-01-15T00:00:00Z')
        q3 = create_weekly_plan(world,self.owner,'2027-Q3',slots=[])
        self.fixture_publish(world,q3,'2027-01-15T00:00:00Z')
        result = self.apply(self.session(world),self.request(mode='AUTOMATIC',pid=pid))
        self.assertTrue(result.skipped); self.assertEqual(result.planning_quarter_id,'2027-Q4')

    def test_default_carry_forward_latest_early_baseline(self):
        session = self.session(); self.apply(session)
        state = session.world['world_state']; previous = deepcopy(state['weekly_plans'][self.pid])
        services = deepcopy(state['services']); numbering = deepcopy(state['service_numbering'])
        result = self.apply(session,self.request(quarter='2027-Q3',absent=True))
        self.assertEqual(commands._plain(result.read.plans[0].slots[0].facts), previous['revisions']['1']['slots'][0])
        self.assertEqual(session.world['world_state']['weekly_plans'][self.pid],previous)
        self.assertEqual(session.world['world_state']['services'],services)
        self.assertEqual(session.world['world_state']['service_numbering'],numbering)
        self.assertEqual(result.planning_quarter_id,'2027-Q4')
        self.assertNotEqual(result.weekly_plan_id,self.pid)

    def test_latest_preceding_baseline_not_older_active_plan(self):
        rows = deepcopy(self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'])
        older = create_weekly_plan(self.world,self.owner,'2027-Q1',slots=[])
        self.fixture_publish(self.world,older,'2027-01-01T00:00:00Z')
        self.fixture_publish(self.world,self.pid)
        session = self.session()
        result = self.apply(session,self.request(quarter='2027-Q3',absent=True))
        self.assertEqual([commands._plain(s.facts) for s in result.read.plans[0].slots],rows)

    def test_explicit_edited_revision_wins_and_retains_prior_facts(self):
        self.fixture_publish(self.world,self.pid)
        rows = deepcopy(self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'])
        target = create_weekly_plan(self.world,self.owner,'2027-Q3',slots=rows)
        rows[0]['fare_offer']['amount_minor'] = 20000
        append_weekly_plan_revision(self.world,target,expected_revision=1,slots=rows)
        session = self.session(); before = deepcopy(session.world['world_state']['weekly_plans'][target]['revisions']['1'])
        result = self.apply(session,self.request(quarter='2027-Q3',pid=target,revision=2))
        self.assertEqual(result.revision,2)
        self.assertEqual(result.read.plans[0].slots[0].facts['fare_offer']['amount_minor'],20000)
        self.assertEqual(session.world['world_state']['weekly_plans'][target]['revisions']['1'],before)

    def test_explicit_removal_empty_plan_does_not_resurrect_baseline(self):
        self.fixture_publish(self.world,self.pid)
        target = create_weekly_plan(self.world,self.owner,'2027-Q3',slots=[])
        result = self.apply(self.session(),self.request(quarter='2027-Q3',pid=target))
        self.assertEqual(result.read.plans[0].slots,())

    def test_retired_baseline_not_inherited_and_number_protection_kept(self):
        self.fixture_publish(self.world,self.pid)
        for row in self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots']:
            retire_service(self.world,row['service_id'])
        session = self.session()
        result = self.apply(session,self.request(quarter='2027-Q3',absent=True))
        self.assertEqual(result.read.plans[0].slots,())
        from game.world_state.service_numbers import eligible_retired_numbers
        self.assertEqual(eligible_retired_numbers(session.world,self.owner),())

    def test_retired_explicit_draft_rejects_without_silent_repair(self):
        sid = self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]['service_id']
        retire_service(self.world,sid)
        session = self.session(); before = foundation.encoded(session.world)
        result = session.prepare_quarterly_command(self.request())
        self.assertEqual(result.issues[0].code,'RETIRED_SERVICE')
        self.assertEqual(foundation.encoded(session.world),before)

    def test_new_airline_missing_plan_does_not_manufacture(self):
        world,_,_ = self.at('2027-01-15T00:00:00Z')
        session = self.session(world); before = foundation.encoded(session.world)
        result = session.prepare_quarterly_command(self.request(absent=True))
        self.assertEqual(result.issues[0].code,'MISSING_PLAN')
        self.assertEqual(foundation.encoded(session.world),before)

    def test_hypothetical_positioning_rejects_and_corrected_plan_retries_fresh(self):
        world,pid,_ = self.at('2027-01-15T00:00:00Z','2027-Q2')
        session = self.session(world); request = self.request(pid=pid)
        prepared = self.prepare(session,request); index = session._quarterly_indexes.current
        before = foundation.encoded(session.world)
        result = session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'UNRESOLVED_POSITIONING')
        self.assertEqual(foundation.encoded(session.world),before)
        self.assertIs(session._quarterly_indexes.current,index)
        # Correct the unsupported literal chain in a separate validated test candidate;
        # rebind revokes old issuance and fresh preparation now succeeds.
        fixed = deepcopy(session.world); self.closed_pattern(fixed,pid)
        session.world = fixed
        self.assertEqual(session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        self.apply(session,request)

    def test_lease_horizon_blocks_publication(self):
        from game.aircraft_market.step5 import preview_lease, accept_lease
        from game.world_state.planning_reference import planning_snapshot
        state = self.world['world_state']; origin = self.f.origin
        offer = state['aircraft_market_state']['active_lease_offer_ids'][0]
        aid = accept_lease(self.world,preview_lease(self.world,airline_id=self.owner,offer_id=offer,
            contract_type='OPERATING_LEASE',term_years=1,delivery_airport_id=origin))
        state = self.world['world_state']; state['weekly_plans'][self.pid]['quarter_id']='2028-Q2'
        for row in state['weekly_plans'][self.pid]['revisions']['1']['slots']:
            row.update(planned_aircraft_id=aid,
                capacity=state['aircraft'][aid]['configuration']['economy_capacity'] if row['service_type']=='PASSENGER' else 0,
                planning_timing=planning_snapshot(state,aid,row['origin_airport_id'],row['destination_airport_id']))
            if row['service_type']=='DEADHEAD': row['departure_local_time']='16:00:00'
        for quarter in ('2027-Q2','2027-Q3','2027-Q4','2028-Q1'):
            pid = create_weekly_plan(self.world,self.owner,quarter,slots=[]); self.fixture_publish(self.world,pid)
        session = self.session(); prepared = self.prepare(session,self.request(quarter='2028-Q2'))
        before = foundation.encoded(session.world)
        result = session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'CONTRACT_HORIZON_EXCEEDED')
        self.assertEqual(foundation.encoded(session.world),before)

    def test_wrong_owner_stale_revision_time_and_absence(self):
        from game.world_state.construction import add_airline
        other = add_airline(self.world,'Other',base_airport_id=self.f.origin)
        result = commands.prepare_quarterly_command(self.world,airline_id=other,request=self.request())
        self.assertEqual(result.issues[0].code,'OWNERSHIP_MISMATCH')
        session = self.session()
        for request,code in ((replace(self.request(),expected_revision=2),'STALE_REVISION'),
                             (replace(self.request(),expected_time_utc='2027-01-14T00:00:00Z'),'STALE_CONTEXT'),
                             (self.request(absent=True),'STALE_REVISION')):
            self.assertEqual(session.prepare_quarterly_command(request).issues[0].code,code)

    def test_load_rebind_and_forged_preparation_revoke_issuance(self):
        session = self.session(); prepared = self.prepare(session)
        self.assertEqual(session.apply_quarterly_command(replace(prepared)).issues[0].code,'STALE_CONTEXT')
        session.load_saved(session.career_id)
        self.assertEqual(session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        prepared = self.prepare(session); session.world = deepcopy(session.world)
        self.assertEqual(session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')

    def test_stale_dependency_rejects_preserving_external_change(self):
        session = self.session(); prepared = self.prepare(session)
        session.world['world_state']['aircraft'][self.f.aircraft]['display_registration']='RP-C9999'
        before = foundation.encoded(session.world)
        result = session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'STALE_CONTEXT')
        self.assertEqual(foundation.encoded(session.world),before)

    def test_published_save_load_occurrence_lineage_roundtrip(self):
        session = self.session(); result = self.apply(session)
        slot = result.read.plans[0].slots[0]
        request = OccurrenceReadRequest(QuarterlyOccurrenceReference(self.pid,1,slot.service_id,1,'2027-04-05'),1)
        observed = resolve_quarterly_occurrences(session.world,airline_id=self.owner,requests=(request,))
        self.assertTrue(observed.succeeded,observed.issues)
        before = foundation.encoded(session.world)
        session.save_manual(); session.load_saved(session.career_id)
        self.assertEqual(resolve_quarterly_occurrences(session.world,airline_id=self.owner,requests=(request,)),observed)
        self.assertEqual(foundation.encoded(session.world),before)

    def test_indexed_reference_and_rebuild_equal_for_existing_and_carry_forward(self):
        for missing in (False,True):
            world = deepcopy(self.world)
            if missing: self.fixture_publish(world,self.pid)
            session = self.session(world); reference = deepcopy(session.world)
            request = self.request(quarter='2027-Q3',absent=True) if missing else self.request()
            indexed = self.prepare(session,request)
            plain = commands.prepare_quarterly_command(reference,airline_id=self.owner,request=request)
            self.assertTrue(plain.succeeded,plain.issues); self.assertEqual(indexed,plain.prepared)
            actual = session.apply_quarterly_command(indexed)
            expected = commands.apply_quarterly_command(reference,airline_id=self.owner,prepared=plain.prepared)
            self.assertTrue(actual.succeeded,actual.issues); self.assertEqual(actual,expected)
            self.assertEqual(foundation.encoded(session.world),foundation.encoded(reference))
            rebuilt = QuarterlyDependencyIndex._build(session.world)
            for field in ('_maps','_plans','_quarters','_numbers','_endpoints','_ends','_departures'):
                self.assertEqual(getattr(session._quarterly_indexes.current,field),getattr(rebuilt,field))

    def test_four_gates_two_copies_and_detached_candidate_aliases(self):
        session = self.session(); gates=[]; copies=[]
        entry = commands._entry; copy = commands.deepcopy
        def gate(world): gates.append(world); return entry(world)
        def cloned(value):
            result = copy(value)
            if type(value) is dict and 'world_state' in value: copies.append(result)
            return result
        with patch.object(commands,'_entry',side_effect=gate), patch.object(commands,'deepcopy',side_effect=cloned):
            self.apply(session)
        self.assertEqual(len(gates),4); self.assertEqual(len(copies),2)
        self.assertIs(gates[2],copies[0]); self.assertIs(gates[3],copies[1])
        copies[0]['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'].clear()
        self.assertEqual(len(session.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots']),2)

    def test_candidate_real_validation_failure_preserves_all_authority_and_retry(self):
        session = self.session(); prepared = self.prepare(session)
        before = foundation.encoded(session.world); index = session._quarterly_indexes.current
        commit = commands.commit_weekly_plan_publication
        def corrupt(*args,**kwargs):
            result = commit(*args,**kwargs)
            args[0]['world_state']['weekly_plans'][self.pid]['revisions']['1']['published_at_utc']='2099-01-01T00:00:00Z'
            return result
        with patch.object(commands,'commit_weekly_plan_publication',side_effect=corrupt):
            result = session.apply_quarterly_command(prepared)
        self.assertFalse(result.succeeded); self.assertEqual(foundation.encoded(session.world),before)
        self.assertIs(session._quarterly_indexes.current,index)
        self.assertTrue(session.apply_quarterly_command(prepared).succeeded)

    def test_final_freshness_rejects_after_index_preparation(self):
        session = self.session(); prepared = self.prepare(session)
        index = session._quarterly_indexes.current
        original = type(session._quarterly_indexes).prepare_publication
        def changed(owner,*args):
            result = original(owner,*args)
            session.world['world_state']['aircraft'][self.f.aircraft]['display_registration']='RP-C9999'
            return result
        with patch.object(type(session._quarterly_indexes),'prepare_publication',changed):
            result = session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'STALE_CONTEXT')
        self.assertIsNone(session.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['published_at_utc'])
        self.assertIs(session._quarterly_indexes.current,index)

    def test_automatic_carry_forward_at_boundary(self):
        world,pid,_ = self.at('2027-03-01T00:00:00Z','2027-Q1')
        self.closed_pattern(world,pid)
        rows = world['world_state']['weekly_plans'][pid]['revisions']['1']['slots']
        # This cold boundary fixture has no prior handling history. Its active
        # baseline must start after now, allowing authoritative preparation.
        rows[0]['departure_local_time']='10:00:00'; rows[1]['departure_local_time']='16:00:00'
        self.fixture_publish(world,pid,'2027-01-01T00:00:00Z')
        rows = deepcopy(world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'])
        result = self.apply(self.session(world),self.request(mode='AUTOMATIC',absent=True))
        self.assertEqual([commands._plain(s.facts) for s in result.read.plans[0].slots],rows)
        self.assertEqual(result.read.plans[0].published_at_utc,'2027-03-01T00:00:00Z')

    def test_cross_quarter_duplicate_service_date_rejects_even_across_aircraft(self):
        session = self.session()
        newer = session.purchase(session.preview_purchase('airbus-a320neo',self.f.origin))
        world = session.world; state = world['world_state']
        first = deepcopy(state['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        earlier = dict(first,weekdays=[3],departure_local_time='07:00:00')
        previous = create_weekly_plan(world,self.owner,'2027-Q1',slots=[earlier])
        self.fixture_publish(world,previous,'2027-01-01T00:00:00Z')
        first.update(weekdays=[3],departure_local_time='09:50:00',planned_aircraft_id=newer)
        state['weekly_plans'][self.pid]['revisions']['1']['slots']=[first]
        session.world = deepcopy(world)
        prepared = self.prepare(session); before = foundation.encoded(session.world)
        result = session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'INFEASIBLE_PLAN')
        self.assertIn('DUPLICATE_OCCURRENCE',result.issues[0].message)
        self.assertEqual(foundation.encoded(session.world),before)

    def test_existing_timed_legacy_deadhead_provides_literal_positioning(self):
        from game.scheduling import WeeklyDraft
        from game.world_state.planning_reference import planning_snapshot
        world,pid,f = self.at('2026-12-01T00:00:00Z','2027-Q1')
        state = world['world_state']; row = state['weekly_plans'][pid]['revisions']['1']['slots'][0]
        row.update(origin_airport_id=f.dest,destination_airport_id=f.origin,
            connection_id=None,service_type='DEADHEAD',capacity=0,fare_offer={'currency':'USD','amount_minor':0},
            planning_timing=planning_snapshot(state,f.aircraft,f.dest,f.origin))
        self.closed_pattern(world,pid)
        draft = WeeklyDraft(world,airline_id=self.owner,aircraft_id=f.aircraft)
        draft.add(f.origin,f.dest,departure_utc='2026-12-31T01:00:00Z',deadhead=True)
        draft.save_current(world)
        self.apply(self.session(world),self.request(mode='AUTOMATIC',quarter='2027-Q1',pid=pid))

    def test_baseline_revision_or_retirement_change_invalidates_missing_target(self):
        self.fixture_publish(self.world,self.pid)
        session = self.session(); request = self.request(quarter='2027-Q3',absent=True)
        prepared = self.prepare(session,request)
        baseline = session.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots']
        sid = baseline[0]['service_id']
        retire_service(session.world,sid)
        before = foundation.encoded(session.world)
        result = session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'STALE_CONTEXT')
        self.assertEqual(foundation.encoded(session.world),before)

    def test_carry_forward_allocation_failure_and_same_preparation_retry_match_control(self):
        self.fixture_publish(self.world,self.pid)
        session = self.session(); request = self.request(quarter='2027-Q3',absent=True)
        prepared = self.prepare(session,request); reference = deepcopy(session.world)
        before = foundation.encoded(session.world); index = session._quarterly_indexes.current
        create = commands.create_weekly_plan
        def fail(*args,**kwargs): create(*args,**kwargs); raise ValueError('after plan allocation')
        with patch.object(commands,'create_weekly_plan',side_effect=fail):
            result = session.apply_quarterly_command(prepared)
        self.assertFalse(result.succeeded); self.assertEqual(foundation.encoded(session.world),before)
        self.assertIs(session._quarterly_indexes.current,index)
        actual = session.apply_quarterly_command(prepared)
        ref_prepared = commands.prepare_quarterly_command(reference,airline_id=self.owner,request=request).prepared
        expected = commands.apply_quarterly_command(reference,airline_id=self.owner,prepared=ref_prepared)
        self.assertEqual(actual,expected)
        self.assertEqual(foundation.encoded(session.world),foundation.encoded(reference))

    def test_failures_after_fallible_staging_keep_exact_world_and_accepted_epoch(self):
        from game.scheduling.quarterly_indexes import QuarterlyIndexOwner
        for target,name in (
            (commands,'commit_weekly_plan_publication'),(commands,'certify_quarterly_feasibility'),
            (commands,'require_execution'),(QuarterlyDependencyIndex,'updated'),
            (QuarterlyDependencyIndex,'verify_delta'),(QuarterlyDependencyIndex,'rebound'),
            (QuarterlyIndexOwner,'prepare_publication'),(commands,'QuarterlyCommandResult')):
            with self.subTest(seam=name):
                session = self.session(); prepared = self.prepare(session)
                before = foundation.encoded(session.world); index = session._quarterly_indexes.current
                original = getattr(target,name)
                def fail(*args,**kwargs):
                    if name=='QuarterlyCommandResult' and not(args and args[0] is True):
                        return original(*args,**kwargs)
                    original(*args,**kwargs)
                    self.assertEqual(foundation.encoded(session.world),before)
                    self.assertIs(session._quarterly_indexes.current,index)
                    raise ValueError('after fallible '+name)
                with patch.object(target,name,side_effect=fail):
                    rejected = session.apply_quarterly_command(prepared)
                self.assertFalse(rejected.succeeded)
                self.assertEqual(foundation.encoded(session.world),before)
                self.assertIs(session._quarterly_indexes.current,index)
                self.assertTrue(session.apply_quarterly_command(prepared).succeeded)

    def test_failure_after_each_apply_gate_keeps_prior_authority(self):
        for gate_number in (1,2,3):
            session = self.session(); prepared = self.prepare(session)
            before = foundation.encoded(session.world); index = session._quarterly_indexes.current
            count=0; entry=commands._entry
            def gate(world):
                nonlocal count
                entry(world); count+=1
                self.assertEqual(foundation.encoded(session.world),before)
                self.assertIs(session._quarterly_indexes.current,index)
                if count==gate_number: raise ValueError('after complete gate')
            with patch.object(commands,'_entry',side_effect=gate):
                result = session.apply_quarterly_command(prepared)
            self.assertFalse(result.succeeded)
            self.assertEqual(foundation.encoded(session.world),before)
            self.assertIs(session._quarterly_indexes.current,index)
            self.assertTrue(session.apply_quarterly_command(prepared).succeeded)

    def test_publication_response_and_preparation_are_detached_and_not_readiness_capabilities(self):
        from dataclasses import FrozenInstanceError
        session = self.session(); prepared = self.prepare(session)
        with self.assertRaises(TypeError): prepared.intent['mode']='AUTOMATIC'
        with self.assertRaises(TypeError): prepared.sources['plans'][self.pid]={}
        ready = session.quarterly_publication_readiness(self.pid,expected_revision=1)
        before = foundation.encoded(session.world)
        self.assertEqual(session.apply_quarterly_command(ready).issues[0].code,'STALE_CONTEXT')
        self.assertEqual(foundation.encoded(session.world),before)
        result = session.apply_quarterly_command(prepared)
        self.assertTrue(result.succeeded,result.issues)
        with self.assertRaises(FrozenInstanceError): result.planning_quarter_id='2027-Q4'
        with self.assertRaises(TypeError): result.read.plans[0].slots[0].facts['capacity']=1

    def new_movement(self, *, reverse=False):
        state=self.world['world_state']
        row=deepcopy(state['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        for key in ('service_id','slot_number','planning_timing'): row.pop(key)
        row.update(weekdays=[1],service_type='DEADHEAD',connection_id=None,capacity=0,
                   fare_offer={'currency':'USD','amount_minor':0})
        if reverse:
            row.update(origin_airport_id=row['destination_airport_id'],destination_airport_id=row['origin_airport_id'],
                       departure_local_time='12:00:00')
        return row

    def test_first_new_service_edit_seeds_baseline_before_publication(self):
        self.fixture_publish(self.world,self.pid)
        session=self.session(); baseline=deepcopy(session.world['world_state']['weekly_plans'][self.pid])
        first=self.apply(session,commands.CreateQuarterlyService('2027-Q3','DAB',self.new_movement()))
        self.assertEqual(len(first.read.plans[0].slots),3)
        inherited={(s.service_id,s.slot_number) for s in first.read.plans[0].slots}
        self.assertTrue({(s['service_id'],s['slot_number']) for s in baseline['revisions']['1']['slots']}<=inherited)
        second=self.apply(session,commands.CreateQuarterlyService('2027-Q3','DAB',self.new_movement(reverse=True),
            first.weekly_plan_id,1))
        result=self.apply(session,self.request(quarter='2027-Q3',pid=first.weekly_plan_id,revision=2))
        self.assertEqual(len(result.read.plans[0].slots),4)
        self.assertEqual(session.world['world_state']['weekly_plans'][self.pid],baseline)

    def test_first_explicit_continuation_amends_one_slot_preserves_other_frequencies(self):
        from game.scheduling.quarterly_edits import ContinueQuarterlySlot
        self.fixture_publish(self.world,self.pid)
        row=self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        session=self.session()
        request=ContinueQuarterlySlot(None,0,self.pid,1,1,row['service_id'],row['slot_number'],
            {'fare_offer':{'currency':'USD','amount_minor':22000}},quarter_id='2027-Q3')
        result=self.apply(session,request)
        self.assertEqual(len(result.read.plans[0].slots),2)
        self.assertEqual(result.read.plans[0].slots[0].facts['fare_offer']['amount_minor'],22000)
        self.assertEqual(len({(s.service_id,s.slot_number) for s in result.read.plans[0].slots}),2)
        self.apply(session,self.request(quarter='2027-Q3',pid=result.weekly_plan_id))

    def test_explicit_removal_after_seed_survives_publication(self):
        from game.scheduling.quarterly_edits import RemoveQuarterlySlots,ContinueQuarterlySlot
        self.fixture_publish(self.world,self.pid)
        row=self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        session=self.session()
        result=self.apply(session,ContinueQuarterlySlot(None,0,self.pid,1,1,row['service_id'],1,{},quarter_id='2027-Q3'))
        keys=tuple((s.service_id,s.slot_number) for s in result.read.plans[0].slots)
        removed=self.apply(session,RemoveQuarterlySlots(result.weekly_plan_id,1,keys))
        self.assertEqual(removed.read.plans[0].slots,())
        self.assertEqual(self.apply(session,self.request(quarter='2027-Q3',pid=result.weekly_plan_id,revision=2)).read.plans[0].slots,())

    def test_first_edit_baseline_stale_facts_reject_and_keep_cursors(self):
        self.fixture_publish(self.world,self.pid)
        session=self.session()
        prepared=self.prepare(session,commands.CreateQuarterlyService('2027-Q3','DAB',self.new_movement()))
        session.world['world_state']['aircraft'][self.f.aircraft]['display_registration']='RP-C9999'
        before=foundation.encoded(session.world)
        result=session.apply_quarterly_command(prepared)
        self.assertEqual(result.issues[0].code,'STALE_CONTEXT')
        self.assertEqual(foundation.encoded(session.world),before)

    def test_first_edit_retired_baseline_excluded_without_lifetime_reuse(self):
        self.fixture_publish(self.world,self.pid)
        retired={s['service_id'] for s in self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots']}
        for sid in retired: retire_service(self.world,sid)
        session=self.session()
        result=self.apply(session,commands.CreateQuarterlyService('2027-Q3','DAB',self.new_movement()))
        self.assertEqual(len(result.read.plans[0].slots),1)
        self.assertNotIn(result.service_id,retired)
        self.assertEqual(result.read.plans[0].slots[0].flight_number,'DAB03')

    def test_first_edit_indexed_reference_and_history_remain_equal(self):
        self.fixture_publish(self.world,self.pid)
        session=self.session(); reference=deepcopy(session.world)
        request=commands.CreateQuarterlyService('2027-Q3','DAB',self.new_movement())
        prepared=self.prepare(session,request)
        plain=commands.prepare_quarterly_command(reference,airline_id=self.owner,request=request)
        self.assertEqual(prepared,plain.prepared)
        actual=session.apply_quarterly_command(prepared)
        expected=commands.apply_quarterly_command(reference,airline_id=self.owner,prepared=plain.prepared)
        self.assertTrue(actual.succeeded,actual.issues); self.assertEqual(actual,expected)
        self.assertEqual(foundation.encoded(session.world),foundation.encoded(reference))


def boundary_case(stamp,quarter):
    def test(self):
        world,pid,_ = self.at(stamp,quarter); self.closed_pattern(world,pid)
        result = self.apply(self.session(world),self.request(mode='AUTOMATIC',quarter=quarter,pid=pid))
        self.assertEqual(result.read.plans[0].published_at_utc,stamp)
        self.assertEqual(result.read.plans[0].quarter_id,quarter)
        self.assertEqual(result.planning_quarter_id,normal_target_quarter(stamp).quarter_id)
    return test

for name,stamp,quarter in (
    ('march','2027-03-01T00:00:00Z','2027-Q2'),
    ('june','2027-06-01T00:00:00Z','2027-Q3'),
    ('september','2027-09-01T00:00:00Z','2027-Q4'),
    ('december','2027-12-01T00:00:00Z','2028-Q1')):
    setattr(QuarterlyPublicationTests,'test_automatic_'+name,boundary_case(stamp,quarter))


if __name__=='__main__': unittest.main()
