"""Patch 2 stable management pages and committed presentation regressions."""
import gc
import json
import math
import os
os.environ.setdefault('KIVY_NO_FILELOG','1')
os.environ.setdefault('KIVY_NO_ARGS','1')
import tempfile
import unittest
import weakref
from unittest.mock import patch
from kivy.clock import Clock
from kivy.effects.scroll import ScrollEffect
from app.gui.app import AirlineTycoonApp
from app.gui.management_table import ManagementTable
from app.gui.navigation import section_for
from app.session import Stage1Session
from tests.test_gui_foundation import FakeClock


class ManagementGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.clock=FakeClock()
        self.app=AirlineTycoonApp(session_factory=lambda:Stage1Session(save_root=self.temp.name,runtime_clock=self.clock))
        self.app.build();self.app.create_new_game('CEO','Table Air','MNL');self.s=self.app.session
        self.ports={r['reference_code']:r['airport_id'] for r in self.s.airports()}
        self.aircraft=self.s.fleet()[0]['aircraft_id']
    def tearDown(self):
        self.app._dismiss();self.app.on_stop();self.temp.cleanup()
    def service(self):
        draft=self.s.begin_scheduling(self.aircraft)
        draft.add(self.ports['MNL'],self.ports['DVO'],departure_utc='2026-09-02T08:00:00Z',fare_minor=11600)
        draft.add_return(fare_minor=11600);self.s.save_scheduling(draft)
        return draft

    def test_sections_and_one_active_region(self):
        for page,section in [('Fleet','Fleet'),('Research','Network'),('Schedule','Operations'),('Acquire','Fleet'),('Saves','Game / System'),('Bookings','Operations')]:
            self.app.show_view(page);self.assertEqual(self.app._section,section)
            self.assertEqual(len(self.app.page_host.children),1)
            self.assertEqual(section_for(page),section)

    def test_pending_schedule_focus_is_cancelled_on_navigation(self):
        self.app.show_view('Schedule');self.app.start_schedule(self.aircraft)
        self.app._focus_week_start()
        event=self.app._week_focus_event
        self.assertTrue(event.is_triggered)
        self.app.show_view('Fleet')
        self.assertFalse(event.is_triggered)
        self.assertIsNone(self.app._week_focus_event)
        # A previously dequeued callback must also reject its detached target.
        event.get_callback()(0)
        self.assertEqual(self.app.current_view,'Fleet')
        self.assertEqual(len(self.app.page_host.children),1)

    def test_fixed_controls_and_stable_refresh(self):
        self.app.show_view('Fleet');page=self.app.content
        cells=dict(page.cells[self.aircraft]);viewport=page.viewport
        page.viewport.scroll_y=.4
        for _ in range(4):self.app.refresh(force=True)
        self.assertIs(self.app.content,page);self.assertIs(page.viewport,viewport)
        self.assertEqual(page.cells[self.aircraft],cells)
        self.assertIs(page.controls.parent,page);self.assertIs(page.body.parent,page.viewport)
        self.assertEqual(page.data_updates,1)

    def test_fleet_identity_neutral_load_and_attributes(self):
        before=self.s.authoritative_bytes();rows=self.s.management_fleet();r=rows[0]
        self.assertEqual(r['aircraft_id'],self.aircraft);self.assertEqual(r['registration'],'RP-C0001')
        self.assertEqual(r['hub'],'MNL');self.assertEqual(r['manufacturer'],'Airbus')
        self.assertIsNone(r['name']);self.assertIsNone(r['weekly_load']);self.assertEqual(r['weekly_seats'],0)
        self.assertEqual(r['status'],'Parked at MNL');self.assertEqual(before,self.s.authoritative_bytes())

    def test_weekly_load_from_confirmed_then_carried_authority(self):
        self.service();self.s.advance_to('2026-09-02T00:00:00Z')
        r=self.s.management_fleet()[0];world=self.s.world['world_state']
        self.assertEqual(r['weekly_seats'],388)
        from game.booking.indexes import rebuild_booking_indexes
        counts=rebuild_booking_indexes(self.s.world).booked_passenger_count_by_dated_flight_id
        expected=sum(counts.get(k,0) for k in world['dated_flights'])
        self.assertEqual(r['weekly_passengers'],expected)
        self.assertEqual(r['weekly_load'],expected*10000//388)
        self.s.advance_to('2026-09-02T12:00:00Z')
        r=self.s.management_fleet()[0]
        self.assertEqual(r['weekly_passengers'],sum(v['carried_passenger_count'] for v in self.s.world['world_state']['flight_results'].values()))

    def test_fleet_search_filters_sort_and_view_state(self):
        self.app.show_view('Fleet');page=self.app.content
        page.search.text='aIrBuS';self.assertEqual(len(page.visible_rows),1)
        page.search.focus=True
        page.filter_widgets['hub'][0].text='All Hub';page.sort_by('registration');page.sort_by('registration')
        page.viewport.scroll_x=.4
        self.app.show_view('Overview');self.assertTrue(page.closed)
        self.assertFalse(page.search.focus)
        self.app.show_view('Fleet');new=self.app.content
        self.assertIsNot(new,page);self.assertEqual(new.search.text,'aIrBuS')
        self.assertTrue(new.state['descending']);self.assertEqual(new.viewport.scroll_x,.4)
        new.search.text='impossible';self.assertEqual(new.visible_rows,[]);self.assertTrue(new.body.children)
        new.reset();self.assertEqual(len(new.visible_rows),1)

    def test_deterministic_numeric_and_text_sort(self):
        table=ManagementTable('Probe',[('value','VALUE',150)],search_fields=('value',))
        try:
            table.set_rows([{'id':'b','value':2},{'id':'a','value':2},{'id':'c','value':1}])
            self.assertEqual([r['id'] for r in table.visible_rows],['c','a','b'])
            table.sort_by('value');self.assertEqual([r['id'] for r in table.visible_rows],['a','b','c'])
        finally:table.close()

    def test_details_identity_attributes_read_only_and_back(self):
        before=self.s.authoritative_bytes();self.app.open_aircraft_details(self.aircraft)
        page=self.app.content;self.assertEqual(page.aircraft_id,self.aircraft)
        values=dict(self.s.aircraft_details(self.aircraft)['attributes'])
        self.assertEqual(values['Passenger capacity'],194);self.assertEqual(values['Ownership'],'OWNED')
        self.assertEqual(values['Home base'],'MNL');self.assertEqual(values['Cargo'],'Not modeled')
        self.assertEqual(self.app._section,'Fleet');self.assertEqual(before,self.s.authoritative_bytes())
        self.app.show_view('Fleet');self.assertTrue(page.closed)
        with self.assertRaises(ValueError):self.s.aircraft_details('not-an-id')

    def test_details_week_and_local_times_exclude_pattern_only(self):
        self.service();self.app.open_aircraft_details(self.aircraft)
        rows=self.s.aircraft_details(self.aircraft)['schedule']
        self.assertEqual(len(rows),2);self.assertTrue(rows[0]['departure'].endswith('+08:00'))
        self.assertIn('T16:00:00',rows[0]['departure']);self.assertIn('T17:40:00',rows[0]['arrival'])
        self.assertEqual(self.s.aircraft_details(self.aircraft)['week_start'],'2026-08-31')
        second=self.s.purchase(self.s.preview_purchase('airbus-a320neo',self.ports['MNL']))
        self.assertEqual(self.s.aircraft_details(second)['schedule'],[])

    def test_schedule_aircraft_handoff_no_publication(self):
        before=self.s.authoritative_bytes();self.app.open_aircraft_details(self.aircraft)
        self.app.schedule_handoff(self.aircraft)
        self.assertEqual(self.app.current_view,'Schedule');self.assertEqual(self.app._draft.aircraft_id,self.aircraft)
        self.assertEqual(self.app._draft.legs,[]);self.assertEqual(before,self.s.authoritative_bytes())

    def test_research_data_semantics_rounding_only(self):
        before=self.s.authoritative_bytes();self.app.show_view('Research');page=self.app.content
        raw=self.s.market_opportunities(origin_airport_id=self.ports['MNL'],limit=2000)
        source={r['market_id']:r for r in raw}
        for row in page.rows:
            r=source[row['id']]
            self.assertEqual(row['code'],r['destination_airport_reference_code'])
            self.assertEqual(row['name'],r['destination_airport_name']);self.assertEqual(row['distance'],r['distance_km'])
            self.assertIsInstance(row['bookers'],int);self.assertLessEqual(abs(row['bookers']-float(r['base_daily_directional_bookers'])),.5)
            self.assertEqual(row['available'],r['market_available']);self.assertEqual(row['seats'],r['player_published_capacity'])
            self.assertEqual(row['confirmed'],r['current_confirmed_bookings'])
        self.assertEqual(before,self.s.authoritative_bytes())

    def test_research_published_seats_fare_confirmed(self):
        self.service();self.s.advance_to('2026-09-02T00:00:00Z');self.app.show_view('Research')
        row=next(r for r in self.app.content.rows if r['code']=='DVO')
        raw=next(r for r in self.s.market_opportunities(origin_airport_id=self.ports['MNL']) if r['destination_airport_reference_code']=='DVO')
        self.assertEqual(row['seats'],194);self.assertEqual(row['fare'],11600)
        self.assertEqual(row['confirmed'],raw['current_confirmed_bookings'])

    def test_research_search_sort_and_airport_search_preserved(self):
        before=self.s.authoritative_bytes();self.app.show_view('Research');page=self.app.content
        page.search.text='francisco bangoy';self.assertEqual([r['code'] for r in page.visible_rows],['DVO'])
        self.assertEqual(page.destination.search('Davao')[0]['airport_id'],self.ports['DVO'])
        page.search.text='';page.sort_by('distance');ascending=[r['distance'] for r in page.visible_rows]
        self.assertEqual(ascending,sorted(ascending));page.sort_by('distance')
        self.assertEqual([r['distance'] for r in page.visible_rows],sorted(ascending,reverse=True))
        self.assertEqual(before,self.s.authoritative_bytes())

    def test_research_handoff_single_compatible(self):
        before=self.s.authoritative_bytes();self.app.show_view('Research')
        self.app.research_add_flight(self.ports['MNL'],self.ports['DVO'])
        self.assertEqual(self.app.current_view,'Schedule');self.assertEqual(self.app._builder_origin,self.ports['MNL'])
        self.assertEqual(self.app._builder_destination,self.ports['DVO']);self.assertEqual(self.app._draft.aircraft_id,self.aircraft)
        self.assertEqual(self.app._draft.legs,[]);self.assertEqual(before,self.s.authoritative_bytes())

    def test_compatibility_invokes_domain_range_boundary(self):
        from game.scheduling.route_compatibility import compatible_aircraft
        with patch('game.scheduling.eligibility.check_eligibility',side_effect=ValueError('AIRCRAFT_RANGE_EXCEEDED')) as check:
            self.assertEqual(compatible_aircraft(self.s.world,self.s.airline_id,self.ports['MNL'],self.ports['DVO']),())
            check.assert_called_once()
        self.assertEqual(self.s.compatible_aircraft(self.ports['MNL'],self.ports['DVO']),(self.aircraft,))

    def test_no_compatible_stays_research_and_multiple_choice(self):
        self.app.show_view('Research')
        with patch.object(self.s,'compatible_aircraft',return_value=()):self.app.research_add_flight(self.ports['MNL'],self.ports['DVO'])
        self.assertEqual(self.app.current_view,'Research');self.assertIn('No compatible',self.app._popup.title);self.app._dismiss()
        other=self.s.purchase(self.s.preview_purchase('airbus-a320neo',self.ports['MNL']))
        self.app.research_add_flight(self.ports['MNL'],self.ports['DVO'])
        self.assertEqual(self.app.current_view,'Research');self.assertIn('Choose compatible',self.app._popup.title)
        from kivy.uix.button import Button
        registration=self.s.scheduling_aircraft(other)['display_registration']
        next(w for w in self.app._popup.content.walk() if isinstance(w,Button) and registration in w.text).dispatch('on_release')
        self.assertEqual(self.app._draft.aircraft_id,other)

    def test_finite_scroll_resize_empty_refresh_and_long_frame(self):
        table=ManagementTable('Geometry',[('value','VALUE',1200)],search_fields=('value',))
        try:
            for size in ((1200,700),(380,500),(900,600)):
                table.size=size;table.do_layout();table.viewport.size=(size[0],max(52,size[1]-190))
                table.set_rows([{'id':str(i),'value':i} for i in range(30)])
                Clock.tick();table.viewport.scroll_x=.5;table.viewport.scroll_y=.4
                table.viewport.effect_y.velocity=200;table.viewport.effect_y.update_velocity(4)
                table.search.text='absent';Clock.tick();self.assertTrue(table.finite())
                table.search.text='';table.sort_by('value');Clock.tick();self.assertTrue(table.finite())
                self.assertEqual(table.header_scroll.scroll_x,table.viewport.scroll_x)
                table.set_rows([]);Clock.tick();self.assertTrue(table.finite())
            self.assertIsInstance(table.viewport.effect_y,ScrollEffect)
        finally:table.close()

    def test_navigation_stress_no_retained_pages_or_page_timers(self):
        refs=[];counts=[];ticker=self.app._ticker
        for _ in range(12):
            for view in ('Fleet','Research','Schedule','Acquire','Flights','Bookings','Finance','Saves','Overview'):
                self.app.show_view(view);Clock.tick()
                self.assertEqual(len(self.app.page_host.children),1)
                if view=='Fleet':
                    page=self.app.content;refs.append(weakref.ref(page))
                    self.app.open_aircraft_details(self.aircraft);Clock.tick();del page
            gc.collect();counts.append(len(list(self.app.screens.walk())))
        self.assertEqual(min(counts),max(counts));self.assertIs(self.app._ticker,ticker)
        self.assertLessEqual(sum(r() is not None for r in refs),1)

    def test_refresh_footer_does_not_accumulate_and_neutral_text_is_unicode(self):
        self.app.show_view('Research');page=self.app.content
        for _ in range(5):self.app.refresh(force=True)
        self.assertEqual(page.footer.text.count('Available ='),1)
        self.app.show_view('Fleet');page=self.app.content
        for _ in range(5):self.app.refresh(force=True)
        self.assertEqual(page.footer.text.count('Week'),1)
        self.assertEqual(page.cells[self.aircraft]['name'].text,'—')

    def test_inactive_not_refreshed_running_and_transient_not_saved(self):
        self.app.show_view('Fleet');page=self.app.content;page.search.text='Airbus'
        self.app.show_view('Research')
        with patch.object(page,'refresh_data',side_effect=AssertionError('inactive refresh')):
            self.s.resume('Fast');self.clock.advance(.01);self.app.tick(0)
        self.assertTrue(page.closed)
        encoded=self.s.authoritative_bytes().decode();self.assertNotIn('sort',json.loads(encoded).get('ui',{}))
        self.s.hard_pause();self.s.save_manual();expected=self.s.authoritative_bytes();self.s.load_saved(self.s.career_id)
        self.assertEqual(self.s.authoritative_bytes(),expected)
        self.assertNotIn('page_states',encoded);self.assertNotIn('Airbus',json.dumps(self.app._page_states.get('Research',{})))
