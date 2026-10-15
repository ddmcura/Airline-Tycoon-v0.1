"""Paid route certification in detached/new temporary careers, never real Saves."""
import os
os.environ.setdefault('KIVY_NO_ARGS','1')
from copy import deepcopy
from dataclasses import replace
import json
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.world_state.stage1_scenario import create_stage1_new_game, STAGE1_SCENARIO_ID
from game.scheduling.quarterly_backend import enable_quarterly_backend_for_testing
from game.route_management.establishment import quote_route, apply_route
from game.economy.route_establishment import route_fee_minor
from game.world_state.validation import validate_world


def encoded(world):
    return json.dumps({k:v for k,v in world.items() if k!='ui_state'},sort_keys=True)


class RouteEstablishmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = create_stage1_new_game(scenario_id=STAGE1_SCENARIO_ID,
            ceo_display_name='CEO',airline_display_name='Routes',base_airport_reference_code='MNL')
        enable_quarterly_backend_for_testing(cls.base)

    def setUp(self):
        self.world=deepcopy(self.base)
        self.state=self.world['world_state'];self.owner=self.state['player']['primary_airline_id']
        self.ports={v['reference_code']:k for k,v in self.state['airports'].items()}
        self.hub=self.ports['MNL']

    def quote(self,destination='CEB',**kw):
        return quote_route(self.world,airline_id=self.owner,hub_airport_id=self.hub,
            origin_airport_id=self.hub,destination_airport_id=self.ports[destination],**kw)

    def buy(self,destination='CEB'):
        quote=self.quote(destination);return apply_route(self.world,quote)

    def test_domestic_fee(self):
        self.assertEqual(route_fee_minor(1_000_000,True,0),3_000_000)

    def test_international_fee(self):
        self.assertEqual(route_fee_minor(1_000_000,False,0),9_000_000)

    def test_distance_factor(self):
        self.assertEqual(route_fee_minor(5_000_000,True,0),5_000_000)

    def test_growth_no_cap(self):
        self.assertEqual(route_fee_minor(0,True,1000),52_500_000)

    def test_half_up_cent(self):
        self.assertEqual(route_fee_minor(1,True,0),2_500_001)

    def test_owned_hub_attribution_is_isolated(self):
        self.state['airlines'][self.owner]['base_airport_ids'].append(self.ports['CEB'])
        self.state['airlines'][self.owner]['hub_airport_ids'].append(self.ports['CEB'])
        self.buy()
        q=quote_route(self.world,airline_id=self.owner,hub_airport_id=self.ports['CEB'],
            origin_airport_id=self.ports['CEB'],destination_airport_id=self.ports['DVO'])
        self.assertEqual(q.active_pair_count,0)
        apply_route(self.world,q)
        self.assertEqual(self.quote('DVO').active_pair_count,1)

    def test_invalid_fee_inputs(self):
        for args in ((True,True,0),(1,1,0),(1,True,True),(-1,True,0),(1,True,-1)):
            with self.assertRaises(ValueError):route_fee_minor(*args)

    def test_quote_has_no_effect(self):
        before=encoded(self.world);q=self.quote()
        self.assertGreater(q.distance_m,0);self.assertTrue(q.domestic)
        self.assertEqual(encoded(self.world),before)

    def test_quote_payment_and_load_validation_ignore_decimal_context(self):
        from decimal import localcontext
        expected=self.quote()
        with localcontext() as context:
            context.prec=4
            actual=self.quote()
            self.assertEqual(actual,expected)
            apply_route(self.world,actual)
            self.assertTrue(validate_world(self.world).is_valid)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_one_payment_two_directions_no_supply(self):
        q=self.quote();cid=apply_route(self.world,q);state=self.world['world_state']
        self.assertEqual(len(state['connections']),2)
        self.assertTrue(all(c['status']=='ACTIVE' for c in state['connections'].values()))
        t=next(iter(state['transactions'].values()))
        self.assertEqual(t['source_id'],cid);self.assertEqual(t['amount_minor'],q.amount_minor)
        for key in ('services','weekly_plans','dated_flights','bookings','flight_results'):
            self.assertFalse(state[key],key)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_duplicate_reverse_purchase_no_charge(self):
        self.buy();before=encoded(self.world)
        with self.assertRaisesRegex(ValueError,'already active'):
            quote_route(self.world,airline_id=self.owner,hub_airport_id=self.hub,
                origin_airport_id=self.ports['CEB'],destination_airport_id=self.hub)
        self.assertEqual(before,encoded(self.world))

    def test_same_command_is_idempotent(self):
        q=self.quote();cid=apply_route(self.world,q);before=encoded(self.world)
        self.assertEqual(apply_route(self.world,q),cid);self.assertEqual(before,encoded(self.world))

    def test_command_identifier_reuse_rejects_alteration(self):
        q=self.quote();apply_route(self.world,q);before=encoded(self.world)
        with self.assertRaisesRegex(ValueError,'already used'):apply_route(self.world,replace(q,amount_minor=q.amount_minor+1))
        self.assertEqual(before,encoded(self.world))

    def test_insufficient_cash_atomic(self):
        self.world['world_state']['financial_accounts'][next(k for k,a in self.state['financial_accounts'].items() if a['code']=='cash')]['balance_minor']=0
        q=self.quote();before=encoded(self.world)
        with self.assertRaisesRegex(ValueError,'insufficient'):apply_route(self.world,q)
        self.assertEqual(before,encoded(self.world))

    def test_invalid_hub(self):
        with self.assertRaisesRegex(ValueError,'owned'):
            quote_route(self.world,airline_id=self.owner,hub_airport_id=self.ports['CEB'],
                origin_airport_id=self.hub,destination_airport_id=self.ports['CEB'])

    def test_prohibited_same_airport(self):
        with self.assertRaisesRegex(ValueError,'distinct'):self.quote('MNL')

    def test_missing_reverse_market(self):
        # A valid incomplete market universe cannot grant the missing direction.
        state=self.world['world_state']
        key=next(k for k,m in state['directional_markets'].items() if m['origin_airport_id']==self.ports['CEB'] and m['destination_airport_id']==self.hub)
        del state['directional_markets'][key]
        before=encoded(self.world)
        with self.assertRaises(ValueError):self.quote()
        self.assertEqual(before,encoded(self.world))

    def test_source_stale_no_charge(self):
        q=self.quote();self.buy('DVO');before=encoded(self.world)
        with self.assertRaisesRegex(ValueError,'stale'):apply_route(self.world,q)
        self.assertEqual(before,encoded(self.world))

    def test_altered_quote_is_rejected(self):
        q=self.quote();before=encoded(self.world)
        with self.assertRaisesRegex(ValueError,'altered'):apply_route(self.world,replace(q,amount_minor=q.amount_minor-1))
        self.assertEqual(before,encoded(self.world))

    def test_post_staging_source_change_rejected(self):
        from game.route_management import establishment
        q=self.quote();original=establishment.validate;calls=[]
        def mutate_after_gate(candidate):
            original(candidate);calls.append(candidate)
            if len(calls)==4:self.world['metadata']['game_version']='concurrent-edit'
        with patch.object(establishment,'validate',side_effect=mutate_after_gate):
            with self.assertRaisesRegex(ValueError,'source changed'):apply_route(self.world,q)
        self.assertFalse(self.world['world_state']['transactions'])
        self.assertFalse(self.world['world_state']['connections'])

    def test_currency_conversion_cannot_pay(self):
        # This isolated eligibility probe proves no FX/payment fallback exists.
        self.state['airlines'][self.owner]['base_currency']='PHP'
        with patch('game.route_management.establishment.validate'):
            with self.assertRaisesRegex(ValueError,'USD'):self.quote()

    def test_foreign_access_cannot_be_inferred(self):
        self.state['airports'][self.ports['CEB']]['country_id']='foreign-country'
        with patch('game.route_management.establishment.validate'):
            with self.assertRaisesRegex(ValueError,'country access'):self.quote()

    def test_late_failure_rolls_back_everything(self):
        q=self.quote();before=encoded(self.world)
        with patch('game.route_management.establishment.record_route_payment',side_effect=ValueError('injected')):
            with self.assertRaisesRegex(ValueError,'injected'):apply_route(self.world,q)
        self.assertEqual(before,encoded(self.world))
        apply_route(self.world,q);self.assertEqual(len(self.world['world_state']['transactions']),1)

    def test_detached_validation_failure_atomic(self):
        from game.route_management import establishment
        q=self.quote();before=encoded(self.world);original=establishment.validate;calls=[]
        def reject_last(world):
            calls.append(world)
            if len(calls)==4:raise ValueError('detached failure')
            return original(world)
        with patch.object(establishment,'validate',side_effect=reject_last):
            with self.assertRaisesRegex(ValueError,'detached failure'):apply_route(self.world,q)
        self.assertEqual(before,encoded(self.world))

    def test_closure_and_reopening_keep_ids_and_pay_again(self):
        cid=self.buy();ids=set(self.world['world_state']['connections'])
        apply_route(self.world,self.quote(action='CLOSE'))
        self.assertTrue(all(c['status']=='CLOSED' for c in self.world['world_state']['connections'].values()))
        q=self.quote();self.assertEqual(q.active_pair_count,0)
        self.assertEqual(apply_route(self.world,q),cid)
        self.assertEqual(set(self.world['world_state']['connections']),ids)
        self.assertEqual(len(self.world['world_state']['transactions']),2)
        self.assertTrue(validate_world(self.world).is_valid)

    def test_count_once_per_pair_and_closure_reduces_count(self):
        self.buy();self.assertEqual(self.quote('DVO').active_pair_count,1)
        apply_route(self.world,self.quote(action='CLOSE'))
        self.assertEqual(self.quote('DVO').active_pair_count,0)

    def test_free_closure_allowed_with_negative_cash(self):
        self.buy()
        cash=next(a for a in self.world['world_state']['financial_accounts'].values() if a['code']=='cash')
        cash['balance_minor']=-1
        apply_route(self.world,self.quote(action='CLOSE'))
        cash=next(a for a in self.world['world_state']['financial_accounts'].values() if a['code']=='cash')
        self.assertEqual(cash['balance_minor'],-1)
        self.assertEqual(len(self.world['world_state']['transactions']),1)
        self.assertTrue(all(c['status']=='CLOSED' for c in self.world['world_state']['connections'].values()))

    def test_closure_operational_dependency_is_owned_not_market_wide(self):
        self.buy();mid=self.quote('DVO').market_ids[0]
        # Test the closure predicate independently of flight construction/validation.
        ceb_mid=next(c['market_id'] for c in self.world['world_state']['connections'].values())
        row={'airline_id':'another-airline','market_id':ceb_mid,'status':'LOCKED'}
        self.world['world_state']['dated_flights']['predicate-probe']=row
        with patch('game.route_management.establishment.validate'):
            self.quote(action='CLOSE')
            row['airline_id']=self.owner
            with self.assertRaisesRegex(ValueError,'operational'):self.quote(action='CLOSE')

    def test_second_pair_surcharge(self):
        q=self.quote('DVO');self.buy();new=self.quote('DVO')
        self.assertEqual(new.amount_minor,route_fee_minor(new.distance_m,True,1))
        self.assertGreater(new.amount_minor,q.amount_minor)

    def test_receipt_alias_and_status_corruption_reject(self):
        cid=self.buy()
        for mutate in (lambda w:w['connections'][cid]['route_establishment']['payment_transaction_ids'].append('missing'),
                       lambda w:w['connections'][cid].update(status='CLOSED'),
                       lambda w:next(iter(w['transactions'].values())).update(amount_minor=1)):
            changed=deepcopy(self.world);mutate(changed['world_state'])
            self.assertFalse(validate_world(changed).is_valid)

    def test_usd_receipt_cannot_be_reinterpreted_as_other_account_currency(self):
        self.buy();state=self.world['world_state']
        state['airlines'][self.owner]['base_currency']='EUR'
        for account in state['financial_accounts'].values():
            if account['airline_id']==self.owner:account['currency']='EUR'
        result=validate_world(self.world)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(e.code=='invalid_route_establishment' for e in result.errors))

    def test_legacy_command_rejected_without_mutation(self):
        del self.world['simulation']['operational_authority'];before=encoded(self.world)
        with self.assertRaisesRegex(ValueError,'quarterly'):self.quote()
        self.assertEqual(before,encoded(self.world))

    def session(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        session=Stage1Session(save_root=temp.name,runtime_clock=lambda:0);self.addCleanup(session.close)
        session.world=deepcopy(self.world);session.career_id=session.save_store.new_career_id()
        session._ensure_runtime();session._bind_owned_reads()
        return session

    def test_session_rebind_and_foreign_quote_reject(self):
        session=self.session();q=session.quote_route(self.hub,self.hub,self.ports['CEB'])
        other=self.session()
        with self.assertRaisesRegex(ValueError,'foreign'):other.apply_route(q)
        session.world=deepcopy(session.world)
        with self.assertRaisesRegex(ValueError,'stale'):session.apply_route(q)

    def test_save_load_and_exact_replay(self):
        session=self.session();q=session.quote_route(self.hub,self.hub,self.ports['CEB']);session.apply_route(q)
        session.save_manual();career=session.career_id
        def finish():
            session.apply_route(session.quote_route(self.hub,self.hub,self.ports['CEB'],action='CLOSE'))
            session.apply_route(session.quote_route(self.hub,self.hub,self.ports['CEB']))
            report=session.advance_to('2026-09-02T00:00:00Z')
            self.assertIsNone(report.result.failure)
            return encoded(session.world)
        expected=finish();session.load_saved(career)
        self.assertEqual(session.world['simulation']['clock_state'],'PAUSED')
        self.assertEqual(session.route_pair_status(self.hub,self.ports['CEB']),'ACTIVE')
        self.assertEqual(finish(),expected)

    def test_original_blocker_route_then_quarterly_service(self):
        session=self.session();self.assertFalse(session.world['world_state']['connections'])
        session.apply_route(session.quote_route(self.hub,self.hub,self.ports['CEB']))
        from game.scheduling.quarterly_commands import CreateQuarterlyService
        aircraft=next(iter(session.world['world_state']['aircraft']))
        slot=session.quarterly_slot_input(aircraft_id=aircraft,origin_id=self.hub,
            destination_id=self.ports['CEB'],weekdays=[0],departure_local_time='09:00:00',fare_minor=10000)
        request=CreateQuarterlyService(session.quarterly_planning_page()['target_quarter'],'RT',slot)
        result=session.prepare_quarterly_command(request)
        self.assertTrue(result.succeeded,result.issues)
        result=session.apply_quarterly_command(result.prepared)
        self.assertTrue(result.succeeded,result.issues)
        self.assertEqual(session.route_pair_status(self.hub,self.ports['CEB']),'ACTIVE')
        with self.assertRaisesRegex(ValueError,'draft'):session.quote_route(self.hub,self.hub,self.ports['CEB'],action='CLOSE')

    def test_resume_boundary_rejects_route_commands(self):
        session=self.session();q=session.quote_route(self.hub,self.hub,self.ports['CEB'])
        session.resume()
        before=encoded(session.world)
        with self.assertRaisesRegex(ValueError,'pause'):session.apply_route(q)
        self.assertEqual(before,encoded(session.world))

    def test_source_candidate_detached_gates_and_two_copies(self):
        from game.route_management import establishment
        q=self.quote();gates=[];copies=[];original=establishment.validate
        def gate(world):gates.append(world);return original(world)
        def clone(world):copies.append(world);return deepcopy(world)
        with patch.object(establishment,'validate',side_effect=gate),patch.object(establishment,'deepcopy',side_effect=clone):
            apply_route(self.world,q)
        self.assertEqual(len(gates),4);self.assertEqual(len(copies),2)
        self.assertIs(gates[0],self.world);self.assertIs(gates[1],self.world)
        self.assertIsNot(gates[2],self.world);self.assertIsNot(gates[3],gates[2])

    def test_paid_provenance_cannot_disappear_or_change_authority(self):
        cid=self.buy()
        changed=deepcopy(self.world);del changed['world_state']['connections'][cid]['route_establishment']
        self.assertFalse(validate_world(changed).is_valid)
        changed=deepcopy(self.world);del changed['simulation']['operational_authority']
        self.assertFalse(validate_world(changed).is_valid)

    def test_published_obligation_blocks_closure(self):
        from game.scheduling.quarterly_commands import CreateQuarterlyService, PublishQuarterlyPlan
        session=self.session();session.apply_route(session.quote_route(self.hub,self.hub,self.ports['CEB']))
        aircraft=next(iter(session.world['world_state']['aircraft']))
        target=session.quarterly_planning_page()['target_quarter']
        for origin,dest,time in ((self.hub,self.ports['CEB'],'09:00:00'),(self.ports['CEB'],self.hub,'13:00:00')):
            slot=session.quarterly_slot_input(aircraft_id=aircraft,origin_id=origin,destination_id=dest,
                weekdays=[0],departure_local_time=time,fare_minor=10000)
            page=session.quarterly_planning_page()
            result=session.prepare_quarterly_command(CreateQuarterlyService(target,'RT',slot,
                weekly_plan_id=page['plan_id'],expected_revision=page['revision']))
            self.assertTrue(result.succeeded,result.issues)
            self.assertTrue(session.apply_quarterly_command(result.prepared).succeeded)
        page=session.quarterly_planning_page()
        result=session.prepare_quarterly_command(PublishQuarterlyPlan('MANUAL',target,page['plan_id'],page['revision']))
        self.assertTrue(result.succeeded,result.issues)
        result=session.apply_quarterly_command(result.prepared)
        self.assertTrue(result.succeeded,result.issues)
        before=encoded(session.world)
        with self.assertRaisesRegex(ValueError,'published'):session.quote_route(self.hub,self.hub,self.ports['CEB'],action='CLOSE')
        self.assertEqual(before,encoded(session.world))

    def test_ineligible_airport_never_charged(self):
        self.state['airports'][self.ports['CEB']]['active_until_date']='2026-01-01'
        before=encoded(self.world)
        # Isolate the date eligibility check; full validation also rejects stale input.
        with patch('game.route_management.establishment.validate'):
            with self.assertRaisesRegex(ValueError,'eligible'):self.quote()
        self.assertEqual(before,encoded(self.world))


class RouteKivyTests(unittest.TestCase):
    def test_normal_loaded_quarterly_gui_purchase_confirmation(self):
        from app.gui.app import AirlineTycoonApp
        from kivy.uix.button import Button
        with tempfile.TemporaryDirectory() as temp:
            app=AirlineTycoonApp(session_factory=lambda:Stage1Session(save_root=temp,runtime_clock=lambda:0))
            app.build()
            try:
                app.session.new_quarterly_development_game('CEO','Route GUI','MNL')
                self.assertFalse(app.session.world['world_state']['connections'])
                app.session.save_manual();career=app.session.career_id;app.session.load_saved(career)
                app._enter_game();app.show_view('Research')
                ports={p['reference_code']:p['airport_id'] for p in app.session.airports()}
                buttons=[w.text for w in app._active_page.walk() if isinstance(w,Button)]
                self.assertIn('Create Route',buttons)
                before=app.session.authoritative_bytes()
                app.research_manage_route(ports['MNL'],ports['CEB'])
                self.assertEqual(before,app.session.authoritative_bytes())
                next(w for w in app._popup.content.walk() if isinstance(w,Button) and w.text=='Cancel').dispatch('on_release')
                self.assertEqual(before,app.session.authoritative_bytes())
                app.research_manage_route(ports['MNL'],ports['CEB'])
                popup=app._popup
                self.assertIsNotNone(popup)
                next(w for w in popup.content.walk() if isinstance(w,Button) and w.text=='Purchase route').dispatch('on_release')
                self.assertEqual(app.session.route_pair_status(ports['MNL'],ports['CEB']),'ACTIVE')
                self.assertTrue(any(r['route_status']=='ACTIVE' for r in app._active_page.rows))
                self.assertFalse(app.quarterly_development)
                before=app.session.authoritative_bytes()
                app.research_manage_route(ports['MNL'],ports['CEB'],action='CLOSE')
                next(w for w in app._popup.content.walk() if isinstance(w,Button) and w.text=='Cancel').dispatch('on_release')
                self.assertEqual(before,app.session.authoritative_bytes())
                app.research_manage_route(ports['MNL'],ports['CEB'],action='CLOSE')
                next(w for w in app._popup.content.walk() if isinstance(w,Button) and w.text=='Close route').dispatch('on_release')
                self.assertEqual(app.session.route_pair_status(ports['MNL'],ports['CEB']),'CLOSED')
                self.assertEqual(len(app.session.world['world_state']['transactions']),1)
            finally:app._dismiss();app.on_stop()
