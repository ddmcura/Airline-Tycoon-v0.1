# Paid Bidirectional Route Establishment — Quarterly Stage 3G-A

Approved 2026-10-11, baseline `668a646fd6deef0ecc15c20b3831f6ff32908c18`.
HEAD, upstream, freshly fetched origin/master and live master matched; tracked
tree/index were clean. `.venv/` and archival stashes are preserved.
This is the route-establishment prerequisite to quarterly Stage 3G, not the
older runtime scalability stage with a similar name. It does not activate
default quarterly careers or change AT-041's 50-aircraft Ultra 1800× gate.

Authority: [Schema 9](Stage%201%20State%20Schema.md#paid-bidirectional-route-establishment--stage-3g-a),
[template mirror](../../Data/Templates/template_reference.txt),
[route architecture](../02%20Gameplay/Market%20%26%20Route%20Management.md),
[Base/Hub architecture](../02%20Gameplay/Base%20%26%20Hub%20Management.md),
[quarterly GUI](Quarterly%20Planning%20GUI.md),
[backend authority](Quarterly%20Backend%20Consumer%20Cutover.md), and
[safe snapshots](Game%20State%20%26%20Save%20Technical%20Specification.md).

## Approved fee and eligibility

Players establish an airport pair before planning passenger services. One payment
activates both directional connections; it creates no schedule, flight, Booking,
demand, aircraft obligation or positioning movement.

`fee_usd = base_fee × (1 + distance_km / 5000) × (1 + 0.02 × N)`.
Domestic base is USD 25,000; international base USD 75,000. Country IDs determine
classification. Distance comes from the existing authoritative market-distance
helper shared by Model 4 and Scheduling, quantized to metres; Kivy calculates none.
The user explicitly approved nearest-cent **half up** and attribution to an owned
**Operating Base or Hub**, without granting Hub privileges. N counts each active
paid pair attributed there once; reverse direction does not increase it. No cap.
Attribution stays with the established pair; transfer is not part of this workflow.

Both directional markets and two distinct passenger-eligible airports must exist.
Current UTC date respects inclusive opening/exclusive closure. Selected attribution
must be an existing owned Base/Hub. Starting-country domestic rights remain;
country-access purchasing and international capability progression have no current
production authority and are not invented here. International fee arithmetic is
tested, but this PH workflow cannot purchase foreign permission implicitly.
Aircraft range, scheduling timing/airport profiles and published chronology remain
their owning commands' responsibilities; route purchase is not execution readiness.

## Audit, atomic command and finance

Legacy `game/route_management/core.py` writes the old active-airline route map,
recalculates legacy distance/demand and charges no authoritative journal. Its hub
selector uses old Hub dictionaries. There is no usable canonical closure command.
Those helpers are migration evidence and remain untouched. Existing low-level
`add_connection` provides immutable directional identities; legacy rotations may
create them, but cannot provide paid-pair attribution or transaction authority.

The new Route Management quote/apply boundary is available only to explicit
quarterly careers. Quotes are immutable runtime values, bind the complete source
fingerprint excluding UI state, and consume no IDs or cash. Session issuance uses
exact object identity, requires a paused completed boundary, and is revoked on
New/Load/rebind. Apply independently validates source, recomputes all intent/fee/
cash facts, stages a whole-world candidate, validates it, creates and validates a
detached second copy, and compares source authority again before exposure.
The existing quarterly transaction implementation is unchanged.

Existing active status in either direction rejects a purchase. Compatibility
connections lacking paid provenance cannot be rewritten silently. Insufficient
cash, forged/stale quotes, invalid attribution/endpoints and any staging/validation
failure leave authority, accounts, journals and cursors unchanged. Retrying the
same domain payment command returns its prior connection without charging again;
session confirmations are consumed on success. A reused command ID with changed
intent rejects. No worker, timer or alternate operational writer is introduced.

World State constructs/validates optional provenance on the canonical direction
(origin airport ID sorts first), pointing to the reverse connection and all payment
transaction IDs. Both statuses must agree. Economy posts one balanced expense/cash
journal and increments the existing finance revision. The canonical connection ID
owns payment lineage; airport codes are display values. Existing account codes,
allocated transaction IDs and integer USD minor amounts are reused. Route rights
are a non-resellable entry expense; no profit or cash-only GUI mutation exists.

## Closure, reopening and persistence

Close Route uses the same fresh quoted session boundary. Future/current draft
memberships, unexpired published commitments and unfinished operational rows block
closure. Players must use existing scheduling commands to remove draft membership;
published commitments cannot be cancelled by closing a route. Historical references
remain valid. Closure atomically sets both statuses CLOSED and records exact UTC,
without refund; it removes the pair from N. Reopening pays anew, restores both
statuses, retains connection IDs and appends immutable payment provenance.

Manual saves and Load use existing complete-world snapshots, previous-file safety,
separate validation and paused restoration. No schema-version bump, save converter,
legacy route rewrite or default mode enrollment. Deleting provenance, orphaning a
receipt, mismatching directions/statuses, altering fee witnesses or removing career
authority rejects at the full trust boundary.

## Player workflow

In a saved quarterly career, ordinary `python -m app.gui` exposes Research's
**Route Pair**, **Create Route**, and **Close Route** columns in the existing
horizontally scrolling table. Select origin/destination; choose attribution when
multiple owned Bases/Hubs exist. Confirmation shows the quoted USD fee, market
distance, active pair count and both unlocked directions. Cancel changes nothing.
Purchase refreshes session reads and scheduling eligibility. Add Flight explains
that an unestablished pair needs purchase first; scheduling still uses certified
passenger-service commands and actual active connection facts.

Ordinary New Game remains legacy, so this stage does not expose a default quarterly
new-career entry. Existing explicit development fixtures retain their pre-established
connections and do not pay retroactively. The original-blocker certification uses
the normal fresh constructor, isolated enrollment without seeded connections, paid
MNL–CEB establishment, and successful quarterly passenger-service creation.
The native test loads that empty isolated career in the normal app without
`--quarterly-dev`, then exercises actual purchase/cancel/closure widgets.

## Evidence and limits

Pre-change quarterly GUI baseline: **45 PASS in 150.563s**, including native Kivy.
Final route focused run: **41 PASS in 52.628s**, including one native Windows Kivy
workflow covering confirmation, cancellation, closure and refreshed route status.
Python 3.12.10, Kivy 2.3.1, SDL2, OpenGL 4.6 Intel UHD Graphics.

Measured exact quotes using current PH references:

| Pair / example | Distance km | N | USD fee |
| --- | ---: | ---: | ---: |
| MNL–CEB, fresh Base | 566.982 | 0 | 27,834.91 |
| MNL–DVO after MNL–CEB | 963.773 | 1 | 30,415.24 |
| International arithmetic control | 1,000 | 0 | 90,000.00 |

Focused coverage includes both fee bases, distance/growth/no cap/half-cent rounding,
owned Hub and Operating Base attribution, one pair count, idempotence, insufficient
cash, invalid/prohibited inputs, stale/altered/foreign/rebound confirmations,
candidate/detached/late-source failures, all gates/two copies, journal/provenance
validation, closure/reopening, draft/published protection and exact save/load replay
through the following daily Booking boundary. Initial test-constructor error was
fixed. Review also corrected free closure under negative cash and limited operational
closure dependencies to the owning airline. Earlier full/regression runs were stopped
for those changes and are excluded from completion evidence. A Decimal precision probe
also reproduced nine-cent quote drift; converting the existing distance through its
exact integer ratio fixes quotation and receipt validation without changing normal
fees. Focused coverage checks quotation/payment/validation under precision 4 and 28;
the corrected source has its own fresh full/regression freeze. No production gate/formula
was weakened.
USD receipts also require USD owning accounts: a probe that changed the owning
ledger to EUR while retaining USD payment witnesses is now rejected rather than
reinterpreted. Display-currency choices remain runtime-only and unchanged.
Full and affected regression, compilation, source-freeze and documentation results are recorded in
[Current Development Status](Current%20Development%20Status.md).

Final affected group: **258 PASS / 846.140s**. Final full discovery:
**1,612 PASS / 2,339.511s**, exit 0, no failures/skips, prior baseline 1,571 plus 41.
All **326 source/test SHA-256 witnesses** match across the final frozen run.
Scoped compilation exits 0; **417 local links / 71 heading targets / 9 changed
Markdown files**, exact **18-file scope**, whitespace and final self-review pass.
Superseded interrupted runs are excluded. Commit/push outcome belongs to the final
completion report; this is evidence for the verified working-tree scope.

Stage 3G remains blocked by its separate required runtime-capacity gate and unrun
combined activation certification. [AT-041 evidence](Runtime%20Capacity%20Certification.md#final-decision)
remains NOT CERTIFIED; this stage measures fees, not fleet throughput. No runtime
optimization, runway queue, automatic positioning, country-access purchase,
blueprint, demand-economics change or unrelated marketplace work. Human manual
playtesting remains outstanding; native automation is not human UX acceptance.

## Changed files

- [Schema](Stage%201%20State%20Schema.md) and [template](../../Data/Templates/template_reference.txt)
- [World provenance/constructor](../../game/world_state/route_establishment.py) and [validation hook](../../game/world_state/validation.py)
- [Route transaction](../../game/route_management/establishment.py) and [expense](../../game/economy/route_establishment.py)
- [Session](../../app/session.py), [Kivy shell](../../app/gui/app.py), [Research](../../app/gui/management_pages.py)
- [Certification](../../tests/test_route_establishment.py)
- [This contract](Paid%20Bidirectional%20Route%20Establishment.md), [status](Current%20Development%20Status.md), [decisions](Decision%20Register.md), [roadmap](Stage%201%20Implementation%20Roadmap.md)
- [Route architecture](../02%20Gameplay/Market%20%26%20Route%20Management.md), [quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md), [quarterly GUI](Quarterly%20Planning%20GUI.md), [index](../README.md)
