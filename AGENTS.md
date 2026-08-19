# Repository Instructions

These instructions apply to the entire repository. A deeper `AGENTS.md` may add
narrower package rules, but it must not contradict the canonical architecture
or schema.

## Authority and scope

Use this order when sources disagree:

1. Current approved architecture in [`Docs/`](Docs/README.md), especially the
   [project foundation](Docs/01%20Core%20Simulation/Project%20Foundation.md) and
   [Game State & Save Architecture](Docs/03%20Technical/Game%20State%20%26%20Save%20Architecture.md).
2. The canonical [Stage 1 State Schema](Docs/03%20Technical/Stage%201%20State%20Schema.md)
   and approved [technical specification](Docs/03%20Technical/Game%20State%20%26%20Save%20Technical%20Specification.md)
   for concrete persistent-state and save requirements.
3. The [Stage 1 roadmap](Docs/03%20Technical/Stage%201%20Implementation%20Roadmap.md)
   for milestone scope and implementation order. A roadmap item is not
   authorization to implement a milestone.
4. The [template rules](docs/template_reference_with_rules.txt) and
   [folder-tree reference](Data/Templates/foldertree.txt) for subordinate naming
   and placement guidance, only where they agree with the sources above and the
   current repository tree.
5. Existing implementation as migration input and characterized behavior, not
   as authority when it conflicts with approved architecture.

The legacy hybrid state example and other material under lowercase `docs/` are
historical or compatibility material only. Do not promote them to authority.

## State, identity, and boundaries

- Update the canonical Stage 1 schema before adding a persistent authoritative
  field. Use its exact vocabulary; never introduce ad hoc synonyms.
- Explicitly classify state as authoritative, derived, runtime-only, UI, or
  compatibility state. Do not duplicate authority across classifications.
- Immutable internal IDs are authoritative. Airline names, aircraft
  registrations, codes, labels, and other display values are not foreign keys.
- `current_focus` and its Stage 1 projection equivalents are UI state only; they
  never select simulation ownership, processing scope, or save scope.
- Authoritative persistent-state schema, construction, serialization, and
  validation belong in `game/world_state`. Simulation clock and generic event
  orchestration belong in `game/simulation`. Scheduling, demand, booking,
  aircraft operations, economy, and other domain behavior belong in their
  owning packages and interact with authority only through explicit validated
  boundaries. The legacy daily tick, hybrid state, route-owned demand, and
  direct profit mutation are non-authoritative migration inputs. Never
  reconnect new simulation work to those legacy authority paths.
- Keep package-specific functions in their owning package. Put only genuinely
  cross-package functions in `game/utils`; do not use it as a dumping ground.
  Authoritative domain code must not depend on CLI, rendering, or legacy
  daily-tick modules.

## Determinism, time, and money

- Persist exact canonical whole-second UTC timestamps. Authoritative outcomes
  must not depend on wall-clock time, sleeping, frame rate, local time,
  dictionary iteration order, or uncontrolled randomness.
- Preserve stable persisted event ordering and deterministic random inputs. Do
  not add offline progress unless a later milestone explicitly approves it.
- Store authoritative money as integer minor units. Never store authoritative
  monetary values as binary floating point.

## Development workflow

- Inspect Git status before editing and preserve unrelated user changes.
- Implement only the explicitly authorized milestone or task; do not begin
  later roadmap behavior speculatively.
- Run the existing baseline tests before major work. Add deterministic tests for
  new behavior and invariants.
- After changes, run the complete standard-library suite with
  `python -m unittest discover -s tests`, then `python -m compileall -q .` and
  `git diff --check`.
- Do not weaken approved formulas merely to satisfy stale tests. Characterize or
  update stale expectations only when the approved behavior is independently
  established.
- Do not commit or push without explicit authorization.

## Files and paths

- Never hardcode absolute machine-specific paths. Follow current repository
  path conventions.
- Treat an absent runtime directory as empty where applicable, and create
  required directories safely before listing or writing them.
- Filesystem tests must use temporary directories, never the repository's real
  `Saves` directory.
- Do not commit generated saves, caches, runtime directories, temporary files,
  or other runtime artifacts.
