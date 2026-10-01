"""Durable career snapshots, recovery, and terminal session boundaries."""

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.terminal.main import run_terminal
from app.terminal.session import Stage1Session
from game.aircraft_market.step5 import accept_lease, preview_lease
from game.scheduling import create_weekly_round_trip_rotation
from game.simulation import process_events_through
from game.simulation.kernel import configure_clock_ratios, schedule_event
from game.simulation.pacing import NANOSECOND, RuntimeController
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.persistence import SaveError, SaveStore
from game.world_state.timestamps import parse_canonical_utc


class SaveLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(
            scenario_id='stage1-philippines-v1', ceo_display_name='A',
            airline_display_name='Dabudhi Airlines', base_airport_reference_code='MNL')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SaveStore(self.temp.name)
        self.career = self.store.new_career_id()
        self.world = deepcopy(self.base)

    def test_manual_roundtrip_and_airline_career_label(self):
        self.store.save(self.career, 'manual', self.world)
        careers = self.store.list_careers()
        self.assertEqual(len(careers), 1)
        self.assertEqual(careers[0]['airline_name'], 'Dabudhi Airlines')
        restored, _ = self.store.load(self.career)
        self.assertEqual(restored, self.world)
        self.assertTrue(validate_world(restored).is_valid)
        self.assertIsNot(restored, self.world)

    def test_opaque_career_ids_prevent_name_collision_and_lineage_mix(self):
        other_id = self.store.new_career_id()
        self.assertNotEqual(other_id, self.career)
        self.store.save(self.career, 'manual', self.world)
        self.store.save(other_id, 'manual', self.world)
        self.assertEqual(len(self.store.list_careers()), 2)
        other_world = deepcopy(self.world)
        other_world['metadata']['lineage_id'] = 'different-lineage'
        with self.assertRaisesRegex(SaveError, 'lineage'):
            self.store.save(self.career, 'manual', other_world)

    def test_market_obligation_and_inflight_exact_future(self):
        state = self.world['world_state']
        owner = state['player']['primary_airline_id']
        home = state['airlines'][owner]['base_airport_ids'][0]
        offer = state['aircraft_market_state']['active_lease_offer_ids'][0]
        preview = preview_lease(self.world, airline_id=owner, offer_id=offer,
                                contract_type='OPERATING_LEASE', term_years=1,
                                delivery_airport_id=home)
        accept_lease(self.world, preview)
        aircraft_id = next(key for key, aircraft in state['aircraft'].items()
                           if aircraft['model_reference'] == 'A320-200')
        result = create_weekly_round_trip_rotation(
            self.world, airline_id=owner, aircraft_id=aircraft_id,
            destination_airport_reference_code='CEB', fare_minor=10_000,
            first_operating_date='2026-09-07')
        self.assertTrue(result.succeeded)
        departures = [e['due_at_utc'] for e in self.world['world_state']['pending_events'].values()
                      if e['event_type'] == 'STAGE1_FLIGHT_DEPARTURE']
        self.assertTrue(process_events_through(self.world, min(departures)).succeeded)
        self.assertTrue(self.world['world_state']['active_aircraft_operations'])
        self.assertTrue(self.world['world_state']['aircraft_contracts'])
        pending = deepcopy(self.world['world_state']['pending_events'])
        seed = deepcopy(self.world['deterministic_state'])
        instant = self.world['simulation']['time_utc']
        self.store.save(self.career, 'manual', self.world)
        reloaded, _ = self.store.load(self.career)
        self.assertEqual(reloaded['world_state']['pending_events'], pending)
        self.assertEqual(reloaded['deterministic_state'], seed)
        self.assertEqual(reloaded['simulation']['time_utc'], instant)
        self.assertEqual(reloaded['simulation']['clock_state'], 'PAUSED')
        target = '2026-09-07T06:00:00Z'
        paced = deepcopy(reloaded)
        controller = RuntimeController(paced, clock=lambda: 0)
        controller.resume()
        controller.credit_ns = int((parse_canonical_utc(target) -
                                    parse_canonical_utc(instant)).total_seconds()) * NANOSECOND
        for _ in range(100):
            controller.pump()
            if controller.work is None and paced['simulation']['time_utc'] == target:
                break
        else:
            self.fail('7× continuation did not reach its target')
        controller.pause()
        configure_clock_ratios(self.world, normal=7)
        configure_clock_ratios(reloaded, normal=7)
        self.assertTrue(process_events_through(self.world, target).succeeded)
        self.assertTrue(process_events_through(reloaded, target).succeeded)
        self.assertEqual(reloaded, self.world)
        self.assertEqual(paced, self.world)

    def test_same_timestamp_order_survives_reload(self):
        owner = self.world['world_state']['player']['primary_airline_id']
        due = '2026-09-02T00:00:00Z'
        first = schedule_event(self.world, event_type='NO_OP', due_at_utc=due,
                               owner_type='airline', owner_id=owner, priority=50)
        second = schedule_event(self.world, event_type='NO_OP', due_at_utc=due,
                                owner_type='airline', owner_id=owner, priority=50)
        self.store.save(self.career, 'manual', self.world)
        loaded, _ = self.store.load(self.career)
        result = process_events_through(loaded, due)
        self.assertTrue(result.succeeded)
        self.assertLess(result.completed_event_ids.index(first),
                        result.completed_event_ids.index(second))
        self.assertTrue(process_events_through(self.world, due).succeeded)
        self.assertEqual(loaded, self.world)

    def test_autosave_rotation_recovery_and_bookmarks_do_not_write_manual(self):
        self.store.save(self.career, 'manual', self.world, progression_revision=1)
        original = Path(self.temp.name, self.career, 'manual.json').read_bytes()
        bookmark_id = self.store.save(self.career, 'bookmark', self.world,
                                      bookmark_name='Before Fleet Expansion')
        with self.assertRaises(SaveError):
            self.store.save(self.career, 'bookmark', self.world,
                            bookmark_name='before fleet expansion')
        for revision in range(2, 6):
            self.world['world_state']['player']['ceo_display_name'] = f'CEO {revision}'
            self.store.save(self.career, 'autosave', self.world,
                            progression_revision=revision)
        self.assertEqual(len(list(Path(self.temp.name, self.career).glob('autosave-*.json'))), 3)
        self.assertTrue(self.store.newer_autosave(self.career))
        autosave, _ = self.store.load(self.career, 'autosave')
        self.assertEqual(autosave['world_state']['player']['ceo_display_name'], 'CEO 5')
        Path(self.temp.name, self.career, 'autosave-0.json').write_text('{ broken', encoding='utf-8')
        fallback_auto, _ = self.store.load(self.career, 'autosave')
        self.assertEqual(fallback_auto['world_state']['player']['ceo_display_name'], 'CEO 4')
        bookmark, _ = self.store.load(self.career, 'bookmark', bookmark_id=bookmark_id)
        self.assertEqual(bookmark['world_state']['player']['ceo_display_name'], 'A')
        self.assertEqual(Path(self.temp.name, self.career, 'manual.json').read_bytes(), original)
        self.store.delete_bookmark(self.career, bookmark_id)
        self.assertFalse(self.store.list_bookmarks(self.career))

    def test_failed_write_and_load_preserve_valid_state(self):
        self.store.save(self.career, 'manual', self.world)
        path = Path(self.temp.name, self.career, 'manual.json')
        original = path.read_bytes()
        self.world['world_state']['player']['ceo_display_name'] = 'Changed'
        import game.world_state.persistence as persistence
        real_replace = persistence.os.replace

        def fail_target(source, target):
            if Path(target) == path:
                raise OSError('simulated interruption')
            return real_replace(source, target)

        with patch.object(persistence.os, 'replace', side_effect=fail_target):
            with self.assertRaises(SaveError):
                self.store.save(self.career, 'manual', self.world)
        self.assertEqual(path.read_bytes(), original)
        path.write_text('{ broken', encoding='utf-8')
        recovered, info = self.store.load(self.career)
        self.assertEqual(recovered['world_state']['player']['ceo_display_name'], 'A')
        self.assertTrue(info['_recovered_from_previous'])
        path.with_suffix('.previous').write_text('{ broken', encoding='utf-8')
        self.assertTrue(self.store.list_careers()[0]['unreadable'])
        session = Stage1Session(save_root=self.temp.name)
        session.new_game('Other', 'Other Airline', 'CEB')
        before = deepcopy(session.world)
        with self.assertRaises(SaveError):
            session.load_saved(self.career)
        self.assertEqual(session.world, before)

    def test_migration_rejection_and_paused_no_offline_time(self):
        old = deepcopy(self.world)
        old['metadata']['save_schema_version'] = 6
        del old['simulation']['configuration']['maintenance']
        self.assertTrue(validate_world(old).is_valid)
        self.store.save(self.career, 'manual', old)
        loaded, _ = self.store.load(self.career)
        self.assertEqual(loaded['metadata']['save_schema_version'], 7)
        self.assertEqual(loaded['simulation']['time_utc'], old['simulation']['time_utc'])
        self.assertEqual(loaded['simulation']['clock_state'], 'PAUSED')
        self.assertEqual(self.store._read(Path(self.temp.name, self.career, 'manual.json'))['world'], old)
        future = deepcopy(self.world)
        future['metadata']['save_schema_version'] = 8
        self.store.save(self.career, 'manual', self.world)
        path = Path(self.temp.name, self.career, 'manual.json')
        wrapper = json.loads(path.read_text(encoding='utf-8'))
        wrapper['world'] = future
        from game.world_state.persistence import _digest
        wrapper['integrity_sha256'] = _digest({k: v for k, v in wrapper.items()
                                                if k != 'integrity_sha256'})
        path.write_text(json.dumps(wrapper), encoding='utf-8')
        with self.assertRaisesRegex(SaveError, 'newer'):
            self.store.load(self.career)
        future_bytes = path.read_bytes()
        with self.assertRaisesRegex(SaveError, 'newer'):
            self.store.save(self.career, 'manual', self.world)
        self.assertEqual(path.read_bytes(), future_bytes)

    def test_every_supported_sequential_migration_and_schema1_foundation(self):
        from tests.test_stage1_demand_model4_foundation import (
            foundation_snapshot, make_schema1_world)
        from game.world_state.migration import (
            migrate_schema_1_to_2, migrate_schema_2_to_3,
            migrate_schema_3_to_4, migrate_schema_4_to_5,
            migrate_schema_5_to_6, migrate_schema_6_to_7)
        source = make_schema1_world()
        foundation = foundation_snapshot(source)
        steps = (migrate_schema_1_to_2, migrate_schema_2_to_3,
                 migrate_schema_3_to_4, migrate_schema_4_to_5,
                 migrate_schema_5_to_6, migrate_schema_6_to_7)
        for version in range(1, 8):
            with self.subTest(schema=version):
                self.store.save(self.career, 'manual', source)
                path = Path(self.temp.name, self.career, 'manual.json')
                original = path.read_bytes()
                if version == 1:
                    with self.assertRaisesRegex(SaveError, 'foundation'):
                        self.store.load(self.career)
                    loaded, _ = self.store.load(self.career,
                                                foundation_snapshot=foundation)
                else:
                    loaded, _ = self.store.load(self.career)
                self.assertEqual(loaded['metadata']['save_schema_version'], 7)
                self.assertTrue(validate_world(loaded).is_valid)
                self.assertEqual(path.read_bytes(), original)
            if version < 7:
                if version == 1:
                    result = steps[0](source, foundation_snapshot=foundation)
                    self.assertTrue(result.succeeded)
                else:
                    result = steps[version - 1](source)
                    self.assertTrue(result.succeeded, result.as_dict())
                    source = result.migrated_world

    def test_real_active_time_and_simulated_week_triggers_coalesce(self):
        ticks = [0]
        session = Stage1Session(runtime_clock=lambda: ticks[0], save_root=self.temp.name)
        session.new_game('A', 'Dabudhi Airlines', 'MNL')
        ticks[0] = 15 * 60 * 1_000_000_000
        self.assertTrue(session.maybe_autosave())
        self.assertFalse(session.maybe_autosave())
        self.assertEqual(len(list(Path(self.temp.name, session.career_id).glob('autosave-*.json'))), 1)
        # The simulation threshold is evaluated at an ordinary completed boundary.
        self.assertTrue(process_events_through(session.world, '2026-09-08T00:00:00Z').succeeded)
        self.assertTrue(session.maybe_autosave())
        self.assertFalse(session.maybe_autosave())
        session._last_auto_sim_time = '2026-09-01T00:00:00Z'
        session.advance_to('2026-09-15T00:00:00Z')
        self.assertEqual(session._last_auto_sim_time, session.world['simulation']['time_utc'])
        self.assertFalse(session.maybe_autosave())

    def test_terminal_save_return_and_load_by_airline(self):
        inputs = StringIO('1\nA\nDabudhi Airlines\n26\n15\n17\n2\n1\n0\n')
        output = StringIO()
        factory = lambda: Stage1Session(save_root=self.temp.name)
        self.assertEqual(run_terminal(inputs, output, session_factory=factory), 0)
        transcript = output.getvalue()
        self.assertIn('Game saved.', transcript)
        self.assertIn('1. Dabudhi Airlines', transcript)
        self.assertIn('Loaded Dabudhi Airlines', transcript)

    def test_terminal_newer_autosave_and_bookmark_choices_leave_manual_intact(self):
        self.store.save(self.career, 'manual', self.world, progression_revision=1)
        manual_path = Path(self.temp.name, self.career, 'manual.json')
        original = manual_path.read_bytes()
        self.store.save(self.career, 'bookmark', self.world,
                        bookmark_name='Before Leasing', progression_revision=1)
        later = deepcopy(self.world)
        later['world_state']['player']['ceo_display_name'] = 'Later CEO'
        self.store.save(self.career, 'autosave', later, progression_revision=2)
        factory = lambda: Stage1Session(save_root=self.temp.name)
        output = StringIO()
        self.assertEqual(run_terminal(StringIO('2\n1\n\na\n0\n'), output,
                                      session_factory=factory), 0)
        self.assertIn('Newer autosave found', output.getvalue())
        self.assertIn('(paused; autosave)', output.getvalue())
        output = StringIO()
        self.assertEqual(run_terminal(StringIO('2\n1\nb\n1\n0\n'), output,
                                      session_factory=factory), 0)
        self.assertIn('Before Leasing', output.getvalue())
        self.assertIn('(paused; bookmark)', output.getvalue())
        self.assertEqual(manual_path.read_bytes(), original)

    def test_terminal_unsaved_exit_cancel_save_and_return_without_save(self):
        factory = lambda: Stage1Session(save_root=self.temp.name)
        output = StringIO()
        script = '1\nA\nDabudhi Airlines\n26\n0\nc\n0\ns\n'
        self.assertEqual(run_terminal(StringIO(script), output,
                                      session_factory=factory), 0)
        self.assertGreaterEqual(output.getvalue().count('Unsaved progression'), 2)
        self.assertEqual(len(self.store.list_careers()), 1)
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        output = StringIO()
        factory = lambda: Stage1Session(save_root=other.name)
        script = '1\nA\nAnother Airline\n26\n17\nd\n0\n'
        self.assertEqual(run_terminal(StringIO(script), output,
                                      session_factory=factory), 0)
        self.assertIn('Unsaved progression', output.getvalue())
        self.assertFalse(SaveStore(other.name).list_careers())

    def test_bookmark_only_career_loads_from_airline_list(self):
        self.store.save(self.career, 'bookmark', self.world,
                        bookmark_name='Opening Day')
        self.assertFalse(self.store.list_careers()[0]['has_manual'])
        output = StringIO()
        factory = lambda: Stage1Session(save_root=self.temp.name)
        self.assertEqual(run_terminal(StringIO('2\n1\n1\n0\n'), output,
                                      session_factory=factory), 0)
        self.assertIn('Loaded Dabudhi Airlines', output.getvalue())
        self.assertIn('(paused; bookmark)', output.getvalue())


if __name__ == '__main__':
    unittest.main()
