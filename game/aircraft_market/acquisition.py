"""Atomic, idempotent purchase commands; previews carry no authority."""

from copy import deepcopy
from dataclasses import dataclass, asdict
from hashlib import sha256
import json

from game.economy.acquisition import purchase_accounts, post_purchase
from game.fleet_management.acquisition import delivery_locations, enter_purchased_aircraft
from game.world_state.validation import validate_world
from .reference_catalog import load_aircraft_catalog


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()


def _fingerprint(envelope):
    return _digest({key: value for key, value in envelope.items() if key != 'ui_state'})


def _validate(envelope):
    result = validate_world(envelope)
    if not result.is_valid:
        raise ValueError(result.errors[0].message)
    if envelope['metadata']['save_schema_version'] != 5:
        raise ValueError('purchase requires explicit schema 5 migration')


@dataclass(frozen=True)
class PurchasePreview:
    airline_id: str
    model_id: str
    catalog_version: str
    delivery_airport_id: str
    command_id: str
    world_fingerprint: str
    amount_minor: int
    cash_after_minor: int


def preview_purchase(envelope, *, airline_id, model_id, catalog_version,
                     delivery_airport_id, command_id=None):
    _validate(envelope)
    world = envelope['world_state']
    view = load_aircraft_catalog(catalog_version=catalog_version).model(model_id)
    if type(airline_id) is not str or airline_id not in world['airlines']:
        raise ValueError('unknown airline')
    if type(delivery_airport_id) is not str or delivery_airport_id not in delivery_locations(world, airline_id):
        raise ValueError('delivery must be an existing airline base or hub')
    accounts = purchase_accounts(world, airline_id)
    price = view['reference_price']['amount_minor']
    fingerprint = _fingerprint(envelope)
    if command_id is None:
        command_id = 'purchase-' + _digest([fingerprint, airline_id, catalog_version,
                                          model_id, delivery_airport_id])
    if (type(command_id) is not str or not command_id or command_id.strip() != command_id
            or len(command_id) > 128 or any(ord(c) < 32 for c in command_id)):
        raise ValueError('invalid command identifier')
    return PurchasePreview(airline_id, model_id, catalog_version, delivery_airport_id,
                           command_id, fingerprint, price,
                           accounts['cash']['balance_minor'] - price)


def purchase_aircraft(envelope, preview):
    """Return aircraft ID; rejected commands raise without modifying authority."""
    _validate(envelope)
    if type(preview) is not PurchasePreview:
        raise ValueError('invalid purchase preview')
    request = _digest(asdict(preview))
    for transaction in envelope['world_state']['transactions'].values():
        if (transaction.get('source_type') == 'AIRCRAFT_PURCHASE'
                and transaction['command_id'] == preview.command_id):
            if transaction['request_fingerprint'] != request:
                raise ValueError('purchase command identifier already used')
            return transaction['source_id']
    expected = preview_purchase(envelope, airline_id=preview.airline_id,
        model_id=preview.model_id, catalog_version=preview.catalog_version,
        delivery_airport_id=preview.delivery_airport_id, command_id=preview.command_id)
    if expected != preview:
        raise ValueError('stale or altered purchase preview; review again')
    if preview.cash_after_minor < 0:
        raise ValueError('insufficient cash')
    view = load_aircraft_catalog(catalog_version=preview.catalog_version).model(preview.model_id)
    candidate = deepcopy(envelope)
    aircraft_id = enter_purchased_aircraft(candidate, preview.airline_id,
                                         preview.delivery_airport_id, view)
    post_purchase(candidate, airline_id=preview.airline_id, aircraft_id=aircraft_id,
                  delivery_airport_id=preview.delivery_airport_id,
                  command_id=preview.command_id, request_fingerprint=request,
                  amount_minor=preview.amount_minor)
    _validate(candidate)
    envelope.clear()
    envelope.update(candidate)
    return aircraft_id
