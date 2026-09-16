"""Schema-5 configuration and purchase journal invariants."""

import re

from game.aircraft_market.reference_catalog import load_aircraft_catalog


def validate_configuration(aircraft, catalogs=None):
    configuration = aircraft['configuration']
    if type(configuration) is not dict or set(configuration) != {
            'contract', 'catalog_version', 'economy_capacity', 'performance_contract'}:
        raise ValueError('invalid aircraft configuration fields')
    if (configuration['contract'] != 'PH_MAX_ECONOMY_V1'
            or configuration['performance_contract'] != 'PH_SCALAR_RANGE_V1'):
        raise ValueError('unsupported aircraft configuration/performance contract')
    catalogs = {} if catalogs is None else catalogs
    version = configuration['catalog_version']
    if type(version) is not str:
        raise ValueError('invalid aircraft catalog version')
    if version not in catalogs:
        catalogs[version] = load_aircraft_catalog(catalog_version=version)
    view = catalogs[version].model(aircraft['model_reference'])
    if (type(configuration['economy_capacity']) is not int
            or configuration['economy_capacity'] != view['model']['max_economy_seats']):
        raise ValueError('installed capacity must match approved maximum Economy layout')
    return view


def validate_acquisition(envelope):
    world = envelope['world_state']
    configured = {key: value for key, value in world['aircraft'].items()
                  if 'configuration' in value}
    purchases = [t for t in world['transactions'].values()
                 if t.get('source_type') == 'AIRCRAFT_PURCHASE']
    if envelope['metadata']['save_schema_version'] != 5:
        if configured or purchases:
            raise ValueError('aircraft acquisition requires schema 5')
        return
    catalogs, views, registrations = {}, {}, {}
    for aircraft_id, aircraft in world['aircraft'].items():
        registrations.setdefault(aircraft['display_registration'], []).append(aircraft_id)
    for aircraft_id, aircraft in configured.items():
        views[aircraft_id] = validate_configuration(aircraft, catalogs)
        if len(registrations[aircraft['display_registration']]) != 1:
            raise ValueError('purchased aircraft registration must be globally unique')
        if aircraft['home_airport_id'] not in world['airlines'][aircraft['airline_id']]['base_airport_ids']:
            raise ValueError('purchased aircraft home must be an airline operating base')
    seen_aircraft, seen_commands = set(), set()
    for transaction in purchases:
        if set(transaction) != {'transaction_id', 'airline_id', 'occurred_at_utc',
                'description', 'currency', 'source_type', 'source_id', 'command_id',
                'request_fingerprint', 'delivery_airport_id', 'entries'}:
            raise ValueError('invalid purchase journal fields')
        aircraft_id = transaction['source_id']
        if type(aircraft_id) is not str or aircraft_id not in configured or aircraft_id in seen_aircraft:
            raise ValueError('purchase must identify exactly one configured aircraft')
        seen_aircraft.add(aircraft_id)
        aircraft = configured[aircraft_id]
        if transaction['airline_id'] != aircraft['airline_id'] or transaction['currency'] != 'USD':
            raise ValueError('purchase airline/currency mismatch')
        command = transaction['command_id']
        if (type(command) is not str or not command or len(command) > 128
                or command.strip() != command or any(ord(c) < 32 for c in command)
                or command in seen_commands):
            raise ValueError('invalid or duplicate purchase command')
        seen_commands.add(command)
        fingerprint = transaction['request_fingerprint']
        if type(fingerprint) is not str or re.fullmatch('[0-9a-f]{64}', fingerprint) is None:
            raise ValueError('invalid purchase request fingerprint')
        airline = world['airlines'][aircraft['airline_id']]
        if transaction['delivery_airport_id'] not in airline['base_airport_ids'] + airline['hub_airport_ids']:
            raise ValueError('invalid purchase delivery location')
        if transaction['occurred_at_utc'] > envelope['simulation']['time_utc']:
            raise ValueError('purchase cannot be in the future')
        accounts = {world['financial_accounts'][key]['code']: key for key in airline['financial_account_ids']}
        price = views[aircraft_id]['reference_price']['amount_minor']
        if transaction['entries'] != [
                {'account_id': accounts['aircraft_assets'], 'amount_minor': price},
                {'account_id': accounts['cash'], 'amount_minor': -price}]:
            raise ValueError('purchase journal must exchange cash for the catalog-price asset')
    if seen_aircraft != set(configured):
        raise ValueError('configured aircraft requires purchase provenance')
