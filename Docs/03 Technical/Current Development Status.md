# Current Development Status

Last updated: **2026-09-16**. Current snapshot, not operational authorization.

## Checkpoint and verification

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

- No authoritative file save/load: exiting loses the session. In-memory state
  validation, JSON-compatible serialization and explicit migrations exist.
- No continuous 7x runtime or interactive running-session pause/resume controls.
- No leasing, lease-to-own, used sales, manufacturer queues/delays, financing,
  maintenance expenses, depreciation or editable cabin configuration.
- No AI, connecting Booking, detailed disruptions, graphical planner or editing
  of already-published plans. Legacy modules remain migration evidence.
- Starting-capital balancing is unchanged. The current PH scenario has USD
  1 million; legacy Easy difficulty has a 500-million setting. Neither observation
  establishes a newly approved design target. Acquisition tests supply funds
  independently. Current new games offer their one established base for delivery.
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

The next roadmap milestone is **PH 1.0 step 4: continuous deterministic runtime
at 7x, manual pause/resume and integration of existing multi-day advancement**.
Develop and approve its bounded contract before implementing it. It must keep
wall-clock pacing runtime-only, retain ordered whole-second commands, profile
realistic PH workloads and prove equivalent continuation across pacing/stepping.

Leasing/lease-to-own/used aircraft, simplified maintenance, safe disk save/load
and integrated PH verification follow in the existing provisional order. AI
follows the verified player-operated PH simulation. This status authorizes none
of those future increments. No unrelated changes were found in final review.
