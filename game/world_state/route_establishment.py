"""Schema 9 optional paid-pair provenance and immutable receipt validation."""
import re
from game.economy.route_establishment import route_fee_minor
from .timestamps import parse_canonical_utc


def activate_paid_pair(candidate, owner, hub, market_ids):
    from .construction import add_connection
    world = candidate['world_state']
    ids = []
    for mid in market_ids:
        matches = [c for c in world['connections'].values()
                   if c['airline_id'] == owner and c['market_id'] == mid]
        cid = matches[0]['connection_id'] if matches else add_connection(candidate,owner,mid,status='ACTIVE')
        world['connections'][cid]['status'] = 'ACTIVE'
        ids.append(cid)
    connection = world['connections'][ids[0]]
    if 'route_establishment' not in connection:
        connection['route_establishment'] = dict(hub_airport_id=hub,reverse_connection_id=ids[1],
                                               payment_transaction_ids=[],closed_at_utc=None)
    connection['route_establishment']['closed_at_utc'] = None
    return tuple(ids)


def record_route_payment(candidate, connection_id, transaction_id):
    candidate['world_state']['connections'][connection_id]['route_establishment']['payment_transaction_ids'].append(transaction_id)


def close_paid_pair(candidate, connection_id):
    connections = candidate['world_state']['connections']
    record = connections[connection_id]['route_establishment']
    connections[connection_id]['status'] = 'CLOSED'
    connections[record['reverse_connection_id']]['status'] = 'CLOSED'
    record['closed_at_utc'] = candidate['simulation']['time_utc']


def validate_route_establishment(envelope):
    world = envelope['world_state']
    connections, markets = world['connections'], world['directional_markets']
    receipts = {k:t for k,t in world['transactions'].items()
                if t.get('source_type') == 'ROUTE_ESTABLISHMENT'}
    if (receipts or any('route_establishment' in c for c in connections.values())) and envelope['simulation'].get('operational_authority') != 'QUARTERLY_BACKEND_V1':
        raise ValueError('paid route provenance requires quarterly career authority')
    seen, commands, paired = set(), set(), set()
    for cid, connection in connections.items():
        if 'route_establishment' not in connection:
            continue
        if envelope['metadata']['save_schema_version'] != 9:
            raise ValueError('paid routes require Schema 9')
        record = connection['route_establishment']
        if type(record) is not dict or set(record) != {
                'hub_airport_id','reverse_connection_id','payment_transaction_ids','closed_at_utc'}:
            raise ValueError('invalid paid route fields')
        reverse_id = record['reverse_connection_id']
        if type(reverse_id) is not str or reverse_id not in connections:
            raise ValueError('missing reverse route connection')
        reverse = connections[reverse_id]
        market, back = markets[connection['market_id']], markets[reverse['market_id']]
        owner = connection['airline_id']
        if world['airlines'][owner]['base_currency'] != 'USD':
            raise ValueError('paid route receipts require USD owning accounts')
        if (market['origin_airport_id'] >= market['destination_airport_id']
                or back['origin_airport_id'] != market['destination_airport_id']
                or back['destination_airport_id'] != market['origin_airport_id']
                or reverse['airline_id'] != owner or 'route_establishment' in reverse
                or cid in paired or reverse_id in paired):
            raise ValueError('invalid canonical bidirectional route ownership')
        paired.update((cid,reverse_id))
        if (connection['status'] not in ('ACTIVE','CLOSED')
                or reverse['status'] != connection['status']):
            raise ValueError('paid route directions must have matching status')
        hub = record['hub_airport_id']
        if type(hub) is not str or hub not in world['airports']:
            raise ValueError('missing route attribution airport')
        if connection['status']=='ACTIVE' and hub not in world['airlines'][owner]['base_airport_ids']:
            raise ValueError('active route attribution must be an owned base or hub')
        closed = record['closed_at_utc']
        if connection['status'] == 'ACTIVE':
            if closed is not None: raise ValueError('active route cannot be closed')
        elif (type(closed) is not str or parse_canonical_utc(closed) > parse_canonical_utc(envelope['simulation']['time_utc'])):
            raise ValueError('invalid route closure timestamp')
        payments = record['payment_transaction_ids']
        if type(payments) is not list or not payments:
            raise ValueError('paid route requires payment provenance')
        last_time = ''
        for tid in payments:
            if type(tid) is not str or tid not in receipts or tid in seen:
                raise ValueError('missing or duplicate route payment')
            seen.add(tid); t = receipts[tid]
            if set(t) != {'transaction_id','airline_id','occurred_at_utc','description','currency',
                    'source_type','source_id','command_id','request_fingerprint','hub_airport_id',
                    'distance_m','base_fee_minor','active_pair_count','amount_minor','entries'}:
                raise ValueError('invalid route journal fields')
            if (t['airline_id'] != owner or t['source_id'] != cid or t['hub_airport_id'] != hub
                    or t['currency'] != 'USD' or t['occurred_at_utc'] < last_time
                    or t['occurred_at_utc'] > envelope['simulation']['time_utc']
                    or (closed is not None and t['occurred_at_utc'] > closed)):
                raise ValueError('invalid route payment lineage')
            last_time = t['occurred_at_utc']
            command = t['command_id']; fp = t['request_fingerprint']
            if (type(command) is not str or not command or len(command) > 128
                    or command.strip() != command or command in commands
                    or any(ord(c) < 32 for c in command)
                    or type(fp) is not str or re.fullmatch('[0-9a-f]{64}',fp) is None):
                raise ValueError('invalid route command witness')
            commands.add(command)
            if type(t['base_fee_minor']) is not int or t['base_fee_minor'] not in (2_500_000,7_500_000):
                raise ValueError('invalid route base fee')
            from game.utils.geo_distance import distance_km
            origin = world['airports'][market['origin_airport_id']]
            destination = world['airports'][market['destination_airport_id']]
            numerator,denominator = distance_km(origin,destination).as_integer_ratio()
            if (t['distance_m'] != numerator*1000//denominator
                    or t['base_fee_minor'] != (2_500_000 if origin['country_id']==destination['country_id'] else 7_500_000)):
                raise ValueError('route payment distance/country witness mismatch')
            amount = route_fee_minor(t['distance_m'],t['base_fee_minor']==2_500_000,t['active_pair_count'])
            if type(t['amount_minor']) is not int or t['amount_minor'] != amount:
                raise ValueError('incorrect route fee')
            accounts = {world['financial_accounts'][k]['code']:k
                        for k in world['airlines'][owner]['financial_account_ids']}
            if t['entries'] != [dict(account_id=accounts['operating_expenses'],amount_minor=amount),
                                dict(account_id=accounts['cash'],amount_minor=-amount)]:
                raise ValueError('incorrect route expense journal')
    if seen != set(receipts):
        raise ValueError('orphaned route payment')
