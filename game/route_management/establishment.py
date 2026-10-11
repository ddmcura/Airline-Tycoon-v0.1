"""Paid pair commands for quarterly careers; legacy route writers are untouched."""
from copy import deepcopy
from dataclasses import dataclass, asdict
from hashlib import sha256
import json

from game.economy.route_establishment import route_fee_minor, post_route_establishment
from game.utils.geo_distance import distance_km
from game.world_state.route_establishment import activate_paid_pair, record_route_payment, close_paid_pair
from game.world_state.validation import validate_world


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,
                             allow_nan=False).encode('ascii')).hexdigest()


def fingerprint(envelope):
    return digest({k:v for k,v in envelope.items() if k != 'ui_state'})


def validate(envelope):
    result = validate_world(envelope)
    if not result.is_valid: raise ValueError(result.errors[0].message)
    if envelope['simulation'].get('operational_authority') != 'QUARTERLY_BACKEND_V1':
        raise ValueError('paid route commands require a quarterly career')


@dataclass(frozen=True)
class RouteQuote:
    action: str
    airline_id: str
    hub_airport_id: str
    airport_ids: tuple[str,str]
    market_ids: tuple[str,str]
    distance_m: int
    domestic: bool
    active_pair_count: int
    amount_minor: int
    cash_after_minor: int
    world_fingerprint: str
    command_id: str


def quote_route(envelope, *, airline_id, hub_airport_id, origin_airport_id,
                destination_airport_id, action='ESTABLISH', command_id=None):
    validate(envelope)
    world = envelope['world_state']; ports = world['airports']
    if type(airline_id) is not str or airline_id not in world['airlines']:
        raise ValueError('unknown airline')
    airline = world['airlines'][airline_id]
    if (type(hub_airport_id) is not str or hub_airport_id not in airline['base_airport_ids']
            or hub_airport_id not in ports):
        raise ValueError('select an owned Operating Base or Hub')
    if (type(origin_airport_id) is not str or type(destination_airport_id) is not str
            or origin_airport_id not in ports or destination_airport_id not in ports
            or origin_airport_id == destination_airport_id):
        raise ValueError('select two distinct authoritative airports')
    if action not in ('ESTABLISH','CLOSE'):
        raise ValueError('unknown route command')
    a,b = sorted((origin_airport_id,destination_airport_id))
    market_ids = []
    for origin,destination in ((a,b),(b,a)):
        matches = [k for k,m in world['directional_markets'].items()
                   if (m['origin_airport_id'],m['destination_airport_id']) == (origin,destination)]
        if len(matches) != 1: raise ValueError('both directional markets must exist')
        market_ids.append(matches[0])
    connections = [c for c in world['connections'].values()
                   if c['airline_id']==airline_id and c['market_id'] in market_ids]
    established = next((c for c in connections if 'route_establishment' in c),None)
    if established and established['route_establishment']['hub_airport_id'] != hub_airport_id:
        raise ValueError('use the original route attribution base')
    active = any(c['status']=='ACTIVE' for c in connections)
    if action == 'ESTABLISH':
        if active: raise ValueError('airport pair is already active')
        if connections and not established: raise ValueError('existing compatibility connections cannot be rewritten')
        date = envelope['simulation']['time_utc'][:10]
        from game.demand.model4 import _airport_available
        if not all(_airport_available(ports[k],date) for k in (a,b)):
            raise ValueError('airport pair is not eligible for passenger service now')
        # PH has no country-access purchase authority. Never infer foreign rights.
        starting_country = ports[airline['base_airport_ids'][0]]['country_id']
        if any(ports[k]['country_id'] != starting_country for k in (a,b)):
            raise ValueError('foreign country access is required and is not implemented')
    else:
        if not established or not active: raise ValueError('select an active paid airport pair')
        ids = {c['connection_id'] for c in connections}
        now = envelope['simulation']['time_utc']
        from game.utils.quarters import parse_quarter_id
        from game.world_state.timestamps import parse_canonical_utc
        for plan in world['weekly_plans'].values():
            rev = plan['revisions'][str(plan['current_revision'])]
            if (any(s['connection_id'] in ids for s in rev['slots'])
                    and parse_quarter_id(plan['quarter_id']).end_exclusive_utc > parse_canonical_utc(now)):
                raise ValueError('remove draft service and resolve published commitments before closure')
        if any(f['airline_id'] == airline_id and f.get('market_id') in market_ids and f['status'] in ('PLANNED','LOCKED')
               for f in world['dated_flights'].values()):
            raise ValueError('resolve operational commitments before closure')
    domestic = ports[a]['country_id'] == ports[b]['country_id']
    numerator,denominator = distance_km(ports[a],ports[b]).as_integer_ratio()
    distance_m = numerator * 1000 // denominator
    count = sum(c['status']=='ACTIVE' and c.get('route_establishment',{}).get('hub_airport_id')==hub_airport_id
                for c in world['connections'].values() if c['airline_id']==airline_id)
    amount = route_fee_minor(distance_m,domestic,count) if action=='ESTABLISH' else 0
    accounts = {world['financial_accounts'][k]['code']:world['financial_accounts'][k]
                for k in airline['financial_account_ids']}
    if airline['base_currency'] != 'USD': raise ValueError('route establishment requires USD accounting')
    fp = fingerprint(envelope)
    if command_id is None: command_id = 'route-'+digest([fp,airline_id,hub_airport_id,a,b,action])
    if (type(command_id) is not str or not command_id or len(command_id)>128
            or command_id.strip()!=command_id or any(ord(c)<32 for c in command_id)):
        raise ValueError('invalid command identifier')
    return RouteQuote(action,airline_id,hub_airport_id,(a,b),tuple(market_ids),distance_m,
                      domestic,count,amount,accounts['cash']['balance_minor']-amount,fp,command_id)


def apply_route(envelope, quote):
    validate(envelope)
    if type(quote) is not RouteQuote: raise ValueError('invalid route quote')
    request = digest(asdict(quote))
    for transaction in envelope['world_state']['transactions'].values():
        if transaction.get('source_type')=='ROUTE_ESTABLISHMENT' and transaction['command_id']==quote.command_id:
            if transaction['request_fingerprint'] != request: raise ValueError('route command identifier already used')
            return transaction['source_id']
    expected = quote_route(envelope,airline_id=quote.airline_id,hub_airport_id=quote.hub_airport_id,
        origin_airport_id=quote.airport_ids[0],destination_airport_id=quote.airport_ids[1],
        action=quote.action,command_id=quote.command_id)
    if expected != quote: raise ValueError('stale or altered route quote; review again')
    if quote.action == 'ESTABLISH' and quote.cash_after_minor < 0:
        raise ValueError('insufficient cash')
    candidate = deepcopy(envelope)
    if quote.action == 'ESTABLISH':
        cid,_ = activate_paid_pair(candidate,quote.airline_id,quote.hub_airport_id,quote.market_ids)
        tid = post_route_establishment(candidate,airline_id=quote.airline_id,source_id=cid,
            command_id=quote.command_id,request_fingerprint=request,hub_airport_id=quote.hub_airport_id,
            distance_m=quote.distance_m,base_fee_minor=2_500_000 if quote.domestic else 7_500_000,
            active_pair_count=quote.active_pair_count,amount_minor=quote.amount_minor)
        record_route_payment(candidate,cid,tid)
    else:
        cid = next(c['connection_id'] for c in candidate['world_state']['connections'].values()
                   if c['airline_id']==quote.airline_id and c['market_id']==quote.market_ids[0])
        close_paid_pair(candidate,cid)
    validate(candidate)
    detached = deepcopy(candidate)
    validate(detached)
    if fingerprint(envelope) != quote.world_fingerprint:
        raise ValueError('source changed during route transaction')
    envelope.clear(); envelope.update(detached)
    return cid
