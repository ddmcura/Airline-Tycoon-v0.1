# Airline Tycoon - Airport Management Architecture

> **Status:** Approved architecture. This document defines historical airport evolution, airport capability, physical infrastructure, operational capacity, airline facilities, airport access, future development and ownership, and the boundaries between Airport Management and the systems that use it. Detailed formulas, persistent schema fields, shareholder governance, and construction balancing remain future design work.

## 1. Purpose and Core Philosophy

Airport Management exists to support and constrain the airline business. Airline Tycoon remains an airline management game, not a detailed airport-building simulator.

Airports must feel like real operational places with their own history, infrastructure, limits, services, fees, congestion, and development opportunities. These characteristics create airline decisions: which airports to serve, where to establish facilities, whether to accept congestion or high fees, when to fund an upgrade, and whether airport investment or ownership supports the wider airline group.

The defining principles are:

```text
Airports are historically grounded operational systems.

Airport capability comes from real facilities and certification,
not from Hub level or one magical Airport Level.

Airport development is strategic placement and investment,
not detailed manual construction.

The airline is always the center of the game.
```

## 2. Historical World and Alternate Development

### 2.1 Historical availability

Airports follow the historical game year.

If a game begins in 1960:

- only airports already open in 1960 are operational;
- their runways, terminals, capabilities, restrictions, and controller reflect the represented historical period;
- later airports open on their historical dates;
- government-controlled airports follow their recorded historical development; and
- airport closures, replacements, expansions, and capability changes occur according to available historical data.

Aircraft availability follows the same overall historical philosophy in its owning systems: aircraft enter production and become available according to their historical dates, while new orders, used-aircraft availability, and leasing remain separate market concerns.

Historical data establishes the default world timeline. The game must not fabricate historical projects merely to continue progression beyond the available records.

### 2.2 End of available historical data

When an airport reaches the latest reliable historical state represented in the data, it remains in that state unless:

- a later game-data update adds newer historical development;
- an AI-controlled owner begins dynamic development; or
- the player obtains control and changes its future.

An untouched airport does not receive invented future construction simply because game time has passed beyond the data set.

### 2.3 Player or AI intervention

Once the player gains control of an airport, historical development stops dictating that airport's future. The player creates an alternate timeline through their own investments and decisions.

Player control may allow an airport to:

- expand earlier or differently from history;
- gain regional or international capability earlier;
- avoid a historical decline or closure;
- omit an expansion that happened historically;
- specialize in passenger, cargo, or other operations;
- be redeveloped or replaced; or
- eventually be closed.

An AI-controlled airport may also develop dynamically rather than remaining bound to the historical timeline. Detailed AI acquisition and development behavior is deferred.

### 2.4 Owner and operator

Airport owner and airport operator are conceptually distinct. A government may own an airport while another company operates it under a concession.

The initial architecture may treat the historical controller as one combined authority where a separate distinction provides no gameplay value. Future business-group and concession systems may represent owner and operator independently.

## 3. Airport Identity, Footprint, and Constraints

Every airport has a physical location and an airport-specific footprint. Its development potential depends on factors such as:

- existing developed area;
- available land;
- terrain and elevation;
- water and reclamation possibilities;
- surrounding urban development;
- obstacles and approach paths;
- environmental and noise restrictions;
- road, rail, and utility conflicts;
- runway orientation and wind conditions; and
- regulatory and safety requirements.

Airports should resemble their historical real-world layouts as reasonably as the project's data and visual resources permit. Future player additions connect to the represented historical airport rather than replacing it with a blank generic construction map.

Money may overcome some constraints through land purchase, demolition, relocation, tunneling, reclamation, or replacement-airport projects. It cannot overcome genuinely impossible geography or aviation-safety constraints.

## 4. Capability and Classification

### 4.1 No universal Airport Level

Airport capability is represented through separate infrastructure, service, technology, and certification states. Hub level never upgrades the physical airport.

Relevant capability areas include:

- domestic passenger capability;
- regional international capability;
- full international capability;
- runway and aircraft compatibility;
- passenger-processing capability;
- terminal, gate, stand, and parking capacity;
- cargo capability;
- rescue, firefighting, and safety capability;
- ground-handling capability;
- maintenance capability;
- fuel capability;
- navigation and poor-weather capability; and
- operating hours, curfews, and local restrictions.

The interface may summarize these capabilities for convenience, but a summary label must be derived from the actual airport state. Increasing a label does not magically create its requirements.

### 4.2 Domestic, Regional, and International service

The game uses three understandable service classifications:

| Classification | Meaning |
|---|---|
| Domestic | Origin and destination are in the same country, regardless of distance. |
| Regional | International service within a defined maximum distance. |
| International | International service beyond the regional-distance limit. |

Regional capability is therefore a simplified intermediate international certification. A Regional airport can process international flights only within the defined regional distance category. Full International capability removes that distance-category limitation.

The exact Regional distance is a balancing value and may vary by historical era, regulation, research, or technology if future design requires it.

This is an intentional gameplay abstraction. Actual customs and immigration do not depend simply on flight distance, but the classification creates a clear progression:

```text
Domestic capability -> Regional capability -> International capability
```

### 4.3 International requirements

Regional and International operations require the appropriate combination of:

- customs;
- immigration;
- security;
- international passenger processing;
- baggage controls;
- suitable terminal space;
- required safety and emergency services; and
- regulatory approval.

Airline country access and route rights provide political and commercial permission. Airport capability determines whether the airport can physically and regulatorily handle the service. Neither replaces the other.

### 4.4 Aircraft compatibility and certification

A runway extension alone does not immediately make an airport suitable for every aircraft. Operation may also require:

- sufficient runway length, width, and pavement strength;
- suitable taxiways;
- compatible gates, stands, and parking;
- adequate rescue and firefighting capability;
- required approach and navigation systems;
- terminal and security capability; and
- completed testing and regulatory certification.

Aircraft size, performance, current weight, weather, and available technology may all affect compatibility.

## 5. Airport Infrastructure

Airport Management owns the physical presence, capacity, compatibility, condition, and developable space for airport infrastructure.

### 5.1 Airfield infrastructure

Airfield infrastructure may include:

- runways and runway extensions;
- taxiways and rapid exits;
- aprons;
- passenger and cargo stands;
- terminal gates;
- remote stands;
- aircraft parking;
- lighting and navigation aids;
- drainage, deicing, and weather equipment; and
- fire and rescue facilities.

Runways track meaningful characteristics such as length, width, pavement strength, orientation, condition, restrictions, approach capability, and supported aircraft.

### 5.2 Terminals, gates, stands, and parking

Terminals may differ by:

- passenger-processing capacity;
- domestic, regional, or international capability;
- gate and stand connections;
- aircraft-size compatibility;
- passenger service quality;
- walking and transfer times;
- baggage and security capability; and
- shared, leased, dedicated, or airline-owned use.

Terminal gates are convenient and may support faster or better passenger handling, but they are more expensive and limited. Remote stands use buses or walking and may increase turnaround time or reduce the airline's service performance.

Overnight and long-stay parking is separate from passenger-gate use. An airline should not occupy a valuable terminal gate for many hours unless it intentionally pays for that use. Operating Bases require appropriate parking arrangements for their stationed fleet.

### 5.3 Other facilities

The architecture preserves the future construction, lease, or operation of:

- cargo terminals;
- maintenance hangars;
- fuel storage and distribution;
- airline lounges;
- airline offices;
- catering facilities;
- ground-service facilities;
- fire and rescue services;
- deicing equipment where relevant;
- hotels and commercial areas;
- car parks and ground-transport facilities;
- warehouses;
- training and crew facilities; and
- other airline-supporting infrastructure.

Not every facility must be implemented at the same development stage.

## 6. Capacity, Congestion, and Airport ATC

### 6.1 Multiple bottlenecks

Airport capacity is not one universal number. Usable throughput may be constrained by:

- runway movements;
- taxiway flow;
- gates and stands;
- long-stay parking;
- terminal processing;
- baggage handling;
- security, customs, or immigration;
- ground handling;
- air-traffic procedures;
- weather; and
- operating restrictions.

The weakest relevant component may limit an operation. A large terminal does not fix a saturated runway, and another runway does not help if no compatible stands are available.

### 6.2 Airport-specific ATC engine

Each operational airport will eventually have its own traffic-control and movement simulation. It evaluates factors such as:

- available runway configuration;
- arrival and departure queues;
- aircraft separation and wake category;
- runway occupancy time;
- aircraft performance and size;
- taxiway congestion;
- stand and gate availability;
- weather and visibility;
- navigation and ATC technology;
- emergencies and priority movements; and
- temporary closures or construction.

Two aircraft scheduled to arrive at 12:00 do not magically land simultaneously on the same runway. The airport sequences them. An aircraft may slow before arrival, receive vectors, enter a holding pattern, wait for runway clearance, or divert if conditions and fuel require it.

The operational timeline distinguishes at least:

- scheduled arrival;
- estimated arrival;
- actual landing; and
- gate arrival.

Actual delay can affect turnaround and propagate into later flights. Actual disruption does not rewrite the originally published schedule.

### 6.3 Planned versus live capacity

Scheduling needs a forecast of whether an exact requested movement time is feasible. This forecast is derived from airport infrastructure, expected traffic, restrictions, and the Airport ATC model rather than from one arbitrary universal maximum-movements-per-15-minutes rule.

Airport Management provides capacity, restrictions, congestion forecasts, and scheduling opportunities. Scheduling assigns exact planned movements. Aircraft Operations and Airport Operations execute the live traffic and record actual results.

The interface should make expected congestion understandable without promising perfect foresight. It may show reserved movements, available opportunities, likely queues, common delay periods, and construction impacts using derived summaries.

## 7. Slots

Airports may operate under different congestion states:

- **Unconstrained:** feasible times are normally approved.
- **Facilitated:** congestion warnings or negotiated time adjustments may occur.
- **Coordinated:** formal slots are required.

An airport may move between these states as traffic, regulation, and capacity change.

Slots are operational assets separate from country access, route rights, Airport Access, and Hub status. Depending on local rules, an airline may:

- apply for slots;
- purchase or lease them;
- trade them;
- return them;
- retain historical-use rights; or
- lose them through non-use.

Scarce coordinated-airport slots should normally have use-it-or-lose-it requirements so one airline cannot permanently block competitors by hoarding unused capacity. Extraordinary events, closures, or approved suspensions may create exemptions.

Exact slot allocation, timing, markets, local rules, and utilization thresholds remain future design work.

## 8. Airport Access and Airline Facilities

### 8.1 Purpose of Airport Access

Airport Access is not required merely to operate an ordinary flight. It is required when an airline wants a permanent operational or commercial footprint at the airport.

Airport Access may permit the airline to seek:

- an Operating Base or Hub;
- permanent parking arrangements;
- dedicated gates or terminal space;
- airline offices;
- lounges;
- hangars and maintenance space;
- fuel storage;
- catering or ground-handling facilities; and
- other leases or construction rights.

Airport Access does not grant country access, route rights, slots, Hub status, airport ownership, or free facilities.

### 8.2 Acquisition

Acquiring Airport Access may require:

- an application to the authority or owner;
- an initial access or concession fee;
- a land or space lease;
- operational, reputation, or regulatory requirements;
- negotiation; or
- a competitive tender at scarce airports.

The exact requirements and prices remain future balancing work.

### 8.3 Lease, shared use, or construction

The airline may eventually choose among:

| Arrangement | Strategic character |
|---|---|
| Shared facility | Low commitment and cost, but exposed to congestion and limited control. |
| Lease | Faster and cheaper upfront, with recurring cost and contract limits. |
| Build or own | Expensive and slow, with greater capacity and control but continuing maintenance and capital costs. |

Dedicated leases can guarantee access within the contract. Shared-use facilities remain available only within their compatibility and capacity.

If the airline closes a Base or Hub, separately owned facilities do not disappear. Leases may expire or be terminated with penalties; owned facilities may be retained, sold, leased to others, or mothballed. Airport Access may remain while the airline continues to own or lease a local facility.

An airline lounge may exist at a major served airport without that airport being the airline's Base or Hub.

## 9. Ground Handling, Maintenance, Fuel, and Cargo

### 9.1 Ground handling

Depending on historical availability, local providers, facilities, contracts, and unlocked capability, an airline may use:

- airport-provided handling;
- a third-party handler;
- partner-airline handling; or
- its own handling operation.

Airport ownership is not required for self-handling. An airline may establish its own operation with Airport Access, appropriate space, equipment, staff, and approval. An airport owner may later operate a handling company serving several airlines.

Handling affects cost, turnaround time, reliability, baggage performance, and usable capacity. Airport Management owns the physical facility and local availability; the detailed work, staff, and contracts belong to the appropriate handling or operations systems.

### 9.2 Maintenance

Hangars have aircraft-size, service-type, and simultaneous-capacity limits. A hangar designed for small aircraft cannot service an A380 merely because both are called hangars.

Airport Management owns the physical hangar and its space and compatibility. Maintenance owns inspections, repairs, labor, parts, certification, downtime, and return to service.

### 9.3 Fuel

Airport Management owns physical fuel infrastructure, including:

- land;
- storage tanks;
- pipelines;
- refueling equipment; and
- delivery capacity.

If an airline has no private or leased fuel-storage operation, it buys through the airport or local fuel provider and pays the applicable retail and service charges.

With Airport Access and suitable facilities, an airline may build or lease tanks, order fuel from suppliers in bulk, store inventory, and reduce unit cost. It also accepts inventory, capacity, supply, and price risk.

Fuel prices fluctuate through market behavior, supply conditions, and events. Fuel Management owns supplier purchases, inventory, stock valuation, prices, consumption, and replenishment decisions. Finance records the resulting transactions.

An airport owner may operate shared fuel infrastructure and sell fuel services to multiple airlines.

### 9.4 Cargo

Cargo is preserved as a first-class future part of airport architecture even while initial development focuses on passengers.

Airport infrastructure may include:

- cargo stands;
- cargo terminals;
- warehouses;
- customs processing;
- cold storage; and
- cargo-handling capacity.

Detailed cargo demand, booking, products, and operations belong to a future Cargo system.

## 10. Future Airport Development

### 10.1 Simplified strategic placement

Airport expansion must not become a detailed construction game.

The intended future interface uses simple lines, boxes, templates, or anchor points:

- draw a line for a runway;
- draw or place a box for a terminal;
- tap or mark an area for gates, stands, hangars, cargo, fuel, or parking;
- resize or rotate the template; and
- confirm the strategic location.

An automatic airport connector or plotter recognizes the occupied area and creates appropriate supporting geometry such as taxiway links, apron connections, gate connections, service access, and internal movement paths.

The player chooses what to build and where it belongs. The game handles minor construction geometry.

Before confirmation, the system should warn about major effects such as insufficient land, obstacles, unsafe runway orientation, unreachable facilities, required demolition, approach-path conflicts, excessive connector cost, and lost future expansion space.

### 10.2 Master planning

Future airport owners may reserve land or corridors for later development, including:

- future runways;
- terminal expansion;
- cargo districts;
- maintenance areas; and
- surface-access improvements.

Poor placement may make future expansion more expensive, but the interface must warn the player before an avoidable layout choice causes severe long-term harm.

### 10.3 Project time and stages

Airport projects take real in-game time. A project may pass through:

- study and planning;
- government or regulatory approval;
- land preparation;
- construction;
- testing and certification; and
- opening.

Small work may take weeks or months. Major terminals, runways, reclamation, and replacement airports may take years.

Construction at an operating airport may reduce capacity through taxiway closures, stand loss, night work, runway resurfacing, temporary terminal congestion, or passenger inconvenience. The player may pay for phased or accelerated work to alter timing and disruption.

Projects may experience explained uncertainty from terrain, weather, material inflation, design changes, regulation, contractor quality, or acceleration. Overruns must not feel like unexplained random punishment. Risks should be visible before approval, and the game should explain changed cost or timing.

### 10.4 Forecasting and research

Development forecasts improve with staff, experience, research, and technology.

Early information may be uncertain and show only broad demand, congestion, cost, and risk ranges. Later capability may unlock better estimates of:

- demand and traffic;
- capacity gained;
- operating cost;
- construction time and disruption;
- revenue and break-even period;
- airline commitments;
- environmental and regulatory risk; and
- whether another bottleneck prevents the project from helping.

The early player takes informed risks rather than receiving perfect future knowledge.

## 11. Airport Ownership and Investment

Airport ownership is approved future scope. It supports the broader aviation-business fantasy but must remain subordinate to the airline-management core.

### 11.1 Acquisition routes

Possible routes to investment or control include:

- purchasing shares from government or private owners;
- financing expansion in exchange for newly issued shares;
- negotiating a direct buyout;
- obtaining an operating concession;
- participating in privatization or a public-private partnership; and
- building a new or replacement airport with approval.

Not every airport must be available for unrestricted purchase. Some may remain publicly owned while offering investment or operating concessions.

### 11.2 Share-based ownership

An airport company may be divided into shares representing 100 percent economic ownership.

Existing-share purchases transfer ownership from the selling government or private shareholder to the player. Newly issued shares send investment capital to the airport company and dilute existing owners, making expansion finance a possible route into ownership.

The approved simple future foundation is:

- one normal share class initially;
- one share gives one vote;
- dividends follow ownership percentage;
- ownership percentages unlock increasing information and influence;
- more than 50 percent normally grants operational control;
- a supermajority may be required for extraordinary corporate decisions; and
- 100 percent represents full economic ownership.

Detailed percentage thresholds, board rights, minority protections, shareholder agreements, negotiation rules, public markets, and acquisition workflows are not finalized and require a separate design discussion.

Share ownership does not magically grant the player's airline free slots, fuel, gates, or route rights. Advantages must arise through legal airport decisions, leases, contracts, facilities, and development agreements.

### 11.3 Negotiation and advisers

Buying toward control or full ownership should involve actual deals rather than one guaranteed purchase button. Sellers may demand a premium, investment commitments, employment guarantees, government approval, or other negotiated conditions.

Future acquisition staff may improve information and outcomes:

- financial advisers assess value;
- lawyers identify restrictions and liabilities;
- negotiators improve terms;
- engineers reveal infrastructure risks;
- accountants examine debt and reporting; and
- government-relations staff support approvals.

Better staff should provide better information and negotiation results rather than merely changing an unexplained random roll.

### 11.4 Competitor access and regulation

Competitors generally remain able to use a player-controlled airport. The player competes through facilities, long-term leases, development, service quality, operational efficiency, and fees within regulation.

Airport control may permit aggressive or dark strategies, including preferential investment, high competitor fees, scarce-facility control, or redevelopment choices that strengthen the player's airline. The game need not forbid every hostile decision, but the world reacts through:

- competitors leaving or challenging the action;
- shareholder disputes;
- fines and reputation loss;
- government or regulatory investigation;
- forced access or pricing rules;
- concession termination;
- forced divestment; or
- investment in competing airports.

Consequences may also follow unsafe capacity declarations, discriminatory access, neglected maintenance, monopoly abuse, or environmental and noise violations.

### 11.5 Revenue and costs

An airport operator may earn from:

- landing and departure fees;
- passenger charges;
- gates and stands;
- parking;
- terminal and facility leases;
- hangars;
- handling;
- fuel infrastructure;
- cargo;
- retail and concessions;
- advertising;
- property and hotels;
- ground transport; and
- other passenger services.

Airport commercial activity supports aviation gameplay; it should not turn Airline Tycoon into a shopping-mall simulator with occasional aircraft.

Airport ownership also brings substantial costs and risks:

- staff;
- security;
- fire and rescue;
- maintenance and pavement upkeep;
- utilities;
- terminal operation;
- construction debt and finance;
- regulatory and environmental compliance;
- insurance; and
- disruption and repair.

Owned airports are potentially profitable businesses, not free money.

### 11.6 Internal group charges

When the player's group owns both an airline and an airport, the airline still records normal airport charges and the airport records the corresponding revenue.

At consolidated group level, the internal payment cancels except for real underlying costs. Separate accounting preserves an honest view of whether the airline and airport businesses are individually healthy.

## 12. Passenger and Airline Effects

Passenger choice remains airline- and service-centered. Airport quality is not an independent universal preference score that overrides the airline choice.

Passengers primarily evaluate the available airline product through factors owned by Passenger Simulation, such as route, fare, timing, duration, connections, reliability, airline reputation, cabin, and service.

Airport conditions influence that product through operational consequences:

- congestion creates delays;
- weak handling harms turnaround or baggage performance;
- missing facilities prevent certain services;
- poor transfer infrastructure affects feasible connections;
- high airport fees affect airline cost and pricing;
- gate or stand limitations affect operations; and
- poor ground access may limit the bookings the airline can capture.

Competing airports in one metropolitan area therefore matter through the airline services that use them and the operational opportunities they provide. The system should not independently make passengers abandon an airline merely because another terminal has better cosmetic quality.

Ground transportation is represented through strategic services, contracts, or investments rather than a full road-building simulation. An airline or airport may pay recurring costs for better connections, offer taxi or hotel pickup service, or help fund bus, rail, metro, or highway access to increase reachable bookings and improve the airline product.

## 13. Restrictions, Weather, and Emergencies

Airports may have:

- operating hours;
- overnight closures;
- noise curfews;
- aircraft-type restrictions;
- runway-direction restrictions;
- delayed-flight exemptions; and
- curfew penalties.

Weather capability depends on the represented historical technology and local infrastructure, including navigation aids, lighting, runway equipment, drainage, deicing, procedures, and staff capability. These can reduce but never eliminate weather disruption. Detailed live weather effects belong to Airport Operations.

Airports may accept emergency or weather diversions without normal commercial route rights. A diversion still requires physical aircraft compatibility and creates fees, passenger disruption, fuel and handling needs, and aircraft-positioning consequences. It does not grant permanent route permission.

### 13.1 Player interface

Airport Management should be presented through the game's office-style interface rather than as one abstract spreadsheet screen. The player may use computers, phones, plans, reports, and other office objects to open the relevant management views.

The airport workspace should eventually provide access to:

- airport overview and represented layout;
- infrastructure, compatibility, and capability;
- congestion, queues, slots, and operating restrictions;
- facilities, leases, Airport Access, and airline arrangements;
- fees, costs, and financial performance when invested or owned;
- development plans and construction projects;
- forecasts and research-limited analysis; and
- ownership, shareholders, and negotiations when those systems exist.

The world map remains the primary view for the airline's network, routes, airport relationships, and current aircraft locations. Airport Management may open or focus the selected airport on that map without replacing the wider network view.

## 14. System Boundaries

| System | Responsibility |
|---|---|
| Airport Management | Owns airport history, footprint, infrastructure, compatibility, capability, physical and forecast capacity, facilities, local restrictions, fees, access opportunities, development, and future ownership. |
| Airport Operations / ATC | Owns live arrival and departure queues, runway sequencing, taxi movement, congestion, diversions, and actual airport events. |
| Scheduling | Requests exact planned movement opportunities, assigns flights, and owns published aircraft rotations and timetables. |
| Aircraft Operations | Owns each aircraft's actual location, movement state, delay propagation, and current operational condition. |
| Market & Route Management | Owns country access, route rights, airport-pair market participation, and market presence. |
| Base Management | Owns the airline's Operating Base role, aircraft-stationing permission, and local operational arrangements acquired by the airline. |
| Hub Management | Owns Hub applications, passenger-connection permission, Hub XP, Hub levels, and connecting-network benefits. |
| Fleet Management | Owns aircraft and persistent home-base assignments. |
| Passenger Simulation | Owns traveler demand, itinerary evaluation, booking, and reactions to the airline product and airport-caused operational effects. |
| Fuel Management | Owns fuel suppliers, purchases, prices, storage inventory, replenishment, and consumption. |
| Maintenance | Owns inspections, repair work, labor, parts, certification, downtime, and return to service. |
| Cargo | Owns future cargo demand, products, bookings, and detailed cargo operations. |
| Finance | Records fees, leases, construction, operating costs, revenues, internal group charges, financing, investment, and ownership returns. |

Airport Management supplies conditions and infrastructure to these systems. It must not duplicate their authoritative state or bypass their rules.

## 15. Staged Implementation

The complete architecture is a destination, not a requirement for the first playable build.

Airport Management follows the project-wide stable-playable-stage rule:

```text
Implement the smallest complete airport support required by the current game.
Stabilize the playable loop.
Add one connected airport layer.
Test and stabilize again.
Repeat without discarding the approved architecture.
```

The earliest playable airport representation may contain only:

- airport identity and location;
- route availability;
- basic aircraft compatibility; and
- a simplified operating fee.

New-game scenarios must provide enough immediately usable aircraft, rights, routes, airport support, and other starting assets for the player to operate the basic loop. Real construction, aircraft-order, approval, and scheduling lead times become strategic once the airline is already playable; the player should not begin by waiting through a long empty period before their first meaningful action.

Later stable stages may add, one layer at a time:

- opening dates and historical changes;
- operating hours and restrictions;
- runways and compatibility detail;
- gates, stands, and parking;
- Airport Access and leases;
- capabilities and certifications;
- congestion forecasting;
- live ATC queues and delay propagation;
- slots;
- handling, fuel, maintenance, and cargo facilities;
- player-funded upgrades;
- simplified placement and the automatic connector;
- airport shares, control, and ownership; and
- dynamic AI airport development.

The exact order is chosen according to the next smallest valuable addition to the playable airline loop. No stage should become a collection of half-built airport systems.

## 16. Non-Goals and Deferred Decisions

This architecture intentionally does not finalize:

- exact airport data schemas or persistent field names;
- exact Regional distance thresholds;
- capability scoring or interface summaries;
- runway, taxiway, gate, stand, terminal, or ATC formulas;
- slot-allocation and use thresholds;
- Airport Access prices and approval requirements;
- facility lease, construction, and maintenance prices;
- detailed fuel-market formulas;
- cargo simulation;
- construction costs, times, and overrun probabilities;
- exact forecasting research and technology unlocks;
- AI airport acquisition and development behavior;
- exact share-percentage privilege thresholds;
- board governance, shareholder agreements, and minority protections;
- acquisition negotiation mechanics;
- concessions, privatization, and public-market mechanics; or
- exact airport-ownership regulation and enforcement formulas.

New persistent fields must be defined in `Data/Templates/template_reference.txt` or its approved canonical successor before code implementation.

## 17. Finalized Architecture

The following decisions should not change without redesigning Airport Management:

```text
Airline Tycoon remains an airline game, not a detailed airport-building game.

Airports and their default development follow the historical game year.
Player-controlled airports leave the historical timeline and develop through
the player's decisions. AI-controlled airports may develop dynamically.

Airport capability comes from separate infrastructure, service, technology,
and certification states. Hub level does not develop the airport.

Domestic service remains within one country. Regional service is international
within a defined distance. Full International service exceeds that limitation.

Airport Access is required for a permanent airline footprint, not for an
ordinary flight. It does not replace country access, route rights, or slots.

Airport capacity has multiple bottlenecks. Each airport may eventually operate
its own ATC and movement simulation; simultaneous scheduled times do not imply
simultaneous runway use.

Slots remain separate operational assets and scarce coordinated-airport slots
may be subject to use-it-or-lose-it rules.

Airport expansion uses simplified lines, boxes, templates, or anchor points.
The player chooses strategic placement and an automatic connector handles minor
taxiway, apron, gate, service, and internal-routing geometry.

Airport ownership is future share-based gameplay. Control provides influence
but not magical free airline privileges, and competitor access remains subject
to regulation and believable consequences.

Airport revenue is paired with serious operating, maintenance, financing, and
regulatory costs. Internal airline-airport charges remain visible in separate
entity accounts and cancel only in consolidated group reporting.

Passenger choice remains airline- and service-centered. Airport conditions
affect the airline product through operations, cost, access, and reliability.

The architecture is implemented through stable playable stages, beginning with
only the airport support required by the current airline gameplay loop.
```
