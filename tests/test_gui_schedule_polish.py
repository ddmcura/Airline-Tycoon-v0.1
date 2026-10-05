"""Scheduling polish: detached atomic edits and GUI-only interaction state."""

from copy import deepcopy
from datetime import date, timedelta
import tempfile
import unittest
from unittest.mock import patch

from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.relativelayout import RelativeLayout

from app.gui.app import AirlineTycoonApp
from app.gui.date_picker import DatePicker
from app.gui.airport_selector import AirportSelector
from app.gui.drag_block import DraftFlightBlock
from app.gui.scrolling import AxisScrollView
from app.gui.weekday_picker import PRESETS, WeekdayPicker
from app.gui.windowing import configure_startup_window
from app.session import Stage1Session
from game.scheduling import WeeklyDraft
from game.world_state import create_stage1_new_game


def world():
    return create_stage1_new_game(
        scenario_id='stage1-philippines-v1', ceo_display_name='CEO',
        airline_display_name='Test Air', base_airport_reference_code='MNL')


class DraftEditTests(unittest.TestCase):
    def setUp(self):
        self.world = world()
        state = self.world['world_state']
        self.airports = {row['reference_code']: key for key, row in state['airports'].items()}
        self.draft = WeeklyDraft(self.world, airline_id=state['player']['primary_airline_id'],
                                 aircraft_id=next(iter(state['aircraft'])))
        self.monday = date(2026, 9, 7)

    def dates(self, *offsets):
        return tuple((self.monday + timedelta(days=offset)).isoformat() for offset in offsets)

    def add_pair(self):
        return self.draft.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                                      self.dates(0), '08:00', return_flight=True,
                                      fare_minor=11600)

    def test_multi_day_return_uses_authoritative_timing_and_one_undo(self):
        before = deepcopy(self.world)
        self.assertEqual(self.draft.add_weekdays(
            self.airports['MNL'], self.airports['DVO'], self.dates(0, 2, 4),
            '08:00', return_flight=True, fare_minor=11600), 6)
        self.assertEqual([leg['departure_utc'] for leg in self.draft.legs], [
            '2026-09-07T00:00:00Z', '2026-09-07T02:10:00Z',
            '2026-09-09T00:00:00Z', '2026-09-09T02:10:00Z',
            '2026-09-11T00:00:00Z', '2026-09-11T02:10:00Z'])
        self.draft.undo()
        self.assertEqual(self.draft.legs, [])
        self.assertEqual(self.world, before)

    def test_pair_and_multi_day_fail_atomically(self):
        self.add_pair()
        before = self.draft.legs
        with self.assertRaisesRegex(ValueError, '2026-09-07'):
            self.draft.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                                    self.dates(0, 2), '08:00', return_flight=True)
        self.assertEqual(self.draft.legs, before)
        with self.assertRaisesRegex(ValueError, '2026-09-07'):
            self.draft.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                                    self.dates(0), '08:00', return_flight=True)
        self.assertEqual(self.draft.legs, before)
        other = WeeklyDraft(self.world, airline_id=self.draft.airline_id,
                            aircraft_id=self.draft.aircraft_id)
        other.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                           self.dates(4), '08:00', return_flight=True)
        prior = other.legs
        with self.assertRaisesRegex(ValueError, '2026-09-11'):
            other.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                               self.dates(2, 4), '08:00', return_flight=True)
        self.assertEqual(other.legs, prior)

    def test_earliest_and_past_guards(self):
        self.assertEqual(self.draft.add_weekdays(self.airports['MNL'],
                         self.airports['DVO'], self.dates(0), '00:00', earliest=True), 1)
        self.assertEqual(self.draft.legs[0]['departure_utc'], '2026-09-06T16:00:00Z')
        before = self.draft.legs
        with self.assertRaisesRegex(ValueError, 'current local week'):
            self.draft.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                                    ('2026-08-24',), '08:00')
        self.assertEqual(self.draft.legs, before)

    def test_multi_paste_relative_atomic_delete_and_undo(self):
        self.add_pair()
        copied = self.draft.copy_selection([0, 1])
        self.assertEqual(copied['anchor_local_time'], '08:00')
        self.assertEqual(self.draft.paste_weekdays(copied, self.dates(1, 2), '14:00'), 4)
        self.assertEqual([leg['departure_utc'] for leg in self.draft.legs[2:]], [
            '2026-09-08T06:00:00Z', '2026-09-08T08:10:00Z',
            '2026-09-09T06:00:00Z', '2026-09-09T08:10:00Z'])
        before = self.draft.legs
        with self.assertRaisesRegex(ValueError, '2026-09-09'):
            self.draft.paste_weekdays(copied, self.dates(3, 2), '14:00')
        self.assertEqual(self.draft.legs, before)
        self.draft.undo()
        self.assertEqual(len(self.draft.legs), 2)
        self.assertEqual(self.draft.delete_selection([0, 1]), 2)
        self.assertEqual(self.draft.legs, [])
        self.draft.undo()
        self.assertEqual(len(self.draft.legs), 2)

    def test_reschedule_valid_and_invalid_and_published_guard(self):
        self.add_pair()
        before = self.draft.legs
        self.draft.reschedule(0, self.dates(0)[0], '07:50')
        self.assertEqual(self.draft.legs[0]['departure_utc'], '2026-09-06T23:50:00Z')
        self.draft.undo()
        self.assertEqual(self.draft.legs, before)
        with self.assertRaises(ValueError):
            self.draft.reschedule(0, self.dates(0)[0], '10:00')
        self.assertEqual(self.draft.legs, before)
        with self.assertRaises(ValueError):
            self.draft.delete_selection([2])
        self.draft.save_current(self.world)
        fresh = WeeklyDraft(self.world, airline_id=self.draft.airline_id,
                            aircraft_id=self.draft.aircraft_id)
        with self.assertRaises(ValueError):
            fresh.reschedule(0, self.dates(0)[0], '07:50')


class GuiControlTests(unittest.TestCase):
    def test_presets_manual_toggle_and_dates(self):
        days = tuple(date(2026, 9, 7) + timedelta(days=i) for i in range(7))
        picker = WeekdayPicker(days)
        for name, expected in PRESETS.items():
            picker.apply_preset(name)
            self.assertEqual(picker.selected_indices, set(expected))
            self.assertEqual(picker.selected_dates(), tuple(days[i].isoformat()
                             for i in sorted(expected)))
        picker.apply_preset('MWF')
        picker.buttons[1].state = 'down'
        self.assertEqual(picker.selected_indices, {0, 1, 2, 4})

    def test_calendar_selection_and_desktop_window(self):
        picker = DatePicker(selected_date='2026-09-07')
        self.assertEqual(picker.text, '2026-09-07')
        popup = picker.open_calendar()
        self.assertIn('September 2026', picker._month_label.text)
        picker.select('2026-09-09')
        self.assertEqual(picker.text, '2026-09-09')
        popup.dismiss()
        optional = DatePicker(selected_date='', display_date='2026-09-07',
                              allow_clear=True)
        self.assertEqual(optional.text, '')

        class Window:
            fullscreen = True
            maximized = False
            def maximize(self):
                self.maximized = True

        window = Window()
        self.assertTrue(configure_startup_window(window, 'win'))
        self.assertFalse(window.fullscreen)
        self.assertTrue(window.maximized)
        mobile = Window()
        self.assertFalse(configure_startup_window(mobile, 'android'))
        self.assertTrue(mobile.fullscreen)

    def test_nested_scroll_axes_and_touch_size(self):
        outer = AxisScrollView(do_scroll_x=False)
        inner = AxisScrollView(do_scroll_y=False)
        self.assertIn('bars', outer.scroll_type)
        self.assertGreaterEqual(outer.bar_width, 14)
        class Wheel:
            is_mouse_scrolling = True
            button = 'scrolldown'
        self.assertFalse(inner.on_touch_down(Wheel()))
        inner.size = (200, 100)
        inner.add_widget(Widget(size_hint=(None, None), size=(1000, 100)))
        shifted = Wheel()
        shifted.modifiers = ('shift',)
        self.assertTrue(inner.on_touch_down(shifted))
        self.assertGreater(inner.scroll_x, 0)
        class SideWheel:
            is_mouse_scrolling = True
            button = 'scrollright'
        self.assertFalse(outer.on_touch_down(SideWheel()))
        drops = []
        block = DraftFlightBlock(label='DRAFT', color=[0, 1, 0, 1],
                                 on_select=lambda: None, on_drop=drops.append,
                                 size_hint=(None, None), size=(180, 72), pos=(100, 10))
        self.assertGreaterEqual(block.children[0].width, 48)
        block.do_layout()
        handle = block.children[0]
        class Touch:
            is_mouse_scrolling = False
            def __init__(self, x, y):
                self.x, self.y = x, y
                self.pos = (x, y)
            def grab(self, widget):
                self.grab_current = widget
            def ungrab(self, widget):
                self.grab_current = None
        touch = Touch(handle.center_x, handle.center_y)
        self.assertTrue(handle.on_touch_down(touch))
        touch.x += 20
        touch.pos = (touch.x, touch.y)
        self.assertTrue(handle.on_touch_move(touch))
        self.assertTrue(handle.on_touch_up(touch))
        self.assertEqual(drops, [20])
        self.assertEqual(block.x, 100)
        # The scroll container sends handle touches immediately, while its
        # ordinary content still uses Kivy touch scrolling.
        eager = AxisScrollView(do_scroll_y=False, do_scroll_x=True,
                               eager_drag_handles=True, size=(300, 100))
        line = RelativeLayout(size_hint=(None, None), size=(1000, 100))
        line.add_widget(block)
        eager.add_widget(line)
        class StreamTouch(Touch):
            def __init__(self, x, y):
                super().__init__(x, y)
                self.ud = {}
                self.profile = []
                self.stack = []
                self.time_start = 0
            def push(self):
                self.stack.append(self.pos)
            def pop(self):
                self.x, self.y = self.stack.pop()
            def apply_transform_2d(self, operation):
                self.x, self.y = operation(self.x, self.y)
        touch = StreamTouch(handle.center_x, handle.center_y)
        self.assertTrue(eager.on_touch_down(touch))
        self.assertIs(touch.grab_current, handle)
        self.assertIsNone(eager._touch)
        touch.x += 20
        self.assertTrue(handle.on_touch_move(touch))
        self.assertTrue(handle.on_touch_up(touch))
        self.assertEqual(drops, [20, 20])
        self.assertEqual(block.x, 100)


class GuiWorkspacePolishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = AirlineTycoonApp(session_factory=lambda: Stage1Session(
            save_root=self.temp.name, runtime_clock=lambda: 0))
        self.app.build()
        self.app.create_new_game('CEO', 'Builder Air', 'MNL')
        self.app.show_view('Schedule')
        self.app.start_schedule(self.app.session.fleet()[0]['aircraft_id'])
        self.airports = {row['reference_code']: row['airport_id']
                         for row in self.app.session.airports()}

    def tearDown(self):
        self.app._dismiss()
        self.app.on_stop()
        self.temp.cleanup()

    def test_earliest_builder_current_partial_day_and_multiple_days(self):
        app = self.app
        app._builder_origin = self.airports['MNL']
        app._builder_destination = self.airports['CEB']
        app._builder_time = '06:00'
        app._builder_return = False
        app._builder_earliest = False
        self.assertEqual(app.add_builder_flights(target_dates=('2026-09-01',)), 1)
        app._builder_destination = self.airports['DVO']
        app._builder_time = '00:00'
        app._builder_earliest = True
        app._builder_return = True
        self.assertEqual(app.add_builder_flights(target_dates=('2026-09-01', '2026-09-02')), 4)
        self.assertEqual(app._draft.legs[1]['departure_utc'], '2026-09-01T00:30:00Z')
        self.assertEqual(app._draft.legs[2]['departure_utc'], '2026-09-01T02:40:00Z')

    def test_single_insert_earliest_keeps_authoritative_seconds(self):
        app = self.app
        app._draft.add_weekdays(self.airports['MNL'], self.airports['CEB'],
                                ['2026-09-01'], '06:00')
        app._draft.add_weekdays(self.airports['CEB'], self.airports['DVO'],
                                ['2026-09-01'], '08:30')
        app._draft.add_weekdays(self.airports['DVO'], self.airports['MNL'],
                                ['2026-09-01'], '11:00')
        with patch.object(app, '_choice_form') as form:
            app.show_add_leg()
        submit = form.call_args.args[2]
        submit(dict(origin=self.airports['MNL'], destination=self.airports['DVO'],
                    date='2026-09-01', time='08:00', timing='Earliest available',
                    fare='116', service='Passenger', position='Reject'))
        self.assertEqual(app._draft.legs[-1]['departure_utc'], '2026-09-01T00:30:01Z')
        app._draft.validate_current(app.session.world)

    def row_add(self, weekday_index):
        rows = self.app._draft.week_rows(self.app._schedule_week.isoformat())
        airports = {row['airport_id']: row['reference_code']
                    for row in self.app.session.airports()}
        timeline = self.app._timeline(rows, airports)
        days = list(reversed(timeline.children[1].children))
        action = next(widget for widget in days[weekday_index + 1].children
                      if isinstance(widget, Button) and widget.text == '+ Add')
        action.dispatch('on_release')

    def test_recurrence_choices_wire_existing_calendar_and_local_clock(self):
        from kivy.uix.spinner import Spinner
        app = self.app
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        self.assertIn('MNL local (Asia/Manila)', app._departure_caption())
        self.assertIn('08:00:00 Asia/Manila', app.status.text)
        app.show_save_schedule()
        widgets = list(app._popup.content.walk())
        mode = next(widget for widget in widgets if isinstance(widget, Spinner))
        self.assertEqual(tuple(mode.values),
                         ('This week / one-off', 'Repeat until date', 'Continuous recurring'))
        self.assertIsInstance(app._repeat_date_picker, DatePicker)
        self.assertTrue(app._repeat_date_picker.disabled)
        mode.text = 'Repeat until date'
        self.assertFalse(app._repeat_date_picker.disabled)
        popup = app._repeat_date_picker.open_calendar()
        app._repeat_date_picker.select('2026-09-30')
        self.assertEqual(app._repeat_date_picker.text, '2026-09-30')
        self.assertIsNone(app._repeat_date_picker._popup)
        with self.assertRaisesRegex(ValueError, 'calendar'):
            app._review_schedule({'mode': 'Repeat until date', 'repeat': ''})
        mode.text = 'Continuous recurring'
        self.assertTrue(app._repeat_date_picker.disabled)
        popup.dismiss()

    def test_finite_pattern_edit_keeps_repeat_mode_and_calendar_default(self):
        from kivy.uix.spinner import Spinner
        app = self.app
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        app._builder_time = '08:00'
        self.row_add(0)
        app._save_schedule('2026-11-30')
        app._dismiss()
        app.start_schedule(app.session.fleet()[0]['aircraft_id'], edit_recurring=True)
        app.show_save_schedule()
        mode = next(w for w in app._popup.content.walk() if isinstance(w, Spinner))
        self.assertEqual(mode.text, 'Repeat until date')
        self.assertEqual(app._repeat_date_picker.text, '2026-11-30')
        self.assertFalse(app._repeat_date_picker.disabled)

    def test_recurring_edit_reopens_first_unpublished_week_with_protected_blocks(self):
        app = self.app
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        app._builder_time = '08:00'
        self.row_add(0)
        self.assertEqual(len(app._draft.legs), 2)
        app._save_schedule(None, continuous=True)
        self.assertIsNone(app._draft)
        app._dismiss()
        aircraft_id = app.session.fleet()[0]['aircraft_id']
        before = deepcopy(app.session.world['world_state']['dated_flights'])
        app.start_schedule(aircraft_id, edit_recurring=True)
        self.assertEqual(app._schedule_week, date(2026, 10, 5))
        self.assertEqual(app._schedule_day, '2026-10-05')
        self.assertEqual(len(app._draft.legs), 2)
        rows = app._draft.week_rows('2026-10-05')
        self.assertTrue(all(row['draft_index'] is not None for row in rows))
        self.assertEqual(len(rows), 2)
        app._draft.reschedule(0, '2026-10-05', '07:50')
        app._save_schedule(None, continuous=True)
        self.assertEqual(app.session.world['world_state']['dated_flights'], before)

    def test_row_add_uses_builder_exact_time_fare_return_without_dialog(self):
        app = self.app
        app.change_schedule_week(1)
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        self.assertEqual(app._builder_fare, '116')
        app._builder_fare_changed('125')
        app._builder_time = '08:00'
        self.assertTrue(app._builder_return)
        before = app.session.authoritative_bytes()
        with patch.object(app, 'show_add_leg',
                          side_effect=AssertionError('legacy form opened')):
            self.row_add(0)
        self.assertIsNone(app._popup)
        self.assertEqual(app._schedule_day, '2026-09-07')
        self.assertEqual(len(app._draft.legs), 2)
        self.assertEqual([leg['departure_utc'] for leg in app._draft.legs],
                         ['2026-09-07T00:00:00Z', '2026-09-07T02:10:00Z'])
        self.assertEqual([leg['fare_minor'] for leg in app._draft.legs],
                         [12_500, 12_500])
        self.assertEqual([leg['destination_airport_id'] for leg in app._draft.legs],
                         [self.airports['DVO'], self.airports['MNL']])
        self.assertEqual(app.session.authoritative_bytes(), before)
        self.assertEqual(len([row for row in app._draft.week_rows('2026-09-07')
                              if row['departure_local'][:10] == '2026-09-07']), 2)

        # Row targets override checkbox selection, and current builder edits apply.
        app._builder_day_picker.apply_preset('MWF')
        selected_days = set(app._builder_weekdays)
        app._builder_airport_changed('_builder_destination', self.airports['CEB'])
        app._builder_fare_changed('90')
        app._builder_time = '12:00'
        app._builder_return = False
        self.row_add(3)  # Thursday, not selected by MWF.
        self.assertIsNone(app._popup)
        self.assertEqual(app._schedule_day, '2026-09-10')
        self.assertEqual(app._builder_weekdays, selected_days)
        self.assertEqual(len(app._draft.legs), 3)
        thursday = app._draft.legs[-1]
        self.assertEqual(thursday['departure_utc'], '2026-09-10T04:00:00Z')
        self.assertEqual(thursday['destination_airport_id'], self.airports['CEB'])
        self.assertEqual(thursday['fare_minor'], 9_000)
        self.assertEqual(len([row for row in app._draft.week_rows('2026-09-07')
                              if row['departure_local'][:10] == '2026-09-10']), 1)

    def test_row_add_accepts_elapsed_current_week_as_inert_pattern(self):
        app = self.app
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        app._builder_time = '08:00'
        before = app.session.authoritative_bytes()
        self.row_add(0)
        self.assertIsNone(app._popup)
        self.assertEqual(app._schedule_day, '2026-08-31')
        self.assertEqual(len(app._draft.legs), 2)
        self.assertTrue(all(row['pattern_only'] for row in app._draft.week_rows('2026-08-31')))
        self.assertEqual(app.session.authoritative_bytes(), before)
        result = app.session.save_scheduling(app._draft)
        self.assertEqual(result.created_dated_flight_ids, ())
        state = app.session.world['world_state']
        for field in ('dated_flights', 'bookings', 'flight_results', 'active_aircraft_operations', 'transactions'):
            self.assertEqual(state[field], {})

    def test_row_earliest_conflict_and_main_add_share_domain_path(self):
        app = self.app
        app.change_schedule_week(1)
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        app._builder_time = '00:00'
        app._builder_earliest = True
        app._builder_return = True
        expected = deepcopy(app._draft)
        expected.add_weekdays(self.airports['MNL'], self.airports['DVO'],
                              ('2026-09-07',), '00:00', earliest=True,
                              return_flight=True, fare_minor=11_600)
        original = WeeklyDraft.add_weekdays
        calls = []

        def traced(draft, *args, **kwargs):
            calls.append((args, kwargs))
            return original(draft, *args, **kwargs)

        with patch.object(WeeklyDraft, 'add_weekdays', traced):
            self.row_add(0)
            self.assertEqual(app._draft.legs, expected.legs)
            self.assertEqual(calls[0][0][2], ('2026-09-07',))
            self.assertTrue(calls[0][1]['earliest'])
            self.assertTrue(calls[0][1]['return_flight'])
            before = app._draft.legs
            app._builder_earliest = False
            app._builder_time = '00:00'
            self.row_add(0)
            self.assertEqual(app._draft.legs, before)
            self.assertEqual(app._popup.title, 'Add Flight rejected')
            self.assertTrue(any('2026-09-07' in widget.text
                                for widget in app._popup.content.walk()
                                if hasattr(widget, 'text')))
            app._dismiss()

            app._builder_day_picker.apply_preset('MWF')
            app._builder_day_picker.buttons[0].state = 'normal'
            self.assertEqual(app.add_builder_flights(), 4)
            self.assertEqual(calls[-1][0][2],
                             ('2026-09-09', '2026-09-11'))
            self.assertEqual(len(app._draft.legs), 6)
            self.assertEqual(app.session.world['world_state']['dated_flights'], {})
            app.undo_leg()
            self.assertEqual(app._draft.legs, before)

    def test_current_week_builder_defaults_suggestion_override_and_search(self):
        self.assertEqual(self.app._schedule_week, date(2026, 8, 31))
        self.assertEqual(self.app._builder_time, '00:00')
        selector = next(widget for widget in self.app.content.walk()
                        if isinstance(widget, AirportSelector)
                        and widget.selected_id == self.airports['MNL'])
        self.assertEqual(selector.search('Davao')[0]['airport_id'], self.airports['DVO'])
        self.app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        self.assertEqual(self.app._builder_fare, '116')
        self.app._builder_fare_changed('120')
        self.app._builder_airport_changed('_builder_destination', self.airports['CEB'])
        self.assertEqual(self.app._builder_fare, '120')
        self.app._use_suggested_fare()
        self.assertNotEqual(self.app._builder_fare, '120')
        self.assertEqual(selector.search('Bangoy')[0]['airport_id'], self.airports['DVO'])
        self.app.show_add_leg()
        endpoints = [widget for widget in self.app._popup.content.walk()
                     if isinstance(widget, AirportSelector)]
        destination = next(widget for widget in endpoints
                           if widget.selected_id != self.airports['MNL'])
        destination.select(self.airports['DVO'])
        fare = next(widget for widget in self.app._popup.content.walk()
                    if isinstance(widget, TextInput) and widget.text == '116.00')
        fare.text = '120'
        destination.select(self.airports['CEB'])
        self.assertEqual(fare.text, '120')
        self.app._dismiss()

    def test_remaining_current_week_can_be_planned(self):
        app = self.app
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        app._builder_time = '12:00'
        app._builder_day_picker.buttons[1].state = 'down'
        self.assertEqual(app.add_builder_flights(), 2)
        self.assertEqual([row['departure_local'][:10] for row in app._draft.week_rows(
            '2026-08-31') if row['draft_index'] is not None],
            ['2026-09-01', '2026-09-01'])

    def test_builder_pairs_current_week_past_rejection_paste_drag_delete_and_save(self):
        app = self.app
        app._builder_airport_changed('_builder_destination', self.airports['DVO'])
        app._builder_time = '08:00'
        app._builder_day_picker.apply_preset('MWF')
        before = app._draft.legs
        self.assertEqual(app.add_builder_flights(), 6)  # Monday is inert pattern intent.
        self.assertEqual(app.session.world['world_state']['dated_flights'], {})
        app.undo_leg()
        self.assertEqual(app._draft.legs, before)
        app.change_schedule_week(1)
        app._builder_day_picker.apply_preset('MWF')
        self.assertEqual(app.add_builder_flights(), 6)
        self.assertEqual([row['departure_local'][:10] for row in app._draft.week_rows(
            '2026-09-07') if row['draft_index'] is not None], [
                '2026-09-07', '2026-09-07', '2026-09-09', '2026-09-09',
                '2026-09-11', '2026-09-11'])
        app.select_schedule_day('2026-09-07')
        app.copy_day()
        self.assertEqual(app._paste_selected({'targets': ('2026-09-08', '2026-09-10'),
                                              'time': '14:00'}), 4)
        self.assertEqual(app._draft.legs[7]['departure_utc'], '2026-09-08T08:10:00Z')
        before = app._draft.legs
        with self.assertRaises(ValueError):
            app._paste_selected({'targets': ('2026-09-12', '2026-09-09'),
                                 'time': '08:00'})
        self.assertEqual(app._draft.legs, before)
        # Roughly seventeen pixels on the 100 px/hour axis proposes ten minutes.
        self.assertIsNotNone(app.reschedule_from_drag(0, '2026-09-07T08:00:00+08:00', -16.7))
        app.undo_leg()
        self.assertEqual(app._draft.legs, before)
        self.assertIsNone(app.reschedule_from_drag(0, '2026-09-07T08:00:00+08:00', 200))
        self.assertEqual(app._draft.legs, before)
        self.assertEqual(app._popup.title, 'Reschedule rejected')
        app._dismiss()
        app.select_schedule_day('2026-09-08')
        self.assertEqual(app.delete_selected(), 2)
        app.undo_leg()
        self.assertEqual(app._draft.legs, before)
        app.session.save_manual()
        self.assertNotIn(b'WEEKLY_DRAFT_CLIPBOARD_V1', app.session.authoritative_bytes())
        self.assertEqual(app.session.world['world_state']['dated_flights'], {})
