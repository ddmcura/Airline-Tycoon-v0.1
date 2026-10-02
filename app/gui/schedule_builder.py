"""Persistent GUI intent controls for a detached weekly aircraft draft."""

from copy import deepcopy

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from app.gui.airport_selector import AirportSelector
from app.gui.weekday_picker import WeekdayPicker
from app.inputs import parse_usd_fare


def fare_text(minor):
    major, cents = divmod(minor, 100)
    return str(major) if cents == 0 else f'{major}.{cents:02d}'


class ScheduleBuilder:
    def _init_builder(self):
        airports = self.session.airports()
        self._builder_origin = self._draft.last_stop
        self._builder_destination = next(row['airport_id'] for row in airports
                                         if row['airport_id'] != self._builder_origin)
        self._builder_time = '00:00'
        self._builder_earliest = False
        self._builder_return = True
        self._builder_weekdays = set()
        self._builder_fare_manual = False
        self._builder_fare = ''
        self._builder_fare_suggestion = None
        self._sync_suggested_fare()

    def _sync_suggested_fare(self):
        try:
            minor = self.session.suggested_economy_fare(
                self._builder_origin, self._builder_destination)
        except ValueError:
            minor = None
        self._builder_fare_suggestion = minor
        if not self._builder_fare_manual:
            self._builder_fare = fare_text(minor) if minor is not None else ''
            widget = getattr(self, '_builder_fare_widget', None)
            if widget is not None:
                self._builder_prefilling = True
                widget.text = self._builder_fare
                self._builder_prefilling = False
        label = getattr(self, '_builder_suggestion_label', None)
        if label is not None:
            label.text = ('Suggested Economy fare unavailable for this pair.'
                          if minor is None else
                          f'Suggested Economy fare: {self._money(minor)}')

    def _builder_airport_changed(self, key, identity):
        setattr(self, key, identity)
        self._sync_suggested_fare()
        label = getattr(self, '_builder_departure_label', None)
        if label is not None:
            label.text = self._departure_caption()

    def _departure_caption(self):
        airport = next(row for row in self.session.airports()
                       if row['airport_id'] == self._builder_origin)
        return f"Departure {airport['reference_code']} local ({airport['timezone']}) HH:MM"

    def _builder_fare_changed(self, value):
        self._builder_fare = value
        if not getattr(self, '_builder_prefilling', False):
            self._builder_fare_manual = True

    def _use_suggested_fare(self):
        self._builder_fare_manual = False
        self._sync_suggested_fare()

    def _render_builder(self):
        from app.gui.app import _button, _label

        body = BoxLayout(orientation='vertical', size_hint_y=None,
                         height=dp(500), spacing=dp(4))
        body.add_widget(_label('FLIGHT BUILDER — select weekdays below or use + Add on a day row', height=35))
        airports = self.session.airports()
        endpoint_row = BoxLayout(size_hint_y=None, height=dp(86), spacing=dp(5))
        for caption, key in (('Origin', '_builder_origin'),
                             ('Destination', '_builder_destination')):
            column = BoxLayout(orientation='vertical')
            column.add_widget(_label(caption, height=28))
            picker = AirportSelector(airports, selected_id=getattr(self, key))
            picker.bind(selected_id=lambda _widget, identity, attr=key:
                        self._builder_airport_changed(attr, identity))
            column.add_widget(picker)
            endpoint_row.add_widget(column)
        body.add_widget(endpoint_row)

        input_row = BoxLayout(size_hint_y=None, height=dp(90), spacing=dp(5))
        departure = BoxLayout(orientation='vertical')
        self._builder_departure_label = _label(self._departure_caption(), height=28)
        departure.add_widget(self._builder_departure_label)
        time = TextInput(text=self._builder_time, multiline=False,
                         size_hint_y=None, height=dp(52))
        time.disabled = self._builder_earliest
        time.bind(text=lambda _widget, value: setattr(self, '_builder_time', value))
        departure.add_widget(time)
        input_row.add_widget(departure)
        fare_column = BoxLayout(orientation='vertical')
        fare_column.add_widget(_label('Economy fare USD', height=28))
        fare = TextInput(text=self._builder_fare, multiline=False,
                         size_hint_y=None, height=dp(52))
        self._builder_fare_widget = fare
        fare.bind(text=lambda _widget, value: self._builder_fare_changed(value))
        fare_column.add_widget(fare)
        input_row.add_widget(fare_column)
        body.add_widget(input_row)

        self._builder_suggestion_label = _label('', height=34)
        body.add_widget(self._builder_suggestion_label)
        self._sync_suggested_fare()
        switches = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(5))
        earliest = ToggleButton(text='Earliest Available',
                                state='down' if self._builder_earliest else 'normal')
        def set_earliest(_button, state):
            self._builder_earliest = state == 'down'
            time.disabled = self._builder_earliest
        earliest.bind(state=set_earliest)
        return_flight = ToggleButton(text='Return Flight',
                                     state='down' if self._builder_return else 'normal')
        return_flight.bind(state=lambda _button, state:
                           setattr(self, '_builder_return', state == 'down'))
        switches.add_widget(earliest)
        switches.add_widget(return_flight)
        switches.add_widget(_button('Use Suggested Fare', self._use_suggested_fare))
        body.add_widget(switches)
        today = self._current_ph_date()
        self._builder_day_picker = WeekdayPicker(
            self._week_dates(), selected=self._builder_weekdays,
            past_before=today, on_change=lambda selected:
            setattr(self, '_builder_weekdays', selected))
        body.add_widget(self._builder_day_picker)
        body.add_widget(_button('+ ADD FLIGHT', self.add_builder_flights))
        self.content.add_widget(body)

    def add_builder_flights(self, *, target_dates=None):
        """Submit the current builder to selected days or one timeline row."""
        if self._draft is None or not self._management_ready():
            return
        try:
            dates = (tuple(self._week_dates()[index].isoformat()
                           for index in sorted(self._builder_weekdays))
                     if target_dates is None else tuple(target_dates))
            fare = parse_usd_fare(self._builder_fare)
            working = deepcopy(self._draft)
            count = working.add_weekdays(
                self._builder_origin, self._builder_destination, dates,
                self._builder_time, earliest=self._builder_earliest,
                return_flight=self._builder_return, fare_minor=fare)
            working.validate_current(self.session.world)
            self._draft = working
            if target_dates is not None:
                self._schedule_day = dates[0]
            self._schedule_selected.clear()
            self.refresh(force=True)
            return count
        except Exception as exc:
            self._error('Add Flight rejected', exc)
            return None
