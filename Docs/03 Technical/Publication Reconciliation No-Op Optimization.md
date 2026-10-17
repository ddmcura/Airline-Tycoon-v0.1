# Publication Reconciliation No-Op Optimization — Phase 2B

Implementation working tree over `120aa5f5c8d1047750cd29f4c14a5212231945de`.
Final verification completed **2026-10-17, Asia/Singapore**; benchmark observations
were collected on October 16 before the compatibility safeguard.
Scope is Candidate 1 from the Phase 2A design in this chat. The
[Phase 1 report](Engine%20Performance%20Profiling%20Phase%201.md), instrumentation
and raw evidence are preserved. No commit or push is authorized or performed.

## Mechanism and ownership

Scheduling adds the private runtime-only read predicate
`_publication_reconciliation_needed` in
[quarterly_boundary.py](../../game/scheduling/quarterly_boundary.py).
It first calls the existing World State `_plain_authority_tree` predicate.
Full validation accepts some compatibility string-key subclasses; their deepcopy
callbacks can be observable. Such inputs must retain the original copying path.
This conservative admission adds a read-only whole-tree traversal; it does not
remove or replace any full-world validation. It then mirrors the existing
`reconcile_candidate` matching rule: every outstanding
owner/quarter obligation needs a pending QUARTERLY_PUBLICATION with that exact
owner, quarter and current operation revision. Missing coverage returns true;
KeyError/TypeError/AttributeError uncertainty also returns true. No ID allocation,
mutation, callback, persistent field, returned mutable record or cached answer
is introduced. The predicate still requires the freshly validated entry world;
its additional plain-tree admission is not a replacement domain validator.

The common [kernel entry](../../game/simulation/kernel.py) still performs backend
reconciliation first and initializes the publication handler before consulting
this predicate. Only proven complete coverage skips the public publication
reconciler. Public `reconcile`, `reconcile_candidate`, repair construction,
validation and detached commit are unchanged. STALE-event direct reconciliation
also remains unchanged. A stale-only match requires repair; current-plus-stale
or duplicate current events retain the original no-op interpretation, and their
later lifecycle processing remains real ordered/budgeted work.

Strict iteration, Next Event, shared request entry and management refresh use
this same existing kernel function. No certificate, batch, fallback, event
handler, Booking allocation/persistence, provider isolation, backend reconciliation,
schema, template or save format is changed. Real repairs retain their existing
owner-ID allocation order, complete candidate rollback and detached publication.
Save/load still captures complete boundaries and restores a separately validated
paused candidate. No later roadmap behavior or second optimization is included.

The proof obligation is narrow: on a freshly validated world where the predicate
returns false, the original detached reconstruction would generate no events and
publish nothing. Reading that world is synchronous and remains inside the existing
exclusive processing boundary. It does not establish reusable validity across
commands, returns, loads, callbacks or future events.

## Correctness verification

Pre-change baseline:
`.venv/Scripts/python.exe -B -m unittest tests.test_quarterly_boundaries -q`
passes **39 / 78.379s**, exit 0.

Initial implementation verification, before the compatibility correction:
`.venv/Scripts/python.exe -B -m unittest tests.test_publication_reconciliation_noop tests.test_quarterly_boundaries tests.test_quarterly_provider_isolation -q`
passes **63 / 168.553s**, exit 0. A subsequently added explicit backend-before-probe
regression passes separately **1 / 1.915s**, exit 0, using
`.venv/Scripts/python.exe -B -m unittest tests.test_publication_reconciliation_noop.PublicationReconciliationNoopTests.test_probe_observes_new_obligation_from_backend_reconciliation -v`.

Final focused `.venv/Scripts/python.exe -B -m unittest tests.test_publication_reconciliation_noop -v`
passes **18 / 30.578s**, exit 0. The added compatibility-key regression first proved
that the unchanged transaction raises its original deepcopy callback exception
while the initial fast path incorrectly succeeded. The final admission predicate
restores that callback/exception and preserves the unchanged live world.

The 18 new tests compare complete encoded worlds and processing results with the
unchanged public reconciliation path, forced by a test-only predicate returning
true. They cover complete/no-copy identity preservation; unchanged public copying;
missing, wrong-quarter, stale, duplicate and mixed-owner events; deterministic
owner order and IDs/cursors; no cached answer; backend-created obligations;
read-only behavior; invalid/uncertain input; strict/shared/Next Event/refresh;
failure after allocation and candidate-validation rejection; exact paused
load/resume with complete/missing events; publication fences and repeated failed
retries, plus valid compatibility-key copy callbacks. Existing provider mutation/
exception/retained-reference regressions remain.

Final `.venv/Scripts/python.exe -B -m unittest discover -s tests -v`
passes **1,763 tests / 2,423.424s**, exit 0: **1,762 passed, one skipped**. The only
skip is the existing `test_opt_in_component_measurements` diagnostic. All **344**
application/test Python source witnesses match before and after discovery.
Audit-launcher wall time including imports/discovery is **2,437.896s**.
The first full run was deliberately stopped for the compatibility correction:
**493 completed rows, zero reported failures, 1,072.015s, 344 source witnesses
unchanged**, not a full pass. Its log/result/witness files are archived with a
`pre-compatibility-` prefix. Standard discovery was restarted on final frozen
source through the same temporary audit launcher, retaining stdout/stderr and
application/test source witnesses before and after execution.

Final scoped compilation command:
`.venv/Scripts/python.exe -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
passes, exit 0. Scope/whitespace/link verification passes. AST comparison against
HEAD confirms seven original repair/execution/commit functions are unchanged;
excluded production/reference scope also matches HEAD. All three Phase 1 report/
instrumentation hashes are preserved. Seven report-local links resolve. No player
Saves or protected tooling content is accessed.

## Bounded paired benchmark — initial implementation only

**Final implementation latency is not measured.** The measurements below predate
the necessary compatibility admission safeguard. Its additional full-tree read
pass changes the timed path; these numbers cannot be presented as final optimized
timings. The original benchmark deadline had expired before that correctness edge
was found, so no further performance experiment was started or budget renewed.
A separate correctness-only check validates the exact retained Phase 1 source,
asserts the final predicate returns false, and verifies its complete source hash
stays identical; it performs no advancement or timing.

The [new opt-in diagnostic](../../tests/benchmark_publication_reconciliation.py)
uses the exact retained Phase 1 operating source, canonical SHA-256
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`,
75,758,607 bytes, 42,923 initial Bookings, one A320neo/four daily passenger sectors,
seed 17012026. Full fixture construction/configuration remains in Phase 1 and the
[90-day baseline](90-Day%20Quarterly%20Catch-Up%20Baseline.md). Python 3.12.10,
Windows 10 build 19045, existing virtual environment. Tests were not running during
either benchmark worker; background OS/process activity was not controlled.

Fresh sequential processes compare October 2 03:00Z to October 3 03:00Z, 2026,
one explicit request, retaining 100 same-UTC generated children, 10,000 processed
events, existing shared-entry batch settings and deterministic runtime clock zero.
Both modes install the same lightweight imported-alias count/timing hooks, never
recursive copy internals or handler identities. Baseline forces the unchanged
public reconciliation transaction; candidate runs the actual new predicate.
These are lightly instrumented paired timings, not uninstrumented repetitions.

The initial plan was two days each under a **480-second total hard deadline**,
with 220-second worker caps and 150-second cooperative request budgets. When the
first baseline day took 135.699s, the comparison was shortened to the completed
one-day window. The identified baseline worker was stopped during day two at
217.272s supervisor elapsed; private unfinished state was discarded. Its exit
code 4294967295 is an intentional process stop, not an engine failure or a completed
two-day run. Only its completed first-day row is used below; its planned final
audit/save/load was not reached.

The shortened candidate retained the **original deadline**, conservatively capped
at `2026-10-16T15:44:00Z` rather than receiving a renewed budget. It exited 0 after
136.766s total worker lifetime, with final audits/save/load. Both benchmark workers
had exited before full discovery started. No additional performance experiments
or timing repetitions ran, and no 90-day workload was attempted. The final
diagnostic defaults to one day to reproduce the bounded completed comparison.

| Completed one-day measurement | Baseline | Candidate |
| --- | ---: | ---: |
| Advancement wall seconds | 135.698797 | 109.764346 |
| Events | 13 | 13 |
| Publication reconciliation whole-world copies | 1 | 0 |
| Runtime candidate/commit/preview clones | 27 | 27 |
| Full-world validations | 15 | 15 |
| Captured provider whole-world copies | 8 | 8 |
| Predicate calls | 1 forced | 1 actual |
| Predicate inclusive seconds | 0.000010 | 0.000036 |
| Target publication deepcopy inclusive seconds | 4.306560 | 0 |
| Full validation inclusive seconds | 47.916231 | 41.191776 |
| Kernel runtime clone inclusive seconds | 56.976253 | 43.007088 |
| Booking preview clone inclusive seconds | 1.090203 | 0.954233 |

Inclusive operation intervals can overlap; do not add them to infer elapsed
savings. The observed total difference is **25.934s / 19.112%**, but this is only
one pair and substantial time also changes in unchanged validation/cloning.
There is **no certified 19.1% speedup or stable latency improvement claim**, and
this provisional pair additionally cannot quantify final-source latency.
Final-source regression tests demonstrate one discarded whole-world publication
copy avoided per already-satisfied plain common entry, while compatibility and
missing/uncertain repair paths still copy. No per-event copy is removed.

Instrumentation limitation: backend reconciliation was lazily imported after
the alias snapshot in both measured first windows. Its unchanged whole-world
copy is source-traced, not present in these recorded call counts/timings. The
publication target was preloaded and fully captured. The final diagnostic also
preloads backend reconciliation for future runs; no repeat filled the coverage
gap. Overall wall time includes the unhooked work. This limitation does not turn
the captured provider/target counts into a claim about every deepcopy in the world.

Both completed worlds match the historical Phase 1 day-one canonical hash:
`f2639799ac18443c62a85dcab3e613e12adbb5627df2051b19a4367df66091a2`.
Each processes four dispatches, four departures, four Completions and one Booking
checkpoint, without an engine failure/retry or unresolved same-UTC work. There are
43,467 final Bookings, 544 newly added, 65,596 booked passengers, nine completed
flights, 47 journals, 63 history rows and 363 pending events. Complete-world hash
equality includes financial balances, passenger quantities, event IDs/history,
revisions and cursors. Final candidate world validation, lineage/conservation,
aircraft chronology/position, unique settlements and balanced journals pass.

Candidate manual save/load is separately **8.736829 / 7.526957s**, with exact paused
world equality and unchanged source hash. The baseline's interrupted second day
means no paired final save/load or memory improvement is claimed. There was no
new publication event within the measured day; boundary behavior is tested by
regressions rather than inferred from this timing window.

Raw logs/JSON, the adaptive deadline launcher, standard discovery log/result and
source witnesses remain outside the repository in temporary directory
`at-publication-noop-20261016-1536`. No raw worlds/saves/caches are staged or committed.

For a fresh bounded repeat from the repository, using the retained source and a
new external temporary directory:

```text
.venv/Scripts/python.exe -B -m tests.benchmark_publication_reconciliation --source <operating-source-1.json> --root <new-TEMP-directory> --days 1 --deadline-seconds 480
```

## Delivery scope and limitations

Production changes are limited to the private Scheduling predicate and its
conditional call in the common kernel entry. New test/diagnostic files are
`tests/test_publication_reconciliation_noop.py` and
`tests/benchmark_publication_reconciliation.py`. This report,
[boundary specification](Quarterly%20Boundary%20Orchestration.md) and
[Current Development Status](Current%20Development%20Status.md) record the change.
Pre-existing Phase 1 files/status changes and untracked `.venv/` are preserved.

Final-source performance acceptance remains open: a fresh bounded comparison
would be needed to measure the new admission scan's cost. No timing estimate for
that scan is substituted for measurement. The copied matcher now exists in both
the read predicate and unchanged repair
writer. Future changes to reconstruction semantics must keep their equivalence
and adversarial tests intact. No persistent validity certificate or ownership
shortcut is implied. Larger latency, aged-career/fleet memory, publication-event
costs and later optimizations remain unmeasured/unapproved. No commits or pushes.
