"""Kivy presentation for modern market, acquisition, and weekly scheduling."""

from copy import deepcopy
from datetime import date

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from app.inputs import parse_usd_fare
from game.scheduling.weekly import local_departure
from game.world_state.timestamps import format_utc


def airport_label(row):
    return f"{row['reference_code']} - {row['city']}"


class GameplayViews:
    """UI-only mixin. Session/domain commands own every authoritative mutation."""

    def _choice_form(self, title, fields, submit, *, decorate=None):
        from app.gui.app import _button, _label
        content = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(8))
        scroll = ScrollView()
        column = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None)
        column.bind(minimum_height=column.setter('height'))
        widgets = {}
        for key, caption, choices, initial in fields:
            column.add_widget(_label(caption, height=36))
            widget = (TextInput(text=initial, multiline=False, size_hint_y=None, height=dp(52))
                      if choices is None else
                      Spinner(text=initial or choices[0], values=choices,
                              size_hint_y=None, height=dp(52)))
            column.add_widget(widget)
            widgets[key] = widget
            if decorate is not None:
                decorate(column, widgets, key)
        scroll.add_widget(column)
        content.add_widget(scroll)

        def apply():
            try:
                submit({key: widget.text.strip() for key, widget in widgets.items()})
            except Exception as exc:
                self._error(title, exc)

        content.add_widget(_button('Continue', apply))
        content.add_widget(_button('Cancel', self._dismiss))
        self._popup = Popup(title=title, content=content, size_hint=(.96, .9),
                            auto_dismiss=False)
        self._popup.open()

    def _management_ready(self):
        if not self._idle():
            return False
        # Callbacks and pump are serialized on Kivy's event loop.
        self.session.pause()
        self.refresh(force=True)
        return True

    def render_research(self):
        from app.gui.app import _button, _label
        airports = self.session.airports()
        if self._research_origin not in {a['airport_id'] for a in airports}:
            self._research_origin = self.session.overview()['base_airports'][0]['airport_id']
        self.content.add_widget(_button('Choose origin', self.choose_research_origin))
        origin = next(a for a in airports if a['airport_id'] == self._research_origin)
        self.content.add_widget(_label(f"Directional opportunities from {airport_label(origin)}"))
        rows = self.session.market_opportunities(origin_airport_id=self._research_origin,
                                                 limit=100)
        for row in rows:
            fare = '—' if row['player_fare_minor'] is None else self._money(row['player_fare_minor'])
            self.content.add_widget(_label(
                f"{row['destination_airport_reference_code']} {row['destination_airport_city']}"
                f"  |  {row['distance_km']} km  |  Base daily bookers "
                f"{row['base_daily_directional_bookers']}\n"
                f"Market {'available' if row['market_available'] else 'unavailable'}"
                f"  |  Your seats {row['player_published_capacity']}"
                f"  |  Fare {fare}  |  Confirmed {row['current_confirmed_bookings']}",
                height=95))
        if not rows:
            self.content.add_widget(_label('No current opportunities from this origin.'))
        self.content.add_widget(_label(
            'Actual bookings depend on fare, schedule, capacity and competition.', height=60))

    def choose_research_origin(self):
        self._list_popup('Market origin', [
            (airport_label(row), lambda item=row: self._set_research_origin(item['airport_id']))
            for row in self.session.airports()])

    def _set_research_origin(self, airport_id):
        self._research_origin = airport_id
        self.refresh(force=True)

    def render_acquisition(self):
        from app.gui.app import _button, _label
        catalog = self.session.aircraft_catalog()
        makers = {maker['manufacturer_id']: maker for maker in catalog.manufacturers()
                  if catalog.models(maker['manufacturer_id'])}
        maker_id = self._acquire_maker
        model_id = self._acquire_model
        if maker_id not in makers:
            self._acquire_maker = self._acquire_model = None
            maker_id = model_id = None
        if maker_id is None:
            self.content.add_widget(_label('Choose manufacturer'))
            for maker in makers.values():
                self.content.add_widget(_button(
                    maker['display_name'],
                    lambda identity=maker['manufacturer_id']: self.choose_acquisition_maker(identity)))
            return

        maker = makers[maker_id]
        self.content.add_widget(_button('Back to Manufacturers', self.back_to_acquisition_makers))
        models = catalog.models(maker_id)
        if model_id not in {model['model_id'] for model in models}:
            self._acquire_model = None
            model_id = None
        if model_id is None:
            self.content.add_widget(_label(f"{maker['display_name']} · Choose aircraft model"))
            for model in models:
                detail = catalog.model(model['model_id'])
                self.content.add_widget(_label(
                    f"{model['display_name']} · {model['aircraft_category']} · "
                    f"{model['max_economy_seats']} seats · reference range "
                    f"{model['reference_range_km']} km\n"
                    f"New aircraft game price {self._money(detail['reference_price']['amount_minor'])}",
                    height=76))
                self.content.add_widget(_button(
                    f"Select {model['display_name']}",
                    lambda identity=model['model_id']: self.choose_acquisition_model(identity)))
            return

        detail = catalog.model(model_id)
        model = detail['model']
        self.content.add_widget(_button('Back to Aircraft Models', self.back_to_acquisition_models))
        self.content.add_widget(_label(
            f"{maker['display_name']} {model['display_name']} · {model['aircraft_category']}\n"
            f"{model['max_economy_seats']} seats · {model['reference_range_km']} km reference range",
            height=76))
        self.content.add_widget(_label(
            f"New aircraft game price {self._money(detail['reference_price']['amount_minor'])}"))
        self.content.add_widget(_button(
            'Review new aircraft purchase',
            lambda: self.begin_acquisition('new', model)))
        for offer in self.session.leasing_offers():
            if offer['model_id'] != model_id or offer['available_quantity'] <= 0:
                continue
            self.content.add_widget(_label(
                f"Lease offer · {offer['available_quantity']} available · "
                f"aircraft value {self._money(offer['aircraft_value_minor'])}", height=64))
            self.content.add_widget(_button(
                'Review operating lease or lease-to-own',
                lambda item=offer: self.begin_acquisition('lease', item)))
        for listing in self.session.used_listings():
            if listing['model_id'] != model_id:
                continue
            self.content.add_widget(_label(
                f"{listing['display_registration']} · {listing['age_months']} months · "
                f"condition {listing['service_condition_bps'] / 100:.2f}%\n"
                f"Asking price {self._money(listing['asking_price_minor'])}", height=76))
            self.content.add_widget(_button(
                f"Review used purchase {listing['display_registration']}",
                lambda item=listing: self.begin_acquisition('used', item)))

    def choose_acquisition_maker(self, manufacturer_id):
        self._acquire_maker = manufacturer_id
        self._acquire_model = None
        self.refresh(force=True)

    def back_to_acquisition_makers(self):
        self._acquire_maker = self._acquire_model = None
        self.refresh(force=True)

    def choose_acquisition_model(self, model_id):
        self._acquire_model = model_id
        self.refresh(force=True)

    def back_to_acquisition_models(self):
        self._acquire_model = None
        self.refresh(force=True)

    def begin_acquisition(self, mode, item):
        if not self._management_ready():
            return
        locations = self.session.delivery_locations()
        by_label = {airport_label(row): row['airport_id'] for row in locations}
        fields = [('delivery', 'Delivery base or hub', tuple(by_label), next(iter(by_label)))]
        if mode == 'lease':
            fields.extend((
                ('product', 'Lease product', ('Operating lease', 'Lease-to-own'), 'Operating lease'),
                ('years', 'Term in years (1–5)', None, '2'),
            ))

        def selected(values):
            location = by_label[values['delivery']]
            if mode == 'new':
                preview = self.session.preview_purchase(item['model_id'], location)
                message = (f"{item['display_name']} · immediate delivery\n"
                           f"Price {self._money(preview.amount_minor)}\n"
                           f"Cash after {self._money(preview.cash_after_minor)}")
                commit = self.session.purchase
            elif mode == 'lease':
                product = {'Operating lease': 'OPERATING_LEASE',
                           'Lease-to-own': 'LEASE_TO_OWN'}[values['product']]
                preview = self.session.preview_lease(item['lease_offer_id'], product,
                                                     int(values['years']), location)
                terms = (f"Monthly rent {self._money(preview.monthly_rent_minor)}"
                         if product == 'OPERATING_LEASE' else
                         f"Monthly financing {self._money(preview.monthly_financing_minor)}; "
                         f"principal base {self._money(preview.principal_base_minor)} "
                         f"(+1 cent for first {preview.principal_remainder_installments} months)")
                message = (f"{item['model_id']} · {values['product']} · {preview.term_years} years\n"
                           f"{terms}; cash may become negative.\n"
                           f"Immediate delivery to {values['delivery']}")
                commit = self.session.accept_lease
            elif mode == 'used':
                preview = self.session.preview_used_purchase(item['used_listing_id'], location)
                message = (f"{item['display_registration']} · immediate delivery\n"
                           f"Price {self._money(preview.asking_price_minor)}\n"
                           f"Cash after {self._money(preview.cash_after_minor)}")
                commit = self.session.purchase_used
            else:
                raise ValueError('unsupported acquisition mode')
            self._dismiss()
            self._dialog('Review acquisition', message, [
                ('Confirm', lambda: self._commit_acquisition(commit, preview)),
                ('Cancel', lambda: None)])

        self._choice_form('Acquire aircraft', fields, selected)

    def _commit_acquisition(self, command, preview):
        try:
            # The original quote is revalidated by the domain command at commit.
            aircraft_id = command(preview)
            self.show_view('Fleet')
            self._dialog('Aircraft delivered', f'Aircraft {aircraft_id} is in your fleet.',
                         [('OK', lambda: None)])
        except Exception as exc:
            self._error('Acquisition rejected', exc)

    def render_scheduling(self):
        from app.gui.app import _button, _label
        if self._draft is None:
            self.content.add_widget(_label(
                'Choose a parked aircraft to begin a transient weekly draft.', height=62))
            for row in self.session.fleet(offset=0, limit=100):
                if row['status'] == 'PARKED':
                    self.content.add_widget(_button(
                        f"Plan {row['display_registration']} · {row['model_reference']} at "
                        f"{row['current_airport_reference_code']}",
                        lambda item=row: self.start_schedule(item['aircraft_id'])))
        else:
            draft = self._draft
            airports = {a['airport_id']: a['reference_code'] for a in self.session.airports()}
            self.content.add_widget(_label(
                f"Draft aircraft {draft.aircraft_id} · current stop {airports[draft.last_stop]}\n"
                f"{len(draft.legs)} unsaved leg(s). Philippine local dates and times.", height=78))
            for leg in draft.legs:
                self.content.add_widget(_label(
                    f"{leg['service_type']}  {airports[leg['origin_airport_id']]} → "
                    f"{airports[leg['destination_airport_id']]}  "
                    f"{leg['departure_utc']} UTC  Fare {self._money(leg['fare_minor'])}",
                    height=65))
            for text, action in [
                ('Add flight or positioning leg', self.show_add_leg),
                ('Add earliest return', self.add_return),
                ('Copy draft day', self.show_copy_day),
                ('Undo last leg', self.undo_leg),
                ('Save and publish draft', self.show_save_schedule),
                ('Discard draft', self.discard_schedule),
            ]:
                self.content.add_widget(_button(text, action))
        self.content.add_widget(_button(
            'Publish next rotation of active schedules', self.publish_next_schedule))

    def start_schedule(self, aircraft_id):
        if not self._management_ready():
            return
        try:
            self._draft = self.session.begin_scheduling(aircraft_id)
            self.refresh(force=True)
        except Exception as exc:
            self._error('Weekly planner', exc)

    def show_add_leg(self):
        if self._draft is None or not self._management_ready():
            return
        airports = self.session.airports()
        by_label = {airport_label(row): row['airport_id'] for row in airports}
        origin_label = next(label for label, aid in by_label.items()
                            if aid == self._draft.last_stop)
        dest_label = next(label for label, aid in by_label.items()
                          if aid != self._draft.last_stop)
        fields = [
            ('origin', 'Origin (aircraft must be present or explicitly positioned)',
             tuple(by_label), origin_label),
            ('destination', 'Destination', tuple(by_label), dest_label),
            ('date', 'Earliest local departure date YYYY-MM-DD', None,
             self.session.default_operating_date()),
            ('time', 'Earliest local time HH:MM', None, '08:00'),
            ('timing', 'Departure timing', ('Earliest available', 'Exact local time'), 'Earliest available'),
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
            value = {'minor': None}

            def update(*_args):
                try:
                    minor = self.session.suggested_economy_fare(
                        by_label[widgets['origin'].text],
                        by_label[widgets['destination'].text])
                except ValueError:
                    minor = None
                value['minor'] = minor
                suggestion.text = (
                    'Suggested Economy fare unavailable for this market.' if minor is None
                    else f'Suggested Economy fare: {self._money(minor)}. '
                         'Reference only; not a profit or booking guarantee.'
                )

            def use_suggestion():
                if value['minor'] is not None:
                    widgets['fare'].text = f"{value['minor'] // 100}.00"

            widgets['origin'].bind(text=update)
            widgets['destination'].bind(text=update)
            column.add_widget(_button('Use Suggested Fare', use_suggestion))
            update()

        def selected(values):
            origin, dest = by_label[values['origin']], by_label[values['destination']]
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
            self._dismiss()
            self.refresh(force=True)

        self._choice_form('Add weekly leg', fields, selected, decorate=decorate)

    def add_return(self):
        if self._draft is None or not self._management_ready():
            return
        try:
            working = deepcopy(self._draft)
            working.add_return()
            self._draft = working
            self.refresh(force=True)
        except Exception as exc:
            self._error('Add return', exc)

    def show_copy_day(self):
        if self._draft is None or not self._management_ready():
            return
        self._choice_form('Copy draft day', [
            ('source', 'Source local date YYYY-MM-DD', None,
             self.session.default_operating_date()),
            ('target', 'Target local date YYYY-MM-DD', None, ''),
        ], self._copy_day)

    def _copy_day(self, values):
        working = deepcopy(self._draft)
        working.copy_day(values['source'], values['target'])
        self._draft = working
        self._dismiss()
        self.refresh(force=True)

    def undo_leg(self):
        if self._draft is not None:
            self._draft.undo()
            self.refresh(force=True)

    def discard_schedule(self):
        self._draft = None
        self.refresh(force=True)

    def show_save_schedule(self):
        if self._draft is None or not self._management_ready():
            return
        self._choice_form('Save weekly schedule', [
            ('repeat', 'Optional inclusive repeat-through local date YYYY-MM-DD '
             '(blank = chosen dates only)', None, ''),
        ], self._review_schedule)

    def _review_schedule(self, values):
        repeat = values['repeat'] or None
        if repeat is not None and date.fromisoformat(repeat).isoformat() != repeat:
            raise ValueError('use canonical YYYY-MM-DD')
        self._dismiss()
        self._dialog('Publish schedule',
                     f"Save {len(self._draft.legs)} draft leg(s)"
                     + (f" weekly through {repeat}?" if repeat
                        else ' on their selected dates?'), [
                         ('Save and publish', lambda: self._save_schedule(repeat)),
                         ('Cancel', lambda: None)])

    def _save_schedule(self, repeat):
        try:
            result = self.session.save_scheduling(self._draft, repeat_until=repeat)
            self._draft = None
            self.refresh(force=True)
            self._dialog('Schedule published',
                         f"Published {len(result.created_dated_flight_ids)} dated flight(s).",
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
