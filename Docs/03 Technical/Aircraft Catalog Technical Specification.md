# Aircraft Catalog Technical Specification

Status: Approved bounded PH 1.0 catalog milestone. The session approval covers
20 curated models, maximum Economy layouts, historical production metadata,
realistic game-calibrated performance/prices, and terminal browsing. The final
scope clarification explicitly leaves scheduling unchanged.

## Behavior and ownership

The terminal offers manufacturer selection, four models per manufacturer, and
model details with Economy capacity, reference range, calibrated cruise speed,
USD reference price, production metadata, and explanatory notes. Back returns
one level; cancel returns to the main menu. Invalid input reprompts. EOF and
interrupt retain the existing terminal exit/cancellation behavior.

World State owns external-reference validation and parsing. Aircraft Market's
new isolated `reference_catalog` module owns exact-version lookup and detached
catalog projections. It imports no legacy catalog/purchase/lease/UI code. The
terminal explicitly selects `ph-aircraft-catalog-v1`; selection and browsing are
runtime/UI state. Prices are separate from physical model records.

See the [canonical reference schema](Stage%201%20State%20Schema.md#approved-aircraft-catalog-reference-contract)
and its [subordinate mirror](../../Data/Templates/template_reference.txt).

## Approved content and calibration

| Manufacturer | Model | Maximum Economy seats | Reference USD millions |
| --- | --- | ---: | ---: |
| Airbus | A320neo | 194 | 55 |
| Airbus | A321neo | 244 | 65 |
| Airbus | A330-900 | 465 | 150 |
| Airbus | A350-900 | 440 | 160 |
| Boeing | 737-8-200 | 210 | 60 |
| Boeing | 737-9 | 220 | 65 |
| Boeing | 787-9 | 406 | 145 |
| Boeing | 787-10 | 440 | 170 |
| De Havilland Canada | Twin Otter Classic 300-G | 19 | 7 |
| De Havilland Canada | Dash 8-200 | 40 | 12 |
| De Havilland Canada | Dash 8-300 | 56 | 17 |
| De Havilland Canada | Dash 8-400 / Q400 | 90 | 30 |
| Embraer | E175 | 88 | 25 |
| Embraer | E190 | 114 | 30 |
| Embraer | E190-E2 | 114 | 35 |
| Embraer | E195-E2 | 146 | 40 |
| Bombardier CRJ | CRJ200 | 50 | 15 |
| Bombardier CRJ | CRJ700 | 78 | 22 |
| Bombardier CRJ | CRJ900 | 90 | 27 |
| Bombardier CRJ | CRJ1000 | 104 | 32 |

The 787-9 uses Boeing's 406-seat all-Economy arrangement, not its 420-person exit
limit. The 737-8-200 denotes the high-capacity MAX 8 variant. MHIRJ is noted as
CRJ program support owner; manufacturer grouping does not implement corporate
history. All models remain browsable irrespective of historical production dates.

Sources and per-model calibration notes live in the pack. Manufacturer figures
anchor capacity and range; cruise speeds are rounded representative gameplay
inputs, not Mach conversions independent of atmosphere. Prices are the approved
rounded game values above, not list-price promises or used-aircraft valuations.
Range assumptions differ by source/configuration; maximum seating and advertised
range are not asserted achievable simultaneously. Twin Otter range explicitly
identifies its payload assumption. Source URLs are provenance only: runtime
never downloads content. Unestablished production dates remain null with notes,
rather than reusing launch, certification, first-flight or delivery years.

## Compatibility and non-goals

No world/save fields, schema-version changes, migrations, aircraft acquisition,
cash movements, delivery events, or availability gating are introduced. The
180-seat free A320-200 remains the starter and is not one of the 20 catalog
offers. Existing aircraft model references, capacity witnesses, timing profiles,
serialized worlds and processed history remain unchanged. Browsing does not
alter the session dirty flag, IDs, events, money or time. Catalog load failures
report unavailability and preserve the active game.

Purchases, leasing, lease-to-own, used listings, operational model binding,
model-specific schedule capacity, runway/range eligibility, operating expenses,
maintenance, runtime, and disk save/load remain later milestones. The preferred
30-minute narrowbody/45-minute widebody handling simplification is deferred to
future acquisition/scheduling integration; no timing data or math changes here.

## Future cabin boundary

Models will define physical cabin geometry and limits; individual aircraft will
own installed layouts. Future seat products may carry dimensions, weight and
comfort, including Economy, comfort seating, Business and open/enclosed suites.
Area is not the sole constraint: access/aisles and passenger limits also matter.
Payload mass and cargo volume stay separate. Future range calculation must
account for installed equipment, passengers, baggage, cargo and fuel. This
milestone invents no area/weight/comfort formulas or unused persistent fields.

## Verification and exit gate

- Validate the complete pack, exact fields, identity topology, numeric types,
  production-year ordering, source references, and complete pricing coverage.
- Reject duplicate JSON keys, unknown versions/models and semantic changes to
  an already published registered version; never substitute legacy values.
- Prove detached sorted projections, stable results across dictionary order,
  and no mutation through returned nested data or constructor input.
- Exercise browsing, back, cancel, invalid input, EOF, interrupted input,
  missing/corrupt content and alternate display currency without world changes.
- Preserve a published/booked world across browsing and deterministic continuation.
- Run focused catalog tests, the full standard-library suite for milestone
  completion, explicit application compilation and `git diff --check`.

The next development milestone is basic new-aircraft acquisition. Its technical
specification must bind model versions and individual configurations, remove the
planner's fixed capacity assumption for new models, and define atomic payment,
aircraft creation and entry into service before implementation.
