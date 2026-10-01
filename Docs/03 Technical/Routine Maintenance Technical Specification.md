# PH 1.0 Step 6 — Simple Routine Maintenance Expenses

Status: Approved for implementation. The canonical [Stage 1 State Schema](Stage%201%20State%20Schema.md) owns persistent fields; this document defines behavior.

For each new schema-7 departure, freeze the authoritative planning-timing distance in metres, or, for a valid legacy schedule without a timing snapshot, the shared geographic-distance fallback in metres. Freeze its source, the aircraft-model classification version and class, the class rate, and the maintenance configuration fingerprint. Historical V1 operations and results are not changed.

At successful completion, determine the class from the actual aircraft's immutable model ID. Routine maintenance is `ceil(distance_m * class_factor_minor_per_km / 1000)`, using integer arithmetic. Add it exactly once to the existing base operating cost and post only the combined cost to operating expense and cash in the existing atomic fulfilment transaction. Completed deadheads are charged. Failed or incomplete flights are not. Flight seconds and cycles continue accumulating independently.

The immutable [classification pack](../../Data/Stage1/aircraft_aerodrome_class_v1.json) covers the 20 Stage 1 catalog models and the legacy A320-200 starter. Its A–G classes use the ICAO wingspan bands (A under 15 m, B under 24 m, C under 36 m, D under 52 m, E under 65 m, F under 80 m; G is a project extension for 80 m or more), with documented manufacturer dimensions. Airport `max_aircraft_class` is never an input to model classification. All classes have rates, even where the current catalog has no model in a band.

| Class | Models in this version |
| --- | --- |
| A | None |
| B | Twin Otter 300-G, CRJ200, CRJ700 |
| C | A320neo, A321neo, 737-8-200, 737-9, Dash 8-200/-300/-400, E175, E190, E190-E2, E195-E2, CRJ900, CRJ1000, starter A320-200 |
| D | None |
| E | A330-900, A350-900, 787-9, 787-10 |
| F | None |
| G | None |

Schema 6→7 migration adds only the configuration and schema marker to a detached, validated candidate. Historical V1 results and journals remain byte-equivalent in meaning and shape. Already locked V1 operations settle under V1 even after migration. New departures use V2. No backfill or maintenance accounts/events are introduced.

The departure command may select a different actual aircraft only when that aircraft is airline-owned and parked at the origin. The substitution is frozen into the operation before it takes off; V1 operations retain their original planned=actual constraint. A substituted aircraft's model, not the planned model, supplies the maintenance class. Existing published-manifest and world validation still apply; Step 6 does not define a general fleet-reassignment or cabin-capacity substitution workflow.

Acceptance requires deterministic event-step/bulk/7× equality, exact integer boundaries, direct cash/expense reconciliation (including negative cash), replay without a second charge, timed and fallback distance witnesses, V1 historical and in-flight migration preservation, unchanged lifecycle counters, and separate projection/terminal visibility.

Out of scope: scheduled checks, condition, downtime, failures, reserves, PBH contracts, monthly settlement, facilities, and flight-hour/cycle expense formulas.
