# Stage 1 Terminal Harness Technical Specification

## Status and scope

This document records the implemented Milestone 7 deterministic in-memory
terminal harness. It is an application adapter over the authoritative Stage 1
schema-4 world and production commands completed through Milestone 6.

Milestone 7 is intentionally temporary. It implements no file writing, file
loading, save slot, quick save, autosave, backup, recovery, persistence
migration orchestration, offline progress, AI airline, or broader Milestone 9
integration. Exiting the process loses the session. No Save or Load menu item is
shown.

The launch boundary is:

```text
python -m app.terminal
```

The production code accepts injected text streams through
`run_terminal(input_stream, output_stream, *, session_factory=...)`, so tests do
not require terminal emulation, sleeping, wall-clock time, or host locale.

## Curated scenario authority

`Data/Stage1/philippines_v1.json` is the immutable explicit reference pack for
scenario `stage1-philippines-v1`. Runtime never reads or normalizes legacy
`PH.json` for this scenario.

The pack fixes:

- `2026-09-01T00:00:00Z` as the paused starting instant;
- one deterministic world seed;
- the 43 active commercial-airport members in the versioned Philippines v1
  recovery catalog, all in `Asia/Manila`;
- the canonical Philippines country/region foundation;
- USD as the authoritative currency;
- 100,000,000 USD minor units of cash and zero debt;
- one free `A320-200`, registration `RP-C0001`, parked at the selected base;
- 180 published Economy seats;
- the fixed 08:00–10:00 outbound and 12:00–14:00 return timetable; and
- optional presentation-only USD/PHP/EUR rational conversion rates.

The loader requires the exact scenario contract and rejects missing, extra,
malformed, or unsupported data. It returns a detached copy. Every one of the
43 active airport members is a legal base selection; inactive LGP is not.

## Atomic bootstrap

`game.world_state.create_stage1_new_game(...)` accepts the scenario ID, CEO
display name, airline display name, and base reference code. Names are display
values, not identity, and duplicate display names remain legal.

Construction occurs only on a private candidate:

1. load and strictly validate the curated pack;
2. call the canonical schema-1 new-world constructor;
3. add the remaining curated airports and all 1,806 directional markets;
4. migrate to schema 2 with the curated country foundation;
5. activate Demand Model 4 through its expected-revision command;
6. add the free starter aircraft through canonical aircraft construction;
7. migrate to schema 3;
8. transition Booking configuration from revision 1 to production revision 2;
9. execute the initial production daily Booking checkpoint, which establishes
   the next-midnight recurrence;
10. migrate to schema 4 and install fulfilment configuration revision 1; and
11. validate the complete candidate and return a final detached copy.

Failure raises a structured bootstrap rejection and exposes no partial world.
The aircraft grant creates no acquisition journal, purchase, lease, delivery,
financing, marketplace, maintenance, or seating-editor authority.

## Booking checkpoint preparation

`game.booking.prepare_daily_booking_checkpoint(...)` is the production-ready
detached witness boundary extracted from the event handler. It runs production
shopping and allocation probes on private candidates, then returns exact:

- Booking, Demand, market-pack, and Booking-configuration revisions;
- Booking-configuration fingerprint;
- affected flight inventory revisions;
- paid affected-airline finance revisions; and
- event-order cursor.

It does not mutate authority. `process_daily_booking_checkpoint(...)` repeats
the deterministic production path and retains all optimistic-concurrency and
late-witness checks. The daily event handler now calls this preparation API
instead of embedding its own witness-probing implementation.

## Weekly rotation command

`game.scheduling.create_weekly_round_trip_rotation(...)` is an atomic composite
over existing construction, schedule-definition, publication, revision,
continuity, event creation, and validation APIs. It requires a parked aircraft
owned by the player airline, uses its current airport as origin, requires one of
the other curated airports as destination, and applies one exact USD fare to
both directions.

The command creates or reuses active connections, creates two weekly schedule
definitions, and publishes exactly their first two occurrences. The return leg
restores aircraft continuity at the origin. Invalid identity, ownership,
location, endpoint, fare, date, market, connection, recurrence, time,
turnaround, overlap, chronology, currency, booked occurrence, or validation
state rejects the candidate without changing the live session.

`publish_next_rotation(...)` expands the same active definitions to their next
eligible weekly date through the normal publication boundary. It does not
create one-off flights or a parallel recurrence model.

## Exact fare and time input

Terminal fare text is USD major units. The parser accepts zero, positive whole
amounts, and one- or two-decimal amounts, then converts by digit arithmetic to
integer USD minor units. It rejects signs, commas, exponent notation, boolean
text, excess decimal places, nonnumeric input, and values beyond the bounded
input length. Binary float and the global Decimal context are not used.

Duration input is a positive whole integer followed by `m`, `h`, or `d`.
Timestamp input is canonical `YYYY-MM-DDTHH:MM:SSZ`. All advancement calls the
production event kernel directly. No wall clock, sleeping thread, frame loop,
background progression, offline catch-up, or legacy daily tick participates.

Next Event invokes the one-event command. Day, Duration, and Timestamp invoke
the process-through command. A failed handler leaves its event pending and
reports its code and event ID; earlier committed event boundaries remain. No
ignore-and-continue path exists.

## Projections

Milestone 6 projections are extended with a validated internal row builder so a
bounded multi-row view validates the whole world once rather than once per
result. Public projections are deterministic, canonically ordered, detached,
bounded, and mutation-safe.

Flight views include immutable IDs, display labels, endpoints, UTC schedule,
aircraft identity/state/location, authoritative USD fare, capacity, confirmed
bookings, derived remaining seats, exact booked and carried load-factor fields,
paid and zero-fare partitions, ticket sales, lifecycle event, recognized
revenue, operating cost/contribution, completion transaction, and immutable
result identity where applicable.

Finance views include cash, unflown-ticket liability, passenger revenue,
operating expenses, cumulative fulfilment revenue/cost/contribution, at most ten
recent results, and at most ten recent transactions. Fleet, overview, next
pending event, and selected event-history rows also use detached projections.

Remaining seats, percentages, contribution summaries, formatted text, and
converted balances are derived only and are never persisted.

Recovery Batch 1 adds `project_market_opportunities(...)`. Each bounded row
contains the directional market and endpoint identities/display data, Model 4
revision witnesses, exact base daily directional bookers, diagnostic share,
distance, availability, and current player service/capacity/unambiguous fare/
confirmed Booking observations. The public projection remains detached and
canonically market-ID ordered; the terminal sorts only its detached copy.
Internal IDs, fingerprints, revisions, cohort language, and diagnostic shares
are not displayed to the player.

## Currency boundary

USD is the single authoritative economic currency. Fares, cash, liabilities,
revenue, expenses, costs, transactions, and flight results remain USD minor
units. Demand, Booking, fulfilment, finance, fingerprints, revisions, event
ordering, validation, and deterministic state never receive converted values.

The session may select USD, PHP, or EUR for presentation. Conversion uses the
scenario's positive integer numerator/denominator and signed round-to-nearest,
ties-to-even arithmetic in target minor units. USD is always displayed and the
conversion is labeled as display-only. Preference changes do not modify world
bytes or mark the authoritative session changed. There is no network or live FX
dependency.

## Runtime session and failure recovery

`Stage1Session` owns only the current in-memory world, runtime display currency,
and runtime changed/loss-warning state. Forms operate on projections and stable
numbered lists ordered by immutable IDs or curated airport code. Cancelling or
interrupting a form applies no mutation.

Domain rejections show status, issue code, and a concise message. Stale witness
failures require a fresh action. Unexpected exceptions trigger validation of the
live world; an invalid world ends safely. EOF is an exit request. Exiting an
active game requires the explicit warning:

```text
This temporary session will be lost. Exit? [y/N]
```

## Persistent-schema decision and deferred work

Milestone 7 originally added no persistent field and did not increment schema
version 4. Philippines v1 Recovery Batch 1 completes the unreleased schema-4
airport reference record with nullable immutable `catalog_airport_id` and
nullable `city`; the Philippines pack requires both. It does not add terminal
state to persistence or increment schema version 4.
Terminal navigation, display preference, warnings, aliases, and formatting stay
outside the authoritative envelope.

Authoritative file saving/loading, slots, autosaves, atomic replacement,
backups, recovery, and persistence migration orchestration remain Milestone 8.
AI airlines and the broader integrated gameplay workflow remain Milestone 9.

## Philippines v1 home-base and market journey

The new-game form lists all 43 active scheduled-commercial airports in IATA
order as `code - airport name - city/location`. Every listed airport is a valid
home base. An invalid number reprompts the base field, preserves accepted CEO
and airline names, and never converts a valid listed number into cancellation.
The current fixed weekly rotation likewise offers every other active airport
with all three labels; inactive/reference-only airports never appear.

Every question uses one terminal primitive that writes the question, writes a
separate `> ` input line, and flushes the output stream before `readline()`.
Blank names are explicitly rejected and reprompted. Blank defaults are accepted
only where the question states a default, such as `[y/N]`, operating date,
research origin, or research sort. This works with ordinary buffered
`python -m app.terminal`; `-u` is not required.

Main-menu `Market Research` defaults the origin to the airline's base, accepts
any active origin code, and sorts destinations by highest base demand, IATA
code, or authoritative-coordinate distance. The browser shows code, city,
base daily total directional demand, distance, player scheduled seats, and
service state; a detail view adds the airport name, availability, fare where
unambiguous, and confirmed Bookings. It states once per list that total market
demand does not guarantee player choice and states in detail that actual
Bookings depend on fare, schedule, capacity, and future competition. Returning
from every research screen leaves authoritative bytes unchanged.

The larger airport foundation does not expand the fixed weekly rotation editor,
hard-code new aircraft capacity policy, or add acquisition, leasing,
maintenance, continuous time, save/load, or AI.
