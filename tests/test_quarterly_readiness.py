"""Stage 3A diagnostic snapshots; independent calendar and literal travel cases."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.scheduling.quarterly_readiness import (
    PublicationReadinessRequest, inspect_quarterly_publication_readiness,
)
from game.scheduling.quarterly_indexes import QuarterlyDependencyIndex
from game.scheduling.quarterly_commands import _plain
from game.scheduling.rotation import _connection
from game.scheduling import WeeklyDraft
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.quarterly_construction import (
    create_service, allocate_service_slot, create_weekly_plan,
)
from tests.profile_quarterly_dependencies import fixture
from tests import test_quarterly_foundation as foundation

encoded = foundation.encoded


class PublicationReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.owner, cls.aid, cls.pid, cls.sid = fixture(1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.world = deepcopy(self.base)

    def inspect(self, world=None, pid=None, revision=1, **kwargs):
        world = self.world if world is None else world
        before = encoded(world)
        result = inspect_quarterly_publication_readiness(world, airline_id=self.owner,
            request=PublicationReadinessRequest(self.pid if pid is None else pid, revision, **kwargs))
        self.assertEqual(encoded(world), before)
        self.assertTrue(result.succeeded, result.issues)
        return result

    def session(self, world=None):
        session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda: 0)
        session.world = deepcopy(self.world if world is None else world)
        session.career_id = session.save_store.new_career_id()
        session.save_manual(); session.load_saved(session.career_id)
        return session

    def at(self, time, quarter=None):
        # Bootstrap a genuinely validated world at this date. Do not move the
        # clock past pending Booking events or weaken their successor witnesses.
        scenario = json.loads(Path('Data/Stage1/philippines_v1.json').read_text(encoding='utf-8'))
        scenario['start_time_utc'] = time
        path = Path(self.temp.name) / 'scenario.json'
        path.write_text(json.dumps(scenario), encoding='utf-8')
        world = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='A', airline_display_name='Dabudhi', base_airport_reference_code='MNL',
            reference_path=path)
        f = foundation.FoundationTests()
        f.world = world; f.state = world['world_state']; f.owner = self.owner
        f.aircraft = next(iter(f.state['aircraft']))
        f.origin = f.state['aircraft'][f.aircraft]['current_airport_id']
        f.dest = next(k for k, row in f.state['airports'].items() if row['reference_code'] == 'DVO')
        f.connection = _connection(world, self.owner, f.origin, f.dest)
        pid = None
        if quarter is not None:
            sid = create_service(world, self.owner, flight_number_prefix='DAB')
            allocate_service_slot(world, sid)
            pid = create_weekly_plan(world, self.owner, quarter, slots=[f.slot(sid, 1)])
        valid = validate_world(world)
        self.assertTrue(valid.is_valid, valid.errors[:2])
        return world, pid, f

    def closed_pattern(self, world=None, pid=None, **changes):
        world = self.world if world is None else world
        pid = self.pid if pid is None else pid
        state = world['world_state']
        row = deepcopy(state['weekly_plans'][pid]['revisions']['1']['slots'][0])
        sid = create_service(world, self.owner, flight_number_prefix='DAB')
        allocate_service_slot(world, sid)
        row.update(service_id=sid, origin_airport_id=row['destination_airport_id'],
            destination_airport_id=row['origin_airport_id'], connection_id=None,
            service_type='DEADHEAD', capacity=0, fare_offer={'currency': 'USD', 'amount_minor': 0},
            departure_local_time='10:10:00')
        row.update(changes)
        from game.world_state.planning_reference import planning_snapshot
        row['planning_timing'] = planning_snapshot(state, row['planned_aircraft_id'],
            row['origin_airport_id'], row['destination_airport_id'])
        state['weekly_plans'][pid]['revisions']['1']['slots'].append(row)
        self.assertTrue(validate_world(world).is_valid)
        return row

    def test_hypothetical_plan_is_feasible_eligible_but_not_executable(self):
        result = self.inspect()
        self.assertTrue(result.publication_eligible)
        self.assertTrue(result.manual_eligible)
        self.assertTrue(result.planning_feasible)
        self.assertFalse(result.execution_ready)
        self.assertTrue(result.execution_blockers)
        self.assertTrue(all(issue.code == 'UNRESOLVED_POSITIONING' for issue in result.execution_blockers))

    def test_explicit_quarterly_deadhead_closes_literal_chain(self):
        self.closed_pattern()
        result = self.inspect()
        self.assertTrue(result.planning_feasible)
        self.assertTrue(result.execution_ready)
        self.assertFalse(result.execution_blockers)

    def test_explicit_legacy_deadhead_anchors_initial_location(self):
        world, pid, f = self.at('2026-12-01T00:00:00Z', '2027-Q1')
        row = world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'][0]
        row.update(origin_airport_id=f.dest, destination_airport_id=f.origin,
                   connection_id=None, service_type='DEADHEAD', capacity=0,
                   fare_offer={'currency': 'USD', 'amount_minor': 0})
        from game.world_state.planning_reference import planning_snapshot
        row['planning_timing'] = planning_snapshot(world['world_state'], f.aircraft, f.dest, f.origin)
        self.closed_pattern(world, pid)
        draft = WeeklyDraft(world, airline_id=self.owner, aircraft_id=f.aircraft)
        draft.add(f.origin, f.dest, departure_utc='2026-12-31T01:00:00Z', deadhead=True)
        draft.save_current(world)
        result = self.inspect(world, pid)
        self.assertTrue(result.planning_feasible, result.planning_issues)
        self.assertTrue(result.execution_ready, result.execution_blockers)
        from game.scheduling.quarterly_feasibility import certify_quarterly_feasibility
        certify_quarterly_feasibility(world, {f.aircraft})

    def test_missing_plan_has_calendar_but_no_feasibility_assertion(self):
        world, _, _ = self.at('2027-01-01T00:00:00Z')
        before = encoded(world)
        result = inspect_quarterly_publication_readiness(world, airline_id=self.owner)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.quarter_id, '2027-Q2')
        self.assertIsNone(result.weekly_plan_id)
        self.assertIsNone(result.baseline)
        self.assertIsNone(result.planning_feasible)
        self.assertIsNone(result.execution_ready)
        self.assertFalse(result.publication_eligible)
        self.assertEqual(result.eligibility_issues[0].code, 'MISSING_PLAN')
        self.assertEqual(encoded(world), before)

    def test_empty_existing_plan_is_vacuously_feasible_without_supply(self):
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'] = []
        result = self.inspect()
        self.assertTrue(result.planning_feasible)
        self.assertTrue(result.execution_ready)
        self.assertEqual(result.plan.slots, ())

    def test_month_three_initial_target_is_after_next(self):
        result = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner)
        self.assertEqual(result.target_quarter_id, '2027-Q1')
        self.assertEqual(result.operating_start_utc, '2027-01-01T00:00:00Z')
        self.assertEqual(result.automatic_publication_utc, '2026-12-01T00:00:00Z')
        self.assertEqual(result.next_publication_boundary_utc, '2026-12-01T00:00:00Z')

    def test_exact_utc_second_and_manual_automatic_distinction(self):
        for time, manual, automatic in (
                ('2028-02-29T23:59:59Z', True, False),
                ('2028-03-01T00:00:00Z', False, True),
                ('2028-03-01T00:00:01Z', False, False)):
            with self.subTest(time=time):
                world, pid, _ = self.at(time, '2028-Q2')
                result = self.inspect(world, pid)
                self.assertEqual(result.manual_eligible, manual)
                self.assertEqual(result.automatic_due, automatic)
                self.assertEqual(result.publication_eligible, manual or automatic)
                self.assertEqual(result.automatic_publication_utc, '2028-03-01T00:00:00Z')

    def test_airport_timezone_does_not_change_utc_calendar(self):
        world, pid, f = self.at('2027-03-01T00:00:00Z', '2027-Q2')
        world['world_state']['airports'][f.origin]['timezone'] = 'America/Los_Angeles'
        result = self.inspect(world, pid)
        self.assertTrue(result.automatic_due)
        self.assertEqual(result.target_quarter_id, '2027-Q3')

    def test_skip_commitments_uses_latest_preceding_published_baseline(self):
        world, q2, f = self.at('2027-01-15T00:00:00Z', '2027-Q2')
        rows = deepcopy(world['world_state']['weekly_plans'][q2]['revisions']['1']['slots'])
        q1 = create_weekly_plan(world, self.owner, '2027-Q1', slots=deepcopy(rows))
        q3 = create_weekly_plan(world, self.owner, '2027-Q3', slots=deepcopy(rows))
        for pid in (q1, q2):
            world['world_state']['weekly_plans'][pid]['revisions']['1']['published_at_utc'] = '2027-01-01T00:00:00Z'
        result = inspect_quarterly_publication_readiness(world, airline_id=self.owner)
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual(result.weekly_plan_id, q3)
        self.assertEqual(result.baseline.weekly_plan_id, q2)
        self.assertEqual(result.next_publication_boundary_utc, '2027-06-01T00:00:00Z')
        self.assertEqual(result.baseline.slots[0].service_id, rows[0]['service_id'])
        world['world_state']['weekly_plans'][q3]['revisions']['1']['published_at_utc'] = '2027-01-15T00:00:00Z'
        result = inspect_quarterly_publication_readiness(world, airline_id=self.owner)
        self.assertEqual(result.quarter_id, '2027-Q4')
        self.assertEqual(result.baseline.weekly_plan_id, q3)

    def test_published_selection_is_observational_only(self):
        self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['published_at_utc'] = self.world['simulation']['time_utc']
        result = self.inspect()
        self.assertFalse(result.publication_eligible)
        self.assertFalse(result.automatic_due)
        self.assertEqual(result.eligibility_issues[0].code, 'PUBLISHED_PLAN')

    def test_wrong_owner_and_stale_revision_reject_without_partial_results(self):
        foreign = next(pid for pid, p in self.world['world_state']['weekly_plans'].items() if p['airline_id'] != self.owner)
        for request, code in ((PublicationReadinessRequest(foreign, 1), 'OWNERSHIP_MISMATCH'),
                              (PublicationReadinessRequest(self.pid, 99), 'STALE_REVISION'),
                              (PublicationReadinessRequest(self.pid, True), 'INVALID_REQUEST')):
            before = encoded(self.world)
            result = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner, request=request)
            self.assertFalse(result.succeeded)
            self.assertEqual(result.issues[0].code, code)
            self.assertIsNone(result.plan)
            self.assertEqual(encoded(self.world), before)

    def test_schema_9_and_canonical_utc_are_required(self):
        for field, value in (('save_schema_version', 8), ('time_utc', '2026-09-01T00:00:00.1Z')):
            world = deepcopy(self.world)
            world['metadata' if field == 'save_schema_version' else 'simulation'][field] = value
            before = encoded(world)
            result = inspect_quarterly_publication_readiness(world, airline_id=self.owner)
            self.assertFalse(result.succeeded)
            self.assertEqual(encoded(world), before)

    def test_expected_utc_and_source_changes_are_stale(self):
        initial = self.inspect()
        for time in ('2026-09-01T00:00:01Z', '2026-09-01T00:00:00Z'):
            self.world['simulation']['time_utc'] = time
            if time.endswith('00Z'):
                self.world['world_state']['aircraft'][self.aid]['current_airport_id'] = initial.plan.slots[0].facts['destination_airport_id']
            result = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner,
                request=PublicationReadinessRequest(self.pid, 1, expected_sources=initial.sources))
            self.assertEqual(result.issues[0].code, 'STALE_CONTEXT')
        result = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner,
            request=PublicationReadinessRequest(self.pid, 1, expected_time_utc='2026-09-02T00:00:00Z'))
        self.assertEqual(result.issues[0].code, 'STALE_CONTEXT')

    def test_session_previous_result_is_revoked_on_load_rebind_and_forgery(self):
        for mode in ('load', 'rebind', 'forged'):
            with self.subTest(mode=mode):
                session = self.session()
                previous = session.quarterly_publication_readiness(self.pid, expected_revision=1)
                self.assertTrue(previous.succeeded, previous.issues)
                if mode == 'load': session.load_saved(session.career_id)
                elif mode == 'rebind': session.world = deepcopy(session.world)
                else: previous = replace(previous)
                before = encoded(session.world)
                result = session.quarterly_publication_readiness(self.pid, expected_revision=1, previous=previous)
                self.assertEqual(result.issues[0].code, 'STALE_CONTEXT')
                self.assertEqual(encoded(session.world), before)
                self.assertTrue(session.quarterly_publication_readiness(self.pid, expected_revision=1).succeeded)

    def test_nested_input_and_result_are_detached_immutable(self):
        first = self.inspect()
        expected = _plain(first.sources)
        result = self.inspect(expected_sources=expected)
        expected['temporal']['aircraft'][self.aid]['current_airport_id'] = 'changed'
        self.assertEqual(result.sources, first.sources)
        with self.assertRaises(FrozenInstanceError): result.execution_ready = True
        with self.assertRaises(TypeError): result.sources['temporal']['aircraft'][self.aid]['status'] = 'PARKED'
        with self.assertRaises(TypeError): result.plan.slots[0].facts['fare_offer']['amount_minor'] = 1
        with self.assertRaises(FrozenInstanceError): result.execution_blockers[0].code = 'READY'

    def test_indexed_reference_and_cold_rebuild_have_identical_results(self):
        session = self.session()
        before = encoded(session.world)
        result = session.quarterly_publication_readiness(self.pid, expected_revision=1)
        index = session._quarterly_indexes.current
        reference = self.inspect(session.world)
        self.assertEqual(result, reference)
        repeated = session.quarterly_publication_readiness(self.pid, expected_revision=1, previous=result)
        self.assertEqual(repeated, result)
        self.assertIs(session._quarterly_indexes.current, index)
        self.assertEqual(index.epoch, 0)
        session._quarterly_indexes.invalidate()
        self.assertEqual(session.quarterly_publication_readiness(self.pid, expected_revision=1), result)
        self.assertEqual(session._quarterly_indexes.current.epoch, 0)
        self.assertEqual(encoded(session.world), before)

    def test_save_load_preserves_source_derived_diagnostic(self):
        session = self.session()
        result = session.quarterly_publication_readiness()
        before = encoded(session.world)
        session.save_manual(); session.load_saved(session.career_id)
        self.assertEqual(session.quarterly_publication_readiness(), result)
        self.assertEqual(encoded(session.world), before)

    def test_query_preserves_prior_accepted_index_epoch(self):
        from game.scheduling.quarterly_commands import ReviseQuarterlyFare
        session = self.session()
        prepared = session.prepare_quarterly_command(ReviseQuarterlyFare(self.pid, 1, self.sid, 1,
            {'currency': 'USD', 'amount_minor': 15000})).prepared
        self.assertTrue(session.apply_quarterly_command(prepared).succeeded)
        index = session._quarterly_indexes.current
        before = encoded(session.world)
        result = session.quarterly_publication_readiness(self.pid, expected_revision=2)
        self.assertTrue(result.succeeded)
        self.assertIs(session._quarterly_indexes.current, index)
        self.assertEqual(index.epoch, 1)
        self.assertEqual(encoded(session.world), before)

    def test_readiness_result_cannot_be_applied_as_a_command(self):
        session = self.session()
        result = session.quarterly_publication_readiness()
        before = encoded(session.world)
        index = session._quarterly_indexes.current
        rejected = session.apply_quarterly_command(result)
        self.assertFalse(rejected.succeeded)
        self.assertEqual(rejected.issues[0].code, 'STALE_CONTEXT')
        self.assertEqual(encoded(session.world), before)
        self.assertIs(session._quarterly_indexes.current, index)

    def test_missing_plan_absence_observation_and_foreign_source_fallback(self):
        world, _, f = self.at('2027-01-01T00:00:00Z')
        initial = inspect_quarterly_publication_readiness(world, airline_id=self.owner,
            request=PublicationReadinessRequest(expected_revision=0))
        self.assertTrue(initial.succeeded)
        sid = create_service(world, self.owner, flight_number_prefix='DAB')
        allocate_service_slot(world, sid)
        pid = create_weekly_plan(world, self.owner, '2027-Q2', slots=[f.slot(sid, 1)])
        rejected = inspect_quarterly_publication_readiness(world, airline_id=self.owner,
            request=PublicationReadinessRequest(expected_revision=0, expected_sources=initial.sources))
        self.assertEqual(rejected.issues[0].code, 'STALE_REVISION')
        session = Stage1Session(save_root=self.temp.name)
        session.world = world
        self.assertIsNone(session._quarterly_indexes)
        self.assertEqual(session.quarterly_publication_readiness(pid, expected_revision=1),
                         inspect_quarterly_publication_readiness(world, airline_id=self.owner,
                             request=PublicationReadinessRequest(pid, 1)))

    def test_weekly_wrap_and_adjacent_quarter_collisions_remain_blockers(self):
        self.closed_pattern(departure_local_time='23:00:00', weekdays=[6])
        row = self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        row['departure_local_time'] = '00:30:00'
        result = self.inspect()
        self.assertFalse(result.planning_feasible)
        self.assertFalse(result.execution_ready)
        self.assertTrue(result.planning_issues)
        # Distinct aircraft cannot evade the service/date/slot quarter collision.
        world, pid, f = self.at('2026-09-01T00:00:00Z', '2027-Q1')
        session = self.session(world)
        aid = session.purchase(session.preview_purchase('airbus-a320neo', f.origin))
        world = session.world
        row = world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'][0]
        row.update(weekdays=[3], departure_local_time='07:00:00')
        next_row = dict(deepcopy(row), planned_aircraft_id=aid, departure_local_time='09:50:00')
        create_weekly_plan(world, self.owner, '2027-Q2', slots=[next_row])
        result = self.inspect(world, pid)
        self.assertFalse(result.planning_feasible)
        self.assertIn('DUPLICATE_OCCURRENCE', result.planning_issues[0].message)

    def test_dst_nonexistent_time_fails_approved_planning_proof(self):
        self.world['world_state']['airports'][self.inspect().plan.slots[0].facts['origin_airport_id']]['timezone'] = 'America/New_York'
        row = self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        row.update(weekdays=[6], departure_local_time='02:30:00')
        result = self.inspect()
        self.assertFalse(result.planning_feasible)
        self.assertIn('does not exist', result.planning_issues[0].message)

    def test_legacy_continuous_commitments_are_not_suppressed(self):
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aid)
        row = self.inspect().plan.slots[0].facts
        draft.add_weekdays(row['origin_airport_id'], row['destination_airport_id'],
            ['2026-09-07'], '08:00', return_flight=True)
        draft.save_current(self.world, continuous=True)
        result = self.inspect()
        self.assertFalse(result.planning_feasible)
        self.assertIn('AIRCRAFT_OVERLAP', result.planning_issues[0].message)

    def test_real_active_arrival_is_used_without_movement(self):
        from game.simulation import process_events_through
        row = self.inspect().plan.slots[0].facts
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aid)
        draft.add_weekdays(row['origin_airport_id'], row['destination_airport_id'], ['2026-09-01'], '09:00')
        draft.save_current(self.world)
        self.assertTrue(process_events_through(self.world, '2026-09-01T01:10:00Z').succeeded)
        result = self.inspect()
        self.assertTrue(result.planning_feasible, result.planning_issues)
        self.assertFalse(result.execution_ready)

    def test_late_source_change_fails_final_snapshot_check(self):
        from game.scheduling import quarterly_readiness as readiness
        original = readiness.certify_quarterly_feasibility
        changed = []
        def late(*args, **kwargs):
            original(*args, **kwargs)
            self.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]['fare_offer']['amount_minor'] += 1
            changed.append(encoded(self.world))
        with patch.object(readiness, 'certify_quarterly_feasibility', side_effect=late):
            result = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner,
                request=PublicationReadinessRequest(self.pid, 1))
        self.assertEqual(result.issues[0].code, 'STALE_CONTEXT')
        self.assertEqual(encoded(self.world), changed[0])

    def test_foreign_owner_epoch_does_not_invalidate_observations(self):
        session = self.session()
        result = session.quarterly_publication_readiness(self.pid, expected_revision=1)
        foreign = next(owner for owner in session.world['world_state']['airlines'] if owner != self.owner)
        session.world['world_state']['airlines'][foreign]['display_name'] = 'Unrelated display'
        session._quarterly_indexes.invalidate()
        self.assertEqual(session.quarterly_publication_readiness(self.pid, expected_revision=1, previous=result), result)

    def test_session_boundary_rejects_running_or_bulk_work(self):
        session = self.session()
        session.world['simulation']['clock_state'] = 'NORMAL'
        self.assertEqual(session.quarterly_publication_readiness().issues[0].code, 'COMMAND_BOUNDARY')
        session.world['simulation']['clock_state'] = 'PAUSED'
        session._bulk_work = object()
        self.assertEqual(session.quarterly_publication_readiness().issues[0].code, 'COMMAND_BOUNDARY')

    def test_confirmed_lease_horizon_and_renewal_are_execution_constraints(self):
        from game.aircraft_market.step5 import preview_lease, accept_lease, renew_operating_lease
        from game.world_state.planning_reference import planning_snapshot
        state = self.world['world_state']
        original = state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        origin = original['origin_airport_id']
        offer = next(k for k in state['aircraft_market_state']['active_lease_offer_ids']
                     if state['aircraft_lease_offers'][k]['model_id'] == 'airbus-a320neo')
        aid = accept_lease(self.world, preview_lease(self.world, airline_id=self.owner,
            offer_id=offer, contract_type='OPERATING_LEASE', term_years=1, delivery_airport_id=origin))
        state = self.world['world_state']
        sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        allocate_service_slot(self.world, sid)
        row = deepcopy(state['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        row.update(service_id=sid, planned_aircraft_id=aid,
                   capacity=state['aircraft'][aid]['configuration']['economy_capacity'],
                   planning_timing=planning_snapshot(state, aid, origin, row['destination_airport_id']))
        pid = create_weekly_plan(self.world, self.owner, '2027-Q3', slots=[row])
        self.closed_pattern(pid=pid)
        initial = self.inspect(pid=pid)
        self.assertTrue(initial.planning_feasible, initial.planning_issues)
        self.assertFalse(initial.execution_ready)
        self.assertIn('CONTRACT_HORIZON_EXCEEDED', {issue.code for issue in initial.execution_blockers})
        renew_operating_lease(self.world, aircraft_id=aid, term_years=1, command_id='readiness-renewal')
        stale = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner,
            request=PublicationReadinessRequest(pid, 1, expected_sources=initial.sources))
        self.assertEqual(stale.issues[0].code, 'STALE_CONTEXT')
        renewed = self.inspect(pid=pid)
        self.assertTrue(renewed.execution_ready, renewed.execution_blockers)

    def test_cyclic_expected_observations_reject_without_mutation(self):
        source = {}; source['cycle'] = source
        before = encoded(self.world)
        result = inspect_quarterly_publication_readiness(self.world, airline_id=self.owner,
            request=PublicationReadinessRequest(self.pid, 1, expected_sources=source))
        self.assertFalse(result.succeeded)
        self.assertEqual(result.issues[0].code, 'INVALID_REQUEST')
        self.assertEqual(encoded(self.world), before)


def calendar_case(month, quarter, boundary):
    def test(self):
        year = 2028
        world, pid, _ = self.at(f'{year}-{month:02d}-01T00:00:00Z', quarter)
        result = self.inspect(world, pid)
        self.assertTrue(result.automatic_due)
        self.assertEqual(result.automatic_publication_utc, boundary)
        self.assertEqual(result.next_publication_boundary_utc, boundary)
        # Literal operating dates are independent of the query's calendar helper.
        start_month = 1 if month == 12 else month + 1
        start_year = year + (month == 12)
        self.assertEqual(result.operating_start_utc, f'{start_year}-{start_month:02d}-01T00:00:00Z')
    return test


for _month, _quarter in ((3, '2028-Q2'), (6, '2028-Q3'), (9, '2028-Q4'), (12, '2029-Q1')):
    setattr(PublicationReadinessTests, f'test_publication_calendar_month_{_month}',
        calendar_case(_month, _quarter, f'2028-{_month:02d}-01T00:00:00Z'))
