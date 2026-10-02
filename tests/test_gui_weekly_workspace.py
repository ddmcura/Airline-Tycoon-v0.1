"""Searchable airports and graphical weekly draft copy/paste boundaries."""

from copy import deepcopy
import tempfile
import unittest

from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

from app.gui.airport_selector import AirportSelector, airport_identity, matching_airports
from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from game.scheduling import WeeklyDraft
from game.world_state import create_stage1_new_game, validate_world


def new_world():
    return create_stage1_new_game(
        scenario_id='stage1-philippines-v1', ceo_display_name='A',
        airline_display_name='B', base_airport_reference_code='MNL')


class AirportSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = new_world()
        cls.session = Stage1Session()
        cls.session.world = cls.world
        cls.airports = cls.session.airports()
        cls.dvo = next(row for row in cls.airports if row['reference_code'] == 'DVO')

    def test_code_city_name_search_and_authoritative_selection(self):
        for query in ('dvo', 'DaVaO', 'francisco bangoy'):
            matches = matching_airports(self.airports, query)
            self.assertEqual([airport_identity(row) for row in matches],
                             [self.dvo['airport_id']])
        control = AirportSelector(self.airports)
        control.select(self.dvo['airport_id'])
        self.assertEqual(control.selected_id, self.dvo['airport_id'])
        self.assertIn('DVO', control.text)
        self.assertIn(self.dvo['display_name'], control.text)

    def test_interactive_filter_and_touch_sized_results(self):
        control = AirportSelector(self.airports)
        popup = control.open_dropdown()
        search = next(widget for widget in popup.content.walk()
                      if isinstance(widget, TextInput))
        search.text = 'Bangoy'
        buttons = [widget for widget in popup.content.walk()
                   if isinstance(widget, Button)]
        self.assertEqual(len(buttons), 1)
        self.assertGreaterEqual(buttons[0].height, 48)
        buttons[0].dispatch('on_release')
        self.assertEqual(control.selected_id, self.dvo['airport_id'])


class WeeklyDraftClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = new_world()

    def setUp(self):
        self.world = deepcopy(self.base)
        state = self.world['world_state']
        self.airports = {row['reference_code']: key for key, row in state['airports'].items()}
        self.draft = WeeklyDraft(self.world,
            airline_id=state['player']['primary_airline_id'],
            aircraft_id=next(iter(state['aircraft'])))
        self.draft.add(self.airports['MNL'], self.airports['DVO'],
                       departure_utc='2026-09-07T00:00:00Z', fare_minor=11600)
        self.draft.add_return()

    def test_monday_sunday_projection_and_single_copy(self):
        rows = self.draft.week_rows('2026-09-07')
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['draft_index'] for row in rows], [0, 1])
        self.assertEqual(rows[0]['departure_local'][11:16], '08:00')
        self.assertEqual(rows[0]['arrival_local'][11:16], '09:40')
        self.assertEqual(rows[1]['departure_local'][11:16], '10:10')
        self.assertEqual(self.draft.week_rows('2026-09-13'), rows)
        copied = self.draft.copy_selection([1])
        self.assertEqual(len(copied['legs']), 1)
        self.assertEqual(copied['legs'][0]['offset_seconds'], 0)
        self.assertEqual(copied['legs'][0]['origin_airport_id'], self.airports['DVO'])

    def test_multi_copy_relative_paste_and_one_step_undo(self):
        before = deepcopy(self.world)
        copied = self.draft.copy_selection([1, 0])
        self.assertEqual([row['offset_seconds'] for row in copied['legs']], [0, 7800])
        self.assertEqual(self.draft.paste_sequence(copied, '2026-09-09', '14:00'), 2)
        self.assertEqual([row['departure_utc'] for row in self.draft.legs[2:]],
                         ['2026-09-09T06:00:00Z', '2026-09-09T08:10:00Z'])
        self.assertEqual([row['draft_index'] for row in
                          self.draft.week_rows('2026-09-07')], [0, 1, 2, 3])
        self.assertEqual(self.world, before)
        self.draft.undo()
        self.assertEqual(len(self.draft.legs), 2)
        self.assertEqual(self.world, before)

    def test_relative_offsets_cross_local_day_and_week(self):
        world = deepcopy(self.base)
        state = world['world_state']
        airports = {row['reference_code']: key for key, row in state['airports'].items()}
        draft = WeeklyDraft(world, airline_id=state['player']['primary_airline_id'],
                            aircraft_id=next(iter(state['aircraft'])))
        draft.add(airports['MNL'], airports['DVO'],
                  departure_utc='2026-09-07T15:00:00Z')  # Monday 23:00 PH
        draft.add_return()  # Tuesday 01:10 PH
        copied = draft.copy_selection([0, 1])
        draft.paste_sequence(copied, '2026-09-13', '22:00')
        self.assertEqual([leg['departure_utc'] for leg in draft.legs[2:]],
                         ['2026-09-13T14:00:00Z', '2026-09-13T16:10:00Z'])
        self.assertEqual(draft.week_rows('2026-09-14')[-1]['departure_local'][:10],
                         '2026-09-14')

    def test_conflict_rejection_is_atomic_and_suggests_domain_slot(self):
        copied = self.draft.copy_selection([0, 1])
        before = self.draft.legs
        with self.assertRaisesRegex(ValueError, 'Pasted flight 1 rejected') as caught:
            self.draft.paste_sequence(copied, '2026-09-07', '08:00')
        self.assertIn('earliest available start', str(caught.exception))
        self.assertEqual(self.draft.legs, before)
        self.assertTrue(validate_world(self.world).is_valid)


class WeeklyWorkspaceGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = AirlineTycoonApp(session_factory=lambda: Stage1Session(
            save_root=self.tmp.name, runtime_clock=lambda: 0))
        self.app.build()
        self.app.create_new_game('CEO', 'Workspace Air', 'MNL')
        self.app.show_view('Schedule')
        self.app.start_schedule(self.app.session.fleet()[0]['aircraft_id'])
        self.airports = {row['reference_code']: row['airport_id']
                         for row in self.app.session.airports()}

    def tearDown(self):
        self.app._dismiss()
        self.app.on_stop()
        self.tmp.cleanup()

    def plan_monday(self):
        draft = self.app._draft
        draft.add(self.airports['MNL'], self.airports['DVO'],
                  departure_utc='2026-09-07T00:00:00Z', fare_minor=11600)
        draft.add_return()
        self.app.refresh(force=True)

    def test_week_rows_blocks_selection_and_copy_day(self):
        self.plan_monday()
        self.assertEqual(self.app._schedule_week.isoformat(), '2026-09-07')
        buttons = [widget.text for widget in self.app.content.walk()
                   if isinstance(widget, Button)]
        for day in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'):
            self.assertTrue(any(text.startswith(day) for text in buttons), day)
        self.assertTrue(any('MNL -> DVO' in text and '08:00-09:40' in text
                            for text in buttons))
        rows = self.app._draft.week_rows('2026-09-07')
        self.app.select_schedule_block(rows[0])
        self.assertEqual(self.app._schedule_selected, {0})
        self.app.copy_selected()
        self.assertEqual(len(self.app._schedule_clipboard['legs']), 1)
        self.app.select_schedule_day('2026-09-07')
        self.app.copy_day()
        self.assertEqual(self.app._schedule_selected, {0, 1})
        self.assertEqual(len(self.app._schedule_clipboard['legs']), 2)

    def test_gui_paste_conflict_transient_state_and_published_view(self):
        self.plan_monday()
        self.app.select_schedule_day('2026-09-07')
        self.app.copy_day()
        career = self.app.session.save_manual()
        restored = Stage1Session(save_root=self.tmp.name, runtime_clock=lambda: 0)
        restored.load_saved(career)
        self.assertEqual(restored.world['world_state']['dated_flights'], {})
        self.assertNotIn(b'WEEKLY_DRAFT_CLIPBOARD_V1', restored.authoritative_bytes())
        restored.close()
        before = self.app.session.authoritative_bytes()
        self.app._paste_selected({'target': '2026-09-09', 'time': '14:00'})
        self.assertEqual(len(self.app._draft.legs), 4)
        self.assertEqual(self.app._draft.legs[3]['departure_utc'], '2026-09-09T08:10:00Z')
        self.assertEqual(self.app.session.authoritative_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'Pasted flight 1 rejected'):
            self.app._paste_selected({'target': '2026-09-09', 'time': '14:00'})
        self.assertEqual(len(self.app._draft.legs), 4)
        self.app.undo_leg()
        self.assertEqual(len(self.app._draft.legs), 2)
        self.app._paste_selected({'target': '2026-09-09', 'time': '14:00'})
        self.app._save_schedule(None)
        self.app._dismiss()
        self.assertIsNone(self.app._schedule_clipboard)
        self.assertFalse(self.app._schedule_selected)
        self.assertNotIn(b'WEEKLY_DRAFT_CLIPBOARD_V1', self.app.session.authoritative_bytes())
        self.app.session.save_manual()
        career = self.app.session.career_id
        self.app.session.load_saved(career)
        self.app._enter_game()
        self.assertIsNone(self.app._schedule_clipboard)
        self.assertFalse(self.app._schedule_selected)
        self.assertEqual(self.app.session.world['simulation']['clock_state'], 'PAUSED')
        self.app.show_view('Schedule')
        self.app.start_schedule(self.app.session.fleet()[0]['aircraft_id'])
        self.assertTrue(any(row['draft_index'] is None for row in
                            self.app._draft.week_rows('2026-09-07')))

    def test_research_airport_selectors_and_destination_filter(self):
        self.app.show_view('Research')
        origin = self.app._research_origin_selector
        destination = self.app._research_destination_selector
        self.assertEqual(origin.selected_id, self.airports['MNL'])
        self.assertEqual(destination.search('dAvAo')[0]['airport_id'],
                         self.airports['DVO'])
        destination.select(self.airports['DVO'])
        self.assertEqual(self.app._research_destination, self.airports['DVO'])
        self.assertEqual(len(self.app.session.market_opportunities(
            origin_airport_id=self.airports['MNL'], limit=100)), 42)
        visible = [widget.text for widget in self.app.content.children
                   if hasattr(widget, 'text')]
        self.assertEqual(sum('Base daily bookers' in text for text in visible), 1)
