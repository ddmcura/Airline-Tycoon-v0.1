# Stable-Root Publication Proof — Phase 3F

2026-10-18, Asia/Singapore. Test-only working-tree experiment over
`120aa5f5c8d1047750cd29f4c14a5212231945de`. Production code, existing test files,
Candidate 1, Phase 3B, Phase 3D and profiling work are preserved. No staging,
commit, push, gameplay activation, schema/save change or pacing change.

**READY FOR PHASE 3G PRODUCTION PILOT**, using the explicit commit-state protocol
and serialized failure model below. This is not production integration or a
claim that arbitrary in-place dictionary operations are atomic.

## Authority and source

Reviewed [canonical Schema 9](Stage%201%20State%20Schema.md), its
[template mirror](../../Data/Templates/template_reference.txt), the selective
[folder tree](../../Data/Templates/foldertree.txt),
[Phase 3B](Scoped%20Completion%20Transaction%20Experiment%20Phase%203B.md),
[Phase 3D](Private%20Session%20Ownership%20Phase%203D.md), the Phase 3C/3E chat
findings, and existing candidate publication/strict/shared recovery code and tests.
All added state is test-only runtime state: preparation ownership/epoch, commit
classification, receipts and counters. No authoritative persistent field is added.

## Beginner explanation and mechanism

The session keeps the same outer ledger. Completion prepares replacement pages
privately, including detached changed records, and validates the whole proposed
ledger. The bridge changes the outer ledger's references to those pages. Runtime
and resolver keep their original ledger reference and therefore see the new pages.

If only some references were installed before a fault, the bridge restores the
five old root references. This is a shallow dictionary of references, not a copy
of the world's records. If all proposed references were installed, the event is
committed even if an exception prevents setting a success flag or returning normally.

The new [test-only bridge](../../tests/stable_root_publication_experiment.py):

1. Accepts only an active built-in Phase 3D closed-owner session.
2. Reuses its already owned world; it does not call Phase 3B's constructor or
   acquire/copy another world. Test-only private-name access attaches the unchanged
   Phase 3B owner implementation to that existing private envelope.
3. Calls the actual unchanged Phase 3B Completion preparation. Its temporary
   private-root swap yields the fully validated successor; the adapter restores
   the experiment's private pointer to the session envelope before returning.
   Session authority has not yet received the Completion changes.
4. Preserves source validation, actual reconciliation, complete manifest work,
   capsule isolation, successor validation and capability revocation. Adds exact
   plain-tree admission plus scoped value/identity checks around output detachment.
5. Issues an opaque preparation bound to bridge epoch, session career binding,
   source read witnesses and original root identities. No public world/capsule
   callback or borrowed successor getter is provided.
6. Uses `dict.update` on exact dictionaries with the same five exact-string keys.
   It never clears the envelope, inserts new root keys, or invokes a caller-supplied
   installer. A private test interception injects partial installations.
7. Classifies the actual installed root identities. Partial installation restores
   the retained roots; full installation is committed. A committed receipt is
   idempotent and stale/foreign unused preparations reject.
8. Notifies committed read/progress state without changing career/runtime binding.
   Notification failure retains the commit and drops stale read contexts.

Neither `Stage1Session._replace_world()` nor `CandidateOwnership.publish()` is
used to install into live authority. No production file imports the experiment.

## Exact atomicity and failure model

The guarantee is externally observable all-or-nothing state at completion of a
bridge operation under a serialized, non-reentrant caller. It is **not** a claim
that every instruction inside installation is indivisible.

The installation window invokes no external read callback. Existing roots remain
alive in the shallow before-image throughout installation and classification.
The tests deliberately replace the installer with partial root writes followed
by a failure. All one-root and two-root permutations restore the exact previous
root identities and complete typed bytes before returning `ROLLED_BACK`.

| Fault | Classification and behavior |
| --- | --- |
| Before preparation; detachment; successor validation; publication preparation | No Completion commit. Discard speculative work. |
| Immediately before installation | No Completion commit; old roots remain/restored. |
| Partial installation, including different root orders | Restore the five references; no record-level undo or world rollback clone. |
| Full installation followed by an exception before the commit marker | `COMMITTED`, determined from actual root identity. No retry. |
| After marker, during bookkeeping or notification | Commit persists, with a diagnostic. No uncommitted-failure result. |
| Interruption at the publication return boundary | Caller recovers `status(preparation)`; the cached committed receipt prevents replay. |

Preparation/receipt status is part of the protocol. A future production caller
must consult it before considering fallback after an ambiguous interruption.
The convenience `complete()` retains the preparation internally and consults
status when a nested publication call is interrupted.

Fault coverage includes RuntimeError, a KeyboardInterrupt after complete
installation, and reached line/return tracing faults. Recovery assumes it can
finish without a second asynchronous failure. Concurrent/reentrant observers,
deliberate private mutation, process termination and repeated asynchronous failure
inside classification/restoration are not certified. If those stronger guarantees
are required, this proof does not establish them; fail-stop/ownership-handle work
would need separate scope. Normal execution never exposes the private injection hooks.

## Reference and integration evidence

[Focused tests](../../tests/test_stable_root_publication.py) compare complete typed
worlds and full ProcessingResults with unchanged strict execution. They assert:

- Outer session envelope, RuntimeController.world and retained request._world
  have the same identity before and after publication.
- Untouched private Booking records remain shared. Changed record/container
  identities are detached. Mutating retained speculative results or previous
  changed records cannot change committed authority.
- Protected capsule reads expire. Old committed read-context witnesses cease
  matching; normal session queries acquire the fresh context. Public UI pages
  remain detached. Private `_OwnedReadViews` objects are not public capabilities.
- Equal-valued cross-record mutable lineage aliases reject before publication.
  A deliberately broken detacher returning its writable input also rejects,
  even though value bytes are identical.
- Foreign, duplicate, stale, close/rebind and advancement-begin preparations have
  explicit behavior. Reusing a committed token returns its receipt, never reruns
  Completion. Reusing a rolled-back token does not install again; retry prepares anew.
- Reconciliation's real successful repair prefix survives a later allocation
  failure and matches strict execution. A subsequent explicit retry matches the
  strict event ID, allocator and complete world.
- Two scoped Completions share one session ownership, interleaved with ordinary
  session strict/shared advancement. A real temporary manual save/load validates
  and restores the same complete world paused.

The retained-runtime test creates an actual paced request and yields a preceding
NO_OP, keeping RuntimeController.work alive. A test-only interception at the
existing event executor runs the bridge for the selected Completion. It also
injects a fault after installation and before the marker. The bridge reports
committed; existing request accounting records the event once, retains its root
reference, finishes with two completed events and exactly matches control world
bytes and the complete request ProcessingResult. The normal session pump performs
its own commit notification; the adapter's duplicate notice is suppressed in this
test. No engine, event selection, budget or pacing implementation is changed.

This executor interception is a proof harness, not a production integration API.
Calling the bridge beside an active request without that request's accounting is
not certified. Phase 3G must put publication and receipt handling inside the
existing event/accounting boundary. It must not blindly retry a post-commit fault.

## Copy and diagnostic accounting

Final-source [bounded accounting driver](../../tests/measure_stable_root_publication.py):
one existing **1,176-Booking** fixture, one real Completion, strict control and
selected detached session reads. Whole-world clone hooks are independently
instrumented; this does not rely on zero-initialized bridge counters.

| Work | Preparation + publication + selected reads | Publication + selected reads only |
| --- | ---: | ---: |
| Whole-world event candidate clones | 0 | 0 |
| Whole-world detached-commit clones | 0 | 0 |
| Other kernel world clones | 0 | 0 |
| Experiment ownership/export clones | 0 | 0 |
| Backend reconciliation world copies | 1 | 0 |
| Publication reconciliation world copies | 0 | 0 |
| Full validations | 2 | 0 |

Additional observed work: **nine existing record copies**, **ten detached output
records**, **one scoped output-pack detachment**, **nine shallow collection-table
copies**, **19 lineage read copies**. The successor also has the existing Phase 3B
shallow envelope/world/deterministic shells and simulation/allocator copies.
The bridge adds **one five-reference root before-image** and **one five-reference
root observation**. Normal success performs one installation and zero restorations.

The session has one initial foreign-input acquisition/copy outside the command,
no ownership reacquisition, and zero automatic complete-world exports. Two complete
typed oracle serializations are explicit harness work outside timing. The initial
Fleet read gate is outside timing; publication rebuilds the existing private read
context, and measured selected reads add no full validation or world export.

Final sample preparation/publication times: **0.2980755 / 0.0000877 seconds**.
Native lifetime peak: **54,370,304 → 57,417,728 bytes**, including fixture setup
and strict control. An earlier draft accounting invocation produced the same
counts; final source was remeasured after added detachment checks. These are small
instrumented diagnostics, not a timing campaign, isolated transaction-memory
measurement, speedup result or retained-history scaling claim. No 90-day run.

## Verification and preservation

Commands use the existing `.venv/Scripts/python.exe`:

- Initial boundary baseline: `-B -m unittest tests.test_scoped_completion_experiment.ScopedCompletionTests.test_success_complete_world_and_independent_postings tests.test_closed_session.ClosedSessionTests.test_successive_requests_exact_results_worlds_and_copy_counts -v`
  — **2 passed / 4.829s**.
- Initial proof command `-B -m unittest tests.test_stable_root_publication -v`
  — **30 passed / 73.285s**: 13 initial proof tests plus all 17 original Phase 3B
  tests, discovered because the fixture class was initially imported directly.
  The import now uses its module, avoiding that accidental extra discovery.
- `-B -m unittest tests.test_stable_root_publication tests.test_closed_session tests.test_candidate_ownership.ReadBoundaryTests tests.test_shared_candidate -q`
  — **73 passed / 57.642s**, including the then-current 15 proof tests and existing
  session/reference/strict/shared recovery regressions.
- Intermediate strengthened proof set — **16 passed / 27.975s**.
- Strengthened `-B -m unittest tests.test_stable_root_publication -q`
  — **17 passed / 30.992s**, including the broken-detachment rejection and the
  actual retained-runtime post-commit fault.
- Final same focused command — **18 passed / 29.413s**, adding silent partial
  installation detection and checking the final shared read-context cleanup.
  **No test failures in these runs.**
- `-B -m tests.measure_stable_root_publication` — exit 0; final counts and exact
  authoritative-world/ProcessingResult equality above.
- `-m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
  — exit 0, explicit application scope only.

Full gameplay discovery is not required for this test-only task and was not run.
SHA-256 preservation witnesses cover **348 pre-existing application/test files**;
all remain unchanged. Final diff/status, documentation local links, new-file
whitespace and `git diff --check` are checked before completion. No workers remain.

Files added: this report, the test-only bridge, its tests and accounting driver.
Current Development Status receives a new current evidence section; prior content
is retained. No other existing repository file is edited.

Remaining production work is the separately approved Phase 3G pilot: replace
test-private coupling/interception with a sealed internal API, preserve the receipt
protocol within request accounting, keep explicit opt-in/strict fallback, and
complete production integration verification. Global validation/reconciliation and
shallow historical table costs remain. Closed ownership stays opt-in.
