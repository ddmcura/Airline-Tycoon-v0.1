"""Kivy controls over detached Session reads and certified quarterly commands."""
from datetime import date, timedelta
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from app.gui.scrolling import AxisScrollView
from app.gui.airport_selector import AirportSelector
from app.gui.weekday_picker import WeekdayPicker
from app.gui.date_picker import DatePicker
from app.inputs import parse_usd_fare


def label(text, height=72):
    widget=Label(text=text,size_hint_y=None,height=dp(height),halign='left',valign='middle')
    widget.bind(width=lambda w,n:setattr(w,'text_size',(n-dp(16),None)))
    widget.bind(texture_size=lambda w,n:setattr(w,'height',max(dp(30),n[1]+dp(12))))
    return widget


def button(text, action):
    widget=Button(text=text,size_hint_y=None,height=dp(52))
    widget.bind(on_release=lambda *_:action())
    return widget


def issues_text(issues):
    return '\n'.join(f'{i.code}: {i.message} ({i.path})' for i in issues)


class QuarterlyPage(BoxLayout):
    def __init__(self, app, state=None):
        super().__init__(orientation='vertical',spacing=dp(4))
        self.app=app; self.controller=app.quarterly_controller
        self.closed=False; self._signature=None; self._form_popup=None; self._selectors=[]
        self._binding=app.session.binding_revision
        self.heading=label('Quarterly planning',150); self.add_widget(self.heading)
        self.message=label('',60)
        self.message_scroll=AxisScrollView(do_scroll_x=False,size_hint_y=None,height=dp(60))
        self.message_scroll.add_widget(self.message);self.add_widget(self.message_scroll)
        self.message.bind(texture_size=lambda _,n:setattr(self.message_scroll,'height',min(dp(80),max(dp(38),n[1]+dp(12)))))
        self.plans=Spinner(text='Eligible planning quarter',size_hint_y=None,height=dp(52))
        self._plan_ids={}; self._updating_plans=False
        self.plans.bind(text=self._choose_plan); self.add_widget(self.plans)
        actions=[('Create service',lambda:self.service_form('create')),
            ('Edit frequency',lambda:self.service_form('edit')),
            ('Revise fare',self.fare_form),('Add frequency',lambda:self.service_form('add')),
            ('Replace endpoints',lambda:self.service_form('replace')),('Remove frequency',self.remove)]
        actions += [('Continue service',self.continue_form),('Retire service',self.retire_form),
                ('Inspect readiness',self.inspect),('Manual Publish',self.publish),
                ('Retry publication',self.retry),('Published day',self.browse)]
        self.action_strip=self.app._horizontal_buttons([(caption,lambda a=action:self.run(a)) for caption,action in actions])
        self.controls={w.text:w for w in self.action_strip.walk() if isinstance(w,Button)}
        self.add_widget(self.action_strip)
        bar=BoxLayout(size_hint_y=None,height=dp(52))
        bar.add_widget(button('Previous services',lambda:self.page(-32)))
        bar.add_widget(button('Next services',lambda:self.page(32)));self.add_widget(bar)
        self.scroll=AxisScrollView(do_scroll_x=False)
        self.rows=GridLayout(cols=1,size_hint_y=None,spacing=dp(4))
        self.rows.bind(minimum_height=self.rows.setter('height')); self.scroll.add_widget(self.rows)
        self.add_widget(self.scroll)

    def run(self, action):
        try: return action()
        except Exception as exc: self.app._error('Quarterly planning',exc)

    def refresh_data(self):
        if self._binding != self.app.session.binding_revision:
            self.close_form();self._binding=self.app.session.binding_revision
        page=self.controller.refresh()
        baseline=page['baseline']
        self.heading.text=(f"Quarterly planning — isolated development career\nUTC {page['time_utc']} | Operating {page['operating_quarter']} | Eligible {page['target_quarter']}\n"
            f"Viewing {page['selected_quarter']} — {'Published / locked' if page['published_at_utc'] else 'Unpublished'} | Deadline {page['deadline_utc']} UTC\n"
            f"Baseline: {baseline['quarter_id'] if baseline else 'None'} | {page['total']} weekly frequencies")
        fence=page['fence']
        if fence and fence['failure']:
            failure=fence['failure']
            self.message.text=f"BLOCKED: publication of {fence['next_quarter_id']}\n{failure['code']}: {failure['message']}\n"+'\n'.join(
                f"{i.get('code','')}: {i.get('message','')}" for i in failure['details'])+'\nCorrect this unpublished quarter, then explicitly Retry publication.'
        elif self.controller.issues:
            self.message.text=issues_text(self.controller.issues)
        elif self.controller.last_published:
            self.message.text='Schedule committed. Simulation UTC is unchanged. Eligible planning has advanced.'
        elif self.controller.readiness is None:
            self.message.text='Edits save the planning version. Manual Publish commits the schedule and opens eligible bookings. Use Inspect readiness for feasibility and actual positioning.'
        options={'Eligible planning quarter':None}
        options.update({p['quarter_id']+' — '+p['status']:p['plan_id'] for p in page['plans']})
        self._plan_ids=options; self.plans.values=tuple(options)
        self._updating_plans=True
        try:
            self.plans.text=next((caption for caption,identity in options.items()
                if identity == self.controller.plan_id),'Eligible planning quarter')
        finally:
            self._updating_plans=False
        for caption in ('Create service','Edit frequency','Revise fare','Add frequency','Replace endpoints','Remove frequency','Continue service','Retire service'):
            self.controls[caption].disabled=not page['editable']
        self.controls['Manual Publish'].disabled=not page['editable'] or bool(fence and fence['failure'])
        self.controls['Retry publication'].disabled=not bool(fence and fence['failure'])
        self.controls['Published day'].disabled=not bool(page['published_at_utc'])
        signature=(page['rows'],self.controller.selected,page['offset'])
        if signature != self._signature:
            self.scroll.stop_motion(); self.rows.clear_widgets()
            for row in page['rows']:
                key=(row['service_id'],row['slot_number'])
                text=(('Selected: ' if key == self.controller.selected else '')+
                    f"{row['flight_number']} / frequency {row['slot_number']} | {row['origin_code']} -> {row['destination_code']} | {row['aircraft_registration']}\n"
                    f"{', '.join(('Mon','Tue','Wed','Thu','Fri','Sat','Sun')[d] for d in row['weekdays'])} {row['departure_local_time']} {row['origin_timezone']} | USD {row['fare_offer']['amount_minor']//100}.{row['fare_offer']['amount_minor']%100:02d}\n"
                    f"Service identity: {row['service_id']}")
                widget=button(text,lambda k=key:self.run(lambda:self.select(k)));widget.height=dp(95)
                self.rows.add_widget(widget)
            if not page['rows']: self.rows.add_widget(label('No weekly services on this page. Create a service or continue an earlier service.'))
            self._signature=signature

    def select(self,key): self.controller.select_slot(key); self.refresh_data()
    def page(self,delta):
        new=max(0,self.controller.offset+delta)
        if new < self.controller.page['total'] or new == 0:
            self.controller.offset=new;self.controller.selected=None;self.refresh_data()
    def _choose_plan(self,_,value):
        if not self._updating_plans and value in self._plan_ids:
            self.run(lambda:(self.controller.select_plan(self._plan_ids[value]),self.refresh_data()))

    def result(self,result):
        if not result.succeeded:
            self.app._error('Quarterly command rejected',issues_text(result.issues))
        self.refresh_data(); self.app.refresh(force=True)

    def inspect(self):
        result=self.controller.inspect()
        if not result.succeeded:
            self.message.text=issues_text(result.issues);return
        def verdict(value): return 'Not available' if value is None else 'Yes' if value else 'No'
        self.message.text=(f"Publication eligible: {verdict(result.publication_eligible)} | Planning feasible: {verdict(result.planning_feasible)} | Execution ready: {verdict(result.execution_ready)}\n"+
            issues_text(result.eligibility_issues+result.planning_issues+result.execution_blockers)+
            '\nHypothetical positioning is planning only; it creates no executable flight. Publication revalidates all facts.')

    def publish(self):
        self.app._after_runtime_pause(self._review_publication)
    def _review_publication(self):
        self.inspect()
        result=self.controller.prepare_publication()
        if not result.succeeded: self.result(result);return
        page=self.controller.page
        readiness=self.controller.readiness
        readiness_text=('Eligibility: '+str(readiness.publication_eligible)+' | Execution readiness: '+str(readiness.execution_ready)
            if readiness and readiness.succeeded else 'Readiness unavailable; publication must revalidate.')
        if readiness and readiness.succeeded:
            readiness_text+='\n'+issues_text(readiness.execution_blockers+readiness.eligibility_issues)
        self.app._dialog('Commit quarterly schedule',
            f"Publish {page['selected_quarter']} with {page['total']} frequencies?\n"+
            'Services on this page: '+', '.join(dict.fromkeys(r['flight_number'] for r in page['rows']))+'\n'+
            ('Carry forward the preceding published baseline.\n' if page['carry_forward'] else 'Use the complete edited plan, including removals.\n')+
            'This commitment opens eligible bookings and permanently locks ordinary edits. Operating dates and simulation UTC stay unchanged.\n'+
            readiness_text+'\nFresh publication validation is required at confirmation.',
            [('Publish schedule',lambda:self.run(lambda:self.result(self.controller.confirm_publication()))),
             ('Keep planning',self.cancel_confirmation)],message_height=230,scroll_message=True)
    def cancel_confirmation(self): self.controller.confirmation=None
    def retry(self):
        report=self.controller.retry()
        if report.result.failure: self.app._error('Publication remains blocked',report.result.failure)
        self.refresh_data();self.app.refresh(force=True)

    def chosen(self):
        key=self.controller.selected
        row=next((r for r in self.controller.page['rows'] if (r['service_id'],r['slot_number']) == key),None)
        if row is None: raise ValueError('select a weekly frequency first')
        if self.controller.page['plan_id'] is None:
            raise ValueError('this is the carry-forward preview; Continue service to initialize the editable plan')
        return row

    def fare_form(self):
        row=self.chosen()
        self.app._form('Revise fare — selected frequency',[('fare','Fare USD',f"{row['fare_offer']['amount_minor']//100}.{row['fare_offer']['amount_minor']%100:02d}")],
            lambda values:(self.app._dismiss(),self.result(self.controller.fare(parse_usd_fare(values['fare'])))))

    def service_form(self,mode):
        self.app._after_runtime_pause(lambda:self.run(lambda:self._service_form(mode)))
    def _service_form(self,mode):
        page=self.controller.refresh(); self.controller._target()
        row=None if mode == 'create' else self.chosen()
        ports=self.app.session.airports(); fleet=self.app.session.management_fleet()
        if not fleet: raise ValueError('acquire an aircraft first')
        aircraft_labels={r['registration']+' — '+r['model']:r['aircraft_id'] for r in fleet}
        aircraft=Spinner(values=tuple(aircraft_labels),text=next(iter(aircraft_labels)),size_hint_y=None,height=dp(52))
        if row:
            aircraft.text=next(k for k,v in aircraft_labels.items() if v == row['planned_aircraft_id'])
        elif self.controller.aircraft_id in aircraft_labels.values():
            aircraft.text=next(k for k,v in aircraft_labels.items() if v == self.controller.aircraft_id)
        default_origin=self.app.session.header()['base_airports'][0]['airport_id']
        default_destination=next(p['airport_id'] for p in ports if p['airport_id'] != default_origin)
        origin=AirportSelector(ports,selected_id=row['origin_airport_id'] if row else default_origin)
        destination=AirportSelector(ports,selected_id=row['destination_airport_id'] if row else default_destination)
        origin.disabled=destination.disabled=mode in ('edit','add')
        first=date.fromisoformat(page['time_utc'][:10]);first-=timedelta(days=first.weekday())
        days=WeekdayPicker(tuple(first+timedelta(days=n) for n in range(7)),selected=row['weekdays'] if row else range(7))
        time=TextInput(text=row['departure_local_time'] if row else '09:00:00',multiline=False,size_hint_y=None,height=dp(48))
        fare=TextInput(text=f"{row['fare_offer']['amount_minor']//100}.{row['fare_offer']['amount_minor']%100:02d}" if row else '100.00',multiline=False,size_hint_y=None,height=dp(48))
        prefix=TextInput(text='DEV',multiline=False,size_hint_y=None,height=dp(48))
        kind=Spinner(values=('PASSENGER','DEADHEAD'),text=row['service_type'] if row else 'PASSENGER',size_hint_y=None,height=dp(52))
        fold=Spinner(values=('0','1'),text=str(row['departure_local_fold']) if row else '0',size_hint_y=None,height=dp(52))
        # Existing prefix is an immutable airline policy, never inferred from a
        # display flight number. The session provides it through its detached page.
        prefix.text=page.get('flight_number_prefix') or 'DEV'
        root=GridLayout(cols=1,size_hint_y=None,spacing=dp(5),padding=dp(8));root.bind(minimum_height=root.setter('height'))
        for caption,widget in [('Aircraft',aircraft),('Origin',origin),('Destination',destination),('Weekly weekdays',days),
                ('Departure HH:MM:SS, origin local',time),('Fare USD',fare),('Service type',kind),('DST fold (0 normally, 1 repeated hour)',fold)]:
            root.add_widget(label(caption,30));root.add_widget(widget)
        if mode in ('create','replace'):root.add_widget(label('Airline flight-number prefix (first service only)',35));root.add_widget(prefix)
        def submit():
            try:
                slot=self.app.session.quarterly_slot_input(aircraft_id=aircraft_labels[aircraft.text],
                    origin_id=origin.selected_id,destination_id=destination.selected_id,
                    weekdays=sorted(days.selected_indices),departure_local_time=time.text.strip(),
                    fare_minor=parse_usd_fare(fare.text.strip()),service_type=kind.text,fold=int(fold.text))
                if mode == 'create':result=self.controller.create(slot,prefix.text.strip())
                elif mode == 'replace':result=self.controller.replace(slot,prefix.text.strip())
                elif mode == 'add':result=self.controller.add_frequency(slot)
                else:
                    changes={k:v for k,v in slot.items() if k not in ('origin_airport_id','destination_airport_id')}
                    result=self.controller.edit(changes)
                if result.succeeded:self.close_form()
                self.result(result)
            except Exception as exc:self.app._error('Service edit rejected',exc)
        root.add_widget(button('Save planning edit',submit));root.add_widget(button('Cancel',self.close_form))
        scroll=AxisScrollView(do_scroll_x=False);scroll.add_widget(root)
        self._selectors=[origin,destination];self._form_popup=Popup(title=mode.title()+' weekly service',content=scroll,size_hint=(.95,.95),auto_dismiss=False)
        self._form_popup.open()

    def remove(self):
        self.chosen();self.app._dialog('Remove frequency','Remove only this frequency from the unpublished plan? This does not retire its identity.',
            [('Remove',lambda:self.run(lambda:self.result(self.controller.remove()))),('Cancel',lambda:None)])
    def retire_form(self):
        services=[s for s in self.controller.page['services'] if not s['retired']]
        self.app._list_popup('Choose service to retire — remove editable membership first',[
            (s['flight_number']+' | '+s['service_id'],lambda sid=s['service_id']:self.app._dialog('Retire service',
                'Retire this identity permanently? Existing published obligations and history remain.',
                [('Retire',lambda:self.run(lambda:self.result(self.controller.retire(sid)))),('Cancel',lambda:None)])) for s in services])
    def continue_form(self):
        target=self.controller.page['selected_quarter']
        sources=[p for p in self.controller.page['plans'] if p['quarter_id'] < target]
        def frequencies(source):
            page=self.app.session.quarterly_planning_page(source['plan_id'])
            self.app._list_popup('Continue an earlier frequency',[
                (r['flight_number']+f" / frequency {r['slot_number']}",lambda row=r:self.run(lambda:self.result(self.controller.continue_slot(source,row))))
                for r in page['rows'] if not r['retired']])
        self.app._list_popup('Choose earlier plan',[(p['quarter_id'],lambda source=p:frequencies(source)) for p in sources])

    def browse(self):
        page=self.controller.page
        # Date selection is origin-local, and each request is at most 32 references.
        picker=DatePicker(selected_date=f"{page['selected_quarter'][:4]}-{(int(page['selected_quarter'][-1])-1)*3+1:02d}-02")
        body=BoxLayout(orientation='vertical');body.add_widget(label('Origin-local departure date; times below are UTC.',55));body.add_widget(picker)
        scroll=AxisScrollView(do_scroll_x=False);rows=GridLayout(cols=1,size_hint_y=None);rows.bind(minimum_height=rows.setter('height'));scroll.add_widget(rows);body.add_widget(scroll)
        offset=[0]
        def render(delta=0):
            try:
                offset[0]=max(0,offset[0]+delta)
                result=self.app.session.quarterly_published_day(page['plan_id'],picker.selected_date,offset=offset[0])
                rows.clear_widgets()
                for r in result['rows']:
                    rows.add_widget(label(f"{r['flight_number']} | {r['origin']} -> {r['destination']} | {r['aircraft']}\n{r['departure_utc']} -> {r['arrival_utc']} UTC\n"
                        f"{r['status']} | {r['passengers']}/{r['capacity']} seats | {r['key']}\nPublished {r['published_at_utc']} | {r['plan_id']} version {r['revision']}",110))
                if not result['rows']:rows.add_widget(label('No occurrences on this page/date.'))
            except Exception as exc:self.app._error('Published schedule',exc)
        picker.bind(selected_date=lambda *_:(offset.__setitem__(0,0),render()))
        bar=BoxLayout(size_hint_y=None,height=dp(52));bar.add_widget(button('Previous',lambda:render(-32)));bar.add_widget(button('Next',lambda:render(32)));body.add_widget(bar)
        popup=Popup(title='Published schedule — bounded date view',content=body,size_hint=(.97,.95));body.add_widget(button('Close',popup.dismiss));popup.open();render()
        self._form_popup=popup;self._selectors=[picker]

    def close_form(self):
        for selector in self._selectors:
            popup=getattr(selector,'popup',None) or getattr(selector,'_popup',None)
            if popup:popup.dismiss()
        self._selectors=[]
        if self._form_popup:self._form_popup.dismiss();self._form_popup=None
    def snapshot(self):return {}
    def close(self):
        self.closed=True;self.controller.confirmation=None;self.close_form()
        self.scroll.dispose();self.message_scroll.dispose();self.action_strip.dispose()
