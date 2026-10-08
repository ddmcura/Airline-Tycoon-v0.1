"""Stage 2A read-only ownership, detachment and explicitly scoped comparisons."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.scheduling.quarterly_reads import PlanReadRequest, resolve_quarterly_reads
from game.scheduling.rotation import _connection
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.construction import add_airline
from game.world_state.persistence import SaveStore
from game.world_state.planning_reference import planning_snapshot
from game.world_state.quarterly_construction import (
    create_service, allocate_service_slot, create_weekly_plan,
    append_weekly_plan_revision, retire_service,
)


def encoded(world):
    return json.dumps(world, sort_keys=True, separators=(',', ':'), allow_nan=False)


class CountingTable(dict):
    """Guard unrelated table traversal without synthetic aircraft or history."""
    def __init__(self, table):
        super().__init__(table)
        self.reads = 0

    def __iter__(self):
        raise AssertionError('unexpected global table traversal')

    def values(self):
        raise AssertionError('unexpected global values traversal')

    def items(self):
        raise AssertionError('unexpected global items traversal')

    def get(self, key, default=None):
        self.reads += 1
        return super().get(key, default)

    def __getitem__(self, key):
        self.reads += 1
        return super().__getitem__(key)


class QuarterlyReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id='stage1-philippines-v1',
            ceo_display_name='A', airline_display_name='Dabudhi',
            base_airport_reference_code='MNL')

    def setUp(self):
        self.world = deepcopy(self.base)
        self.state = self.world['world_state']
        self.owner = self.state['player']['primary_airline_id']
        self.aircraft = next(iter(self.state['aircraft']))
        self.origin = self.state['aircraft'][self.aircraft]['current_airport_id']
        self.dest = next(k for k, row in self.state['airports'].items() if row['reference_code'] == 'DVO')
        self.ceb = next(k for k, row in self.state['airports'].items() if row['reference_code'] == 'CEB')
        self.sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        self.number = allocate_service_slot(self.world, self.sid)
        self.row = self.slot(self.sid, self.number)
        self.pid = create_weekly_plan(self.world, self.owner, '2028-Q1', slots=[self.row])

    def slot(self, sid, number, *, origin=None, dest=None, **changes):
        origin = self.origin if origin is None else origin
        dest = self.dest if dest is None else dest
        row = dict(service_id=sid, slot_number=number, weekdays=[0],
            departure_local_time='08:00:00', departure_local_fold=0,
            origin_airport_id=origin, destination_airport_id=dest,
            planned_aircraft_id=self.aircraft,
            connection_id=_connection(self.world, self.owner, origin, dest),
            service_type='PASSENGER',
            capacity=self.state['aircraft'][self.aircraft]['configuration']['economy_capacity'],
            fare_offer={'currency': 'USD', 'amount_minor': 10000},
            planning_timing=planning_snapshot(self.state, self.aircraft, origin, dest))
        row.update(changes)
        return row

    def read(self, *, owner=None, requests=None, world=None):
        return resolve_quarterly_reads(self.world if world is None else world,
            airline_id=self.owner if owner is None else owner,
            selections=(PlanReadRequest(self.pid, 1),) if requests is None else requests)

    def test_direct_owner_dependencies_and_pure_deterministic_resolution(self):
        before = encoded(self.world)
        result = self.read()
        self.assertTrue(result.succeeded, result.issues)
        market = self.state['connections'][self.row['connection_id']]['market_id']
        expected = {('airlines', self.owner), ('weekly_plans', self.pid),
            ('services', self.sid), ('service_numbering', self.owner),
            ('aircraft', self.aircraft), ('airports', self.origin), ('airports', self.dest),
            ('connections', self.row['connection_id']), ('directional_markets', market)}
        self.assertEqual(result.dependencies, tuple(sorted(expected)))
        view = result.plans[0]
        self.assertEqual((view.airline_id, view.weekly_plan_id, view.revision), (self.owner, self.pid, 1))
        self.assertEqual(view.slots[0].flight_number, 'DAB01')
        self.assertEqual(result, self.read())
        self.assertEqual(encoded(self.world), before)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_wrong_plan_owner(self):
        other = add_airline(self.world, 'Other', base_airport_id=self.origin)
        before = encoded(self.world)
        result = self.read(owner=other)
        self.assertEqual(result.issues[0].code, 'OWNERSHIP_MISMATCH')
        self.assertFalse(result.plans)
        self.assertEqual(encoded(self.world), before)

    def test_foreign_service_aircraft_and_connection_owners(self):
        other = add_airline(self.world, 'Other', base_airport_id=self.origin)
        for table, identity in [('services', self.sid), ('aircraft', self.aircraft),
                                ('connections', self.row['connection_id'])]:
            record = self.state[table][identity]
            record['airline_id'] = other
            before = encoded(self.world)
            result = self.read()
            self.assertEqual(result.issues[0].code, 'OWNERSHIP_MISMATCH')
            self.assertIn(table, result.issues[0].path)
            self.assertFalse(result.dependencies)
            self.assertEqual(encoded(self.world), before)
            record['airline_id'] = self.owner

    def test_dangling_direct_references(self):
        market = self.state['connections'][self.row['connection_id']]['market_id']
        for table, identity in [('services', self.sid), ('aircraft', self.aircraft),
                                ('connections', self.row['connection_id']),
                                ('directional_markets', market), ('airports', self.dest),
                                ('weekly_plans', self.pid), ('airlines', self.owner)]:
            with self.subTest(table=table):
                record = self.state[table].pop(identity)
                before = encoded(self.world)
                result = self.read()
                self.assertEqual(result.issues[0].code, 'INVALID_REFERENCE')
                self.assertFalse(result.plans)
                self.assertEqual(encoded(self.world), before)
                self.state[table][identity] = record

    def test_identity_keys_not_display_labels_or_record_position(self):
        result = self.read(requests=(PlanReadRequest('DAB01', 1),))
        self.assertEqual(result.issues[0].code, 'INVALID_REQUEST')
        self.state['services'][self.sid]['service_id'] = 'service-999999999999'
        self.assertEqual(self.read().issues[0].code, 'INVALID_REFERENCE')

    def test_invalid_requests_and_missing_selected_slots(self):
        before = encoded(self.world)
        for requests in [(), [], (None,), (PlanReadRequest(self.pid, True),),
                         (PlanReadRequest(self.pid, 1, revision=True),),
                         (PlanReadRequest(self.pid, 1, revision=99),),
                         (PlanReadRequest(self.pid, 1, slot_keys=((self.sid, 99),)),),
                         (PlanReadRequest(self.pid, 1, slot_keys=((self.sid, True),)),),
                         (PlanReadRequest(self.pid, 1), PlanReadRequest(self.pid, 1))]:
            with self.subTest(requests=requests):
                self.assertFalse(self.read(requests=requests).succeeded)
                self.assertEqual(encoded(self.world), before)

    def test_stale_observation_and_explicit_old_revision(self):
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1,
                                    slots=[dict(self.row, departure_local_time='09:00:00')])
        before = encoded(self.world)
        issue = self.read().issues[0]
        self.assertEqual((issue.code, issue.observed_revision), ('STALE_REVISION', 2))
        result = self.read(requests=(PlanReadRequest(self.pid, 2, revision=1),
                                     PlanReadRequest(self.pid, 2, revision=2)))
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual([p.slots[0].facts['departure_local_time'] for p in result.plans],
                         ['08:00:00', '09:00:00'])
        self.assertEqual(encoded(self.world), before)

    def test_nested_facts_are_immutable_and_detached_in_both_directions(self):
        result = self.read()
        facts = result.plans[0].slots[0].facts
        before = encoded(self.world)
        with self.assertRaises(TypeError):
            facts['fare_offer']['amount_minor'] = 0
        with self.assertRaises(TypeError):
            facts['weekdays'][0] = 4
        with self.assertRaises(TypeError):
            facts['planning_timing']['model_reference']['model_id'] = 'other'
        with self.assertRaises(FrozenInstanceError):
            result.plans[0].airline_id = 'other'
        self.assertEqual(encoded(self.world), before)
        self.state['weekly_plans'][self.pid]['revisions']['1']['slots'][0]['fare_offer']['amount_minor'] = 5
        self.assertEqual(facts['fare_offer']['amount_minor'], 10000)

    def test_explicit_cross_quarter_continuation_and_input_order_independence(self):
        pid = create_weekly_plan(self.world, self.owner, '2028-Q2', slots=[
            dict(self.row, departure_local_time='08:30:00', weekdays=[0, 2])])
        requests = (PlanReadRequest(self.pid, 1), PlanReadRequest(pid, 1))
        before = encoded(self.world)
        result = self.read(requests=requests)
        self.assertTrue(result.succeeded)
        self.assertEqual(result, self.read(requests=tuple(reversed(requests))))
        self.assertEqual([p.slots[0].service_id for p in result.plans], [self.sid, self.sid])
        self.assertEqual([p.slots[0].flight_number for p in result.plans], ['DAB01', 'DAB01'])
        self.assertEqual(encoded(self.world), before)

    def test_endpoint_changes_in_explicit_versions_reject_without_schema_changes(self):
        for origin, dest in [(self.origin, self.ceb), (self.ceb, self.dest)]:
            with self.subTest(endpoints=(origin, dest)):
                changed = self.slot(self.sid, self.number, origin=origin, dest=dest)
                world = deepcopy(self.world)
                pid = create_weekly_plan(world, self.owner, '2028-Q2', slots=[self.row])
                world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'] = [changed]
                self.assertFalse(validate_world(world).is_valid)
                before = encoded(world)
                result = self.read(world=world, requests=(PlanReadRequest(self.pid, 1), PlanReadRequest(pid, 1)))
                self.assertEqual(result.issues[0].code, 'ENDPOINT_INCONSISTENCY')
                self.assertFalse(result.plans)
                self.assertEqual(encoded(world), before)

    def test_endpoint_check_within_selected_plan_and_across_retained_revisions(self):
        n = allocate_service_slot(self.world, self.sid)
        changed = self.slot(self.sid, n, dest=self.ceb)
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1, slots=[self.row, dict(self.row, slot_number=n)])
        self.state['weekly_plans'][self.pid]['revisions']['2']['slots'][1] = changed
        result = self.read(requests=(PlanReadRequest(self.pid, 2),))
        self.assertEqual(result.issues[0].code, 'ENDPOINT_INCONSISTENCY')
        self.state['weekly_plans'][self.pid]['revisions']['3'] = {'revision': 3, 'published_at_utc': None, 'slots': [changed]}
        self.state['weekly_plans'][self.pid]['current_revision'] = 3
        result = self.read(requests=(PlanReadRequest(self.pid, 3, revision=1),
                                     PlanReadRequest(self.pid, 3, revision=3)))
        self.assertEqual(result.issues[0].code, 'ENDPOINT_INCONSISTENCY')

    def test_retirement_preserves_readable_facts_not_mutation_permission(self):
        historic = deepcopy(self.state['weekly_plans'][self.pid])
        retire_service(self.world, self.sid)
        result = self.read()
        self.assertTrue(result.succeeded)
        self.assertEqual(result.plans[0].slots[0].retired_at_utc, self.world['simulation']['time_utc'])
        self.assertEqual(self.state['weekly_plans'][self.pid], historic)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_deadhead_and_explicit_slot_subset(self):
        sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        n = allocate_service_slot(self.world, sid)
        row = self.slot(sid, n, service_type='DEADHEAD', connection_id=None, capacity=0,
                        fare_offer={'currency': 'USD', 'amount_minor': 0})
        append_weekly_plan_revision(self.world, self.pid, expected_revision=1, slots=[self.row, row])
        result = self.read(requests=(PlanReadRequest(self.pid, 2, slot_keys=((sid, n),)),))
        self.assertTrue(result.succeeded)
        self.assertIsNone(result.plans[0].slots[0].market_id)
        self.assertFalse(any(table in ('connections', 'directional_markets') for table, _ in result.dependencies))

    def test_full_gate_not_called_by_trusted_resolver_and_no_allocations(self):
        before = encoded(self.world)
        for table in ('airlines', 'weekly_plans', 'services', 'service_numbering', 'aircraft',
                      'airports', 'connections', 'directional_markets'):
            self.state[table] = CountingTable(self.state[table])
        with (patch('game.world_state.ids.allocate_id', side_effect=AssertionError('read allocation')),
              patch('game.world_state.validation.validate_world', side_effect=AssertionError('resolver global gate'))):
            result = self.read()
        self.assertTrue(result.succeeded, result.issues)
        # Encode the original equivalent world, avoiding instrumentation's deliberate iteration guards.
        for table in ('airlines', 'weekly_plans', 'services', 'service_numbering', 'aircraft',
                      'airports', 'connections', 'directional_markets'):
            self.state[table] = {key: value for key, value in dict.items(self.state[table])}
        self.assertEqual(encoded(self.world), before)

    def test_unrelated_authoritative_service_population_does_not_increase_reads(self):
        counts = []
        for count in (1, 10, 25, 50, 100, 250, 500, 1000):
            world = deepcopy(self.world)
            for _ in range(count):
                create_service(world, self.owner, flight_number_prefix='DAB')
            self.assertTrue(validate_world(world).is_valid)
            tables = []
            for name in ('airlines', 'weekly_plans', 'services', 'service_numbering', 'aircraft',
                         'airports', 'connections', 'directional_markets'):
                table = CountingTable(world['world_state'][name])
                world['world_state'][name] = table
                tables.append(table)
            result = self.read(world=world)
            self.assertTrue(result.succeeded, result.issues)
            counts.append(sum(t.reads for t in tables))
        self.assertEqual(len(set(counts)), 1, counts)

    def test_exact_schema9_save_load_and_serialization_read_equivalence(self):
        before = encoded(self.world)
        expected = self.read()
        with tempfile.TemporaryDirectory() as root:
            store = SaveStore(root)
            career = store.new_career_id()
            store.save(career, 'manual', self.world)
            loaded, _ = store.load(career)
            self.assertEqual(encoded(loaded), before)
            self.assertEqual(self.read(world=loaded), expected)
        self.assertEqual(self.read(world=json.loads(before)), expected)
        self.assertEqual(self.world['metadata']['save_schema_version'], 9)

    def test_session_trust_boundary_and_explicit_comparison(self):
        session = Stage1Session()
        self.assertEqual(session.quarterly_plan_dependencies(self.pid, expected_revision=1).issues[0].code, 'INVALID_WORLD')
        session.world = deepcopy(self.world)
        before = encoded(session.world)
        result = session.quarterly_plan_dependencies(self.pid, expected_revision=1)
        self.assertEqual(result, self.read())
        self.assertEqual(encoded(session.world), before)
        bad = deepcopy(self.world)
        del bad['world_state']['aircraft'][self.aircraft]
        session.world = bad
        self.assertEqual(session.quarterly_plan_dependencies(self.pid, expected_revision=1).issues[0].code, 'INVALID_WORLD')
        pid = create_weekly_plan(self.world, self.owner, '2028-Q2', slots=[self.row])
        self.state['weekly_plans'][pid]['revisions']['1']['slots'] = [self.slot(self.sid, self.number, dest=self.ceb)]
        session.world = self.world
        result = session.quarterly_plan_dependencies(self.pid, expected_revision=1,
            compare_with=(PlanReadRequest(pid, 1),))
        self.assertEqual(result.issues[0].code, 'INVALID_WORLD')

    def test_read_lifecycle_is_derived_and_not_changed(self):
        self.state['weekly_plans'][self.pid]['revisions']['1']['published_at_utc'] = self.world['simulation']['time_utc']
        before = encoded(self.world)
        self.assertEqual(self.read().plans[0].current_lifecycle, 'PUBLISHED')
        self.assertEqual(encoded(self.world), before)
        self.assertEqual(self.state['dated_flights'], {})

    def test_session_trusted_repeat_keeps_full_validation_boundary(self):
        session = Stage1Session()
        session.world = deepcopy(self.world)
        initial = session.quarterly_plan_dependencies(self.pid, expected_revision=1)
        self.assertTrue(initial.succeeded, initial.issues)
        with patch('app.session.validate_world', side_effect=AssertionError('unchanged owned source regated')):
            self.assertEqual(session.quarterly_plan_dependencies(self.pid, expected_revision=1), initial)
        # Foreign rebinding revokes trust, including an equivalent deserialized world.
        session.world = json.loads(encoded(self.world))
        with patch('app.session.validate_world', wraps=validate_world) as gate:
            self.assertEqual(session.quarterly_plan_dependencies(self.pid, expected_revision=1), initial)
            self.assertEqual(gate.call_count, 1)

    def test_new_identity_on_different_route_is_readable_not_false_continuation(self):
        sid = create_service(self.world, self.owner, flight_number_prefix='DAB')
        n = allocate_service_slot(self.world, sid)
        pid = create_weekly_plan(self.world, self.owner, '2028-Q2', slots=[self.slot(sid, n, dest=self.ceb)])
        result = self.read(requests=(PlanReadRequest(self.pid, 1), PlanReadRequest(pid, 1)))
        self.assertTrue(result.succeeded, result.issues)
        self.assertEqual([p.slots[0].flight_number for p in result.plans], ['DAB01', 'DAB02'])
        self.assertNotEqual(result.plans[0].slots[0].service_id, result.plans[1].slots[0].service_id)
        self.assertTrue(validate_world(self.world).is_valid)


if __name__ == '__main__':
    unittest.main()
