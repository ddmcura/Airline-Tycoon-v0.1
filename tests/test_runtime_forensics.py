"""Diagnostic instrumentation must not change production routing or authority."""
import unittest
from copy import deepcopy
from tests.profile_runtime_forensics import structure,changes,booking_temperature,run
from tests.flight_fixtures import flight_world
from tests.resolution_oracle import world_digest
from game.world_state.timestamps import parse_canonical_utc

class RuntimeForensicsTests(unittest.TestCase):
    def test_rejects_nonfinite_budget_before_engine_work(self):
        for budget in (float('nan'),float('inf'),0,-1):
            with self.assertRaises(ValueError):run({},budget=budget)

    def test_structure_counts_shared_container_once(self):
        row={'x':[1,2]};value={'a':row,'b':row}
        self.assertEqual(structure(value)['containers'],3)
        self.assertEqual(structure(value)['entries'],5)
    def test_change_report_uses_stable_record_ids(self):
        a={'world_state':{'aircraft':{'aircraft-id':{'status':'PARKED'}}}}
        b=deepcopy(a);b['world_state']['aircraft']['aircraft-id']['status']='IN_FLIGHT'
        self.assertEqual(changes(a,b),{'aircraft':['aircraft-id']})
        self.assertEqual(a['world_state']['aircraft']['aircraft-id']['status'],'PARKED')
    def test_instrumented_and_quiet_complete_authority_match(self):
        world=flight_world(1);before=world_digest(world)
        departure=min(e['due_at_utc'] for e in world['world_state']['pending_events'].values() if e['event_type']=='STAGE1_FLIGHT_DEPARTURE')
        seconds=int((parse_canonical_utc(departure)-parse_canonical_utc(world['simulation']['time_utc'])).total_seconds())
        quiet=run(world,seconds,budget=60,profiled=False)
        diagnostic=run(world,seconds,budget=60,profiled=True)
        self.assertTrue(quiet['complete'] and diagnostic['complete'])
        self.assertEqual(quiet['hash'],diagnostic['hash'])
        self.assertEqual(quiet['event_vector'],diagnostic['event_vector'])
        self.assertEqual(quiet['callback_count'],diagnostic['callback_count'])
        self.assertIn('flight_witness',diagnostic['calls'])
        self.assertEqual(world_digest(world),before)
        self.assertGreaterEqual(diagnostic['residual'],-.01)
        self.assertEqual(diagnostic['families']['STAGE1_FLIGHT_DEPARTURE']['children'],1)
    def test_booking_temperature_is_derived_and_read_only(self):
        w={'world_state':{'bookings':{'b':{'itinerary_id':'i'}},'itineraries':{'i':{'dated_flight_ids':['f']}},'dated_flights':{'f':{'status':'COMPLETED'}}}}
        old=deepcopy(w);self.assertEqual(booking_temperature(w),{'COMPLETED':1});self.assertEqual(w,old)
    def test_instrumentation_does_not_replace_certificate_metadata(self):
        from contextlib import ExitStack
        from tests.profile_runtime_forensics import instrument
        from tests.profile_atomic_boundaries import ExclusiveProfile
        from game.simulation.handlers import initialize_runtime_handlers
        from game.simulation.kernel import DEFAULT_EVENT_HANDLERS
        initialize_runtime_handlers()
        contract=DEFAULT_EVENT_HANDLERS.execution_contract_for('STAGE1_FLIGHT_DEPARTURE')
        with ExitStack() as stack:
            instrument(stack,ExclusiveProfile(),{})
            self.assertIs(DEFAULT_EVENT_HANDLERS.execution_contract_for('STAGE1_FLIGHT_DEPARTURE'),contract)
            self.assertIs(DEFAULT_EVENT_HANDLERS.handler_for('STAGE1_FLIGHT_DEPARTURE'),contract.handler)
    def test_instrumentation_cleanup_restores_hooks_and_gc(self):
        import gc
        from contextlib import ExitStack
        from tests.profile_runtime_forensics import instrument
        from tests.profile_atomic_boundaries import ExclusiveProfile
        from game.simulation import kernel
        original=kernel._apply_handler_candidate;callbacks=list(gc.callbacks)
        with ExitStack() as stack:
            instrument(stack,ExclusiveProfile(),{})
            self.assertIsNot(kernel._apply_handler_candidate,original)
        self.assertIs(kernel._apply_handler_candidate,original);self.assertEqual(gc.callbacks,callbacks)

if __name__=='__main__':unittest.main()
