"""GUI-only PH-local calendar selector; emits canonical YYYY-MM-DD text."""

import calendar
from datetime import date

from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup


class DatePicker(BoxLayout):
    selected_date = StringProperty('')

    def __init__(self, *, selected_date='', display_date=None, allow_clear=False, **kwargs):
        super().__init__(orientation='vertical', size_hint_y=None,
                         height=dp(54), **kwargs)
        self.allow_clear = allow_clear
        self._shown_month = date.fromisoformat(selected_date or display_date).replace(day=1) if (selected_date or display_date) else date.today().replace(day=1)
        self._popup = None
        self.button = Button(size_hint_y=None, height=dp(52))
        self.button.bind(on_release=lambda *_: self.open_calendar())
        self.add_widget(self.button)
        self.select(selected_date)

    @property
    def text(self):
        return self.selected_date

    def select(self, value):
        if not value and self.allow_clear:
            self.selected_date = ''
            self.button.text = 'Choose date (optional)'
        else:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError('use a valid calendar date')
            self.selected_date = value
            self._shown_month = parsed.replace(day=1)
            self.button.text = parsed.strftime('%a %b %d, %Y')
        if self._popup is not None:
            self._popup.dismiss()
            self._popup = None

    def shift_month(self, amount):
        year = self._shown_month.year
        month = self._shown_month.month + amount
        while month < 1:
            year, month = year - 1, month + 12
        while month > 12:
            year, month = year + 1, month - 12
        self._shown_month = date(year, month, 1)
        self._render_calendar()

    def open_calendar(self):
        self._root = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(8))
        self._header = BoxLayout(size_hint_y=None, height=dp(54))
        previous = Button(text='‹', size_hint_x=None, width=dp(60))
        previous.bind(on_release=lambda *_: self.shift_month(-1))
        self._month_label = Label()
        following = Button(text='›', size_hint_x=None, width=dp(60))
        following.bind(on_release=lambda *_: self.shift_month(1))
        for widget in (previous, self._month_label, following):
            self._header.add_widget(widget)
        self._root.add_widget(self._header)
        self._days = GridLayout(cols=7, spacing=dp(3))
        self._root.add_widget(self._days)
        if self.allow_clear:
            clear = Button(text='Clear date', size_hint_y=None, height=dp(52))
            clear.bind(on_release=lambda *_: self.select(''))
            self._root.add_widget(clear)
        self._popup = Popup(title='Choose local calendar date', content=self._root,
                            size_hint=(.94, .85), auto_dismiss=True)
        self._popup.bind(on_dismiss=lambda *_: setattr(self, '_popup', None))
        self._render_calendar()
        self._popup.open()
        return self._popup

    def _render_calendar(self):
        self._month_label.text = self._shown_month.strftime('%B %Y')
        self._days.clear_widgets()
        for name in ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'):
            self._days.add_widget(Label(text=name, size_hint_y=None,
                                        height=dp(32)))
        for week in calendar.monthcalendar(self._shown_month.year,
                                           self._shown_month.month):
            for day in week:
                if day:
                    value = date(self._shown_month.year,
                                 self._shown_month.month, day).isoformat()
                    button = Button(text=str(day), size_hint_y=None,
                                    height=dp(48), background_normal='',
                                    background_color=([.16, .57, .84, 1]
                                                      if value == self.selected_date
                                                      else [.42, .43, .45, 1]))
                    button.bind(on_release=lambda _button, chosen=value:
                                self.select(chosen))
                    self._days.add_widget(button)
                else:
                    self._days.add_widget(Label(size_hint_y=None, height=dp(48)))
