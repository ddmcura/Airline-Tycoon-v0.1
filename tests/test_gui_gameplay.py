"""Graphical PH action loop over the shared authoritative session."""

import os
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')

from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from app.gui.app import AirlineTycoonApp
from app.session import Stage1Session
from app.terminal.session import Stage1Session as TerminalSession
from game.world_state.timestamps import format_utc, parse_canonical_utc


class FakeClock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += int(seconds * 1_000_000_000)


class GameplayGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.app = AirlineTycoonApp(session_factory=lambda: Stage1Session(
            save_root=self.tmp.name, runtime_clock=self.clock))
        self.app.build()
        self.app.create_new_game('CEO', 'Action Air', 'MNL')

    def tearDown(self):
        self.app._dismiss()
        self.app.on_stop()
        self.tmp.cleanup()

    def click(self, caption):
        button = next(w for w in self.app._popup.content.walk()
                      if isinstance(w, Button) and w.text == caption)
        button.dispatch('on_release')

    def form_fields(self):
        return [w for w in self.app._popup.content.walk()
                if isinstance(w, (Spinner, TextInput))]

    def test_research_projection_and_frontend_neutral_parsing(self):
        self.assertIs(Stage1Session, TerminalSession)
        before = self.app.session.authoritative_bytes()
        self.app.show_view('Research')
        labels = [w.text for w in self.app.content.children if isinstance(w, Label)]
        self.assertTrue(any('Base daily bookers' in text for text in labels))
        self.assertEqual(self.app.session.authoritative_bytes(), before)
        self.app.choose_research_origin()
        self.assertTrue(self.app._popup)
        self.app._dismiss()

    def test_new_purchase_preview_commit_and_stale_rejection(self):
        session = self.app.session
        catalog = session.aircraft_catalog()
        models = [model for maker in catalog.manufacturers()
                  for model in catalog.models(maker['manufacturer_id'])]
        model = min(models, key=lambda m: catalog.model(m['model_id'])['reference_price']['amount_minor'])
        self.app.show_view('Acquire')
        before = session.authoritative_bytes()
        self.app.begin_acquisition('new', model)
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')
        self.click('Continue')
        self.assertIn('Cash after', self.app._popup.content.children[-1].text)
        self.click('Confirm')
        self.assertEqual(len(session.fleet(limit=100)), 2)
        self.assertNotEqual(session.authoritative_bytes(), before)
        self.assertIn('Fleet', self.app.current_view)
        self.assertIn('Cash', self.app.status.text)
        self.app._dismiss()

        quote = session.preview_purchase(model['model_id'], session.delivery_locations()[0]['airport_id'])
        session.resume()
        unchanged = session.authoritative_bytes()
        with self.assertRaisesRegex(ValueError, 'stale'):
            session.purchase(quote)
        self.assertEqual(session.authoritative_bytes(), unchanged)


    def test_unpublished_draft_requires_discard_choice_before_departure(self):
        session = self.app.session
        session.save_manual()
        aircraft_id = session.fleet(limit=100)[0]['aircraft_id']
        self.app.show_view('Schedule')
        self.app.start_schedule(aircraft_id)
        self.assertFalse(session.unsaved_progress)
        self.app.return_to_title()
        self.assertEqual(self.app.screens.current, 'game')
        self.assertEqual(self.app._popup.title, 'Unpublished schedule draft')
        self.click('Cancel')
        self.assertIsNotNone(self.app._draft)
        self.app.return_to_title()
        self.click('Discard draft and continue')
        self.assertEqual(self.app.screens.current, 'title')
        self.assertIsNone(self.app._draft)

    def test_unaffordable_purchase_is_rejected_without_world_change(self):
        session = self.app.session
        catalog = session.aircraft_catalog()
        model = max((m for maker in catalog.manufacturers()
                     for m in catalog.models(maker['manufacturer_id'])),
                    key=lambda m: catalog.model(m['model_id'])['reference_price']['amount_minor'])
        session.purchase(session.preview_purchase(
            model['model_id'], session.delivery_locations()[0]['airport_id']))
        before = session.authoritative_bytes()
        self.app.begin_acquisition('new', model)
        self.click('Continue')
        self.assertIn('Cash after -', self.app._popup.content.children[-1].text)
        self.click('Confirm')
        self.assertIn('Acquisition rejected', self.app._popup.title)
        self.assertEqual(session.authoritative_bytes(), before)

    def test_lease_used_and_invalid_acquisition(self):
        session = self.app.session
        delivery = session.delivery_locations()[0]['airport_id']
        offer = session.leasing_offers()[0]
        self.app.begin_acquisition('lease', offer)
        fields = self.form_fields()
        next(w for w in fields if isinstance(w, Spinner) and 'Lease-to-own' in w.values).text = 'Lease-to-own'
        self.click('Continue')
        self.assertIn('Monthly financing', self.app._popup.content.children[-1].text)
        self.click('Confirm')
        self.assertEqual(len(session.fleet(limit=100)), 2)
        self.app._dismiss()

        listing = session.used_listings()[0]
        self.app.begin_acquisition('used', listing)
        self.click('Continue')
        self.click('Confirm')
        self.assertEqual(len(session.fleet(limit=100)), 3)
        self.app._dismiss()

        before = session.authoritative_bytes()
        with self.assertRaises(ValueError):
            session.preview_lease(offer['lease_offer_id'], 'OPERATING_LEASE', 8, delivery)
        self.assertEqual(session.authoritative_bytes(), before)

    def test_graphical_weekly_loop_run_observe_save_load(self):
        session = self.app.session
        self.app.show_view('Research')
        self.app.show_view('Acquire')
        model = min((m for maker in session.aircraft_catalog().manufacturers()
                     for m in session.aircraft_catalog().models(maker['manufacturer_id'])),
                    key=lambda m: session.aircraft_catalog().model(m['model_id'])['reference_price']['amount_minor'])
        prior_ids = {row['aircraft_id'] for row in session.fleet(limit=100)}
        self.app.begin_acquisition('new', model)
        self.click('Continue')
        self.click('Confirm')
        self.app._dismiss()
        aircraft = next(row for row in session.fleet(limit=100)
                        if row['aircraft_id'] not in prior_ids)
        self.app.show_view('Schedule')
        self.app.start_schedule(aircraft['aircraft_id'])
        before = session.authoritative_bytes()
        self.app.show_add_leg()
        spinners = [w for w in self.form_fields() if isinstance(w, Spinner)]
        spinners[1].text = spinners[0].text
        self.click('Continue')
        self.assertEqual(session.authoritative_bytes(), before)
        self.assertEqual(len(self.app._draft.legs), 0)
        self.app._dismiss()
        self.app.show_add_leg()
        self.click('Continue')
        self.assertEqual(len(self.app._draft.legs), 1)
        self.assertEqual(session.authoritative_bytes(), before)
        self.app.add_return()
        self.assertEqual(len(self.app._draft.legs), 2)
        self.app.show_save_schedule()
        self.click('Continue')
        self.click('Save and publish')
        self.assertIsNone(self.app._draft)
        self.assertTrue(session.flights(limit=100))
        self.assertTrue(session.validate())
        self.app._dismiss()

        flights = session.flights(limit=100)
        target = format_utc(parse_canonical_utc(
            max(row['scheduled_departure_utc'] for row in flights)) + timedelta(days=1))
        self.app._begin_target(target)
        for _ in range(1200):
            if not session.advancing:
                break
            self.app.tick(0)
        self.assertFalse(session.advancing)
        self.app.show_view('Flights')
        self.assertTrue(any('COMPLETED' in w.text for w in self.app.content.children
                            if isinstance(w, Label)))
        self.app.show_view('Finance')
        self.assertTrue(any('Passenger revenue' in w.text for w in self.app.content.children
                            if isinstance(w, Label)))
        self.app.save_game()
        self.app._dismiss()
        saved = session.authoritative_bytes()
        career = session.career_id
        session.load_saved(career)
        self.assertEqual(session.world['simulation']['clock_state'], 'PAUSED')
        self.assertTrue(session.validate())
        self.assertTrue(session.flights(limit=100))
        self.assertNotEqual(saved, b'')
        self.assertTrue(Path(self.tmp.name, career, 'manual.json').exists())


if __name__ == '__main__':
    unittest.main()
