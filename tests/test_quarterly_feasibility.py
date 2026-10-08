"""2C real timing/chronology, explicit lineage and rejection atomicity."""
from copy import deepcopy
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from tests import test_quarterly_foundation as foundation
from game.scheduling.quarterly_commands import (
    CreateQuarterlyService, ReviseQuarterlyFare, ReviseQuarterlySlot,
    AddQuarterlyFrequency, RemoveQuarterlySlots, ContinueQuarterlySlot,
    RetireQuarterlyService, ReplaceQuarterlyService)
from game.scheduling.quarterly_feasibility import certify_quarterly_feasibility, temporal_sources
from game.world_state.quarterly_construction import (
    create_weekly_plan, create_service, allocate_service_slot)
from game.world_state import validate_world
from game.utils.quarters import normal_target_quarter, parse_quarter_id


class QuarterlyFeasibilityTests(unittest.TestCase):
    setUpClass = classmethod(foundation.FoundationTests.setUpClass.__func__)
    slot = foundation.FoundationTests.slot

    def setUp(self):
        foundation.FoundationTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda: 0)
        self.session.world = self.world
        self.session.career_id = self.session.save_store.new_career_id()
        self.quarter = normal_target_quarter(self.world['simulation']['time_utc']).quarter_id

    def facts(self, **changes):
        row = self.slot('unused', 1)
        for key in ('service_id', 'slot_number', 'planning_timing'):
            del row[key]
        row.update(changes)
        return row

    def create(self):
        return self.apply(CreateQuarterlyService(self.quarter, 'DAB', self.facts()))

    def apply(self, request, *, success=True):
        prepared = self.session.prepare_quarterly_command(request)
        self.assertTrue(prepared.succeeded, prepared.issues)
        before = foundation.encoded(self.world)
        result = self.session.apply_quarterly_command(prepared.prepared)
        self.assertEqual(result.succeeded, success, result.issues)
        if not success:
            self.assertEqual(foundation.encoded(self.world), before)
        return result

    def revise(self, first, **changes):
        return ReviseQuarterlySlot(first.weekly_plan_id, first.revision, first.service_id, 1, changes)

    def test_real_planning_reposition_is_proof_only(self):
        old = deepcopy(self.world); first = self.create()
        self.assertEqual(first.revision, 1)
        for key in old['world_state']:
            if key not in {'services', 'service_numbering', 'weekly_plans'}:
                self.assertEqual(self.world['world_state'][key], old['world_state'][key])
        self.assertEqual(self.world['simulation'], old['simulation'])

    def test_overlap_rejects_and_does_not_allocate(self):
        first = self.create()
        bad = self.apply(CreateQuarterlyService(self.quarter, 'DAB', self.facts(), first.weekly_plan_id, 1), success=False)
        self.assertIn('AIRCRAFT_OVERLAP', bad.issues[0].message)

    def test_insufficient_positioning_rejects(self):
        first = self.create()
        bad = self.apply(AddQuarterlyFrequency(first.weekly_plan_id, 1, first.service_id,
                            self.facts(departure_local_time='11:00:00')), success=False)
        self.assertIn('REPOSITIONING_INFEASIBLE', bad.issues[0].message)

    def test_exact_reposition_readiness_boundary(self):
        first = self.create()
        self.apply(AddQuarterlyFrequency(first.weekly_plan_id, 1, first.service_id,
                    self.facts(departure_local_time='12:19:59')), success=False)
        second = self.apply(AddQuarterlyFrequency(first.weekly_plan_id, 1, first.service_id,
                    self.facts(departure_local_time='12:20:00')))
        self.assertEqual(second.slot_number, 2)
        self.assertEqual(second.read.plans[0].slots[1].flight_number, 'DAB01')

    def test_same_airport_turnaround(self):
        first = self.create()
        row = self.facts(origin_airport_id=self.dest, destination_airport_id=self.origin,
            connection_id=None, service_type='DEADHEAD', capacity=0,
            fare_offer={'currency':'USD', 'amount_minor':0}, departure_local_time='10:09:59')
        self.apply(CreateQuarterlyService(self.quarter, 'DAB', row, first.weekly_plan_id, 1), success=False)
        row['departure_local_time'] = '10:10:00'
        self.apply(CreateQuarterlyService(self.quarter, 'DAB', row, first.weekly_plan_id, 1))

    def test_weekly_wrap_is_checked(self):
        first = self.create()
        self.apply(AddQuarterlyFrequency(first.weekly_plan_id, 1, first.service_id,
                  self.facts(weekdays=[6], departure_local_time='23:00:00')))
        bad = self.apply(self.revise(replace(first, revision=2), departure_local_time='02:00:00'), success=False)
        self.assertIn('REPOSITIONING_INFEASIBLE', bad.issues[0].message)

    def test_adjacent_quarter_successor_is_checked(self):
        first = self.create(); state = self.world['world_state']
        sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        allocate_service_slot(self.world, sid)
        source = self.slot(sid, 1)
        source.update(weekdays=[3], departure_local_time='09:50:00')  # Apr 1 2027 after UTC boundary
        create_weekly_plan(self.world, self.owner, '2027-Q2', slots=[source])
        bad = self.apply(self.revise(first, weekdays=[3], departure_local_time='07:00:00'), success=False)
        self.assertIn('REPOSITIONING_INFEASIBLE', bad.issues[0].message)

    def test_prior_committed_quarter_is_checked(self):
        first = self.create()
        sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        allocate_service_slot(self.world, sid)
        row = self.slot(sid, 1, weekdays=[4], departure_local_time='07:00:00')
        pid = create_weekly_plan(self.world, self.owner, '2026-Q4', slots=[row])
        self.world['world_state']['weekly_plans'][pid]['revisions']['1']['published_at_utc'] = self.world['simulation']['time_utc']
        bad = self.apply(self.revise(first, weekdays=[4], departure_local_time='09:50:00'), success=False)
        self.assertIn('REPOSITIONING_INFEASIBLE', bad.issues[0].message)

    def test_changed_frequency_keeps_identity_and_cursors(self):
        first = self.create(); alloc = deepcopy(self.world['deterministic_state'])
        second = self.apply(self.revise(first, weekdays=[1, 3], departure_local_time='09:00:00'))
        self.assertEqual(second.service_id, first.service_id)
        self.assertEqual(second.read.plans[0].slots[0].flight_number, 'DAB01')
        self.assertEqual(self.world['deterministic_state'], alloc)
        self.assertEqual(first.read.plans[0].slots[0].facts['weekdays'], (0,))

    def test_endpoint_mutation_rejects_before_allocation(self):
        first = self.create(); before = foundation.encoded(self.world)
        bad = self.session.prepare_quarterly_command(self.revise(first, destination_airport_id=self.origin))
        self.assertEqual(bad.issues[0].code, 'ENDPOINT_REPLACEMENT_REQUIRED')
        self.assertEqual(foundation.encoded(self.world), before)

    def test_endpoint_replacement_allocates_distinct_service_and_retains_history(self):
        first = self.create()
        row = self.facts(origin_airport_id=self.dest, destination_airport_id=self.origin,
            connection_id=None, service_type='DEADHEAD', capacity=0, fare_offer={'currency':'USD','amount_minor':0})
        second = self.apply(ReplaceQuarterlyService(first.weekly_plan_id, 1, first.service_id, 'DAB', row))
        self.assertNotEqual(second.service_id, first.service_id)
        self.assertEqual(second.read.plans[0].slots[0].flight_number, 'DAB02')
        old = self.world['world_state']['weekly_plans'][first.weekly_plan_id]['revisions']['1']['slots'][0]
        self.assertEqual(old['origin_airport_id'], self.origin)
        self.assertIsNone(self.world['world_state']['services'][first.service_id]['retired_at_utc'])

    def test_plan_local_removal_does_not_retire_or_release_number(self):
        first = self.create()
        second = self.apply(RemoveQuarterlySlots(first.weekly_plan_id, 1, ((first.service_id, 1),)))
        self.assertEqual(second.read.plans[0].slots, ())
        self.assertIsNone(self.world['world_state']['services'][first.service_id]['retired_at_utc'])
        fresh = self.apply(CreateQuarterlyService(self.quarter, 'DAB', self.facts(), first.weekly_plan_id, 2))
        self.assertEqual(fresh.read.plans[0].slots[0].flight_number, 'DAB02')

    def test_retirement_rejects_live_draft_membership(self):
        first = self.create()
        bad = self.apply(RetireQuarterlyService(first.weekly_plan_id, 1, first.service_id), success=False)
        self.assertEqual(bad.issues[0].code, 'SERVICE_IN_USE')

    def test_retirement_after_removal_releases_number_without_erasing_history(self):
        first = self.create()
        self.apply(RemoveQuarterlySlots(first.weekly_plan_id, 1, ((first.service_id, 1),)))
        self.apply(RetireQuarterlyService(first.weekly_plan_id, 2, first.service_id))
        fresh = self.apply(CreateQuarterlyService(self.quarter, 'DAB', self.facts(), first.weekly_plan_id, 2))
        self.assertNotEqual(fresh.service_id, first.service_id)
        self.assertEqual(fresh.read.plans[0].slots[0].flight_number, 'DAB01')
        self.assertEqual(self.world['world_state']['weekly_plans'][first.weekly_plan_id]['revisions']['1']['slots'][0]['service_id'], first.service_id)

    def test_retirement_preserves_committed_use_and_number_protection(self):
        first = self.create(); source = self.slot(first.service_id, 1)
        pid = create_weekly_plan(self.world, self.owner, '2026-Q4', slots=[source])
        self.world['world_state']['weekly_plans'][pid]['revisions']['1']['published_at_utc'] = self.world['simulation']['time_utc']
        self.apply(RemoveQuarterlySlots(first.weekly_plan_id, 1, ((first.service_id, 1),)))
        committed = deepcopy(self.world['world_state']['weekly_plans'][pid])
        self.apply(RetireQuarterlyService(first.weekly_plan_id, 2, first.service_id))
        self.assertEqual(self.world['world_state']['weekly_plans'][pid], committed)
        new = self.apply(CreateQuarterlyService(self.quarter, 'DAB', self.facts(), first.weekly_plan_id, 2))
        self.assertEqual(new.read.plans[0].slots[0].flight_number, 'DAB02')

    def continuation(self):
        first = self.create(); source = self.slot(first.service_id, 1)
        pid = create_weekly_plan(self.world, self.owner, '2026-Q4', slots=[source])
        self.apply(RemoveQuarterlySlots(first.weekly_plan_id, 1, ((first.service_id, 1),)))
        return first, ContinueQuarterlySlot(first.weekly_plan_id, 2, pid, 1, 1, first.service_id, 1, {})

    def test_explicit_continuation_preserves_service_slot_number(self):
        first, request = self.continuation(); cursors = deepcopy(self.world['deterministic_state'])
        result = self.apply(request)
        self.assertEqual((result.service_id, result.slot_number), (first.service_id, 1))
        self.assertEqual(self.world['deterministic_state'], cursors)

    def test_continuation_can_create_explicitly_absent_destination(self):
        sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        allocate_service_slot(self.world, sid)
        pid = create_weekly_plan(self.world, self.owner, '2026-Q4', slots=[self.slot(sid, 1)])
        request = ContinueQuarterlySlot(None, 0, pid, 1, 1, sid, 1, {}, self.quarter)
        result = self.apply(request)
        self.assertEqual((result.service_id, result.slot_number, result.revision), (sid, 1, 1))
        self.assertEqual(self.world['world_state']['services'][sid]['next_slot_number'], 2)

    def test_continuation_stale_source_rejects(self):
        first, request = self.continuation()
        bad = self.session.prepare_quarterly_command(replace(request, source_expected_revision=2))
        self.assertEqual(bad.issues[0].code, 'STALE_REVISION')

    def test_continuation_dangling_source_rejects(self):
        first, request = self.continuation()
        self.assertFalse(self.session.prepare_quarterly_command(replace(request, slot_number=99)).succeeded)

    def test_removal_stale_revision_rejects(self):
        first = self.create()
        bad = self.session.prepare_quarterly_command(RemoveQuarterlySlots(first.weekly_plan_id, 2, ((first.service_id, 1),)))
        self.assertEqual(bad.issues[0].code, 'STALE_REVISION')

    def test_published_target_remains_locked(self):
        first = self.create()
        self.world['world_state']['weekly_plans'][first.weekly_plan_id]['revisions']['1']['published_at_utc'] = self.world['simulation']['time_utc']
        bad = self.session.prepare_quarterly_command(self.revise(first, weekdays=[1]))
        self.assertEqual(bad.issues[0].code, 'PUBLISHED_PLAN')

    def test_apply_rechecks_temporal_source_changes(self):
        first = self.create()
        prepared = self.session.prepare_quarterly_command(self.revise(first, weekdays=[1])).prepared
        row = self.slot(first.service_id, 1, weekdays=[3])
        create_weekly_plan(self.world, self.owner, '2027-Q2', slots=[row])
        before = foundation.encoded(self.world)
        bad = self.session.apply_quarterly_command(prepared)
        self.assertEqual(bad.issues[0].code, 'STALE_CONTEXT')
        self.assertEqual(foundation.encoded(self.world), before)

    def test_feasibility_failure_retry_matches_control(self):
        first = self.create(); request = self.revise(first, weekdays=[1]); prepared = self.session.prepare_quarterly_command(request).prepared
        control = Stage1Session(save_root=self.temp.name); control.world = deepcopy(self.world)
        expected = control.apply_quarterly_command(control.prepare_quarterly_command(request).prepared)
        before = foundation.encoded(self.world)
        with patch('game.scheduling.quarterly_commands.certify_quarterly_feasibility', side_effect=ValueError('injected')):
            self.assertFalse(self.session.apply_quarterly_command(prepared).succeeded)
        self.assertEqual(foundation.encoded(self.world), before)
        actual = self.session.apply_quarterly_command(prepared)
        self.assertEqual(actual, expected)
        self.assertEqual(foundation.encoded(self.world), foundation.encoded(control.world))

    def test_save_load_and_detached_reads_after_frequency_edit(self):
        first = self.create(); result = self.apply(self.revise(first, weekdays=[1, 3]))
        self.session.save_manual()
        before = foundation.encoded(self.world)
        self.session.load_saved(self.session.career_id)
        self.assertEqual(foundation.encoded(self.session.world), before)
        read = self.session.quarterly_plan_dependencies(result.weekly_plan_id, expected_revision=2)
        with self.assertRaises(TypeError):
            read.plans[0].slots[0].facts['weekdays'][0] = 0

    def test_new_frequency_endpoint_inconsistency_rejects(self):
        first = self.create()
        row = self.facts(origin_airport_id=self.dest, destination_airport_id=self.origin,
            connection_id=None, service_type='DEADHEAD', capacity=0, fare_offer={'currency':'USD','amount_minor':0})
        self.apply(AddQuarterlyFrequency(first.weekly_plan_id, 1, first.service_id, row), success=False)

    def test_actual_aircraft_status_restricts_future_assignment(self):
        first = self.create()
        # Direct pure proof must fail closed rather than invent availability for
        # an unavailable state. Trust-boundary state validation remains stronger.
        self.world['world_state']['aircraft'][self.aircraft]['status'] = 'UNAVAILABLE'
        with self.assertRaisesRegex(ValueError, 'AIRCRAFT_UNAVAILABLE'):
            certify_quarterly_feasibility(self.world, {self.aircraft})

    def test_temporal_observations_exclude_cold_quarters_and_finance(self):
        first = self.create()
        old = create_weekly_plan(self.world, self.owner, '2026-Q2', slots=[self.slot(first.service_id, 1)])
        facts = temporal_sources(self.world, {self.aircraft})
        self.assertNotIn(old, facts['plans'])
        self.assertNotIn('bookings', facts); self.assertNotIn('accounting', facts)

    def test_complete_world_stays_schema9(self):
        self.create()
        self.assertEqual(self.world['metadata']['save_schema_version'], 9)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_origin_local_date_collision_across_utc_quarters_rejects(self):
        first = self.create()
        row = self.slot(first.service_id, 1, weekdays=[3], departure_local_time='09:50:00')
        create_weekly_plan(self.world, self.owner, '2027-Q2', slots=[row])
        bad = self.apply(self.revise(first, weekdays=[3], departure_local_time='07:00:00'), success=False)
        self.assertIn('DUPLICATE_OCCURRENCE', bad.issues[0].message)

    def test_occurrence_collision_is_independent_of_aircraft(self):
        first = self.create()
        self.session.purchase(self.session.preview_purchase('airbus-a320neo', self.origin))
        self.world = self.session.world
        aid = next(a for a in self.world['world_state']['aircraft'] if a != self.aircraft)
        row = self.slot(first.service_id, 1, planned_aircraft_id=aid,
                        weekdays=[3], departure_local_time='09:50:00')
        create_weekly_plan(self.world, self.owner, '2027-Q2', slots=[row])
        bad = self.apply(self.revise(first, weekdays=[3], departure_local_time='07:00:00'), success=False)
        self.assertIn('DUPLICATE_OCCURRENCE', bad.issues[0].message)

    def test_nonexistent_dst_departure_rejects_atomically(self):
        self.world['world_state']['airports'][self.origin]['timezone'] = 'America/New_York'
        self.assertTrue(validate_world(self.world).is_valid)
        bad = self.apply(CreateQuarterlyService(self.quarter, 'DAB',
            self.facts(weekdays=[6], departure_local_time='02:30:00')), success=False)
        self.assertIn('does not exist', bad.issues[0].message.lower())

    def test_explicit_removal_of_retired_editable_reference_is_allowed(self):
        from game.world_state.quarterly_construction import retire_service
        first = self.create(); retire_service(self.world, first.service_id)
        self.apply(RemoveQuarterlySlots(first.weekly_plan_id, 1, ((first.service_id, 1),)))

    def test_legacy_continuous_commitments_project_beyond_90_days(self):
        from game.scheduling import WeeklyDraft
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)
        draft.add_weekdays(self.origin, self.dest, ['2026-09-07'], '08:00', return_flight=True)
        draft.save_current(self.world, continuous=True)
        before = foundation.encoded(self.world)
        prepared = self.session.prepare_quarterly_command(CreateQuarterlyService(self.quarter, 'DAB', self.facts()))
        self.assertTrue(prepared.succeeded, prepared.issues)
        bad = self.session.apply_quarterly_command(prepared.prepared)
        self.assertFalse(bad.succeeded)
        self.assertIn('AIRCRAFT_OVERLAP', bad.issues[0].message)
        self.assertEqual(foundation.encoded(self.world), before)

    def test_real_active_arrival_anchors_future_proof(self):
        from game.scheduling import WeeklyDraft
        from game.simulation import process_events_through
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)
        draft.add_weekdays(self.origin, self.dest, ['2026-09-01'], '09:00')
        draft.save_current(self.world)
        self.assertTrue(process_events_through(self.world, '2026-09-01T01:10:00Z').succeeded)
        self.create()

    def test_real_scalar_range_rejects_unsupported_new_route(self):
        self.session.purchase(self.session.preview_purchase('dhc-twin-otter-300-g', self.origin))
        aid = next(r['aircraft_id'] for r in self.session.fleet() if r['model_reference'] == 'dhc-twin-otter-300-g')
        self.world = self.session.world
        ports = {r['reference_code']: key for key, r in self.world['world_state']['airports'].items()}
        row = self.facts(planned_aircraft_id=aid, origin_airport_id=ports['BSO'],
            destination_airport_id=ports['TWT'], connection_id=None, service_type='DEADHEAD',
            capacity=0, fare_offer={'currency':'USD','amount_minor':0})
        bad = self.apply(CreateQuarterlyService(self.quarter, 'DAB', row), success=False)
        self.assertIn('AIRCRAFT_RANGE_EXCEEDED', bad.issues[0].message)

    def test_airport_profile_failure_has_no_allocations(self):
        from game.world_state.planning_reference import _PlanningReferences
        original = _PlanningReferences.__init__
        def missing_profile(reference):
            original(reference)
            reference.profile['airports'].clear()
        request = CreateQuarterlyService(self.quarter, 'DAB', self.facts())
        prepared = self.session.prepare_quarterly_command(request).prepared
        before = foundation.encoded(self.world)
        with patch.object(_PlanningReferences, '__init__', missing_profile):
            bad = self.session.apply_quarterly_command(prepared)
        self.assertFalse(bad.succeeded); self.assertIn('airport', bad.issues[0].message)
        self.assertEqual(foundation.encoded(self.world), before)

    def test_wrong_owner_assignment_rejects(self):
        from game.world_state.construction import add_airline, add_aircraft
        first = self.create()
        owner = add_airline(self.world, 'Other', base_airport_id=self.origin)
        aid = add_aircraft(self.world, owner, 'RP-OTHER', 'A320-200', home_airport_id=self.origin)
        before = foundation.encoded(self.world)
        bad = self.session.prepare_quarterly_command(self.revise(first, planned_aircraft_id=aid))
        self.assertEqual(bad.issues[0].code, 'OWNERSHIP_MISMATCH')
        self.assertEqual(foundation.encoded(self.world), before)

    def test_unrelated_aircraft_is_not_in_temporal_proof(self):
        first = self.create()
        self.session.purchase(self.session.preview_purchase('airbus-a320neo', self.origin))
        self.world = self.session.world
        calls = []
        from game.scheduling import quarterly_commands as commands
        original = commands.certify_quarterly_feasibility
        def scoped(world, aircraft_ids, **kwargs):
            calls.append(aircraft_ids)
            return original(world, aircraft_ids, **kwargs)
        with patch.object(commands, 'certify_quarterly_feasibility', side_effect=scoped):
            self.apply(self.revise(first, weekdays=[1]))
        self.assertEqual(calls, [{self.aircraft}])

    def test_old_and_new_aircraft_both_are_certified(self):
        first = self.create()
        self.session.purchase(self.session.preview_purchase('airbus-a320neo', self.origin))
        self.world = self.session.world
        aid = next(a for a in self.world['world_state']['aircraft'] if a != self.aircraft)
        calls = []
        from game.scheduling import quarterly_commands as commands
        original = commands.certify_quarterly_feasibility
        def scoped(world, aircraft_ids, **kwargs):
            calls.append(aircraft_ids)
            return original(world, aircraft_ids, **kwargs)
        with patch.object(commands, 'certify_quarterly_feasibility', side_effect=scoped):
            self.apply(self.revise(first, planned_aircraft_id=aid))
        self.assertEqual(calls, [{self.aircraft, aid}])


if __name__ == '__main__':
    unittest.main()
