"""Shared time-resolution facade over the strict chronological kernel.

Stage 1 preserves every existing isolated event transaction. Requests, progress,
and boundary descriptions are runtime-only; no additional state enters saves.
Only the owner thread may step a request or apply commands between its steps.
"""

from dataclasses import dataclass

from . import kernel


# Future shared-candidate implementations must retain these causal fences.
# Stage 1 isolates EVERY event, including custom handlers; this is not dispatch.
PROTECTED_CAUSAL_FENCES = frozenset({
    "DAILY_BOOKING_CHECKPOINT",
    "STAGE1_WEEKLY_PUBLICATION",
    "AIRCRAFT_CONTRACT_EXPIRY",
})


@dataclass(frozen=True)
class ResolutionProgress:
    status: str
    authoritative_utc: str
    requested_target_utc: str
    completed_event_count: int
    stale_event_count: int
    event_id: str | None = None
    processing_result: kernel.ProcessingResult | None = None

    @property
    def finished(self):
        return self.processing_result is not None

    @property
    def unresolved_target_utc(self):
        return None if self.status == "COMPLETED" else self.requested_target_utc


@dataclass(frozen=True)
class ResolutionBoundary:
    """Describe an owned complete-event snapshot, not a new clock authority.

    A complete event transaction can leave other events due at the same UTC.
    In that case current_utc_fully_resolved is False: the snapshot is safe for
    saves/commands, but it does not establish resolution through that timestamp.
    last_committed_event_* refers to this request, not global historical progress.
    """

    authoritative_utc: str
    requested_target_utc: str
    last_committed_event_id: str | None
    last_committed_event_utc: str | None
    current_utc_fully_resolved: bool


class ResolutionRequest:
    """Step genuine kernel yields, retaining its whole-request safety limits.

    step() executes at most one event, or finishes the target without an event.
    Some kernel stop/error boundaries commit an event and terminate immediately.
    No wall-time budget, batch transaction, automatic retry, or recovery exists.
    close() leaves all committed events intact and does not change clock policy.
    """

    def __init__(self, envelope, target_time_utc, **kernel_options):
        self._world = envelope
        self.target_time_utc = target_time_utc
        self._work = kernel.iter_events_through(envelope, target_time_utc, **kernel_options)
        self._started = False
        self.finished = False
        self.result = None
        self._completed = 0
        self._stale = 0
        self._last_event_id = None
        self._last_event_utc = None

    def step(self, *, management_changed=False):
        """Continue; signal validated intervening commands to refresh the heap."""
        if self.finished:
            raise ValueError("resolution request is finished")
        try:
            event_id = (self._work.send(management_changed) if self._started
                        else next(self._work))
            self._started = True
        except StopIteration as done:
            self.finished = True
            self.result = done.value
            # STOPPED/limit failures may terminate immediately after a commit,
            # without yielding its ID. Counts identify that actual last event,
            # even if it generated a lower-priority event at the same UTC.
            unyielded = (self.result.completed_event_ids[self._completed:]
                         + self.result.skipped_event_ids[self._stale:])
            if unyielded:
                self._remember_event(unyielded[-1])
            self._completed = len(self.result.completed_event_ids)
            self._stale = len(self.result.skipped_event_ids)
            return self._progress(self.result.status, result=self.result)
        except BaseException:
            self.finished = True
            raise
        self._remember_event(event_id)
        if self._world["world_state"]["event_history"][event_id]["status"] == "STALE":
            self._stale += 1
        else:
            self._completed += 1
        return self._progress("YIELDED", event_id=event_id)

    def _remember_event(self, event_id):
        self._last_event_id = event_id
        self._last_event_utc = self._world["world_state"]["event_history"][event_id]["resolved_at_utc"]

    def _progress(self, status, *, event_id=None, result=None):
        return ResolutionProgress(status, self._world["simulation"]["time_utc"],
            self.target_time_utc, self._completed, self._stale, event_id, result)

    def boundary(self):
        """Inspect completeness on demand; do not add a scan to every pump.

        Requires a valid exclusively owned world, as do intervening commands.
        This derived description never validates, mutates, or persists a clock.
        """
        now = self._world["simulation"]["time_utc"]
        fully_resolved = not any(event["due_at_utc"] <= now
            for event in self._world["world_state"]["pending_events"].values())
        return ResolutionBoundary(now, self.target_time_utc, self._last_event_id,
                                  self._last_event_utc, fully_resolved)

    def close(self):
        self._work.close()
        self.finished = True


def begin_resolution(envelope, target_time_utc, *, shared=False, shadow=False,
                     max_batch_events=8, execution_state=None, **kernel_options):
    """Strict by default. Stage 3A shared/shadow infrastructure is opt-in only.

    Pacing/session/Kivy deliberately keep using the unchanged strict default.
    Arbitrary stop callbacks require the original per-event strict boundaries.
    """
    if shared and kernel_options.get('stop_condition') is None:
        from .shared_candidate import SharedResolutionRequest
        return SharedResolutionRequest(envelope, target_time_utc,
            shadow=shadow, max_batch_events=max_batch_events,
            execution_state=execution_state, **kernel_options)
    return ResolutionRequest(envelope, target_time_utc, **kernel_options)


def resolve_until(envelope, target_time_utc, **kernel_options):
    """Synchronously drain the same request; return the unchanged kernel result."""
    request = begin_resolution(envelope, target_time_utc, **kernel_options)
    try:
        while not request.finished:
            request.step()
        return request.result
    finally:
        request.close()


def resolve_next_event(envelope, *, registry=kernel.DEFAULT_EVENT_HANDLERS):
    """Preserve Next Event: exactly one event, including equal-time queues."""
    return kernel.process_next_event(envelope, registry=registry)
