"""Balanced schema-6 aircraft-market postings inside isolated candidates."""

from game.economy.acquisition import purchase_accounts
from game.world_state.ids import allocate_id


def post_aircraft_market_transaction(candidate, *, airline_id, description,
                                     source_type, source_id, entries,
                                     command_id=None, request_fingerprint=None,
                                     delivery_airport_id=None):
    world = candidate["world_state"]
    normalized = normalize_market_entries(world, airline_id, entries)
    transaction_id = allocate_id(candidate, "transaction")
    row = market_transaction_record(transaction_id=transaction_id, airline_id=airline_id,
        occurred_at_utc=candidate["simulation"]["time_utc"], description=description,
        source_type=source_type, source_id=source_id, entries=normalized,
        command_id=command_id, request_fingerprint=request_fingerprint,
        delivery_airport_id=delivery_airport_id)
    world["transactions"][transaction_id] = row
    for entry in normalized:
        world["financial_accounts"][entry["account_id"]]["balance_minor"] += entry["amount_minor"]
    world["airlines"][airline_id]["finance_revision"] += 1
    return transaction_id


def normalize_market_entries(world, airline_id, entries):
    """The existing exact posting predicates, shared with transition validation."""
    accounts = purchase_accounts(world, airline_id)
    normalized = []
    for code, amount in entries:
        if type(amount) is not int:
            raise ValueError("aircraft-market posting amounts must be integer minor units")
        if not amount:
            continue
        if code not in accounts:
            raise ValueError("aircraft-market posting references an unknown account")
        normalized.append({"account_id": accounts[code]["account_id"], "amount_minor": amount})
    if len(normalized) < 2 or sum(row["amount_minor"] for row in normalized):
        raise ValueError("financial posting must have balanced nonzero entries")
    return normalized


def market_transaction_record(*, transaction_id, airline_id, occurred_at_utc,
                              description, source_type, source_id, entries,
                              command_id=None, request_fingerprint=None,
                              delivery_airport_id=None):
    """Pure construction; allocation, balance mutation and revision stay in posting."""
    row = {"transaction_id": transaction_id, "airline_id": airline_id,
        "occurred_at_utc": occurred_at_utc, "description": description, "currency": "USD",
        "source_type": source_type, "source_id": source_id, "entries": entries}
    if command_id is not None:
        row["command_id"] = command_id
        row["request_fingerprint"] = request_fingerprint
    if delivery_airport_id is not None:
        row["delivery_airport_id"] = delivery_airport_id
    return row


__all__ = ("post_aircraft_market_transaction",)
