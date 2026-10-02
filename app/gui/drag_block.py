"""GUI-only drag handle for unpublished timeline blocks."""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button


class DragHandle(Button):
    def __init__(self, *, on_drop, **kwargs):
        super().__init__(text='↔', size_hint_x=None, width=dp(52), **kwargs)
        self.is_schedule_drag_handle = True
        self.on_drop_callback = on_drop
        self._touch = None
        self._start_x = 0
        self._original_x = 0

    def on_touch_down(self, touch):
        if touch.is_mouse_scrolling:
            return False
        if not self.collide_point(*touch.pos):
            return False
        self._touch = touch
        self._start_x = touch.x
        self._original_x = self.parent.x
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch is self._touch:
            self.parent.x = self._original_x + touch.x - self._start_x
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch is self._touch:
            delta = touch.x - self._start_x
            self.parent.x = self._original_x
            touch.ungrab(self)
            self._touch = None
            if abs(delta) >= dp(5):
                self.on_drop_callback(delta)
            return True
        return super().on_touch_up(touch)


class DraftFlightBlock(BoxLayout):
    def __init__(self, *, label, color, on_select, on_drop, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        select = Button(text=label, background_normal='',
                        background_color=color, font_size='13sp')
        select.bind(on_release=lambda *_: on_select())
        self.add_widget(select)
        self.add_widget(DragHandle(on_drop=on_drop, background_normal='',
                                   background_color=color))
