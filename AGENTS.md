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

### Fresh-thread startup

Every fresh Codex task must recover context from the repository:

1. Read this `AGENTS.md` completely and any applicable deeper instructions.
2. Read [Current Development Status](Docs/03%20Technical/Current%20Development%20Status.md).
3. Read the development roadmap in [Stage 1 Implementation Roadmap](Docs/03%20Technical/Stage%201%20Implementation%20Roadmap.md), starting with its PH 1.0 release sequence.
4. Consult the [Decision Register](Docs/03%20Technical/Decision%20Register.md).
5. Inspect `git rev-parse HEAD`, `git status --short --branch`, recent history,
   and branch/upstream divergence. Local upstream refs are not proof of remote freshness.
6. Read only the canonical specifications relevant to the requested milestone;
   consult `Data/Templates/foldertree.txt` before creating or moving files.
7. Summarize the committed checkpoint, local changes, verification evidence,
   and authorized scope before proposing work.

Conversation history never overrides committed repository facts. Current user
authorization may request changes to those facts, but does not make proposed
work implemented. Status is a snapshot; the roadmap is planning; the decision
register is an index. None replaces the canonical architecture or schema.

### Authorization modes

These are repository workflow labels, not Codex application settings. Explicit
natural-language authorization is sufficient; magic keywords are not required.

- **DISCUSS:** Read-only inspection, analysis, planning, and recommendations.
  No repository edits. Use this when implementation has not been authorized.
- **IMPLEMENT:** Implement the explicitly approved bounded specification and
  verify it. Do not stage, commit, or push without separate authorization.
- **COMMIT:** Verify the intended implementation and update status documents
  with durable facts. Stage only intended files when committing is authorized;
  commit and push only to the extent explicitly requested. A commit request
  alone does not authorize a push or additional implementation.

Never silently expand a milestone. Preserve legacy compatibility unless the
approved specification explicitly changes it. Keep package-only helpers in
their owning package; genuinely cross-package helpers belong in `game/utils`.

For new schema fields, update the canonical Stage 1 schema first, then update
`Data/Templates/template_reference.txt` before implementation. The template is
a subordinate mirror, not a competing schema authority.

### Shutdown and durable recovery

- In IMPLEMENT or COMMIT, replace stale facts in Current Development Status
  when this task changes them; never append a transcript. Record the actual
  verification command, result/count, date, and revision or working-tree scope.
  If not run, say so; never equate test inventory with passing tests.
- Update this existing roadmap for changed scope/order and index newly approved
  durable decisions with canonical links. Do not promote proposals to Approved.
- Record remaining work, limitations, intended uncommitted files, protected
  paths, and the immediate next step. In DISCUSS, report proposed updates only.
- Before an authorized commit, identify the last verified implementation hash
  and describe the pending commit separately. Never invent a commit's own hash
  inside its contents. On the next startup, reconcile the snapshot with HEAD;
  a documentation-only successor need not invalidate implementation evidence.
- Inspect the final diff and Git status, preserve unrelated changes, and report
  validation, remaining gaps, and actual commit/push outcome. Never claim a
  clean tree or successful push without checking.

- Inspect Git status before editing and preserve unrelated user changes.
- Implement only the explicitly authorized milestone or task; do not begin
  later roadmap behavior speculatively.
- Run the existing baseline tests before major work. Add deterministic tests for
  new behavior and invariants.
- After source-code changes, run the complete standard-library suite with
  `python -m unittest discover -s tests`, then `python -m compileall -q .` and
  `git diff --check`.
- For documentation-only tasks, validate links, authority, scope, and the diff;
  do not run the gameplay suite unless explicitly requested.
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
- Treat `.serena/` as protected local tooling metadata. Do not inspect, edit,
  delete, or stage its contents without a separate explicit tooling task.
