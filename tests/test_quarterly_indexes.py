"""Independent source oracles, owner freshness and atomic inverse deltas."""
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from tests.profile_quarterly_dependencies import fixture
from tests.test_quarterly_foundation import encoded
from game.scheduling.quarterly_indexes import QuarterlyDependencyIndex, QuarterlyIndexOwner
from game.scheduling.quarterly_feasibility import temporal_sources, certify_quarterly_feasibility
from game.scheduling.quarterly_commands import (
    _sources, CreateQuarterlyService, ReviseQuarterlyFare, ReviseQuarterlySlot,
    AddQuarterlyFrequency, RemoveQuarterlySlots, ContinueQuarterlySlot,
    ReplaceQuarterlyService, RetireQuarterlyService)
from game.world_state.quarterly_construction import create_weekly_plan
from game.world_state.service_numbers import protected_number_holders, eligible_retired_numbers
from game.world_state.timestamps import parse_canonical_utc


def independent_edges(world):
    """Separate direct field enumeration, not the index's edge builder."""
    result = {}
    def add(relation, key, value):
        result.setdefault(relation, {}).setdefault(key, set()).add(value)
    state = world['world_state']
    for pid, plan in state['weekly_plans'].items():
        add('owner_plans', plan['airline_id'], pid)
        for row in plan['revisions'][str(plan['current_revision'])]['slots']:
            add('service_plans', row['service_id'], pid)
            add('aircraft_plans', row['planned_aircraft_id'], pid)
            add('aircraft_slots', row['planned_aircraft_id'], (pid,row['service_id'],row['slot_number']))
            for field in ('origin_airport_id','destination_airport_id'):
                add('airport_plans', row[field], pid)
            if row['connection_id'] is not None:add('connection_plans', row['connection_id'], pid)
    for sid, service in state['services'].items():add('owner_services', service['airline_id'], sid)
    for sid, schedule in state['schedule_definitions'].items():
        for row in schedule['revisions'].values():add('aircraft_schedules', row['planned_aircraft_id'], sid)
    for fid, flight in state['dated_flights'].items():
        if flight['status'] not in {'SUPERSEDED','CANCELLED'}:add('aircraft_flights', flight['planned_aircraft_id'], fid)
    for oid, operation in state['active_aircraft_operations'].items():add('aircraft_operations', operation['actual_aircraft_id'], oid)
    return result


class QuarterlyIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.world, self.owner, self.aid, self.pid, self.sid = fixture(2)
        self.session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        self.session.world = self.world; self.session.career_id = self.session.save_store.new_career_id()
        self.session.save_manual(); self.session.load_saved(self.session.career_id)

    @property
    def state(self):return self.session.world['world_state']

    def request(self, revision=1):
        return ReviseQuarterlyFare(self.pid, revision, self.sid, 1, {'currency':'USD','amount_minor':20000})

    def warm(self):
        revision = self.state['weekly_plans'][self.pid]['current_revision']
        ready = self.session.prepare_quarterly_command(self.request(revision))
        self.assertTrue(ready.succeeded, ready.issues)
        return self.session._quarterly_indexes.current

    def assert_index(self):
        index = self.session._quarterly_indexes.current
        self.assertTrue(index.matches(self.session.world))
        expected = independent_edges(self.session.world)
        actual = {name: {key:set(values) for key,values in mapping.items()}
                  for name,mapping in index._maps.items() if mapping}
        self.assertEqual(actual, expected)
        for owner in self.state['service_numbering']:
            holders = protected_number_holders(self.session.world, airline_id=owner)
            self.assertEqual(dict(index.number_holders(owner)), {suffix:ids for (_,suffix),ids in holders.items()})
            self.assertEqual(index.eligible_numbers(owner), eligible_retired_numbers(self.session.world, owner))
        self.assertEqual(temporal_sources(self.session.world,{self.aid},index=index),
                         temporal_sources(self.session.world,{self.aid}))

    def apply(self, request):
        prepared = self.session.prepare_quarterly_command(request)
        self.assertTrue(prepared.succeeded, prepared.issues)
        result = self.session.apply_quarterly_command(prepared.prepared)
        self.assertTrue(result.succeeded, result.issues); self.assert_index()
        return result

    def facts(self, **changes):
        row = deepcopy(self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        for key in ('service_id','slot_number','planning_timing'):del row[key]
        row.update(changes);return row

    def test_build_matches_independent_source_relationships(self):
        self.warm(); self.assert_index()

    def test_quarter_pair_and_endpoint_lookup(self):
        index = self.warm()
        self.assertEqual(index.plan_for_quarter(self.owner,'2027-Q1'),self.pid)
        row = self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        self.assertEqual(index._endpoints[self.sid],(row['origin_airport_id'],row['destination_airport_id']))

    def test_snapshot_and_returned_relationships_are_immutable(self):
        index = self.warm()
        with self.assertRaises(AttributeError):index.epoch=99
        with self.assertRaises(TypeError):index._maps['aircraft_plans'][self.aid]=frozenset()
        self.assertIsInstance(index.ids('aircraft_plans',self.aid),tuple)

    def test_fare_update_uses_delta_without_rebuild(self):
        index = self.warm()
        with patch.object(QuarterlyDependencyIndex,'_build',side_effect=AssertionError('unexpected rebuild')):
            self.apply(self.request())
        self.assertEqual(self.session._quarterly_indexes.current.epoch,index.epoch+1)

    def test_frequency_add_revise_and_remove_match_oracle(self):
        self.warm()
        self.apply(AddQuarterlyFrequency(self.pid,1,self.sid,self.facts(weekdays=[1])))
        self.apply(ReviseQuarterlySlot(self.pid,2,self.sid,2,{'weekdays':[2],'departure_local_time':'09:00:00'}))
        self.apply(RemoveQuarterlySlots(self.pid,3,((self.sid,2),)))

    def test_creation_updates_number_and_plan_edges(self):
        self.warm()
        new = self.apply(CreateQuarterlyService('2027-Q1','DAB',self.facts(weekdays=[2]),self.pid,1))
        self.assertIn(new.service_id,self.session._quarterly_indexes.current.ids('owner_services',self.owner))

    def test_endpoint_replacement_keeps_retained_binding(self):
        index = self.warm(); origin,dest = index._endpoints[self.sid]
        new = self.apply(ReplaceQuarterlyService(self.pid,1,self.sid,'DAB',self.facts(
            origin_airport_id=dest,destination_airport_id=origin,connection_id=None,
            service_type='DEADHEAD',capacity=0,fare_offer={'currency':'USD','amount_minor':0})))
        index = self.session._quarterly_indexes.current
        self.assertEqual(index._endpoints[self.sid],(origin,dest))
        self.assertEqual(index._endpoints[new.service_id],(dest,origin))

    def test_removal_retirement_and_reuse_keep_number_oracle(self):
        self.warm()
        self.apply(RemoveQuarterlySlots(self.pid,1,((self.sid,1),)))
        self.apply(RetireQuarterlyService(self.pid,2,self.sid))
        self.assertEqual(self.session._quarterly_indexes.current.eligible_numbers(self.owner),(1,))
        new = self.apply(CreateQuarterlyService('2027-Q1','DAB',self.facts(),self.pid,2))
        self.assertNotEqual(new.service_id,self.sid)
        self.assertEqual(new.read.plans[0].slots[0].flight_number,'DAB01')

    def test_explicit_continuation_uses_both_quarter_relationships(self):
        source = deepcopy(self.state['weekly_plans'][self.pid]['revisions']['1']['slots'])
        prior = create_weekly_plan(self.session.world,self.owner,'2026-Q4',slots=source)
        # This is fixture construction, not a production writer. Cold validated
        # load establishes fresh exclusive ownership before index use.
        self.session.save_manual(); self.session.load_saved(self.session.career_id)
        self.warm();self.apply(RemoveQuarterlySlots(self.pid,1,((self.sid,1),)))
        self.apply(ContinueQuarterlySlot(self.pid,2,prior,1,1,self.sid,1,{'weekdays':[1]}))
        self.assertEqual(set(self.session._quarterly_indexes.current.ids('service_plans',self.sid)),{self.pid,prior})

    def test_committed_retirement_protection_matches_number_oracle(self):
        prior = create_weekly_plan(self.session.world,self.owner,'2026-Q4',slots=deepcopy(
            self.state['weekly_plans'][self.pid]['revisions']['1']['slots']))
        self.state['weekly_plans'][prior]['revisions']['1']['published_at_utc']=self.session.world['simulation']['time_utc']
        self.session.save_manual();self.session.load_saved(self.session.career_id)
        self.warm();self.apply(RemoveQuarterlySlots(self.pid,1,((self.sid,1),)))
        self.apply(RetireQuarterlyService(self.pid,2,self.sid))
        self.assertEqual(self.session._quarterly_indexes.current.eligible_numbers(self.owner),())

    def test_stale_preparation_rejects_without_delta(self):
        prepared = self.session.prepare_quarterly_command(self.request()).prepared
        self.apply(ReviseQuarterlySlot(self.pid,1,self.sid,1,{'weekdays':[1]}))
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        bad=self.session.apply_quarterly_command(prepared)
        self.assertFalse(bad.succeeded);self.assertEqual(encoded(self.session.world),before)
        self.assertIs(self.session._quarterly_indexes.current,index)

    def test_delta_failure_is_atomic_and_retry_matches_control(self):
        prepared=self.session.prepare_quarterly_command(self.request()).prepared
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        with patch.object(QuarterlyDependencyIndex,'updated',side_effect=ValueError('delta failure')):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(encoded(self.session.world),before);self.assertIs(self.session._quarterly_indexes.current,index)
        self.assertTrue(self.session.apply_quarterly_command(prepared).succeeded);self.assert_index()

    def test_index_publication_failure_precedes_authority_commit(self):
        prepared=self.session.prepare_quarterly_command(self.request()).prepared
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        with patch.object(QuarterlyIndexOwner,'prepare_publication',side_effect=ValueError('publication failure')):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(encoded(self.session.world),before);self.assertIs(self.session._quarterly_indexes.current,index)

    def test_chronology_failure_does_not_publish_delta(self):
        prepared=self.session.prepare_quarterly_command(AddQuarterlyFrequency(self.pid,1,self.sid,self.facts())).prepared
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(encoded(self.session.world),before);self.assertIs(self.session._quarterly_indexes.current,index)

    def test_foreign_binding_retains_safe_enumeration(self):
        self.warm(); self.session.world=deepcopy(self.session.world)
        self.assertIsNone(self.session._quarterly_indexes)
        self.apply_without_index(self.request())

    def apply_without_index(self, request):
        prepared=self.session.prepare_quarterly_command(request)
        self.assertTrue(prepared.succeeded,prepared.issues)
        result=self.session.apply_quarterly_command(prepared.prepared)
        self.assertTrue(result.succeeded,result.issues)

    def test_load_reconstructs_and_revokes_preparation(self):
        prepared=self.session.prepare_quarterly_command(self.request()).prepared
        old=self.session._quarterly_indexes.current
        self.session.save_manual();self.session.load_saved(self.session.career_id)
        self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertIsNone(self.session._quarterly_indexes.current)
        self.assertIsNot(self.warm(),old);self.assert_index()

    def test_legacy_purchase_invalidates_lazily(self):
        self.warm()
        origin=self.state['aircraft'][self.aid]['home_airport_id']
        self.session.purchase(self.session.preview_purchase('airbus-a320neo',origin))
        self.assertIsNone(self.session._quarterly_indexes.current)
        self.warm();self.assert_index()

    def test_wrong_owner_rejects_and_index_stays_unchanged(self):
        index=self.warm();other=next(s for s in self.state['services'] if s!=self.sid)
        request=ReviseQuarterlyFare(self.pid,1,other,1,{'currency':'USD','amount_minor':100})
        self.assertFalse(self.session.prepare_quarterly_command(request).succeeded)
        self.assertIs(self.session._quarterly_indexes.current,index)

    def test_index_and_reference_feasibility_agree(self):
        index=self.warm()
        certify_quarterly_feasibility(self.session.world,{self.aid},index=index)
        certify_quarterly_feasibility(self.session.world,{self.aid})
        # Existing independent 2C oracle must also reject an indexed duplicate.
        other=deepcopy(self.session.world)
        from game.world_state.quarterly_construction import append_weekly_plan_revision,allocate_service_slot
        number=allocate_service_slot(other,self.sid)
        row=deepcopy(other['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]);row['slot_number']=number
        append_weekly_plan_revision(other,self.pid,expected_revision=1,slots=[other['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0],row])
        idx=QuarterlyDependencyIndex._build(other)
        for selected in (None,idx):
            with self.assertRaisesRegex(ValueError,'AIRCRAFT_OVERLAP'):
                certify_quarterly_feasibility(other,{self.aid},index=selected)

    def test_construction_order_does_not_change_discovery(self):
        first=self.warm();other=deepcopy(self.session.world)
        for table in ('weekly_plans','services','aircraft'):
            other['world_state'][table]=dict(reversed(list(other['world_state'][table].items())))
        second=QuarterlyDependencyIndex._build(other)
        self.assertEqual(first._maps,second._maps)
        self.assertEqual(temporal_sources(self.session.world,{self.aid},index=first),temporal_sources(other,{self.aid},index=second))

    def test_sources_match_unindexed_oracle_exactly(self):
        index=self.warm();intent={'kind':'FARE','weekly_plan_id':self.pid,'expected_revision':1,
            'service_id':self.sid,'slot_number':1,'fare_offer':{'currency':'USD','amount_minor':100}}
        self.assertEqual(_sources(self.session.world,self.owner,intent,index),_sources(self.session.world,self.owner,intent))

    def test_partial_foreign_index_fails_closed(self):
        self.warm();self.session._quarterly_indexes.current=object()
        before=encoded(self.session.world)
        self.assertFalse(self.session.prepare_quarterly_command(self.request()).succeeded)
        self.assertEqual(encoded(self.session.world),before)

    def test_incomplete_inverse_delta_cannot_approve_overlap(self):
        prepared=self.session.prepare_quarterly_command(AddQuarterlyFrequency(self.pid,1,self.sid,self.facts())).prepared
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        original=QuarterlyDependencyIndex.updated
        def incomplete(current,candidate,**kwargs):
            good=original(current,candidate,**kwargs)
            from types import MappingProxyType
            maps=dict(good._maps);maps['aircraft_plans']=MappingProxyType({})
            object.__setattr__(good,'_maps',MappingProxyType(maps))
            return good
        with patch.object(QuarterlyDependencyIndex,'updated',incomplete):
            result=self.session.apply_quarterly_command(prepared)
        self.assertFalse(result.succeeded);self.assertIn('incomplete',result.issues[0].message)
        self.assertEqual(encoded(self.session.world),before);self.assertIs(self.session._quarterly_indexes.current,index)

    def test_advance_invalidates_index_and_stales_clock_observation(self):
        prepared=self.session.prepare_quarterly_command(self.request()).prepared
        self.session.advance_seconds(1)
        self.assertIsNone(self.session._quarterly_indexes.current)
        self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.warm();self.assert_index()

    def test_new_game_resets_index_and_issued_context(self):
        prepared=self.session.prepare_quarterly_command(self.request()).prepared
        self.session.new_game('New','New','MNL')
        self.assertIsNotNone(self.session._quarterly_indexes)
        self.assertIsNone(self.session._quarterly_indexes.current)
        self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)

    def legacy_pattern(self, continuous=False):
        row=self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        draft=self.session.begin_scheduling(self.aid)
        draft.add_weekdays(row['origin_airport_id'],row['destination_airport_id'],['2026-09-07'],'08:00',return_flight=True)
        self.session.save_scheduling(draft,continuous=continuous)

    def test_legacy_scheduling_invalidates_and_rebuilds_reservations(self):
        self.warm();self.legacy_pattern()
        self.assertIsNone(self.session._quarterly_indexes.current)
        self.warm();self.assert_index()
        index=self.session._quarterly_indexes.current
        self.assertTrue(index.ids('aircraft_schedules',self.aid))
        self.assertTrue(index.relevant_flights(self.aid))

    def test_temporal_neighbors_match_ordered_dated_authority(self):
        self.legacy_pattern();index=self.warm()
        rows=sorted((parse_canonical_utc(f['scheduled_off_block_utc']),fid)
                    for fid,f in self.state['dated_flights'].items() if f['planned_aircraft_id']==self.aid)
        before,after=index.neighbors(self.aid,rows[0][0])
        self.assertEqual((before,after),(rows[0][1],rows[1][1]))

    def test_indexed_continuous_legacy_obligations_remain_protected(self):
        self.legacy_pattern(True);prepared=self.session.prepare_quarterly_command(self.request()).prepared
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        result=self.session.apply_quarterly_command(prepared)
        self.assertFalse(result.succeeded);self.assertIn('AIRCRAFT_OVERLAP',result.issues[0].message)
        self.assertEqual(encoded(self.session.world),before);self.assertIs(self.session._quarterly_indexes.current,index)

    def test_indexed_quarter_boundary_rejects_same_lineage_on_other_aircraft(self):
        row=deepcopy(self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        row['planned_aircraft_id']=self.session.purchase(self.session.preview_purchase(
            'airbus-a320neo',row['origin_airport_id']))
        row.update(weekdays=[3],departure_local_time='09:50:00')
        create_weekly_plan(self.session.world,self.owner,'2027-Q2',slots=[row])
        self.session.save_manual();self.session.load_saved(self.session.career_id)
        request=ReviseQuarterlySlot(self.pid,1,self.sid,1,{'weekdays':[3],'departure_local_time':'07:00:00'})
        prepared=self.session.prepare_quarterly_command(request).prepared
        before=encoded(self.session.world);index=self.session._quarterly_indexes.current
        result=self.session.apply_quarterly_command(prepared)
        self.assertFalse(result.succeeded);self.assertIn('DUPLICATE_OCCURRENCE',result.issues[0].message)
        self.assertEqual(encoded(self.session.world),before);self.assertIs(self.session._quarterly_indexes.current,index)

    def test_indexed_weekly_wrap_is_not_shortened_to_two_neighbors(self):
        self.apply(AddQuarterlyFrequency(self.pid,1,self.sid,self.facts(weekdays=[6],departure_local_time='23:00:00')))
        prepared=self.session.prepare_quarterly_command(ReviseQuarterlySlot(self.pid,2,self.sid,1,{'departure_local_time':'02:00:00'})).prepared
        before=encoded(self.session.world)
        result=self.session.apply_quarterly_command(prepared)
        self.assertFalse(result.succeeded);self.assertIn('REPOSITIONING_INFEASIBLE',result.issues[0].message)
        self.assertEqual(encoded(self.session.world),before)

    def test_indexed_and_unindexed_commands_commit_identical_authority(self):
        control=Stage1Session(save_root=self.temp.name);control.world=deepcopy(self.session.world)
        request=ReviseQuarterlySlot(self.pid,1,self.sid,1,{'weekdays':[1,3]})
        expected=control.apply_quarterly_command(control.prepare_quarterly_command(request).prepared)
        actual=self.apply(request)
        self.assertEqual(actual,expected)
        self.assertEqual(encoded(self.session.world),encoded(control.world))

    def test_unrelated_owner_sources_do_not_stale_preparation(self):
        prepared=self.session.prepare_quarterly_command(self.request()).prepared
        other=next(owner for owner in self.state['airlines'] if owner!=self.owner)
        self.state['airlines'][other]['display_name']='Changed'
        self.session._mark_progress()  # Simulate a known other-owner notification.
        self.assertTrue(self.session.apply_quarterly_command(prepared).succeeded);self.assert_index()

    def test_assignment_delta_removes_old_and_adds_new_aircraft(self):
        row=self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        aircraft=self.session.purchase(self.session.preview_purchase('airbus-a320neo',row['origin_airport_id']))
        self.warm()
        self.apply(ReviseQuarterlySlot(self.pid,1,self.sid,1,{'planned_aircraft_id':aircraft}))
        index=self.session._quarterly_indexes.current
        self.assertEqual(index.ids('aircraft_plans',self.aid),())
        self.assertEqual(index.ids('aircraft_plans',aircraft),(self.pid,))

    def test_empty_new_game_initial_creation_maintains_complete_coverage(self):
        facts=self.facts()
        facts.update(connection_id=None,service_type='DEADHEAD',capacity=0,
                     fare_offer={'currency':'USD','amount_minor':0})
        self.session.new_game('New','New','MNL')
        # Same deterministic curated airport/aircraft IDs, fresh empty authority.
        ready=self.session.prepare_quarterly_command(CreateQuarterlyService('2027-Q1','DAB',facts))
        self.assertTrue(ready.succeeded,ready.issues)
        result=self.session.apply_quarterly_command(ready.prepared)
        self.assertTrue(result.succeeded,result.issues)
        self.assert_index()


if __name__=='__main__':unittest.main()
