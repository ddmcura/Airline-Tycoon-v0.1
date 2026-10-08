"""Reconstructible Schema 9 number protection; no stored pool or maintained index.

Callers supply quarterly authority, not legacy flights/history. Allocation scopes
record processing to one airline; trust-boundary validation can cover all owners.
"""
import re

from game.utils.quarters import parse_quarter_id
from .ids import parse_entity_id
from .timestamps import parse_canonical_utc


def protected_number_holders(envelope, *, airline_id=None):
    """Return (airline, suffix) -> frozen protected service IDs; fail closed."""
    world = envelope['world_state']
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    if airline_id is not None and airline_id not in world['airlines']:
        raise ValueError('unknown numbering airline')
    owners = world['service_numbering'] if airline_id is None else (airline_id,)
    for owner in owners:
        record = world['service_numbering'].get(owner)
        if (owner not in world['airlines'] or type(record) is not dict
                or set(record) != {'flight_number_prefix', 'next_number'}
                or type(record['flight_number_prefix']) is not str
                or re.fullmatch(r'[A-Z]{2,8}', record['flight_number_prefix']) is None
                or type(record['next_number']) is not int or record['next_number'] < 1):
            raise ValueError('invalid airline number authority')
    protected = set()
    for sid, service in world['services'].items():
        if airline_id is not None and service['airline_id'] != airline_id:
            continue
        owner = service['airline_id']
        if (sid != service['service_id'] or parse_entity_id(sid, 'service') is None
                or owner not in world['service_numbering']
                or type(service['flight_number_number']) is not int
                or not 0 < service['flight_number_number'] < world['service_numbering'][owner]['next_number']):
            raise ValueError('invalid service number authority')
        stamp = service['retired_at_utc']
        if stamp is None:
            protected.add(sid)
        elif parse_canonical_utc(stamp) > now:
            raise ValueError('retirement cannot be in the future')
    for plan in world['weekly_plans'].values():
        owner = plan['airline_id']
        if airline_id is not None and owner != airline_id:
            continue
        quarter = parse_quarter_id(plan['quarter_id'])
        row = plan['revisions'][str(plan['current_revision'])]
        stamp = row['published_at_utc']
        if stamp is None:
            continue
        if parse_canonical_utc(stamp) > min(now, quarter.start_utc):
            raise ValueError('inconsistent plan publication commitment')
        # Historical published references retain identity, not live ownership.
        if now >= quarter.end_exclusive_utc:
            continue
        for slot in row['slots']:
            sid = slot['service_id']
            service = world['services'].get(sid)
            if service is None or service['airline_id'] != owner:
                raise ValueError('published service reference missing or cross-owner')
            protected.add(sid)
    holders = {}
    for sid in sorted(protected):
        service = world['services'][sid]
        key = (service['airline_id'], service['flight_number_number'])
        holders.setdefault(key, set()).add(sid)
        if len(holders[key]) > 1:
            raise ValueError('duplicate protected flight number')
    return {key: frozenset(value) for key, value in sorted(holders.items())}


def eligible_retired_numbers(envelope, airline_id):
    """Sorted deduplicated suffixes, reconstructible without mutating authority."""
    holders = protected_number_holders(envelope, airline_id=airline_id)
    return tuple(sorted({s['flight_number_number']
        for s in envelope['world_state']['services'].values()
        if s['airline_id'] == airline_id and s['retired_at_utc'] is not None
        and (airline_id, s['flight_number_number']) not in holders}))
