"""Dormant 2B ownership, rejection atomicity and prepared-command isolation."""
from copy import deepcopy
from dataclasses import replace, FrozenInstanceError
import json
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from tests import test_quarterly_foundation as foundation
from game.scheduling.quarterly_commands import CreateQuarterlyService, ReviseQuarterlyFare
from game.world_state.quarterly_construction import retire_service, create_weekly_plan
from game.world_state.construction import add_airline, add_aircraft
from game.utils.quarters import normal_target_quarter
from game.world_state import validate_world


class QuarterlyCommandTests(unittest.TestCase):
    setUpClass = classmethod(foundation.FoundationTests.setUpClass.__func__)
    slot = foundation.FoundationTests.slot

    def setUp(self):
        foundation.FoundationTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda:0)
        self.session.world = self.world
        self.session.career_id = self.session.save_store.new_career_id()
        self.quarter = normal_target_quarter(self.world['simulation']['time_utc']).quarter_id

    def request(self, *, pid=None, revision=0, **changes):
        row = self.slot('unused',1)
        for key in ('service_id','slot_number','planning_timing'):del row[key]
        row.update(changes)
        return CreateQuarterlyService(self.quarter,'DAB',row,pid,revision)

    def prepare(self, request=None):
        result=self.session.prepare_quarterly_command(request or self.request())
        self.assertTrue(result.succeeded,result.issues)
        return result.prepared

    def create(self, request=None):
        result=self.session.apply_quarterly_command(self.prepare(request))
        self.assertTrue(result.succeeded,result.issues)
        return result

    def bytes(self):return foundation.encoded(self.world)

    def test_create_bundles_service_slot_plan_and_leaves_operational_roots_unchanged(self):
        old=deepcopy(self.world);result=self.create()
        self.assertEqual(result.revision,1);self.assertEqual(result.slot_number,1)
        self.assertEqual(result.read.plans[0].slots[0].flight_number,'DAB01')
        for root in ('metadata','simulation','ui_state'):self.assertEqual(self.world[root],old[root])
        for key in old['world_state']:
            if key not in ('services','service_numbering','weekly_plans'):
                self.assertEqual(self.world['world_state'][key],old['world_state'][key])
        self.assertTrue(validate_world(self.world).is_valid)
        self.assertTrue(self.session.unsaved_progress)

    def test_create_appends_existing_plan_without_overwriting_old_revision(self):
        first=self.create();history=deepcopy(self.world['world_state']['weekly_plans'][first.weekly_plan_id]['revisions']['1'])
        second=self.create(self.request(pid=first.weekly_plan_id,revision=1))
        self.assertEqual(second.revision,2);self.assertNotEqual(first.service_id,second.service_id)
        self.assertEqual(len(second.read.plans[0].slots),2)
        self.assertEqual(self.world['world_state']['weekly_plans'][first.weekly_plan_id]['revisions']['1'],history)

    def fare(self, result, amount=20000, revision=None):
        return ReviseQuarterlyFare(result.weekly_plan_id, revision or result.revision,
            result.service_id,result.slot_number,{'currency':'USD','amount_minor':amount})

    def test_fare_revision_preserves_service_number_endpoints_and_all_cursors(self):
        first=self.create();cursors=deepcopy(self.world['deterministic_state'])
        services=deepcopy(self.world['world_state']['services'])
        result=self.create_command(self.fare(first))
        self.assertEqual(result.revision,2);self.assertEqual(result.service_id,first.service_id)
        self.assertEqual(self.world['deterministic_state'],cursors)
        self.assertEqual(self.world['world_state']['services'],services)
        self.assertEqual(result.read.plans[0].slots[0].facts['fare_offer']['amount_minor'],20000)
        self.assertEqual(first.read.plans[0].slots[0].facts['fare_offer']['amount_minor'],10000)

    def create_command(self, request):
        return self.session.apply_quarterly_command(self.prepare(request))

    def test_prepare_is_read_only_and_input_is_detached(self):
        request=self.request();before=self.bytes();prepared=self.prepare(request)
        self.assertEqual(self.bytes(),before)
        request.slot['fare_offer']['amount_minor']=999
        request.slot['weekdays'].append(3)
        result=self.session.apply_quarterly_command(prepared)
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(result.read.plans[0].slots[0].facts['fare_offer']['amount_minor'],10000)
        self.assertEqual(result.read.plans[0].slots[0].facts['weekdays'],(0,))

    def test_response_and_context_nested_values_are_immutable(self):
        prepared=self.prepare()
        with self.assertRaises(TypeError):prepared.intent['slot']['fare_offer']['amount_minor']=0
        with self.assertRaises(FrozenInstanceError):prepared.airline_id='other'
        result=self.session.apply_quarterly_command(prepared);before=self.bytes()
        with self.assertRaises(TypeError):result.read.plans[0].slots[0].facts['weekdays'][0]=1
        self.assertEqual(self.bytes(),before)

    def test_forged_or_other_session_preparation_rejects(self):
        prepared=self.prepare();before=self.bytes()
        forged=replace(prepared,airline_id=self.owner)
        self.assertFalse(self.session.apply_quarterly_command(forged).succeeded)
        other=Stage1Session(save_root=self.temp.name);other.world=deepcopy(self.world)
        self.assertFalse(other.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)

    def test_same_bytes_rebind_and_load_invalidate_preparation(self):
        prepared=self.prepare();self.session.world=deepcopy(self.world)
        self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        prepared=self.prepare();self.session.save_manual()
        self.session.load_saved(self.session.career_id)
        self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')

    def test_stale_revision_and_absence_expectation_reject_without_changes(self):
        a=self.prepare();b=self.prepare();first=self.session.apply_quarterly_command(a)
        before=self.bytes();bad=self.session.apply_quarterly_command(b)
        self.assertEqual(bad.issues[0].code,'STALE_REVISION');self.assertEqual(self.bytes(),before)
        old=self.prepare(self.fare(first));self.create_command(self.fare(first,30000))
        before=self.bytes();bad=self.session.apply_quarterly_command(old)
        self.assertEqual(bad.issues[0].code,'STALE_REVISION')
        self.assertEqual(bad.issues[0].observed_revision,2);self.assertEqual(self.bytes(),before)

    def test_retirement_dependency_and_clock_changes_stale_context(self):
        first=self.create();prepared=self.prepare(self.fare(first))
        retire_service(self.world,first.service_id);before=self.bytes()
        self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'RETIRED_SERVICE')
        self.assertEqual(self.bytes(),before)
        prepared=self.prepare(self.request(pid=first.weekly_plan_id,revision=1))
        self.world['simulation']['time_utc']='2026-09-01T00:00:01Z';before=self.bytes()
        self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        self.assertEqual(self.bytes(),before)

    def test_dependency_change_rejects_but_unrelated_display_change_does_not(self):
        prepared=self.prepare();self.world['world_state']['aircraft'][self.aircraft]['registration']='RP-CHANGED'
        before=self.bytes();self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        self.assertEqual(self.bytes(),before)
        prepared=self.prepare();self.world['ui_state']['filters']['unrelated']='kept'
        result=self.session.apply_quarterly_command(prepared)
        self.assertTrue(result.succeeded,result.issues);self.assertEqual(self.world['ui_state']['filters']['unrelated'],'kept')

    def test_wrong_owner_plan_service_aircraft_and_connection_reject(self):
        first=self.create()
        owner=add_airline(self.world,'Other',base_airport_id=self.origin)
        pid=create_weekly_plan(self.world,owner,self.quarter)
        cases=[self.request(pid=pid,revision=1)]
        aircraft=self.world['world_state']['aircraft'][self.aircraft]
        aircraft['airline_id']=owner
        before=self.bytes();bad=self.session.prepare_quarterly_command(self.request())
        self.assertFalse(bad.succeeded);self.assertEqual(self.bytes(),before)
        aircraft['airline_id']=self.owner
        for request in cases:
            before=self.bytes();bad=self.session.prepare_quarterly_command(request)
            self.assertEqual(bad.issues[0].code,'OWNERSHIP_MISMATCH');self.assertEqual(self.bytes(),before)

    def test_missing_plan_service_slot_and_malformed_ids_reject(self):
        first=self.create()
        for request in (self.request(pid='weekly_plan-999999999999',revision=1),
                replace(self.fare(first),service_id='service-999999999999'),
                replace(self.fare(first),slot_number=99),self.request(planned_aircraft_id='display-label')):
            before=self.bytes();bad=self.session.prepare_quarterly_command(request)
            self.assertFalse(bad.succeeded);self.assertEqual(self.bytes(),before)

    def test_endpoint_and_identity_fields_cannot_enter_revision_api(self):
        first=self.create();before=self.bytes()
        request={'weekly_plan_id':first.weekly_plan_id,'origin_airport_id':self.dest}
        self.assertEqual(self.session.prepare_quarterly_command(request).issues[0].code,'INVALID_REQUEST')
        self.assertEqual(self.bytes(),before)
        self.assertFalse(self.session.prepare_quarterly_command(self.request(service_id=first.service_id)).succeeded)

    def test_published_and_wrong_quarter_targets_reject(self):
        first=self.create();plan=self.world['world_state']['weekly_plans'][first.weekly_plan_id]
        plan['revisions']['1']['published_at_utc']=self.world['simulation']['time_utc']
        before=self.bytes();self.assertEqual(self.session.prepare_quarterly_command(self.fare(first)).issues[0].code,'PUBLISHED_PLAN')
        self.assertEqual(self.bytes(),before)
        bad=self.session.prepare_quarterly_command(replace(self.request(),quarter_id='2026-Q3'))
        self.assertEqual(bad.issues[0].code,'CLOSED_TARGET')

    def test_schema9_reuse_and_draft_reservation_keep_high_water(self):
        first=self.create();retire_service(self.world,first.service_id)
        # Existing editable membership of retired service needs 2C removal first.
        plan=self.world['world_state']['weekly_plans'][first.weekly_plan_id]
        from game.world_state.quarterly_construction import append_weekly_plan_revision
        append_weekly_plan_revision(self.world,first.weekly_plan_id,expected_revision=1,slots=[])
        second=self.create(self.request(pid=first.weekly_plan_id,revision=2))
        third=self.create(self.request(pid=first.weekly_plan_id,revision=3))
        self.assertNotEqual(first.service_id,second.service_id)
        self.assertEqual(second.read.plans[0].slots[0].flight_number,'DAB01')
        self.assertEqual(third.read.plans[0].slots[1].flight_number,'DAB02')
        self.assertEqual(self.world['world_state']['service_numbering'][self.owner]['next_number'],3)

    def test_failed_creation_after_each_staging_boundary_has_no_effect_and_retry_matches_control(self):
        from game.scheduling import quarterly_commands as commands
        for name in ('allocate_service_slot','planning_snapshot','create_weekly_plan'):
            with self.subTest(boundary=name):
                before=self.bytes();prepared=self.prepare()
                with patch.object(commands,name,side_effect=ValueError('injected')):
                    bad=self.session.apply_quarterly_command(prepared)
                self.assertFalse(bad.succeeded);self.assertEqual(self.bytes(),before)
        before=self.bytes();prepared=self.prepare()
        with patch.object(commands,'_entry',side_effect=[None,ValueError('candidate gate')]):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)
        control=Stage1Session(save_root=self.temp.name);control.world=json.loads(before)
        expected=control.apply_quarterly_command(control.prepare_quarterly_command(self.request()).prepared)
        actual=self.session.apply_quarterly_command(prepared)
        self.assertEqual(actual,expected);self.assertEqual(foundation.encoded(control.world),self.bytes())

    def test_late_gate_revision_staging_and_final_freshness_rejection_are_atomic(self):
        from game.scheduling import quarterly_commands as commands
        first=self.create();prepared=self.prepare(self.fare(first));before=self.bytes()
        for name in ('append_weekly_plan_revision','resolve_quarterly_reads'):
            with self.subTest(boundary=name),patch.object(commands,name,side_effect=ValueError('injected')):
                self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
            self.assertEqual(self.bytes(),before)
        with patch.object(commands,'_entry',side_effect=[None,None,ValueError('detached gate')]):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)
        original=commands._sources;calls=[]
        def changed(*args):
            calls.append(1);return original(*args) if len(calls)==1 else {}
        with patch.object(commands,'_sources',side_effect=changed):
            self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        self.assertEqual(self.bytes(),before)

    def test_invalid_fare_rejects_after_staging_without_consumption(self):
        prepared=self.prepare(self.request(fare_offer={'currency':'USD','amount_minor':-1}))
        before=self.bytes();self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)

    def test_no_active_or_running_or_bulk_session_command(self):
        empty=Stage1Session(save_root=self.temp.name)
        self.assertFalse(empty.prepare_quarterly_command(self.request()).succeeded)
        prepared=self.prepare();self.session._bulk_work=object();before=self.bytes()
        self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'COMMAND_BOUNDARY')
        self.assertEqual(self.bytes(),before);self.session._bulk_work=None
        self.session.resume();before=self.bytes()
        self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'COMMAND_BOUNDARY')
        self.assertEqual(self.bytes(),before)

    def test_save_load_preserves_exact_world_and_equivalent_new_preparation(self):
        first=self.create();self.create_command(self.fare(first));before=self.bytes()
        self.session.save_manual();self.session.load_saved(self.session.career_id)
        self.assertEqual(foundation.encoded(self.session.world),before)
        self.assertTrue(self.session.prepare_quarterly_command(self.fare(first,revision=2)).succeeded)

    def test_stale_non_revision_dependency_is_not_hidden_by_matching_plan_pointer(self):
        first=self.create();prepared=self.prepare(self.fare(first))
        self.world['world_state']['connections'][self.connection]['schedule_display_name']='new'
        # Accepted display metadata still invalidates the observed connection.
        before=self.bytes();self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        self.assertEqual(self.bytes(),before)

    def test_successful_preparation_cannot_be_replayed(self):
        prepared=self.prepare();self.assertTrue(self.session.apply_quarterly_command(prepared).succeeded)
        before=self.bytes();self.assertEqual(self.session.apply_quarterly_command(prepared).issues[0].code,'STALE_CONTEXT')
        self.assertEqual(self.bytes(),before)

    def test_valid_foreign_aircraft_connection_and_service_owners_reject_explicitly(self):
        first=self.create()
        owner=add_airline(self.world,'Foreign',base_airport_id=self.origin)
        aircraft=add_aircraft(self.world,owner,'RP-OTHER','A320-200',home_airport_id=self.origin)
        from game.scheduling.rotation import _connection
        connection=_connection(self.world,owner,self.origin,self.dest)
        from game.world_state.quarterly_construction import create_service
        service=create_service(self.world,owner,flight_number_prefix='OTH')
        self.assertTrue(validate_world(self.world).is_valid)
        for request in (self.request(pid=first.weekly_plan_id,revision=1,planned_aircraft_id=aircraft),
                        self.request(pid=first.weekly_plan_id,revision=1,connection_id=connection),replace(self.fare(first),service_id=service)):
            before=self.bytes();bad=self.session.prepare_quarterly_command(request)
            self.assertEqual(bad.issues[0].code,'OWNERSHIP_MISMATCH');self.assertEqual(self.bytes(),before)

    def test_unrelated_airline_allocation_does_not_stale_owned_command(self):
        prepared=self.prepare()
        owner=add_airline(self.world,'Foreign',base_airport_id=self.origin)
        from game.world_state.quarterly_construction import create_service
        create_service(self.world,owner,flight_number_prefix='OTH')
        result=self.session.apply_quarterly_command(prepared)
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(result.read.plans[0].slots[0].flight_number,'DAB01')

    def test_final_response_failure_and_post_revision_failure_do_not_publish(self):
        from game.scheduling import quarterly_commands as commands
        first=self.create();prepared=self.prepare(self.fare(first));before=self.bytes()
        original=commands.append_weekly_plan_revision
        def staged(*args,**kwargs):
            original(*args,**kwargs);raise ValueError('after revision staging')
        with patch.object(commands,'append_weekly_plan_revision',side_effect=staged):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)
        original_read=commands.resolve_quarterly_reads;calls=[]
        def failed(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise ValueError('response construction')
            return original_read(*args,**kwargs)
        with patch.object(commands,'resolve_quarterly_reads',side_effect=failed):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)

    def test_malformed_foreign_world_boundary_rejects_without_exception(self):
        self.session.world={};before=deepcopy(self.session.world)
        self.assertEqual(self.session.prepare_quarterly_command(self.request()).issues[0].code,'INVALID_WORLD')
        self.assertEqual(self.session.world,before)

    def test_malformed_metadata_and_wrong_schema_reject_cleanly(self):
        for metadata in (None, [], {'save_schema_version':8}):
            world=deepcopy(self.world);world['metadata']=metadata
            self.session.world=world;before=foundation.encoded(world)
            self.assertEqual(self.session.prepare_quarterly_command(self.request()).issues[0].code,'INVALID_SCHEMA')
            self.assertEqual(foundation.encoded(world),before)

    def test_committed_future_use_prevents_number_reuse_and_target_query_does_not_publish(self):
        first=self.create();retire_service(self.world,first.service_id)
        plan=self.world['world_state']['weekly_plans'][first.weekly_plan_id]
        plan['revisions']['1']['published_at_utc']=self.world['simulation']['time_utc']
        from game.utils.quarters import parse_quarter_id
        request=replace(self.request(),quarter_id=parse_quarter_id(self.quarter).shift().quarter_id)
        before=deepcopy(self.world['simulation']);result=self.create(request)
        self.assertEqual(result.read.plans[0].slots[0].flight_number,'DAB02')
        self.assertIsNone(result.read.plans[0].published_at_utc)
        self.assertEqual(self.world['simulation'],before)

    def test_failed_fare_revision_retry_matches_uninterrupted_control(self):
        from game.scheduling import quarterly_commands as commands
        first=self.create();request=self.fare(first);prepared=self.prepare(request)
        control=Stage1Session(save_root=self.temp.name);control.world=deepcopy(self.world)
        expected=control.apply_quarterly_command(control.prepare_quarterly_command(request).prepared)
        before=self.bytes()
        with patch.object(commands,'append_weekly_plan_revision',side_effect=ValueError('injected')):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(self.bytes(),before)
        actual=self.session.apply_quarterly_command(prepared)
        self.assertEqual(actual,expected);self.assertEqual(self.bytes(),foundation.encoded(control.world))

    def test_freshness_observation_does_not_copy_retained_plan_revisions(self):
        first=self.create();second=self.create_command(self.fare(first))
        prepared=self.prepare(self.fare(second))
        observed=prepared.sources['records']['weekly_plans/'+first.weekly_plan_id]
        self.assertEqual(tuple(observed['revisions']),('2',))
        self.assertEqual(len(self.world['world_state']['weekly_plans'][first.weekly_plan_id]['revisions']),2)

    def test_unexpected_staging_exception_still_does_not_touch_authority(self):
        from game.scheduling import quarterly_commands as commands
        prepared=self.prepare();before=self.bytes()
        with patch.object(commands,'planning_snapshot',side_effect=RuntimeError('unexpected defect')):
            with self.assertRaises(RuntimeError):self.session.apply_quarterly_command(prepared)
        self.assertEqual(self.bytes(),before)
