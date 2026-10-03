"""Kivy weekly aircraft workspace over the transient domain WeeklyDraft."""

from copy import deepcopy
from datetime import date, datetime, timedelta

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.relativelayout import RelativeLayout

from app.inputs import parse_usd_fare
from app.gui.scrolling import AxisScrollView
from game.scheduling.weekly import local_departure, monday
from game.world_state.timestamps import format_utc
from app.gui.schedule_builder import ScheduleBuilder
from app.gui.drag_block import DraftFlightBlock
from app.gui.weekday_picker import WeekdayPicker


class WeeklyWorkspace(ScheduleBuilder):
    """Presentation, intent and clipboard; schedule authority stays in game.scheduling."""

    def render_scheduling(self):
        from app.gui.app import _button, _label
        self.content.add_widget(_label('WEEKLY AIRCRAFT SCHEDULE', height=48))
        if self._draft is None:
            self.content.add_widget(_label(
                'Select an aircraft to plan its Monday-Sunday week. Future availability is validated.',
                height=68))
            for row in self.session.fleet(offset=0, limit=100):
                if row['status'] in {'PARKED', 'IN_FLIGHT'}:
                    self.content.add_widget(_button(
                        f"Plan {row['display_registration']} - {row['model_reference']} at "
                        f"{row['current_airport_reference_code'] or row['status']}",
                        lambda item=row: self.start_schedule(item['aircraft_id'])))
                    if self.session.has_recurring_pattern(row['aircraft_id']):
                        self.content.add_widget(_button(
                            f"Edit recurring pattern - {row['display_registration']}",
                            lambda item=row: self.start_schedule(item['aircraft_id'], edit_recurring=True)))
        else:
            draft = self._draft
            aircraft = self.session.scheduling_aircraft(draft.aircraft_id) or self._schedule_aircraft
            airports = {row['airport_id']: row['reference_code']
                        for row in self.session.airports()}
            rows = draft.week_rows(self._schedule_week.isoformat())
            draft_count = sum(row['draft_index'] is not None for row in rows)
            published_count = sum(row.get('published', row['draft_index'] is None) for row in rows)
            preview_count = len(rows) - draft_count - published_count
            week_end = self._schedule_week + timedelta(days=6)
            week_label = (f'{self._schedule_week:%b} {self._schedule_week.day}–'
                          + (f'{week_end.day}, {week_end.year}'
                             if self._schedule_week.month == week_end.month else
                             f'{week_end:%b} {week_end.day}, {week_end.year}'))
            self.content.add_widget(_label(
                f"{aircraft['display_registration']} - {self._schedule_model_label}  |  "
                f"Home {aircraft['home_airport_reference_code']}  |  "
                f"Current {aircraft['current_airport_reference_code'] or aircraft['status']}\n"
                f"Week: {week_label} ({draft.context_timezone})  |  "
                f"{draft_count} draft / {published_count} published / {preview_count} pattern previews", height=78))
            if draft.revision_from:
                self.content.add_widget(_label(
                    f'Recurring pattern replacement effective week: {draft.revision_from}. '
                    'Published/booked flights stay unchanged.', height=70))
            self.content.add_widget(_label(
                'Green blocks are unpublished draft flights; gray blocks are already published. '
                'Elapsed slots are pattern only and never operate retroactively. '
                'This draft is local until Publish Schedule and is not in a game save.', height=78))
            self.content.add_widget(self._horizontal_buttons([
                ('Previous week', lambda: self.change_schedule_week(-1)),
                ('Next week', lambda: self.change_schedule_week(1)),
                ('Advanced single flight', self.show_add_leg),
                ('Edit recurring pattern', self.edit_recurring_schedule),
                ('Add earliest return', self.add_return),
            ]))
            self._render_builder()
            self.content.add_widget(self._timeline(rows, airports))
            self.content.add_widget(_label(
                f"Selected: {len(self._schedule_selected)} draft flight(s)  |  "
                f"Clipboard: {len(self._schedule_clipboard['legs']) if self._schedule_clipboard else 0} "
                f"flight(s)  |  Day: {self._schedule_day}", height=60))
            if len(self._schedule_selected) == 1:
                index = next(iter(self._schedule_selected))
                selected = next((row for row in rows if row['draft_index'] == index), None)
                if selected is not None:
                    leg = draft.legs[index]
                    self.content.add_widget(_label(
                        f"Selected draft: {airports[selected['origin_airport_id']]} -> "
                        f"{airports[selected['destination_airport_id']]}  "
                        f"{selected['departure_local'][11:16]}-"
                        f"{selected['arrival_local'][11:16]}  "
                        f"{leg['service_type']}  Fare {self._money(leg['fare_minor'])}", height=62))
            self.content.add_widget(self._horizontal_buttons([
                ('Copy Selected', self.copy_selected), ('Copy Day', self.copy_day),
                ('Paste', self.show_paste), ('Delete Selected', self.delete_selected),
                ('Undo', self.undo_leg),
                ('Review & Publish', self.show_save_schedule),
                ('Discard Draft', self.discard_schedule),
            ]))
        # Graphical recurrence is managed by the rolling publisher.
        # The legacy single-day rotation command remains in the terminal API.

    def _timeline(self, rows, airports):
        hour_width, row_height = dp(100), dp(94)
        width = hour_width * 24 + dp(100)
        grid_height = row_height * 8
        outer = BoxLayout(orientation='horizontal', size_hint_y=None,
                          height=grid_height)
        days = BoxLayout(orientation='vertical', size_hint=(None, None),
                         width=dp(180), height=grid_height)
        days.add_widget(Label(text='DAY / ACTION', size_hint_y=None, height=row_height))
        timeline = AxisScrollView(do_scroll_y=False, do_scroll_x=True,
                                  eager_drag_handles=True,
                              size_hint_y=None, height=grid_height)
        timeline.scroll_x = self._schedule_scroll_x
        timeline.bind(scroll_x=lambda _widget, value: setattr(self, '_schedule_scroll_x', value))
        column = BoxLayout(orientation='vertical', size_hint=(None, None),
                           width=width, height=grid_height)
        # RelativeLayout keeps each hour label and flight block in its own
        # header/day coordinate space as the outer week scrolls vertically.
        header = RelativeLayout(size_hint=(None, None), size=(width, row_height))
        for hour in range(0, 25, 4):
            header.add_widget(Label(text=f'{hour:02d}:00', size_hint=(None, None),
                                    size=(dp(76), dp(52)),
                                    pos=(hour_width * hour, dp(20))))
        column.add_widget(header)
        for day in self._week_dates():
            day_rows = sorted((row for row in rows if row.get('timeline_departure_local', row['departure_local'])[:10] == day.isoformat()),
                              key=lambda row: row['departure_local'])
            actions = BoxLayout(orientation='horizontal', size_hint_y=None,
                                height=row_height, spacing=dp(3))
            chosen = day.isoformat() == self._schedule_day
            choose = Button(text=f'{day:%a %d %b}\nSelect Day', size_hint_x=None,
                            width=dp(105), background_normal='',
                            background_color=([.16, .57, .84, 1] if chosen else
                                              [.42, .43, .45, 1]))
            choose.bind(on_release=lambda _button, target=day.isoformat():
                        self.select_schedule_day(target))
            if day == self._schedule_week:
                self._schedule_monday_button = choose
            actions.add_widget(choose)
            add = Button(text='+ Add')
            add.bind(on_release=lambda _button, target=day.isoformat():
                     self.add_builder_flights(target_dates=(target,)))
            actions.add_widget(add)
            days.add_widget(actions)
            line = RelativeLayout(size_hint=(None, None), size=(width, row_height))
            for row in day_rows:
                start = datetime.fromisoformat(row.get('timeline_departure_local', row['departure_local']))
                end = datetime.fromisoformat(row.get('timeline_arrival_local', row['arrival_local']))
                display_start = datetime.fromisoformat(row['departure_local'])
                display_end = datetime.fromisoformat(row['arrival_local'])
                hour = start.hour + start.minute / 60 + start.second / 3600
                # Coordinates only: duration comes from the domain's projected timestamps.
                visual_width = max(dp(180), (end - start).total_seconds() / 3600 * hour_width)
                index = row['draft_index']
                selected = index is not None and index in self._schedule_selected
                color = ([.16, .57, .84, 1] if selected else
                         [.23, .55, .28, 1] if index is not None else
                         [.42, .43, .45, 1] if row.get('published', True) else [.39, .30, .52, 1])
                state_label = ('PATTERN ONLY' if index is not None and row.get('pattern_only')
                               else 'DRAFT' if index is not None
                               else 'PUBLISHED' if row.get('published', True)
                               else 'PATTERN PREVIEW')
                label = (f"{airports[row['origin_airport_id']]} -> "
                         f"{airports[row['destination_airport_id']]}\n"
                         f"{display_start:%H:%M}-{display_end:%H:%M}"
                         + (f" ({display_end:%d %b})" if display_end.date() != display_start.date() else '')
                         + f"\n{state_label}")
                if row.get('departure_timezone') != self._draft.context_timezone or row.get('arrival_timezone') != self._draft.context_timezone:
                    label += f"\n{row['departure_timezone']} / {row['arrival_timezone']}"
                geometry = dict(size_hint=(None, None),
                                size=(visual_width, dp(72)),
                                pos=(hour * hour_width, dp(10)))
                if index is None:
                    block = Button(text=label, background_normal='',
                                   background_color=color, font_size='13sp',
                                   **geometry)
                    block.bind(on_release=lambda _button, item=row:
                               self.select_schedule_block(item))
                else:
                    block = DraftFlightBlock(
                        label=label, color=color,
                        on_select=lambda item=row: self.select_schedule_block(item),
                        on_drop=lambda delta, draft_index=index, local=row.get('timeline_departure_local', row['departure_local']):
                        self.reschedule_from_drag(draft_index, local, delta),
                        **geometry)
                line.add_widget(block)
            column.add_widget(line)
        timeline.add_widget(column)
        outer.add_widget(days)
        outer.add_widget(timeline)
        return outer

    def _week_dates(self):
        return tuple(self._schedule_week + timedelta(days=offset)
                     for offset in range(7))

    def _current_ph_date(self):
        # Compatibility name; date now comes from the draft's home-airport zone.
        return self.session.local_datetime(self._draft.context_airport_id).date()

    def _focus_week_start(self):
        self.content.parent.scroll_y = 1

        def focus(_dt):
            button = self._schedule_monday_button
            if (self._draft is not None and self.current_view == 'Schedule'
                    and button.get_root_window() is not None):
                self.content.parent.scroll_to(button, padding=dp(8))

        Clock.schedule_once(focus, .3)

    def reschedule_from_drag(self, index, departure_local, delta_px):
        """Translate a gesture to a five-minute UI slot; domain validates it."""
        departure = datetime.fromisoformat(departure_local)
        minute = departure.hour * 60 + departure.minute
        proposed = round((minute + delta_px * 60 / dp(100)) / 5) * 5
        if proposed == minute:
            self.refresh(force=True)
            return None
        if proposed < 0 or proposed >= 24 * 60:
            self.refresh(force=True)
            self._error('Reschedule rejected', 'Drag within the same local weekday.')
            return None
        if not self._management_ready():
            self.refresh(force=True)
            return None
        try:
            working = deepcopy(self._draft)
            moved = working.reschedule_in_context(index, departure.date().isoformat(),
                                       f'{proposed // 60:02d}:{proposed % 60:02d}')
            working.validate_current(self.session.world)
            self._draft = working
            self._schedule_selected.clear()
            self.refresh(force=True)
            return moved
        except Exception as exc:
            self.refresh(force=True)
            self._error('Reschedule rejected', exc)
            return None

    def change_schedule_week(self, weeks):
        self._schedule_week += timedelta(days=7 * weeks)
        self._schedule_day = self._schedule_week.isoformat()
        self._schedule_selected.clear()
        self.refresh(force=True)
        self._focus_week_start()

    def start_schedule(self, aircraft_id, *, edit_recurring=False):
        if not self._management_ready():
            return
        try:
            self._draft = self.session.begin_scheduling(aircraft_id, edit_recurring=edit_recurring)
            self._schedule_aircraft = next(row for row in self.session.fleet(limit=100)
                                           if row['aircraft_id'] == aircraft_id)
            try:
                model = self.session.aircraft_catalog().model(
                    self._schedule_aircraft['model_reference'])
                self._schedule_model_label = (model['manufacturer']['display_name']
                                              + ' ' + model['model']['display_name'])
            except ValueError:
                self._schedule_model_label = self._schedule_aircraft['model_reference']
            self._schedule_week = monday(date.fromisoformat(self._draft.revision_from)
                                         if self._draft.revision_from else self._current_ph_date())
            self._schedule_day = self._schedule_week.isoformat()
            self._schedule_selected = set()
            self._schedule_clipboard = None
            self._schedule_scroll_x = 0
            self._init_builder()
            self.refresh(force=True)
            self.content.parent.scroll_y = 1
        except Exception as exc:
            self._error('Weekly planner', exc)

    def select_schedule_day(self, target_date):
        self._schedule_day = target_date
        rows = self._draft.week_rows(self._schedule_week.isoformat())
        self._schedule_selected = {row['draft_index'] for row in rows
                                   if row.get('timeline_departure_local', row['departure_local'])[:10] == target_date
                                   and row['draft_index'] is not None}
        self.refresh(force=True)

    def select_schedule_block(self, row):
        index = row['draft_index']
        if index is None:
            self._dialog('Published flight' if row.get('published', True) else 'Recurring pattern preview',
                         f"{row['departure_local']} -> {row['arrival_local']}\n"
                         + ('Published reservations cannot be edited in this draft.' if row.get('published', True)
                          else 'Not materialized/bookable yet. Use Edit recurring pattern to change future weeks.'),
                         [('OK', lambda: None)])
            return
        self._schedule_day = row.get('timeline_departure_local', row['departure_local'])[:10]
        if index in self._schedule_selected:
            self._schedule_selected.remove(index)
        else:
            self._schedule_selected.add(index)
        self.refresh(force=True)

    def copy_selected(self):
        if self._draft is None or not self._schedule_selected:
            self._error('Copy Selected', 'Select one or more draft flight blocks first.')
            return
        try:
            self._schedule_clipboard = self._draft.copy_selection(
                sorted(self._schedule_selected))
            self.refresh(force=True)
        except Exception as exc:
            self._error('Copy Selected', exc)

    def copy_day(self):
        if self._draft is None:
            return
        rows = self._draft.week_rows(self._schedule_week.isoformat())
        indices = [row['draft_index'] for row in rows
                   if row.get('timeline_departure_local', row['departure_local'])[:10] == self._schedule_day
                   and row['draft_index'] is not None]
        if not indices:
            self._error('Copy Day', 'Select a day with draft flights first.')
            return
        self._schedule_selected = set(indices)
        self.copy_selected()

    def show_paste(self):
        if self._draft is None or not self._schedule_clipboard or not self._management_ready():
            self._error('Paste', 'Copy one or more draft flights first.')
            return
        from app.gui.app import _button, _label
        body = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(10),
                         size_hint_y=None, height=dp(430))
        body.add_widget(_label("Anchor copied sequence at the first origin's local time", height=42))
        start = TextInput(text=self._schedule_clipboard.get('anchor_local_time', '08:00'),
                          multiline=False, size_hint_y=None, height=dp(52))
        body.add_widget(start)
        body.add_widget(_label('Choose every target weekday; all targets succeed or none.', height=50))
        picker = WeekdayPicker(self._week_dates(), past_before=self._current_ph_date())
        body.add_widget(picker)

        def apply():
            try:
                self._paste_selected({'targets': picker.selected_dates(),
                                      'time': start.text.strip()})
            except Exception as exc:
                self._error('Paste rejected', exc)

        body.add_widget(_button('Paste to selected weekdays', apply))
        body.add_widget(_button('Cancel', self._dismiss))
        scroll = AxisScrollView(do_scroll_x=False)
        scroll.add_widget(body)
        self._popup = Popup(title='Paste copied flights', content=scroll,
                            size_hint=(.94, .9), auto_dismiss=False)
        self._popup.open()

    def _paste_selected(self, values):
        working = deepcopy(self._draft)
        targets = values['targets'] if 'targets' in values else (values['target'],)
        count = working.paste_weekdays(self._schedule_clipboard,
                                       targets, values['time'])
        working.validate_current(self.session.world)
        self._draft = working
        self._schedule_day = targets[0]
        self._schedule_selected.clear()
        self._dismiss()
        self.refresh(force=True)
        return count

    def delete_selected(self):
        if self._draft is None or not self._schedule_selected or not self._management_ready():
            self._error('Delete draft flights', 'Select unpublished draft blocks first.')
            return
        try:
            working = deepcopy(self._draft)
            count = working.delete_selection(sorted(self._schedule_selected))
            working.validate_current(self.session.world)
            self._draft = working
            self._schedule_selected.clear()
            self.refresh(force=True)
            return count
        except Exception as exc:
            self._error('Delete rejected', exc)
            return None

    def show_add_leg(self):
        if self._draft is None or not self._management_ready():
            return
        airports = self.session.airports()
        origin = self._draft.last_stop
        destination = next(row['airport_id'] for row in airports
                           if row['airport_id'] != origin)
        fields = [
            ('origin', 'Origin (aircraft must be present or explicitly positioned)',
             airports, origin),
            ('destination', 'Destination', airports, destination),
            ('date', 'Origin-local departure date (calendar)', None,
             self._schedule_day),
            ('time', 'Local time HH:MM', None, '08:00'),
            ('timing', 'Departure timing',
             ('Earliest available', 'Exact local time'), 'Earliest available'),
            ('fare', 'Economy fare USD (passenger leg)', None, '99.00'),
            ('service', 'Service', ('Passenger', 'Positioning'), 'Passenger'),
            ('position', 'If aircraft is elsewhere',
             ('Reject', 'Add explicit positioning flight'), 'Reject'),
        ]

        def decorate(column, widgets, key):
            if key != 'fare':
                return
            from app.gui.app import _button, _label
            suggestion = _label('', height=72)
            column.add_widget(suggestion)
            value = {'minor': None, 'manual': False, 'prefilling': False}

            def update(*_args):
                try:
                    minor = self.session.suggested_economy_fare(
                        widgets['origin'].selected_id,
                        widgets['destination'].selected_id)
                except ValueError:
                    minor = None
                value['minor'] = minor
                if minor is not None and not value['manual']:
                    value['prefilling'] = True
                    widgets['fare'].text = f'{minor // 100}.{minor % 100:02d}'
                    value['prefilling'] = False
                suggestion.text = (
                    'Suggested Economy fare unavailable for this market.' if minor is None
                    else f'Suggested Economy fare: {self._money(minor)}. '
                         'Reference only; not a profit or booking guarantee.')

            def use_suggestion():
                if value['minor'] is not None:
                    value['manual'] = False
                    update()

            widgets['origin'].bind(selected_id=update)
            widgets['destination'].bind(selected_id=update)
            widgets['fare'].bind(text=lambda _widget, _text:
                                 value.__setitem__('manual', True)
                                 if not value['prefilling'] else None)
            column.add_widget(_button('Use Suggested Fare', use_suggestion))
            update()

        def selected(values):
            origin, dest = values['origin'], values['destination']
            floor = format_utc(local_departure(self.session.world['world_state'],
                                               origin, values['date'], values['time']))
            working = deepcopy(self._draft)
            if origin != working.last_stop and values['position'] == 'Add explicit positioning flight':
                positioning = working.earliest(working.last_stop, origin, not_before=floor)
                working.add(working.last_stop, origin, departure_utc=positioning,
                            deadhead=True)
            departure = (working.earliest(origin, dest, not_before=floor)
                         if values['timing'] == 'Earliest available' else floor)
            fare = parse_usd_fare(values['fare']) if values['service'] == 'Passenger' else 0
            working.add(origin, dest, departure_utc=departure, fare_minor=fare,
                        deadhead=values['service'] == 'Positioning')
            self._draft = working
            self._schedule_selected.clear()
            self._dismiss()
            self.refresh(force=True)

        self._choice_form('Add weekly flight', fields, selected, decorate=decorate)

    def add_return(self):
        if self._draft is None or not self._management_ready():
            return
        try:
            working = deepcopy(self._draft)
            working.add_return()
            self._draft = working
            self._schedule_selected.clear()
            self.refresh(force=True)
        except Exception as exc:
            self._error('Add return', exc)

    def undo_leg(self):
        if self._draft is not None:
            self._draft.undo()
            self._schedule_selected.clear()
            self.refresh(force=True)

    def discard_schedule(self):
        self._draft = None
        self._schedule_selected.clear()
        self._schedule_clipboard = None
        self.refresh(force=True)

    def edit_recurring_schedule(self):
        if self._draft is None:
            return
        aircraft_id = self._draft.aircraft_id
        self._dialog('Edit recurring pattern',
                     'Replace this local draft with the saved recurring pattern? '
                     'Changes begin in its first unpublished future week.', [
                         ('Edit pattern', lambda: self.start_schedule(aircraft_id, edit_recurring=True)),
                         ('Cancel', lambda: None)])

    def show_save_schedule(self):
        if self._draft is None or not self._management_ready():
            return
        defaults = self._draft.publication_defaults
        def decorate(column, widgets, key):
            if key == 'repeat':
                picker = widgets['repeat']
                self._repeat_date_picker = picker
                def sync(_widget=None, value=None):
                    picker.disabled = widgets['mode'].text != 'Repeat until date'
                widgets['mode'].bind(text=sync)
                sync()
        self._choice_form('Review weekly publication', [
            ('mode', 'Operation / recurrence',
             ('This week / one-off', 'Repeat until date', 'Continuous recurring'),
             defaults['mode']),
            ('repeat', 'Until (inclusive airport-local date; choose from calendar)', None, defaults['repeat']),
        ], self._review_schedule, decorate=decorate)

    def _review_schedule(self, values):
        mode = values.get('mode', 'Repeat until date' if values.get('repeat') else 'This week / one-off')
        repeat = (values.get('repeat') or None) if mode == 'Repeat until date' else None
        continuous = mode == 'Continuous recurring'
        if mode == 'Repeat until date' and repeat is None:
            raise ValueError('choose an inclusive Repeat Until date from the calendar')
        if repeat is not None and date.fromisoformat(repeat).isoformat() != repeat:
            raise ValueError('choose a valid calendar date')
        self._dismiss()
        effective = self._draft.revision_from
        stopping = not self._draft.legs and effective is not None
        message = (f'Stop this recurring pattern beginning {effective}? '
                   'Existing published/booked flights will still operate.' if stopping else
                   f"Publish pattern with {len(self._draft.legs)} local flight(s)"
                   + (f" effective week {effective}" if effective else '')
                   + (' continuously, keeping four future weeks bookable?' if continuous else
                      f" weekly through {repeat}?" if repeat else ' on their selected dates only?')
                   + ' Elapsed slots remain pattern only. Published flights stay protected.')
        self._dialog('Publish Schedule', message, [
                         ('Publish Schedule', lambda: self._queue_schedule_publication(repeat, continuous=continuous)),
                         ('Cancel', lambda: None)])

    def _queue_schedule_publication(self, repeat, *, continuous=False):
        """Paint feedback before one serialized domain command; no worker thread."""
        if not self._idle():
            return
        self.session.pause()
        self._dialog('Publishing schedule',
                     'Validating and publishing the complete schedule. Please wait.', [])
        def publish(_dt):
            self._schedule_publication_pending = None
            self._dismiss()
            self._save_schedule(repeat, continuous=continuous)
        # A short event-loop deferral lets the modal notice paint first. No world
        # work is spread across frames and the authoritative command stays atomic.
        self._schedule_publication_pending = Clock.schedule_once(publish, .05)

    def _save_schedule(self, repeat, *, continuous=False):
        try:
            stopping = not self._draft.legs and self._draft.revision_from is not None
            result = self.session.save_scheduling(self._draft, repeat_until=repeat, continuous=continuous)
            self._draft = None
            self._schedule_selected.clear()
            self._schedule_clipboard = None
            self.refresh(force=True)
            self._dialog('Schedule published',
                         ("Recurring pattern stopped after existing published flights." if stopping else
                          f"Published {len(result.created_dated_flight_ids)} new dated flight(s). ")
                         + ('Recurring schedules extend automatically each week.' if not stopping and (continuous or repeat) else ''),
                         [('OK', lambda: None)])
        except Exception as exc:
            self._error('Schedule rejected', exc)

    def publish_next_schedule(self):
        if not self._management_ready():
            return
        try:
            result = self.session.publish_next_rotation()
            if not result.succeeded:
                issue = result.issues[0]
                raise ValueError(f'{issue.code}: {issue.message}')
            self.refresh(force=True)
            self._dialog('Next rotation',
                         f"Published {len(result.dated_flight_ids)} flights.",
                         [('OK', lambda: None)])
        except Exception as exc:
            self._error('Next rotation rejected', exc)
