"""Kivy presentation for modern market, acquisition, and weekly scheduling."""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from app.gui.airport_selector import AirportSelector, airport_label
from app.gui.date_picker import DatePicker
from app.gui.scrolling import AxisScrollView
from app.gui.weekly_workspace import WeeklyWorkspace


class GameplayViews(WeeklyWorkspace):
    """UI-only mixin. Session/domain commands own every authoritative mutation."""

    def _choice_form(self, title, fields, submit, *, decorate=None):
        from app.gui.app import _button, _label
        content = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(8))
        scroll = AxisScrollView()
        column = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None)
        column.bind(minimum_height=column.setter('height'))
        widgets = {}
        for key, caption, choices, initial in fields:
            column.add_widget(_label(caption, height=36))
            if choices is None and key in {'date', 'repeat'}:
                widget = DatePicker(selected_date=initial,
                                    display_date=(self._schedule_week.isoformat()
                                                  if self._schedule_week else None),
                                    allow_clear=key == 'repeat')
            elif choices is None:
                widget = TextInput(text=initial, multiline=False,
                                   size_hint_y=None, height=dp(52))
            elif choices and isinstance(choices[0], dict):
                widget = AirportSelector(choices, selected_id=initial)
            else:
                widget = Spinner(text=initial or choices[0], values=choices,
                                 size_hint_y=None, height=dp(52))
            column.add_widget(widget)
            widgets[key] = widget
            if decorate is not None:
                decorate(column, widgets, key)
        scroll.add_widget(column)
        content.add_widget(scroll)

        def apply():
            try:
                submit({key: (widget.selected_id if isinstance(widget, AirportSelector)
                              else widget.text.strip()) for key, widget in widgets.items()})
            except Exception as exc:
                self._error(title, exc)

        content.add_widget(_button('Continue', apply))
        content.add_widget(_button('Cancel', self._dismiss))
        self._popup = Popup(title=title, content=content, size_hint=(.96, .9),
                            auto_dismiss=False)
        self._popup.open()

    def _management_ready(self, *, refresh=True):
        if not self._idle():
            return False
        # Callbacks and pump are serialized on Kivy's event loop.
        self.session.pause()
        if self.session.runtime.draining:
            self._error('Pausing', 'Earned time is draining. Retry this edit when paused.')
            return False
        if refresh:
            self.refresh(force=True)
        return True

    def choose_research_origin(self):
        self._popup = self._research_origin_selector.open_dropdown()

    def choose_research_destination(self):
        self._popup = self._research_destination_selector.open_dropdown()

    def _set_research_origin(self, airport_id):
        self._research_origin = airport_id
        self.refresh(force=True)

    def _set_research_destination(self, airport_id):
        self._research_destination = airport_id or None
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
        fields = [('delivery', 'Delivery base or hub', locations,
                   locations[0]['airport_id'])]
        if mode == 'lease':
            fields.extend((
                ('product', 'Lease product', ('Operating lease', 'Lease-to-own'), 'Operating lease'),
                ('years', 'Term in years (1–5)', None, '2'),
            ))

        def selected(values):
            location = values['delivery']
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
                           f"Immediate delivery to {next(airport_label(row) for row in locations if row['airport_id'] == location)}")
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
