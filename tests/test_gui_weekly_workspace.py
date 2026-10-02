"""Searchable airports and graphical weekly draft copy/paste boundaries."""

from copy import deepcopy
from datetime import date, timedelta
import tempfile
import unittest

from kivy.uix.button import Button
from kivy.uix.relativelayout import RelativeLayout
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

    def week_grid(self):
        rows = self.app._draft.week_rows(self.app._schedule_week.isoformat())
        airports = {row['airport_id']: row['reference_code']
                    for row in self.app.session.airports()}
        outer = self.app._timeline(rows, airports)
        day_widgets = list(reversed(outer.children[1].children))
        time_widgets = list(reversed(outer.children[0].children[0].children))
        return outer, day_widgets, time_widgets

    def test_seven_weekday_controls_dates_and_add_targets(self):
        self.assertEqual(self.app._schedule_week, date(2026, 9, 7))
        expected = [date(2026, 9, 7) + timedelta(days=offset)
                    for offset in range(7)]
        self.assertEqual(self.app._week_dates(), tuple(expected))
        outer, days, lines = self.week_grid()
        self.assertEqual(len(days), 8)  # one header and exactly seven days
        self.assertEqual(len(lines), 8)
        self.assertEqual(days[0].text, 'DAY / ACTION')
        self.assertIsInstance(lines[0], RelativeLayout)
        self.assertEqual(days[0].height, lines[0].height)
        self.assertEqual(outer.height, days[0].height * 8)
        self.assertEqual(outer.children[1].height, outer.children[0].height)
        self.assertEqual(outer.children[0].children[0].height, outer.height)
        add_targets = []
        self.app.show_add_leg = lambda target_date=None: add_targets.append(target_date)
        for offset, day in enumerate(expected):
            actions = days[offset + 1]
            choose = next(widget for widget in actions.children
                          if isinstance(widget, Button) and 'Select Day' in widget.text)
            add = next(widget for widget in actions.children
                       if isinstance(widget, Button) and widget.text == '+ Add')
            self.assertEqual(choose.text.split('\n')[0], f'{day:%a %d %b}')
            choose.dispatch('on_release')
            self.assertEqual(self.app._schedule_day, day.isoformat())
            self.assertTrue(any(f'Day: {day.isoformat()}' in widget.text
                                for widget in self.app.content.walk()
                                if hasattr(widget, 'text')))
            add.dispatch('on_release')
        self.assertEqual(add_targets, [day.isoformat() for day in expected])
        del self.app.show_add_leg
        add_form = {}
        self.app._choice_form = lambda title, fields, submit, **kwargs: add_form.update(
            {key: initial for key, _label, _choices, initial in fields})
        self.app.show_add_leg('2026-09-07')
        self.assertEqual(add_form['date'], '2026-09-07')
        self.assertEqual(self.app._schedule_day, '2026-09-07')
        self.assertTrue(any('Day: 2026-09-07' in widget.text
                            for widget in self.app.content.walk()
                            if hasattr(widget, 'text')))
        self.app._schedule_week = date(2026, 12, 28)
        self.assertEqual(self.app._week_dates()[-1], date(2027, 1, 3))
        self.app.change_schedule_week(1)
        self.assertEqual(self.app._schedule_week, date(2027, 1, 4))
        self.assertEqual(self.app._schedule_day, '2027-01-04')
        self.assertEqual(self.app._week_dates()[-1], date(2027, 1, 10))

    def test_flights_render_in_exact_weekday_rows_and_paste_targets(self):
        self.plan_monday()
        self.app.select_schedule_day('2026-09-07')
        self.app.copy_day()
        captured = {}
        self.app._choice_form = lambda title, fields, submit, **kwargs: captured.update(
            {key: (choices, initial) for key, _label, choices, initial in fields})
        self.app.show_paste()
        self.assertEqual(captured['target'][0], tuple(
            (date(2026, 9, 7) + timedelta(days=offset)).isoformat()
            for offset in range(7)))
        self.assertEqual(captured['target'][1], '2026-09-07')
        self.app._paste_selected({'target': '2026-09-09', 'time': '14:00'})
        rows = self.app._draft.week_rows('2026-09-07')
        self.assertEqual([row['departure_local'][:10] for row in rows],
                         ['2026-09-07', '2026-09-07',
                          '2026-09-09', '2026-09-09'])
        self.assertEqual(self.app._schedule_day, '2026-09-09')
        _, days, lines = self.week_grid()
        self.assertEqual(len(days), 8)
        self.assertEqual([len(line.children) for line in lines[1:]],
                         [2, 0, 2, 0, 0, 0, 0])
        self.assertTrue(all(isinstance(line, RelativeLayout) for line in lines))
        self.assertTrue(all(block.y == 10 for line in (lines[1], lines[3])
                            for block in line.children))
        lines[0].parent.do_layout()
        self.assertEqual(lines[1].top, lines[0].y)
        for line in (lines[1], lines[3]):
            for block in line.children:
                rendered_y = block.to_window(*block.pos)[1]
                self.assertGreaterEqual(rendered_y, line.y)
                self.assertLessEqual(rendered_y + block.height, line.top)
        self.assertGreater(lines[1].children[0].to_window(*lines[1].children[0].pos)[1],
                           lines[7].top)
        self.assertEqual(sorted(block.text.split('\n')[1][:11]
                                for block in lines[1].children),
                         ['08:00-09:40', '10:10-11:50'])
        self.assertEqual(sorted(block.text.split('\n')[1][:11]
                                for block in lines[3].children),
                         ['14:00-15:40', '16:10-17:50'])
        self.app.select_schedule_day('2026-09-07')
        self.app.copy_day()
        self.assertEqual(len(self.app._schedule_clipboard['legs']), 2)
        self.assertEqual([leg['offset_seconds'] for leg in
                          self.app._schedule_clipboard['legs']], [0, 7800])

    def test_each_of_seven_days_owns_only_its_departing_blocks(self):
        self.plan_monday()
        copied = self.app._draft.copy_selection([0, 1])
        for day in self.app._week_dates()[1:]:
            self.app._draft.paste_sequence(copied, day.isoformat(), '08:00')
        _, days, lines = self.week_grid()
        self.assertEqual(len(days), 8)
        self.assertEqual(len(lines), 8)
        for offset, day in enumerate(self.app._week_dates()):
            self.assertEqual(len(lines[offset + 1].children), 2, day)
            self.assertTrue(all('DRAFT' in block.text
                                for block in lines[offset + 1].children))
            self.assertEqual(days[offset + 1].children[-1].text.split('\n')[0],
                             f'{day:%a %d %b}')

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
