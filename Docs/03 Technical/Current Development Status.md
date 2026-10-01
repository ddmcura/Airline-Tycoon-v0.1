# Current Development Status

Last updated: **2026-10-01**. Current snapshot, not operational authorization.

## PH 1.0 Kivy GUI foundation

The approved Kivy foundation now uses `app.session.Stage1Session` as the one
application owner shared by `app.gui` and the retained `app.terminal` developer
harness. The historical terminal session import remains a compatibility
re-export. The modern GUI launches with `python -m app.gui` under a
Kivy-compatible Python environment. Development verification used Python
3.12.14 and Kivy 2.3.1; the host's default Python 3.14 environment has no
compatible installed Kivy wheel. `requirements.txt` now specifies Kivy.

The graphical title creates PH Normal careers or loads current airline career
saves, with manual/autosave recovery and bookmark choices. The game shell shows
airline/CEO/base, cash, exact UTC and paused/7x state, with in-place status
refresh. It offers pause/resume and explicit next-event/day/duration/UTC
advancement. Fleet, flights/Bookings/operations and finance are read-only
derived views. Manual save and bookmark create/load/delete use the existing
validated persistence; unsaved return/exit/load offers Save, discard or cancel.
No authoritative schema field or save format changed. The GUI remains a single
world owner with no simulation worker thread; explicit bulk work yields after
complete event transactions. Flight projection paging is a bounded derived
view extension. The old Kivy title stub no longer invokes legacy gameplay.

Verified on the complete working tree based on `20cc38c` on 2026-10-01:
focused GUI tests passed **7 tests**; the earlier focused GUI, runtime, save
and terminal set passed **58 tests in 124.366 s**; the final
`python -m unittest discover -s tests -q` passed **613 tests in 484.746 s**
using the isolated Python 3.12.14 environment with `requirements.txt` installed.
`python -m compileall -q app game tests main.py make_snapshot.py settings.py
test.py` exited 0, and `git diff --check` passed. A Kivy event-loop smoke run
started and stopped. In a newly created PH career, 30 GUI pump callbacks using
an injected fake clock measured **40.173 ms median, 100.315 ms maximum** on
this host. This small-world smoke measure is not a 50-aircraft GUI performance
gate or a mobile measurement. Existing complete-event transaction latency can
still delay UI response until its boundary.

The next bounded GUI gameplay slice is aircraft acquisition, market research
and weekly scheduling actions. Step 8 deterministic engine checks can proceed
independently; the sustained graphical player run needs those GUI actions.
This foundation does not add cabin editing, aircraft sale, advanced maintenance,
AI, a map or extra player speeds.

## PH 1.0 Normal starting-capital correction

New Philippines careers remain `Normal` and start with USD 300,000,000
(30,000,000,000 USD minor units) under reference-data version
`stage1-philippines-v1-recovery-2026-10-01`. This matches the legacy Normal
amount for integrated player-simulation verification; it is not final economy
or difficulty balancing. Existing careers retain their saved cash. Schema 7,
aircraft prices, acquisition and economy rules, and difficulty selection are
unchanged. The next PH roadmap step remains Step 8 integrated player-simulation
verification.

Verified on the working tree based on `464cf04` on 2026-10-01:
`python -m unittest tests.test_stage1_terminal_harness.Stage1BootstrapTests
tests.test_stage1_aircraft_acquisition.AcquisitionTests
tests.test_step7_save_load -q` passed **37 tests in 65.554 s**;
`python -m unittest discover -s tests -q` passed **606 tests in 454.297 s**;
`python -m compileall -q app game tests main.py make_snapshot.py settings.py
test.py` exited 0. The career bootstrap test checks the Normal difficulty,
revised reference version, and exact cash account balance.

## PH 1.0 Step 7 save/load completion

The schema-7 whole world now saves durably at completed transaction boundaries.
An opaque file-level career ID keeps each airline game separate even if display
names collide or change. One explicit current manual save, three rotating
autosaves and player-named, explicitly deletable bookmarks belong to the career.
Autosaves use the first of 15 active real minutes or seven simulated days of
ordinary continuous runtime; nearby triggers coalesce. Explicit bulk advancement
does not produce intermediate weekly saves. There are no before-action or exit
autosaves. Unsaved exit and return-to-title paths offer Save, discard or cancel.

Loads check container integrity, run adjacent migrations on a detached candidate,
validate the complete world, rebuild the event queue index, and replace the active
world only on success. Restoration is paused at the exact saved UTC second, with
no offline progress. Schemas 2–7 migrate automatically; schema 1 requires its
matching approved foundation snapshot and otherwise reports a compatibility
failure. Newer schemas and unversioned legacy saves are not loaded. A previous
valid recovery copy protects replaced files. Autosave and bookmark loads do not
change the manual file; a newer autosave offers a recovery choice.

The verified implementation scope is the working tree based on
`fcb6aa73a9e10e3f01d7c738e26bad08662f3251`. The focused save, terminal and
runtime run passed **51 tests in 109.607 s**. After the final source changes,
`python -m unittest discover -s tests -q` passed **606 tests in 454.170 s**.
The application-scope `python -m compileall -q app game tests main.py
make_snapshot.py settings.py test.py` exited 0. Local links in the six changed
technical documents passed target validation, and `git diff --check` passed.
A representative 50-aircraft scheduled PH world with 102 pending events and
672,851 serialized JSON bytes saved in **0.203 s** and loaded in **0.171 s**
with exact world equality on this host. This measures the bounded scheduled
workload, not a multi-week processed-history scale claim.
The next PH roadmap step is Step 8 integrated player-simulation verification.
Disk layout, save serials, integrity metadata, autosave timers and recovery
copies add no authoritative world field or schema version.

## PH 1.0 Step 6 completion

Simple routine maintenance expenses are implemented as save schema 7 on the
working tree based on `768556c56a52d3c4600e4037f02e11836d40791d`.
The versioned dimensional classification reference covers all 20 catalog
models plus the legacy A320-200 starter. New departures freeze the authoritative
timing-snapshot distance or the shared geographic fallback and the actual
aircraft's A–G class/rate. Successful completion, including deadheads, adds
`ceil(distance_m × class_factor_minor_per_km / 1000)` to the unchanged base
operating cost. The single existing fulfilment journal posts the combined
operating expense and cash cost; per-flight projections and the terminal show
the components separately. Negative cash, replay, event-step/bulk/7×
equivalence and existing lifetime counters are covered by regressions.

Detached schema 6→7 migration adds the maintenance configuration only. V1
historical results and journals remain unchanged; locked V1 flights finish on
V1 rules, while only new departures receive Step 6. There is no backfill or
new maintenance account/event. The next PH roadmap step is Step 7 save/load.
Scheduled checks, condition deterioration, facilities, downtime, failures,
reserves, PBH and monthly maintenance settlement remain deferred.

| Step 6 verification, 2026-10-01 | Result |
| --- | --- |
| `python -m unittest tests.test_step6_maintenance tests.test_stage1_aircraft_acquisition.AcquisitionTests.test_booking_fulfilment_mixed_fleet_deadhead_and_replay -q` | 11 passed in 131.210 s |
| `python -m unittest tests.test_step6_maintenance -q` after detached-reference hardening | 10 passed in 108.609 s |
| `python -m unittest discover -s tests -q` after detached-reference hardening | 593 passed in 451.683 s on the final source state |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| Changed-document local link-target check | Passed across 6 documents and 122 local targets |
| `git diff --check` | Passed before commit preparation |

The full suite used bundled CPython 3.12.14 and isolated, test-only
`tabulate 0.10.0`/`tzdata 2026.3` outside the repository. An earlier run
without those pinned dependencies had two import/version failures and one
schema-5 fixture failure; the fixture now removes schema-7 configuration
when reconstructing schema 5, and the final full run passed. No dependency
copies are part of this working tree.

## PH 1.0 Step 5 completion

PH 1.0 Step 5 is implemented as save schema 6. The terminal exposes rotating
operating-lease and lease-to-own offers, operating renewal/return, and persistent
used-aircraft listings. Contracts use automatic monthly integer-USD postings that
may make cash negative. Lease-to-own principal and financing are separate;
ownership and ordinary configuration rights transfer after final settlement.
Used purchases retain the exact listed airframe identity, age, block hours,
cycles, condition and registration.

Marketplace rotation, offer inventory and background seller listings are
seed-keyed deterministic authority. Unaccepted lease offers expire; unsold used
listings persist. Lease scheduling is bounded by the confirmed contract horizon,
with payment before flight lifecycle and expiry/return after flight completion at
equal timestamps. Schema-5 migration preserves legacy aircraft and history
without inventing lifecycle facts. Exact formulas, constants, worked settlement
examples and future boundaries are in the
[Aircraft Marketplace Technical Specification](Aircraft%20Marketplace%20Technical%20Specification.md).

The independent review corrected a condition double-counting risk in the first
settlement draft: cancellation equity now uses age-depreciated value while
condition is charged exactly once as restoration. It also added collision probing
for used registrations, current-event cardinality validation to prevent duplicate
payments, allocator checks for embedded airframes, and a genuine schema-5
migration fixture rather than a partial version-number downgrade.

Final verification evidence for this combined Step 4 and Step 5 working tree is
recorded below. The verified scope is the complete working tree based on
`e5c079cc98f931d74456662129ee2661c39d1abb`, including the previously completed
Step 4 increment and Step 5. The next roadmap milestone is Step 6, simple
versioned maintenance expenses. Advanced maintenance, manufacturer installments,
active AI fleet sales, physical delivery/return, banking/loans, bankruptcy rules
and lease-to-own refinancing remain future work.

| Step 5 completion verification, 2026-09-20 | Result |
| --- | --- |
| `python -B -m unittest discover -s tests` | 583 passed in 324.598 s |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| 50-aircraft live 7× profile, 60 seconds | 60.949 active s; 416 simulation s; raw 6.825×; 10.644 s retained credit; accounted 7.000×; max pump 12.395 s; 4 events; no overload |
| World State validation-first and Simulation-first import probes | Both passed |
| Bulk versus same-timestamp-draining stepped marketplace rotation | Exact authoritative equality |
| Changed-document local Markdown target check | Passed across 9 changed/new documents |
| `git diff --check` | Passed before final commit preparation |

The full suite used bundled CPython 3.12.14 with temporary, test-only
`tabulate 0.10.0` and pinned `tzdata 2026.3`; neither dependency copy is in the
repository. The live profile used the production 43-airport/1,806-market world,
50 aircraft and production runtime controller. Raw clock progress waits for
atomic transactions; retained credit accounts for the difference and is not
discarded.

## PH step 4 working-tree checkpoint

Continuous runtime is implemented against clean starting revision
`e5c079cc98f931d74456662129ee2661c39d1abb` on `master`. The bounded 1/10/50
workloads and retained-credit live gate now pass on the documented host; PH step
4 is complete in this uncommitted working tree. Unpaced throughput alone is not
the acceptance evidence. Live `git ls-remote --heads origin
refs/heads/master` on 2026-09-17 confirmed origin still at that base. No new commit
or push was performed for this increment; the changes remain uncommitted.

The terminal now supports `/resume`, `/pause` and `/status` throughout management
navigation, with an input-only worker and one owner of world mutations. Resume
uses the existing NORMAL ratio of 7. Monotonic active uptime excludes suspension;
fractional credit, input queues and iterators are runtime-only. Schema 5 remained
the authoritative version at that Step 4 checkpoint; Step 5 subsequently adds schema 6.
Kernel iteration yields only between complete events and preserves processing
limits across yields. Manual bulk advancement finishes paused. Live Ctrl+C
requests a boundary stop. Weekly drafts revalidate explicit legs against current
authority; strict purchase-preview freshness and idempotent replay are unchanged.
See the [runtime contract](Continuous%20Runtime%20Technical%20Specification.md).

| Verification, 2026-09-17 | Result |
| --- | --- |
| `python -B -m unittest discover -s tests -p test_stage1_event_kernel.py` | 53 passed, 1.509 s |
| `python -B -m unittest discover -s tests -p test_stage1_aircraft_catalog.py` | 14 passed, 9.974 s |
| `python -B -m unittest discover -s tests` | 569 passed, 486.483 s |
| `python -B -m unittest discover -s tests -p test_stage1_runtime.py` | 21 passed, 83.437 s, including late input-only EOF fix |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 after final source/profiler edits |
| Changed-document link/anchor check | Passed, including final status update |
| `git diff --check` | Passed |
| Actual Windows terminal smoke test | Clock advanced inside Aircraft Catalogue; explicit Pause froze 00:10:10Z through Main Menu and Airline Overview; exit 0 |

The first full run (564 tests) found one controller-binding regression in sessions
whose world was replaced directly. Lazy rebinding fixed it; the subsequent full
run passed. Isolated kernel tests also exposed an existing planning-validation
import cycle, fixed with a local import without changing validation semantics.
The late EOF fix prevents live exit confirmation waiting on an exhausted input
worker and passed the final 21-test runtime run. Tests used bundled Python 3.12.14 and
the existing temporary test-only `tabulate 0.10.0` dependency via `PYTHONPATH`.
No machine-specific dependency path or runtime artifact is committed.

The 2026-09-18 audit follow-up added clean UTC-range failure coverage, historical
purchase-delivery validation coverage and a regression ensuring checkpoint
preparation executes shopping once. Focused runtime (21), acquisition (19) and
shopping (29) suites passed; an allocation rollback regression exposed during
the optimization was corrected before the final 573-test pass. Final whole-suite
and compile results are recorded below.
The World State planning-validation import cycle was rechecked in both import
orders; the existing local import is the minimal correction and no package move
or broader dependency redesign was needed.

| Audit completion verification, 2026-09-18 | Result |
| --- | --- |
| `python -B -m unittest discover -s tests` | 573 passed, 262.030 s |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| World State planning-first and Scheduling-first import probes | Both passed |
| Changed-document local link/anchor check | Passed |
| `git diff --check` | Passed |

## Runtime performance evidence

Host: Windows 10 build 19045, Core i5-10400 @ 2.90 GHz, 12 logical CPUs,
approximately 16 GB physical RAM, CPython 3.14.6. These are observed desktop
measurements from the 2026-09-18 acceptance rerun.

Commands: `python -B -m tests.profile_ph_runtime --fleets 1 10 50 --days 1`
and `python -B -m tests.profile_ph_runtime --fleets 50 --days 1 --live-only --live-seconds 185`.
The fixture uses the full 43-airport/1,806-market pack, test-only acquisition
funding, one daily return pair per aircraft across five destinations, six days
of Booking and one operating day. All domain processing is production code.

| Aircraft | Processing seconds | Resolved events/history growth | Events/s | Max transaction | Unpaced capacity | Peak process working set | Serialized bytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 12.179 | 11 | 0.903 | 2.199 s | 49,658x | 48,689,152 B | 1,608,264 |
| 10 | 108.044 | 47 | 0.435 | 8.257 s | 5,598x | 91,869,184 B | 6,089,645 |
| 50 | 660.077 | 207 | 0.314 | 14.056 s | 916x | 139,325,440 B | 12,137,356 |

At 50 aircraft, p95 yielded-transaction latency was 3.437 s. The bulk profiler
hit the generated-event limit once and explicitly continued; the live controller
does not silently retry. Authoritative history and yielded-event count both grew
by 207. Peak memory
includes profiler snapshot copies, not just a single live world.

The 185-second live run crossed the busy final Booking midnight and departures.
Successive raw authoritative-clock windows were **6.822x, 7.007x and 6.994x**.
Overall: 185.254 active seconds, 1,267 simulation seconds advanced, raw **6.839x**,
nine resolved events, 29.775 simulation seconds of retained credit, max pump
11.513 seconds and no overload. Advanced time plus retained credit was 1,296.775
seconds, or **7.000x accounted pacing**. Each window likewise accounts to 7x;
the raw clock can lag only at complete atomic boundaries and later catches up.
No clock-credit discard, event omission, formula change or validation bypass was
used. This satisfies the retained-credit sustained gate defined by the runtime
contract; raw timestamp-only rate remains a latency diagnostic, not a loss metric.

The current overload threshold is 120 active seconds of
backlog persisting for another 30 seconds; the measured 14.056-second burst is
well below it. Overload pauses visibly and retains credit. Input can still wait
for the current transaction. Profiling confirmed redundant preparation: the
checkpoint first ran shopping only to discover inventory revisions, then allocation
immediately reran the same shopping work. Preparation now derives the exact
inventory witness from its validated allocation result. Nested commands reuse an
already validated caller boundary only through private flags and retain their own
authoritative mutation/final validation boundaries. Atomicity, deterministic
results, public invalid-world rejection and rollback coverage remain intact.
Whole-world validation/copying remains the main future scale limitation; broad
redesign was not needed for this milestone.

An exploratory seven-operating-day run completed at one aircraft: 41 events,
127.425 seconds processing, max transaction 13.125 seconds. The denser ten-aircraft
run was stopped before completion to prioritize the bounded 1/10/50 comparison.
No larger-fleet or multi-week sustained-runtime claim is made. The architectural
thousands-of-aircraft objective remains future scale work, not tested capacity.

## Previous completed acquisition checkpoint

PH 1.0 step 3, basic new-aircraft acquisition, is implemented and verified.
Verification base: `8d67ab0c2883247d304f6c622ab780b7a547c764`, the completed
catalog checkpoint (historically 531 tests). The tree began clean on `master`.
Results below cover the acquisition source/tests in this working tree; Git history
identifies the resulting commit. This pre-commit snapshot invents no commit hash
or push outcome. Documentation-only successors do not invalidate source evidence.

On 2026-09-16, `git fetch origin master`, local divergence inspection and live
`git ls-remote --heads origin refs/heads/master` confirmed the remote still
matched that base, with 0/0 local divergence before the milestone commit.

| Verification command | Result, 2026-09-16 |
| --- | --- |
| `python -B -m unittest discover -s tests -p test_stage1_aircraft_acquisition.py` | 18 passed in 48.598 seconds |
| `python -B -m unittest discover -s tests` | 549 passed in 349.439 seconds |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| Local Markdown link/anchor validator over changed/new documents | Passed |
| `git diff --check` | Exit 0 |

Tests used bundled Python 3.12. The full run used the existing temporary test-only
`tabulate 0.10.0` dependency on `PYTHONPATH` with approved external execution
access. The initial run exposed missing sandbox dependency access and two stale
terminal expectations (the formerly unavailable purchase message and catalog-only
import guard); those were corrected without changing approved gameplay formulas.
No machine-specific dependency paths or tooling artifacts are committed.

## Implemented and available

The state/schema, immutable IDs, deterministic clock/events and dated publication
foundation supports compact Model 4 demand, market-pack lifecycle, direct-Economy
Booking, timed fulfilment and finance. The in-memory terminal exposes the complete
schedule-to-Booking-to-flight-to-finance loop. PH recovery supplies 43 active
commercial airports, 1,806 directional markets, selectable starting base, market
research, versioned air suitability and destination-only tourism.

`python -m app.terminal` starts a paused session with a free 180-seat A320-200.
Weekly Scheduler supports one-way chains, explicit return/positioning, custom
local times, day copy, undo, bounded repeat, Monday-week views and atomic
publication. It validates unpublished recurrences without extending the actual
publication window. Quick Rotation remains the starter compatibility path.
Explicit next-event, day, positive-duration/multi-day and exact UTC-target
advancement exist. PHP/EUR conversion remains presentation-only.

Option 11 browses the immutable 20-model aircraft catalog. Option 12 provides
manufacturer/model selection, delivery choice from existing airline bases/hubs,
price/remaining-cash preview and confirmation. One purchase creates one parked
individual aircraft immediately, posts a balanced cash/aircraft-assets journal,
and leaves time unchanged. Exact-balance purchases are valid. Stale/tampered
previews reject; exact successful-command replay does not create a second asset.
Candidate failures preserve IDs, money, RNG and all other authority.

Schema 5 adds compact purchased-aircraft configuration and acquisition journal
provenance. Explicit 4-to-5 migration changes only schema version; existing
starter/published/booked/processed history is not backfilled or rewritten.
Delivery sets physical location separately from the already-required home base.
PH registrations use a seeded expanded numeric namespace with deterministic
collision probing, independent of immutable aircraft identity.

Purchased aircraft use installed maximum Economy capacity, catalog cruise speed,
scalar-range eligibility and versioned V2 timing. Total stand turnaround is counted
once: 30 minutes for turboprops/regional jets/narrowbodies and 45 for widebodies;
taxi remains separate. Starter V1 activity timing and historical witnesses remain
unchanged. Deadheads retain zero passengers/revenue and existing fixed costs.
Fleet display/selection uses derived pages; finance shows aircraft assets and
purchase journals separately from operating contribution.

See the [acquisition specification](Aircraft%20Acquisition%20Technical%20Specification.md),
[canonical schema](Stage%201%20State%20Schema.md),
[Decision Register](Decision%20Register.md) and
[roadmap](Stage%201%20Implementation%20Roadmap.md).

## Limitations and remaining work

- Authoritative file save/load is implemented above. A schema-1 file without a
  matching approved foundation snapshot remains a reported compatibility failure;
  unversioned legacy import is outside PH 1.0 Step 7.
- Runtime controls and the retained-credit performance gate are implemented above.
  Individual event and management transactions can block input until their
  completed boundary.
- Leasing, lease-to-own, used listings and simple routine maintenance are
  implemented. Manufacturer queues/delays, banking/loans, full depreciation and
  editable cabin configuration remain deferred.
- Reconfiguration remains deferred. Before it is implemented, its contract must
  preserve historical installed-configuration witnesses rather than validate old
  purchases, plans or operations against only the aircraft's latest configuration.
- No AI, connecting Booking, detailed disruptions, graphical planner or editing
  of already-published plans. Legacy modules remain migration evidence.
- The approved PH 1.0 Normal starting capital is USD 300 million for newly
  created careers, matching the legacy Normal amount. Reference-data version
  `stage1-philippines-v1-recovery-2026-10-01` distinguishes this scenario
  correction. Existing careers retain saved cash. This is not final economy or
  difficulty balancing; acquisition tests supply funds independently. Current
  new games offer their one established base for delivery.
- PH scalar range is a temporary gameplay ceiling, not a full-load guarantee.
  Airport/runway compatibility is deferred: physically unsuitable airport/aircraft
  combinations are not yet rejected. Payload-range/cargo/weight remain future work.
- Fulfilment cost revision 1 remains simplified and unchanged for purchased models.
  Production-date metadata remains incomplete and never gates availability.
- Compact records, derived pages and expanded registration avoid small fleet caps;
  world copying/hashing/validation, registration scans and fleet sorting remain
  scale limitations. Interactive performance at tens of thousands of aircraft has
  not been established and needs profiling before broad runtime integration.

## Next action

**PH Step 8 integrated verification** follows Step 7. Exercise multiple weeks of
scheduling, Booking, operations, finance, all acquisition modes, maintenance,
runtime controls, multi-day advancement and reload as one player-operated
scenario. AI follows the verified PH player simulation. This status does not
authorize the next implementation increment.
