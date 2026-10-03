"""Runtime-only 7x pacing; one caller owns all world mutations."""

from datetime import timedelta
import sys
import time

from .handlers import initialize_runtime_handlers
from .kernel import (
    DEFAULT_EVENT_HANDLERS, configure_clock_ratios, iter_events_through,
    set_clock_mode,
)
from game.world_state.timestamps import format_utc, parse_canonical_utc

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


class RuntimeController:
    """Each pump executes at most one complete domain event transaction.

    Credit is simulation nanoseconds and never enters the envelope. An iterator
    retains its original processing limits across pumps and management input.
    """

    def __init__(self, world, *, clock=active_monotonic_ns,
                 registry=DEFAULT_EVENT_HANDLERS,
                 overload_seconds=120, overload_grace_seconds=30):
        if registry is DEFAULT_EVENT_HANDLERS:
            initialize_runtime_handlers()
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
        self.overload_ns = overload_seconds * 7 * NANOSECOND
        self.grace_ns = overload_grace_seconds * NANOSECOND
        self.overloaded_since = None

    @property
    def running(self):
        return not self.closed and self.world['simulation']['clock_state'] == 'NORMAL'

    def _sample(self):
        now = self.clock()
        if now < self.last_ns:
            raise ValueError('monotonic clock moved backward')
        if self.running:
            self.credit_ns += (now - self.last_ns) * 7
        self.last_ns = now
        return now

    def resume(self):
        if self.closed:
            raise ValueError('session is closed')
        self._sample()
        if self.blocked:
            self.cancel_work()
            self.blocked = False
        configure_clock_ratios(self.world, normal=7)
        set_clock_mode(self.world, 'NORMAL')
        self.diagnostic = None
        self.overloaded_since = None

    def pause(self):
        self._sample()
        set_clock_mode(self.world, 'PAUSED')
        self.overloaded_since = None

    def close(self):
        self.pause()
        self.closed = True
        self.cancel_work()

    def cancel_work(self):
        if self.work is not None:
            self.work.close()
            self.work = None

    def management_changed(self):
        self.refresh = True

    def pump(self):
        now = self._sample()
        if not self.running:
            return None
        if self.credit_ns > self.overload_ns:
            if self.overloaded_since is None:
                self.overloaded_since = now
            elif now - self.overloaded_since >= self.grace_ns:
                self.pause()
                self.diagnostic = 'OVERLOAD: paused with unprocessed pacing credit retained'
                return None
        else:
            self.overloaded_since = None
        fresh = self.work is None
        if fresh:
            seconds = self.credit_ns // NANOSECOND
            if not seconds:
                return None
            target = format_utc(parse_canonical_utc(self.world['simulation']['time_utc'])
                                + timedelta(seconds=seconds))
            self.work = iter_events_through(self.world, target, registry=self.registry)
            self.refresh = False
        before = parse_canonical_utc(self.world['simulation']['time_utc'])
        result = None
        try:
            event_id = next(self.work) if fresh else self.work.send(self.refresh)
            self.refresh = False
            result = event_id
        except StopIteration as done:
            self.last_result = done.value
            self.work = None
            result = done.value
        finally:
            finished_ns = self.clock()
            self.credit_ns += (finished_ns - self.last_ns) * 7
            self.last_ns = finished_ns
            after = parse_canonical_utc(self.world['simulation']['time_utc'])
            self.credit_ns -= int((after - before).total_seconds()) * NANOSECOND
        if result is not None and not isinstance(result, str):
            if not result.succeeded or result.status == 'STOPPED':
                self.pause()
                self.blocked = not result.succeeded
                self.diagnostic = (f'{result.failure.code}: {result.failure.message}'
                                   if result.failure else 'Paused by an event')
        return result
