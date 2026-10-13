"""B3B diagnostic only: exact one-use whole-value Completion witness.

Not a local production certificate: capture validates and copies the full source;
verification scans both worlds and aliases. Pure domain constructors are shared
with the handler, so independent formula coverage remains a named limitation.
"""
from copy import deepcopy

import game.world_state
from game.world_state import validate_world
from game.world_state.flight_proof_witness import protected_bytes, mutable_alias_error
from game.world_state.ids import format_entity_id
from game.aircraft_operations import fulfilment
from game.simulation import kernel


def record_count(world):
    """Top-level keyed records; nested containers are additional traversal work."""
    return sum(len(table) for table in world['world_state'].values()
               if type(table) is dict)


class CompletionCertificate:
    def __init__(self, source, event_id):
        validation = validate_world(source)
        if not validation.is_valid:
            raise ValueError(str(validation.errors[0]))
        if source['metadata']['save_schema_version'] != 9:
            raise ValueError('Schema 9 required')
        world = source['world_state']
        event = world['pending_events'][event_id]
        flight = world['dated_flights'][event['owner_id']]
        operation = world['active_aircraft_operations'][flight['dated_flight_id']]
        if ('quarterly_lineage' not in flight or
                event['event_type'] != 'STAGE1_FLIGHT_COMPLETION' or
                min(world['pending_events'].values(), key=kernel._event_key)['event_id'] != event_id or
                flight['status'] != 'OPERATIONALLY_LOCKED' or
                operation['completion_event_id'] != event_id or
                event['due_at_utc'] != flight['scheduled_in_block_utc']):
            raise ValueError('not the next eligible quarterly Completion')
        self.source = source  # Identity is an additional lifetime fence, not validity.
        self.source_bytes = protected_bytes(source)
        self.event_id = event_id
        self.used = False
        self.flight_id = flight['dated_flight_id']
        self.aircraft_id = operation['actual_aircraft_id']
        self.booking_ids = tuple(operation['source_booking_ids'])
        self.itinerary_ids = tuple(world['bookings'][key]['itinerary_id']
                                   for key in self.booking_ids)
        self.records_inspected = record_count(source)

        expected = deepcopy(source)
        expected['simulation']['time_utc'] = event['due_at_utc']
        state = expected['world_state']
        manifest = fulfilment._build_confirmed_carriage_manifest(expected, self.flight_id)
        if not manifest.succeeded:
            raise ValueError(str(manifest.issues[0]))
        for key in ('source_booking_ids', 'paid_booking_ids', 'zero_fare_booking_ids',
                    'source_ticket_sale_transaction_ids', 'booking_witnesses', 'inventory_witnesses'):
            if protected_bytes(operation[key]) != protected_bytes(manifest.as_dict()[key]):
                raise ValueError('frozen manifest mismatch')
        cost = fulfilment.completion_cost(expected, flight, operation)
        allocator = expected['deterministic_state']['id_allocator']['next_by_type']
        transaction_id = format_entity_id('transaction', allocator['transaction'])
        self.transaction_id = transaction_id
        transaction, result = fulfilment.settlement_records(
            expected, flight, operation, manifest, transaction_id, cost)
        accounts = fulfilment._account_ids(state, flight['airline_id'])
        revenue = manifest.recognized_revenue_minor
        if state['financial_accounts'][accounts['unflown_tickets']]['balance_minor'] < revenue:
            raise ValueError('insufficient unflown-ticket liability')
        # Own transition equations, without executing the handler or strict kernel.
        for code, delta in (('unflown_tickets', -revenue), ('passenger_revenue', revenue),
                            ('operating_expenses', cost['operating_cost_minor']),
                            ('cash', -cost['operating_cost_minor'])):
            state['financial_accounts'][accounts[code]]['balance_minor'] += delta
        state['transactions'][transaction_id] = transaction
        allocator['transaction'] += 1
        state['airlines'][flight['airline_id']]['finance_revision'] += 1
        state['dated_flights'][self.flight_id]['status'] = 'COMPLETED'
        state['dated_flights'][self.flight_id]['operation_revision'] += 1
        expected['simulation']['operation_revisions'][self.flight_id] += 1
        aircraft = state['aircraft'][self.aircraft_id]
        aircraft['status'] = 'PARKED'
        aircraft['current_airport_id'] = flight['destination_airport_id']
        if type(aircraft.get('lifecycle')) is dict:
            aircraft['lifecycle']['lifetime_cycles'] += 1
            aircraft['lifecycle']['lifetime_flight_seconds'] += cost['block_seconds']
        state['flight_results'][self.flight_id] = result
        del state['active_aircraft_operations'][self.flight_id]
        del state['pending_events'][event_id]
        state['event_history'][event_id] = {
            **deepcopy(event), 'status': 'COMPLETED', 'resolved_at_utc': event['due_at_utc']}
        self.expected_bytes = protected_bytes(expected)

    def verify(self, source, candidate, event_id, generated=()):
        if self.used:
            raise ValueError('certificate already consumed')
        self.used = True  # A failed attempt expires too; retry requires fresh binding.
        if source is not self.source or event_id != self.event_id:
            raise ValueError('different source or event')
        if protected_bytes(source) != self.source_bytes:
            raise ValueError('source changed after capture')
        if generated != ():
            raise ValueError('Completion must generate no events')
        if mutable_alias_error([source, candidate]) is not None:
            raise ValueError('mutable source/candidate or cross-world alias')
        if protected_bytes(candidate) != self.expected_bytes:
            raise ValueError('candidate differs from exact Completion transition')
        return True
