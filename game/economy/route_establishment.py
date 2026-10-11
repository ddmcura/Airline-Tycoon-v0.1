"""Exact USD route-entry expense, posted only inside a private candidate."""
from game.world_state.ids import allocate_id


def route_fee_minor(distance_m, domestic, active_pair_count):
    if (type(distance_m) is not int or distance_m < 0 or type(domestic) is not bool
            or type(active_pair_count) is not int or active_pair_count < 0):
        raise ValueError('invalid route fee inputs')
    base = 2_500_000 if domestic else 7_500_000
    numerator = base * (5_000_000 + distance_m) * (50 + active_pair_count)
    denominator = 5_000_000 * 50
    return (2 * numerator + denominator) // (2 * denominator)


def post_route_establishment(candidate, *, airline_id, source_id, command_id,
                             request_fingerprint, hub_airport_id, distance_m,
                             base_fee_minor, active_pair_count, amount_minor):
    world = candidate['world_state']
    airline = world['airlines'][airline_id]
    accounts = {world['financial_accounts'][k]['code']: world['financial_accounts'][k]
                for k in airline['financial_account_ids']}
    if airline['base_currency'] != 'USD' or accounts['cash']['balance_minor'] < amount_minor:
        raise ValueError('insufficient USD cash')
    tid = allocate_id(candidate, 'transaction')
    world['transactions'][tid] = dict(transaction_id=tid, airline_id=airline_id,
        occurred_at_utc=candidate['simulation']['time_utc'], description='Bidirectional route establishment',
        currency='USD', source_type='ROUTE_ESTABLISHMENT', source_id=source_id,
        command_id=command_id, request_fingerprint=request_fingerprint,
        hub_airport_id=hub_airport_id, distance_m=distance_m, base_fee_minor=base_fee_minor,
        active_pair_count=active_pair_count, amount_minor=amount_minor,
        entries=[dict(account_id=accounts['operating_expenses']['account_id'],amount_minor=amount_minor),
                 dict(account_id=accounts['cash']['account_id'],amount_minor=-amount_minor)])
    accounts['cash']['balance_minor'] -= amount_minor
    accounts['operating_expenses']['balance_minor'] += amount_minor
    airline['finance_revision'] += 1
    return tid
