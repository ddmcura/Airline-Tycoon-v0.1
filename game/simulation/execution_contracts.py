"""Runtime-only handler contracts; registration alone grants no certification.

Stage 3A keeps complete per-event validation even inside shared candidates.
Only the exact kernel NO_OP has a built-in shared contract. Shadow-only probes
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
