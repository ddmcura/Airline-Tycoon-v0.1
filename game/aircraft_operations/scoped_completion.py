"""Closed-owner quarterly passenger Completion only; full gates remain."""
from copy import deepcopy

from . import fulfilment
from game.simulation import kernel
from game.simulation.candidate_ownership import CandidateOwnership, ReadOnlyDict, ReadOnlyList
from game.simulation.owned_event import _prepare_successor
from game.world_state import validate_world
from game.world_state.validation import _plain_authority_tree
from game.world_state.quarterly_consumers import LINEAGE_FIELDS, valid_quarterly_lineage
from game.world_state.flight_transition_validation import completion_ownership

_HANDLER = fulfilment._completion_handler


def _fault(stage, capsule):
    """Private test instrumentation; not an application callback interface."""


def _snapshot(base, alive, counts):
    cache = {}
    def wrap(value):
        if not alive[0]:
            raise ValueError('scoped read capability expired')
        if value is None or type(value) in (str, bool, int, float):
            return value
        if type(value) is dict and value.keys() == LINEAGE_FIELDS:
            counts['lineage_read_copies'] += 1
            return deepcopy(value)
        if type(value) not in (dict, list):
            raise ValueError('unsupported protected scoped read')
        marker = id(value)
        if marker not in cache:
            cache[marker] = ReadOnlyDict(value, _wrap=wrap) if type(value) is dict else ReadOnlyList(value, _wrap=wrap)
        return cache[marker]
    return wrap(base), cache


def _prepare_completion(owner, event_id, registry):
    base = owner._world
    event = base['world_state']['pending_events'].get(event_id)
    if (registry is not kernel.DEFAULT_EVENT_HANDLERS
            or registry.handler_for('STAGE1_FLIGHT_COMPLETION') is not _HANDLER
            or fulfilment._completion_handler is not _HANDLER
            or base['metadata']['save_schema_version'] != 9
            or base['simulation'].get('operational_authority') != 'QUARTERLY_BACKEND_V1'
            or event is None or event['event_type'] != 'STAGE1_FLIGHT_COMPLETION'):
        return None
    if not _plain_authority_tree(base):
        return None
    owner._counts['source_validations'] += 1
    if not validate_world(base).is_valid:
        # An intermediate equal-UTC state may only be admitted by the existing
        # through-request strict path. Do not introduce a new command boundary.
        return None
    heap = kernel.build_event_queue_index(base)
    if not heap or heap[0][3] != event_id:
        return None
    world = base['world_state']; flight = world['dated_flights'].get(event['owner_id'])
    operation = world['active_aircraft_operations'].get(event['owner_id'])
    if (not flight or not operation or not valid_quarterly_lineage(flight.get('quarterly_lineage'))
            or flight['service_type'] != 'PASSENGER' or flight['status'] != 'OPERATIONALLY_LOCKED'
            or flight['dated_flight_id'] in world['flight_results']
            or event['operation_revision'] != base['simulation']['operation_revisions'].get(event['owner_id'], 0)
            or operation['completion_event_id'] != event_id
            or operation['actual_aircraft_id'] != flight['planned_aircraft_id']):
        return None
    aircraft = world['aircraft'].get(operation['actual_aircraft_id'])
    if (not aircraft or aircraft['status'] != 'IN_FLIGHT' or aircraft['current_airport_id'] is not None
            or aircraft['airline_id'] != flight['airline_id']):
        return None
    footprint = completion_ownership(base, event_id)
    accounts = fulfilment._account_ids(world, flight['airline_id'])
    footprint['financial_accounts'] = {accounts[code] for code in
        ('cash','unflown_tickets','passenger_revenue','operating_expenses')}
    owner._counts['attempts'] += 1
    owner._counts['copied_existing_records'] += sum(key in world[name] for name, keys in footprint.items() for key in keys)
    ownership = CandidateOwnership(base, _validated=True)
    ownership._snapshot, reads = _snapshot(base, ownership._alive, owner._counts)
    capsule = ownership.begin(footprint, local=True)
    try:
        _fault('before_handler', capsule)
        before = kernel._event_contract_witness(base, ownership=capsule)
        outcome, failure, generated = kernel._apply_handler_candidate(before, capsule.envelope, event_id, _HANDLER)
        if failure:
            raise ValueError('scoped handler failure: ' + failure.code + ': ' + failure.message)
        if outcome != 'COMPLETED' or generated:
            raise ValueError('unsupported scoped Completion lifecycle')
        _fault('after_handler', capsule)
        return _prepare_successor(owner, capsule.checked_outputs(), footprint, event_id)
    finally:
        ownership.close()
        reads.clear()
