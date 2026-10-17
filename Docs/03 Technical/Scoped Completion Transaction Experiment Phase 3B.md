# Scoped Completion Transaction Experiment — Phase 3B

**2026-10-17, Asia/Singapore. Test-only feasibility experiment.** Working tree
over `120aa5f5c8d1047750cd29f4c14a5212231945de`; existing Candidate 1, profiling
evidence and unrelated changes are preserved. No production code, canonical
schema, template, save format, gameplay or pacing changes. No commits or pushes.

**Recommendation: CONTINUE TEST-ONLY INVESTIGATION.** Scoped Completion actually
executes and commits in this experiment. It is not the older strict-only fallback
shell. Tested rollback/reference isolation and two-Completion private-owner reuse
pass. This does not establish a production ownership API, local validation
certificate, long-history scaling, or a reliable latency/memory improvement.

## Authority and design context

[AGENTS](../../AGENTS.md), [canonical Schema 9](Stage%201%20State%20Schema.md),
[template mirror](../../Data/Templates/template_reference.txt) and
[selective placement reference](../../Data/Templates/foldertree.txt) govern.
The Phase 3A investigation is the preceding chat report; no standalone repository
copy was supplied. Its central distinction is retained: a small write footprint
does not establish a small complete invariant/read footprint.

Relevant evidence includes [Phase 1 profiling](Engine%20Performance%20Profiling%20Phase%201.md),
[Candidate 1 final verification](Publication%20Reconciliation%20Final%20Performance%20Verification.md),
[ownership capsules](Runtime%20Candidate%20Ownership.md),
[earlier Completion counterexamples](Hybrid%20Quarterly%20Completion%20Feasibility.md),
[shared recovery](Runtime%20Shared%20Candidate%20Infrastructure.md), and the
[rejected provider isolation trial](Quarterly%20Runtime%20Benchmarking.md#stage-3g-b26--provider-isolation-trial-rejected-on-safety-2026-10-13).
No earlier negative result is relabelled as solved through selected facts alone.

## Implemented boundary

[Test-only owner](../../tests/scoped_completion_experiment.py) validates a plain,
alias-free complete input and clones it once into private authority. It accepts
only the default registry/exact built-in Completion binding and no caller
callbacks. It never registers with production or exposes a borrowed world.
Snapshots are separately counted full detached exports.

Each attempt retains full source validation and the actual kernel quarterly
reconciliation before canonical queue selection. A repair is an independently
committed prefix, exactly as in strict Next Event. It admits only Schema 9,
`QUARTERLY_BACKEND_V1`, non-stale built-in passenger Completion with a locked
flight and no existing result. Unsupported boundaries return explicit refusal;
the caller can invoke the separately counted unchanged strict fallback. Refusal
may follow a real reconciliation repair and is not a promise to undo that prefix.

The experiment reuses `CandidateOwnership` and local writable tables, with a
test-local protected-read adapter. Initial trials exposed a real compatibility
gap: exact quarterly lineage validators reject the ordinary read-only dictionary
views. The adapter returns fresh detached plain scalar lineage dictionaries;
all other protected dict/list values remain revocable recursive read capabilities.
These read projection copies are counted. No validator/type predicate is relaxed.
This adapter uses private capsule internals and is intentionally not a public API.

The unchanged built-in handler and kernel handler/lifecycle primitive execute on
the capsule. No arbitrary handler receives the private base. Full manifest
reconstruction remains; no frozen-ID membership shortcut or new index is used.

### Copied and shared data

The observed small fixture copies **nine existing writable records**:

- One dated flight, aircraft, active operation, selected pending event and airline.
- Four account records: cash, unflown tickets, passenger revenue, operating expenses.

The footprint also permits one new transaction, result and terminal event. The
active operation and pending row disappear, leaving **ten detached output records**.
Simulation and allocator structures are copied too, including the complete current
operation-revision map. Before-event kernel witnesses add their scoped copies.
The nine-record metric does not count these structures, nested objects or lineage
read projections, and is not a claim of nine total allocation operations.

Checked outputs are deep-copied as one scoped pack, then inserted into a prospective
plain envelope. Affected collection dictionaries are shallow-copied; unchanged
rows and untouched collections share nodes only between successive PRIVATE roots.
They share nothing mutable with the constructor input or exported snapshots.
Table copying is pointer/topology copying, not isolation by itself. Recursive
protected reads, privately copied writable records and detached outputs provide
the isolation. Ordinary dictionary reconstruction still costs O(table key count).

Full successor validation checks this prospective complete world, including
aliases, unrelated history, Booking membership, journals and UTC-dependent rules.
Return objects are prepared and capabilities revoked before the single private
root assignment. Any earlier exception/failed gate discards the unpublished
successor. There is no live-world undo journal and no incremental in-place
publication into the authoritative private root.

Retained writable capsule references refer to pre-detachment objects. Retained
protected reads expire, and detached lineage projections cannot mutate authority.
No private candidate crosses into the application/session/save API. The prototype
is an ordinary Python API boundary, not protection against deliberate reflection,
monkeypatching or concurrent unsynchronized access.

## Correctness evidence

[Seventeen focused tests](../../tests/test_scoped_completion_experiment.py) cover:

- Exact complete typed-world and ProcessingResult equality against strict Next;
  detailed reference validation, passenger/Booking/itinerary conservation and
  alias freedom.
- Independent account deltas, exact journal entries, integer operating and frozen
  maintenance cost equations, allocator movement, event cursor, aircraft cycles
  and flight seconds. These assertions do not use the cost/settlement constructors
  as their expected-result oracle.
- Failure after transaction allocation/insertion and result insertion; line-trace
  injections after each of four balance postings, airline/flight revision writes,
  aircraft status, lifecycle counter and active-operation deletion. Each line-trace
  injection asserts that its intended write was actually reached.
- Failures before handler, after handler/history resolution, before validation and
  before publication; failed real full validation; exact unpublished-state rollback
  and explicit successful retry.
- Mutation through protected nested reads, mutation of detached lineage copies,
  retained writable/result references, expired read capabilities, and detached
  exported snapshots.
- Equal-valued cross-record output lineage aliasing (unchanged typed result bytes
  still reject), source aliases, protected-root replacement and unapproved inserts.
- Missing/additional manifest membership and unrelated invalid history rejected
  by the complete entry gate; callbacks/custom registries/compatibility keys
  refused without invoking them.
- Canonical equal-UTC priority/fallback, stale corruption rejection or unsupported
  stale admission, real reconciliation-created IDs, and repair-prefix preservation
  when Completion fails after allocation.
- Actual shared-facade comparison (`shared=True`; quarterly Completion remains
  strict there), temporary SaveStore paused round-trip, and two Completions in
  one owner with an intervening unchanged strict dispatch/departure fence.
- Instrumented zero event candidate/commit whole-world clones in a successful
  scoped attempt, while explicitly observing the retained backend world copy.

The equal-UTC test first tried separate Next Event calls around a preceding NO_OP.
Stopping after that NO_OP at arrival UTC leaves a state rejected by the next entry
gate; the test now correctly exercises the original through-boundary strict
fallback for the entire equal-UTC group. No production behavior was changed to
accommodate this experiment, and this case is not admitted as local Completion.

Rollback and reference isolation are demonstrated for these cases. They are not
universal proofs across all handler/helper variants, interrupts, callback protocols,
or session lifetimes. Existing full gates and the original engine remain necessary.

## Small bounded measurement

Only after focused correctness passed, the
[opt-in measurement](../../tests/measure_scoped_completion_experiment.py) ran one
small strict-then-scoped instrumented pair on the existing deterministic
**1,176-Booking** fixture. No large retained fixture, fleet or 90-day benchmark.
The first invocation's output was lost to an orchestration serialization error;
one repeat captured durable evidence. This was not a timing search or repetition
campaign. Recorded JSON: `%TEMP%/at-scoped-completion-phase3b-20261017.json`.

| Inside complete command timer | Strict | Scoped |
| --- | ---: | ---: |
| Seconds | 0.300920 | 0.281640 |
| Event candidate/commit whole-world clones | 2 | 0 |
| Ownership/export whole-world clones | 0 | 0 |
| Backend reconciliation whole-world copies | 1 | 1 |
| Publication reconciliation whole-world copies | 0 | 0 |
| Full validations | 2 | 2 |
| Inclusive validation seconds | 0.198617 | 0.186619 |

Owner construction, outside the command timer, took **0.144806s** and made one
full ownership clone. The separately counted complete export after timing made
another full clone. The scoped command copied nine existing records, detached
ten output records, and made **19 scalar-lineage read copies**. Existing copied
record JSON payload was **8,663 bytes**, a payload proxy only; simulation, allocator,
witnesses/read projections and Python allocation overhead are additional.

Complete worlds and ProcessingResults matched. Native process lifetime peak
working set was **54,722,560 bytes** before/after both commands. Setup and both
paths share that lifetime high-water mark; it is not isolated transaction memory
or evidence of reduced memory. Counters/timers add overhead, order is fixed, and
there is only one retained pair. **No reliable latency improvement is claimed.**

### Can ownership be amortized?

**Yes within this deliberately closed test owner:** two scoped Completions use
one initial detached ownership clone. Private roots share unchanged authority;
expired capabilities and detached exports prevent borrowed mutation. Intervening
dispatch/departure execute strictly and keep their normal copies. No initial
ownership clone is rebuilt to resume the same owner after that fence.

**No claim of copy-free commands or history-independent cost:** each Completion
still has one backend reconciliation whole-world deepcopy, two full validation
gates, a retained Booking scan, scoped simulation/revision-map copies and affected
dictionary pointer copies. Source validity is never inferred from the owner ID,
revision, selected rows or an old validity flag. Reconciliation, full gates and
the manifest scan remain unresolved scalability costs. An application session
cannot presently inherit this closed-owner lifetime merely by setting a flag.

## Verification and limitations

Executed on the working tree, using existing `.venv` Python:

- `.venv/Scripts/python.exe -B -m unittest tests.test_scoped_completion_experiment -v`
  — **17 passed / 48.019s**. Subsequently strengthened tests were rerun below.
- `.venv/Scripts/python.exe -B -m unittest tests.test_scoped_completion_experiment.ScopedCompletionTests.test_reconciliation_order_shared_facade_and_save_load tests.test_candidate_ownership.ReadBoundaryTests -v`
  — **9 passed / 5.469s**, including explicit shared-mode coverage and eight existing
  read-boundary regressions.
- `.venv/Scripts/python.exe -B -m unittest tests.test_scoped_completion_experiment.ScopedCompletionTests.test_nested_output_alias_rejected -v`
  — **1 passed / 2.783s**, strengthened to require rejection of an equal-valued alias.
- `.venv/Scripts/python.exe -B -m unittest tests.test_scoped_completion_experiment.ScopedCompletionTests.test_rollback_after_allocator_and_record_writes -v`
  — **1 passed / 3.526s**, with explicit reached-stage assertions for journal/result
  insertion faults.
- Earlier combined new/old run: **42 tests / 63.581s**, 41 passed and one new
  equal-UTC test errored; all **26 existing hybrid counterexample regressions
  passed**. The corrected equal-UTC test passed in the 17-test run. Earlier draft
  failures exposed the lineage-view compatibility and detached-projection test
  assumptions, both corrected; they are not presented as passing runs.
- `.venv/Scripts/python.exe -B -m tests.measure_scoped_completion_experiment`
  with output captured through `Tee-Object` to the external JSON — exit 0;
  complete-world equivalence and copy accounting pass.
- `.venv/Scripts/python.exe -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
  — exit 0. Compilation scope excludes repository metadata/runtime directories.

No full gameplay discovery: this is isolated test-only machinery, with focused
failure injection and relevant existing regressions inside the approximately
20-minute budget. No long benchmark, production optimization or current certificate
change. The 42,923-Booking source and historical growth curve are not measured.
Generalized reference-type compatibility, worst-case memory, asynchronous/session
observers, production flush/return integration, broad fault coverage and end-to-end
benefit remain open. Full local validation replacement is explicitly out of scope.

Files added: the test-only owner, safety tests, measurement driver and this report.
Current Development Status receives a current evidence entry; earlier evidence
and Candidate 1 are preserved. Final diff/status review, `git diff --check`, new-file
whitespace and report local-link checks pass. The production diff remains the
pre-existing Candidate 1 change. Future production integration requires separate approval.
