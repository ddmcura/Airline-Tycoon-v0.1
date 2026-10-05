"""Operational Flights day and directional Booking week; UI state only."""
from datetime import date, timedelta, datetime
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from app.gui.management_table import ManagementTable
from app.gui.date_picker import DatePicker


def button(text, action):
    b=Button(text=text);b.bind(on_release=lambda *_:action());return b


def load_text(row):
    if row['load'] is None:return '—'
    return f"{row['passengers']}/{row['capacity']} · {row['load']/100:.1f}%"


class FlightsPage(ManagementTable):
    def __init__(self,app,state=None):
        self.app=app
        super().__init__('Flights — published operational day',
            [('departure','DEPARTURE origin local',235),('arrival','ARRIVAL destination local',235),
             ('id','OCCURRENCE',220),('registration','AIRCRAFT',150),('origin','ORIGIN',95),
             ('destination','DESTINATION',115),('status','STATUS',215),('load','PASSENGERS / SEATS',210),
             ('fare','FARE USD',100),('revenue','RESULT REVENUE USD',175)],
            search_fields=('id','registration','model','origin','destination'),state=state,
            filters=(('registration','Aircraft'),('origin','Origin'),('destination','Destination'),('status','Status')))
        self.state.setdefault('day',app.session.operational_context()['today'])
        self.day_picker=DatePicker(selected_date=self.state['day'])
        bar=BoxLayout();bar.add_widget(button('Previous Day',lambda:self.shift(-1)))
        bar.add_widget(button('Today',self.today));bar.add_widget(button('Next Day',lambda:self.shift(1)))
        bar.add_widget(self.day_picker);self.extra_controls.height=dp(56);self.extra_controls.add_widget(bar)
        self.day_picker.bind(selected_date=lambda _,value:self.choose_day(value))

    def choose_day(self,value):
        self.state['day']=date.fromisoformat(value).isoformat();self.refresh_data()
    def shift(self,n):self.day_picker.select((date.fromisoformat(self.state['day'])+timedelta(days=n)).isoformat())
    def today(self):self.day_picker.select(self.app.session.operational_context()['today'])
    def refresh_data(self):
        context=self.app.session.operational_context()
        rows=self.app.session.operational_flights(self.state['day'],include_spanning=True)
        for r in rows:
            r['departure_text']=r['departure_local'].replace('T',' ')
            r['arrival_text']=r['arrival_local'].replace('T',' ')
            r['status_text']={'PLANNED':'Upcoming','OPERATIONALLY_LOCKED':'Airborne','COMPLETED':'Completed'}.get(r['status'],r['status'])
            r['load_text']=load_text(r)+' '+r['load_basis']
            r['fare_text']=f"{r['fare']/100:.2f}" if r['service_type']=='PASSENGER' else '—'
            r['revenue_text']=f"{r['revenue']/100:.2f}" if r['revenue'] is not None else '—'
        self.set_rows(rows)
        relation='PAST' if self.state['day']<context['today'] else 'CURRENT' if self.state['day']==context['today'] else 'FUTURE'
        self.heading.text=f"Flights {self.state['day']} — {relation} | operating during day in {context['code']} / {context['timezone']}"
        self.footer.text=f"{len(self.visible_rows)} of {len(rows)} published occurrences | CONFIRMED upcoming / LOCKED airborne / CARRIED completed"
    def close(self):
        if self.day_picker._popup is not None:self.day_picker._popup.dismiss()
        super().close()


def booking_matrix(start, flights):
    """Display grouping only. Each cell contains one exact published occurrence.

    Columns are origin-local departure slots, ordinal within a hub-local day.
    Equal-time occurrences use immutable ID order; never merge their bookings.
    """
    first=date.fromisoformat(start);groups={};widths={}
    for r in flights:
        if r['service_type']!='PASSENGER' or r['status'] not in {'PLANNED','OPERATIONALLY_LOCKED','COMPLETED'}:continue
        slot=datetime.fromisoformat(r['departure_local']).strftime('%H:%M:%S')
        groups.setdefault((r['operational_date'],slot),[]).append(r)
    for (day,slot),items in groups.items():widths[slot]=max(widths.get(slot,0),len(items))
    columns=[('day','DAY / HUB DATE',185)]
    for slot,count in sorted(widths.items()):
        for n in range(count):columns.append((f'{slot}#{n}',slot+(f' #{n+1}' if count>1 else ''),285))
    if not widths:columns.append(('empty','NO PUBLISHED SERVICE',285))
    rows=[]
    for n in range(7):
        day=(first+timedelta(days=n)).isoformat();row={'id':day,'day':day,'day_text':(first+timedelta(days=n)).strftime('%a %d %b'),'occurrences':{}}
        for key,_,_ in columns[1:]:row[key]=None
        for (d,slot),items in groups.items():
            if d!=day:continue
            for ordinal,item in enumerate(sorted(items,key=lambda r:r['id'])):
                key=f'{slot}#{ordinal}';row[key]=item['load'];row['occurrences'][key]=item
                row[key+'_text']=load_text(item)+f" {item['load_basis']}\n"+item['registration']+'\n'+item['id']
        rows.append(row)
    return columns,rows


class BookingsPage(ManagementTable):
    def __init__(self,app,state=None):
        self.app=app;self.markets=[]
        super().__init__('Bookings — directional weekly passenger load',
            [('day','DAY / HUB DATE',185),('empty','NO PUBLISHED SERVICE',285)],search_fields=('day','day_text'),state=state,sortable=False,row_height=76,pin_first=True)
        self.state.setdefault('week',app.session.operational_context()['week_start'])
        self.state.setdefault('market',None)
        self.market_selector=Spinner(text='No published passenger markets')
        self.market_selector.bind(text=self.choose_market)
        bar=BoxLayout();bar.add_widget(button('Previous Week',lambda:self.shift(-1)))
        bar.add_widget(button('Current Week',self.current));bar.add_widget(button('Next Week',lambda:self.shift(1)))
        bar.add_widget(self.market_selector);self.extra_controls.height=dp(56);self.extra_controls.add_widget(bar)
        self.search.hint_text='Filter weekday / hub date'
    def choose_market(self,_,label):
        found=next((r for r in self.markets if r['label']==label),None)
        if found:
            self.state['market']=[found['origin_id'],found['destination_id']];self.refresh_data()
    def shift(self,n):
        self.state['week']=(date.fromisoformat(self.state['week'])+timedelta(days=7*n)).isoformat();self.refresh_data()
    def current(self):self.state['week']=self.app.session.operational_context()['week_start'];self.refresh_data()
    def refresh_data(self):
        self.markets=self.app.session.service_markets()
        pairs=[[r['origin_id'],r['destination_id']] for r in self.markets]
        if self.state['market'] not in pairs:self.state['market']=pairs[0] if pairs else None
        selected=next((r['label'] for r in self.markets if [r['origin_id'],r['destination_id']]==self.state['market']), 'No published passenger markets')
        self.market_selector.values=tuple(r['label'] for r in self.markets)
        # Programmatic value changes must not trigger recursive refresh.
        self.market_selector.unbind(text=self.choose_market);self.market_selector.text=selected;self.market_selector.bind(text=self.choose_market)
        flights=self.app.session.operational_flights(self.state['week'],days=7,market=self.state['market']) if self.state['market'] else []
        columns,rows=booking_matrix(self.state['week'],flights)
        self.set_columns_and_rows(columns,rows)
        context=self.app.session.operational_context();end=date.fromisoformat(self.state['week'])+timedelta(days=6)
        self.heading.text=f"Bookings {selected} | Week {self.state['week']}–{end} | {context['code']} / {context['timezone']}"
        self.footer.text='CONFIRMED upcoming / LOCKED departure manifest / CARRIED completed | — no applicable service; slot columns use origin-local time'
