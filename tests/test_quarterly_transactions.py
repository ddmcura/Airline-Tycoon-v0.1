"""Stage 2E: independent transaction witnesses, adversarial seams and dormancy.

Source-scan commands are the differential discovery oracle, not an independent
implementation of chronology formulas. Literal chronology cases in the 2C/2D
suites remain required. Direct field scans below independently certify indexes.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.scheduling import quarterly_commands as commands
from game.scheduling.quarterly_indexes import QuarterlyDependencyIndex, QuarterlyIndexOwner
from game.scheduling.quarterly_feasibility import temporal_sources
from game.world_state import validate_world
from game.world_state.quarterly_construction import create_weekly_plan
from tests.profile_quarterly_dependencies import fixture
from tests.test_quarterly_foundation import encoded
from tests.test_quarterly_indexes import independent_edges


KINDS = ('create', 'fare', 'revise', 'add', 'continue', 'replace', 'remove', 'retire')


def operational_witness(world):
    """Every envelope fact except the three dormant roots and their ID cursors."""
    result = deepcopy(world)
    for key in ('services', 'service_numbering', 'weekly_plans'):
        result['world_state'].pop(key)
    cursors = result['deterministic_state']['id_allocator']['next_by_type']
    for key in ('service', 'weekly_plan'):
        cursors.pop(key)
    return encoded(result)


def number_oracle(world, owner):
    """Direct schema rule, without allocator/index eligibility helpers."""
    state = world['world_state']
    now = datetime.fromisoformat(world['simulation']['time_utc'].replace('Z', '+00:00'))
    committed = set()
    for plan in state['weekly_plans'].values():
        year, quarter = map(int, plan['quarter_id'].split('-Q'))
        end = datetime(year + (quarter == 4), 1 if quarter == 4 else quarter * 3 + 1,
                       1, tzinfo=timezone.utc)
        revision = plan['revisions'][str(plan['current_revision'])]
        if end > now and revision['published_at_utc'] is not None:
            committed.update(row['service_id'] for row in revision['slots'])
    protected, retired = {}, set()
    for sid, service in state['services'].items():
        if service['airline_id'] != owner:
            continue
        suffix = service['flight_number_number']
        if service['retired_at_utc'] is None or sid in committed:
            protected.setdefault(suffix, []).append(sid)
        else:
            retired.add(suffix)
    return ({key: tuple(sorted(value)) for key, value in protected.items()},
            tuple(sorted(retired - protected.keys())))


class QuarterlyTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.owner, cls.aid, cls.pid, cls.sid = fixture(1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def session(self, world=None):
        session = Stage1Session(save_root=self.temp.name, runtime_clock=lambda: 0)
        session.world = deepcopy(self.base if world is None else world)
        session.career_id = session.save_store.new_career_id()
        session.save_manual()
        session.load_saved(session.career_id)
        return session

    def facts(self, **changes):
        row = deepcopy(self.base['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        for key in ('service_id', 'slot_number', 'planning_timing'):
            del row[key]
        row.update(changes)
        return row

    def scenario(self, kind):
        world = deepcopy(self.base)
        pid, sid = self.pid, self.sid
        if kind == 'create':
            request = commands.CreateQuarterlyService('2027-Q1', 'DAB', self.facts(weekdays=[2]), pid, 1)
        elif kind == 'fare':
            request = commands.ReviseQuarterlyFare(pid, 1, sid, 1, {'currency': 'USD', 'amount_minor': 20000})
        elif kind == 'revise':
            request = commands.ReviseQuarterlySlot(pid, 1, sid, 1, {'weekdays': [1], 'departure_local_time': '09:00:00'})
        elif kind == 'add':
            request = commands.AddQuarterlyFrequency(pid, 1, sid, self.facts(weekdays=[2]))
        elif kind == 'continue':
            rows = deepcopy(world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'])
            prior = create_weekly_plan(world, self.owner, '2026-Q4', slots=rows)
            world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'] = []
            request = commands.ContinueQuarterlySlot(pid, 1, prior, 1, 1, sid, 1, {'weekdays': [1]})
        elif kind == 'replace':
            facts = self.facts()
            request = commands.ReplaceQuarterlyService(pid, 1, sid, 'DAB', self.facts(
                origin_airport_id=facts['destination_airport_id'], destination_airport_id=facts['origin_airport_id'],
                connection_id=None, service_type='DEADHEAD', capacity=0,
                fare_offer={'currency': 'USD', 'amount_minor': 0}))
        elif kind == 'remove':
            request = commands.RemoveQuarterlySlots(pid, 1, ((sid, 1),))
        else:
            world['world_state']['weekly_plans'][pid]['revisions']['1']['slots'] = []
            request = commands.RetireQuarterlyService(pid, 1, sid)
        self.assertTrue(validate_world(world).is_valid)
        return world, request

    def prepare(self, session, request):
        ready = session.prepare_quarterly_command(request)
        self.assertTrue(ready.succeeded, ready.issues)
        return ready.prepared

    def assert_index(self, session):
        world = session.world
        index = session._quarterly_indexes.current
        self.assertTrue(index.matches(world))
        actual = {name: {key: set(values) for key, values in mapping.items()}
                  for name, mapping in index._maps.items() if mapping}
        self.assertEqual(actual, independent_edges(world))
        endpoints = {}
        for plan in world['world_state']['weekly_plans'].values():
            for revision in plan['revisions'].values():
                for row in revision['slots']:
                    pair = row['origin_airport_id'], row['destination_airport_id']
                    self.assertEqual(endpoints.setdefault(row['service_id'], pair), pair)
        self.assertEqual(dict(index._endpoints), endpoints)
        for owner in world['world_state']['service_numbering']:
            holders, eligible = number_oracle(world, owner)
            self.assertEqual({key: tuple(sorted(ids)) for key, ids in index.number_holders(owner).items()}, holders)
            self.assertEqual(index.eligible_numbers(owner), eligible)
        rebuilt = QuarterlyDependencyIndex._build(world)
        for name in ('_maps', '_plans', '_quarters', '_numbers', '_endpoints', '_ends', '_departures'):
            left, right = getattr(index, name), getattr(rebuilt, name)
            if name == '_maps':
                # Deltas retain empty relation containers; cold builds omit them.
                # Relationship coverage is independently checked above in full.
                left = {key: value for key, value in left.items() if value}
                right = {key: value for key, value in right.items() if value}
            self.assertEqual(left, right)
        self.assertEqual(temporal_sources(world, {self.aid}, index=index), temporal_sources(world, {self.aid}))

    def differential(self, world, request, success=True):
        session = self.session(world)
        reference = deepcopy(session.world)
        before = encoded(session.world)
        operational = operational_witness(session.world)
        prepared = self.prepare(session, request)
        ref = commands.prepare_quarterly_command(reference, airline_id=self.owner, request=deepcopy(request))
        self.assertTrue(ref.succeeded, ref.issues)
        self.assertEqual(prepared, ref.prepared)
        index = session._quarterly_indexes.current
        expected = commands.apply_quarterly_command(reference, airline_id=self.owner, prepared=ref.prepared)
        actual = session.apply_quarterly_command(prepared)
        self.assertEqual(actual, expected)
        self.assertEqual(actual.succeeded, success, actual.issues)
        self.assertEqual(encoded(session.world), encoded(reference))
        self.assertEqual(operational_witness(session.world), operational)
        if success:
            self.assertEqual(session._quarterly_indexes.current.epoch, index.epoch + 1)
            self.assert_index(session)
        else:
            self.assertEqual(encoded(session.world), before)
            self.assertIs(session._quarterly_indexes.current, index)
        return session, actual

    def failure_matrix(self, seam, gate=None):
        for kind in KINDS:
            with self.subTest(command=kind, seam=seam, gate=gate):
                world, request = self.scenario(kind)
                session = self.session(world)
                prepared = self.prepare(session, request)
                before = encoded(session.world)
                index = session._quarterly_indexes.current
                snapshot = (index._maps, index._plans, index._numbers, index.epoch)
                if gate is not None:
                    original = commands._entry
                    calls = []
                    def injected(value):
                        calls.append(value)
                        original(value)
                        self.assertEqual(encoded(session.world), before)
                        self.assertIs(session._quarterly_indexes.current, index)
                        if len(calls) == gate:
                            raise ValueError('certification after full gate')
                    target, name = commands, '_entry'
                else:
                    if seam == 'prepare_publication':
                        target, name = QuarterlyIndexOwner, seam
                    elif seam in {'updated', 'verify_delta', 'rebound'}:
                        target, name = QuarterlyDependencyIndex, seam
                    else:
                        target, name = commands, seam
                    original = getattr(target, name)
                    def injected(*args, **kwargs):
                        # Result construction includes the rejection result too.
                        if seam == 'QuarterlyCommandResult' and not (args and args[0] is True):
                            return original(*args, **kwargs)
                        original(*args, **kwargs)
                        self.assertEqual(encoded(session.world), before)
                        self.assertIs(session._quarterly_indexes.current, index)
                        raise ValueError('certification after fallible staging')
                with patch.object(target, name, autospec=True, side_effect=injected):
                    rejected = session.apply_quarterly_command(prepared)
                self.assertFalse(rejected.succeeded)
                self.assertEqual(encoded(session.world), before)
                self.assertIs(session._quarterly_indexes.current, index)
                self.assertEqual((index._maps, index._plans, index._numbers, index.epoch), snapshot)
                # Retry the exact issued object, compare every byte/result to control.
                reference = deepcopy(world)
                ref = commands.prepare_quarterly_command(reference, airline_id=self.owner, request=request)
                expected = commands.apply_quarterly_command(reference, airline_id=self.owner, prepared=ref.prepared)
                actual = session.apply_quarterly_command(prepared)
                self.assertTrue(actual.succeeded, actual.issues)
                self.assertEqual(actual, expected)
                self.assertEqual(encoded(session.world), encoded(reference))
                self.assert_index(session)

    def test_reused_number_sequence_matches_independent_schema_rule(self):
        session, _ = self.differential(*self.scenario('remove'))
        self.assertEqual(number_oracle(session.world, self.owner)[1], ())
        session, _ = self.differential(session.world, commands.RetireQuarterlyService(self.pid, 2, self.sid))
        self.assertEqual(number_oracle(session.world, self.owner)[1], (1,))
        cursor = session.world['world_state']['service_numbering'][self.owner]['next_number']
        session, result = self.differential(session.world, commands.CreateQuarterlyService(
            '2027-Q1', 'DAB', self.facts(), self.pid, 2))
        self.assertNotEqual(result.service_id, self.sid)
        self.assertEqual(session.world['world_state']['services'][result.service_id]['flight_number_number'], 1)
        self.assertEqual(session.world['world_state']['service_numbering'][self.owner]['next_number'], cursor)

    def test_committed_number_survives_removal_and_retirement(self):
        world, request = self.scenario('continue')
        prior = next(pid for pid in world['world_state']['weekly_plans'] if pid != self.pid
                     and world['world_state']['weekly_plans'][pid]['airline_id'] == self.owner)
        world['world_state']['weekly_plans'][prior]['revisions']['1']['published_at_utc'] = world['simulation']['time_utc']
        request = commands.RetireQuarterlyService(self.pid, 1, self.sid)
        session, _ = self.differential(world, request)
        self.assertEqual(number_oracle(session.world, self.owner), ({1: (self.sid,)}, ()))

    def test_gate_and_copy_roles_and_no_early_visibility(self):
        for kind in KINDS:
            with self.subTest(command=kind):
                world, request = self.scenario(kind)
                session = self.session(world)
                before = encoded(session.world)
                gates, copies, order = [], [], []
                entry, clone = commands._entry, commands.deepcopy
                def gate(value):
                    self.assertEqual(encoded(session.world), before)
                    gates.append(value); order.append('gate')
                    return entry(value)
                def copy(value):
                    result = clone(value)
                    if type(value) is dict and 'world_state' in value:
                        copies.append((value, result)); order.append('copy')
                    return result
                with patch.object(commands, '_entry', side_effect=gate), patch.object(commands, 'deepcopy', side_effect=copy):
                    prepared = self.prepare(session, request)
                    result = session.apply_quarterly_command(prepared)
                self.assertTrue(result.succeeded, result.issues)
                self.assertEqual(order, ['gate', 'gate', 'copy', 'gate', 'copy', 'gate'])
                self.assertIs(gates[0], session.world)
                self.assertIs(gates[1], session.world)
                self.assertIs(gates[2], copies[0][1])
                self.assertIs(gates[3], copies[1][1])
                self.assertIs(copies[1][0], copies[0][1])
                self.assertIsNot(copies[0][1], copies[1][1])

    def test_caller_preparation_result_and_staging_alias_isolation(self):
        for kind in KINDS:
            with self.subTest(command=kind):
                world, request = self.scenario(kind)
                session = self.session(world)
                prepared = self.prepare(session, request)
                reference = deepcopy(session.world)
                ref = commands.prepare_quarterly_command(reference, airline_id=self.owner, request=request)
                expected = commands.apply_quarterly_command(reference, airline_id=self.owner, prepared=ref.prepared)
                for field in ('slot', 'changes', 'fare_offer'):
                    value = getattr(request, field, None)
                    if isinstance(value, dict):
                        value.clear()
                with self.assertRaises(FrozenInstanceError):
                    prepared.airline_id = 'other'
                with self.assertRaises(TypeError):
                    prepared.intent['kind'] = 'RETIRE'
                with self.assertRaises(TypeError):
                    prepared.sources['time'] = 'invalid'
                captured = []
                original = commands.append_weekly_plan_revision
                def append(*args, **kwargs):
                    captured.append((args[0], kwargs['slots']))
                    return original(*args, **kwargs)
                with patch.object(commands, 'append_weekly_plan_revision', side_effect=append):
                    result = session.apply_quarterly_command(prepared)
                self.assertTrue(result.succeeded, result.issues)
                self.assertEqual(result, expected)
                self.assertEqual(encoded(session.world), encoded(reference))
                before = encoded(session.world)
                with self.assertRaises(FrozenInstanceError):
                    result.revision = 99
                for slot in result.read.plans[0].slots:
                    with self.assertRaises(TypeError):
                        slot.facts['capacity'] = 999
                    with self.assertRaises(TypeError):
                        slot.facts['fare_offer']['amount_minor'] = 999
                for candidate, rows in captured:
                    candidate['world_state']['services'].clear()
                    rows.clear()
                self.assertEqual(encoded(session.world), before)
                self.assert_index(session)

    def test_final_freshness_real_clock_change_preserves_external_mutation(self):
        for kind in KINDS:
            with self.subTest(command=kind):
                world, request = self.scenario(kind)
                session = self.session(world)
                prepared = self.prepare(session, request)
                index = session._quarterly_indexes.current
                original = QuarterlyIndexOwner.prepare_publication
                changed = []
                def late(owner, proposed, detached):
                    result = original(owner, proposed, detached)
                    # Deliberate test seam; no sanctioned production writer yields here.
                    session.world['simulation']['time_utc'] = '2026-09-01T00:00:01Z'
                    changed.append(encoded(session.world))
                    return result
                with patch.object(QuarterlyIndexOwner, 'prepare_publication', autospec=True, side_effect=late):
                    result = session.apply_quarterly_command(prepared)
                self.assertFalse(result.succeeded)
                # UTC invalidates the index binding before typed comparison.
                self.assertEqual(result.issues[0].code, 'INVALID_REQUEST')
                self.assertEqual(result.issues[0].message, 'stale dependency index')
                self.assertEqual(encoded(session.world), changed[0])
                self.assertIs(session._quarterly_indexes.current, index)

    def test_load_rebind_and_forged_contexts_revoke_every_command(self):
        for kind in KINDS:
            for mode in ('load', 'rebind', 'forged'):
                with self.subTest(command=kind, mode=mode):
                    world, request = self.scenario(kind)
                    session = self.session(world)
                    prepared = self.prepare(session, request)
                    if mode == 'load':
                        session.load_saved(session.career_id)
                    elif mode == 'rebind':
                        session.world = deepcopy(session.world)
                    else:
                        prepared = replace(prepared)
                    before = encoded(session.world)
                    result = session.apply_quarterly_command(prepared)
                    self.assertEqual(result.issues[0].code, 'STALE_CONTEXT')
                    self.assertEqual(encoded(session.world), before)
                    self.differential(session.world, request)

    def test_wrong_owner_and_stale_revision_reference_agree(self):
        world, request = self.scenario('fare')
        session = self.session(world)
        reference = commands.prepare_quarterly_command(world, airline_id=self.owner,
            request=replace(request, expected_revision=99))
        self.assertEqual(session.prepare_quarterly_command(replace(request, expected_revision=99)), reference)
        foreign = next(pid for pid, row in world['world_state']['weekly_plans'].items() if row['airline_id'] != self.owner)
        request = replace(request, weekly_plan_id=foreign)
        before = encoded(session.world)
        reference = commands.prepare_quarterly_command(world, airline_id=self.owner, request=request)
        self.assertEqual(session.prepare_quarterly_command(request), reference)
        self.assertEqual(reference.issues[0].code, 'OWNERSHIP_MISMATCH')
        self.assertEqual(encoded(session.world), before)

    def test_foreign_owner_and_competing_revision_reject_every_command(self):
        foreign = next(owner for owner in self.base['world_state']['airlines'] if owner != self.owner)
        for kind in KINDS:
            with self.subTest(command=kind):
                world, request = self.scenario(kind)
                session = self.session(world)
                prepared = self.prepare(session, request)
                before = encoded(session.world)
                index = session._quarterly_indexes.current
                result = commands.apply_quarterly_command(session.world, airline_id=foreign,
                    prepared=prepared, _indexes=session._quarterly_indexes)
                self.assertEqual(result.issues[0].code, 'OWNERSHIP_MISMATCH')
                self.assertEqual(encoded(session.world), before)
                self.assertIs(session._quarterly_indexes.current, index)
                competing = commands.CreateQuarterlyService('2027-Q1', 'DAB',
                    self.facts(weekdays=[4]), self.pid, 1)
                accepted = session.apply_quarterly_command(self.prepare(session, competing))
                self.assertTrue(accepted.succeeded, accepted.issues)
                before = encoded(session.world)
                index = session._quarterly_indexes.current
                result = session.apply_quarterly_command(prepared)
                self.assertFalse(result.succeeded)
                self.assertIn(result.issues[0].code, {'STALE_CONTEXT', 'STALE_REVISION'})
                self.assertEqual(encoded(session.world), before)
                self.assertIs(session._quarterly_indexes.current, index)

    def test_corrupt_candidate_and_detached_worlds_fail_real_validation(self):
        for kind in KINDS:
            for copy_number in (1, 2):
                with self.subTest(command=kind, copy=copy_number):
                    world, request = self.scenario(kind)
                    session = self.session(world)
                    prepared = self.prepare(session, request)
                    before = encoded(session.world)
                    index = session._quarterly_indexes.current
                    original = commands.deepcopy
                    calls = []
                    def corrupt(value):
                        result = original(value)
                        if type(value) is dict and 'world_state' in value:
                            calls.append(result)
                            if len(calls) == copy_number:
                                result['simulation']['clock_state'] = 'INVALID'
                        return result
                    with patch.object(commands, 'deepcopy', side_effect=corrupt):
                        result = session.apply_quarterly_command(prepared)
                    self.assertFalse(result.succeeded)
                    self.assertEqual(result.issues[0].code, 'INVALID_WORLD')
                    self.assertEqual(encoded(session.world), before)
                    self.assertIs(session._quarterly_indexes.current, index)
                    self.assertTrue(session.apply_quarterly_command(prepared).succeeded)

    def test_private_inplace_mutation_is_not_a_deep_index_guard(self):
        session = self.session()
        self.prepare(session, self.scenario('fare')[1])
        index = session._quarterly_indexes.current
        row = session.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0]
        other = next(aid for aid in session.world['world_state']['aircraft'] if aid != self.aid)
        row['planned_aircraft_id'] = other
        self.assertTrue(index.matches(session.world))
        self.assertNotEqual(independent_edges(session.world)['aircraft_plans'],
                            {key: set(values) for key, values in index._maps['aircraft_plans'].items()})
        # This demonstrates the documented unsupported bypass, not an accepted command.
        session._quarterly_indexes.invalidate()
        self.assertIsNone(session._quarterly_indexes.current)

    def test_post_allocation_failures_and_retry_preserve_all_cursors(self):
        from game.scheduling import quarterly_edits as edits
        for kind, module, seam in (
                ('create', commands, 'create_service'),
                ('create', commands, 'allocate_service_slot'),
                ('create', commands, 'append_weekly_plan_revision'),
                ('replace', commands, 'create_service'),
                ('add', edits, 'allocate_service_slot')):
            with self.subTest(command=kind, seam=seam):
                world, request = self.scenario(kind)
                session = self.session(world)
                prepared = self.prepare(session, request)
                before = encoded(session.world)
                index = session._quarterly_indexes.current
                original = getattr(module, seam)
                def after(*args, **kwargs):
                    original(*args, **kwargs)
                    raise ValueError('after authoritative candidate allocation')
                with patch.object(module, seam, side_effect=after):
                    self.assertFalse(session.apply_quarterly_command(prepared).succeeded)
                self.assertEqual(encoded(session.world), before)
                self.assertIs(session._quarterly_indexes.current, index)
                expected_session, expected = self.differential(world, request)
                actual = session.apply_quarterly_command(prepared)
                self.assertEqual(actual, expected)
                self.assertEqual(encoded(session.world), encoded(expected_session.world))

    def test_latest_prepublication_failure_is_atomic_for_every_command(self):
        for kind in KINDS:
            with self.subTest(command=kind):
                world, request = self.scenario(kind)
                session = self.session(world)
                prepared = self.prepare(session, request)
                before = encoded(session.world)
                index = session._quarterly_indexes.current
                original = commands._sources
                calls = []
                def late(*args, **kwargs):
                    result = original(*args, **kwargs)
                    calls.append(result)
                    self.assertEqual(encoded(session.world), before)
                    self.assertIs(session._quarterly_indexes.current, index)
                    if len(calls) == 2:
                        raise ValueError('after final freshness computation')
                    return result
                with patch.object(commands, '_sources', side_effect=late):
                    self.assertFalse(session.apply_quarterly_command(prepared).succeeded)
                self.assertEqual(len(calls), 2)
                self.assertEqual(encoded(session.world), before)
                self.assertIs(session._quarterly_indexes.current, index)
                self.assertTrue(session.apply_quarterly_command(prepared).succeeded)

    def test_legacy_obligations_neighbors_and_invalidation_reference_agree(self):
        session = self.session()
        self.prepare(session, self.scenario('fare')[1])
        facts = self.facts()
        draft = session.begin_scheduling(self.aid)
        draft.add_weekdays(facts['origin_airport_id'], facts['destination_airport_id'],
                           ['2026-09-07'], '08:00', return_flight=True)
        session.save_scheduling(draft, continuous=True)
        self.assertIsNone(session._quarterly_indexes.current)
        self.prepare(session, self.scenario('fare')[1])
        self.assert_index(session)
        index = session._quarterly_indexes.current
        rows = sorted((datetime.fromisoformat(row['scheduled_off_block_utc'].replace('Z', '+00:00')), fid)
                      for fid, row in session.world['world_state']['dated_flights'].items()
                      if row['planned_aircraft_id'] == self.aid and row['status'] not in {'CANCELLED', 'SUPERSEDED'})
        for time, _ in rows:
            previous = [fid for departure, fid in rows if departure <= time]
            following = [fid for departure, fid in rows if departure > time]
            self.assertEqual(index.neighbors(self.aid, time),
                             (previous[-1] if previous else None, following[0] if following else None))
        _, result = self.differential(session.world, self.scenario('fare')[1], success=False)
        self.assertIn('AIRCRAFT_OVERLAP', result.issues[0].message)

    def test_quarter_boundary_duplicate_lineage_reference_agrees(self):
        session = self.session()
        facts = self.facts()
        aircraft = session.purchase(session.preview_purchase('airbus-a320neo', facts['origin_airport_id']))
        row = deepcopy(session.world['world_state']['weekly_plans'][self.pid]['revisions']['1']['slots'][0])
        row.update(planned_aircraft_id=aircraft, weekdays=[3], departure_local_time='09:50:00')
        create_weekly_plan(session.world, self.owner, '2027-Q2', slots=[row])
        request = commands.ReviseQuarterlySlot(self.pid, 1, self.sid, 1,
            {'weekdays': [3], 'departure_local_time': '07:00:00'})
        _, result = self.differential(session.world, request, success=False)
        self.assertIn('DUPLICATE_OCCURRENCE', result.issues[0].message)

    def test_rebuild_and_mapping_order_do_not_change_command_outcome(self):
        for kind in KINDS:
            with self.subTest(command=kind):
                world, request = self.scenario(kind)
                expected_session, expected = self.differential(world, request)
                shuffled = deepcopy(world)
                for name, rows in shuffled['world_state'].items():
                    if type(rows) is dict:
                        shuffled['world_state'][name] = dict(reversed(list(rows.items())))
                session = self.session(shuffled)
                prepared = self.prepare(session, request)
                session._quarterly_indexes.invalidate()
                actual = session.apply_quarterly_command(prepared)
                self.assertEqual(actual, expected)
                self.assertEqual(encoded(session.world), encoded(expected_session.world))
                self.assert_index(session)


def differential_case(kind):
    def test(self):
        self.differential(*self.scenario(kind))
    return test


def failure_case(seam, gate=None):
    def test(self):
        self.failure_matrix(seam, gate)
    return test


for _kind in KINDS:
    setattr(QuarterlyTransactionTests, 'test_reference_' + _kind, differential_case(_kind))
for _gate in (1, 2, 3):
    setattr(QuarterlyTransactionTests, 'test_rejection_after_apply_gate_' + str(_gate), failure_case('_entry', _gate))
for _seam in ('certify_quarterly_feasibility', 'QuarterlyCommandResult', 'prepare_publication',
              'updated', 'verify_delta', 'rebound'):
    setattr(QuarterlyTransactionTests, 'test_rejection_after_' + _seam, failure_case(_seam))
