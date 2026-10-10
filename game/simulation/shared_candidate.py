"""Opt-in shared infrastructure. Certified payments/flights have local proofs.

Production pacing explicitly uses this bounded path. Unapproved handlers execute
the strict kernel transaction. Private candidates exist only within step(), not
between cooperative returns. The strict kernel remains the recovery authority.
"""

import heapq

from . import kernel
from .execution_contracts import SharedExecutionState
from .candidate_ownership import CandidateOwnership
from .resolver import ResolutionRequest
from game.world_state.timestamps import parse_canonical_utc


def _validate_batch(candidate):
    return kernel.validate_world(candidate)


def _shared_transition(candidate, event_id, handler, contract=None, *, ownership=None, oracle=False, selection_heap=None):
    global_before = kernel._event_contract_witness(candidate) if oracle or ownership is None else None
    oracle_witness = (contract.capture_transition(candidate,event_id,global_before)
                      if oracle and contract is not None else None)
    capsule = (ownership.begin(contract.mutation_footprint(candidate,event_id),
                               read_lookup_factory=contract.read_lookup_factory, local=True)
               if ownership is not None and contract is not None else None)
    before = kernel._event_contract_witness(candidate, ownership=capsule) if capsule is not None else global_before
    execution = capsule.envelope if capsule is not None else candidate
    witness = (contract.capture_transition(candidate, event_id, before, ownership=capsule)
               if capsule is not None else contract.capture_transition(candidate, event_id, before)
               if contract is not None else None)
    outcome, failure, generated = kernel._apply_handler_candidate(
        before, execution, event_id, handler,
        read_capability=capsule.read_lookup if capsule is not None else None,
        selection=kernel._seal_canonical_selection(capsule, selection_heap)
                  if capsule is not None and selection_heap is not None else None)
    if failure:
        return outcome, failure, generated
    if contract is not None:
        try:
            contract.validate_transition(witness, execution, event_id, generated)
            if capsule is not None: ownership.publish(candidate,capsule)
            if oracle_witness is not None:
                contract.validate_transition(oracle_witness,candidate,event_id,generated)
        except Exception as exc:
            return None, kernel.EventFailure('TRANSITION_PROOF_FAILED',
                f'certified transition proof failed: {exc}', event_id), ()
        return outcome, None, generated
    # NO_OP and synthetic shadow probes retain full per-event validation.
    validation = kernel.validate_world(candidate)
    if not validation.is_valid:
        return None, kernel.EventFailure('RESULT_VALIDATION_FAILED',
            'handler result did not satisfy authoritative validation', event_id,
            tuple(issue.as_dict() for issue in validation.errors)), ()
    return outcome, None, generated


class SharedResolutionRequest(ResolutionRequest):
    """Bounded infrastructure request, explicitly selected by the resolver.

    Certification remains identity-bound. Shadow-only synthetic contracts are
    private fixtures used to prove generated-event/failure machinery, not a
    supported way to certify arbitrary gameplay handlers. Certified domains use their
    identity/version-bound transition proof; other probes receive full validation.
    Strict fallbacks execute once, never shadowed.
    """

    def __init__(self, envelope, target_time_utc, *, shadow=False,
                 max_batch_events=8, execution_state=None,
                 registry=kernel.DEFAULT_EVENT_HANDLERS,
                 max_events=kernel.DEFAULT_MAX_EVENTS_PER_ADVANCE,
                 max_generated_events=kernel.DEFAULT_MAX_GENERATED_EVENTS_PER_ADVANCE,
                 stop_condition=None):
        if stop_condition is not None:
            raise ValueError('stop callbacks require strict resolution')
        self._world = envelope
        self.target_time_utc = target_time_utc
        self._target = parse_canonical_utc(target_time_utc, 'target_time_utc')
        self.registry = registry
        self.shadow = shadow
        self.max_batch_events = kernel._positive_int(max_batch_events, 'max_batch_events')
        self.max_events = kernel._positive_int(max_events, 'max_events')
        self.max_generated = kernel._positive_int(max_generated_events, 'max_generated_events')
        self.execution_state = execution_state or SharedExecutionState()
        self._started = False
        self.finished = False
        self.result = None
        self._completed = self._stale = self._generated = 0
        self._generation_boundary = None
        self._completed_ids = []
        self._skipped_ids = []
        self._last_event_id = self._last_event_utc = None
        self._heap = []

    def _finish(self, status, failure=None):
        self.finished = True
        self.result = kernel.ProcessingResult(status, self._started_utc,
            self._world['simulation']['time_utc'], tuple(self._completed_ids),
            tuple(self._skipped_ids), failure)
        return self._progress(status, result=self.result)

    def _limit_before(self, heap, additional=0):
        if self._completed + self._stale + additional >= self.max_events:
            return kernel.EventFailure('EVENT_LIMIT_REACHED',
                f'processing stopped after {self.max_events} events; retry explicitly to continue',
                heap[0][3])
        return None

    def _limit_after(self, heap, boundary, generated):
        return kernel._causal_generation_limit(heap, boundary, generated, self.max_generated)

    def _paused_by_event(self, world):
        return (self._started_mode != 'PAUSED'
                and world['simulation']['clock_state'] == 'PAUSED')

    @staticmethod
    def _insert_generated(heap, world, generated):
        for event_id in generated:
            heapq.heappush(heap, kernel._event_key(world['world_state']['pending_events'][event_id]))

    def _record(self, event_id, outcome, generated):
        (self._skipped_ids if outcome == 'STALE' else self._completed_ids).append(event_id)
        self._stale += outcome == 'STALE'
        self._completed += outcome != 'STALE'
        self._generation_boundary, self._generated = kernel._causal_generation_accounting(
            self._world, event_id, generated, self._generation_boundary, self._generated)
        self._remember_event(event_id)

    def _can_share(self, world, event_id):
        if not self.execution_state.enabled:
            return False
        event = world['world_state']['pending_events'][event_id]
        revision = world['simulation']['operation_revisions'].get(event['owner_id'], 0)
        if event['operation_revision'] < revision:
            return False  # Lifecycle-only stale handling stays strict initially.
        handler = self.registry.handler_for(event['event_type'])
        contract = self.registry.execution_contract_for(event['event_type'])
        certified = False
        if contract.validate_transition is not None:
            # Fixed approved certificate, not a caller-provided proof escape hatch.
            from game.world_state.payment_validation import is_payment_certificate
            from game.world_state.flight_transition_validation import is_flight_certificate
            certified = is_payment_certificate(contract) or is_flight_certificate(contract)
            if not certified:
                return False
        if handler is not kernel._no_op and not certified and not (self.shadow and contract.shadow_only):
            return False
        return (contract.permits_shared(handler, world['metadata']['save_schema_version'], shadow=self.shadow)
                and (contract.supports_input is None or contract.supports_input(world, event)))

    def _strict_one(self):
        event_id = self._heap[0][3]
        failure = self._limit_before(self._heap)
        if failure:
            return self._finish('BLOCKED', failure)
        outcome, failure, generated = kernel._execute_event(self._world, event_id, self.registry)
        if failure:
            return self._finish('BLOCKED', failure)
        heapq.heappop(self._heap)
        self._insert_generated(self._heap, self._world, generated)
        self._record(event_id, outcome, generated)
        failure = self._limit_after(self._heap, self._generation_boundary, self._generated)
        if failure:
            return self._finish('BLOCKED', failure)
        if self._paused_by_event(self._world):
            return self._finish('STOPPED')
        return self._progress('YIELDED', event_id=event_id)

    def _recover(self, attempts):
        """Candidate is discarded by caller. Strict replay reselects every event.

        No counters/IDs are charged for speculation. No arbitrary strict handler
        is replayed: every attempted handler was identity-certified at entry.
        """
        for _ in range(attempts):
            progress = self._strict_one()
            if progress.finished:
                if progress.processing_result.failure is not None:
                    return progress  # Strict failure owns its exact successful prefix.
                # A valid strict handler pause is still a successful transition.
                # Preserve it, but do not hide the optimizer defect as STOPPED.
                break
        message = 'shared candidate disagreed with strict execution; shared execution disabled'
        self.execution_state.disable(message)
        # Resolver stops; the owning runtime applies its existing blocked/pause
        # policy. Do not invent a failing gameplay event or mutate clock policy.
        return self._finish('BLOCKED', kernel.EventFailure('OPTIMIZER_DIVERGENCE', message))

    def _shared_batch(self):
        candidate = kernel._clone_runtime_world(self._world)
        candidate_heap = kernel._copy_event_queue(self._heap, candidate)
        reference = kernel._clone_runtime_world(self._world) if self.shadow else None
        ownership = None
        records = []
        attempts = 0
        generated_count = self._generated
        generation_boundary = self._generation_boundary
        terminal = None
        while candidate_heap and candidate_heap[0][0] <= self._target:
            failure = self._limit_before(candidate_heap, len(records))
            if failure:
                terminal = ('BLOCKED', failure)
                break
            if len(records) >= self.max_batch_events:
                break
            event_id = candidate_heap[0][3]
            if not self._can_share(candidate, event_id):
                break  # Flush BEFORE a fence/unknown/custom/stale event.
            event = candidate['world_state']['pending_events'][event_id]
            attempts += 1
            try:
                contract = self.registry.execution_contract_for(event['event_type'])
                handler = self.registry.handler_for(event['event_type'])
                if contract.validate_transition is not None:
                    if contract.mutation_footprint is not None and ownership is None:
                        ownership = CandidateOwnership(candidate, _validated=True)
                    outcome, failure, generated = _shared_transition(candidate, event_id, handler, contract,
                        ownership=ownership,oracle=self.shadow,selection_heap=candidate_heap)
                else:
                    if ownership is not None: ownership.close()
                    ownership = None  # Full-gated probes have a broader write surface.
                    outcome, failure, generated = _shared_transition(candidate, event_id, handler)
            except Exception:
                if ownership is not None: ownership.close()
                candidate = reference = ownership = None
                return self._recover(attempts)
            if failure:
                if ownership is not None: ownership.close()
                candidate = reference = ownership = None
                return self._recover(attempts)
            heapq.heappop(candidate_heap)
            self._insert_generated(candidate_heap, candidate, generated)
            records.append((event_id, outcome, generated))
            generation_boundary, generated_count = kernel._causal_generation_accounting(
                candidate, event_id, generated, generation_boundary, generated_count)
            if reference is not None:
                try:
                    strict = kernel.process_next_event(reference, registry=self.registry)
                except Exception:
                    if ownership is not None: ownership.close()
                    candidate = reference = ownership = None
                    return self._recover(attempts)
                if not strict.succeeded or reference != candidate:
                    if ownership is not None: ownership.close()
                    candidate = reference = ownership = None
                    return self._recover(attempts)
            failure = self._limit_after(candidate_heap, generation_boundary, generated_count)
            if failure:
                terminal = ('BLOCKED', failure)
                break
            if self._paused_by_event(candidate):
                terminal = ('STOPPED', None)
                break
        if ownership is not None:
            ownership.close()
            ownership = None
        try:
            validation = _validate_batch(candidate)
        except Exception:
            candidate = reference = ownership = None
            return self._recover(attempts)
        if not validation.is_valid or (reference is not None and reference != candidate):
            candidate = reference = ownership = None
            return self._recover(attempts)
        kernel._replace_envelope(self._world, candidate)
        self._heap = candidate_heap
        for event_id, outcome, generated in records:
            self._record(event_id, outcome, generated)
        # No candidate/reference stored on the request or exposed by progress.
        if terminal is not None:
            return self._finish(*terminal)
        return self._progress('YIELDED', event_id=self._last_event_id)

    def step(self, *, management_changed=False, boundary_requested=False):
        if self.finished:
            raise ValueError('resolution request is finished')
        if not self._started:
            self._started_utc = self._world['simulation']['time_utc']
            self._started_mode = self._world['simulation']['clock_state']
            if self._target < parse_canonical_utc(self._started_utc):
                raise ValueError('simulation time cannot move backward')
        if not self._started or management_changed:
            failure = kernel._valid_world_failure(self._world)
            if failure:
                return self._finish('BLOCKED', failure)
            kernel._reconcile_quarterly(self._world)
            self._heap = kernel.build_event_queue_index(self._world)
        was_started = self._started
        self._started = True
        if was_started and self._paused_by_event(self._world):
            return self._finish('STOPPED')
        if boundary_requested:
            return self._progress('YIELDED')  # Honor command before starting work.
        if not self._heap or self._heap[0][0] > self._target:
            # Preserve the strict final clock-gap validation/rollback behavior.
            final = kernel._complete_target(self._world, self.target_time_utc, self._started_utc)
            return self._finish(final.status, final.failure)
        if self._can_share(self._world, self._heap[0][3]):
            return self._shared_batch()
        return self._strict_one()

    def close(self):
        self._heap.clear()
        self.finished = True
