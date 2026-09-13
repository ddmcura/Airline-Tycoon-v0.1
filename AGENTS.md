# Airline Tycoon repository instructions

These rules apply throughout the repository. Narrower instructions must preserve
the canonical architecture and state contract.

## Authority and contextual routing

For persistent state and naming, the approved hierarchy is:

1. [Stage 1 State Schema](Docs/03%20Technical/Stage%201%20State%20Schema.md)
   is the canonical contract.
2. `Data/Templates/template_reference.txt` is its subordinate implementation mirror.
3. Implementation code must follow both; the canonical schema prevails on conflict.

Before implementing a new authoritative persistent field, update the canonical
schema first, then its template mirror. This replaces older instructions naming
the template as the sole source of truth.

Approved architecture defines behavior and package ownership; technical
specifications define domain contracts. Use [Docs/README.md](Docs/README.md)
to locate documents relevant to the task:

- For checkpoint recovery or milestone planning, consult Current Development
  Status, the PH 1.0 roadmap sequence, and relevant Decision Register entries.
- For persistent-state or save changes, consult the Stage 1 schema and relevant
  Game State & Save specifications.
- For domain behavior, consult the owning domain's architecture, technical
  specification, and compatibility contract.
- For new package placement or moves, consult `Data/Templates/foldertree.txt`
  as a selective reference. Approved ownership and the current tracked tree prevail.

The roadmap defines scope and order, not implementation permission. Status is
an implementation snapshot; the Decision Register is an index. Neither replaces
a specification. Historical material tracked under lowercase `docs/`, including
legacy template rules, and legacy code are migration evidence, not authority for
new simulation behavior. Use repository and working-tree evidence for implemented
facts; user authorization defines requested changes, not completed work.

## Authorization and completion

Read-only requests permit no repository changes. A request to fix or implement
a bounded task authorizes that task. Newly designed milestones require explicit
scope approval before implementation; approval may cover schema work together
with implementation. Workflow labels such as DISCUSS, IMPLEMENT, and COMMIT are
optional; natural-language authorization is sufficient.

Within approved scope, finish implementation, debugging, regression fixes,
verification, and necessary documentation without asking again for routine steps.
Stop affected work for unresolved product decisions, scope expansion, conflicting
authoritative contracts, destructive operations not already authorized, or unrelated
changes that cannot safely be preserved. Continue independent authorized work.
Do not begin later roadmap behavior speculatively.

Stage and commit only when explicitly authorized. Push only when explicitly
authorized; commit approval alone does not authorize push. Permission may be
granted in the implementation request and need not be requested again. It applies
only to the specified work, not future tasks or history rewrites. In-scope
completion fixes remain authorized during commit preparation.

## Simulation invariants

- Use canonical field names. For new or changed state, identify it as
  authoritative, derived, runtime-only, UI, or compatibility state; do not
  duplicate authority.
- Immutable internal IDs own relationships. Names, codes, registrations, and
  labels are display values, not foreign keys. `current_focus` and equivalent
  UI selections never determine simulation ownership, processing, or save scope.
- Persistent-state schema, construction, serialization, and validation belong
  in `game/world_state`. Clock and generic event orchestration belong in
  `game/simulation`. Domain behavior belongs in its owning package and changes
  authority through explicit validated boundaries.
- Keep package-specific helpers and domain operations local. Genuinely
  domain-independent cross-package helpers belong in `game/utils`. Cross-package
  callers do not make a domain operation a shared utility.
- Authoritative domain code must not depend on CLI, rendering, or the legacy
  daily tick. Do not reconnect hybrid state, route-owned demand, or direct
  profit mutation as simulation authority.
- Preserve exact whole-second UTC timestamps, stable persisted event ordering,
  and deterministic inputs. Authoritative outcomes must not depend on wall-clock
  pacing, sleeping, frame rate, local time, iteration order, or uncontrolled
  randomness. No offline progress without explicit scope approval.
- Authoritative money uses integer minor units, never binary floating point.
- Preserve compatibility contracts, saved-state meaning, processed history,
  fixtures, and exact witnesses unless an approved change explicitly replaces
  them. Do not weaken approved formulas to satisfy stale expectations; establish
  approved behavior before changing tests.
- Save work must preserve complete event-boundary snapshots, validated separate
  load candidates, the previous valid file on failure, and paused restoration,
  as defined by the Game State & Save specifications.

## Verification and durable memory

Inspect Git status before editing and preserve unrelated changes. Inspect
history, revisions, and divergence when checkpoint recovery or Git work needs
them. Local upstream refs do not establish remote freshness.

Establish a baseline when existing evidence is insufficient to distinguish
pre-existing failures from regressions. Add deterministic coverage for changed
behavior and invariants. Use proportional verification:

- Run focused or affected tests for ordinary source changes.
- Run `python -m unittest discover -s tests` before completing a substantive
  milestone, when shared simulation/state behavior is affected, when regression
  risk warrants it, or when the approved task explicitly requires it.
- For source changes, compile only the explicit application scope:
  `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`.
  Exclude protected metadata and runtime directories; never recurse from the
  repository root.
- For documentation-only changes, validate links, authority, scope, and
  `git diff --check`; do not run the gameplay suite.

Do not repeat unchanged verification solely for commit preparation. Changes,
failures, or unresolved concerns determine reruns.

Update Current Development Status when implementation, verification, limitations,
or the next development step changes. Record actual commands, results, dates,
and verified revision or working-tree scope. Keep it a current snapshot, not a
transcript or source of operational authorization. A documentation-only successor
does not invalidate recorded implementation evidence. Update the roadmap only
for changed scope/order and the Decision Register for durable decisions with
canonical links; do not promote proposals to Approved.

Before completion, inspect the diff and Git status, run `git diff --check`, and
report verification, material remaining work, and actual commit/push outcomes.
Record unresolved work or unrelated changes when they affect continuation.
Do not present pending operations as completed or invent a pending commit's hash.

## Protected files

- Preserve repository-relative source path conventions; do not hardcode
  machine-specific absolute paths.
- Filesystem tests use temporary directories, never the real `Saves` directory.
- Do not commit generated saves, snapshots, caches, temporary files, runtime
  artifacts, or local tooling/editor metadata.
- Do not inspect, edit, delete, or stage `.serena/` contents without a separate
  explicit tooling task.
