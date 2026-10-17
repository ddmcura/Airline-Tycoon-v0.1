# Private Session Ownership — Phase 3D

2026-10-18, Asia/Singapore. Bounded application/session implementation on the
working tree over `120aa5f5c8d1047750cd29f4c14a5212231945de`. Candidate 1,
Phase 3B, profiling evidence and all pre-existing changes are preserved.
No staging, commit, push, schema, save-format, pacing or gameplay change.

Authority follows [Schema 9](Stage%201%20State%20Schema.md), its
[template mirror](../../Data/Templates/template_reference.txt), the selective
[folder tree](../../Data/Templates/foldertree.txt), and the existing
[save contract](Game%20State%20%26%20Save%20Technical%20Specification.md).
Reviewed the Phase 3A and Phase 3C read-only reports in chat
`01a149bf-ed45-7390-aebb-38302d65f47a`, and the retained
[Phase 3B experiment](Scoped%20Completion%20Transaction%20Experiment%20Phase%203B.md).

## Implemented boundary

`Stage1Session(closed_owner=True)` opts into private authority. Default sessions
retain borrowed-world/runtime/storage compatibility. The GUI pilot is explicitly
selected with `.venv/Scripts/python.exe -m app.gui --closed-owner`; it can be
combined with the existing `--quarterly-dev` switch. The terminal stays legacy.

Closed sessions reject reads of `world`, reads/replacement of `runtime` and
`save_store`, and mode replacement. Foreign `world = value` remains an explicit
acquisition operation: complete canonical validation and an exact primitive-tree
check precede one detached copy. Invalid/aliased/compatibility inputs fail before
replacing the current binding. New Game construction and internal SaveStore load
results transfer ownership without an extra session copy. SaveStore already
copies, validates, pauses, revalidates and checks the queue of its separate load
candidate; the returned save metadata contains a separate source world.

Private `_world`, `_runtime`, storage, requests, read contexts and indexes remain
implementation details. There is no public trusted/adopt flag, world-returning
runtime facade, controller reference or callback receiving mutable authority.
The existing no-argument advancement notification remains available. This is an
ordinary serialized Python application API boundary, not a sandbox against
reflection, monkeypatching, private attribute access or unsynchronized threads.

Runtime status uses a frozen scalar `RuntimeView`; no controller, resolver,
execution state or live world appears in it. Existing detached domain queries
remain the read interface. Complete diagnostic serialization is explicit through
`authoritative_bytes()` and counted; `world` never silently copies or exports.
Existing management fingerprint checks still serialize whole state, and saves
retain their complete snapshot copies. These costs were not optimized.

The GUI's five direct world accesses become named draft validation/local-time
operations. WeeklyDraft retains its existing detached complete base and existing
planning/publication protections; this pilot does not narrow its dependencies or
remove its copies. Closed mode admits only built-in drafts and rejects foreign
draft callbacks. Runtime-only draft binding survives ordinary draft copying and
rejects use after career replacement. Quarterly controller operations continue
using existing named queries and owner-issued preparations.

Deferred GUI actions use `(career binding revision, runtime generation)`, not a
runtime/controller reference or a newly allocated status snapshot. Committed
progress/read-cache invalidation does not change that identity. Rebind, runtime
replacement, close and blocked failure revoke or suppress pending actions.

No simulation capability or domain operation was moved to a shared utility.
Strict/shared event transactions, ordering, IDs, budgets, full gates, successful
prefixes and recovery machinery are untouched. Scoped Completion remains test-only.

## Bounded measurements

`tests.measure_closed_session` runs one legacy/closed pair, two actual scheduled
events and selected reads; `--quarterly` repeats that small shape on the existing
quarterly fixture. Setup, constructor acquisition and diagnostic exports are
outside event accounting. These are copy-count checks, not timing benchmarks.

| Per two requests and selected reads | Legacy fixture, both modes | Quarterly fixture, both modes |
| --- | ---: | ---: |
| Kernel candidate/commit clones | 4 | 6 |
| Backend reconciliation whole-world copies | 0 | 2 |
| Publication reconciliation whole-world copies | 0 | 1 |
| Full validation calls in instrumented runtime modules | 4 | 6 |

Closed mode: **one acquisition, one foreign-input ownership clone, zero owner
exports during either pair**. Successive requests do not reacquire ownership.
One deliberate complete diagnostic export afterwards increments exports to one.
New Game plus saved-game Load: two acquisitions, zero added ownership clones;
normal constructor/persistence validation and snapshot copying remain.

Both pairs compare complete decoded authoritative worlds and full reports,
including ProcessingResults and projected event rows: **exact equality**.
The final oracle additionally compares complete canonical serialized bytes,
preserving integer/float distinctions: both measurement commands pass again with
unchanged counts. Final headless ownership tests pass **14 / 9.456s** after this
assertion strengthening; the native GUI code/tests are unchanged from the 17-test pass.
Additional deterministic tests compare cooperative shared advancement, planner
publication/management results and failed-event-prefix/retry results against
legacy sessions. No complete-world differences are waived or filtered out.

Native process lifetime peaks, legacy pair: 36,806,656 → 39,886,848 bytes,
then closed 39,886,848 → 41,918,464. Quarterly pair: 37,535,744 → 40,144,896,
then closed 40,185,856 → 41,996,288. Peaks include fixture setup and both paths;
they do not isolate transaction memory or demonstrate a memory reduction.
The final byte-oracle reruns peak at 41,025,536 bytes (ordinary pair) and
41,402,368 (quarterly pair), with the same lifetime/setup caveat.
No speedup, history-independent cost or 90-day performance claim is made.

## Verification

Commands use the existing `.venv` interpreter and temporary save directories.

- `-B -m unittest tests.test_owned_reads tests.test_gui_cooperative_runtime tests.test_quarterly_gui -q`
  — **71 passed / 120.449s**.
- `-B -m unittest tests.test_stage1_runtime tests.test_owned_reads -q`
  — **40 passed / 94.239s** (overlaps the preceding run).
- `-B -m unittest tests.test_gui_foundation tests.test_gui_weekly_workspace tests.test_gui_schedule_polish tests.test_stage1_weekly_planner tests.test_shared_candidate tests.test_candidate_ownership -q`
  — **139 passed / 90.160s**, including existing strict/shared recovery and
  alias/capability regressions.
- Initial new ownership/GUI set: **14 passed / 11.386s**. Final set adds the
  cooperative shared complete-world comparison; final combined result below.
- `-B -m unittest tests.test_closed_session tests.test_closed_session_gui tests.test_stage1_terminal_harness -q`
  — **34 passed / 29.424s**, including cooperative shared equivalence and legacy
  terminal transcripts. Two final new tests cover quarterly New and blocked GUI actions.
- Final `-B -m unittest tests.test_closed_session tests.test_closed_session_gui -q`
  — **17 passed / 13.887s**, including those two additions.
- `-B -m tests.measure_closed_session` and the same command with `--quarterly`
  — exit 0; counts/equality above.
- `-m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
  — exit 0; compilation excludes protected metadata/runtime directories.

Draft test failures were corrected: the management oracle initially lent its
class fixture to a legacy mutable session; it now copies the fixture. Initial
failure injection targeted a nonexistent helper, then the NO_OP optimized bypass;
the final injection reaches a throwing handler through the actual handler lookup,
mutates only its candidate and verifies exact rollback/retry equality.

Full gameplay discovery is attempted with a fixed 180-second deadline to respect
the approximately 20-minute task budget; the earlier recorded full suite takes
about 40 minutes. An interrupted run is not full-suite certification.
The attempt (`-B -m unittest discover -s tests -v`) stopped at **180.016s** with
**152 passing test rows** and no reported failures/errors. Its log is
`%TEMP%/at-phase3d-discovery-20261018.log`; the child process was terminated and
the launcher exited. This attempt predates the final two test additions.
Final scoped compilation, documentation local-link checks, `git diff --check`
and working-tree/diff review pass. No background test worker remains.

## Files and remaining scope

Application changes: `app/session.py`, new `app/session_ownership.py`,
`app/gui/__main__.py`, `app/gui/app.py`, `app/gui/gameplay.py`,
`app/gui/schedule_builder.py`, `app/gui/weekly_workspace.py`.
Coverage/measurement: new `tests/test_closed_session.py`,
`tests/test_closed_session_gui.py`, `tests/measure_closed_session.py`.
Documentation: this report and the existing Current Development Status snapshot.

Legacy sessions deliberately retain borrowed world/runtime/storage and arbitrary
legacy draft compatibility. Closed sessions fail explicitly for unsupported draft
implementations; there is no automatic unsafe fallback into borrowed authority.
The terminal has not been migrated. Named projections are detached values, so
retained reads can be old but cannot mutate a subsequent committed generation.

Remaining risks: full discovery completion, exhaustive GUI/manual screen coverage,
arbitrary third-party extensions and concurrent access are not certified. Existing
global validation, reconciliation and WeeklyDraft copying remain scaling costs.
The bounded result supports **READY FOR SCOPED TRANSACTION INTEGRATION DESIGN**,
not production scoped execution, default ownership activation or performance
certification. No event transaction redesign is implemented or authorized here.
