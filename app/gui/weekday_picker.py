"""Transient seven-day selection and presets for PH-local weekly forms."""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton

from app.gui.scrolling import AxisScrollView


PRESETS = {
    'MWF': frozenset((0, 2, 4)),
    'TThS': frozenset((1, 3, 5)),
    'Even': frozenset((1, 3, 5)),
    'Odd': frozenset((0, 2, 4, 6)),
    'Daily': frozenset(range(7)),
    'Clear': frozenset(),
}


class WeekdayPicker(BoxLayout):
    def __init__(self, week_dates, *, selected=(), past_before=None,
                 on_change=None, **kwargs):
        super().__init__(orientation='vertical', size_hint_y=None,
                         height=dp(116), spacing=dp(5), **kwargs)
        self.week_dates = tuple(week_dates)
        if len(self.week_dates) != 7:
            raise ValueError('week picker requires Monday through Sunday')
        self.selected_indices = set(selected)
        self.on_change = on_change
        self.buttons = {}
        self.add_widget(self._strip(PRESETS.keys(), self.apply_preset, width=dp(82)))
        row = BoxLayout(size_hint_x=None, width=dp(7 * 96), spacing=dp(3))
        for index, day in enumerate(self.week_dates):
            suffix = '\nPAST' if past_before is not None and day < past_before else ''
            button = ToggleButton(text=f'{day:%a %d}{suffix}',
                                  size_hint_x=None, width=dp(93),
                                  state='down' if index in self.selected_indices else 'normal')
            button.bind(state=lambda widget, state, offset=index:
                        self._toggle(offset, state))
            self.buttons[index] = button
            row.add_widget(button)
        scroll = AxisScrollView(do_scroll_y=False, do_scroll_x=True,
                                size_hint_y=None, height=dp(55))
        scroll.add_widget(row)
        self.add_widget(scroll)

    def _strip(self, labels, action, *, width):
        row = BoxLayout(size_hint_x=None, width=width * len(labels),
                        spacing=dp(3))
        for label in labels:
            button = Button(text=label, size_hint_x=None, width=width)
            button.bind(on_release=lambda _button, name=label: action(name))
            row.add_widget(button)
        scroll = AxisScrollView(do_scroll_y=False, do_scroll_x=True,
                                size_hint_y=None, height=dp(55))
        scroll.add_widget(row)
        return scroll

    def _toggle(self, index, state):
        if state == 'down':
            self.selected_indices.add(index)
        else:
            self.selected_indices.discard(index)
        if self.on_change:
            self.on_change(set(self.selected_indices))

    def apply_preset(self, name):
        self.selected_indices = set(PRESETS[name])
        for index, button in self.buttons.items():
            button.state = 'down' if index in self.selected_indices else 'normal'
        if self.on_change:
            self.on_change(set(self.selected_indices))

    def selected_dates(self):
        return tuple(self.week_dates[index].isoformat()
                     for index in sorted(self.selected_indices))
