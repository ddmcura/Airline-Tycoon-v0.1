"""PH 1.0 Step 5 leasing and used-aircraft regression coverage."""

from copy import deepcopy
import json
import unittest

from game.aircraft_market.step5 import (
    _depreciated_value,
    _restoration,
    accept_lease,
    preview_lease,
    preview_used_purchase,
    purchase_used_aircraft,
    renew_operating_lease,
    terminate_contract,
)
from game.economy.acquisition import purchase_accounts
from game.scheduling.weekly import WeeklyDraft
from game.simulation import process_events_through, process_next_event
from game.world_state import create_stage1_new_game, validate_world
from game.world_state.schema import AIRCRAFT_MARKET_CONFIGURATION


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class AircraftMarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.world = create_stage1_new_game(
            scenario_id="stage1-philippines-v1", ceo_display_name="A",
            airline_display_name="B", base_airport_reference_code="MNL")
        state = self.world["world_state"]
        self.airline_id = state["player"]["primary_airline_id"]
        self.delivery = state["airlines"][self.airline_id]["base_airport_ids"][0]
        self.airports = {row["reference_code"]: key for key, row in state["airports"].items()}

    def lease(self, product="OPERATING_LEASE", years=1, offer_id=None):
        state = self.world["world_state"]
        offer_id = offer_id or state["aircraft_market_state"]["active_lease_offer_ids"][0]
        preview = preview_lease(self.world, airline_id=self.airline_id,
            offer_id=offer_id, contract_type=product, term_years=years,
            delivery_airport_id=self.delivery)
        return accept_lease(self.world, preview)

    def test_schema6_market_generation_is_deterministic_and_valid(self):
        other = create_stage1_new_game(
            scenario_id="stage1-philippines-v1", ceo_display_name="A",
            airline_display_name="B", base_airport_reference_code="MNL")
        self.assertEqual(encoded(self.world), encoded(other))
        state = self.world["world_state"]
        self.assertEqual(len(state["aircraft_market_state"]["active_lease_offer_ids"]), 6)
        self.assertEqual(len(state["used_aircraft_listings"]), 4)
        self.assertTrue(validate_world(self.world).is_valid)
        restored = json.loads(encoded(self.world))
        self.assertEqual(encoded(restored), encoded(self.world))
        self.assertTrue(validate_world(restored).is_valid)

    def test_term_pricing_has_approved_direction_and_discount(self):
        offer = self.world["world_state"]["aircraft_market_state"]["active_lease_offer_ids"][0]
        operating, lto = [], []
        for years in range(1, 6):
            op = preview_lease(self.world, airline_id=self.airline_id, offer_id=offer,
                contract_type="OPERATING_LEASE", term_years=years,
                delivery_airport_id=self.delivery, command_id=f"op-{years}")
            own = preview_lease(self.world, airline_id=self.airline_id, offer_id=offer,
                contract_type="LEASE_TO_OWN", term_years=years,
                delivery_airport_id=self.delivery, command_id=f"own-{years}")
            operating.append(op.monthly_rent_minor)
            lto.append(own.monthly_financing_minor)
            self.assertLess(own.monthly_financing_minor, op.monthly_rent_minor)
        self.assertEqual(operating, sorted(operating, reverse=True))
        self.assertEqual(lto, sorted(lto, reverse=True))
        self.assertGreater(5 * 12 * operating[-1], operating[0] * 12)
        self.assertGreater(5 * 12 * lto[-1], lto[0] * 12)

    def test_accept_is_atomic_stale_safe_and_idempotent(self):
        state = self.world["world_state"]
        offer = state["aircraft_market_state"]["active_lease_offer_ids"][0]
        preview = preview_lease(self.world, airline_id=self.airline_id, offer_id=offer,
            contract_type="OPERATING_LEASE", term_years=2,
            delivery_airport_id=self.delivery, command_id="lease-command")
        state["aircraft_lease_offers"][offer]["available_quantity"] += 1
        before = encoded(self.world)
        with self.assertRaisesRegex(ValueError, "stale"):
            accept_lease(self.world, preview)
        self.assertEqual(encoded(self.world), before)
        preview = preview_lease(self.world, airline_id=self.airline_id, offer_id=offer,
            contract_type="OPERATING_LEASE", term_years=2,
            delivery_airport_id=self.delivery, command_id="lease-command-2")
        aircraft_id = accept_lease(self.world, preview)
        self.assertEqual(accept_lease(self.world, preview), aircraft_id)
        self.assertEqual(len(self.world["world_state"]["aircraft_contracts"]), 1)

    def test_payment_is_automatic_separate_and_allows_negative_cash(self):
        aircraft_id = self.lease("LEASE_TO_OWN", 1)
        state = self.world["world_state"]
        contract = next(iter(state["aircraft_contracts"].values()))
        accounts = purchase_accounts(state, self.airline_id)
        accounts["cash"]["balance_minor"] = 0
        due = contract["next_payment_at_utc"]
        result = process_events_through(self.world, due)
        self.assertTrue(result.succeeded, result.failure)
        contract = self.world["world_state"]["aircraft_contracts"][contract["aircraft_contract_id"]]
        self.assertEqual(contract["paid_installments"], 1)
        self.assertGreater(contract["principal_paid_minor"], 0)
        self.assertEqual(contract["financing_paid_minor"], contract["monthly_financing_minor"])
        self.assertLess(purchase_accounts(self.world["world_state"], self.airline_id)["cash"]["balance_minor"], 0)
        self.assertEqual(self.world["world_state"]["aircraft"][aircraft_id]["lifecycle"]["ownership_status"], "LESSOR_OWNED")
        expected_settlement = contract["principal_paid_minor"] - (
            contract["total_installments"] - contract["paid_installments"]
        ) * contract["monthly_financing_minor"]
        settlement = terminate_contract(self.world, aircraft_id=aircraft_id,
                                        command_id="cancel-lto-after-one")
        self.assertEqual(settlement, expected_settlement)
        self.assertEqual(purchase_accounts(self.world["world_state"], self.airline_id)["aircraft_assets"]["balance_minor"], 0)

    def test_operating_termination_charges_only_remaining_rent_and_is_idempotent(self):
        aircraft_id = self.lease()
        contract = next(iter(self.world["world_state"]["aircraft_contracts"].values()))
        expected = -(contract["total_installments"] * contract["monthly_rent_minor"])
        self.assertEqual(terminate_contract(self.world, aircraft_id=aircraft_id,
                                             command_id="terminate-op"), expected)
        self.assertEqual(terminate_contract(self.world, aircraft_id=aircraft_id,
                                             command_id="terminate-op"), expected)
        self.assertEqual(self.world["world_state"]["aircraft"][aircraft_id]["status"], "RETURNED")

    def test_lto_settlement_worked_examples_and_no_condition_double_count(self):
        config = AIRCRAFT_MARKET_CONFIGURATION
        value = 10_000_000_000
        self.assertEqual(_depreciated_value(value, "2025-09-01", "2026-09-01T00:00:00Z", config),
                         9_600_000_000)
        self.assertEqual(_restoration(value, 9_000, config), 200_000_000)
        principal_paid = 5_000_000_004
        equity = max(0, 9_600_000_000 - (value - principal_paid))
        self.assertEqual(equity - 12 * 85_000_000 - 200_000_000, 3_380_000_004)
        first_principal = 416_666_667
        early_equity = max(0, value - (value - first_principal))
        self.assertEqual(early_equity - 23 * 85_000_000 - _restoration(value, 8_000, config),
                         -1_938_333_333)

    def test_used_purchase_preserves_specific_airframe_and_consumes_once(self):
        state = self.world["world_state"]
        purchase_accounts(state, self.airline_id)["cash"]["balance_minor"] = 10**14
        listing = next(row for row in state["used_aircraft_listings"].values()
                       if row["status"] == "ACTIVE")
        facts = deepcopy(listing)
        preview = preview_used_purchase(self.world, airline_id=self.airline_id,
            listing_id=listing["used_listing_id"], delivery_airport_id=self.delivery,
            command_id="used-command")
        aircraft_id = purchase_used_aircraft(self.world, preview)
        self.assertEqual(purchase_used_aircraft(self.world, preview), aircraft_id)
        aircraft = self.world["world_state"]["aircraft"][aircraft_id]
        lifecycle = aircraft["lifecycle"]
        for listing_field, lifecycle_field in (
            ("airframe_id", "airframe_id"), ("manufactured_date", "manufactured_date"),
            ("lifetime_flight_seconds", "lifetime_flight_seconds"),
            ("lifetime_cycles", "lifetime_cycles"),
            ("service_condition_bps", "service_condition_bps")):
            self.assertEqual(facts[listing_field], lifecycle[lifecycle_field])
        self.assertEqual(aircraft["display_registration"], facts["display_registration"])
        self.assertEqual(self.world["world_state"]["used_aircraft_listings"][facts["used_listing_id"]]["status"], "SOLD")

    def test_rotation_expires_lease_offers_but_retains_used_listings(self):
        state = self.world["world_state"]
        old_offers = set(state["aircraft_market_state"]["active_lease_offer_ids"])
        old_listings = set(state["used_aircraft_listings"])
        target = state["aircraft_market_state"]["next_rotation_at_utc"]
        stepped = deepcopy(self.world)
        result = process_events_through(self.world, target)
        self.assertTrue(result.succeeded, result.failure)
        while any(event["due_at_utc"] <= target
                  for event in stepped["world_state"]["pending_events"].values()):
            result = process_next_event(stepped)
            self.assertTrue(result.succeeded, result.failure)
        self.assertEqual(encoded(stepped), encoded(self.world))
        state = self.world["world_state"]
        self.assertTrue(old_listings.issubset(state["used_aircraft_listings"]))
        self.assertTrue(all(state["aircraft_lease_offers"][key]["status"] == "EXPIRED"
                            for key in old_offers))
        self.assertEqual(len(state["used_aircraft_listings"]), len(old_listings) + 4)

    def test_renewal_preserves_aircraft_and_extends_confirmed_horizon(self):
        aircraft_id = self.lease()
        state = self.world["world_state"]
        aircraft_before = deepcopy(state["aircraft"][aircraft_id])
        current = next(iter(state["aircraft_contracts"].values()))
        successor_id = renew_operating_lease(self.world, aircraft_id=aircraft_id,
                                              term_years=3, command_id="renew-1")
        state = self.world["world_state"]
        successor = state["aircraft_contracts"][successor_id]
        self.assertEqual(successor["status"], "FUTURE")
        self.assertGreater(successor["expires_at_utc"], current["expires_at_utc"])
        after = state["aircraft"][aircraft_id]
        for field in ("aircraft_id", "display_registration", "configuration", "lifecycle"):
            self.assertEqual(after[field], aircraft_before[field])

    def test_schedule_beyond_unrenewed_expiry_rejects_atomically(self):
        aircraft_id = self.lease()
        state = self.world["world_state"]
        contract = next(iter(state["aircraft_contracts"].values()))
        # Bring the boundary inside the publication window; the guard is about
        # the exact completion boundary, independent of commercial term length.
        expiry = contract["next_payment_at_utc"]
        contract["expires_at_utc"] = expiry
        for event in state["pending_events"].values():
            if event["owner_id"] == contract["aircraft_contract_id"] and event["event_type"] == "AIRCRAFT_CONTRACT_EXPIRY":
                event["due_at_utc"] = expiry
        self.assertTrue(validate_world(self.world).is_valid)
        draft = WeeklyDraft(self.world, airline_id=self.airline_id, aircraft_id=aircraft_id)
        draft.add(self.airports["MNL"], self.airports["CEB"], departure_utc=expiry)
        before = encoded(self.world)
        with self.assertRaisesRegex(ValueError, "contract horizon"):
            draft.save(self.world)
        self.assertEqual(encoded(self.world), before)


if __name__ == "__main__":
    unittest.main()
