"""Plain, touch-friendly Kivy playtest shell over the shared PH session."""

from datetime import timedelta
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.utils import platform

from game.simulation.speeds import PLAYER_SPEEDS
from app.session import Stage1Session
from app.gui.gameplay import GameplayViews
from app.gui.navigation import SECTIONS, section_for
from app.gui.management_pages import FleetPage, ResearchPage, AircraftDetailsPage
from app.gui.airport_selector import AirportSelector
from app.gui.scrolling import AxisScrollView
from app.gui.windowing import configure_startup_window
from app.inputs import parse_duration_seconds
from game.world_state.timestamps import format_utc, parse_canonical_utc


def _money(minor):
    sign = '-' if minor < 0 else ''
    major, cents = divmod(abs(minor), 100)
    return f'{sign}USD {major:,}.{cents:02d}'


def _button(text, action, *, width=None):
    button = Button(text=text, size_hint_y=None, height=dp(52))
    if width is not None:
        button.size_hint_x = None
        button.width = dp(width)
    button.bind(on_release=lambda _button: action())
    return button


def _label(text, *, height=46):
    label = Label(text=str(text), size_hint_y=None, height=dp(height),
                  halign='left', valign='middle')
    label.bind(width=lambda widget, width: setattr(widget, 'text_size', (width - dp(12), None)))
    return label


def _column():
    layout = GridLayout(cols=1, spacing=dp(6), padding=dp(8), size_hint_y=None)
    layout.bind(minimum_height=layout.setter('height'))
    return layout


class AirlineTycoonApp(GameplayViews, App):
    """One Kivy/UI owner calls one shared session at completed event boundaries."""

    def __init__(self, *, session_factory=Stage1Session, **kwargs):
        super().__init__(**kwargs)
        self.session = session_factory()
        self.current_view = 'Overview'
        self.view_offset = 0
        self._last_revision = None
        self._last_render_time = 0.0
        self._last_diagnostic = None
        self._last_autosave_error = None
        self._pending_runtime_action = None
        self._allow_close = False
        self._ticker = None
        self._active_page = None
        self._week_focus_event = None
        self._page_states = {}
        self._section = None
        self._details_aircraft_id = None
        self._schedule_publication_pending = None
        self._popup = None
        self._draft = None
        self._research_origin = None
        self._research_destination = None
        self._schedule_week = None
        self._schedule_day = None
        self._schedule_selected = set()
        self._schedule_clipboard = None
        self._schedule_aircraft = None
        self._schedule_model_label = None
        self._schedule_scroll_x = 0
        self._acquire_maker = None
        self._acquire_model = None

    def build(self):
        self.title = 'Airline Tycoon - PH 1.0'
        self.screens = ScreenManager()
        self.screens.add_widget(self._title_screen())
        self.screens.add_widget(self._game_screen())
        self._ticker = Clock.schedule_interval(self.tick, .2)
        Window.bind(on_request_close=self._window_close)
        return self.screens

    def on_start(self):
        configure_startup_window(Window, platform)

    def on_stop(self):
        if self._schedule_publication_pending is not None:
            self._schedule_publication_pending.cancel()
            self._schedule_publication_pending = None
        if self._ticker is not None:
            self._ticker.cancel()
        Window.unbind(on_request_close=self._window_close)
        self._pending_runtime_action = None
        self._leave_page()
        self.session.close()

    def _window_close(self, *_args):
        if self._allow_close:
            return False
        self.request_exit()
        return True

    def _title_screen(self):
        screen = Screen(name='title')
        root = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(20))
        root.add_widget(Label(text='Airline Tycoon\nPhilippines 1.0', font_size='24sp'))
        for text, action in [('New Game', self.show_new_game),
                             ('Load Game', self.show_load_game),
                             ('Exit', self.request_exit)]:
            root.add_widget(_button(text, action))
        root.add_widget(Label(size_hint_y=1))
        screen.add_widget(root)
        return screen

    def _game_screen(self):
        screen = Screen(name='game')
        root = BoxLayout(orientation='vertical', spacing=dp(4), padding=dp(6))
        self.identity = _label('', height=48)
        self.status = _label('', height=54)
        self.status.bind(texture_size=lambda label, size: setattr(
            label, 'height', max(dp(54), size[1] + dp(12))))
        root.add_widget(self.identity)
        root.add_widget(self.status)
        root.add_widget(self._horizontal_buttons([
            ('Pause', self.pause),
            *((speed.name, lambda name=speed.name: self.resume(name))
              for speed in PLAYER_SPEEDS),
            ('Advance', self.show_advance), ('Cancel advance', self.cancel_advance),
        ]))
        root.add_widget(self._horizontal_buttons([
            (section, lambda name=section: self.show_view(SECTIONS[name][0][1]))
            for section in SECTIONS]))
        self.subnavigation = BoxLayout(orientation='vertical',size_hint_y=None,height=dp(58))
        root.add_widget(self.subnavigation)
        self.page_host = BoxLayout(orientation='vertical')
        root.add_widget(self.page_host)
        self.content = _column()
        screen.add_widget(root)
        return screen

    def _horizontal_buttons(self, actions):
        scroll = AxisScrollView(size_hint_y=None, height=dp(58), do_scroll_y=False)
        row = BoxLayout(size_hint_x=None, spacing=dp(5))
        row.width = sum(max(112, len(text) * 11 + 30) + 5 for text, _ in actions)
        for text, action in actions:
            row.add_widget(_button(text, action, width=max(112, len(text) * 11 + 30)))
        scroll.add_widget(row)
        return scroll

    def _dialog(self, title, message, actions):
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        content.add_widget(_label(message, height=92))
        for text, action in actions:
            content.add_widget(_button(text, lambda callback=action: (self._dismiss(), callback())))
        popup = Popup(title=title, content=content, size_hint=(.94, None),
                      height=dp(min(570, 130 + len(actions) * 60)), auto_dismiss=False)
        self._popup = popup
        popup.open()

    def _dismiss(self):
        if self._popup is not None:
            self._popup.dismiss()
            self._popup = None

    def _error(self, title, error):
        self._dismiss()
        self._dialog(title, str(error), [('OK', lambda: None)])

    def _form(self, title, fields, submit):
        """Small reusable dialog for presentation input only."""
        content = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(10))
        inputs = {}
        for key, caption, initial in fields:
            content.add_widget(_label(caption, height=30))
            field = TextInput(text=initial, multiline=False, size_hint_y=None, height=dp(48))
            content.add_widget(field)
            inputs[key] = field
        def apply():
            try:
                submit({key: widget.text.strip() for key, widget in inputs.items()})
            except Exception as exc:
                self._error(title, exc)
        content.add_widget(_button('Confirm', apply))
        content.add_widget(_button('Cancel', self._dismiss))
        popup = Popup(title=title, content=content, size_hint=(.94, .85), auto_dismiss=False)
        self._popup = popup
        popup.open()

    def show_new_game(self):
        airports = self.session.available_airports()
        content = BoxLayout(orientation='vertical', spacing=dp(7), padding=dp(10))
        content.add_widget(_label('CEO name', height=28))
        ceo = TextInput(multiline=False, size_hint_y=None, height=dp(48))
        content.add_widget(ceo)
        content.add_widget(_label('Airline name', height=28))
        airline = TextInput(multiline=False, size_hint_y=None, height=dp(48))
        content.add_widget(airline)
        content.add_widget(_label('Philippines home base (Normal, USD 300 million)', height=42))
        base = AirportSelector(airports, selected_id=airports[0]['reference_code'])
        content.add_widget(base)
        def create():
            self.create_new_game(ceo.text.strip(), airline.text.strip(),
                                 base.selected_id)
        content.add_widget(_button('Create Game', create))
        content.add_widget(_button('Cancel', self._dismiss))
        self._popup = Popup(title='New PH 1.0 Game', content=content,
                            size_hint=(.95, .9), auto_dismiss=False)
        self._popup.open()

    def create_new_game(self, ceo_name, airline_name, base_code):
        try:
            self.session.new_game(ceo_name, airline_name, base_code)
            self._dismiss()
            self._enter_game()
        except Exception as exc:
            self._error('New Game failed', exc)

    def show_load_game(self):
        try:
            careers = self.session.list_careers()
        except Exception as exc:
            self._error('Load Game', exc)
            return
        if not careers:
            self._dialog('Load Game', 'No saved airline games found.', [('OK', lambda: None)])
            return
        self._list_popup('Load Game - airline careers', [
            (f"{row['airline_name']}  |  {row['simulation_time_utc']}",
             lambda career=row: self._choose_career(career)) for row in careers
        ])

    def _list_popup(self, title, actions):
        root = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(8))
        scroll = AxisScrollView(do_scroll_x=False)
        column = _column()
        for text, action in actions:
            column.add_widget(_button(text, lambda callback=action: (self._dismiss(), callback())))
        scroll.add_widget(column)
        root.add_widget(scroll)
        root.add_widget(_button('Back', self._dismiss))
        self._popup = Popup(title=title, content=root, size_hint=(.96, .9), auto_dismiss=False)
        self._popup.open()

    def _choose_career(self, career):
        if career.get('unreadable'):
            self._error('Load Game', career.get('diagnostic') or 'Career is unreadable')
            return
        career_id = career['career_id']
        bookmarks = self.session.list_bookmarks(career_id)
        actions = []
        if career['has_manual']:
            actions.append(('Current manual save', lambda: self._load(career_id, 'manual')))
        if career['has_autosave']:
            label = ('Newer autosave (recovery)' if self.session.newer_autosave(career_id)
                     else 'Latest autosave')
            actions.append((label, lambda: self._load(career_id, 'autosave')))
        if bookmarks:
            actions.append(('Browse bookmarks', lambda: self._load_bookmark_list(career_id)))
        if not actions:
            self._error('Load Game', 'No readable save is available for this career')
            return
        self._dialog('Load ' + career['airline_name'],
                     'Choose a save. Loading an autosave or bookmark leaves the manual save unchanged.',
                     actions + [('Cancel', lambda: None)])

    def _load_bookmark_list(self, career_id):
        bookmarks = self.session.list_bookmarks(career_id)
        self._list_popup('Bookmarks', [
            (f"{row['name']}  |  {row['simulation_time_utc']}",
             lambda item=row: self._load(career_id, 'bookmark', bookmark_id=item['bookmark_id']))
            for row in bookmarks
        ])

    def _load(self, career_id, kind, *, bookmark_id=None):
        def perform():
            try:
                self.session.load_saved(career_id, kind, bookmark_id=bookmark_id)
                self._enter_game()
            except Exception as exc:
                self._error('Load failed', exc)
        self._guard_unsaved(perform)

    def _enter_game(self):
        self._leave_page()
        self._page_states.clear()
        self._section = None
        self.current_view = 'Overview'
        self.view_offset = 0
        self._draft = None
        self._research_origin = None
        self._research_destination = None
        self._schedule_week = None
        self._schedule_day = None
        self._schedule_selected = set()
        self._schedule_clipboard = None
        self._schedule_aircraft = None
        self._schedule_model_label = None
        self._schedule_scroll_x = 0
        self._acquire_maker = None
        self._acquire_model = None
        self._last_revision = None
        self.screens.current = 'game'
        self.refresh(force=True)

    def tick(self, _dt):
        if self._schedule_publication_pending is not None:
            return
        if not self.session.active:
            return
        try:
            finished_advance = False
            if self.session.advancing:
                # One bounded resolver unit; no chain of expensive batches
                # inside a single UI callback.
                report = self.session.advance_tick()
                finished_advance = report is not None
                if report is not None and report.result.failure:
                    self._error('Advancement stopped', report.result.failure.message)
            else:
                self.session.pump()
            if self._pending_runtime_action is not None and not self.session.runtime.draining:
                owner, action = self._pending_runtime_action
                self._pending_runtime_action = None
                if owner is not self.session.runtime:
                    pass  # Session replacement revokes a deferred old-world action.
                elif owner.blocked:
                    self._error('Runtime stopped', owner.diagnostic)
                else:
                    action()
            self.refresh(force=finished_advance)
        except Exception as exc:
            self._pending_runtime_action = None
            self.session.cancel_advance()
            self.session.hard_pause()
            self._error('Runtime stopped', exc)

    def refresh(self, *, force=False):
        if not self.session.active:
            return
        world = self.session.world
        sim = world['simulation']
        diagnostic = self.session.runtime.diagnostic if self.session.runtime else None
        autosave_error = self.session.autosave_error
        render_due = (not self.session.advancing
                      and self._last_revision != self.session.progression_revision
                      and time.monotonic() - self._last_render_time >= 1.5)
        if (force or render_due or diagnostic != self._last_diagnostic
                or autosave_error != self._last_autosave_error):
            overview = self.session.header()
            self._header = overview
            self.identity.text = (f"{overview['airline_display_name']}  |  CEO {overview['ceo_display_name']}"
                                  f"  |  Base {', '.join(row['reference_code'] for row in overview['base_airports'])}")
            self._cash = overview['cash_minor']
            self._last_revision = self.session.progression_revision
            self._last_render_time = time.monotonic()
            self._last_diagnostic = diagnostic
            self._last_autosave_error = autosave_error
            self._render_view()
        mode = self.session.runtime_status
        if self.session.advancing:
            mode = 'ADVANCING (event boundaries)'
        self.status.text = f"{self.session.local_clock()} hub local | {sim['time_utc']} UTC | {mode} | Cash {_money(self._cash)}"
        if self.session.runtime.draining:
            self.status.text += f'\nEarned target: {self.session.runtime.earned_target_utc}; remaining {self.session.runtime.credit_ns // 1_000_000_000} game seconds'
        if diagnostic:
            self.status.text += f'\n{diagnostic}'

    def _leave_page(self):
        if self._week_focus_event is not None:
            self._week_focus_event.cancel()
            self._week_focus_event = None
        page = self._active_page
        if page is None: return
        if hasattr(page, 'snapshot'):
            self._page_states[self.current_view] = page.snapshot()
        else:
            self._page_states[self.current_view] = {'scroll_x':page.scroll_x,'scroll_y':page.scroll_y,'offset':self.view_offset}
        if hasattr(page, 'close'): page.close()
        else: page.dispose()
        if page.parent is not None: page.parent.remove_widget(page)
        descendants = set(page.walk())
        for widget in descendants:
            if isinstance(widget,TextInput): widget.focus = False
        for name,value in list(vars(self).items()):
            if name != '_active_page' and isinstance(value,Widget) and value in descendants:
                setattr(self,name,None)
        self._active_page = None

    def show_view(self, view):
        if view != self.current_view:
            self._leave_page()
            self.view_offset = self._page_states.get(view,{}).get('offset',0)
        if view == 'Acquire' and self.current_view != 'Acquire':
            self._acquire_maker = self._acquire_model = None
        self.current_view = view
        self.refresh(force=True)

    def _render_view(self):
        view = self.current_view
        section = section_for(view)
        if section != self._section:
            for old in self.subnavigation.children:
                if isinstance(old,AxisScrollView): old.dispose()
            self.subnavigation.clear_widgets()
            actions=[(text, lambda value=value:self.show_view(value)) for text,value in SECTIONS[section]]
            if section == 'Game / System':
                actions += [('Return to Title',self.return_to_title),('Exit',self.request_exit)]
            self.subnavigation.add_widget(self._horizontal_buttons(actions))
            self._section = section
        if view in {'Fleet','Research','Aircraft Details'}:
            if self._active_page is None:
                state = self._page_states.get(view)
                factory = {'Fleet':FleetPage,'Research':ResearchPage}.get(view)
                page = factory(self,state) if factory else AircraftDetailsPage(self,self._details_aircraft_id,state)
                page.refresh_data()  # Resolve before attaching to visible host.
                self.page_host.add_widget(page);self._active_page=page
            else: self._active_page.refresh_data()
            self.content=self._active_page
            return
        # Existing non-redesigned pages render offscreen, then swap once. Their
        # outer viewport survives refresh; inactive viewports stop all momentum.
        old_content = self.content
        replacement = _column()
        self.content = replacement
        try:
            self._render_compatibility_content()
        except Exception:
            self.content = old_content
            raise
        if self._active_page is None:
            scroll=AxisScrollView(do_scroll_x=False,eager_drag_handles=True)
            scroll.add_widget(replacement);self.page_host.add_widget(scroll);self._active_page=scroll
            state=self._page_states.get(view,{})
            scroll.scroll_x=state.get('scroll_x',0);scroll.scroll_y=state.get('scroll_y',1)
        else:
            scroll=self._active_page
            scroll.stop_motion()
            old=scroll._viewport
            for w in list(old.walk()):
                if isinstance(w,AxisScrollView):w.dispose()
            scroll.remove_widget(old);scroll.add_widget(replacement)

    def _render_compatibility_content(self):
        view = self.current_view
        self.content.add_widget(_label(view, height=40))
        if view == 'Overview':
            self.content.add_widget(_label('PH 1.0 Normal career. Manage time here; fleet, flights and finances remain visible while running.', height=72))
            next_event = self.session.next_event_for_display()
            if next_event:
                self.content.add_widget(_label(f"Next: {next_event['event_type']} at {next_event['due_at_utc']}", height=65))
            if self.session.runtime and self.session.runtime.diagnostic:
                self.content.add_widget(_label(self.session.runtime.diagnostic, height=70))
            if self.session.autosave_error:
                self.content.add_widget(_label('Autosave failed: ' + self.session.autosave_error, height=70))
        elif view == 'Acquire':
            self.render_acquisition()
        elif view == 'Schedule':
            self.render_scheduling()
        elif view in {'Flights','Bookings'}:
            rows = self.session.flights(offset=self.view_offset, limit=30)
            for row in rows:
                self.content.add_widget(_label(
                    f"{row['origin_airport_reference_code']} → {row['destination_airport_reference_code']}  "
                    f"{row['scheduled_departure_utc']}  {row['status']}\n"
                    f"{row['aircraft_registration']}  |  Booked {row['booked_passenger_count']}/{row['published_capacity']}  "
                    f"|  Carried {row['carried_passenger_count']}  |  Ticket sales {_money(row['ticket_sales_minor'])}\n"
                    f"Revenue {_money(row['recognized_revenue_minor'])}  |  Cost {_money(row['operating_cost_minor'])} "
                    f"(routine maintenance {_money(row['maintenance_expense_minor'])})", height=116))
            self._page_buttons(len(rows), 30)
        elif view == 'Finance':
            finance = self.session.finances()
            for caption, key in [('Cash', 'cash_minor'), ('Aircraft assets', 'aircraft_assets_minor'),
                                 ('Unflown ticket liability', 'unflown_ticket_liability_minor'),
                                 ('Passenger revenue', 'passenger_revenue_minor'),
                                 ('Operating expenses', 'operating_expenses_minor'),
                                 ('Cumulative flight contribution', 'cumulative_profit_minor')]:
                self.content.add_widget(_label(f'{caption}: {_money(finance[key])}'))
            self.content.add_widget(_label('Recent transactions', height=38))
            for row in finance['recent_transactions']:
                entries = ', '.join(f"{item['account_id']}: {_money(item['amount_minor'])}"
                                    for item in row['entries'])
                self.content.add_widget(_label(
                    f"{row['occurred_at_utc']}  {row['description']}  [{row['source_type']}]\n{entries}", height=86))
            self.content.add_widget(_label('Recent flight results', height=38))
            for row in finance['recent_results']:
                self.content.add_widget(_label(
                    f"{row['scheduled_departure_utc']}  "
                    f"{row['origin_airport_reference_code']} → {row['destination_airport_reference_code']}\n"
                    f"Carried {row['carried_passenger_count']}  |  "
                    f"Revenue {_money(row['recognized_revenue_minor'])}  |  "
                    f"Cost {_money(row['operating_cost_minor'])}", height=86))
        elif view == 'Saves':
            for text, action in [('Save Game', self.save_game), ('Bookmarks / Checkpoints', self.show_bookmarks)]:
                self.content.add_widget(_button(text, action))
            self.content.add_widget(_label('One current manual save; autosaves run by the existing session policy.', height=65))

    def open_aircraft_details(self, aircraft_id):
        self.session.aircraft_details(aircraft_id)  # Stable identity/ownership gate.
        if self.current_view == 'Aircraft Details': self._leave_page()
        self._details_aircraft_id = aircraft_id
        self.show_view('Aircraft Details')

    def research_add_flight(self, origin_id, destination_id):
        ids = self.session.compatible_aircraft(origin_id, destination_id)
        if not ids:
            self._dialog('No compatible aircraft', 'No owned aircraft meets current route planning eligibility.', [('OK', lambda:None)])
            return
        if len(ids) == 1:
            self.schedule_handoff(ids[0],origin_id,destination_id)
            return
        rows = {r['aircraft_id']:r for r in self.session.management_fleet()}
        self._list_popup('Choose compatible aircraft — availability validated in Scheduling',[
            (rows[k]['registration']+' — '+rows[k]['model'], lambda key=k:(self._dismiss(),self.schedule_handoff(key,origin_id,destination_id)))
            for k in ids])

    def schedule_handoff(self, aircraft_id, origin_id=None, destination_id=None):
        def open_planner():
            self.show_view('Schedule')
            if self._draft is None or self._draft.aircraft_id != aircraft_id:
                self.start_schedule(aircraft_id)
            if self._draft is not None and self._draft.aircraft_id == aircraft_id:
                if origin_id is not None: self._builder_origin=origin_id
                if destination_id is not None: self._builder_destination=destination_id
                if origin_id is not None:
                    self._builder_fare_manual=False;self._sync_suggested_fare()
                self.refresh(force=True)
        def proceed(): self._after_runtime_pause(open_planner)
        if self._draft is not None and self._draft.aircraft_id != aircraft_id and self._draft.legs:
            self._dialog('Unpublished draft', 'Discard the current draft before selecting another aircraft?',[
                ('Discard draft and open',lambda:self._discard_draft_then(proceed)),('Cancel',lambda:None)])
        else: proceed()

    _money = staticmethod(_money)

    def _page_buttons(self, count, size):
        if self.view_offset:
            self.content.add_widget(_button('Previous page', lambda: self._change_page(-size)))
        if count == size:
            self.content.add_widget(_button('Next page', lambda: self._change_page(size)))
        if not count:
            self.content.add_widget(_label('No records to show.'))

    def _change_page(self, delta):
        self.view_offset = max(0, self.view_offset + delta)
        self.refresh(force=True)

    def _idle(self):
        if self._pending_runtime_action is not None:
            self._error('Pausing', 'An action is waiting for earned time to drain.')
            return False
        if self._schedule_publication_pending is not None:
            return False
        if self.session.advancing:
            self._error('Advance Time', 'Cancel or finish the current advancement first.')
            return False
        return True

    def pause(self):
        if self._idle():
            self.session.pause()
            self.refresh(force=True)

    def resume(self, speed=None):
        if self._idle():
            try:
                self.session.resume(speed)
                self.refresh(force=True)
            except ValueError as exc:
                self._error('Resume', exc)

    def show_advance(self):
        if not self._idle():
            return
        self._dialog('Advance Time', 'Explicit advancement finishes paused. Long jumps yield between complete events.', [
            ('Next event', self._next_event),
            ('One day', lambda: self._begin_seconds(86400)),
            ('By duration', lambda: self._form('Duration', [('value', 'Examples: 30m, 6h, 1d', '')], self._duration)),
            ('To UTC timestamp', lambda: self._form('UTC target', [('value', 'YYYY-MM-DDTHH:MM:SSZ', '')], self._target)),
            ('Cancel', lambda: None),
        ])

    def _next_event(self):
        try:
            report = self.session.advance_next_event()
            self.refresh(force=True)
            if report.result.failure:
                self._error('Next event', report.result.failure.message)
        except Exception as exc:
            self._error('Next event', exc)

    def _duration(self, values):
        self._begin_seconds(parse_duration_seconds(values['value']))

    def _target(self, values):
        target = values['value']
        parse_canonical_utc(target)
        self._begin_target(target)

    def _begin_seconds(self, seconds):
        target = format_utc(parse_canonical_utc(self.session.world['simulation']['time_utc'])
                            + timedelta(seconds=seconds))
        self._begin_target(target)

    def _begin_target(self, target):
        try:
            self.session.begin_advance_to(target)
            self._dismiss()
            self.refresh()
        except Exception as exc:
            self._error('Advance Time', exc)

    def cancel_advance(self):
        if self.session.advancing:
            self.session.cancel_advance()
            self.refresh(force=True)

    def _after_runtime_pause(self, action):
        self.session.pause()
        if self.session.runtime.draining:
            if self._pending_runtime_action is not None:
                self._error('Pausing', 'An action is already waiting for earned time to drain.')
                return
            self._pending_runtime_action = (self.session.runtime, action)
            self.refresh(force=True)
        else:
            action()

    def save_game(self):
        if not self._idle():
            return
        def save():
            try:
                self.session.save_manual()
                self._dialog('Save Game', 'Game saved.', [('OK', lambda: None)])
            except Exception as exc:
                self._error('Save failed', exc)
        self._after_runtime_pause(save)

    def show_bookmarks(self):
        if not self._idle():
            return
        rows = self.session.list_bookmarks()
        actions = [('New bookmark', lambda: self._form('New bookmark', [('name', 'Name', '')], self._create_bookmark))]
        for row in rows:
            actions.append((f"Load: {row['name']}  |  {row['simulation_time_utc']}",
                            lambda item=row: self._load(self.session.career_id, 'bookmark', bookmark_id=item['bookmark_id'])))
            actions.append((f"Delete: {row['name']}",
                            lambda item=row: self._confirm_delete_bookmark(item)))
        self._list_popup('Bookmarks / Checkpoints', actions)

    def _create_bookmark(self, values):
        def save():
            try:
                self.session.save_bookmark(values['name'])
                self._dismiss()
                self.show_bookmarks()
            except Exception as exc:
                self._error('Bookmark failed', exc)
        self._after_runtime_pause(save)

    def _confirm_delete_bookmark(self, row):
        self._dialog('Delete bookmark', f"Delete {row['name']}?", [
            ('Delete', lambda: self._delete_bookmark(row['bookmark_id'])),
            ('Cancel', lambda: None),
        ])

    def _delete_bookmark(self, bookmark_id):
        try:
            self.session.delete_bookmark(bookmark_id)
            self.show_bookmarks()
        except Exception as exc:
            self._error('Delete bookmark', exc)

    def _guard_unsaved(self, action):
        if self._schedule_publication_pending is not None:
            return
        if self.session.active and self.session.runtime.processing:
            self._after_runtime_pause(lambda: self._guard_unsaved(action))
            return
        if self._schedule_publication_pending is not None:
            return
        if self.session.advancing:
            self._error('Advance Time', 'Cancel or finish advancement first.')
            return
        if self._draft is not None:
            self._dialog('Unpublished schedule draft',
                         'This draft has not been published and is not part of a game save.',
                         [('Discard draft and continue',
                           lambda: self._discard_draft_then(action)),
                          ('Cancel', lambda: None)])
            return
        if not self.session.active or not self.session.unsaved_progress:
            action()
            return
        def decide(choice):
            self._resolve_departure(choice, action)
        self._dialog('Unsaved progress', 'Save before leaving this career?', [
            ('Save and continue', lambda: decide('save')),
            ('Leave without saving', lambda: decide('discard')),
            ('Cancel', lambda: decide('cancel')),
        ])

    def _discard_draft_then(self, action):
        self._draft = None
        self._schedule_selected.clear()
        self._schedule_clipboard = None
        self._guard_unsaved(action)

    def _resolve_departure(self, choice, action):
        try:
            if self.session.resolve_departure(choice):
                action()
        except Exception as exc:
            self._error('Save failed', exc)

    def return_to_title(self):
        def leave():
            self._leave_page()
            self.session.leave_game()
            self._draft = None
            self._schedule_selected.clear()
            self._schedule_clipboard = None
            self._last_revision = None
            self.screens.current = 'title'
        self._guard_unsaved(leave)

    def request_exit(self):
        def exit_app():
            self._allow_close = True
            self.stop()
        self._guard_unsaved(exit_app)


def main():
    AirlineTycoonApp().run()
    return 0


__all__ = ('AirlineTycoonApp', 'main')
