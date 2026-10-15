"""Stage 3F session/controller and native Kivy integration in temporary careers."""
import os
os.environ.setdefault('KIVY_NO_ARGS','1')
from copy import deepcopy
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from app.quarterly_planning import QuarterlyPlanningController
from tests import test_quarterly_backend as backend_tests
from game.utils.quarters import normal_target_quarter


class QuarterlyGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base,cls.pid,cls.sid,cls.owner,cls.aircraft,_=backend_tests.QuarterlyBackendTests.fixture(quarter='2027-Q2',published=False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.session=Stage1Session(save_root=self.temp.name,runtime_clock=lambda:0)
        self.session.world=deepcopy(self.base)
        self.session.career_id=self.session.save_store.new_career_id()
        self.session._ensure_runtime();self.session._bind_owned_reads()
        self.controller=QuarterlyPlanningController(self.session);self.controller.refresh()

    def tearDown(self):
        self.session.close();self.temp.cleanup()

    def selected(self,index=0):
        row=self.controller.page['rows'][index]
        self.controller.select_slot((row['service_id'],row['slot_number']))
        return row

    def slot(self, row=None, **changes):
        row=row or self.controller.page['rows'][0]
        result={k:deepcopy(row[k]) for k in ('planned_aircraft_id','origin_airport_id','destination_airport_id',
            'weekdays','departure_local_time','departure_local_fold','connection_id','service_type','capacity','fare_offer')}
        result.update(changes);return result

    def publish(self):
        result=self.controller.prepare_publication();self.assertTrue(result.succeeded,result.issues)
        result=self.controller.confirm_publication();self.assertTrue(result.succeeded,result.issues)
        return result

    def test_default_new_game_remains_legacy(self):
        self.session.new_game('CEO','Legacy','MNL')
        self.assertFalse(self.session.quarterly_career)
        self.assertNotIn('operational_authority',self.session.world['simulation'])

    def test_development_new_game_is_explicit_and_empty(self):
        self.session.new_quarterly_development_game('CEO','Development','MNL')
        self.assertTrue(self.session.quarterly_career)
        state=self.session.world['world_state']
        for name in ('weekly_plans','services','dated_flights','bookings','schedule_definitions'):
            self.assertFalse(state[name],name)
        self.assertFalse(state['connections'])
        self.assertEqual(self.session.world['simulation']['clock_state'],'PAUSED')
        self.assertFalse(any(e['event_type'] in ('QUARTERLY_DISPATCH','STAGE1_WEEKLY_PUBLICATION') for e in state['pending_events'].values()))

    def test_literal_planning_status(self):
        page=self.controller.page
        self.assertEqual((page['operating_quarter'],page['target_quarter'],page['deadline_utc']),
            ('2027-Q1','2027-Q2','2027-03-01T00:00:00Z'))
        self.assertEqual(page['total'],2);self.assertTrue(page['editable'])

    def test_detached_cached_planning_read_avoids_validation(self):
        before=self.session.authoritative_bytes()
        with patch('app.session.validate_world',side_effect=AssertionError('no ordinary render validation')):
            page=self.session.quarterly_planning_page();page['rows'][0]['weekdays'].clear()
            self.assertTrue(self.session.quarterly_planning_page()['rows'][0]['weekdays'])
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_new_service_uses_certified_commands_and_no_events(self):
        before=deepcopy(self.session.world['world_state']['pending_events'])
        result=self.controller.create(self.slot(weekdays=[0],departure_local_time='18:00:00'),'DAB')
        self.assertTrue(result.succeeded,result.issues);self.assertNotEqual(result.service_id,self.sid)
        self.assertEqual(before,self.session.world['world_state']['pending_events'])
        self.assertFalse(self.session.world['world_state']['dated_flights'])

    def test_fare_revision_retains_identity(self):
        row=self.selected();result=self.controller.fare(12345)
        self.assertTrue(result.succeeded,result.issues)
        changed=next(r for r in self.controller.page['rows'] if r['service_id']==row['service_id'])
        self.assertEqual(changed['fare_offer']['amount_minor'],12345)
        self.assertEqual(changed['flight_number'],row['flight_number'])

    def test_schedule_revision_retains_identity(self):
        row=self.selected();result=self.controller.edit({'departure_local_time':'10:00:00','weekdays':[0,2,4]})
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(self.controller.page['rows'][0]['service_id'],row['service_id'])

    def test_aircraft_change_rejected_without_owner(self):
        self.selected();before=self.session.authoritative_bytes()
        result=self.controller.edit({'planned_aircraft_id':'aircraft-999999999999'})
        self.assertFalse(result.succeeded);self.assertEqual(before,self.session.authoritative_bytes())

    def test_add_frequency_preserves_service(self):
        row=self.selected();result=self.controller.add_frequency(self.slot(row,weekdays=[0],departure_local_time='18:00:00'))
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(result.service_id,row['service_id']);self.assertEqual(result.slot_number,2)

    def test_endpoint_change_is_not_an_edit(self):
        self.selected();before=self.session.authoritative_bytes()
        result=self.controller.edit({'destination_airport_id':self.controller.page['rows'][1]['destination_airport_id']})
        self.assertFalse(result.succeeded);self.assertEqual(result.issues[0].code,'ENDPOINT_REPLACEMENT_REQUIRED')
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_remove_then_retire_preserves_other_services(self):
        row=self.selected();result=self.controller.remove();self.assertTrue(result.succeeded,result.issues)
        self.assertIsNone(self.session.world['world_state']['services'][row['service_id']]['retired_at_utc'])
        result=self.controller.retire(row['service_id']);self.assertTrue(result.succeeded,result.issues)
        self.assertIsNotNone(self.session.world['world_state']['services'][row['service_id']]['retired_at_utc'])
        self.assertEqual(len(self.controller.page['rows']),1)

    def test_identity_safe_replacement(self):
        row=self.selected();back=self.controller.page['rows'][1]
        result=self.controller.replace(self.slot(row,origin_airport_id=back['origin_airport_id'],
            destination_airport_id=back['destination_airport_id'],connection_id=back['connection_id']),'DAB')
        self.assertTrue(result.succeeded,result.issues);self.assertNotEqual(result.service_id,row['service_id'])
        self.assertIn(row['service_id'],self.session.world['world_state']['services'])

    def test_readiness_is_informational(self):
        before=self.session.authoritative_bytes();result=self.controller.inspect()
        self.assertTrue(result.succeeded,result.issues);self.assertTrue(result.execution_ready)
        self.assertEqual(before,self.session.authoritative_bytes())
        refused=self.session.apply_quarterly_command(result)
        self.assertFalse(refused.succeeded)

    def test_missing_actual_positioning_is_explained(self):
        self.selected(1);self.assertTrue(self.controller.remove().succeeded)
        result=self.controller.inspect()
        self.assertTrue(result.planning_feasible);self.assertFalse(result.execution_ready)
        self.assertTrue(any(i.code=='UNRESOLVED_POSITIONING' for i in result.execution_blockers))

    def test_publication_confirmation_is_required(self):
        before=self.session.authoritative_bytes();result=self.controller.prepare_publication()
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(before,self.session.authoritative_bytes())
        self.assertIsNone(self.controller.page['published_at_utc'])

    def test_manual_success_moves_planning_without_clock(self):
        now=self.controller.page['time_utc'];result=self.publish()
        self.assertEqual(self.controller.page['target_quarter'],'2027-Q3')
        self.assertEqual(self.controller.page['time_utc'],now)
        self.assertEqual(self.controller.last_published,result.weekly_plan_id)
        self.assertFalse(self.session.world['world_state']['dated_flights'])

    def test_published_quarter_is_locked(self):
        result=self.publish();self.controller.select_plan(result.weekly_plan_id)
        self.assertFalse(self.controller.page['editable'])
        self.selected()
        with self.assertRaisesRegex(ValueError,'locked'):self.controller.fare(100)

    def test_failed_manual_publication_is_atomic(self):
        self.selected(1);self.assertTrue(self.controller.remove().succeeded)
        before=self.session.authoritative_bytes();result=self.controller.prepare_publication()
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(before,self.session.authoritative_bytes())
        result=self.controller.confirm_publication()
        self.assertFalse(result.succeeded);self.assertTrue(result.issues)
        self.assertIsNone(self.controller.confirmation)
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_stale_confirmation_revalidates(self):
        self.assertTrue(self.controller.prepare_publication().succeeded)
        prepared=self.controller.confirmation
        other=QuarterlyPlanningController(self.session);other.refresh();other.select_slot((self.sid,1));self.assertTrue(other.fare(9000).succeeded)
        result=self.controller.confirm_publication();self.assertFalse(result.succeeded)
        self.assertIsNotNone(prepared)

    def test_rebind_revokes_selection_readiness_and_confirmation(self):
        self.selected();self.controller.inspect();self.controller.prepare_publication()
        self.session.world=deepcopy(self.session.world)
        with self.assertRaisesRegex(ValueError,'expired'):self.controller.confirm_publication()
        self.controller.refresh()
        self.assertIsNone(self.controller.selected);self.assertIsNone(self.controller.readiness)

    def test_published_date_browsing_is_read_only(self):
        result=self.publish();before=self.session.authoritative_bytes()
        page=self.session.quarterly_published_day(result.weekly_plan_id,'2027-04-02')
        self.assertEqual(len(page['rows']),2)
        self.assertTrue(all(r['published_at_utc']=='2027-01-01T00:00:00Z' for r in page['rows']))
        self.assertTrue(all(r['passengers']==0 for r in page['rows']))
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_browsing_bounds_are_enforced(self):
        result=self.publish()
        for offset,limit in ((0,129),(-1,32),(True,32),(0,0)):
            with self.subTest(offset=offset,limit=limit),self.assertRaises(ValueError):
                self.session.quarterly_published_day(result.weekly_plan_id,'2027-04-02',offset=offset,limit=limit)

    def test_no_occurrences_for_unselected_weekday(self):
        self.selected();self.assertTrue(self.controller.edit({'weekdays':[0]}).succeeded)
        self.selected(1);self.assertTrue(self.controller.edit({'weekdays':[0]}).succeeded)
        result=self.publish();page=self.session.quarterly_published_day(result.weekly_plan_id,'2027-04-02')
        self.assertEqual(len(page['rows']),0)

    def test_load_after_publication_reconstructs_context(self):
        result=self.publish();self.session.save_manual();career=self.session.career_id
        self.session.load_saved(career);self.controller.refresh()
        self.assertEqual(self.controller.page['target_quarter'],'2027-Q3')
        self.assertIsNone(self.controller.selected);self.assertIsNone(self.controller.confirmation)
        self.assertEqual(len(self.session.quarterly_published_day(result.weekly_plan_id,'2027-04-02')['rows']),2)

    def fence(self):
        world,pid,sid,owner,aircraft,_=backend_tests.QuarterlyBackendTests.fixture('2027-02-28T23:59:59Z','2027-Q2',published=False)
        self.session.world=world;self.session.runtime=None;self.session._ensure_runtime();self.session._bind_owned_reads()
        self.controller=QuarterlyPlanningController(self.session);self.controller.refresh()
        back=self.selected(1);self.assertTrue(self.controller.remove().succeeded)
        report=self.session.advance_to('2027-03-01T00:00:00Z')
        self.assertIsNotNone(report.result.failure)
        self.controller.refresh()
        return back

    def test_automatic_fence_exposes_correction_target(self):
        self.fence();page=self.controller.page
        self.assertEqual(page['target_quarter'],'2027-Q3')
        self.assertEqual(page['selected_quarter'],'2027-Q2');self.assertTrue(page['editable'])
        self.assertTrue(page['fence']['failure']);self.assertEqual(page['binding_clock'],'PAUSED')

    def test_unchanged_retry_preserves_fence(self):
        self.fence();before=self.session.authoritative_bytes()
        report=self.controller.retry();self.assertIsNotNone(report.result.failure)
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_fence_cannot_present_normal_running(self):
        self.fence();before=self.session.authoritative_bytes()
        with self.assertRaisesRegex(ValueError,'Publication is blocked'):self.session.resume()
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_missing_fenced_plan_does_not_inspect_wrong_quarter(self):
        world,pid,_,_,_,_=backend_tests.QuarterlyBackendTests.fixture('2027-02-28T23:59:59Z','2027-Q2',published=False)
        del world['world_state']['weekly_plans'][pid]
        self.session.world=world;self.session.runtime=None;self.session._ensure_runtime();self.session._bind_owned_reads()
        report=self.session.advance_to('2027-03-01T00:00:00Z');self.assertIsNotNone(report.result.failure)
        controller=QuarterlyPlanningController(self.session);page=controller.refresh()
        self.assertEqual(page['selected_quarter'],'2027-Q2');self.assertIsNone(page['plan_id'])
        with patch.object(self.session,'quarterly_publication_readiness',side_effect=AssertionError('wrong-quarter query')):
            with self.assertRaisesRegex(ValueError,'Initialize the fenced'):controller.inspect()

    def test_fence_disables_normal_future_plan_editing_in_gui(self):
        from game.world_state.quarterly_construction import create_weekly_plan
        world,pid,_,owner,_,_=backend_tests.QuarterlyBackendTests.fixture('2027-02-28T23:59:59Z','2027-Q2',published=False)
        next_pid=create_weekly_plan(world,owner,'2027-Q3',slots=[])
        self.session.world=world;self.session.runtime=None;self.session._ensure_runtime();self.session._bind_owned_reads()
        controller=QuarterlyPlanningController(self.session);controller.refresh()
        back=controller.page['rows'][1];controller.select_slot((back['service_id'],back['slot_number']))
        self.assertTrue(controller.remove().succeeded)
        self.session.advance_to('2027-03-01T00:00:00Z')
        page=controller.select_plan(next_pid);self.assertFalse(page['editable'])

    def test_correct_and_retry_existing_engine(self):
        back=self.fence()
        result=self.controller.create(self.slot(back),'DAB');self.assertTrue(result.succeeded,result.issues)
        report=self.controller.retry();self.assertIsNone(report.result.failure,report.result.failure)
        self.assertIsNone(self.controller.page['fence']['failure'])
        self.assertEqual(self.controller.page['target_quarter'],'2027-Q3')

    def test_fenced_load_restores_and_revokes_objects(self):
        self.fence();self.session.save_manual();self.session.load_saved(self.session.career_id)
        page=self.controller.refresh()
        self.assertTrue(page['fence']['failure']);self.assertEqual(page['selected_quarter'],'2027-Q2')
        self.assertIsNone(self.controller.readiness)

    def test_retry_without_failure_rejected(self):
        with self.assertRaisesRegex(ValueError,'no failed'):self.controller.retry()

    def test_backend_slot_input_owns_capacity_and_routes(self):
        row=self.controller.page['rows'][0]
        slot=self.session.quarterly_slot_input(aircraft_id=row['planned_aircraft_id'],
            origin_id=row['origin_airport_id'],destination_id=row['destination_airport_id'],
            weekdays=[0],departure_local_time='18:00:00',fare_minor=123)
        self.assertEqual(slot['capacity'],row['capacity']);self.assertEqual(slot['connection_id'],row['connection_id'])

    def test_continuation_after_early_commit_initializes_baseline(self):
        published=self.publish();source=dict(plan_id=published.weekly_plan_id,revision=published.revision)
        result=self.controller.continue_slot(source,self.controller.page['rows'][0])
        self.assertTrue(result.succeeded,result.issues);self.assertEqual(self.controller.page['total'],2)

    def test_finance_and_stored_operations_reads_are_detached(self):
        before=self.session.authoritative_bytes()
        finance=self.session.finances();finance['recent_results'].clear()
        self.session.operational_flights('2027-01-01');self.session.service_markets()
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_published_read_shows_sold_seats_and_finance_lineage(self):
        world,pid,_,_,_,_=backend_tests.QuarterlyBackendTests.fixture()
        self.session.world=world;self.session.runtime=None;self.session._ensure_runtime();self.session._bind_owned_reads()
        report=self.session.advance_to('2027-01-02T00:00:00Z');self.assertIsNone(report.result.failure)
        state=self.session.world['world_state']
        self.assertTrue(state['bookings']);self.assertTrue(state['flight_results'])
        sold=next(f for f in state['dated_flights'].values() if f['status']=='PLANNED')
        before=self.session.authoritative_bytes()
        rows=self.session.quarterly_published_day(pid,sold['quarterly_lineage']['operating_date'])['rows']
        self.assertTrue(any(r['passengers']>0 for r in rows))
        self.assertTrue(self.session.finances()['recent_transactions'])
        self.assertFalse(state['schedule_definitions'])
        self.assertFalse(any(e['event_type']=='STAGE1_WEEKLY_PUBLICATION' for e in state['pending_events'].values()))
        self.assertEqual(before,self.session.authoritative_bytes())

    def test_gui_and_controller_never_borrow_world(self):
        for filename in ('app/gui/quarterly_page.py','app/quarterly_planning.py'):
            tree=ast.parse(Path(filename).read_text(encoding='utf-8'))
            self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr in ('world','_world','world_state') for n in ast.walk(tree)),filename)

    def test_ordinary_save_cannot_be_converted_on_load(self):
        self.session.new_game('CEO','Legacy','MNL');self.session.save_manual()
        self.session.load_saved(self.session.career_id)
        self.assertFalse(self.session.quarterly_career)
        with self.assertRaises(ValueError):self.session.quarterly_planning_page()


class QuarterlyKivyTests(unittest.TestCase):
    def setUp(self):
        from app.gui.app import AirlineTycoonApp
        self.temp=tempfile.TemporaryDirectory()
        self.app=AirlineTycoonApp(quarterly_development=True,session_factory=lambda:Stage1Session(save_root=self.temp.name,runtime_clock=lambda:0))
        self.app.build()
    def tearDown(self):
        self.app._dismiss();self.app.on_stop();self.temp.cleanup()

    def test_development_button_and_default_button_are_separate(self):
        from kivy.uix.button import Button
        texts=[w.text for w in self.app.screens.get_screen('title').walk() if isinstance(w,Button)]
        self.assertIn('New Game',texts);self.assertIn('New quarterly development career',texts)
        self.app.create_new_game('CEO','Legacy','MNL');self.assertFalse(self.app.session.quarterly_career)

    def test_native_quarterly_screen_and_navigation(self):
        from app.gui.quarterly_page import QuarterlyPage
        self.app.create_quarterly_development_game('CEO','Quarterly','MNL')
        self.assertIsInstance(self.app._active_page,QuarterlyPage)
        self.assertIn('isolated development',self.app._active_page.heading.text)
        self.app.show_view('Fleet');self.app.show_view('Schedule')
        self.assertIsInstance(self.app._active_page,QuarterlyPage)
        self.app._active_page.run(lambda:self.app._active_page.service_form('create'))
        self.assertIsNotNone(self.app._active_page._form_popup)

    def test_native_form_saves_only_planning_and_rebind_closes_form(self):
        from kivy.uix.button import Button
        self.app.create_quarterly_development_game('CEO','Quarterly','MNL')
        ports={p['reference_code']:p['airport_id'] for p in self.app.session.airports()}
        self.app.session.apply_route(self.app.session.quote_route(ports['MNL'],ports['MNL'],ports['CEB']))
        page=self.app._active_page;page._service_form('create')
        page._selectors[1].select(ports['CEB'])
        next(w for w in page._form_popup.content.walk() if isinstance(w,Button)
             and w.text=='Save planning edit').dispatch('on_release')
        self.assertEqual(page.controller.page['total'],1)
        self.assertFalse(self.app.session.world['world_state']['dated_flights'])
        page._service_form('create');self.assertIsNotNone(page._form_popup)
        self.app.session.world=deepcopy(self.app.session.world);page.refresh_data()
        self.assertIsNone(page._form_popup);self.assertIsNone(page.controller.selected)

    def test_entry_unavailable_without_flag(self):
        self.app.quarterly_development=False
        with self.assertRaises(ValueError):self.app.create_quarterly_development_game('CEO','Hidden','MNL')

    def test_native_service_viewport_survives_small_window(self):
        from kivy.core.window import Window
        from kivy.base import EventLoop
        self.app.create_quarterly_development_game('CEO','Quarterly','MNL')
        root=self.app.screens;previous_size=Window.size
        try:
            Window.size=(1000,720);Window.add_widget(root);root.transition.stop()
            for _ in range(12):EventLoop.idle()
            self.assertGreaterEqual(self.app._active_page.scroll.height,96)
            self.assertEqual(len(self.app._active_page.controls),12)
        finally:
            Window.remove_widget(root);Window.size=previous_size

    def test_native_publication_confirmation_wiring(self):
        world,pid,_,_,_,_=backend_tests.QuarterlyBackendTests.fixture(quarter='2027-Q2',published=False)
        self.app.session.world=world;self.app.session._ensure_runtime();self.app.session._bind_owned_reads()
        self.app._enter_game();self.app.show_view('Schedule')
        page=self.app._active_page;before=self.app.session.authoritative_bytes();page._review_publication()
        self.assertIsNotNone(self.app._popup);self.assertEqual(before,self.app.session.authoritative_bytes())
        from kivy.uix.button import Button
        next(w for w in self.app._popup.content.walk() if isinstance(w,Button) and w.text=='Publish schedule').dispatch('on_release')
        self.assertEqual(self.app.quarterly_controller.page['target_quarter'],'2027-Q3')

    def test_native_blocked_confirmation_keeps_warning_and_all_diagnostics(self):
        from app.gui.scrolling import AxisScrollView
        world,pid,_,_,_,_=backend_tests.QuarterlyBackendTests.fixture(quarter='2027-Q2',published=False)
        self.app.session.world=world;self.app.session._ensure_runtime();self.app.session._bind_owned_reads()
        self.app._enter_game();self.app.show_view('Schedule')
        controller=self.app.quarterly_controller;row=controller.page['rows'][1]
        controller.select_slot((row['service_id'],row['slot_number']));self.assertTrue(controller.remove().succeeded)
        self.app._active_page._review_publication()
        scroll=next(w for w in self.app._popup.content.walk() if isinstance(w,AxisScrollView))
        text=scroll._viewport.text
        self.assertIn('permanently locks ordinary edits',text)
        self.assertLess(text.index('permanently locks ordinary edits'),text.index('UNRESOLVED_POSITIONING'))
        self.assertEqual(text.count('UNRESOLVED_POSITIONING'),len(controller.readiness.execution_blockers))
