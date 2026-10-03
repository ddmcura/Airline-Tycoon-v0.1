"""Versioned exact payment proof (schema 6/7), from a valid predecessor.

No full-world validator or journal replay here. Protected fingerprints and journal
chronology scans still grow with retained history. See certification document.
"""
from copy import deepcopy
from hashlib import sha256
import json
from .ids import format_entity_id
from .timestamps import format_utc, parse_canonical_utc

VERSION = 'ph-aircraft-contract-payment-shared-v1'


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _exact(actual, expected, label):
    # Python equality alone accepts True == 1 and 1.0 == 1.
    if _encoded(actual) != _encoded(expected):
        raise ValueError(f'payment transition changed {label} incorrectly')


def supports_payment_transition(envelope, event):
    """Conservative applicability; unsupported valid histories stay strict."""
    from game.aircraft_market.step5 import _add_months, PAYMENT_EVENT, PAYMENT_PRIORITY
    try:
        world = envelope['world_state']
        row = world['aircraft_contracts'][event['owner_id']]
        installment = row['paid_installments'] + 1
        expected_due = format_utc(_add_months(parse_canonical_utc(row['started_at_utc']), installment))
        return (event['event_type'] == PAYMENT_EVENT
            and event['owner_type'] == 'aircraft_contract'
            and row['status'] == 'ACTIVE' and installment <= row['total_installments']
            and event['operation_revision'] == 0
            and envelope['simulation']['operation_revisions'][event['owner_id']] == 0
            and event['order_key'][0] == PAYMENT_PRIORITY
            and event['due_at_utc'] == row['next_payment_at_utc'] == expected_due
            and expected_due <= row['expires_at_utc']
            and _encoded(event['payload']) == _encoded({'contract': 'PH_AIRCRAFT_CONTRACT_PAYMENT_V1', 'installment': installment})
            and world['airlines'][row['airline_id']]['base_currency'] == 'USD'
            and all(tx['occurred_at_utc'] <= expected_due
                for tx in world['transactions'].values()
                if tx.get('source_id') == row['aircraft_contract_id']
                and tx.get('source_type') in {'AIRCRAFT_LEASE_PAYMENT', 'AIRCRAFT_LTO_PAYMENT'}))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _protected_digest(envelope, contract_id, airline_id, account_ids, transaction_id, event_id, successor_id):
    """Immutable before evidence, shallow views serialized immediately.

    Kernel witness covers event contracts; exact checks cover selected rows and
    allocator. Everything else, including old journals, is fingerprinted here.
    No authoritative mutation, full-world clone or escaped borrowed view.
    """
    world = dict(envelope['world_state'])
    for name, excluded in (('aircraft_contracts', {contract_id}), ('airlines', {airline_id}),
                           ('financial_accounts', account_ids), ('transactions', {transaction_id})):
        world[name] = {key: row for key, row in world[name].items() if key not in excluded}
    world['pending_events'] = {key: row for key, row in world['pending_events'].items()
                               if key not in {event_id, successor_id}}
    world['event_history'] = {key: row for key, row in world['event_history'].items() if key != event_id}
    protected = {**envelope, 'world_state': world}
    protected.pop('simulation')
    deterministic = dict(protected['deterministic_state'])
    deterministic.pop('id_allocator')
    protected['deterministic_state'] = deterministic
    return sha256(_encoded(protected).encode('utf-8')).digest()


def capture_payment_transition(candidate, event_id, kernel_before):
    from game.aircraft_market.step5 import payment_terms
    from game.economy.aircraft_market import normalize_market_entries, market_transaction_record
    event = deepcopy(candidate['world_state']['pending_events'][event_id])
    if not supports_payment_transition(candidate, event):
        raise ValueError('payment input is outside the certified contract')
    world = candidate['world_state']
    contract = deepcopy(world['aircraft_contracts'][event['owner_id']])
    airline = deepcopy(world['airlines'][contract['airline_id']])
    accounts = {key: deepcopy(world['financial_accounts'][key]) for key in airline['financial_account_ids']}
    allocator = deepcopy(candidate['deterministic_state']['id_allocator'])
    transaction_id = format_entity_id('transaction', allocator['next_by_type']['transaction'])
    if transaction_id in world['transactions']:
        raise ValueError('payment journal ID collision')
    terms = payment_terms(contract)
    entries = normalize_market_entries(world, contract['airline_id'], terms['entries'])
    transaction = market_transaction_record(transaction_id=transaction_id,
        airline_id=contract['airline_id'], occurred_at_utc=event['due_at_utc'],
        description=terms['description'], source_type=terms['source_type'],
        source_id=contract['aircraft_contract_id'], entries=entries)
    successor_id = (format_entity_id('event', allocator['next_by_type']['event'])
                    if terms['next_due'] is not None else None)
    return dict(event=event, contract=contract, airline=airline, accounts=accounts, successor_id=successor_id,
        allocator=allocator, terms=terms, transaction=transaction, kernel=kernel_before,
        protected=_protected_digest(candidate, event['owner_id'], contract['airline_id'],
                                    set(accounts), transaction_id, event_id, successor_id))


def validate_payment_transition(before, candidate, event_id, generated):
    """Prove actual transition before any later event can repair it."""
    from game.aircraft_market.step5 import PAYMENT_EVENT, PAYMENT_PRIORITY
    world = candidate['world_state']
    event, row, terms = before['event'], before['contract'], before['terms']
    contract_id, airline_id = event['owner_id'], row['airline_id']
    _exact(world['aircraft_contracts'][contract_id], {**row,
        'paid_installments': terms['installment'],
        'principal_paid_minor': row['principal_paid_minor'] + terms['principal'],
        'financing_paid_minor': row['financing_paid_minor'] + terms['financing'],
        'next_payment_at_utc': terms['next_due']}, 'contract/progress')
    _exact(world['airlines'][airline_id], {**before['airline'],
        'finance_revision': before['airline']['finance_revision'] + 1}, 'airline/revision')
    expected_accounts = deepcopy(before['accounts'])
    transaction = before['transaction']
    for entry in transaction['entries']:
        expected_accounts[entry['account_id']]['balance_minor'] += entry['amount_minor']
    _exact({key: world['financial_accounts'][key] for key in expected_accounts}, expected_accounts, 'accounts/balances')
    _exact(world['transactions'][transaction['transaction_id']], transaction, 'journal/lineage')
    allocator = deepcopy(before['allocator'])
    allocator['next_by_type']['transaction'] += 1
    simulation = deepcopy(before['kernel']['simulation'])
    simulation['time_utc'] = event['due_at_utc']
    pending = set(before['kernel']['world_state']['pending_events']) - {event_id}
    if terms['next_due'] is not None:
        successor_id = format_entity_id('event', allocator['next_by_type']['event'])
        successor = dict(event_id=successor_id, event_type=PAYMENT_EVENT,
            due_at_utc=terms['next_due'], owner_type='aircraft_contract', owner_id=contract_id,
            operation_revision=0, order_key=[PAYMENT_PRIORITY, simulation['event_order_cursor']],
            payload={'contract': 'PH_AIRCRAFT_CONTRACT_PAYMENT_V1', 'installment': terms['installment'] + 1}, status='PENDING')
        _exact(world['pending_events'][successor_id], successor, 'successor event')
        _exact(list(generated), [successor_id], 'generated IDs')
        pending.add(successor_id)
        allocator['next_by_type']['event'] += 1
        simulation['event_order_cursor'] += 1
    else:
        _exact(list(generated), [], 'final-payment generated IDs')
    _exact(candidate['deterministic_state']['id_allocator'], allocator, 'allocator cursors')
    _exact(candidate['simulation'], simulation, 'simulation/revisions/clock')
    if set(world['pending_events']) != pending:
        raise ValueError('payment pending-event topology changed')
    if set(world['event_history']) != set(before['kernel']['world_state']['event_history']) | {event_id}:
        raise ValueError('payment event history topology changed')
    _exact(world['event_history'][event_id], {**event, 'status': 'COMPLETED',
        'resolved_at_utc': event['due_at_utc']}, 'event lifecycle')
    if _protected_digest(candidate, contract_id, airline_id, set(before['accounts']),
                         transaction['transaction_id'], event_id, before['successor_id']) != before['protected']:
        raise ValueError('payment changed an unrelated protected structure')


def payment_execution_contract(handler):
    from game.aircraft_market.step5 import _payment_handler
    from game.simulation.execution_contracts import ExecutionMode, HandlerExecutionContract
    if handler is not _payment_handler:
        raise ValueError('only the exact built-in payment callable can be certified')
    return HandlerExecutionContract(handler, ExecutionMode.SHARED, VERSION,
        'Exact payment delta, protected dependencies and intermediate validity; '
        'Contract Payment Shared Certification.md', True, (6, 7),
        capture_transition=capture_payment_transition, validate_transition=validate_payment_transition,
        supports_input=supports_payment_transition)


def is_payment_certificate(contract):
    from game.aircraft_market.step5 import _payment_handler
    expected = payment_execution_contract(_payment_handler)
    return (type(contract) is type(expected)
            and contract.handler is _payment_handler
            and contract.capture_transition is capture_payment_transition
            and contract.validate_transition is validate_payment_transition
            and contract.supports_input is supports_payment_transition
            and contract == expected)
