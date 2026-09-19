# Aircraft Marketplace Technical Specification

## Status and scope

This is the implemented PH 1.0 Step 5 contract for operating leases,
lease-to-own contracts, deterministic rotating lease offers, and persistent
used-aircraft listings. The canonical field contract remains the
[Stage 1 State Schema](Stage%201%20State%20Schema.md). Manufacturer outright
purchase remains governed by the Aircraft Acquisition specification.

## Market rotation

The market initializes during schema-5-to-6 migration and rotates at 00:00:00Z
on the first of each UTC month. A seed-keyed SHA-256 draw uses the world seed,
month, stable counterparty/slot identity and purpose label; it consumes no shared
random stream. Each of three persistent lessors specializes in a bounded catalog
subset and creates two offers with one to three units. Rotation expires unused
lease offers and creates four background-airline used listings. Unsold used
listings are never expired by rotation. Accepted contracts retain the immutable
lessor identity and all pricing witnesses independently of later market state.

Used age is drawn from 24 through 240 months. Annual utilization is 1,200 through
3,600 hours and mean sector length 55 through 300 minutes. Lifetime seconds are
derived from age and utilization; cycles are derived from lifetime seconds and
sector length. Condition starts at 100.00% and loses deterministic utilization
and cycle components, with a 40.00% floor. These are coherent market-generation
witnesses, not a maintenance simulation.

## Pricing

All division rounds upward unless stated otherwise. Operating monthly rent is
new catalog value times the term rate: 1 year 1.75%, 2 years 1.60%, 3 years
1.45%, 4 years 1.35%, and 5 years 1.25%. Lease-to-own monthly financing is
separate from principal and uses 1.00%, 0.85%, 0.70%, 0.60%, and 0.50%
respectively. Thus a longer term lowers the monthly component while increasing
total financing cost, and lease-to-own financing remains cheaper than comparable
operating rent.

Lease-to-own principal equals original value divided over 12 times term years.
The earliest remainder installments receive one extra minor unit, guaranteeing
that final accumulated principal equals original value exactly. Payments are in
arrears on monthly anniversaries. Automatic payments post even when cash becomes
negative. There is no delinquency or default state.

Used asking value applies 4.00% depreciation for each completed year, with a
20.00% residual floor. It then applies a linear condition multiplier from 50.00%
at zero condition to 100.00% at perfect condition. This simple value is not a
promise of future maintenance economics.

## Cancellation settlement

Operating cancellation immediately charges every unpaid monthly rent installment
and nothing else.

Lease-to-own cancellation uses:

1. `depreciated value = new value × max(20%, 100% − 4% × completed years)`;
2. `remaining principal = new value − principal paid`;
3. `equity after depreciation = max(0, depreciated value − remaining principal)`;
4. `restoration = ceil(new value × missing-condition share × 20%)`;
5. `net cash = equity after depreciation − unpaid financing − restoration`.

Remaining principal is extinguished. Age depreciation affects equity once;
condition affects restoration once. It is intentionally not also multiplied
into the equity value. The journal removes paid principal from aircraft assets,
posts net cash, and balances the difference to operating expense.

Worked example, using a USD 100,000,000.00 two-year contract: monthly financing
is USD 850,000.00; principal is USD 4,166,666.66 plus one cent on the first 16
payments. After 12 payments, paid principal is USD 50,000,000.04. At exactly one
completed year and 90.00% condition, depreciated value is USD 96,000,000.00,
remaining principal USD 49,999,999.96, equity USD 46,000,000.04, unpaid financing
USD 10,200,000.00 and restoration USD 2,000,000.00. Net cash is a positive
USD 33,800,000.04.

After only the first payment at zero completed years and 80.00% condition, equity
is USD 4,166,666.67, unpaid financing is USD 19,550,000.00, restoration is
USD 4,000,000.00, and net cash is negative USD 19,383,333.33. These examples
also specify cent allocation and demonstrate that depreciation, condition and
principal are not double counted.

## Contract scheduling and event order

A lessor-owned aircraft may have live flights only when every arrival is at or
before its continuous confirmed contract horizon. A confirmed operating renewal
extends that horizon; an unconfirmed intention does not. At a shared timestamp,
market rotation has priority 10, contract payment 20, flight lifecycle 100, and
contract expiry 200. Final payment and a legitimate arrival therefore settle
before transfer or return. Voluntary return requires the aircraft parked with no
live commitments. PH 1.0 return clears current location and marks the retained
aircraft record `RETURNED`; no ferry flight is inferred.

## Compatibility and future work

Migration does not invent lifecycle records for legacy aircraft. New schema-6
manufacturer purchases receive new-airframe lifecycle facts; used purchases
retain their listed airframe facts; renewals preserve aircraft ID, registration,
configuration and history. Save/reload needs no runtime cache to reconstruct
offers, listings, contracts or payment order.

Future manufacturer installments require a down payment and interest-bearing
financing of the balance, with ownership and configuration rights from delivery;
rates, terms, lenders and refinancing remain undecided. Future maintenance may
add hours/cycles deterioration, age-sensitive A/B/C/D-style inspections,
component overhauls, cost and downtime; maintenance may restore relevant
condition but never age or lifetime history. Future AI airlines may list their
actual fleet identities, including distress sales. Physical delivery/return,
banking and loans, AI bankruptcy, and lease-to-own refinancing are not
implemented. Future bankruptcy is intended to measure consecutive time below
zero cash, reset that duration when cash becomes positive, and use a threshold
that remains undecided; schema 6 does not invent that threshold or duration.
