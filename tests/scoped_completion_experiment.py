"""Phase 3B opt-in experiment. Never imported or registered by production.

One detached owner, disposable event capsules, full gates, atomic private-root
publication. This is NOT a quarterly transition certificate or a session API.
Normal Python API discipline is assumed; reflection/monkeypatching is not a sandbox.
"""
from copy import deepcopy
from dataclasses import dataclass

from game.aircraft_operations import fulfilment
from game.simulation import kernel
from game.simulation.candidate_ownership import CandidateOwnership, ReadOnlyDict, ReadOnlyList
from game.world_state.quarterly_consumers import LINEAGE_FIELDS
from game.world_state.validation import validate_world, _plain_authority_tree
from game.world_state.serialization import _clone_runtime_world
from game.world_state.flight_transition_validation import completion_ownership


_HANDLER = fulfilment._completion_handler


def _quarterly_snapshot(base, alive, counts):
    """Exact lineage validators require plain dicts, so return detached scalar
    lineage projections. All other protected containers remain revocable views.
    These extra read copies are counted; no type predicate is weakened.
    """
    cache = {}
    def wrap(value):
        if not alive[0]:
            raise ValueError('ownership read capability expired')
        if value is None or type(value) in (str, bool, int, float):
            return value
        if type(value) is dict and value.keys() == LINEAGE_FIELDS:
            counts['lineage_read_copies'] += 1
            return deepcopy(value)
        if type(value) not in (dict, list):
            raise ValueError('unsupported protected read')
        key = id(value)
        if key not in cache:
            cache[key] = (ReadOnlyDict(value, _wrap=wrap) if type(value) is dict
                          else ReadOnlyList(value, _wrap=wrap))
        return cache[key]
    return wrap(base), cache


def _fault(stage, capsule):
    """Test instrumentation only; no caller-supplied callbacks are accepted."""


@dataclass(frozen=True)
class Attempt:
    admitted: bool
    processing_result: object
    copied_records: tuple = ()
    reason: str = ''


class ScopedCompletionOwner:
    """Own authority exclusively. Only detached snapshots leave this object.

    Unchanged records are shared between PRIVATE successive roots, not with the
    input or any snapshot. Capabilities expire before every return. Full source
    validation is deliberately repeated; no history-validity cache is inferred.
    """
    def __init__(self, source, *, registry=kernel.DEFAULT_EVENT_HANDLERS, callbacks=()):
        if (registry is not kernel.DEFAULT_EVENT_HANDLERS or type(callbacks) is not tuple
                or callbacks or registry.handler_for('STAGE1_FLIGHT_COMPLETION') is not _HANDLER):
            raise ValueError('unsupported registry, handler or callbacks')
        if not _plain_authority_tree(source) or not validate_world(source).is_valid:
            raise ValueError('plain valid alias-free source required')
        self.__base = _clone_runtime_world(source)
        self.__closed = False
        self.counts = dict(ownership_world_clones=1, export_world_clones=0,
                           scoped_transactions=0, copied_existing_records=0,
                           detached_output_records=0, strict_fallbacks=0,
                           reconciliation_calls=0, lineage_read_copies=0)

    def _require_open(self):
        if self.__closed:
            raise ValueError('owner closed')

    def snapshot(self):
        self._require_open()
        self.counts['export_world_clones'] += 1
        return _clone_runtime_world(self.__base)

    def close(self):
        self.__closed = True
        self.__base = None

    def strict_next(self):
        """Explicit unchanged fallback; counted, never called scoped success."""
        self._require_open()
        self.counts['strict_fallbacks'] += 1
        return kernel.process_next_event(self.__base)

    def strict_through(self, target):
        """Explicit strict fence for intervening dispatch/departure/Booking work."""
        self._require_open()
        self.counts['strict_fallbacks'] += 1
        return kernel.process_events_through(self.__base, target)

    def complete(self):
        self._require_open()
        base = self.__base
        started = base['simulation']['time_utc']
        if kernel.DEFAULT_EVENT_HANDLERS.handler_for('STAGE1_FLIGHT_COMPLETION') is not _HANDLER:
            raise ValueError('built-in handler binding changed')
        validation = validate_world(base)
        if not validation.is_valid:
            raise ValueError('private source invalid')
        # Retain actual command-entry reconciliation, including its world copy.
        # A repair is an independently committed prefix, just as in strict Next.
        self.counts['reconciliation_calls'] += 1
        kernel._reconcile_quarterly(base)
        heap = kernel.build_event_queue_index(base)
        if not heap:
            return Attempt(False, None, reason='no event; use explicit strict fallback')
        event = base['world_state']['pending_events'][heap[0][3]]
        if (base['metadata']['save_schema_version'] != 9
                or base['simulation'].get('operational_authority') != 'QUARTERLY_BACKEND_V1'
                or event['event_type'] != 'STAGE1_FLIGHT_COMPLETION'
                or event['operation_revision'] != base['simulation']['operation_revisions'].get(event['owner_id'], 0)):
            return Attempt(False, None, reason='unsupported/stale boundary; use explicit strict fallback')
        world = base['world_state']
        flight = world['dated_flights'][event['owner_id']]
        if ('quarterly_lineage' not in flight or flight['service_type'] != 'PASSENGER'
                or flight['status'] != 'OPERATIONALLY_LOCKED'
                or flight['dated_flight_id'] in world['flight_results']):
            return Attempt(False, None, reason='unsupported flight; use explicit strict fallback')
        footprint = completion_ownership(base, event['event_id'])
        accounts = fulfilment._account_ids(world, flight['airline_id'])
        footprint['financial_accounts'] = {accounts[c] for c in
            ('cash', 'unflown_tickets', 'passenger_revenue', 'operating_expenses')}
        copied = tuple((name, key) for name, keys in footprint.items()
                       for key in sorted(keys) if key in world[name])
        self.counts['scoped_transactions'] += 1
        self.counts['copied_existing_records'] += len(copied)
        ownership = CandidateOwnership(base, _validated=True)
        # Existing production capsules intentionally exclude quarterly careers.
        # Supply test-local safe reads compatible with exact lineage predicates.
        ownership._snapshot, read_cache = _quarterly_snapshot(base, ownership._alive, self.counts)
        capsule = ownership.begin(footprint, local=True)
        try:
            _fault('before_handler', capsule)
            before = kernel._event_contract_witness(base, ownership=capsule)
            outcome, failure, generated = kernel._apply_handler_candidate(
                before, capsule.envelope, event['event_id'], _HANDLER)
            if failure:
                return Attempt(True, kernel._failure_result(started, base, failure), copied)
            if generated:
                raise ValueError('Completion unexpectedly generated events')
            _fault('after_handler', capsule)
            outputs = capsule.checked_outputs()
            # This clone covers ONLY simulation, allocator and allowed outputs.
            # It detaches any retained writable handler/capsule references.
            detached = deepcopy(outputs)
            self.counts['detached_output_records'] += sum(len(rows) for rows in detached['records'].values())
            successor = dict(base)
            successor['world_state'] = dict(world)
            successor['simulation'] = detached['simulation']
            successor['deterministic_state'] = dict(base['deterministic_state'])
            successor['deterministic_state']['id_allocator'] = detached['allocator']
            for name, keys in footprint.items():
                table = dict(world[name])  # pointer copy, NOT deep isolation
                for key in keys:
                    if key in detached['records'][name]:
                        table[key] = detached['records'][name][key]
                    else:
                        table.pop(key, None)
                successor['world_state'][name] = table
            _fault('before_validation', capsule)
            final = validate_world(successor)
            if not final.is_valid:
                failure = kernel.EventFailure('RESULT_VALIDATION_FAILED',
                    'handler result did not satisfy authoritative validation', event['event_id'],
                    tuple(issue.as_dict() for issue in final.errors))
                return Attempt(True, kernel._failure_result(started, base, failure), copied)
            _fault('before_publish', capsule)
            result = kernel.ProcessingResult('COMPLETED', started,
                successor['simulation']['time_utc'], (event['event_id'],), ())
            accepted = Attempt(True, result, copied)
            # Revoke capabilities BEFORE the single publication assignment.
            ownership.close()
            self.__base = successor
            return accepted
        except Exception as exc:
            failure = kernel.EventFailure('EXPERIMENT_FAILED', str(exc), event['event_id'])
            return Attempt(True, kernel._failure_result(started, base, failure), copied)
        finally:
            ownership.close()
            read_cache.clear()
