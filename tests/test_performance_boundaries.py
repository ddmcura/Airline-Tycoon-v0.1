"""Structural checks for session-owned GUI reads and kernel event validation."""

from copy import deepcopy
from contextlib import ExitStack
import importlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.session import Stage1Session
from game.booking.checkpoint import prepare_daily_booking_checkpoint
from game.simulation.kernel import process_events_through
from game.world_state.validation import validate_world


class PerformanceBoundaryTests(unittest.TestCase):
    def test_booking_event_keeps_kernel_validation_without_nested_full_scans(self):
        with tempfile.TemporaryDirectory() as save_root:
            session = Stage1Session(save_root=save_root, runtime_clock=lambda: 0)
            session.new_game('CEO', 'Performance Air', 'MNL')
            calls = 0

            def count_validation(frame, event, _argument):
                nonlocal calls
                if event == 'call' and frame.f_code is validate_world.__code__:
                    calls += 1

            sys.setprofile(count_validation)
            try:
                report = session.advance_seconds(86_400)
            finally:
                sys.setprofile(None)
            self.assertTrue(report.result.succeeded)
            self.assertEqual(len(report.event_rows), 1)
            # Input, isolated candidate, and final clock boundaries remain.
            self.assertEqual(calls, 3)
            self.assertTrue(validate_world(session.world).is_valid)

    def test_fast_booking_event_matches_fully_validated_transaction(self):
        with tempfile.TemporaryDirectory() as save_root:
            session = Stage1Session(save_root=save_root, runtime_clock=lambda: 0)
            session.new_game('CEO', 'Performance Air', 'MNL')
            airports = {row['reference_code']: row['airport_id']
                        for row in session.airports()}
            aircraft_id = session.fleet()[0]['aircraft_id']
            draft = session.begin_scheduling(aircraft_id)
            draft.add(airports['MNL'], airports['DVO'],
                      departure_utc='2026-09-07T00:00:00Z', fare_minor=11_600)
            draft.add_return(fare_minor=11_600)
            self.assertTrue(session.save_scheduling(draft).succeeded)
            optimized = deepcopy(session.world)
            fully_validated = deepcopy(session.world)
            target = '2026-09-02T00:00:00Z'

            fast_result = process_events_through(optimized, target)
            with ExitStack() as stack:
                for name in ('game.booking.checkpoint', 'game.booking.allocation',
                             'game.booking.shopping', 'game.demand.model4'):
                    module = importlib.import_module(name)
                    stack.enter_context(patch.object(
                        module, '_EVENT_TRANSACTION_TOKEN', object()))
                slow_result = process_events_through(fully_validated, target)
            self.assertEqual(fast_result, slow_result)
            self.assertTrue(fast_result.succeeded)
            self.assertTrue(optimized['world_state']['bookings'])
            self.assertEqual(json.dumps(optimized, sort_keys=True),
                             json.dumps(fully_validated, sort_keys=True))
            self.assertTrue(validate_world(optimized).is_valid)

    def test_boolean_flag_cannot_bypass_public_booking_validation(self):
        with tempfile.TemporaryDirectory() as save_root:
            session = Stage1Session(save_root=save_root, runtime_clock=lambda: 0)
            session.new_game('CEO', 'Performance Air', 'MNL')
            invalid = deepcopy(session.world)
            invalid['simulation']['clock_state'] = 'INVALID'
            result = prepare_daily_booking_checkpoint(
                invalid, _event_transaction=True)
            self.assertFalse(result.succeeded)
            self.assertEqual(result.issues[0].code, 'INVALID_WORLD_STATE')

    def test_session_owned_header_is_fresh_after_advancement(self):
        with tempfile.TemporaryDirectory() as save_root:
            session = Stage1Session(save_root=save_root, runtime_clock=lambda: 0)
            session.new_game('CEO', 'Performance Air', 'MNL')
            initial = session.header()
            session.advance_seconds(86_400)
            later = session.header()
            self.assertNotEqual(initial['simulation_time_utc'],
                                later['simulation_time_utc'])
            self.assertEqual(later['simulation_time_utc'],
                             session.overview()['simulation_time_utc'])
            self.assertEqual(later['cash_minor'], session.finances()['cash_minor'])
