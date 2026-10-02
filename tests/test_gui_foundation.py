"""Kivy foundation checks use a fake runtime clock and isolated careers."""

import os
os.environ.setdefault('KIVY_NO_ARGS', '1')

import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from app.terminal.session import Stage1Session as TerminalCompatibilitySession
from game.world_state.persistence import SaveStore
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput


class FakeClock:
    def __init__(self):
        self.nanoseconds = 0

    def __call__(self):
        return self.nanoseconds

    def advance(self, seconds):
        self.nanoseconds += int(seconds * 1_000_000_000)


class GuiFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.app = AirlineTycoonApp(session_factory=lambda: Stage1Session(
            runtime_clock=self.clock, save_root=self.temp.name))
        self.app.build()

    def tearDown(self):
        self.app._dismiss()
        self.app.on_stop()
        self.temp.cleanup()

    def start(self):
        self.app.create_new_game('CEO', 'Graphical Air', 'MNL')
        self.assertEqual(self.app.screens.current, 'game')
        self.assertTrue(self.app.session.validate())

    def test_new_and_load_forms_are_wired_to_modern_session(self):
        self.app.show_new_game()
        content = self.app._popup.content
        fields = [widget for widget in content.children if isinstance(widget, TextInput)]
        self.assertEqual(len(fields), 2)
        # Kivy stores children in reverse insertion order.
        fields[1].text = 'CEO'
        fields[0].text = 'Graphical Air'
        next(widget for widget in content.children
             if isinstance(widget, Button) and widget.text == 'Create Game').dispatch('on_release')
        self.assertEqual(self.app.screens.current, 'game')
        self.assertTrue(self.app.session.validate())
        self.app.session.save_manual()
        self.app.return_to_title()
        self.app.show_load_game()
        career_button = next(widget for widget in self.app._popup.content.walk()
                             if isinstance(widget, Button) and 'Graphical Air' in widget.text)
        career_button.dispatch('on_release')
        manual_button = next(widget for widget in self.app._popup.content.children
                             if isinstance(widget, Button) and widget.text == 'Current manual save')
        manual_button.dispatch('on_release')
        self.assertEqual(self.app.screens.current, 'game')
        self.assertEqual(self.app.session.world['simulation']['clock_state'], 'PAUSED')

    def test_shared_session_and_no_legacy_gui_imports(self):
        self.assertIs(Stage1Session, TerminalCompatibilitySession)
        self.assertEqual(self.app.screens.screen_names, ['title', 'game'])
        gui_files = (Path('app/gui/app.py'), Path('game/gui/app.py'))
        forbidden = {'game.game_state', 'game.game_loop', 'game.new_game',
                     'game.simulation.daily_tick'}
        for path in gui_files:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            imports = {node.module for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom)}
            self.assertTrue(imports.isdisjoint(forbidden), path)

    def test_new_game_dashboard_navigation_and_read_only_refresh(self):
        self.start()
        session = self.app.session
        self.assertIn('Graphical Air', self.app.identity.text)
        self.assertIn('USD 300,000,000.00', self.app.status.text)
        before = session.authoritative_bytes()
        for view in ('Fleet', 'Flights', 'Finance', 'Saves', 'Overview'):
            self.app.show_view(view)
            self.app.tick(0)
        self.assertEqual(session.authoritative_bytes(), before)
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')

    def test_owned_gui_header_and_overview_avoid_full_history_validation(self):
        self.start()
        session = self.app.session
        before = session.authoritative_bytes()
        with patch('game.aircraft_operations.projections.validate_world',
                   side_effect=AssertionError('redundant aircraft projection validation')), \
             patch('game.simulation.projections.validate_world',
                   side_effect=AssertionError('redundant event projection validation')):
            self.app.show_view('Overview')
            self.app.refresh(force=True)
            self.assertEqual(session.header()['cash_minor'], 30_000_000_000)
        self.assertEqual(session.authoritative_bytes(), before)
        # Public arbitrary-envelope projections retain their validation boundary.
        with patch('game.aircraft_operations.projections.validate_world') as validation:
            validation.return_value.is_valid = False
            self.assertIsNone(session.overview())
            validation.assert_called_once()
        with patch('game.simulation.projections.validate_world') as validation:
            validation.return_value.is_valid = False
            self.assertIsNone(session.next_event())
            validation.assert_called_once()

    def test_successful_advance_report_reads_kernel_validated_event_history(self):
        self.start()
        session = self.app.session
        with patch('game.simulation.projections.validate_world',
                   side_effect=AssertionError('redundant report validation')):
            report = session.advance_seconds(86_400)
        self.assertTrue(report.result.succeeded)
        self.assertTrue(session.validate())
        self.assertTrue(report.event_rows)

    def test_runtime_pump_pause_resume_and_cooperative_jump(self):
        self.start()
        session = self.app.session
        initial = session.world['simulation']['time_utc']
        self.app.resume()
        self.clock.advance(1)
        self.app.tick(0)
        self.assertNotEqual(session.world['simulation']['time_utc'], initial)
        self.assertIn('RUNNING 7x', self.app.status.text)
        self.app.pause()
        paused = session.world['simulation']['time_utc']
        self.clock.advance(30)
        self.app.tick(0)
        self.assertEqual(session.world['simulation']['time_utc'], paused)
        self.app._begin_seconds(60)
        self.assertTrue(session.advancing)
        self.app.tick(0)
        self.assertFalse(session.advancing)
        self.assertTrue(session.validate())
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')

    def test_save_load_bookmarks_and_unsaved_departure(self):
        self.start()
        session = self.app.session
        career_id = session.career_id
        self.app.save_game()
        self.app._dismiss()
        self.assertFalse(session.unsaved_progress)
        session.save_bookmark('Before operations')
        bookmarks = session.list_bookmarks()
        self.assertEqual(len(bookmarks), 1)
        manual = Path(self.temp.name, career_id, 'manual.json').read_bytes()
        session.resume()
        self.assertTrue(session.unsaved_progress)
        self.app._load(career_id, 'bookmark', bookmark_id=bookmarks[0]['bookmark_id'])
        self.assertIsNotNone(self.app._popup)  # Unsaved progress requires a choice.
        buttons = [widget for widget in self.app._popup.content.children
                   if isinstance(widget, Button)]
        next(widget for widget in buttons if widget.text == 'Leave without saving').dispatch('on_release')
        self.assertFalse(session.unsaved_progress)
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')
        self.assertEqual(Path(self.temp.name, career_id, 'manual.json').read_bytes(), manual)
        session.delete_bookmark(bookmarks[0]['bookmark_id'])
        self.assertEqual(session.list_bookmarks(), ())
        self.app.return_to_title()
        self.assertEqual(self.app.screens.current, 'title')
        self.app._load(career_id, 'manual')
        self.assertEqual(self.app.screens.current, 'game')
        self.assertTrue(session.validate())

    def test_newer_autosave_is_offered_without_replacing_manual(self):
        self.start()
        session = self.app.session
        career_id = session.save_manual()
        manual_path = Path(self.temp.name, career_id, 'manual.json')
        original_manual = manual_path.read_bytes()
        session.resume()
        self.clock.advance(15 * 60)
        self.assertTrue(session.maybe_autosave())
        self.app.return_to_title()
        next(widget for widget in self.app._popup.content.children
             if isinstance(widget, Button) and widget.text == 'Leave without saving').dispatch('on_release')
        self.assertEqual(self.app.screens.current, 'title')
        career = session.list_careers()[0]
        self.app._choose_career(career)
        self.assertTrue(any(isinstance(widget, Button) and 'Newer autosave' in widget.text
                            for widget in self.app._popup.content.children))
        next(widget for widget in self.app._popup.content.children
             if isinstance(widget, Button) and 'Newer autosave' in widget.text).dispatch('on_release')
        self.assertEqual(self.app.screens.current, 'game')
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')
        self.assertEqual(manual_path.read_bytes(), original_manual)

    def test_exit_requires_explicit_choice(self):
        self.start()
        self.app.return_to_title()
        self.assertEqual(self.app.screens.current, 'game')
        self.app._dismiss()
        self.app._resolve_departure('cancel', lambda: self.fail('cancel exited'))
        self.app._resolve_departure('save', self.app.return_to_title)
        self.assertEqual(self.app.screens.current, 'title')
        self.assertEqual(len(SaveStore(self.temp.name).list_careers()), 1)


if __name__ == '__main__':
    unittest.main()
