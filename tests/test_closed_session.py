"""Phase 3D ownership, detached reads and complete-world differential checks."""
from copy import deepcopy
from dataclasses import fields, is_dataclass, FrozenInstanceError
from collections.abc import Mapping
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from app.quarterly_planning import QuarterlyPlanningController
from game.simulation import kernel
from game.world_state.persistence import SaveStore, SaveError
from tests.test_simulation_resolver import ph_world, published_pair
from tests.test_stage1_runtime import Clock


def mutable_ids(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return set()
    seen.add(id(value))
    result = {id(value)} if isinstance(value, (dict, list, set)) else set()
    children = (value.values() if isinstance(value, Mapping) else
                value if isinstance(value, (list, tuple, set)) else
                (getattr(value, f.name) for f in fields(value)) if is_dataclass(value) else ())
    for child in children:
        result.update(mutable_ids(child, seen))
    return result


class ClosedSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ph_world()
        cls.operating = published_pair(deepcopy(cls.base))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.session = self.make()
        self.session.world = self.base

    def make(self, closed=True):
        return Stage1Session(closed_owner=closed, save_root=self.temp.name,
                             runtime_clock=self.clock)

    def exported(self, session=None):
        return json.loads((session or self.session).authoritative_bytes())

    def test_foreign_acquisition_detaches_nested_retained_references(self):
        foreign = deepcopy(self.base)
        self.session.world = foreign
        before = self.session.authoritative_bytes()
        self.assertFalse(mutable_ids(foreign) & mutable_ids(self.session._world))
        foreign['world_state']['aircraft'].clear()
        self.assertEqual(before, self.session.authoritative_bytes())
        self.assertEqual(self.session.ownership_counts()['acquisition_clones'], 2)

    def test_invalid_alias_and_compatibility_input_preserve_binding(self):
        before = self.session.authoritative_bytes()
        binding = self.session.binding_revision
        invalid = deepcopy(self.base)
        invalid['simulation']['time_utc'] = 'bad'
        with self.assertRaises(ValueError): self.session.world = invalid
        aliased = deepcopy(self.base)
        aliased['extra'] = aliased['simulation']
        with self.assertRaises(ValueError): self.session.world = aliased
        class Key(str): pass
        compatibility = {Key(k): v for k, v in self.base.items()}
        with self.assertRaises(ValueError): self.session.world = compatibility
        self.assertEqual(binding, self.session.binding_revision)
        self.assertEqual(before, self.session.authoritative_bytes())

    def test_public_authority_and_indirect_controller_access_denied(self):
        s = self.session
        s._ensure_runtime()
        for name in ('world', 'runtime', 'save_store'):
            with self.assertRaises(AttributeError): getattr(s, name)
        for name in ('runtime', 'save_store', 'closed_owner'):
            with self.assertRaises(AttributeError): setattr(s, name, None)
        view = s.runtime_view()
        self.assertFalse(hasattr(view, 'world'))
        self.assertFalse(hasattr(view, 'work'))
        with self.assertRaises(FrozenInstanceError): view.credit_ns = 100
        self.assertFalse(mutable_ids(view) & mutable_ids(s._world))

    def test_named_reads_detached_and_no_full_exports(self):
        s = self.session
        s._ensure_runtime()
        aircraft = next(iter(self.base['world_state']['aircraft']))
        reads = [s.header(), s.fleet(), s.flights(), s.finances(), s.airports(),
                 s.aircraft_details(aircraft), s.scheduling_aircraft(aircraft),
                 s.next_event_for_display(), s.operational_context(), s.service_markets(),
                 s.management_fleet(), s.aircraft_contracts(), s.leasing_offers(),
                 s.used_listings(), s.runtime_view()]
        for result in reads:
            self.assertFalse(mutable_ids(result) & mutable_ids(s._world))
        reads[0]['base_airports'].clear()
        self.assertTrue(s.header()['base_airports'])
        self.assertEqual(s.ownership_counts(), dict(acquisitions=1, acquisition_clones=1,
                                                  full_world_exports=0))

    def test_successive_requests_exact_results_worlds_and_copy_counts(self):
        s = self.session
        s.world = self.operating
        legacy = self.make(False)
        legacy.world = deepcopy(self.operating)
        observed = []
        for session in (legacy, s):
            with patch.object(kernel, '_clone_runtime_world', wraps=kernel._clone_runtime_world) as clones:
                reports = [session.advance_next_event(), session.advance_next_event()]
                session.header(); session.fleet(); session.runtime_view()
                observed.append((reports, clones.call_count))
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(s.ownership_counts(), dict(acquisitions=2, acquisition_clones=2,
                                                  full_world_exports=0))
        self.assertEqual(self.exported(), self.exported(legacy))
        self.assertEqual(s.authoritative_bytes(), legacy.authoritative_bytes())
        for report in observed[1][0]:
            self.assertFalse(mutable_ids(report) & mutable_ids(s._world))

    def test_cooperative_shared_requests_match_legacy_complete_world(self):
        from datetime import timedelta
        from game.world_state.timestamps import parse_canonical_utc, format_utc
        source = deepcopy(self.base)
        now = source['simulation']['time_utc']
        owner = source['world_state']['player']['primary_airline_id']
        for _ in range(12):
            kernel.schedule_event(source, event_type='NO_OP', due_at_utc=now,
                                  owner_type='airline', owner_id=owner)
        target = format_utc(parse_canonical_utc(now) + timedelta(seconds=30))
        outcomes = []
        for s in (self.make(False), self.session):
            s.world = deepcopy(source)
            outcomes.append((s.advance_to(target), s.advance_seconds(1)))
            s.header(); s.fleet()
            if s.closed_owner:
                self.assertEqual(s.ownership_counts()['full_world_exports'], 0)
            outcomes[-1] += (s.authoritative_bytes(),)
        self.assertEqual(outcomes[0], outcomes[1])

    def test_new_load_transfer_no_redundant_owner_clone_failed_load_safe(self):
        s = self.make()
        s.new_game('CEO', 'Private Air', 'MNL')
        self.assertEqual(s.ownership_counts()['acquisition_clones'], 0)
        career = s.save_manual()
        before = s.authoritative_bytes()
        binding = s.binding_revision
        with self.assertRaises(SaveError): s.load_saved('missing-career')
        self.assertEqual(binding, s.binding_revision)
        self.assertEqual(before, s.authoritative_bytes())

        data = s.load_saved(career)
        self.assertEqual(s.ownership_counts()['acquisitions'], 2)
        self.assertEqual(s.ownership_counts()['acquisition_clones'], 0)
        self.assertEqual(self.exported(s)['simulation']['clock_state'], 'PAUSED')
        self.assertFalse(mutable_ids(data) & mutable_ids(s._world))
        data['world']['world_state']['aircraft'].clear()
        self.assertEqual(before, s.authoritative_bytes())

    def test_quarterly_new_game_transfers_private_constructor_result(self):
        s = self.make()
        s.new_quarterly_development_game('CEO', 'Closed Quarterly', 'MNL')
        self.assertTrue(s.quarterly_career)
        self.assertEqual(s.ownership_counts(), dict(acquisitions=1, acquisition_clones=0,
                                                  full_world_exports=0))
        self.assertEqual(s.quarterly_planning_page()['rows'], [])

    def test_save_failure_preserves_previous_file(self):
        s = self.make(); s.new_game('CEO', 'Saved Air', 'MNL')
        career = s.save_manual()
        store = SaveStore(self.temp.name)
        saved, _ = store.load(career)
        with patch('game.world_state.persistence.os.replace', side_effect=OSError('injected')):
            with self.assertRaises(SaveError): s.save_manual()
        actual, _ = store.load(career)
        self.assertEqual(saved, actual)

    def test_pause_cooperative_requests_close_rebind_and_stale_reads(self):
        s = self.session
        old = s.header(); binding = s.binding_revision
        s.resume(); self.clock.advance(1_000_000_000)
        s.pump(); s.pause()
        for _ in range(100):
            if not s.runtime_view().draining: break
            s.pump()
        self.assertFalse(s.runtime_view().processing)
        s.advance_seconds(1); s.advance_seconds(1)
        self.assertEqual(binding, s.binding_revision)
        self.assertEqual(s.ownership_counts()['acquisitions'], 1)
        s.close(); self.assertTrue(s.runtime_view().closed)
        s.new_game('Replacement', 'Rebound', 'MNL')
        self.assertNotEqual(binding, s.binding_revision)
        old['base_airports'].clear()
        self.assertTrue(s.header()['base_airports'])
        s.leave_game(); self.assertFalse(s.active); self.assertIsNone(s.runtime_view())

    def test_builtin_planner_detached_custom_callback_refused_and_stale_draft(self):
        s = self.session
        aircraft = next(iter(self.base['world_state']['aircraft']))
        draft = s.begin_scheduling(aircraft)
        checked = s.validate_scheduling(deepcopy(draft))
        self.assertFalse(mutable_ids(checked._base) & mutable_ids(s._world))
        class Foreign:
            def save_current(self, world, **options):
                raise AssertionError('must not receive authority')
        with self.assertRaises(ValueError): s.save_scheduling(Foreign())
        s.world = self.base
        with self.assertRaisesRegex(ValueError, 'stale'): s.validate_scheduling(draft)

    def test_planner_management_results_and_whole_world_match_legacy(self):
        sessions = (self.make(False), self.session)
        results = []
        for s in sessions:
            s.world = deepcopy(self.base)
            aircraft = next(iter(self.base['world_state']['aircraft']))
            ports = {row['reference_code']: row['airport_id'] for row in s.airports()}
            draft = s.begin_scheduling(aircraft)
            draft.add_weekdays(ports['MNL'], ports['DVO'], ('2026-08-31',), '08:00',
                               return_flight=True, fare_minor=11600)
            s.validate_scheduling(deepcopy(draft))
            results.append(s.save_scheduling(draft))
            self.assertFalse(mutable_ids(draft._base) & mutable_ids(s._world))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.exported(sessions[0]), self.exported(sessions[1]))
        self.assertEqual(sessions[0].authoritative_bytes(), sessions[1].authoritative_bytes())

    def test_quarterly_controller_edits_detached_results_and_stale_preparation(self):
        from tests.test_quarterly_backend import QuarterlyBackendTests
        from game.scheduling.quarterly_commands import ReviseQuarterlyFare
        source, pid, sid, _, _, _ = QuarterlyBackendTests.fixture(quarter='2027-Q2', published=False)
        s = self.session; s.world = source
        controller = QuarterlyPlanningController(s)
        page = controller.refresh()
        row = page['rows'][0]
        controller.select_slot((row['service_id'], row['slot_number']))
        result = controller.fare(12000)
        self.assertTrue(result.succeeded, result.issues)
        self.assertFalse(mutable_ids(result) & mutable_ids(s._world))
        prepared = s.prepare_quarterly_command(ReviseQuarterlyFare(pid, result.revision, sid,
                        row['slot_number'], {'currency':'USD','amount_minor':13000}))
        self.assertTrue(prepared.succeeded, prepared.issues)
        s.world = source
        self.assertFalse(s.apply_quarterly_command(prepared.prepared).succeeded)
        controller.refresh()
        self.assertIsNone(controller.selected)
        page['rows'].clear()
        self.assertTrue(s.quarterly_planning_page()['rows'])

    def test_failed_event_retry_preserves_exact_prefix_and_owner(self):
        source = deepcopy(self.base)
        owner = source['world_state']['player']['primary_airline_id']
        now = source['simulation']['time_utc']
        for _ in range(2):
            kernel.schedule_event(source, event_type='NO_OP', due_at_utc=now,
                                  owner_type='airline', owner_id=owner)
        results = []
        for s in (self.make(False), self.session):
            s.world = source if s.closed_owner else deepcopy(source)
            first = s.advance_next_event()
            before = s.authoritative_bytes()
            def fail(context):
                context.envelope['world_state']['history']['operations'].append('uncommitted')
                raise RuntimeError('injected')
            with patch.object(kernel.DEFAULT_EVENT_HANDLERS, 'handler_for', return_value=fail):
                failed = s.advance_next_event()
            self.assertFalse(failed.result.succeeded)
            self.assertEqual(before, s.authoritative_bytes())
            retried = s.advance_next_event()
            self.assertTrue(retried.result.succeeded)
            results.append((first, failed, retried, s.authoritative_bytes()))
        self.assertEqual(results[0], results[1])


if __name__ == '__main__':
    unittest.main()
