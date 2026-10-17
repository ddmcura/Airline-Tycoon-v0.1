"""Private closed-owner Completion publication; no arbitrary-handler framework.

Serialized/non-reentrant API, with one recoverable fault and uninterrupted cleanup.
Prepared state never escapes the owner. A shallow root before-image restores a
partial install; an installed successor is committed even if its marker failed.
"""
from copy import deepcopy
from dataclasses import dataclass

from .execution_contracts import SharedExecutionState
from game.world_state import validate_world
from game.world_state.flight_proof_witness import protected_bytes


def _fault(stage):
    """Private instrumentation boundary, never a public authority callback."""


def _same_roots(world, image):
    return (type(world) is dict and world.keys() == image.keys()
            and all(world[key] is value for key, value in image.items()))


def _mutable_nodes(value):
    seen = set(); pending = [value]
    while pending:
        item = pending.pop()
        if type(item) not in (dict, list) or id(item) in seen:
            continue
        seen.add(id(item))
        pending.extend(item.values() if type(item) is dict else item)
    return seen


def _install(world, successor):
    dict.update(world, successor)


@dataclass(frozen=True)
class _Receipt:
    committed: bool
    diagnostic: str | None = None


class _Prepared:
    def __init__(self, owner, successor, event_id):
        self.owner = owner
        self.successor = successor
        self.before = dict(owner._world)
        self.epoch = owner._epoch
        self.event_id = event_id
        self.state = 'PREPARED'
        self.receipt = None
        self.committed_before = owner._counts['committed']


def _prepare_successor(owner, outputs, footprint, event_id):
    """Detach only accepted outputs and validate the complete prospective tree."""
    base = owner._world
    expected = protected_bytes(outputs)
    _fault('output_detachment')
    detached = deepcopy(outputs)
    if (protected_bytes(detached) != expected
            or _mutable_nodes(outputs).intersection(_mutable_nodes(detached))):
        raise ValueError('scoped output detachment mismatch or retained mutable reference')
    owner._counts['output_detachments'] += 1
    owner._counts['detached_output_records'] += sum(len(rows) for rows in detached['records'].values())
    successor = dict(base)
    successor['world_state'] = dict(base['world_state'])
    successor['simulation'] = detached['simulation']
    successor['deterministic_state'] = dict(base['deterministic_state'])
    successor['deterministic_state']['id_allocator'] = detached['allocator']
    for name, keys in footprint.items():
        table = dict(base['world_state'][name])
        for key in keys:
            if key in detached['records'][name]:
                table[key] = detached['records'][name][key]
            else:
                table.pop(key, None)
        successor['world_state'][name] = table
        owner._counts['shallow_collection_tables'] += 1
    _fault('successor_validation')
    owner._counts['successor_validations'] += 1
    final = validate_world(successor)
    if not final.is_valid:
        raise ValueError('scoped successor validation failed: ' + final.errors[0].message)
    _fault('publication_preparation')
    owner._counts['root_before_images'] += 1
    return _Prepared(owner, successor, event_id)


class _OwnedCompletionAuthority:
    """Session-private, root-bound grant. It is never returned by session APIs."""
    def __init__(self, world):
        self._world = world
        self._alive = True
        self._busy = False
        self._epoch = 0
        self.execution_state = SharedExecutionState()
        self._pending_divergence = None
        self._diagnostic = None
        self._active_preparation = None
        self._counts = dict(attempts=0, committed=0, precommit_failures=0,
            postcommit_faults=0, copied_existing_records=0, detached_output_records=0,
            output_detachments=0, shallow_collection_tables=0, root_before_images=0,
            restorations=0, source_validations=0, successor_validations=0,
            lineage_read_copies=0)

    def close(self):
        self._alive = False
        self._active_preparation = None

    def diagnostics(self):
        return dict(enabled=self._alive and self.execution_state.enabled,
                    diagnostic=self._diagnostic or self.execution_state.diagnostic,
                    counts=dict(self._counts))

    def _publish(self, prepared):
        if prepared.owner is not self:
            raise ValueError('foreign scoped preparation')
        if prepared.receipt is not None:
            return prepared.receipt
        if (not self._alive or prepared.epoch != self._epoch
                or prepared.state != 'PREPARED' or not _same_roots(self._world, prepared.before)):
            raise ValueError('stale scoped preparation')
        successor = prepared.successor
        if (type(successor) is not dict or successor.keys() != prepared.before.keys()
                or any(type(key) is not str for key in successor)):
            raise ValueError('only existing plain envelope roots may be published')
        diagnostic = None
        try:
            _fault('before_installation')
            _install(self._world, successor)
            if not _same_roots(self._world, successor):
                raise ValueError('incomplete scoped installation')
            _fault('after_installation_before_marker')
            prepared.state = 'COMMITTED'
            _fault('after_commit_marker')
        except BaseException as exc:
            diagnostic = type(exc).__name__ + ': ' + str(exc)
            if _same_roots(self._world, successor):
                prepared.state = 'COMMITTED'
            else:
                dict.update(self._world, prepared.before)
                self._counts['restorations'] += 1
                if not _same_roots(self._world, prepared.before):
                    raise RuntimeError('scoped root restoration failed; fail-stop required')
                prepared.state = 'ROLLED_BACK'
        receipt = _Receipt(prepared.state == 'COMMITTED', diagnostic)
        prepared.receipt = receipt
        return receipt

    def _status(self, prepared):
        if prepared.receipt is not None:
            return prepared.receipt
        return _Receipt(prepared.state == 'COMMITTED' or _same_roots(self._world, prepared.successor),
                        'publication receipt recovered after interruption')

    def try_execute(self, world, event_id, registry):
        """None means inadmissible; a receipt distinguishes recovery from commit."""
        if not self._alive or world is not self._world or not self.execution_state.enabled:
            return None
        if self._busy:
            raise ValueError('scoped execution is not reentrant')
        from game.aircraft_operations.scoped_completion import _prepare_completion
        prepared = None
        self._active_preparation = None
        self._busy = True
        try:
            prepared = _prepare_completion(self, event_id, registry)
            if prepared is None:
                return None
            self._active_preparation = prepared
            try:
                receipt = self._publish(prepared)
                _fault('receipt_return')
            except BaseException as exc:
                receipt = self._status(prepared)
                if receipt.committed:
                    receipt = _Receipt(True, 'post-commit ' + type(exc).__name__ + ': ' + str(exc))
                else:
                    raise
            if receipt.committed:
                self._epoch += 1
                self._counts['committed'] += 1
                if receipt.diagnostic:
                    self._counts['postcommit_faults'] += 1
                    self._diagnostic = receipt.diagnostic
            else:
                self._counts['precommit_failures'] += 1
            prepared.receipt = receipt
            return receipt
        except BaseException as exc:
            if prepared is not None and self._status(prepared).committed:
                # The request MUST count this event; never strict-replay a commit.
                self._diagnostic = 'post-commit ' + type(exc).__name__ + ': ' + str(exc)
                return self.recover_receipt(world, event_id, self._diagnostic)
            if not isinstance(exc, Exception):
                raise
            self._counts['precommit_failures'] += 1
            self._diagnostic = type(exc).__name__ + ': ' + str(exc)
            return _Receipt(False, self._diagnostic)
        finally:
            self._busy = False
            if prepared is not None and prepared.receipt is not None:
                prepared.before = prepared.successor = None

    def recover_receipt(self, world, event_id, diagnostic='publication return interrupted'):
        """Called by the event executor before ANY strict recovery/replay."""
        prepared = self._active_preparation
        if world is not self._world or prepared is None or prepared.event_id != event_id:
            return None
        receipt = self._status(prepared)
        if not receipt.committed:
            return receipt
        self._epoch = max(self._epoch, prepared.epoch + 1)
        self._counts['committed'] = max(self._counts['committed'], prepared.committed_before + 1)
        self._diagnostic = diagnostic
        receipt = _Receipt(True, diagnostic)
        prepared.receipt = receipt
        prepared.before = prepared.successor = None
        return receipt

    def recovered_strict(self):
        from .kernel import EventFailure
        message = 'scoped Completion disagreed with strict execution; shared execution disabled'
        self.execution_state.disable(message)
        self._diagnostic = message
        self._pending_divergence = EventFailure('OPTIMIZER_DIVERGENCE', message)

    def pop_divergence(self):
        failure, self._pending_divergence = self._pending_divergence, None
        return failure


def _new_owned_completion_authority(world):
    return _OwnedCompletionAuthority(world)
