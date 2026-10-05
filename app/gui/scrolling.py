"""Axis-aware scroll containers for nested desktop and touch navigation."""

from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect


class AxisScrollView(ScrollView):
    def __init__(self, **kwargs):
        self.eager_drag_handles = kwargs.pop('eager_drag_handles', False)
        # Clamped kinetic scrolling avoids elastic spring instability after a
        # long atomic engine frame. Scoped to our containers, never a Kivy patch.
        kwargs.setdefault('effect_cls', ScrollEffect)
        kwargs.setdefault('always_overscroll', False)
        kwargs.setdefault('bar_width', dp(14))
        kwargs.setdefault('bar_color', (.65, .7, .75, 1))
        kwargs.setdefault('bar_inactive_color', (.5, .55, .6, .65))
        kwargs.setdefault('scroll_type', ['bars', 'content'])
        kwargs.setdefault('scroll_wheel_distance', dp(90))
        super().__init__(**kwargs)

    def stop_motion(self):
        for effect in (self.effect_x, self.effect_y):
            if effect is not None:
                effect.velocity = 0
                effect.is_manual = False
                effect.trigger_velocity_update.cancel()

    def dispose(self):
        self.stop_motion()
        event = getattr(self, '_update_effect_bounds_ev', None)
        if event is not None: event.cancel()
        for child in list(self.walk()):
            if child is not self and isinstance(child, AxisScrollView): child.dispose()

    def on_touch_down(self, touch):
        # ScrollView normally withholds child touches until its drag timeout.
        # Draft handles need the touch immediately; other content keeps normal
        # touch scrolling. Both the outer page and inner timeline opt in.
        if (self.eager_drag_handles and not touch.is_mouse_scrolling
                and self.collide_point(*touch.pos)):
            window_x, window_y = self.to_window(*touch.pos)
            for child in self.walk():
                if getattr(child, 'is_schedule_drag_handle', False):
                    x, y = child.to_widget(window_x, window_y, relative=True)
                    if 0 <= x <= child.width and 0 <= y <= child.height:
                        return self.simulate_touch_down(touch)
        if touch.is_mouse_scrolling:
            if touch.button in ('scrollup', 'scrolldown') and not self.do_scroll_y:
                if 'shift' in getattr(touch, 'modifiers', ()) and self.do_scroll_x:
                    child = self._viewport
                    excess = child.width - self.width if child is not None else 0
                    if excess > 0:
                        direction = -1 if touch.button == 'scrollup' else 1
                        self.scroll_x = max(0, min(1, self.scroll_x +
                                                     direction * self.scroll_wheel_distance / excess))
                        return True
                return False
            if touch.button in ('scrollleft', 'scrollright') and not self.do_scroll_x:
                return False
        return super().on_touch_down(touch)
