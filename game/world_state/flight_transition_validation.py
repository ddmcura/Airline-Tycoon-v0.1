"""Exact Stage 3C flight transitions from a fully valid predecessor.

Runtime witnesses only. No full-world gate, authoritative index or new formulas.
Exact protected bytes and manifest/kernel witnesses still grow with history.
"""
from copy import deepcopy
import json
from .ids import format_entity_id
from .flight_proof_witness import protected_bytes, mutable_alias_error as _container_alias_error
from .serialization import json_compatibility_error
from .fulfilment_validation import _valid_flight_event
from .schema import (FLIGHT_DEPARTURE_EVENT_TYPE as DEPARTURE,
    FLIGHT_COMPLETION_EVENT_TYPE as COMPLETION, FLIGHT_DEPARTURE_EVENT_CONTRACT,
    FLIGHT_COMPLETION_EVENT_CONTRACT, FLIGHT_EVENT_PRIORITY)

DEPARTURE_VERSION = 'ph-flight-departure-shared-v1'
COMPLETION_VERSION = 'ph-flight-completion-shared-v1'


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _exact(actual, expected, label):
    if _encoded(actual) != _encoded(expected):
        raise ValueError(f'flight transition changed {label} incorrectly')


def supports_departure(envelope, event):
    try:
        world=envelope['world_state']; flight=world['dated_flights'][event['owner_id']]
        aircraft=world['aircraft'][flight['planned_aircraft_id']]
        return (envelope['metadata']['save_schema_version']==7
            and flight['status']=='PLANNED'
            and flight['dated_flight_id'] not in world['active_aircraft_operations']
            and flight['dated_flight_id'] not in world['flight_results']
            and aircraft['status']=='PARKED' and aircraft['current_airport_id']==flight['origin_airport_id']
            and aircraft['airline_id']==flight['airline_id']
            and _valid_flight_event(event,flight,event_type=DEPARTURE,
                contract=FLIGHT_DEPARTURE_EVENT_CONTRACT,due_at_utc=flight['scheduled_off_block_utc'],
                operation_revision=flight['operation_revision'],status='PENDING'))
    except (KeyError,TypeError,ValueError): return False


def _protected_digest(envelope, excluded):
    # Historical private name; now returns exact typed bytes, not a hash.
    # These shallow views must not erase a noncanonical root/table type.
    if type(envelope) is not dict or any(type(envelope[key]) is not dict
            for key in ('world_state','deterministic_state')):
        raise ValueError('flight introduced non-JSON authority: non-plain root')
    world=dict(envelope['world_state'])
    for name,keys in excluded.items():
        if type(world[name]) is not dict:
            raise ValueError('flight introduced non-JSON authority: non-plain collection')
        world[name]={key:row for key,row in world[name].items() if key not in keys}
    protected={**envelope,'world_state':world}
    protected.pop('simulation')
    deterministic=dict(protected['deterministic_state']); deterministic.pop('id_allocator')
    protected['deterministic_state']=deterministic
    return protected_bytes(protected)


def _capture(envelope,event_id,kernel_before,completion=False):
    from game.aircraft_operations import fulfilment
    world=envelope['world_state']; event=deepcopy(world['pending_events'][event_id])
    flight=deepcopy(world['dated_flights'][event['owner_id']]); flight_id=flight['dated_flight_id']
    operation=deepcopy(world['active_aircraft_operations'].get(flight_id))
    aircraft_id=operation['actual_aircraft_id'] if completion else flight['planned_aircraft_id']
    aircraft=deepcopy(world['aircraft'][aircraft_id])
    manifest=fulfilment._build_confirmed_carriage_manifest(envelope,flight_id)
    if not manifest.succeeded: raise ValueError(manifest.issues[0].message)
    allocator=deepcopy(envelope['deterministic_state']['id_allocator'])
    excluded={'dated_flights':{flight_id},'aircraft':{aircraft_id},
        'active_aircraft_operations':{flight_id},'pending_events':{event_id},'event_history':{event_id}}
    witness=dict(event=event,flight=flight,aircraft=aircraft,operation=operation,
        manifest=manifest,allocator=allocator,kernel=kernel_before,excluded=excluded)
    return witness


def capture_departure(envelope,event_id,kernel_before):
    from game.aircraft_operations.fulfilment import departure_operation
    if not supports_departure(envelope,envelope['world_state']['pending_events'][event_id]):
        raise ValueError('departure outside certified inputs')
    before=_capture(envelope,event_id,kernel_before)
    flight=before['flight']; aircraft=before['aircraft']; allocator=before['allocator']
    successor_id=format_entity_id('event',allocator['next_by_type']['event'])
    before['excluded']['pending_events'].add(successor_id)
    next_flight={**flight,'status':'OPERATIONALLY_LOCKED','operation_revision':flight['operation_revision']+1}
    operation=departure_operation(envelope,next_flight,aircraft['aircraft_id'],before['manifest'],event_id)
    operation['completion_event_id']=successor_id
    before['expected_operation']=operation
    before['protected']=_protected_digest(envelope,before['excluded'])
    return before


def _kernel_transition(before,candidate,event_id,generated,successor=None):
    event=before['event']; flight=before['flight']; flight_id=flight['dated_flight_id']
    simulation=deepcopy(before['kernel']['simulation'])
    simulation['time_utc']=event['due_at_utc']
    simulation['operation_revisions'][flight_id]=flight['operation_revision']+1
    allocator=deepcopy(before['allocator'])
    pending=set(before['kernel']['world_state']['pending_events'])-{event_id}
    if successor is not None:
        allocator['next_by_type']['event']+=1; simulation['event_order_cursor']+=1
        pending.add(successor['event_id'])
        _exact(candidate['world_state']['pending_events'][successor['event_id']],successor,'completion event')
        _exact(list(generated),[successor['event_id']],'generated IDs')
    else:
        allocator['next_by_type']['transaction']+=1
        _exact(list(generated),[],'generated IDs')
    _exact(candidate['simulation'],simulation,'simulation/revisions')
    _exact(candidate['deterministic_state']['id_allocator'],allocator,'all allocator cursors')
    world=candidate['world_state']
    if set(world['pending_events']) != pending: raise ValueError('flight pending topology changed')
    if set(world['event_history']) != set(before['kernel']['world_state']['event_history'])|{event_id}:
        raise ValueError('flight history topology changed')
    _exact(world['event_history'][event_id],{**event,'status':'COMPLETED','resolved_at_utc':event['due_at_utc']},'event lifecycle')
    # Unchanged records inherit entry JSON compatibility ONLY after exact typed
    # protected comparison. Check every excluded/new/changed record explicitly.
    changed=[candidate['simulation'],candidate['deterministic_state']['id_allocator']]
    for name,keys in before['excluded'].items():
        changed.extend(world[name][key] for key in keys if key in world[name])
    error=json_compatibility_error(changed)
    if error is not None:
        raise ValueError(f'flight introduced non-JSON authority: {error}')
    # Value bytes cannot detect mutable aliases; retain the whole-graph predicate.
    if _container_alias_error(candidate) is not None:
        raise ValueError('flight introduced an authoritative mutable-container alias')
    if _protected_digest(candidate,before['excluded']) != before['protected']:
        # Failure-only canonical diagnostic preserves useful non-JSON errors.
        error=json_compatibility_error(candidate)
        if error is not None:
            raise ValueError(f'flight introduced non-JSON authority: {error}')
        raise ValueError('flight changed unrelated protected structure')


def validate_departure(before,candidate,event_id,generated):
    world=candidate['world_state']; flight=before['flight']; aircraft=before['aircraft']
    flight_id=flight['dated_flight_id']; operation=before['expected_operation']
    _exact(world['dated_flights'][flight_id],{**flight,'status':'OPERATIONALLY_LOCKED',
        'operation_revision':flight['operation_revision']+1},'departure flight')
    _exact(world['aircraft'][aircraft['aircraft_id']],{**aircraft,'status':'IN_FLIGHT','current_airport_id':None},'departure aircraft')
    _exact(world['active_aircraft_operations'][flight_id],operation,'frozen operation/manifest/maintenance')
    successor=dict(event_id=operation['completion_event_id'],event_type=COMPLETION,
        due_at_utc=flight['scheduled_in_block_utc'],owner_type='dated_flight',owner_id=flight_id,
        operation_revision=flight['operation_revision']+1,
        order_key=[FLIGHT_EVENT_PRIORITY,before['kernel']['simulation']['event_order_cursor']],
        payload=dict(contract=FLIGHT_COMPLETION_EVENT_CONTRACT,dated_flight_id=flight_id,
            schedule_id=flight['schedule_id'],schedule_revision=flight['schedule_revision'],occurrence_key=flight['occurrence_key']),status='PENDING')
    _kernel_transition(before,candidate,event_id,generated,successor)


def departure_execution_contract(handler):
    from game.aircraft_operations.fulfilment import _departure_handler
    from game.simulation.execution_contracts import ExecutionMode,HandlerExecutionContract
    if handler is not _departure_handler: raise ValueError('exact built-in departure required')
    return HandlerExecutionContract(handler,ExecutionMode.SHARED,DEPARTURE_VERSION,
        'Exact Departure before/after proof; Flight Shared Certification.md',True,(7,),
        capture_transition=capture_departure,validate_transition=validate_departure,supports_input=supports_departure)


def supports_completion(envelope,event):
    try:
        world=envelope['world_state']; flight=world['dated_flights'][event['owner_id']]
        operation=world['active_aircraft_operations'][flight['dated_flight_id']]
        aircraft=world['aircraft'][operation['actual_aircraft_id']]
        # Conservative chronology guard: this result must become the latest one.
        latest=(flight['scheduled_in_block_utc'],flight['dated_flight_id'])
        return (envelope['metadata']['save_schema_version']==7
            and flight['status']=='OPERATIONALLY_LOCKED'
            and flight['dated_flight_id'] not in world['flight_results']
            and aircraft['status']=='IN_FLIGHT' and aircraft['current_airport_id'] is None
            and aircraft['airline_id']==flight['airline_id']
            and operation['completion_event_id']==event['event_id']
            and _valid_flight_event(event,flight,event_type=COMPLETION,
                contract=FLIGHT_COMPLETION_EVENT_CONTRACT,due_at_utc=flight['scheduled_in_block_utc'],
                operation_revision=flight['operation_revision'],status='PENDING')
            and all((row['completed_at_utc'],key)<latest for key,row in world['flight_results'].items()
                if row['actual_aircraft_id']==aircraft['aircraft_id']))
    except (KeyError,TypeError,ValueError): return False


def capture_completion(envelope,event_id,kernel_before):
    from game.aircraft_operations.fulfilment import completion_cost,settlement_records,_account_ids
    if not supports_completion(envelope,envelope['world_state']['pending_events'][event_id]):
        raise ValueError('completion outside certified inputs')
    before=_capture(envelope,event_id,kernel_before,completion=True)
    world=envelope['world_state']; flight=before['flight']; operation=before['operation']
    flight_id=flight['dated_flight_id']; airline_id=flight['airline_id']
    frozen=before['manifest'].as_dict()
    for key in ('source_booking_ids','paid_booking_ids','zero_fare_booking_ids',
                'source_ticket_sale_transaction_ids','booking_witnesses','inventory_witnesses'):
        _exact(operation[key],frozen[key],'predecessor frozen manifest')
    before['airline']=deepcopy(world['airlines'][airline_id])
    before['accounts']={key:deepcopy(world['financial_accounts'][key])
        for key in before['airline']['financial_account_ids']}
    account_ids=_account_ids(world,airline_id)
    if world['financial_accounts'][account_ids['unflown_tickets']]['balance_minor'] < before['manifest'].recognized_revenue_minor:
        raise ValueError('insufficient unflown-ticket liability')
    transaction_id=format_entity_id('transaction',before['allocator']['next_by_type']['transaction'])
    if transaction_id in world['transactions']: raise ValueError('settlement ID collision')
    cost=completion_cost(envelope,flight,operation)
    transaction,result=settlement_records(envelope,flight,operation,before['manifest'],transaction_id,cost)
    if sum(entry['amount_minor'] for entry in transaction['entries']): raise ValueError('unbalanced settlement')
    before.update(expected_transaction=transaction,expected_result=result,cost=cost)
    before['excluded'].update(airlines={airline_id},financial_accounts=set(before['accounts']),
        transactions={transaction_id},flight_results={flight_id})
    before['protected']=_protected_digest(envelope,before['excluded'])
    return before


def validate_completion(before,candidate,event_id,generated):
    world=candidate['world_state']; flight=before['flight']; flight_id=flight['dated_flight_id']
    aircraft=deepcopy(before['aircraft']); airline=before['airline']
    _exact(world['dated_flights'][flight_id],{**flight,'status':'COMPLETED',
        'operation_revision':flight['operation_revision']+1},'completed flight')
    if flight_id in world['active_aircraft_operations']: raise ValueError('completed operation retained')
    aircraft['current_airport_id']=flight['destination_airport_id']; aircraft['status']='PARKED'
    if type(aircraft.get('lifecycle')) is dict:
        aircraft['lifecycle']['lifetime_flight_seconds']+=before['cost']['block_seconds']
        aircraft['lifecycle']['lifetime_cycles']+=1
    _exact(world['aircraft'][aircraft['aircraft_id']],aircraft,'completed aircraft/lifetime counters')
    _exact(world['airlines'][airline['airline_id']],{**airline,'finance_revision':airline['finance_revision']+1},'finance revision')
    expected=deepcopy(before['accounts']); transaction=before['expected_transaction']
    # Existing journal's debit signs: unflown/revenue are credit-normal accounts.
    for entry in transaction['entries']:
        row=expected[entry['account_id']]
        row['balance_minor']+=entry['amount_minor'] * (-1 if row['code'] in ('unflown_tickets','passenger_revenue') else 1)
    _exact({key:world['financial_accounts'][key] for key in expected},expected,'settlement accounts/liability')
    _exact(world['transactions'][transaction['transaction_id']],transaction,'settlement journal/lineage')
    _exact(world['flight_results'][flight_id],before['expected_result'],'result/manifest/maintenance')
    _kernel_transition(before,candidate,event_id,generated)


def completion_execution_contract(handler):
    from game.aircraft_operations.fulfilment import _completion_handler
    from game.simulation.execution_contracts import ExecutionMode,HandlerExecutionContract
    if handler is not _completion_handler: raise ValueError('exact built-in completion required')
    return HandlerExecutionContract(handler,ExecutionMode.SHARED,COMPLETION_VERSION,
        'Exact Completion before/after proof; Flight Shared Certification.md',True,(7,),
        capture_transition=capture_completion,validate_transition=validate_completion,supports_input=supports_completion)


def is_flight_certificate(contract):
    from game.aircraft_operations.fulfilment import _departure_handler,_completion_handler
    if contract.handler is _departure_handler: expected=departure_execution_contract(_departure_handler)
    elif contract.handler is _completion_handler: expected=completion_execution_contract(_completion_handler)
    else: return False
    return (type(contract) is type(expected) and contract.handler is expected.handler
        and contract.capture_transition is expected.capture_transition
        and contract.validate_transition is expected.validate_transition
        and contract.supports_input is expected.supports_input and contract==expected)
