"""Cross-record invariants for the schema-6 aircraft market."""

from datetime import date, timedelta
import re

from .ids import parse_entity_id
from .schema import AIRCRAFT_MARKET_CONFIGURATION
from .timestamps import is_canonical_utc


def _ceil_div(value, divisor):
    return (value + divisor - 1) // divisor


def _integer(value, *, minimum=0, label="value"):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")


def _listing_value(new_value, manufactured_date, generated_month, condition_bps, config):
    made = date.fromisoformat(manufactured_date)
    valued = date.fromisoformat(generated_month + "-01")
    completed_years = valued.year - made.year - ((valued.month, valued.day) < (made.month, made.day))
    age_bps = max(config["residual_value_bps"],
                  10_000 - completed_years * config["annual_depreciation_bps"])
    condition_multiplier = config["condition_value_floor_bps"] + (
        (10_000 - config["condition_value_floor_bps"]) * condition_bps // 10_000)
    return new_value * age_bps // 10_000 * condition_multiplier // 10_000


def _depreciated_value(new_value, manufactured_date, at_date, config):
    made = date.fromisoformat(manufactured_date)
    valued = date.fromisoformat(at_date)
    completed_years = valued.year - made.year - ((valued.month, valued.day) < (made.month, made.day))
    age_bps = max(config["residual_value_bps"],
                  10_000 - max(0, completed_years) * config["annual_depreciation_bps"])
    return new_value * age_bps // 10_000


def validate_aircraft_market(envelope):
    world = envelope["world_state"]
    config = envelope["simulation"]["configuration"].get("aircraft_market")
    if config != AIRCRAFT_MARKET_CONFIGURATION:
        raise ValueError("aircraft-market configuration is not the approved immutable contract")
    state = world["aircraft_market_state"]
    if set(state) != {"aircraft_market_id", "contract", "current_month", "rotation_revision",
                      "next_rotation_at_utc", "active_lease_offer_ids"}:
        raise ValueError("aircraft market state has noncanonical fields")
    if parse_entity_id(state["aircraft_market_id"], "aircraft_market") is None:
        raise ValueError("invalid aircraft market identifier")
    if state["contract"] != "PH_AIRCRAFT_MARKET_STATE_V1":
        raise ValueError("invalid aircraft market state contract")
    date.fromisoformat(state["current_month"] + "-01")
    _integer(state["rotation_revision"], label="rotation revision")
    if not is_canonical_utc(state["next_rotation_at_utc"]):
        raise ValueError("invalid next marketplace rotation timestamp")
    market_events = [event for event in world["pending_events"].values()
        if event.get("owner_type") == "aircraft_market"
        and event.get("owner_id") == state["aircraft_market_id"]
        and event.get("operation_revision") == envelope["simulation"]["operation_revisions"].get(
            state["aircraft_market_id"])]
    if (len(market_events) != 1
            or market_events[0].get("event_type") != "AIRCRAFT_MARKET_ROTATION"
            or market_events[0].get("due_at_utc") != state["next_rotation_at_utc"]):
        raise ValueError("aircraft marketplace requires exactly one current rotation event")
    counterparties = world["aircraft_market_counterparties"]
    offers = world["aircraft_lease_offers"]
    listings = world["used_aircraft_listings"]
    contracts = world["aircraft_contracts"]
    for key, row in counterparties.items():
        if key != row.get("counterparty_id") or parse_entity_id(key, "market_counterparty") is None:
            raise ValueError("invalid marketplace counterparty identity")
        if row.get("counterparty_type") not in {"LESSOR", "BACKGROUND_AIRLINE"}:
            raise ValueError("invalid marketplace counterparty type")
        if type(row.get("display_name")) is not str or not row["display_name"].strip():
            raise ValueError("counterparty display name is required")
        if type(row.get("active")) is not bool or type(row.get("specialization_model_ids")) is not list:
            raise ValueError("invalid counterparty fields")
        if set(row) != {"counterparty_id", "counterparty_type", "display_name", "active",
                        "specialization_model_ids"}:
            raise ValueError("counterparty has noncanonical fields")
        models = row["specialization_model_ids"]
        if len(models) != len(set(models)) or any(type(value) is not str for value in models):
            raise ValueError("counterparty specialization must contain unique model IDs")
        if (row["counterparty_type"] == "LESSOR") != bool(models):
            raise ValueError("only lessors require a nonempty specialization")
    active = []
    for key, row in offers.items():
        if key != row.get("lease_offer_id") or parse_entity_id(key, "lease_offer") is None:
            raise ValueError("invalid lease offer identity")
        if row.get("lessor_id") not in counterparties or counterparties[row["lessor_id"]]["counterparty_type"] != "LESSOR":
            raise ValueError("lease offer has invalid lessor")
        if row.get("status") not in {"ACTIVE", "EXHAUSTED", "EXPIRED"}:
            raise ValueError("invalid lease offer status")
        if set(row) != {"lease_offer_id", "lessor_id", "generated_month", "expires_at_utc",
                        "model_id", "catalog_version", "aircraft_value_minor",
                        "available_quantity", "configuration", "status"}:
            raise ValueError("lease offer has noncanonical fields")
        _integer(row.get("available_quantity"), label="offer quantity")
        if row["status"] == "ACTIVE":
            if row["available_quantity"] < 1:
                raise ValueError("active lease offer requires inventory")
            active.append(key)
    if state["active_lease_offer_ids"] != sorted(active):
        raise ValueError("active lease offer index is not canonical")
    airframes = set()
    sold_airframes = {}
    registrations = {row.get("display_registration") for row in world["aircraft"].values()}
    for key, row in listings.items():
        if key != row.get("used_listing_id") or parse_entity_id(key, "used_listing") is None:
            raise ValueError("invalid used listing identity")
        airframe_id = row.get("airframe_id")
        if parse_entity_id(airframe_id, "airframe") is None or airframe_id in airframes:
            raise ValueError("used listing airframe identity must be unique")
        if row.get("status") == "ACTIVE":
            airframes.add(airframe_id)
        else:
            if airframe_id in sold_airframes:
                raise ValueError("used listing airframe identity must be unique")
            sold_airframes[airframe_id] = row.get("sold_aircraft_id")
        if row.get("seller_id") not in counterparties or counterparties[row["seller_id"]]["counterparty_type"] != "BACKGROUND_AIRLINE":
            raise ValueError("used listing has invalid seller")
        if row.get("seller_source") != "BACKGROUND_AIRLINE":
            raise ValueError("schema-6 used listing requires the background-seller source")
        if row.get("status") not in {"ACTIVE", "SOLD"}:
            raise ValueError("invalid used listing status")
        if ((row["status"] == "ACTIVE" and row.get("sold_aircraft_id") is not None)
                or (row["status"] == "SOLD" and row.get("sold_aircraft_id") not in world["aircraft"])):
            raise ValueError("used listing sale linkage is inconsistent")
        if set(row) != {"used_listing_id", "airframe_id", "seller_id", "seller_source",
                        "generated_month", "model_id", "catalog_version", "configuration",
                        "display_registration", "manufactured_date",
                        "lifetime_flight_seconds", "lifetime_cycles", "service_condition_bps",
                        "asking_price_minor", "new_value_minor", "status", "sold_aircraft_id"}:
            raise ValueError("used listing has noncanonical fields")
        registration = row.get("display_registration")
        if type(registration) is not str or not registration:
            raise ValueError("used listing registration is required")
        if row["status"] == "ACTIVE" and registration in registrations:
            raise ValueError("active used listing registration must be globally unique")
        registrations.add(registration)
        for field in ("lifetime_flight_seconds", "lifetime_cycles",
                      "service_condition_bps", "asking_price_minor"):
            _integer(row.get(field), minimum=1 if field == "asking_price_minor" else 0, label=field)
        if row["service_condition_bps"] > 10_000:
            raise ValueError("service condition exceeds 100 percent")
        made = date.fromisoformat(row["manufactured_date"])
        generated = date.fromisoformat(row["generated_month"] + "-01")
        age_months = (generated.year - made.year) * 12 + generated.month - made.month
        if made.day > generated.day:
            age_months -= 1
        if not 24 <= age_months <= 240:
            raise ValueError("used listing age is inconsistent")
        annualized_hours = row["lifetime_flight_seconds"] * 12 // (age_months * 3600)
        if not 1_199 <= annualized_hours <= 3_600:
            raise ValueError("used listing utilization is incoherent")
        mean_leg_seconds = row["lifetime_flight_seconds"] // max(1, row["lifetime_cycles"])
        if not 55 * 60 <= mean_leg_seconds <= 300 * 60 + 1:
            raise ValueError("used listing cycles are incoherent with hours")
        expected_condition = max(4_000, 10_000
            - min(3_500, row["lifetime_flight_seconds"] // (18_000 * 3600))
            - min(2_500, row["lifetime_cycles"] // 8))
        if row["service_condition_bps"] != expected_condition:
            raise ValueError("used listing condition is inconsistent with history")
        _integer(row.get("new_value_minor"), minimum=1, label="new value")
        if row["asking_price_minor"] != _listing_value(row["new_value_minor"],
                row["manufactured_date"], row["generated_month"],
                row["service_condition_bps"], config):
            raise ValueError("used listing asking price is inconsistent")
    for aircraft in world["aircraft"].values():
        lifecycle = aircraft.get("lifecycle")
        if lifecycle is None:
            continue
        airframe_id = lifecycle.get("airframe_id")
        if parse_entity_id(airframe_id, "airframe") is None or airframe_id in airframes:
            raise ValueError("airframe identity must be globally unique")
        if airframe_id in sold_airframes and sold_airframes[airframe_id] != aircraft.get("aircraft_id"):
            raise ValueError("sold listing must link to the transferred airframe")
        airframes.add(airframe_id)
        if set(lifecycle) != {"airframe_id", "acquisition_type", "ownership_status",
                             "aircraft_contract_id", "source_listing_id",
                             "fixed_configuration", "manufactured_date",
                             "lifetime_flight_seconds", "lifetime_cycles",
                             "service_condition_bps"}:
            raise ValueError("aircraft lifecycle has noncanonical fields")
        if lifecycle.get("acquisition_type") not in {
                "NEW_PURCHASE", "USED_PURCHASE", "OPERATING_LEASE", "LEASE_TO_OWN",
                "STARTER_GRANT"}:
            raise ValueError("invalid aircraft acquisition type")
        if lifecycle.get("ownership_status") not in {"OWNED", "LESSOR_OWNED", "RETURNED"}:
            raise ValueError("invalid aircraft ownership status")
        if type(lifecycle.get("fixed_configuration")) is not bool:
            raise ValueError("fixed-configuration marker must be boolean")
        date.fromisoformat(lifecycle.get("manufactured_date"))
        for field in ("lifetime_flight_seconds", "lifetime_cycles", "service_condition_bps"):
            _integer(lifecycle.get(field), label=field)
        if lifecycle["service_condition_bps"] > 10_000:
            raise ValueError("aircraft condition exceeds 100 percent")
        if lifecycle["ownership_status"] == "LESSOR_OWNED" and (
                not lifecycle["fixed_configuration"]
                or lifecycle.get("aircraft_contract_id") not in contracts):
            raise ValueError("lessor-owned aircraft requires a fixed configuration and contract")
        if lifecycle["ownership_status"] == "OWNED" and lifecycle["fixed_configuration"]:
            raise ValueError("owned aircraft cannot retain the lessor configuration lock")
        if lifecycle["acquisition_type"] == "STARTER_GRANT":
            if ("configuration" not in aircraft
                    or lifecycle["ownership_status"] != "OWNED"
                    or lifecycle["aircraft_contract_id"] is not None
                    or lifecycle["source_listing_id"] is not None
                    or lifecycle["fixed_configuration"]
                    or lifecycle["manufactured_date"] != envelope["metadata"]["world_created_at_utc"][:10]
                    or any(contract["aircraft_id"] == aircraft["aircraft_id"]
                           for contract in contracts.values())
                    or any(listing.get("sold_aircraft_id") == aircraft["aircraft_id"]
                           for listing in listings.values())):
                raise ValueError("starter grant requires a configured, unencumbered opening aircraft")
        if lifecycle["acquisition_type"] == "USED_PURCHASE" and (
                lifecycle.get("source_listing_id") not in listings
                or listings[lifecycle["source_listing_id"]].get("sold_aircraft_id") != aircraft.get("aircraft_id")):
            raise ValueError("used aircraft must preserve sold-listing provenance")
    command_ids = set()
    for key, row in contracts.items():
        if key != row.get("aircraft_contract_id") or parse_entity_id(key, "aircraft_contract") is None:
            raise ValueError("invalid aircraft contract identity")
        if row.get("contract_type") not in {"OPERATING_LEASE", "LEASE_TO_OWN"}:
            raise ValueError("invalid aircraft contract type")
        if row.get("status") not in {"FUTURE", "ACTIVE", "COMPLETED", "RETURNED", "CANCELLED"}:
            raise ValueError("invalid aircraft contract status")
        common_fields = {"aircraft_contract_id", "contract_type", "status", "airline_id",
            "aircraft_id", "lessor_id", "offer_id", "predecessor_contract_id",
            "successor_contract_id", "delivery_airport_id", "started_at_utc",
            "expires_at_utc", "term_years", "total_installments", "paid_installments",
            "aircraft_value_minor", "monthly_rent_minor", "monthly_financing_minor",
            "principal_base_minor", "principal_remainder_installments",
            "principal_paid_minor", "financing_paid_minor", "next_payment_at_utc",
            "command_id", "request_fingerprint"}
        cancellation_fields = {"cancellation_depreciated_value_minor", "cancellation_equity_minor",
                               "cancellation_restoration_minor"}
        if frozenset(row) not in {frozenset(common_fields), frozenset(common_fields | cancellation_fields)}:
            raise ValueError("aircraft contract has noncanonical fields")
        if (row.get("aircraft_id") not in world["aircraft"]
                or row.get("lessor_id") not in counterparties
                or counterparties[row["lessor_id"]].get("counterparty_type") != "LESSOR"):
            raise ValueError("aircraft contract has dangling party or aircraft")
        if row.get("airline_id") not in world["airlines"]:
            raise ValueError("aircraft contract has dangling airline")
        if row.get("delivery_airport_id") not in world["airports"]:
            raise ValueError("aircraft contract has dangling delivery airport")
        offer_id = row.get("offer_id")
        predecessor_id = row.get("predecessor_contract_id")
        if offer_id is None:
            if (row["contract_type"] != "OPERATING_LEASE" or predecessor_id not in contracts
                    or contracts[predecessor_id].get("successor_contract_id") != key):
                raise ValueError("only a linked operating renewal may omit its offer")
        elif offer_id not in offers or offers[offer_id].get("lessor_id") != row["lessor_id"]:
            raise ValueError("aircraft contract has invalid offer provenance")
        elif (world["aircraft"][row["aircraft_id"]].get("model_reference") != offers[offer_id].get("model_id")
              or world["aircraft"][row["aircraft_id"]].get("configuration") != offers[offer_id].get("configuration")):
            raise ValueError("leased aircraft must match its accepted offer")
        successor_id = row.get("successor_contract_id")
        if successor_id is not None and (
                row["contract_type"] != "OPERATING_LEASE" or successor_id not in contracts
                or contracts[successor_id].get("predecessor_contract_id") != key):
            raise ValueError("invalid operating renewal link")
        command_id = row.get("command_id")
        fingerprint = row.get("request_fingerprint")
        if (type(command_id) is not str or not command_id or command_id in command_ids
                or re.fullmatch("[0-9a-f]{64}", str(fingerprint)) is None):
            raise ValueError("invalid or duplicate contract command witness")
        command_ids.add(command_id)
        if type(row.get("term_years")) is not int or row["term_years"] not in range(1, 6):
            raise ValueError("contract term must be one through five years")
        for field in ("started_at_utc", "expires_at_utc"):
            if not is_canonical_utc(row.get(field)):
                raise ValueError("contract timestamp is invalid")
        if row["started_at_utc"] >= row["expires_at_utc"]:
            raise ValueError("contract expiry must follow its start")
        _integer(row.get("paid_installments"), label="paid installments")
        _integer(row.get("total_installments"), minimum=12, label="total installments")
        if row["paid_installments"] > row["total_installments"]:
            raise ValueError("paid installments exceed contract installments")
        if row["total_installments"] != row["term_years"] * 12:
            raise ValueError("contract installment count must match term")
        for field in ("aircraft_value_minor", "monthly_rent_minor", "monthly_financing_minor",
                      "principal_base_minor", "principal_remainder_installments",
                      "principal_paid_minor", "financing_paid_minor"):
            _integer(row.get(field), label=field)
        value = row["aircraft_value_minor"]
        years = row["term_years"]
        paid = row["paid_installments"]
        if row["contract_type"] == "OPERATING_LEASE":
            expected_rent = _ceil_div(value * config["operating_rate_bps_by_term_years"][str(years)], 10_000)
            if (row["monthly_rent_minor"] != expected_rent or row["monthly_financing_minor"]
                    or row["principal_base_minor"] or row["principal_remainder_installments"]
                    or row["principal_paid_minor"] or row["financing_paid_minor"]):
                raise ValueError("operating lease pricing/progress is inconsistent")
        else:
            months = years * 12
            expected_financing = _ceil_div(value * config["lto_financing_bps_by_term_years"][str(years)], 10_000)
            base, remainder = divmod(value, months)
            expected_principal = paid * base + min(paid, remainder)
            if (row["monthly_rent_minor"] or row["monthly_financing_minor"] != expected_financing
                    or row["principal_base_minor"] != base
                    or row["principal_remainder_installments"] != remainder
                    or row["principal_paid_minor"] != expected_principal
                    or row["financing_paid_minor"] != paid * expected_financing):
                raise ValueError("lease-to-own pricing/progress is inconsistent")
        if row["status"] in {"ACTIVE", "FUTURE"}:
            expected_next = row.get("next_payment_at_utc")
            if paid < row["total_installments"] and not is_canonical_utc(expected_next):
                raise ValueError("live contract requires the next payment timestamp")
            if paid == row["total_installments"] and expected_next is not None:
                raise ValueError("fully paid contract cannot retain a next payment timestamp")
        elif row.get("next_payment_at_utc") is not None:
            raise ValueError("closed contract cannot retain a next payment timestamp")
        pending = [event for event in world["pending_events"].values()
                   if event.get("owner_type") == "aircraft_contract"
                   and event.get("owner_id") == key
                   and event.get("operation_revision") == envelope["simulation"]["operation_revisions"].get(key)]
        if row["status"] == "ACTIVE":
            payments = [event for event in pending if event.get("event_type") == "AIRCRAFT_CONTRACT_PAYMENT"]
            expiries = [event for event in pending if event.get("event_type") == "AIRCRAFT_CONTRACT_EXPIRY"]
            expected_payments = 0 if paid == row["total_installments"] else 1
            if len(payments) != expected_payments or len(expiries) != 1:
                raise ValueError("active contract has an invalid event schedule")
            if payments and payments[0].get("due_at_utc") != row["next_payment_at_utc"]:
                raise ValueError("contract payment event does not match next payment")
            if expiries[0].get("due_at_utc") != row["expires_at_utc"]:
                raise ValueError("contract expiry event does not match expiry")
        elif row["status"] == "FUTURE" and pending:
            raise ValueError("future renewal events must wait for activation")
    account_codes = {key: row["code"] for key, row in world["financial_accounts"].items()}

    def coded_entries(transaction):
        return [(account_codes.get(entry.get("account_id")), entry.get("amount_minor"))
                for entry in transaction.get("entries", [])]

    contract_transactions = {key: [] for key in contracts}
    used_purchase_transactions = []
    for transaction in world["transactions"].values():
        if transaction.get("source_type") in {"AIRCRAFT_LEASE_TERMINATION",
                "AIRCRAFT_LTO_CANCELLATION", "USED_AIRCRAFT_PURCHASE"}:
            transaction_command = transaction.get("command_id")
            if (type(transaction_command) is not str or not transaction_command
                    or transaction_command in command_ids
                    or re.fullmatch("[0-9a-f]{64}", str(transaction.get("request_fingerprint"))) is None):
                raise ValueError("invalid or duplicate aircraft-market command witness")
            command_ids.add(transaction_command)
        if transaction.get("source_type") == "USED_AIRCRAFT_PURCHASE":
            used_purchase_transactions.append(transaction)
        if transaction.get("source_type") in {
                "AIRCRAFT_LEASE_PAYMENT", "AIRCRAFT_LEASE_TERMINATION",
                "AIRCRAFT_LTO_PAYMENT", "AIRCRAFT_LTO_CANCELLATION"}:
            if transaction.get("source_id") not in contract_transactions:
                raise ValueError("aircraft contract journal has a dangling source")
            contract_transactions[transaction["source_id"]].append(transaction)
    for contract_id, contract in contracts.items():
        rows = sorted(contract_transactions[contract_id],
                      key=lambda row: (row["occurred_at_utc"], row["transaction_id"]))
        payment_type = ("AIRCRAFT_LEASE_PAYMENT" if contract["contract_type"] == "OPERATING_LEASE"
                        else "AIRCRAFT_LTO_PAYMENT")
        payments = [row for row in rows if row["source_type"] == payment_type]
        if len(payments) != contract["paid_installments"]:
            raise ValueError("contract payment journals do not match installment progress")
        for index, transaction in enumerate(payments, 1):
            if transaction.get("airline_id") != contract["airline_id"]:
                raise ValueError("contract payment journal has the wrong airline")
            if contract["contract_type"] == "OPERATING_LEASE":
                amount = contract["monthly_rent_minor"]
                expected = [("operating_expenses", amount), ("cash", -amount)]
            else:
                principal = contract["principal_base_minor"] + (
                    1 if index <= contract["principal_remainder_installments"] else 0)
                financing = contract["monthly_financing_minor"]
                expected = [("aircraft_assets", principal),
                            ("operating_expenses", financing),
                            ("cash", -(principal + financing))]
            if coded_entries(transaction) != expected:
                raise ValueError("contract payment journal entries are inconsistent")
        cancellations = [row for row in rows if row["source_type"] in {
            "AIRCRAFT_LEASE_TERMINATION", "AIRCRAFT_LTO_CANCELLATION"}]
        if len(cancellations) != (1 if contract["status"] == "CANCELLED" else 0):
            raise ValueError("contract cancellation journal count is inconsistent")
        if cancellations:
            transaction = cancellations[0]
            remaining = contract["total_installments"] - contract["paid_installments"]
            if contract["contract_type"] == "OPERATING_LEASE":
                settlement = -(remaining * contract["monthly_rent_minor"])
                asset_remove = 0
                if transaction["source_type"] != "AIRCRAFT_LEASE_TERMINATION":
                    raise ValueError("operating cancellation has the wrong journal type")
            else:
                aircraft = world["aircraft"][contract["aircraft_id"]]
                lifecycle = aircraft["lifecycle"]
                depreciated = _depreciated_value(contract["aircraft_value_minor"],
                    lifecycle["manufactured_date"], transaction["occurred_at_utc"][:10], config)
                remaining_principal = contract["aircraft_value_minor"] - contract["principal_paid_minor"]
                equity = max(0, depreciated - remaining_principal)
                restoration = _ceil_div(contract["aircraft_value_minor"]
                    * (10_000 - lifecycle["service_condition_bps"])
                    * config["restoration_max_bps"], 100_000_000)
                settlement = equity - remaining * contract["monthly_financing_minor"] - restoration
                asset_remove = contract["principal_paid_minor"]
                if (transaction["source_type"] != "AIRCRAFT_LTO_CANCELLATION"
                        or contract.get("cancellation_depreciated_value_minor") != depreciated
                        or contract.get("cancellation_equity_minor") != equity
                        or contract.get("cancellation_restoration_minor") != restoration):
                    raise ValueError("lease-to-own cancellation witnesses are inconsistent")
            expected = []
            if settlement:
                expected.append(("cash", settlement))
            expense = asset_remove - settlement
            if expense:
                expected.append(("operating_expenses", expense))
            if asset_remove:
                expected.append(("aircraft_assets", -asset_remove))
            if coded_entries(transaction) != expected:
                raise ValueError("contract cancellation journal entries are inconsistent")
    for listing in listings.values():
        purchases = [row for row in used_purchase_transactions
                     if row.get("source_id") == listing.get("sold_aircraft_id")]
        if len(purchases) != (1 if listing["status"] == "SOLD" else 0):
            raise ValueError("used listing purchase journal count is inconsistent")
        if purchases:
            transaction = purchases[0]
            aircraft = world["aircraft"][listing["sold_aircraft_id"]]
            if (transaction.get("airline_id") != aircraft["airline_id"]
                    or transaction.get("delivery_airport_id") not in world["airports"]
                    or coded_entries(transaction) != [("aircraft_assets", listing["asking_price_minor"]),
                                                      ("cash", -listing["asking_price_minor"])]):
                raise ValueError("used-aircraft purchase journal is inconsistent")
    sold_aircraft_ids = {row["sold_aircraft_id"] for row in listings.values()
                         if row["status"] == "SOLD"}
    if {row.get("source_id") for row in used_purchase_transactions} != sold_aircraft_ids:
        raise ValueError("used-aircraft purchase journals must map exactly to sold listings")
    def contract_horizon(aircraft, lifecycle):
        contract = contracts.get(lifecycle.get("aircraft_contract_id"))
        if contract is None:
            raise ValueError("lessor-owned aircraft requires an active contract")
        horizon = contract["expires_at_utc"]
        successor_id = contract.get("successor_contract_id")
        seen = set()
        while successor_id is not None:
            if successor_id in seen:
                raise ValueError("operating-lease renewal chain cannot contain a cycle")
            seen.add(successor_id)
            successor = contracts.get(successor_id)
            if successor is None or successor.get("contract_type") != "OPERATING_LEASE":
                raise ValueError("invalid operating-lease renewal chain")
            horizon = successor["expires_at_utc"]
            successor_id = successor.get("successor_contract_id")
        return horizon

    from game.scheduling.publication import _occurrence_record
    for schedule in world["schedule_definitions"].values():
        for revision in schedule["revisions"].values():
            aircraft = world["aircraft"].get(revision.get("planned_aircraft_id"), {})
            lifecycle = aircraft.get("lifecycle")
            if type(lifecycle) is not dict or lifecycle.get("ownership_status") != "LESSOR_OWNED":
                continue
            until = revision.get("recurrence", {}).get("until_local_date")
            if until is None:
                raise ValueError("leased schedule requires a finite confirmed recurrence")
            until_date = date.fromisoformat(until)
            for weekday in revision["recurrence"]["weekdays"]:
                last_date = until_date - timedelta(days=(until_date.weekday() - weekday) % 7)
                if last_date < date.fromisoformat(revision["effective_from_local_date"]):
                    continue
                occurrence = _occurrence_record(envelope, schedule, revision, last_date)
                if occurrence["scheduled_in_block_utc"] > contract_horizon(aircraft, lifecycle):
                    raise ValueError("leased schedule recurrence exceeds the confirmed contract horizon")

    for flight in world["dated_flights"].values():
        if flight.get("status") not in {"PLANNED", "OPERATIONALLY_LOCKED"}:
            continue
        aircraft = world["aircraft"].get(flight.get("planned_aircraft_id"), {})
        lifecycle = aircraft.get("lifecycle")
        if type(lifecycle) is not dict:
            continue
        if lifecycle.get("ownership_status") == "RETURNED":
            raise ValueError("returned aircraft cannot retain a live flight")
        if lifecycle.get("ownership_status") != "LESSOR_OWNED":
            continue
        horizon = contract_horizon(aircraft, lifecycle)
        if flight.get("scheduled_in_block_utc", "") > horizon:
            raise ValueError("leased flight must complete within the confirmed contract horizon")
    issued = {
        "aircraft_market": [state["aircraft_market_id"]],
        "market_counterparty": list(counterparties),
        "lease_offer": list(offers),
        "used_listing": list(listings),
        "aircraft_contract": list(contracts),
        "airframe": [row["airframe_id"] for row in listings.values()] + [
            row["lifecycle"]["airframe_id"] for row in world["aircraft"].values()
            if type(row.get("lifecycle")) is dict
        ],
    }
    allocator = envelope["deterministic_state"]["id_allocator"]["next_by_type"]
    for entity_type, identifiers in issued.items():
        maximum = max((parse_entity_id(value, entity_type)[1] for value in identifiers),
                      default=0)
        if allocator.get(entity_type, 0) <= maximum:
            raise ValueError(f"{entity_type} allocator must exceed every issued identity")
