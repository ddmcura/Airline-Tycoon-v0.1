# Contract Payment Shared Certification — Stage 3B

Approved bounded scope, 2026-10-04; baseline
`f44b2790bf02bec2d5ddd4c2bd674ffc902c6b07`, verified against live origin/master.
Authority: [canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract)
and [marketplace specification](Aircraft%20Marketplace%20Technical%20Specification.md).
Schema remains 7. This document records the audit before enabling certification;
implementation verification is recorded in Current Development Status.

## Stage 3D.2 successor — bounded mutation ownership

[Runtime Candidate Ownership](Runtime%20Candidate%20Ownership.md) documents the
separately approved successor. Exact built-in Payment/Departure/Completion receive
one-event write capsules and recursively read-only protected authority. Genuine
predecessor/selected-output proofs remain; protected JSON/alias validity inherits
from fully validated entry plus enforced write isolation and local output checks.
Full protected/alias oracles remain in shadow mode, with strict replay, final full
validation and detached commit unchanged. Memoized read capabilities end before
flush/recovery; they are neither authority nor Stage 2 indexes. Schema stays 7.
Normal session/Kivy/Advance pacing remains strict; no Stage 3E/3F or new certificate.
Earlier dated sections below retain their historical implementation evidence.

## Exact write footprint

The current exact `step5._payment_handler` and its posting/scheduling helpers write:

| Structure | Successful applicable payment |
| --- | --- |
| Selected aircraft contract | `paid_installments += 1`; LTO `principal_paid_minor` and `financing_paid_minor` increase by the current installment; `next_payment_at_utc` becomes the following anniversary or null after final payment |
| Owning airline | `finance_revision += 1`; no other airline field changes |
| Owning accounts | Operating: expense + rent, cash - rent. LTO: assets + principal, expense + financing, cash - principal - financing. All integer minor units; negative cash is allowed |
| Transactions | Exactly one new balanced journal, allocated transaction ID, exact due UTC, USD, description, contract source ID and ordered nonzero entries; no command/delivery fields |
| Event allocator/order | Exactly one successor payment ID/sequence when another installment remains; otherwise no generated event |
| Pending/history | Kernel archives the selected event COMPLETED at its due UTC; removes it from pending; inserts the exact successor where required |
| Simulation | Kernel advances `time_utc` to selected due UTC; order cursor advances only for successor generation |

Principal is base plus one cent for each early remainder installment. Financing
and rent are retained approved pricing witnesses. There is **no debt/liability
posting**, contract/domain revision increment, aircraft ownership/location/status
change, expiry mutation, RNG draw or deferred/external effect. No-op inactive or
exhausted contracts and unsupported historical inputs retain strict execution.

## Validator dependency map and induction

The predecessor must pass full world validation at request entry or the preceding
strict/final batch boundary. Each certified successor must establish:

| Validator/dependency | Local preservation argument |
| --- | --- |
| `validation.py` airline/accounts/journal | Exact selected airline/account records preserve IDs, ownership, currency/category/index membership; integer deltas and balanced exact journal preserve money/ownership/timestamp constraints |
| `aircraft_market_validation.py` contract progress | Exact installment increment and retained pricing prove cumulative principal/financing totals, bounds and final-null next-payment semantics |
| Market journal lineage | Exactly one correctly owned/source-linked payment journal added; previous journals unchanged, and new journal sorts after prior payments; journal count increases with paid count |
| Active-contract topology | Current payment removed, exact successor inserted unless final; the existing sole expiry remains unchanged; owner/revision/priority/payload relationships preserved |
| Kernel event contract | Genuine before-event simulation/pending/history witness; existing records immutable; exact lifecycle, generated IDs, sequence and allocator deltas |
| ID validator | Only transaction/event cursors advance; exact fresh IDs use previous next values, preserving global uniqueness and all other namespaces |
| Booking/fulfilment finance dependencies | Previous referenced journals/results/checkpoints unchanged; airline finance revision only increases by one, retaining historical upper-bound relationships |
| Acquisition/lifecycle/schedules/demand | Source records and every unrelated authoritative subtree unchanged; payment does not alter aircraft or confirmed expiry/horizon |
| JSON/schema/config/UI/metadata | Protected structure witness remains equal; no new persisted field or runtime object |

Final full validation remains mandatory before detached commit. It supplements
the per-payment transition proof and cannot excuse an invalid intermediate state.
The proof uses exact records and actual before-event witnesses, not final-record
inspection alone or a mutated candidate compared against itself.

## Scope boundary

Only the exact built-in Payment callable may receive the versioned certificate.
Custom/replacement callables remain strict. Expiry, Booking and weekly publication
remain fences; Departure, Completion and Rotation remain strict. Session/Kivy
pacing remains strict; no Stage 3C–3F, overload recovery or formula change.

The payment proof belongs in `game/world_state`, with pure payment arithmetic
retained in the aircraft-market package and posting construction in economy.
No payment formulas belong in the generic resolver or `game/utils`.


## Implemented certificate and supported inputs

`game/world_state/payment_validation.py` captures genuine detached selected rows,
allocator and kernel witnesses before handler execution. Expected journal entries
and installment arithmetic reuse pure owning-domain helpers extracted from the
existing handler/posting code. Exact JSON record comparisons distinguish booleans
and floats from integer money/revisions. SHA-256 protected fingerprints cover all
unrelated envelope content, including old journals, pending/history records,
aircraft, configuration, RNG, metadata and UI. Only precisely checked selected
rows/new IDs/kernel clock facts are excluded. Fingerprints are runtime-only and
compare unchanged dependencies; shadow/oracle compares complete worlds without
excluding or normalizing authoritative fields.

After each payment, the proof checks the entire selected contract, airline,
all owning accounts (including unchanged debt/unflown/revenue), exact new journal,
all allocator namespaces, full simulation facts, pending/history topology, archived
selected event and optional generated successor. Earlier payment journals must
sort before the new timestamp/ID, preserving the existing installment-index
validation. Negative cash is valid. Final installments generate no successor;
expiry and ownership remain unchanged until the strict expiry fence.

Eligibility requires ACTIVE remaining installments, revision zero, expected
monthly anniversary/next-payment UTC, priority 20, exact V1 payload, USD owner,
and chronological existing payment journals. Inactive/exhausted, custom/replaced,
unsupported schema/payload/priority/anniversary/history inputs remain strict.
Certificate matching checks actual handler AND capture/validator/predicate callable
identity plus the approved metadata/version; equal-looking callable objects cannot
inherit it. No caller-controlled generic proof registration exists.

The valid predecessor and canonical minimum-event selection ensure no untouched
pending event becomes past when UTC advances. Older history/result timestamps
remain at or before monotonic UTC. Successor due UTC is the next strictly later
anniversary. Time-dependent causal work remains earlier in the canonical queue,
including weekly publication and daily Booking fences. A failed intermediate proof
cannot be repaired by later payments: speculation discards, strict replay reselects
and retains only the genuine successful prefix. Divergence stops and disables via
the existing runtime-only latch. Old Stage 2 epochs cannot see the private finance
candidate and invalidate on detached commit; schema/save format is unchanged.

## Remaining growing-history costs

The conservative proof serializes/fingerprints protected state before and after
EACH payment. Its applicability predicate scans transactions for payment chronology;
the Stage 3A kernel witness also copies and checks retained pending/event history.
These are O(retained state/history) costs, not constant-time local proofs. Batching
reduces whole-world validation and detached clones; it does not eliminate history
scanning or make payments/flight runtime universally scalable. No history/index
optimization or compaction is included. Full validator marketplace timing includes
contract/journal checks but is not a separately isolated finance-only timer.

Repeatable tooling: `python -B -m tests.profile_contract_payment --mode both
--repeats 3`. Setup/maturation/copies/final hashing are outside latency samples.
Counters/proof capture/proof validation/market-validator timers are separate
instrumented runs. Native smoke and exact measurements/results are recorded in
[Current Development Status](Current%20Development%20Status.md).
