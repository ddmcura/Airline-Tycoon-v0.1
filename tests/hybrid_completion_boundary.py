"""B3D rejected local admission experiment; no production registration.

Selected facts are inspected, NOT certified. Plain mutable WorldState cannot
inherit whole-source validity from this frame. The shell therefore never commits
local writes: it either refuses a callback/handler outside scope or uses the
unchanged strict command. That fallback cost must be measured in full.
"""
from copy import deepcopy
from dataclasses import dataclass

import game.world_state
from game.simulation import kernel
from game.aircraft_operations.fulfilment import _completion_handler
from game.world_state.flight_proof_witness import protected_bytes


@dataclass(frozen=True)
class BoundaryAttempt:
    processing_result: object
    local_admitted: bool
    reason: str
    selected_records: int


class UnsupportedBoundary(ValueError):
    pass


def selected_inputs(envelope):
    """Direct selected lookups plus canonical queue minimum, not a full scan.

    Checkpoint/plan rows can themselves contain large nested data. This is not
    a constant-sized dependency closure or an exclusive source ownership grant.
    """
    if type(envelope) is not dict or type(envelope.get('world_state')) is not dict:
        raise ValueError('plain envelope required')
    world = envelope['world_state']
    if type(world.get('pending_events')) is not dict:
        raise ValueError('plain pending table required')
    # These selected/queue scans are explicitly additional work. Refuse custom
    # reduction/deepcopy objects before touching their protocol methods.
    protected_bytes(world['pending_events'])
    def row(name, key):
        if type(world.get(name)) is not dict:
            raise ValueError('plain selected table required')
        value = world[name][key]
        if type(value) is not dict:
            raise ValueError('plain selected row required')
        protected_bytes(value)
        return value
    event = min(world['pending_events'].values(), key=kernel._event_key)
    if event['event_type'] != 'STAGE1_FLIGHT_COMPLETION':
        raise UnsupportedBoundary('experiment requires next Completion')
    flight = row('dated_flights', event['owner_id'])
    if 'quarterly_lineage' not in flight:
        raise UnsupportedBoundary('quarterly Completion only')
    operation = row('active_aircraft_operations', flight['dated_flight_id'])
    airline = row('airlines', flight['airline_id'])
    ids = {
        'dated_flights': [flight['dated_flight_id']],
        'active_aircraft_operations': [flight['dated_flight_id']],
        'aircraft': [operation['actual_aircraft_id']],
        'airlines': [flight['airline_id']],
        'pending_events': [event['event_id']],
        'event_history': [operation['departure_event_id']],
        'financial_accounts': airline['financial_account_ids'],
        'bookings': operation['source_booking_ids'],
        'itineraries': [row('bookings', key)['itinerary_id']
                        for key in operation['source_booking_ids']],
        'transactions': operation['source_ticket_sale_transaction_ids'],
        'airports': [flight['origin_airport_id'], flight['destination_airport_id']],
        'connections': [flight['connection_id']],
        'directional_markets': [operation['market_id']],
        'weekly_plans': [flight['quarterly_lineage']['weekly_plan_id']],
        'services': [flight['quarterly_lineage']['service_id']],
    }
    frame = {name: {key: row(name, key) for key in sorted(set(keys))}
             for name, keys in ids.items()}
    checkpoint_ids = {row('bookings', key)['booking_checkpoint_id']
                      for key in operation['source_booking_ids']}
    if type(world.get('booking_state')) is not dict:
        raise ValueError('plain booking state required')
    if type(world['booking_state'].get('booking_checkpoints')) is not dict:
        raise ValueError('plain checkpoint table required')
    frame['booking_state'] = {
        'booking_revision': world['booking_state']['booking_revision'],
        'booking_checkpoints': {key: world['booking_state']['booking_checkpoints'][key]
                               for key in sorted(checkpoint_ids)},
    }
    sim = envelope.get('simulation')
    deterministic = envelope.get('deterministic_state')
    if (type(sim) is not dict or type(sim.get('configuration')) is not dict
            or type(sim.get('operation_revisions')) is not dict or type(deterministic) is not dict):
        raise ValueError('plain runtime source required')
    frame['simulation'] = {
        'time_utc': envelope['simulation']['time_utc'],
        'event_order_cursor': envelope['simulation']['event_order_cursor'],
        'operation_revisions': {flight['dated_flight_id']:
                               envelope['simulation']['operation_revisions'][flight['dated_flight_id']]},
        'configuration': {name: envelope['simulation']['configuration'][name]
                          for name in ('flight_fulfilment', 'maintenance')},
    }
    frame['deterministic_state'] = {'id_allocator': envelope['deterministic_state']['id_allocator']}
    # Only selected input data are copied, not the envelope. No raw reference is
    # returned. Full-world aliases and omitted manifest membership are unproved.
    protected_bytes(frame)
    return deepcopy(frame), sum(len(set(keys)) for keys in ids.values()) + len(checkpoint_ids)


def plausible_selected_facts(frame):
    """Independent necessary checks only; deliberately never a validity proof."""
    fields = {'weekly_plan_id', 'revision', 'service_id', 'slot_number',
              'operating_date', 'published_at_utc'}
    def lineage(value):
        return (type(value) is dict and set(value) == fields and
                all(type(value[key]) is int and value[key] >= 1
                    for key in ('revision', 'slot_number')) and
                all(type(value[key]) is str and bool(value[key])
                    for key in fields - {'revision', 'slot_number'}))
    flight = next(iter(frame['dated_flights'].values()))
    operation = next(iter(frame['active_aircraft_operations'].values()))
    event = next(iter(frame['pending_events'].values()))
    aircraft = next(iter(frame['aircraft'].values()))
    return (flight['status'] == 'OPERATIONALLY_LOCKED' and
            aircraft['status'] == 'IN_FLIGHT' and aircraft['current_airport_id'] is None and
            event['due_at_utc'] == flight['scheduled_in_block_utc'] and
            operation['completion_event_id'] == event['event_id'] and
            len(operation['source_booking_ids']) == len(set(operation['source_booking_ids'])) and
            lineage(flight['quarterly_lineage']) and
            all(lineage(row['quarterly_lineage']) for row in frame['itineraries'].values()))


def attempt_completion(envelope, *, registry=kernel.DEFAULT_EVENT_HANDLERS, callbacks=()):
    if (type(callbacks) is not tuple or len(callbacks) != 0
            or registry is not kernel.DEFAULT_EVENT_HANDLERS
            or registry.handler_for('STAGE1_FLIGHT_COMPLETION') is not _completion_handler):
        raise ValueError('B3D rejects providers/custom callbacks and non-built-in handlers')
    if envelope['simulation'].get('operational_authority') != 'QUARTERLY_BACKEND_V1':
        raise ValueError('B3D does not execute legacy careers')
    count = 0
    try:
        frame, count = selected_inputs(envelope)
        plausible_selected_facts(frame)
    except UnsupportedBoundary:
        raise
    except (KeyError, TypeError, ValueError):
        # Do not manufacture a new gameplay error or mask strict diagnostics.
        pass
    result = kernel.process_next_event(envelope, registry=registry)
    return BoundaryAttempt(result, False,
        'NO_GO: selected inputs do not prove unchanged source validity, alias freedom, '
        'complete manifest membership or UTC-dependent invariant closure', count)
