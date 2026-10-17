"""Phase 3F TEST ONLY. Nothing here is imported by production.

Serialized, non-reentrant closed-owner experiment. Ordinary Python reflection,
concurrent observers and a second asynchronous failure inside restoration are
outside the failure model. Installation is NOT assumed to be atomic: a shallow
root before-image restores partial installations. Fully installed state wins over
an exception/absent success marker. No clear(), world clone or event replay here.
"""
from dataclasses import dataclass
from unittest.mock import patch

from app.owned_reads import _OwnedReadViews
from app.session import Stage1Session
from game.world_state.flight_proof_witness import protected_bytes
from tests import scoped_completion_experiment as scoped


def _fault(stage):
    """Private test hook. No mutable world/capsule is passed to a callback."""


def _install(target, successor):
    # Exact dicts, existing exact-str keys, plain values. Keep all old roots
    # alive in the preparation through installation/classification/restoration.
    dict.update(target, successor)


def _same_roots(target, image):
    return (type(target) is dict and target.keys() == image.keys()
            and all(target[key] is value for key, value in image.items()))


def _mutable_nodes(value):
    seen = set(); pending = [value]
    while pending:
        item = pending.pop()
        if type(item) not in (dict, list) or id(item) in seen:
            continue
        seen.add(id(item))
        pending.extend(item.values() if type(item) is dict else item)
    return seen


@dataclass(frozen=True)
class PublicationOutcome:
    state: str
    attempt: object = None
    diagnostic: str | None = None

    @property
    def committed(self):
        return self.state == 'COMMITTED'


class _Prepared:
    """Opaque one-use issuance. Private attributes are not public capabilities."""
    def __init__(self, owner, successor, attempt):
        self._owner = owner
        self._successor = successor
        self._attempt = attempt
        self._before = dict(owner._session._world)  # FIVE references, no records
        self._epoch = owner._epoch
        self._binding = owner._session.binding_revision
        self._views = _OwnedReadViews(owner._session._world,
                                     owner._session.progression_revision)
        self._state = 'PREPARED'
        self._receipt = None


class StableRootBridge:
    def __init__(self, session):
        if type(session) is not Stage1Session or not session.closed_owner or not session.active:
            raise ValueError('an active built-in closed-owner session is required')
        self._session = session
        self._binding = session.binding_revision
        self._world = session._world
        self._epoch = 0
        self._busy = False
        self._proof_owner = scoped.ScopedCompletionOwner.__new__(scoped.ScopedCompletionOwner)
        # Internal TEST-ONLY transfer/lending: session already detached/owns this
        # world. Do not invoke the experiment constructor's extra ownership clone.
        self._proof_owner._ScopedCompletionOwner__base = self._world
        self._proof_owner._ScopedCompletionOwner__closed = False
        self._proof_owner.counts = dict(ownership_world_clones=0, export_world_clones=0,
            scoped_transactions=0, copied_existing_records=0, detached_output_records=0,
            strict_fallbacks=0, reconciliation_calls=0, lineage_read_copies=0)
        self.counts = dict(full_world_candidate_clones=0, full_world_commit_clones=0,
            publication_world_clones=0, ownership_acquisitions=0, full_world_exports=0,
            validation_calls=0, scoped_output_detachments=0,
            shallow_collection_tables=0, shallow_root_before_images=0,
            shallow_root_observations=0,
            installations=0, restorations=0, committed=0)

    def _require_current(self):
        if (self._binding != self._session.binding_revision
                or self._world is not self._session._world):
            raise ValueError('stale bridge after career replacement')
        if self._session._runtime is not None and self._session._runtime.closed:
            raise ValueError('closed session cannot publish')

    def prepare(self):
        self._require_current()
        if not scoped._plain_authority_tree(self._world):
            raise ValueError('plain alias-free closed authority required')
        if self._busy:
            raise ValueError('publication is not reentrant')
        self._busy = True
        base = self._world
        old_roots = dict(base)
        self.counts['shallow_root_observations'] += 1
        original_copy = scoped.deepcopy
        original_validate = scoped.validate_world
        repair_notified = False

        def detach(value):
            pack = type(value) is dict and value.keys() == {'simulation','allocator','records'}
            if pack:
                _fault('during_output_detachment')
                expected = protected_bytes(value)
                self.counts['scoped_output_detachments'] += 1
            result = original_copy(value)
            if pack and protected_bytes(result) != expected:
                raise ValueError('scoped detachment changed accepted output values')
            if pack and _mutable_nodes(value).intersection(_mutable_nodes(result)):
                raise ValueError('scoped detachment retained writable references')
            return result

        def validate(value):
            self.counts['validation_calls'] += 1
            if value is not base:
                _fault('during_successor_validation')
            return original_validate(value)

        try:
            _fault('before_successor_preparation')
            with patch.object(scoped, 'deepcopy', detach), patch.object(scoped, 'validate_world', validate):
                attempt = self._proof_owner.complete()
            if not attempt.admitted or not attempt.processing_result.succeeded:
                raise ValueError('scoped preparation refused/failed: ' + str(attempt))
            successor = self._proof_owner._ScopedCompletionOwner__base
            if successor is base:
                raise ValueError('experiment did not prepare a successor')
            self.counts['shallow_collection_tables'] += sum(
                successor['world_state'][name] is not table
                for name, table in base['world_state'].items())
            # Reconciliation is an existing independently committed prefix. Make
            # its cache/progress notification before sealing this preparation.
            if not _same_roots(base, old_roots):
                self._session._mark_progress()
                repair_notified = True
            _fault('during_publication_preparation')
            prepared = _Prepared(self, successor, attempt)
            self.counts['shallow_root_before_images'] += 1
            return prepared
        finally:
            self._proof_owner._ScopedCompletionOwner__base = base
            self._busy = False
            if not repair_notified and not _same_roots(base, old_roots):
                self._session._mark_progress()

    def _notify_commit(self):
        self._session._mark_progress()

    def _drop_read_contexts(self):
        self._session._read_views = None
        if self._session._quarterly_indexes is not None:
            self._session._quarterly_indexes.invalidate()

    def publish(self, prepared):
        """Classify late Python exceptions using the actual installed roots too."""
        try:
            return self._publish(prepared)
        except BaseException as exc:
            if type(prepared) is _Prepared and prepared._owner is self:
                committed = prepared._state == 'COMMITTED' or (
                    prepared._successor is not None
                    and _same_roots(self._world, prepared._successor))
                if committed:
                    prepared._state = 'COMMITTED'
                    self._drop_read_contexts()
                    receipt = PublicationOutcome('COMMITTED', prepared._attempt,
                        'post-commit ' + type(exc).__name__ + ': ' + str(exc))
                    prepared._receipt = receipt
                    prepared._successor = prepared._before = prepared._views = None
                    return receipt
            raise

    def _publish(self, prepared):
        if type(prepared) is not _Prepared or prepared._owner is not self:
            raise ValueError('foreign publication preparation')
        if prepared._receipt is not None:
            return prepared._receipt  # Idempotent receipt; NEVER execute again.
        self._require_current()
        if (self._busy or prepared._state != 'PREPARED'
                or prepared._epoch != self._epoch
                or prepared._binding != self._session.binding_revision
                or not prepared._views.matches(self._world, self._session.progression_revision)
                or not _same_roots(self._world, prepared._before)):
            raise ValueError('stale or reentrant publication preparation')
        successor = prepared._successor
        if (type(successor) is not dict or successor.keys() != prepared._before.keys()
                or any(type(key) is not str for key in successor)):
            raise ValueError('publication must replace existing plain envelope roots only')
        self._busy = True
        diagnostic = None
        try:
            _fault('immediately_before_installation')
            self.counts['installations'] += 1
            _install(self._world, successor)
            if not _same_roots(self._world, successor):
                raise ValueError('incomplete root installation')
            _fault('after_installation_before_marker')
            prepared._state = 'COMMITTED'
            _fault('after_commit_marker')
        except BaseException as exc:
            diagnostic = type(exc).__name__ + ': ' + str(exc)
            if _same_roots(self._world, successor):
                # Actual root identity is the commit fact, not a fallible Python
                # marker/return. Post-commit faults must not become retry signals.
                prepared._state = 'COMMITTED'
            else:
                # No domain undo and no full-world rollback clone. Keep the old
                # five references until installation has been fully classified.
                dict.update(self._world, prepared._before)
                self.counts['restorations'] += 1
                if not _same_roots(self._world, prepared._before):
                    raise RuntimeError('root restoration failed; fail-stop required')
                prepared._state = 'ROLLED_BACK'
        finally:
            self._busy = False
        if prepared._state == 'COMMITTED':
            self._epoch += 1
            self.counts['committed'] += 1
            try:
                self._notify_commit()
                _fault('after_notification_before_return')
            except BaseException as exc:
                diagnostic = type(exc).__name__ + ': ' + str(exc)
                # Commit survives failure in an observer. Discard stale cached
                # contexts directly; never interpret this as event rollback.
                self._drop_read_contexts()
        receipt = PublicationOutcome(prepared._state, prepared._attempt, diagnostic)
        prepared._receipt = receipt
        prepared._successor = prepared._before = prepared._views = None
        return receipt

    def complete(self):
        prepared = None
        try:
            prepared = self.prepare()
            return self.publish(prepared)
        except BaseException as exc:
            if prepared is not None:
                receipt = self.status(prepared)
                if receipt.committed:
                    return PublicationOutcome('COMMITTED', receipt.attempt,
                        'post-commit ' + type(exc).__name__ + ': ' + str(exc))
            return PublicationOutcome('PRECOMMIT_FAILED', diagnostic=type(exc).__name__ + ': ' + str(exc))

    def status(self, prepared):
        """Recover commit fact after a caller/return interruption; never replay."""
        if type(prepared) is not _Prepared or prepared._owner is not self:
            raise ValueError('foreign publication preparation')
        if prepared._receipt is not None:
            return prepared._receipt
        if prepared._state == 'COMMITTED' or (prepared._successor is not None
                and _same_roots(self._world, prepared._successor)):
            return PublicationOutcome('COMMITTED', prepared._attempt,
                                      'commit fact recovered from state/root identity')
        return PublicationOutcome(prepared._state)
