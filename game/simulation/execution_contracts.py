"""Runtime-only handler contracts; registration alone grants no certification.

NO_OP/probes retain full per-event validation. Stage 3B payment alone has a
versioned local transition proof and conservative input predicate. Shadow-only probes
are private test fixtures, never a production certification escape hatch.
"""

from dataclasses import dataclass
from enum import Enum


class ExecutionMode(str, Enum):
    STRICT = 'STRICT'
    SHARED = 'SHARED'
    FENCE = 'FENCE'


@dataclass(frozen=True)
class HandlerExecutionContract:
    handler: object
    mode: ExecutionMode = ExecutionMode.STRICT
    version: str = 'strict-v1'
    proof: str = ''
    replay_eligible: bool = False
    supported_schemas: tuple[int, ...] = ()
    shadow_only: bool = False
    capture_transition: object = None
    validate_transition: object = None
    supports_input: object = None

    def permits_shared(self, handler, schema, *, shadow):
        return (self.handler is handler and self.mode is ExecutionMode.SHARED
                and self.replay_eligible and bool(self.proof)
                and schema in self.supported_schemas
                and (not self.shadow_only or shadow))


@dataclass
class SharedExecutionState:
    """Disposable disable latch, reusable across opt-in requests by their owner."""
    enabled: bool = True
    diagnostic: str | None = None

    def disable(self, message):
        self.enabled = False
        self.diagnostic = message
