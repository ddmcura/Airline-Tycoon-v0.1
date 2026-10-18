# Scoped Completion Production Pilot — Phase 3G

## Retirement — Simplification Stage 1 (2026-10-18)

The Phase 3G production pilot is retired on `codex/simplify-engine-stage1`,
based on checkpoint `2fb3c9457b47b07e561ef6413c8f7394024e971d`.
The user approved this bounded deletion. `--scoped-completion`, session capability
creation/revocation/diagnostics, domain admission/protected execution, stable-root
publication/receipts and private forwarding through kernel/resolver/pacing/shared
requests are removed. Production caller inspection found no other users of
`game/aircraft_operations/scoped_completion.py` or `game/simulation/owned_event.py`.
Both modules and the pilot-only measurement driver are deleted.

The existing strict Completion handler, isolated candidate validation and detached
commit remain. Existing certified shared execution, its strict recovery and optimizer
latch, closed ownership, Candidate 1, and earlier Phase 3B/3D/3F test experiments
remain. Phase 3G tests specific to removed admission/publication faults are retired;
useful differentials, allocation failure/prefix/retry, custom-handler detachment,
equal-UTC, quarterly event and GUI deferred-action tests are adapted to strict
execution in [session regressions](../../tests/test_strict_completion_session.py)
and [GUI regressions](../../tests/test_strict_completion_gui.py).
[Entrypoint coverage](../../tests/test_gui_entrypoint.py) checks supported startup
options without the removed flag.

No persistent field, schema/template, gameplay formula, event limit, pacing,
Booking/Demand/Departure/Finance/publication behavior or save meaning changes.
The [canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract)
and [save contract](Game%20State%20%26%20Save%20Technical%20Specification.md) still
apply. Current commands/results and limitations are in
[Current Development Status](Current%20Development%20Status.md#simplification-stage-1--scoped-completion-retired-2026-10-18).

The remainder of this report is historical pilot evidence. Its activation commands,
production module/test paths and extended-pilot recommendation no longer describe
available execution or next work. No further simplification is implemented here.

Date: 2026-10-18. Working-tree implementation above HEAD
`120aa5f5c8d1047750cd29f4c14a5212231945de`; earlier uncommitted work is preserved.
No staging, commit or push. This report records implementation evidence, not
permission to broaden the pilot or enable it by default.

## Implementation and activation

`Stage1Session(closed_owner=True, scoped_completion=True)` explicitly enables a
session-private, root-bound Completion authority. Passing the pilot option without
closed ownership raises `ValueError`. Defaults remain off. The GUI entry point is:

```text
.venv/Scripts/python.exe -m app.gui --closed-owner --scoped-completion --quarterly-dev
```

Remove `--scoped-completion` to return to closed-owner strict execution. Existing
saves retain the same format and restore paused. No new persistent fields, schema,
template, gameplay formulas, Booking/demand optimization or pacing changes.

The production implementation follows the [Phase 3F proof](Stable%20Root%20Publication%20Proof%20Phase%203F.md)
and [Phase 3D ownership boundary](Private%20Session%20Ownership%20Phase%203D.md).
Production modules do not import test experiments. The existing handler, manifest,
full validator, strict executor, reconciliation and shared certificates remain
authoritative. Candidate 1 publication optimization is preserved.

Files changed for this phase:

- `app/session.py`: configuration, private capability lifecycle, command/runtime wiring,
  detached diagnostics; no new mutable public world/controller/storage interface.
- `app/gui/app.py`, `app/gui/__main__.py`: explicit optional activation.
- `game/simulation/kernel.py`, `resolver.py`, `pacing.py`, `shared_candidate.py`:
  private capability forwarding and committed-event receipt accounting.
- New `game/simulation/owned_event.py`: confined successor preparation, stable-root
  publication, receipt recovery and optimizer-disable diagnostics.
- New `game/aircraft_operations/scoped_completion.py`: domain admission, protected
  read view, confined Completion handler execution and ownership footprint.
- New `tests/test_scoped_completion_pilot.py`, `test_scoped_completion_pilot_gui.py`,
  `measure_scoped_completion_pilot.py`: deterministic differentials, faults, GUI
  integration and bounded accounting measurements.
- This report and [Current Development Status](Current%20Development%20Status.md).

## Admission and strict recovery

Only the live private authority bound to this exact owned root can try the pilot.
It is serialized and non-reentrant. Admission requires the exact default registry
and built-in Completion handler; Schema 9; `QUARTERLY_BACKEND_V1`; a plain, fully
valid authority tree; the selected canonical queue head; valid quarterly lineage;
an operationally locked passenger flight without a result; current operation
revision; matching active operation/Completion/planned aircraft; and the owning
airline's aircraft in flight with no current airport. Existing stale, unknown and
NO_OP handling runs first. Stop callbacks retain strict boundaries. An invalid
intermediate equal-time source refuses scoped admission rather than inserting a
new command-entry reconciliation boundary.

All other event types, ordinary worlds, legacy sessions, custom registries and
disabled authorities use existing strict execution. No handler certification or
shared batch admission has been broadened. Handler candidate validation retains
the full ownership manifest. The footprint narrows financial accounts to cash,
unflown tickets, passenger revenue and operating expenses. Reads are revocable
protected views; quarterly lineage scalar dictionaries are detached for the
existing exact-type validator. There is no new Booking index or fast path.

Precommit errors discard the local candidate and execute the original strict path
once. If strict also fails, its original failure and successful prefix survive;
allocator state remains retryable. If strict succeeds after scoped failure, that
event is counted once, the request reports `OPTIMIZER_DIVERGENCE`, and the existing
shared execution latch is disabled for subsequent requests. Source admission
refusal alone is not a divergence. Close/rebind/New/Load revoke the old capability;
successful new ownership gets a fresh capability, while failed load preserves the
current one. Pause/resume retains the same capability and runtime references.

## Publication and accounting

Accepted outputs alone are deeply detached, compared with a typed witness and
checked for retained mutable aliases. New shallow world/deterministic shells and
nine collection tables form a complete successor; unchanged records remain owned
internally. The full successor is validated. There is no candidate or detached
commit whole-world clone in the eligible transaction.

Publication preserves the outer root and its fixed key set. A shallow five-root
before-image restores partial installation. Fully installed successor references
establish COMMITTED even when the marker or return is interrupted. The private
preparation caches an idempotent receipt; the kernel recovers it before considering
strict replay. Before-images and successor references are released after receipt
classification. Postcommit faults are diagnostic and count the committed event
once through normal Next Event, retained request and paced runtime accounting.

Tests cover partial installation, before-install faults, after-install/pre-marker,
after-marker, receipt-return faults, `KeyboardInterrupt` and a trace-induced
authority-return interruption. A real retained runtime request containing a
preceding strict NO_OP preserves results, event counts, credit, root and controller
references. No nested advancement, extra event reconciliation, request replacement
or deferred GUI action cancellation is introduced.

This uses the Phase 3F serialized, single-recoverable-fault model with uninterrupted
cleanup. Concurrent observers, malicious private-attribute access, process crash,
repeated asynchronous interruption during restoration, and arbitrary interrupts
outside the receipt protocol are not certified.

## Differential and regression verification

Complete typed authoritative trees, canonical serialized bytes, ProcessingResults,
projected rows and allocator state are compared with strict control sessions.
Coverage includes two Completions across requests, request limits, equal UTC,
stale events, Booking checkpoints, dispatch/departure, quarterly publication,
legacy management, selected GUI reads, save/load, close/rebind, retained candidate
references, nested aliases, broken detachment and real successor validation failure.
Fault tests exercise intermediate handler mutation and allocation failure, output
detachment, successor validation, publication preparation, installation and receipt
handling. Financial/passenger/Booking state remains part of the complete-world
oracle and the unchanged manifest/validator gates.

Commands executed with `.venv/Scripts/python.exe -B -m unittest`:

- `tests.test_scoped_completion_pilot -v`: initial 14 pass / 40.065s.
- `tests.test_closed_session tests.test_stage1_runtime tests.test_simulation_resolver.ResolverBoundaryTests tests.test_shared_candidate tests.test_candidate_ownership -q`:
  119 pass / 51.657s.
- Five additional pilot boundary tests: 5 pass / 16.611s.
- `tests.test_quarterly_gui tests.test_closed_session_gui tests.test_gui_cooperative_runtime tests.test_publication_reconciliation_noop -q`:
  73 pass / 66.120s.
- `tests.test_scoped_completion_pilot tests.test_scoped_completion_pilot_gui -q`:
  21 pass / 63.988s, before the final two added pilot tests and GUI flag wiring.
- `tests.test_scoped_completion_pilot tests.test_scoped_completion_pilot_gui tests.test_gui_foundation -q`:
  final **33 pass / 72.258s**, covering all 21 pilot and two pilot GUI tests.

Final `.venv/Scripts/python.exe -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
and `git diff --check` exit zero. Existing test files are unchanged.
Documentation links and new-file whitespace checks pass. A 351-file pre-edit
application/test source hash inventory detects exactly the seven intended existing
source edits listed above; all other 344 witnesses, including Candidate 1 and
earlier ownership/experiment/proof implementations and tests, remain unchanged.
Final Git inspection confirms nothing staged; no commit or push was performed.

Full `discover -s tests -v` was attempted with a fixed 240-second subprocess
budget: stopped at 240.031s, 158 passing rows and no reported FAIL/ERROR. It is
**incomplete**, predates the final two tests/GUI activation, and is not a full-suite
certification. The worker exited. Log: `%TEMP%/at-phase3g-discovery-20261018.log`.
No 90-day benchmark was run.

## Bounded copy and performance evidence

`-B -m tests.measure_scoped_completion_pilot` measures one control-then-pilot pair
on identical ordinary and quarterly fixtures. Control uses the same closed owner
with the pilot off. A separate differential test covers an actual borrowed legacy
session. Acquisition/read gate and explicit oracle exports are outside timing.
Advancement includes unchanged entry reconciliation; complete command adds selected
reads; event time isolates execution. Full validations are instrumented separately.

| Fixture / mode | Candidate / commit world clones | Backend / publication world copies | Full validations | Command incl. selected reads (s) | Event (s) |
| --- | --- | --- | --- | --- | --- |
| Ordinary / control | 1 / 1 | 0 / 0 | 2 | 0.138940 | 0.118032 |
| Ordinary / pilot | 1 / 1 | 0 / 0 | 2 | 0.137179 | 0.117045 |
| Quarterly, 1,176 Bookings / control | 1 / 1 | 1 / 0 | 2 | 0.271613 | 0.115478 |
| Quarterly, 1,176 Bookings / pilot | 0 / 0 | 1 / 0 | 3 | 0.377000 | 0.218222 |
| Retained, 42,923 Bookings / control | 1 / 1 | 1 / 0 | 2 | 8.306342 | 3.933655 |
| Retained, 42,923 Bookings / pilot | 0 / 0 | 1 / 0 | 3 | 9.945917 | 5.556994 |

All three pairs have exact typed-world, canonical-byte and report equality.
Advancement seconds respectively: ordinary 0.138813/0.137062; small quarterly
0.271480/0.376900; retained 8.306162/9.945784. Every mode acquires ownership once,
performs one initial acquisition clone and exports zero full worlds during measured
advancement/reads. Eligible pilot events copy nine existing records, detach ten
output records once, shallow-copy nine collection tables, and retain one five-root
before-image. Lineage reads detach 19 scalar dictionaries in the small fixture,
219 in retained history. Source and successor admission each perform one full
validation; the original command entry gate remains, giving three versus two.

Retained input is the existing external 75,758,607-byte fixture with canonical SHA256
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`.
One existing strict retained request prepares dispatch/departure, stops immediately
before Completion, and closes; only one Completion per mode is measured. Prepared
source SHA256 is `8d4d589e7993da4480535f923f6e70196f69a3ecb261c67f2cafbbdcab440690`.
Both resulting canonical worlds hash to
`472b0dd743359f1c4551abe6e71772a4bc2bd59316395e1d53d6089f34656f01`.
The external source is read only. Successful setup plus pair takes 47.360s inside
the driver (49.422s launcher wall time). Two prior setup attempts ended before a
paired measurement (62.734s and 168.047s): repeated Next Event calls re-entered
equal-time dispatch reconciliation. Using one retained request corrected the
harness; engine reconciliation was not changed.

Lifetime process memory peaks (bytes), before/after each mode: ordinary control
55,701,504/55,701,504 and pilot same; small quarterly control 56,582,144/57,020,416,
pilot 57,020,416/57,020,416; retained control 644,874,240/732,266,496, pilot
732,266,496/732,266,496. These are lifetime peaks including setup and earlier
modes, not isolated per-event allocation peaks. Measurements overlapped some
verification, use one sample, and establish neither speedup nor memory reduction.
The pilot is slower in both eligible timing samples despite removing two clones.
Remaining full validation, backend copying and historical table scanning dominate.
No validation or reconciliation optimization is authorized by this phase.

Machine-readable local evidence is outside the repository:
`%TEMP%/at-phase3g-small-final.json`,
`%TEMP%/at-phase3g-retained-request-20261018.json`, and final focused test log
`%TEMP%/at-phase3g-final-focused.log`. Generated fixtures/logs are not staged.

## Remaining work

Complete the full gameplay suite in a longer validation window, broaden manual GUI
coverage, and repeat isolated measurements before any default activation decision.
No broader event admission, validation reduction or performance claim is approved.

Recommendation: **READY FOR EXTENDED VALIDATION**.
