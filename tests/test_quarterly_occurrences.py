"""Dormant lineage, literal date/reference oracles and exact noninterference."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.scheduling.quarterly_occurrences import (
    QuarterlyOccurrenceReference, OccurrenceReadRequest, resolve_quarterly_occurrences,
    MAX_OCCURRENCE_REFERENCES,
)
from game.scheduling.local_time import local_departure
from game.scheduling.quarterly_commands import ReviseQuarterlyFare
from game.scheduling.service_identity import plan_occurrence_identity
from game.world_state.construction import add_airline
from game.world_state.persistence import SaveStore
from game.world_state.quarterly_construction import (
    create_weekly_plan, append_weekly_plan_revision, retire_service,
)
from tests import test_quarterly_foundation as foundation


class QuarterlyOccurrenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.FoundationTests.setUpClass.__func__(cls)

    def setUp(self):
        foundation.FoundationTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pid, self.sid, self.n, self.row = self.plan()

    slot = foundation.FoundationTests.slot
    service = foundation.FoundationTests.service
    plan = foundation.FoundationTests.plan

    def request(self, day='2028-04-03', *, pid=None, sid=None, n=None, revision=1,
                expected=1, published=None):
        return OccurrenceReadRequest(QuarterlyOccurrenceReference(
            self.pid if pid is None else pid, revision, self.sid if sid is None else sid,
            self.n if n is None else n, day), expected, published)

    def resolve(self, requests=None, *, world=None, owner=None, **kwargs):
        world = self.world if world is None else world
        before = foundation.encoded(world)
        result = resolve_quarterly_occurrences(world, airline_id=self.owner if owner is None else owner,
            requests=(self.request(),) if requests is None else requests, **kwargs)
        self.assertEqual(foundation.encoded(world), before)
        return result

    def draft(self, requests=None, **kwargs):
        result = self.resolve(requests, require_published=False, **kwargs)
        self.assertTrue(result.succeeded, result.issues)
        return result

    def publish_fixture(self, pid=None):
        pid = self.pid if pid is None else pid
        plan = self.state['weekly_plans'][pid]
        stamp = self.world['simulation']['time_utc']
        plan['revisions'][str(plan['current_revision'])]['published_at_utc'] = stamp
        return stamp

    def session(self):
        session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda: 0)
        session.world = deepcopy(self.world)
        session.career_id = session.save_store.new_career_id()
        session.save_manual(); session.load_saved(session.career_id)
        return session

    def test_published_lineage_required_by_default(self):
        self.assertEqual(self.resolve().issues[0].code, 'UNPUBLISHED_LINEAGE')
        stamp = self.publish_fixture()
        result = self.resolve()
        self.assertTrue(result.succeeded, result.issues)
        self.assertTrue(result.occurrences[0].committed)
        self.assertEqual(result.occurrences[0].published_at_utc, stamp)

    def test_literal_weekly_dates_and_public_number(self):
        result = self.draft((self.request('2028-04-10'), self.request()))
        a, b = result.occurrences
        self.assertEqual(a.occurrence_key, self.sid + '@2028-04-03#1')
        self.assertEqual(b.occurrence_key, self.sid + '@2028-04-10#1')
        self.assertEqual(a.departure_utc, '2028-04-03T00:00:00Z')
        self.assertEqual(a.flight_number, b.flight_number)
        self.assertEqual(a.flight_number, 'DAB01')
        self.assertFalse(a.committed)

    def test_same_day_multiple_frequencies(self):
        from game.world_state.quarterly_construction import allocate_service_slot
        other = allocate_service_slot(self.world, self.sid)
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1,
            slots=[self.row, self.slot(self.sid, other, departure_local_time='12:00:00')])
        result = self.draft((self.request(revision=2, expected=2),
                            self.request(n=other, revision=2, expected=2)))
        self.assertEqual(len({r.occurrence_key for r in result.occurrences}), 2)

    def test_retained_revision_stable_key_changed_assignment_facts(self):
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1,
            slots=[dict(self.row, departure_local_time='09:00:00')])
        old = self.draft((self.request(expected=2),)).occurrences[0]
        new = self.draft((self.request(expected=2, revision=2),)).occurrences[0]
        self.assertEqual(old.occurrence_key, new.occurrence_key)
        self.assertEqual(old.departure_utc, '2028-04-03T00:00:00Z')
        self.assertEqual(new.departure_utc, '2028-04-03T01:00:00Z')
        self.assertEqual(new.slot_facts['planned_aircraft_id'], self.aircraft)
        self.assertNotEqual(old.reference, new.reference)

    def test_duplicate_key_across_versions_rejects_complete_batch(self):
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1, slots=[self.row])
        result = self.resolve((self.request(expected=2), self.request(revision=2, expected=2)),
                              require_published=False)
        self.assertEqual(result.issues[0].code, 'DUPLICATE_OCCURRENCE')
        self.assertEqual(result.occurrences, ())

    def test_continuation_and_quarter_boundary_utc_second(self):
        row = dict(self.row, weekdays=[5], departure_local_time='07:59:59')
        q1 = create_weekly_plan(self.world, self.owner, '2028-Q1', slots=[row])
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1,
            slots=[dict(row, departure_local_time='08:00:00')])
        left = self.draft((self.request('2028-04-01', pid=q1),)).occurrences[0]
        right = self.draft((self.request('2028-04-01', revision=2, expected=2),)).occurrences[0]
        self.assertEqual(left.departure_utc, '2028-03-31T23:59:59Z')
        self.assertEqual(right.departure_utc, '2028-04-01T00:00:00Z')
        self.assertEqual(left.occurrence_key, right.occurrence_key)
        both = self.resolve((self.request('2028-04-01', pid=q1),
            self.request('2028-04-01', revision=2, expected=2)), require_published=False)
        self.assertEqual(both.issues[0].code, 'DUPLICATE_OCCURRENCE')

    def test_year_boundary_continuation(self):
        row = dict(self.row, weekdays=list(range(7)))
        q4 = create_weekly_plan(self.world, self.owner, '2028-Q4', slots=[row])
        q1 = create_weekly_plan(self.world, self.owner, '2029-Q1', slots=[row])
        result = self.draft((self.request('2028-12-31', pid=q4), self.request('2029-01-01', pid=q1)))
        self.assertEqual([r.departure_utc for r in result.occurrences],
                         ['2028-12-31T00:00:00Z', '2029-01-01T00:00:00Z'])
        self.assertEqual({r.reference.service_id for r in result.occurrences}, {self.sid})

    def test_arrival_obligation_crosses_quarter_without_reassignment(self):
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1,
            slots=[dict(self.row, weekdays=[5], departure_local_time='07:59:59')])
        row = self.draft((self.request('2028-07-01', expected=2, revision=2),)).occurrences[0]
        self.assertEqual(row.quarter_id, '2028-Q2')
        self.assertEqual(row.departure_utc, '2028-06-30T23:59:59Z')
        self.assertGreater(row.planning_arrival_utc, '2028-07-01T00:00:00Z')
        self.assertEqual(row.slot_facts['planned_aircraft_id'], self.aircraft)

    def test_endpoint_replacement_distinct_service(self):
        new, n = self.service()
        pid = create_weekly_plan(self.world, self.owner, '2028-Q3',
            slots=[self.slot(new, n, origin_airport_id=self.dest, destination_airport_id=self.origin,
                             connection_id=None, service_type='DEADHEAD', capacity=0,
                             fare_offer={'currency':'USD','amount_minor':0})])
        result = self.draft((self.request(), self.request('2028-07-03', pid=pid, sid=new, n=n)))
        self.assertNotEqual(result.occurrences[0].reference.service_id,
                            result.occurrences[1].reference.service_id)
        self.assertIsNone(result.occurrences[1].market_id)

    def test_retirement_number_reuse_keeps_old_lineage(self):
        retire_service(self.world, self.sid)
        newer, n = self.service()
        pid = create_weekly_plan(self.world, self.owner, '2028-Q3', slots=[self.slot(newer, n)])
        result = self.draft((self.request(), self.request('2028-07-03', pid=pid, sid=newer, n=n)))
        self.assertEqual([r.flight_number for r in result.occurrences], ['DAB01', 'DAB01'])
        self.assertEqual(len({r.occurrence_key for r in result.occurrences}), 2)

    def test_published_retirement_retains_protection(self):
        self.publish_fixture(); retire_service(self.world, self.sid)
        newer, _ = self.service()
        self.assertEqual(self.state['services'][newer]['flight_number_number'], 2)
        self.assertTrue(self.resolve().succeeded)

    def test_removed_slot_only_exists_in_retained_revision(self):
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1, slots=[])
        self.assertTrue(self.draft((self.request(expected=2),)).succeeded)
        result = self.resolve((self.request(expected=2, revision=2),), require_published=False)
        self.assertEqual(result.issues[0].code, 'INVALID_REFERENCE')

    def test_wrong_plan_owner(self):
        other = add_airline(self.world, 'Other', base_airport_id=self.origin)
        result = self.resolve(owner=other, require_published=False)
        self.assertEqual(result.issues[0].code, 'OWNERSHIP_MISMATCH')

    def test_stale_pointer_utc_and_publication_observations(self):
        for requests, kwargs, code in (
            ((self.request(expected=2),), {}, 'STALE_REVISION'),
            ((self.request(),), {'expected_time_utc':'2027-01-02T00:00:00Z'}, 'STALE_CONTEXT'),
            ((self.request(published='2027-01-01T00:00:00Z'),), {}, 'STALE_CONTEXT')):
            result = self.resolve(requests, require_published=False, **kwargs)
            self.assertEqual(result.issues[0].code, code)

    def test_invalid_membership_dates_and_reference_shapes(self):
        request = self.request()
        for ref in (replace(request.reference, operating_date='2028-04-04'),
                    replace(request.reference, operating_date='2028-07-03'),
                    replace(request.reference, operating_date='2028-4-3'),
                    replace(request.reference, slot_number=True),
                    replace(request.reference, service_id='DAB01'),
                    replace(request.reference, revision=True),
                    replace(request.reference, weekly_plan_id='weekly_plan-999999999999')):
            result = self.resolve((replace(request, reference=ref),), require_published=False)
            self.assertFalse(result.succeeded)
            self.assertEqual(result.occurrences, ())

    def test_dst_gap_rejects_without_shifting(self):
        self.state['airports'][self.origin]['timezone'] = 'America/New_York'
        pid = create_weekly_plan(self.world, self.owner, '2028-Q1',
            slots=[dict(self.row, weekdays=[6], departure_local_time='02:30:00')])
        result = self.resolve((self.request('2028-03-12', pid=pid),), require_published=False)
        self.assertFalse(result.succeeded)

    def test_nested_detachment_and_immutable_reference(self):
        row = self.draft().occurrences[0]
        with self.assertRaises(FrozenInstanceError): row.reference.revision = 99
        with self.assertRaises(TypeError): row.slot_facts['fare_offer']['amount_minor'] = 1
        self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]['fare_offer']['amount_minor'] = 123
        self.assertEqual(row.slot_facts['fare_offer']['amount_minor'], 10000)
        self.assertEqual(self.draft().occurrences[0].slot_facts['fare_offer']['amount_minor'], 123)

    def test_rebuild_order_and_independent_identity_oracle(self):
        dates = ['2028-04-03','2028-04-10','2028-04-17','2028-04-24']
        requests = tuple(self.request(day) for day in dates)
        result = self.draft(requests)
        self.assertEqual(self.draft(tuple(reversed(requests))), result)
        self.assertEqual(self.draft(requests, world=deepcopy(self.world)), result)
        for row, day in zip(result.occurrences, dates):
            self.assertEqual(row.occurrence_key, self.sid + '@' + day + '#1')
            self.assertEqual(row.occurrence_key, plan_occurrence_identity(
                self.world, self.pid, 1, self.sid, 1, day))

    def test_save_load_published_roundtrip_reconstructs(self):
        self.publish_fixture()
        result = self.resolve()
        store = SaveStore(self.temp.name); career = store.new_career_id()
        store.save(career, 'manual', self.world)
        loaded, _ = store.load(career)
        self.assertEqual(self.resolve(world=loaded), result)

    def test_bounded_batch_and_noniterating_rejection(self):
        class Bomb:
            def __iter__(self): raise AssertionError('arbitrary iterable consumed')
        with patch('game.scheduling.quarterly_occurrences._entry', side_effect=AssertionError('invalid batch reached gate')):
            for requests in (Bomb(), (), [self.request()], (self.request(),) * (MAX_OCCURRENCE_REFERENCES+1)):
                self.assertEqual(self.resolve(requests).issues[0].code, 'INVALID_REQUEST')
        from game.world_state.quarterly_construction import allocate_service_slot
        other = allocate_service_slot(self.world, self.sid)
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1,
            slots=[dict(self.row, weekdays=list(range(7))),
                   self.slot(self.sid, other, weekdays=list(range(7)), departure_local_time='12:00:00')])
        # The exact API maximum resolves only requested dates/frequencies.
        requests = tuple(self.request((date(2028,4,1)+timedelta(days=n)).isoformat(),
            n=slot, revision=2, expected=2) for n in range(64) for slot in (self.n, other))
        result = self.draft(requests)
        self.assertEqual(len(result.occurrences), 128)
        self.assertEqual(len({r.occurrence_key for r in result.occurrences}), 128)

    def test_late_dependency_change_rejects_no_partial_output(self):
        def changed(*args, **kwargs):
            departure = local_departure(*args, **kwargs)
            self.state['aircraft'][self.aircraft]['display_registration'] = 'RP-C9999'
            return departure
        # External valid display mutation is preserved; query must reject its mixed snapshot.
        with patch('game.scheduling.quarterly_occurrences.local_departure', side_effect=changed):
            result = resolve_quarterly_occurrences(self.world, airline_id=self.owner,
                requests=(self.request(),), require_published=False)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.occurrences, ())
        self.assertEqual(result.issues[0].code, 'STALE_CONTEXT')

    def test_session_load_rebind_and_no_command_capability(self):
        session = self.session()
        request = (self.request(),)
        before = foundation.encoded(session.world)
        result = session.quarterly_occurrences(request, require_published=False)
        self.assertTrue(result.succeeded, result.issues)
        session.save_manual(); session.load_saved(session.career_id)
        self.assertEqual(session.quarterly_occurrences(request, require_published=False), result)
        session.world = deepcopy(session.world)
        self.assertEqual(session.quarterly_occurrences(request, require_published=False), result)
        self.assertFalse(session.apply_quarterly_command(result).succeeded)
        self.assertEqual(foundation.encoded(session.world), before)

    def test_session_accepted_epoch_unchanged_and_old_pointer_stale(self):
        # Build an editable target through the existing 2B command boundary.
        from game.utils.quarters import normal_target_quarter
        quarter = normal_target_quarter(self.world['simulation']['time_utc'])
        self.state['weekly_plans'][self.pid]['quarter_id'] = quarter.quarter_id
        session = self.session()
        prepared = session.prepare_quarterly_command(ReviseQuarterlyFare(self.pid, 1, self.sid, 1,
            {'currency':'USD','amount_minor':15000})).prepared
        applied = session.apply_quarterly_command(prepared)
        self.assertTrue(applied.succeeded, applied.issues)
        index = session._quarterly_indexes.current
        before = foundation.encoded(session.world)
        day = quarter.start_utc.date()
        while day.weekday() != 0: day += timedelta(days=1)
        request = self.request(day.isoformat(), revision=2, expected=2)
        self.assertTrue(session.quarterly_occurrences((request,), require_published=False).succeeded)
        self.assertEqual(session.quarterly_occurrences((replace(request,expected_revision=1),),
            require_published=False).issues[0].code, 'STALE_REVISION')
        self.assertIs(session._quarterly_indexes.current, index)
        self.assertEqual(index.epoch, 1)
        self.assertEqual(foundation.encoded(session.world), before)

    def test_session_running_and_bulk_reject(self):
        session = self.session()
        session._bulk_work = object()
        self.assertFalse(session.quarterly_occurrences((self.request(),), require_published=False).succeeded)
        session._bulk_work = None
        session.world['simulation']['clock_state'] = 'RUNNING'
        self.assertFalse(session.quarterly_occurrences((self.request(),), require_published=False).succeeded)

    def test_assignment_lineage_uses_selected_aircraft(self):
        session = self.session()
        newer = session.purchase(session.preview_purchase('airbus-a320neo', self.origin))
        self.world = session.world; self.state = self.world['world_state']
        from game.world_state.planning_reference import planning_snapshot
        row = dict(self.row, planned_aircraft_id=newer,
            capacity=self.state['aircraft'][newer]['configuration']['economy_capacity'],
            planning_timing=planning_snapshot(self.state, newer, self.origin, self.dest))
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1, slots=[row])
        old = self.draft((self.request(expected=2),)).occurrences[0]
        current = self.draft((self.request(expected=2, revision=2),)).occurrences[0]
        self.assertEqual(old.slot_facts['planned_aircraft_id'], self.aircraft)
        self.assertEqual(current.slot_facts['planned_aircraft_id'], newer)
        self.assertEqual(old.occurrence_key, current.occurrence_key)

    def test_legacy_commitments_remain_separate_and_unchanged(self):
        from game.scheduling import WeeklyDraft
        from game.world_state.timestamps import parse_canonical_utc, format_utc
        draft = WeeklyDraft(self.world, airline_id=self.owner, aircraft_id=self.aircraft)
        departure = parse_canonical_utc(self.world['simulation']['time_utc']) + timedelta(days=1)
        draft.add(self.origin, self.dest, departure_utc=format_utc(departure), deadhead=True)
        draft.save_current(self.world)
        self.state = self.world['world_state']
        self.assertTrue(self.state['dated_flights'])
        before = deepcopy(self.state['dated_flights'])
        result = self.draft()
        self.assertEqual(len(result.occurrences), 1)
        self.assertEqual(self.state['dated_flights'], before)
        self.assertNotIn(result.occurrences[0].occurrence_key,
                         {r['occurrence_key'] for r in before.values()})

    def test_two_full_source_gates_and_one_date_conversion_per_reference(self):
        from game.scheduling import quarterly_occurrences as module
        with patch.object(module, '_entry', wraps=module._entry) as gates, \
             patch.object(module, 'local_departure', wraps=module.local_departure) as conversions:
            result = self.draft((self.request(), self.request('2028-04-10')))
        self.assertEqual(gates.call_count, 2)
        self.assertEqual(conversions.call_count, len(result.occurrences))

    def test_invalid_world_and_schema_fail_closed(self):
        for mutate in (lambda w: w['metadata'].update(save_schema_version=8),
                       lambda w: w['world_state']['services'][self.sid].update(next_slot_number=1)):
            world = deepcopy(self.world); mutate(world)
            self.assertFalse(self.resolve(world=world, require_published=False).succeeded)


if __name__ == '__main__':
    unittest.main()
