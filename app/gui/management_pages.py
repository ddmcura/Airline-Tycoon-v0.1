"""Active-only Fleet, aircraft detail and directional Research pages."""
from decimal import Decimal, ROUND_HALF_UP
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from app.gui.management_table import ManagementTable
from app.gui.airport_selector import AirportSelector
from app.gui.scrolling import AxisScrollView

FLEET_COLUMNS = [('hub','HUB',90),('name','AIRPLANE NAME',155),('registration','REGISTRATION',150),
                 ('model','MODEL',165),('manufacturer','MANUFACTURER',150),('weekly_load','WEEKLY LOAD',145),
                 ('status','STATUS',230),('details','DETAILS',105)]
RESEARCH_COLUMNS = [('code','IATA',80),('name','AIRPORT NAME',320),('distance','DISTANCE km',135),
                    ('bookers','BASE DAILY BOOKERS',170),('available','MARKET AVAILABLE',170),
                    ('seats','YOUR SEATS',125),('fare','FARE USD',150),('confirmed','CONFIRMED',125),
                    ('add','ADD FLIGHT',125)]


class FleetPage(ManagementTable):
    def __init__(self, app, state=None):
        self.app = app
        super().__init__('Fleet Overview — Hub means aircraft home base', FLEET_COLUMNS,
            search_fields=('name','registration','model','manufacturer'), state=state,
            filters=(('hub','Hub'),('manufacturer','Manufacturer'),('model','Model'),('status_filter','Status')),
            actions={'details':('Details',lambda r:app.open_aircraft_details(r['id']))})

    def refresh_data(self):
        rows = self.app.session.management_fleet()
        for r in rows:
            r['id'] = r['aircraft_id']
            r['weekly_load_text'] = f"{r['weekly_load']/100:.2f}%" if r['weekly_load'] is not None else '—'
        self.set_rows(rows)
        if rows:
            self.footer.text = f"{len(self.visible_rows)} of {len(self.rows)} records | Week {rows[0]['week_start']}: carried + confirmed / published passenger seats"


class ResearchPage(ManagementTable):
    def __init__(self, app, state=None):
        self.app = app
        super().__init__('Research — directional markets', RESEARCH_COLUMNS,
                         search_fields=('code','name'), state=state,
                         actions={'add':('Add Flight',lambda r:app.research_add_flight(r['origin_id'],r['destination_id']))})
        ports = app.session.airports()
        if not app._research_origin: app._research_origin = app.session.header()['base_airports'][0]['airport_id']
        self.origin = AirportSelector(ports,selected_id=app._research_origin)
        self.destination = AirportSelector(ports,selected_id=app._research_destination,
                                           allow_clear=True,placeholder='All destinations')
        app._research_origin_selector = self.origin; app._research_destination_selector = self.destination
        self.origin.bind(selected_id=lambda _,k: self._origin(k))
        self.destination.bind(selected_id=lambda _,k: self._destination(k))
        self.extra_controls.height = dp(54)
        airport_row = BoxLayout()
        airport_row.add_widget(self.origin); airport_row.add_widget(self.destination)
        self.extra_controls.add_widget(airport_row)

    def _origin(self, identity):
        self.app._research_origin = identity; self.refresh_data()

    def _destination(self, identity):
        self.app._research_destination = identity or None; self.refresh_data()

    def refresh_data(self):
        source = self.app.session.market_opportunities(origin_airport_id=self.app._research_origin, limit=2000)
        rows = []
        for r in source:
            if self.app._research_destination and self.app._research_destination != r['destination_airport_id']:continue
            fare = r['player_fare_minor']
            suggested = not r['qualifying_player_service_exists']
            if suggested: fare = self.app.session.suggested_economy_fare(r['origin_airport_id'],r['destination_airport_id'])
            rows.append({'id':r['market_id'],'code':r['destination_airport_reference_code'],
                         'name':r['destination_airport_name'],'distance':r['distance_km'],
                         'bookers':int(Decimal(str(r['base_daily_directional_bookers'])).quantize(Decimal(1),rounding=ROUND_HALF_UP)),
                         'available':r['market_available'],'available_text':'Yes' if r['market_available'] else 'No',
                         'seats':r['player_published_capacity'],'fare':fare,
                         'fare_text':('Mixed fares' if fare is None else f"{fare/100:.2f}"+(' suggested' if suggested else '')),
                         'confirmed':r['current_confirmed_bookings'],
                         'origin_id':r['origin_airport_id'],'destination_id':r['destination_airport_id']})
        self.set_rows(rows)
        self.footer.text = f'{len(self.visible_rows)} of {len(self.rows)} records | Available = airport availability; seats/confirmed = remaining publication horizon'

    def close(self):
        for selector in (self.origin,self.destination):
            if selector.popup is not None: selector.popup.dismiss()
        super().close()


class AircraftDetailsPage(BoxLayout):
    def __init__(self, app, aircraft_id, state=None):
        super().__init__(orientation='vertical',spacing=dp(4))
        self.app=app; self.aircraft_id=aircraft_id; self.closed=False; self._attributes=None
        bar=BoxLayout(size_hint_y=None,height=dp(52))
        for text,action in [('Back to Fleet',lambda:app.show_view('Fleet')),
                            ('Schedule Aircraft',lambda:app.schedule_handoff(aircraft_id))]:
            b=Button(text=text);b.bind(on_release=lambda _, a=action:a());bar.add_widget(b)
        self.add_widget(bar)
        self.info_scroll=AxisScrollView(do_scroll_x=False,size_hint_y=.45)
        self.info=BoxLayout(orientation='vertical',size_hint_y=None,height=dp(52));self.info_scroll.add_widget(self.info);self.add_widget(self.info_scroll)
        self.table=ManagementTable('Current week — published flights only',
            [('day','DAY',155),('departure','DEPARTURE origin local',270),('origin','ORIGIN',90),
             ('destination','DESTINATION',110),('arrival','ARRIVAL destination local',270),('state','STATE',210)],
            search_fields=('origin','destination','state'),state=(state or {}).get('table'))
        self.table.size_hint_y=.55;self.add_widget(self.table)

    def refresh_data(self):
        data=self.app.session.aircraft_details(self.aircraft_id)
        attributes=data['attributes']
        if attributes != self._attributes:
            # Prepare complete replacement before mounting, never clear live geometry.
            replacement=BoxLayout(orientation='vertical',size_hint_y=None,height=dp(len(attributes)*38))
            for title,value in attributes:
                replacement.add_widget(Label(text=f'{title}: {value}',size_hint_y=None,height=dp(38),halign='left'))
            self.info_scroll.stop_motion();old=self.info
            self.info_scroll.remove_widget(old);self.info_scroll.add_widget(replacement);self.info=replacement
            self._attributes=attributes
        self.table.heading.text='Current week '+data['week_start']+' — published flights only'
        self.table.set_rows(data['schedule'])

    def snapshot(self):return {'table':self.table.snapshot()}
    def close(self):self.closed=True;self.info_scroll.dispose();self.table.close()
