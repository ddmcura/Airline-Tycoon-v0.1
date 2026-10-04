"""Runtime-only configurable PH pacing; one caller owns all world mutations."""

from datetime import timedelta
import sys
import time

from .handlers import initialize_runtime_handlers
from .kernel import (
    DEFAULT_EVENT_HANDLERS, configure_clock_ratios,
    set_clock_mode,
)
from .resolver import begin_resolution
from game.world_state.timestamps import format_utc, parse_canonical_utc

from .speeds import player_speed

NANOSECOND = 1_000_000_000


def active_monotonic_ns():
    """Monotonic active uptime, excluding computer suspension.

    Windows perf_counter includes sleep; unbiased interrupt time does not.
    POSIX CLOCK_MONOTONIC excludes suspended time (unlike CLOCK_BOOTTIME).
    """
    if sys.platform == 'win32':
        import ctypes
        ticks = ctypes.c_ulonglong()
        if not ctypes.windll.kernel32.QueryUnbiasedInterruptTime(ctypes.byref(ticks)):
            raise OSError('Cannot read suspension-safe monotonic clock')
        return ticks.value * 100
    if hasattr(time, 'CLOCK_MONOTONIC'):
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    raise RuntimeError('A suspension-safe clock is required on this platform')


# Policy bounds are runtime-only. Eight amortizes dense certified work while
# returning substantially sooner than a 64-event candidate (see Stage 3E audit).
DEFAULT_BATCH_EVENTS = 8
DEFAULT_OVERLOAD_SECONDS = 120
DEFAULT_OVERLOAD_GRACE_SECONDS = 30


class RuntimeController:
    """One safe resolver step per pump; no private candidate crosses a return.

    Integer nanosecond credit includes all earned but unresolved time. A retained
    request has a finite target and cumulative event/generation limits. Draining
    freezes accrual, not event processing. No pacing state enters the envelope.
    """

    def __init__(self, world, *, clock=active_monotonic_ns,
                 registry=DEFAULT_EVENT_HANDLERS,
                 overload_seconds=DEFAULT_OVERLOAD_SECONDS,
                 overload_grace_seconds=DEFAULT_OVERLOAD_GRACE_SECONDS,
                 max_batch_events=DEFAULT_BATCH_EVENTS, shared=True,
                 execution_state=None):
        from .execution_contracts import SharedExecutionState
        if registry is DEFAULT_EVENT_HANDLERS:
            initialize_runtime_handlers()
        if type(max_batch_events) is not int or max_batch_events < 1:
            raise ValueError('max_batch_events must be a positive integer')
        if overload_seconds <= 0 or overload_grace_seconds < 0:
            raise ValueError('invalid overload policy')
        self.world = world
        self.clock = clock
        self.registry = registry
        self.credit_ns = 0
        self.last_ns = clock()
        self.work = None
        self.refresh = False
        self.closed = False
        self.diagnostic = None
        self.last_result = None
        self.blocked = False
        self.selected_speed = player_speed('Normal Speed')
        self.overload_seconds = overload_seconds
        self.grace_ns = overload_grace_seconds * NANOSECOND
        self.overloaded_since = None
        self.max_batch_events = max_batch_events
        self.shared = shared
        self.execution_state = execution_state or SharedExecutionState()
        self.state = 'PAUSED'
        self.commit_serial = 0
        self.last_pump = None

    @property
    def ratio(self):
        return self.world['simulation']['configuration']['clock_ratios']['NORMAL']

    @property
    def overload_ns(self):
        return self.overload_seconds * self.ratio * NANOSECOND

    @property
    def draining(self):
        return self.state in ('PLAYER_DRAIN', 'OVERLOAD_DRAIN')

    @property
    def processing(self):
        return not self.closed and (self.running or self.draining)

    @property
    def running(self):
        return (not self.closed and self.state == 'RUNNING'
                and self.world['simulation']['clock_state'] == 'NORMAL')

    @property
    def earned_target_utc(self):
        """Whole-second earned horizon, distinct from resolved world UTC."""
        return format_utc(parse_canonical_utc(self.world['simulation']['time_utc'])
                          + timedelta(seconds=self.credit_ns // NANOSECOND))

    @property
    def status_text(self):
        selected = self.selected_speed.name
        if self.state == 'RUNNING': return f'Running — {selected}'
        if self.state == 'OVERLOAD_DRAIN': return f'Catching up — {selected} selected (new pacing paused)'
        if self.state == 'PLAYER_DRAIN': return f'Pausing — draining earned time; {selected} selected'
        if self.state == 'RECOVERED': return f'Paused — Overload recovered; {selected} selected'
        if self.state == 'ERROR': return f'Paused — Runtime error; {selected} selected'
        return f'Paused — {selected} selected'

    def _sample(self):
        now = self.clock()
        if now < self.last_ns:
            raise ValueError('monotonic clock moved backward')
        if not self.closed and self.state == 'RUNNING':
            self.credit_ns += (now - self.last_ns) * self.ratio
        self.last_ns = now
        return now

    def select_speed(self, name):
        speed = player_speed(name)
        if self.closed: raise ValueError('session is closed')
        if self.draining: raise ValueError('Finish draining earned time before changing speed')
        self._sample()
        self.selected_speed = speed
        configure_clock_ratios(self.world, normal=speed.ratio)
        self.refresh = True
        self.overloaded_since = None

    def resume(self, speed=None):
        if self.closed: raise ValueError('session is closed')
        if self.draining: raise ValueError('Finish draining earned time before Resume')
        self.select_speed(self.selected_speed.name if speed is None else speed)
        if self.blocked:
            self.cancel_work()
            self.blocked = False
        set_clock_mode(self.world, 'NORMAL')
        self.state = 'RUNNING'
        self.diagnostic = None
        self.overloaded_since = None

    def _finish_pause(self, recovered=False):
        set_clock_mode(self.world, 'PAUSED')
        self.state = 'RECOVERED' if recovered else 'PAUSED'
        self.overloaded_since = None
        self.diagnostic = ('OVERLOAD recovered: earned target resolved; Resume explicitly'
                           if recovered else None)

    def pause(self):
        """Stop accrual now, then drain the already-earned finite horizon."""
        self._sample()
        if self.draining or self.state in ('ERROR', 'RECOVERED'): return
        if self.work is not None or self.credit_ns >= NANOSECOND:
            self.state = 'PLAYER_DRAIN'
            self.diagnostic = 'Pausing: draining earned time before management/save'
        else:
            self._finish_pause()
        self.overloaded_since = None

    def hard_pause(self):
        """Immediate committed boundary; retain debt in memory, release request.

        Used for shutdown/replacement/error/debug and explicit Advance's existing
        target-replacement policy. A snapshot never serializes the retained debt.
        """
        self._sample()
        self.cancel_work()
        set_clock_mode(self.world, 'PAUSED')
        if self.state != 'ERROR':
            self.state = 'PAUSED'
            self.diagnostic = None
        self.overloaded_since = None

    def close(self):
        self.hard_pause()
        self.closed = True
        self.state = 'CLOSED'

    def cancel_work(self):
        if self.work is not None:
            self.work.close()
            self.work = None

    def management_changed(self):
        self.refresh = True

    def _stop_error(self, message, *, blocked=True):
        self._sample()
        self.cancel_work()
        set_clock_mode(self.world, 'PAUSED')
        self.state = 'ERROR'
        self.blocked = blocked
        self.diagnostic = message
        self.overloaded_since = None

    def pump(self):
        self.last_pump = None
        now = self._sample()
        backlog_before = self.credit_ns
        if not self.processing: return None
        # Preserve the existing rate-normalized backlog/grace policy. A temporary
        # backlog is not overload; processing continues throughout the grace.
        if self.running:
            if self.credit_ns > self.overload_ns:
                if self.overloaded_since is None: self.overloaded_since = now
                if now - self.overloaded_since >= self.grace_ns:
                    self.state = 'OVERLOAD_DRAIN'
                    self.diagnostic = 'OVERLOAD: catching up to earned target; new pacing paused'
            else: self.overloaded_since = None
        if self.work is None:
            if self.credit_ns < NANOSECOND:
                if self.draining: self._finish_pause(self.state == 'OVERLOAD_DRAIN')
                return None
            self.work = begin_resolution(self.world, self.earned_target_utc,
                registry=self.registry, shared=self.shared,
                max_batch_events=self.max_batch_events, execution_state=self.execution_state)
            self.refresh = False
        work = self.work
        before = parse_canonical_utc(self.world['simulation']['time_utc'])
        count = work._completed + work._stale
        progress = None
        try:
            progress = work.step(management_changed=self.refresh)
            self.refresh = False
        except Exception as exc:
            self._stop_error(f'RUNTIME_EXCEPTION: {exc}')
            raise
        finally:
            self._sample()
            after = parse_canonical_utc(self.world['simulation']['time_utc'])
            self.credit_ns -= int((after - before).total_seconds()) * NANOSECOND
            events = work._completed + work._stale - count
            if events or after != before: self.commit_serial += 1
            self.last_pump = dict(events=events, backlog_before_ns=backlog_before,
                                  backlog_ns=self.credit_ns,
                                  authoritative_utc=format_utc(after), state=self.state)
        if self.running and self.credit_ns <= self.overload_ns:
            # Recovery within this unit must reset the grace, even when no next
            # callback arrives until another independently earned burst.
            self.overloaded_since = None
        if progress.finished:
            self.last_result = progress.processing_result
            work.close()
            self.work = None
            result = progress.processing_result
            if not result.succeeded or result.status == 'STOPPED':
                self._stop_error(f'{result.failure.code}: {result.failure.message}'
                    if result.failure else 'Paused by an event', blocked=not result.succeeded)
            elif self.draining and self.credit_ns < NANOSECOND:
                self._finish_pause(self.state == 'OVERLOAD_DRAIN')
            self.last_pump['state'] = self.state
            return result
        return progress.event_id
