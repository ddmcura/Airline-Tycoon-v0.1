"""USD aircraft purchase accounting; called inside an isolated transaction."""

from game.world_state.ids import allocate_id


def purchase_accounts(world, airline_id):
    airline = world['airlines'][airline_id]
    if airline['base_currency'] != 'USD':
        raise ValueError('PH purchases require USD accounting')
    return {world['financial_accounts'][key]['code']: world['financial_accounts'][key]
            for key in airline['financial_account_ids']}


def post_purchase(candidate, *, airline_id, aircraft_id, delivery_airport_id,
                  command_id, request_fingerprint, amount_minor):
    world = candidate['world_state']
    accounts = purchase_accounts(world, airline_id)
    if type(amount_minor) is not int or amount_minor <= 0:
        raise ValueError('invalid purchase price')
    if accounts['cash']['balance_minor'] < amount_minor:
        raise ValueError('insufficient cash')
    transaction_id = allocate_id(candidate, 'transaction')
    world['transactions'][transaction_id] = {
        'transaction_id': transaction_id, 'airline_id': airline_id,
        'occurred_at_utc': candidate['simulation']['time_utc'],
        'description': 'New aircraft purchase', 'currency': 'USD',
        'source_type': 'AIRCRAFT_PURCHASE', 'source_id': aircraft_id,
        'command_id': command_id, 'request_fingerprint': request_fingerprint,
        'delivery_airport_id': delivery_airport_id,
        'entries': [
            {'account_id': accounts['aircraft_assets']['account_id'], 'amount_minor': amount_minor},
            {'account_id': accounts['cash']['account_id'], 'amount_minor': -amount_minor},
        ],
    }
    accounts['cash']['balance_minor'] -= amount_minor
    accounts['aircraft_assets']['balance_minor'] += amount_minor
    world['airlines'][airline_id]['finance_revision'] += 1
    return transaction_id
