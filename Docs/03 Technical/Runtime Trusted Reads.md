# Runtime Trusted Reads — Stage 2

Scope: measured read/derivation optimization on Stage 1 baseline
`6c729ff0d1265f6eef2abac8420f8ed69afca5b5`, live origin/master verified before edits.
Authority stays in the [canonical schema](Stage%201%20State%20Schema.md).
Schema **7**, template, save encoding, resolver/kernel transactions and gameplay
outputs remain unchanged. No Stage 3 shared candidate or multi-event commit.

## Ownership and validation

`app.session.Stage1Session` exclusively owns mutations on the single caller
thread. New Game construction and detached validated Load establish a private
`app.owned_reads._OwnedReadViews` context. Successful session management/event
boundaries discard the old epoch; deterministic event dispatch is unchanged.
Explicit advancement begin/end/cancel also discard views after controlled clock
changes. No index participates in a command or event handler.

`session.world` remains the existing borrowed envelope for domain calls and reads;
frontends must not write borrowed rows. Rebinding it revokes trust. Foreign input,
including external root-preserving commits, gets one full validation before a new
read context can be acquired. The context checks session revision, root identity,
strong references and sizes for envelope/world collections and simulation subtrees,
plus exact UTC/clock/target/ratio witnesses. Replacement or revision mismatch clears
it and requires validation. It retains references rather than relying on reusable
object IDs. Failed validation returns no view and retains no read context.

This is exclusive ownership, not a detector for arbitrary illicit deep in-place
writes to borrowed records. Such external input must be rebound and validated;
public arbitrary-world APIs are the supported independent read boundary. No
caller-controlled `trusted=True` switch is introduced. Private rendering helpers
are implementation details of the owner, not public unchecked world APIs.

Public Fleet/Flights/overview/recent-results and public manifest entry points keep
their full validation behavior and diagnostics. Session Fleet/Flights/Finance reuse
the same rendering/manifest rules after the owning boundary. Header and existing
bounded planner reads are unchanged. Both Kivy and terminal consume the shared
session, with no screen changes or duplicate gameplay calculations.

## Derived structures and invalidation

| Structure | Authority/source | Scope and invalidation | Persistence |
| --- | --- | --- | --- |
| Booking IDs by dated flight | Validated bookings and authoritative itinerary flight IDs; existing `rebuild_booking_indexes` | Lazy once per operations-read epoch; sorted immutable tuples in mapping proxies; rebuild on any epoch change | Never saved |
| Next event ID by dated flight | Validated pending flight-owned events; minimum `(UTC, priority, sequence, ID)` | Same epoch; immutable ID mapping; discarded with booking lookup | Never saved |
| Bounded page cache | Same-epoch Fleet/Flights/Finance render output | At most eight pages, key includes view/airline/page; each flight/fleet page max 100, Finance max 10 results/10 transactions; immutable JSON strings, detached decode per return; all pages discarded together | Never saved |

The lookup holds IDs, not cloned authoritative records. Indexed projection
manifests still perform every original relevant-booking lineage, checkpoint,
journal, witness and capacity check, in original booking-ID order. Only unrelated
record lookup is removed. Public manifests and departure/completion handlers
continue their original full scan. The strict candidate currently has no safe
source-bound runtime index capability across its clone/mutations; handler lookup
optimization is deferred rather than adding an unproven hint or changing the
transaction contract. Removing/rebuilding every view gives the same output.

No broad aircraft/schedule/history cache was added: sorting the bounded projection
inputs was not a meaningful measured hotspot. Reference catalog integrity/version
checks remain unchanged: only .081–.085 instrumented seconds per representative
next event, compared with 19.38 seconds in complete validation on Divine Air. The
lost repeated view validations also eliminate their catalog loads without changing
catalog authority or introducing process-global mutable reference state.

## Measurement method and fixtures

2026-10-03, Windows/Python 3.12.10. Opt-in tool:

```powershell
python -B -m tests.profile_owned_reads --fixtures <temporary-fixtures> --output <temporary-results.json>
```

Optional `--compare <before-results.json>` asserts input/view/next-event/Advance
identity against recorded results. Its CLI comparison was smoke-tested on the
unchanged busy-starter fixture.

Fixture JSON was frozen before optimization; setup, hashing, initial copies and
post-validation are outside latency timings. cProfile timings are separate and
include instrumentation overhead. These are single local samples with host-load
variation, not controlled medians or portable thresholds. Some baseline preparation
ran concurrently; event timing differences below are **not claimed improvements**.
No production save was written. The observed fixture is the latest valid Divine Air
autosave loaded paused, at `2026-09-12T12:20:00Z` (input hash
`646c2fb27f0055fab61712573f5debc06376115324357b3c86bf7b8ba62def9a`).
Busy fixtures use existing public PH benchmark builders; aged state processed
14 real days before freezing (not fabricated history).

| Fixture | Aircraft / flights / bookings / results |
| --- | --- |
| Divine Air | 1 / 718 / 21,901 / 117 |
| Busy starter | 1 / 70 / 1,848 / 0 |
| Aged recurring | 1 / 98 / 4,251 / 28 |
| Ten aircraft | 10 / 700 / 8,825 / 0 |

### Views: seconds, before → cold already-owned / repeat owned

The normal New Game/Load proof is outside these owned-view times. The tooling's
first foreign-binding Fleet call still pays a complete validation (.259/.679/.890/
2.314 s after, depending on fixture); foreign input does not bypass the gate.
Cold owned samples explicitly discard derived pages after acquiring validated
ownership. Output dictionaries/lists were compared exactly to frozen baseline.

| Fixture | Fleet | Flights (20) | Finance/recent results |
| --- | --- | --- | --- |
| Divine Air | 3.104 → .00019 / .000035 | 4.668 → .08193 / .000214 | 3.558 → .02677 / .000195 |
| Busy starter | .265 → .00012 / .000029 | .350 → .04028 / .000238 | .229 → .00021 / .000033 |
| Aged recurring | .738 → .00011 / .000027 | .882 → .05265 / .000242 | .821 → .02919 / .000184 |
| Ten aircraft | 1.117 → .00022 / .000043 | 1.475 → .05840 / .000231 | 1.061 → .00028 / .000047 |

Divine Air's three-view profile previously made **3 full validations (33.275 s
instrumented)**, six catalog loads and 30 full booking scans: 657,030 manifest
booking visits. Cold owned reads make zero validations/copies/catalog loads,
one booking-index build (21,901 source records) and just **398 relevant manifest
booking visits**. Its cold indexed manifest work took .100 instrumented seconds
versus 3.837 before; index construction .309 s. Repeated cached reads make no
index rebuild or manifest call. Other cold epochs likewise build once: 588/1,264/
497 relevant manifest visits for starter/aged/ten-aircraft, compared with
36,960/127,530/176,500 full-scan visits before. These visit counts describe the
projection manifest loops, not validation's independent authority scans.

### Retained strict event work: seconds, before → after

| Fixture | Full validation | Next event | One-hour Advance / events |
| --- | --- | --- | --- |
| Divine Air | 3.298 → 2.388 | 7.207 → 6.946 | 10.039 → 11.324 / 1 |
| Busy starter | .250 → .244 | 1.237 → 1.166 | 2.155 → 1.935 / 2 |
| Aged recurring | .718 → .756 | 2.931 → 2.722 | 4.830 → 4.456 / 2 |
| Ten aircraft | 1.002 → .908 | 5.736 → 5.100 | 26.950 → 25.071 / 11 |

Every input, next-event output and Advance output hash matches before/after on
all four fixtures. Single-event full-validation counts remain **2 → 2**; physical
clones remain **2 → 2** for departure and **5 → 5** for Booking checkpoints. The
Divine Air next-departure profile still spends 19.375 instrumented seconds in
validation and 1.416 in cloning; catalog .085 and manifest .107. Those costs
remain dominant. Bulk initialization/final-target and per-event result gates,
NO_OP/stale behavior, failure prefixes, ordering and generation ceilings are not
changed. Read responsiveness is not certification of sustainable Ultra pacing.

### Memory

Cold owned view/index tracemalloc retained/peak bytes, setup/validation excluded:

| Fixture | Retained | Peak | Encoded three-page bytes |
| --- | ---: | ---: | ---: |
| Divine Air | 306,715 | 935,566 | 54,520 |
| Busy starter | 62,634 | 129,740 | 34,519 |
| Aged recurring | 111,339 | 259,701 | 54,992 |
| Ten aircraft | 165,883 | 418,964 | 39,048 |

The existing booking builder temporarily derives additional maps that are then
released. Lookup storage scales with bookings; eight bounded pages do not store
eight worlds. Whole-process lifetime peak before/after was about 482.27 MB in
both sequential benchmark processes; this includes prior clones/fixtures. No
whole-process memory improvement is claimed. Historical state remains untouched.

## Verification and next boundary

Focused ownership tests exercise public rejection, immutable maps, attempted
output poisoning, stale context injection, subtree/root replacement, revisions,
external validated commands, disposal, page bounds, paused save/load/another career,
clock-only changes, session commands, checkpoint/weekly/flight boundaries and real
contract payment/expiry. Readful and read-free paths compare complete envelopes.
The existing resolver oracle covers every Stage 1 strategy and failure fence.

Verification commands/results and native Kivy observations are recorded in
[Current Development Status](Current%20Development%20Status.md). Load creates a
fresh context from validated saved authority; all indexes/pages remain absent
from JSON and schema. No historical output expectations are updated.

Remaining scaling work is the strict transaction validation/copy cost, Booking
prepare/commit duplication/provider purity, and handler-side history scans.
Stage 3 warrants a separate bounded design/approval that explicitly amends the
isolated-candidate contract and proves complete intermediate validity, failure
prefixes and exact equivalence. This implementation stops at Stage 2; no shared
candidate, prefix replay, event aggregation, recovery, threads or offline progress.
