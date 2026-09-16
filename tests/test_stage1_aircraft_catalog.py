"""Catalog content, strict boundaries, browsing and deterministic continuation."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.terminal.main import _Terminal, _EndOfInput, run_terminal
from app.terminal.session import Stage1Session
from game.aircraft_market.reference_catalog import (
    AircraftCatalog, PH_AIRCRAFT_CATALOG_VERSION, load_aircraft_catalog,
)
from game.world_state.aircraft_catalog import parse_aircraft_catalog, validate_aircraft_catalog


def pack():
    return json.loads((Path(__file__).parents[1] / "Data/Stage1/aircraft_catalog_v1.json")
                      .read_text(encoding="utf-8"))


def catalog():
    return load_aircraft_catalog(catalog_version=PH_AIRCRAFT_CATALOG_VERSION)


class CatalogTests(unittest.TestCase):
    def test_approved_roster_seats_and_prices(self):
        expected = {
            "airbus": [("A320neo",194,55),("A321neo",244,65),("A330-900",465,150),("A350-900",440,160)],
            "boeing": [("737-8-200",210,60),("737-9",220,65),("787-9",406,145),("787-10",440,170)],
            "de-havilland-canada": [("Twin Otter Classic 300-G",19,7),("Dash 8-200",40,12),("Dash 8-300",56,17),("Dash 8-400 / Q400",90,30)],
            "embraer": [("E175",88,25),("E190",114,30),("E190-E2",114,35),("E195-E2",146,40)],
            "bombardier-crj": [("CRJ200",50,15),("CRJ700",78,22),("CRJ900",90,27),("CRJ1000",104,32)],
        }
        ref = catalog()
        self.assertEqual({m["manufacturer_id"] for m in ref.manufacturers()}, set(expected))
        for mfr, entries in expected.items():
            actual = [(row["display_name"], row["max_economy_seats"],
                       ref.model(row["model_id"])["reference_price"]["amount_minor"])
                      for row in ref.models(mfr)]
            self.assertEqual(sorted(actual), sorted((n,s,p*100_000_000) for n,s,p in entries))

    def test_exact_version_and_identifiers_only(self):
        for version in (None, [], "latest", "../aircraft_catalog_v1", "ph-aircraft-catalog-v2"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                load_aircraft_catalog(catalog_version=version)
        with self.assertRaises(TypeError):
            load_aircraft_catalog()
        for model_id in ("A320neo", "A320-200", [], None):
            with self.subTest(model_id=model_id), self.assertRaises(ValueError):
                catalog().model(model_id)
        with self.assertRaises(ValueError):
            catalog().models("Airbus")

    def test_immutable_value_and_deeply_detached_projections(self):
        source = pack()
        ref = AircraftCatalog(source)
        original = ref.model("airbus-a320neo")
        source["models"]["airbus-a320neo"]["max_economy_seats"] = 1
        view = ref.model("airbus-a320neo")
        view["model"]["source_ids"].clear()
        view["reference_price"]["amount_minor"] = 1
        view["sources"][0]["url"] = "changed"
        ref.manufacturers()[0]["display_name"] = "changed"
        ref.models("airbus")[0]["max_economy_seats"] = 1
        self.assertEqual(ref.model("airbus-a320neo"), original)
        with self.assertRaises(FrozenInstanceError):
            ref._json = "{}"

    def test_order_and_json_roundtrip_do_not_change_projections(self):
        source = pack()
        def reverse(value):
            if type(value) is dict:
                return {k: reverse(v) for k,v in reversed(list(value.items()))}
            if type(value) is list:
                return [reverse(v) for v in value]
            return value
        left, right = AircraftCatalog(source), AircraftCatalog(reverse(source))
        self.assertEqual(left, right)
        self.assertEqual(left.manufacturers(), right.manufacturers())
        self.assertEqual(left.models("boeing"), right.models("boeing"))
        self.assertEqual(parse_aircraft_catalog(json.dumps(source)), source)

    def test_bad_numeric_fields_reject_without_repair(self):
        for field, values in {
            "max_economy_seats": [True, 1.0, 0, 1001, None],
            "reference_range_km": [True, -1, 30001, "100"],
            "cruise_speed_kph": [False, 0, 2001],
            "production_start_year": [False, 1800, 10000, 2000.0],
            "production_end_year": [True, 1900],
        }.items():
            for value in values:
                source = pack()
                source["models"]["airbus-a320neo"][field] = value
                before = deepcopy(source)
                with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                    validate_aircraft_catalog(source)
                self.assertEqual(source, before)

    def test_bad_shapes_foreign_keys_text_and_sources_reject(self):
        cases = [
            lambda p: p.update(extra=True),
            lambda p: p.update(models=[]),
            lambda p: p["models"]["airbus-a320neo"].update(model_id="other"),
            lambda p: p["models"]["airbus-a320neo"].update(manufacturer_id=[]),
            lambda p: p["models"]["airbus-a320neo"].update(manufacturer_id="missing"),
            lambda p: p["models"]["airbus-a320neo"].update(aircraft_category="UNKNOWN"),
            lambda p: p["models"]["airbus-a320neo"].update(notes="line\nbreak"),
            lambda p: p["models"]["airbus-a320neo"].update(display_name=" padded "),
            lambda p: p["models"]["airbus-a320neo"].update(source_ids=[[]]),
            lambda p: p["models"]["airbus-a320neo"].update(source_ids=["missing"]),
            lambda p: p["models"]["airbus-a320neo"].update(source_ids=["airbus-prices"]*2),
            lambda p: p["reference_prices"].pop("airbus-a320neo"),
            lambda p: p["reference_prices"]["airbus-a320neo"].update(amount_minor=True),
            lambda p: p["reference_prices"]["airbus-a320neo"].update(currency="PHP"),
            lambda p: p["reference_prices"]["airbus-a320neo"].update(model_id="other"),
            lambda p: p["sources"]["airbus-prices"].update(url="file:///test"),
            lambda p: p["sources"]["airbus-prices"].update(source_id="other"),
            lambda p: p["manufacturers"]["airbus"].update(manufacturer_id="other"),
        ]
        for number, mutate in enumerate(cases):
            source = pack()
            mutate(source)
            with self.subTest(case=number), self.assertRaises(ValueError):
                validate_aircraft_catalog(source)

    def test_dates_are_metadata_not_availability_rules(self):
        source = pack()
        source["models"]["airbus-a320neo"].update(production_start_year=1950,production_end_year=1951)
        source["models"]["boeing-737-9"].update(production_start_year=2100,production_end_year=None)
        ref = AircraftCatalog(source)
        self.assertEqual(len(ref.models("airbus")),4)
        self.assertEqual(len(ref.models("boeing")),4)

    def test_duplicate_json_keys_and_nonfinite_constants_reject(self):
        for raw in ('{"models":{},"models":{}}', '{"models":{"a":{},"a":{}}}',
                    '{"contract":NaN}', '{"contract":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_aircraft_catalog(raw)

    def test_registered_content_is_pinned_semantically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"aircraft_catalog_v1.json"
            source = pack()
            # Formatting is not authority, so a reformatted file remains compatible.
            path.write_text(json.dumps(source),encoding="utf-8")
            with patch("game.aircraft_market.reference_catalog._DATA", Path(directory)):
                self.assertEqual(catalog().version, PH_AIRCRAFT_CATALOG_VERSION)
                source["models"]["airbus-a320neo"]["max_economy_seats"] = 193
                path.write_text(json.dumps(source),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"content mismatch"):
                    catalog()
                source["catalog_version"] = "other-version"
                path.write_text(json.dumps(source),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"version mismatch"):
                    catalog()


class CatalogTerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Stage1Session()
        base.new_game("Avery", "Meridian", "MNL")
        cls.seed = deepcopy(base.world)

    def session(self):
        session = Stage1Session()
        session.world = deepcopy(self.seed)
        session.changed = False
        return session

    def test_browse_back_cancel_invalid_selection_and_currency_are_read_only(self):
        session = self.session()
        session.set_display_currency("PHP")
        before = session.authoritative_bytes()
        output = StringIO()
        terminal = _Terminal(StringIO("bad\n1\nbad\n1\nback\n2\n1\ncancel\n"),output,session)
        terminal.aircraft_catalogue()
        text = output.getvalue()
        for expected in ("Invalid manufacturer", "Invalid model", "194 seats", "USD", "PHP",
                         "Production start: 2012", "Purchase New Aircraft"):
            self.assertIn(expected,text)
        self.assertEqual(before,session.authoritative_bytes())
        self.assertFalse(session.changed)

    def test_menu_integration_and_eof_preserve_world(self):
        for transcript in ("11\n1\n1\ncancel\n0\ny\n", "11\n1\n"):
            session = self.session()
            before = session.authoritative_bytes()
            output = StringIO()
            # run_terminal enters startup, so inject the pre-existing game via new_game_form.
            with patch.object(_Terminal,"startup",_Terminal.main_menu):
                self.assertEqual(run_terminal(StringIO(transcript),output,
                                              session_factory=lambda:session),0)
            self.assertIn("Aircraft Catalogue",output.getvalue())
            self.assertEqual(before,session.authoritative_bytes())
            self.assertFalse(session.changed)

    def test_missing_or_corrupt_content_keeps_session_usable(self):
        for error in (FileNotFoundError("missing"),ValueError("invalid content")):
            session = self.session()
            before = session.authoritative_bytes()
            output = StringIO()
            with patch.object(session,"aircraft_catalog",side_effect=error):
                _Terminal(StringIO(),output,session).aircraft_catalogue()
            self.assertIn("catalogue unavailable",output.getvalue())
            self.assertEqual(before,session.authoritative_bytes())
            self.assertTrue(session.validate())
            self.assertFalse(session.changed)

    def test_interrupt_and_eof_do_not_mutate(self):
        for error in (_EndOfInput(),KeyboardInterrupt()):
            session = self.session()
            before = session.authoritative_bytes()
            terminal = _Terminal(StringIO(),StringIO(),session)
            with patch.object(terminal,"prompt",side_effect=error), self.assertRaises(type(error)):
                terminal.aircraft_catalogue()
            self.assertEqual(before,session.authoritative_bytes())
            self.assertFalse(session.changed)

    def test_booked_published_world_and_continuation_are_unchanged(self):
        left = self.session()
        aircraft_id = next(iter(left.world["world_state"]["aircraft"]))
        self.assertTrue(left.plan_rotation(aircraft_id,"CEB",10_000,"2026-09-07").succeeded)
        left.advance_seconds(86400)
        right = self.session()
        right.world = deepcopy(left.world)
        right.changed = left.changed
        before = left.authoritative_bytes()
        _Terminal(StringIO("1\n1\ncancel\n"),StringIO(),left).aircraft_catalogue()
        self.assertEqual(before,left.authoritative_bytes())
        left.advance_seconds(86400)
        right.advance_seconds(86400)
        self.assertEqual(left.authoritative_bytes(),right.authoritative_bytes())


if __name__ == "__main__":
    unittest.main()
