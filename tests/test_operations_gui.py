"""Patch 3 occurrence/history, directional load and stable active-page regressions."""
import gc
import os
os.environ.setdefault('KIVY_NO_ARGS','1');os.environ.setdefault('KIVY_NO_FILELOG','1')
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, timedelta
from kivy.clock import Clock
from app.gui.app import AirlineTycoonApp
from app.gui.operations_pages import booking_matrix
from app.session import Stage1Session
from tests.test_gui_foundation import FakeClock


class OperationsGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.clock=FakeClock()
        self.app=AirlineTycoonApp(session_factory=lambda:Stage1Session(save_root=self.temp.name,runtime_clock=self.clock))
        self.app.build();self.app.create_new_game('CEO','Operations Air','MNL');self.s=self.app.session
        self.ports={r['reference_code']:r['airport_id'] for r in self.s.airports()}
        self.aircraft=self.s.fleet()[0]['aircraft_id']
    def tearDown(self):self.app._dismiss();self.app.on_stop();self.temp.cleanup()
    def service(self,aircraft=None):
        draft=self.s.begin_scheduling(aircraft or self.aircraft)
        for day in (2,3,7):
            draft.add(self.ports['MNL'],self.ports['DVO'],departure_utc=f'2026-09-{day:02d}T08:00:00Z',fare_minor=11600)
            draft.add_return(fare_minor=11600)
        self.s.save_scheduling(draft);return draft
    def page(self,view):self.app.show_view(view);return self.app.content

    def test_day_controls_use_game_clock_and_retain_light_state(self):
        page=self.page('Flights');self.assertEqual(page.state['day'],'2026-09-01')
        page.shift(-1);self.assertEqual(page.state['day'],'2026-08-31')
        page.shift(2);self.assertEqual(page.state['day'],'2026-09-02')
        page.search.text='MNL';page.viewport.scroll_x=.3
        self.page('Fleet');new=self.page('Flights')
        self.assertEqual(new.state['day'],'2026-09-02');self.assertEqual(new.search.text,'MNL')
        self.assertEqual(new.viewport.scroll_x,.3);new.today();self.assertEqual(new.state['day'],'2026-09-01')

    def test_pattern_only_is_absent_and_future_is_published_only(self):
        draft=self.s.begin_scheduling(self.aircraft)
        draft.add(self.ports['MNL'],self.ports['DVO'],departure_utc='2026-09-02T08:00:00Z',fare_minor=11600)
        self.assertEqual(self.s.operational_flights('2026-09-02'),[])
        self.s.save_scheduling(draft)
        rows=self.s.operational_flights('2026-09-02');self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'PLANNED');self.assertEqual(rows[0]['load_basis'],'CONFIRMED')
        self.assertEqual(self.s.operational_flights('2026-09-09'),[])

    def test_local_grouping_and_chronological_order_readonly(self):
        self.service();before=self.s.authoritative_bytes()
        rows=self.s.operational_flights('2026-09-02')
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['departure_local'],'2026-09-02T16:00:00+08:00')
        self.assertEqual(rows[0]['arrival_local'],'2026-09-02T17:40:00+08:00')
        self.assertEqual([r['departure'] for r in rows],sorted(r['departure'] for r in rows))
        self.assertEqual(before,self.s.authoritative_bytes())
        # PH midnight belongs to the next operational date despite its UTC date.
        draft=self.s.begin_scheduling(self.aircraft)
        draft.add(self.ports['MNL'],self.ports['CEB'],departure_utc='2026-09-04T16:00:00Z',fare_minor=6800)
        draft.add_return(fare_minor=6800)
        self.s.save_scheduling(draft)
        self.assertEqual(self.s.operational_flights('2026-09-04'),[])
        self.assertEqual(self.s.operational_flights('2026-09-05')[0]['departure_local'],'2026-09-05T00:00:00+08:00')

    def test_completed_active_and_upcoming_refresh_is_stable(self):
        self.service();page=self.page('Flights');page.day_picker.select('2026-09-02')
        controls=page.controls;viewport=page.viewport;page.search.text='MNL';page.viewport.scroll_x=.4
        self.s.advance_to('2026-09-02T08:10:00Z');self.app.refresh(force=True)
        self.assertIs(page,self.app.content);self.assertIs(page.controls,controls);self.assertIs(page.viewport,viewport)
        self.assertEqual([r['status'] for r in page.rows],['OPERATIONALLY_LOCKED','PLANNED'])
        self.assertEqual(page.rows[0]['load_basis'],'LOCKED')
        self.s.advance_to('2026-09-02T12:00:00Z');self.app.refresh(force=True)
        self.assertTrue(all(r['status']=='COMPLETED' for r in page.rows))
        world=self.s.world['world_state']
        for r in page.rows:
            self.assertEqual(r['passengers'],world['flight_results'][r['id']]['carried_passenger_count'])
            self.assertEqual(r['revenue'],world['flight_results'][r['id']]['recognized_revenue_minor'])
        self.assertEqual(page.state['day'],'2026-09-02');self.assertEqual(page.search.text,'MNL')
        bookings=self.page('Bookings');bookings.market_selector.text='MNL -> DVO'
        past=[r for day in bookings.rows for r in day['occurrences'].values() if r['operational_date']=='2026-09-02']
        self.assertTrue(past);self.assertTrue(all(r['load_basis']=='CARRIED' for r in past))
        page=self.page('Flights')
        page.day_picker.select('2026-09-01');self.assertEqual(page.rows,[])
        page.day_picker.select('2026-09-03');self.assertTrue(all(r['status']=='PLANNED' for r in page.rows))

    def test_overnight_airborne_and_completed_visible_without_duplicate_booking_day(self):
        draft=self.s.begin_scheduling(self.aircraft)
        draft.add(self.ports['MNL'],self.ports['DVO'],departure_utc='2026-09-01T15:00:00Z',fare_minor=11600)
        draft.add_return(fare_minor=11600);self.s.save_scheduling(draft)
        self.s.advance_to('2026-09-01T16:10:00Z')
        page=self.page('Flights');self.assertEqual(page.state['day'],'2026-09-02')
        overnight=next(r for r in page.rows if r['origin']=='MNL')
        self.assertEqual(overnight['operational_date'],'2026-09-01')
        self.assertEqual(overnight['status'],'OPERATIONALLY_LOCKED')
        identity=overnight['id']
        self.s.advance_to('2026-09-01T16:50:00Z');self.app.refresh(force=True)
        self.assertEqual(next(r for r in page.rows if r['id']==identity)['status'],'COMPLETED')
        bookings=self.page('Bookings');bookings.market_selector.text='MNL -> DVO'
        occupied=[(r['id'],item['id']) for r in bookings.rows for item in r['occurrences'].values()]
        self.assertEqual(occupied,[('2026-09-01',identity)])

    def test_search_filters_sort_and_detached_rows(self):
        self.service();before=self.s.authoritative_bytes();page=self.page('Flights');page.day_picker.select('2026-09-02')
        page.search.text='RP-C0001';self.assertEqual(len(page.visible_rows),2)
        page.filter_widgets['origin'][0].text='MNL';self.assertEqual(len(page.visible_rows),1)
        page.reset();page.sort_by('departure');self.assertGreater(page.visible_rows[0]['departure'],page.visible_rows[1]['departure'])
        rows=self.s.operational_flights('2026-09-02');rows[0]['status']='MUTATED UI'
        self.assertNotEqual(self.s.operational_flights('2026-09-02')[0]['status'],'MUTATED UI')
        self.assertEqual(before,self.s.authoritative_bytes())

    def test_directional_market_and_week_controls(self):
        self.service();page=self.page('Bookings');self.assertEqual(page.state['week'],'2026-08-31')
        page.market_selector.text='MNL -> DVO';self.assertEqual(page.state['market'],[self.ports['MNL'],self.ports['DVO']])
        outbound=[i for r in page.rows for i in r['occurrences'].values()]
        page.market_selector.text='DVO -> MNL'
        inbound=[i for r in page.rows for i in r['occurrences'].values()]
        self.assertFalse({r['id'] for r in outbound}&{r['id'] for r in inbound})
        page.shift(1);self.assertEqual(page.state['week'],'2026-09-07');page.shift(-2)
        self.assertEqual(page.state['week'],'2026-08-24');page.current();self.assertEqual(page.state['week'],'2026-08-31')
        self.page('Research');new=self.page('Bookings');self.assertEqual(new.state['market'],page.state['market'])

    def test_matrix_seven_days_confirmed_capacity_and_percentage(self):
        self.service();self.s.advance_to('2026-09-02T00:00:00Z')
        before=self.s.authoritative_bytes();page=self.page('Bookings');page.market_selector.text='MNL -> DVO'
        self.assertEqual([r['id'] for r in page.rows],[(date(2026,8,31)+timedelta(days=n)).isoformat() for n in range(7)])
        self.assertFalse(page.rows[0]['occurrences']);self.assertFalse(page.rows[1]['occurrences'])
        row=page.rows[2];item=next(iter(row['occurrences'].values()))
        from game.booking.indexes import rebuild_booking_indexes
        expected=rebuild_booking_indexes(self.s.world).booked_passenger_count_by_dated_flight_id.get(item['id'],0)
        self.assertEqual(item['passengers'],expected);self.assertEqual(item['capacity'],194)
        self.assertEqual(item['load'],expected*10000//194)
        self.assertEqual(before,self.s.authoritative_bytes())
        for b in page.header_buttons.values():b.dispatch('on_release')
        self.assertEqual(page.rows[0]['id'],'2026-08-31')

    def test_zero_capacity_and_same_time_occurrences_are_not_combined(self):
        self.service();rows=self.s.operational_flights('2026-09-02',market=(self.ports['MNL'],self.ports['DVO']))
        sample=rows[0];second=dict(sample,id='another-exact-flight',capacity=0,passengers=0,load=None)
        cols,matrix=booking_matrix('2026-08-31',[sample,second])
        self.assertEqual(len(cols),3);self.assertIn('#1',cols[1][1]);self.assertIn('#2',cols[2][1])
        occurrences=matrix[2]['occurrences'];self.assertEqual(len(occurrences),2)
        self.assertEqual({r['id'] for r in occurrences.values()},{sample['id'],second['id']})
        self.assertIn('—',matrix[2][next(k for k,v in occurrences.items() if v['id']==second['id'])+'_text'])

    def test_empty_populated_refresh_resize_scroll_and_disposal(self):
        page=self.page('Bookings');controls=page.controls;viewport=page.viewport
        self.assertEqual(len(page.rows),7);self.assertTrue(page.body.children)
        self.service();self.app.refresh(force=True)
        page.market_selector.text='MNL -> DVO'
        page.viewport.scroll_x=.3;page.viewport.scroll_y=.4
        self.assertEqual(page.pinned_scroll.scroll_y,.4)
        self.assertEqual(page.pinned_scroll.scroll_x,0)
        for n in range(12):
            page.size=(340+n*20,480);Clock.tick();self.app.refresh(force=True)
            page.viewport.effect_y.velocity=200;page.viewport.effect_y.update_velocity(4)
            self.assertTrue(page.finite());self.assertTrue(page.body.children)
            self.assertIs(page.controls,controls);self.assertIs(page.viewport,viewport)
            self.assertEqual(page.pinned_scroll.scroll_y,page.viewport.scroll_y)
            self.assertEqual(page.pinned_body.height,page.body.height)
            self.assertEqual(len(page.pinned_body.children),7)
        page.search.text='missing';self.assertFalse(page.visible_rows);page.reset();self.assertEqual(len(page.rows),7)
        self.page('Flights');self.assertTrue(page.closed)
        self.assertEqual(page.viewport.effect_y.velocity,0)

    def test_running_bookings_changes_values_without_rebuilding_or_reset(self):
        self.service();page=self.page('Bookings');page.market_selector.text='MNL -> DVO'
        page.viewport.scroll_x=.4;page.search.text='2026-09-02';controls=page.controls
        cells=dict(page.cells['2026-09-02']);selected=list(page.state['market'])
        self.s.advance_to('2026-09-02T00:00:00Z');self.s.resume('Fast');self.app.refresh(force=True)
        self.assertIs(page.controls,controls);self.assertEqual(page.cells['2026-09-02'],cells)
        self.assertEqual(page.state['market'],selected);self.assertEqual(page.state['week'],'2026-08-31')
        self.assertEqual(page.search.text,'2026-09-02');self.assertEqual(page.viewport.scroll_x,.4)
        self.assertTrue(page.finite());self.assertTrue(page.body.children)
        self.page('Fleet')
        with patch.object(page,'refresh_data',side_effect=AssertionError('inactive refresh')):self.app.refresh(force=True)

    def test_navigation_stress_single_host_and_exact_save(self):
        # The outgoing title screen is temporarily mounted during startup.
        # Measure management navigation after that normal animation settles.
        self.app.screens.transition.stop()
        self.service();before=self.s.authoritative_bytes();counts=[]
        for _ in range(8):
            for view in ('Flights','Bookings','Schedule','Fleet','Research','Flights','Bookings','Overview'):
                self.page(view);Clock.tick();self.assertEqual(len(self.app.page_host.children),1)
            gc.collect();counts.append(len(list(self.app.screens.walk())))
        self.assertEqual(len(set(counts)),1,counts);self.assertEqual(before,self.s.authoritative_bytes())
        self.s.save_manual();self.s.load_saved(self.s.career_id)
        self.assertEqual(before,self.s.authoritative_bytes());self.assertEqual(self.s.world['metadata']['save_schema_version'],8)
        self.assertFalse(self.s.runtime.running)

if __name__=='__main__':unittest.main()
