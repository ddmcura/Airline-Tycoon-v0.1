# Airline Tycoon - Economy Simulation Architecture

> **Status:** Approved architecture. This document defines the separation between cash, earned revenue, liabilities, assets, expenses, profit, company value, entity accounts, currencies, and financial distress. It also defines how bookings, operated flights, aircraft, fuel, maintenance, and connecting itineraries affect airline finances. It does not finalize formulas, prices, tax rules, loan underwriting, exchange-rate generation, persistent schema fields, or detailed passenger compensation.

## 1. Purpose and Core Philosophy

Economy Simulation explains where the airline's money comes from, where it goes, what the company owns, what it owes, and whether its operations are sustainable.

The system should be believable without requiring the player to be an accountant.

The core separation is:

```text
Cash
    money currently available

Revenue
    money earned by delivering goods or services

Expense
    economic cost incurred during the period

Asset
    something valuable the company owns or controls

Liability
    an obligation the company still owes

Profit
    earned revenue minus expenses
```

These concepts must not be collapsed into one balance.

## 2. Cash Is Not the Same as Revenue

An airline normally receives ticket cash before it has flown the passenger.

For example:

```text
Passenger books a future flight for PHP 5,000.
```

At booking:

```text
Cash increases by PHP 5,000.
Unflown Ticket Obligation increases by PHP 5,000.
Earned Passenger Revenue does not increase yet.
```

The airline holds the passenger's money but still owes the promised transport or an appropriate later remedy.

When the booked service is delivered:

```text
Unflown Ticket Obligation decreases.
Earned Passenger Revenue increases.
```

No second ticket payment is created at flight completion because the cash was already collected.

If the booking is refunded before service is delivered:

```text
Cash decreases.
Unflown Ticket Obligation decreases.
No Passenger Revenue is earned.
```

The player-facing interface may use plain labels such as `Advance Ticket Sales` or `Unflown Tickets` instead of requiring accounting terminology.

## 3. Booked Fares and Revenue Recognition

Every confirmed booking retains the fare actually paid.

Later changes to the route's currently advertised fare do not rewrite existing tickets.

Passenger revenue is recognized when the relevant booked flight leg is actually carried. A booking is not earned merely because:

- it was created;
- cash was received;
- the flight was scheduled;
- the departure date arrived; or
- the passenger was assigned to an itinerary.

Aircraft Operations supplies the actual completed-carriage outcome. Booking supplies the fare and booked passenger batch. Finance performs settlement from those authoritative facts.

If a passenger is not carried, the amount remains an obligation until Passenger Service and the applicable fare or policy rules resolve it through rebooking, credit, forfeiture where permitted, or refund.

Detailed no-show, voluntary cancellation, flexible-ticket, and forfeiture rules remain Passenger Service and fare-product work.

## 4. Ancillary Revenue

Flight revenue may include more than the base ticket.

Possible ancillary products include:

- meals and drinks;
- internet access;
- checked or excess baggage;
- seat selection;
- upgrades;
- lounge access;
- onboard entertainment;
- duty-free or onboard retail later; and
- other airline-provided services.

### 4.1 Prepaid extras

When a passenger prepays for a future extra:

```text
Cash increases at purchase.
The undelivered-service obligation increases.
Revenue is recognized only when that service is delivered.
```

### 4.2 Onboard purchases

A product purchased and delivered during the flight normally creates cash and revenue at that time.

### 4.3 Flight revenue

Conceptually:

```text
Earned Flight Revenue
= carried ticket fares
 + delivered prepaid extras
 + onboard sales
 + other delivered flight services
```

Exact products, prices, costs, take-up rates, refunds, and service-quality effects belong to future Product, Cabin Service, Passenger Service, and technical design.

## 5. Connecting Itinerary Revenue

Stage 1 prices a connecting journey as the sum of its booked leg fares.

For example:

```text
DVO -> MNL fare: PHP 3,000
MNL -> NRT fare: PHP 15,000

Total itinerary price: PHP 18,000
```

Each leg earns its own booked fare when that leg is carried:

```text
DVO -> MNL earns PHP 3,000 after that leg is flown.
MNL -> NRT earns PHP 15,000 after that leg is flown.
```

This removes the need for a separate Stage 1 proration formula.

For an unpartnered self-connection, each airline sells and settles its own separate leg ticket.

Future interline, codeshare, alliance, bundled through-fare, discount, commission, and revenue-sharing arrangements belong to Partnership architecture. They must define their own settlement rather than changing the Stage 1 leg-fare rule silently.

## 6. Flight Profit and Contribution

An individual flight's direct economic contribution is:

```text
Flight Contribution
= earned ticket revenue
 + earned ancillary revenue
 - flight-specific operating expenses
```

Flight-specific costs may include:

- fuel consumed;
- airport movement and passenger charges;
- handling services;
- navigation or airspace charges;
- aircraft-variable operating cost;
- flight-specific crew cost later;
- catering and onboard product cost;
- maintenance cost accrued from hours or cycles; and
- disruption costs attributable to the operation.

`Flight Contribution` is not necessarily the company's final profit because company overhead remains outside an individual flight.

## 7. Network Contribution

A feeder flight may be weak in isolation but enable profitable connecting travel elsewhere in the airline network.

Reports should therefore distinguish:

```text
Direct flight or route contribution

Downstream or network revenue enabled
```

Network contribution is an analytical attribution. It never creates extra revenue or counts one ticket twice.

For example, DVO -> MNL may show the direct fare earned on that leg while also reporting that its passengers purchased onward MNL -> NRT legs. The onward fare remains revenue of the actual onward flight.

Exact attribution methods remain reporting and technical design. They must preserve financial conservation.

## 8. Costs Follow Actual Events

Costs are recorded when their real cost-causing event occurs, not merely because a schedule forecast expected them.

Examples:

- handling costs occur when handling services are supplied;
- fuel cash cost occurs when fuel is purchased or uplifted under the applicable arrangement;
- fuel operating expense follows consumption;
- airport movement charges follow the applicable movement event;
- passenger charges follow actual passenger handling or carriage rules;
- navigation charges follow actual operation;
- parking costs follow real occupation and duration;
- cancellation retains costs already incurred; and
- fixed costs occur on their contractual calendar dates.

Scheduling may forecast costs, but forecasts do not write actual financial transactions.

## 9. Cancelled and Disrupted Flights

Cancelling a flight does not erase costs already incurred.

Possible retained costs include:

- completed handling;
- fuel purchased or uplifted;
- parking or gate occupation;
- staff and contractor costs;
- passenger care;
- rebooking costs;
- refund or compensation costs; and
- other services already delivered.

Ticket cash for an uncarried passenger remains an obligation until resolved.

Aircraft Operations records operational facts and causes. Passenger Service determines passenger recovery under player policy and applicable rules. Finance records the resulting transactions.

This document does not define compensation eligibility or amount.

## 10. Fuel as Inventory and Expense

Fuel is valuable inventory when purchased and an operating expense when consumed.

At purchase:

```text
Cash decreases.
Fuel Inventory increases.
```

During operation:

```text
Fuel Inventory decreases by actual consumption.
Fuel Expense increases by the value of fuel consumed.
```

This is especially important when an airline buys bulk fuel at a Base, Hub, or owned facility and stores it for later use.

If the airline instead purchases fuel directly for immediate uplift, purchase and consumption may occur close together while remaining conceptually distinct.

Fuel Management owns suppliers, quantities, storage, prices, inventory method, availability, and consumption inputs. Finance records cash, inventory value, and expense.

Exact fuel-valuation method, hedging, spoilage, taxes, and market behavior remain future Fuel and technical work.

## 11. Aircraft Purchase and Asset Value

Buying an aircraft reduces cash immediately and creates an owned aircraft asset.

For example:

```text
Purchase aircraft for PHP 500 million.

Cash:                 -PHP 500 million
Aircraft asset value: +PHP 500 million
```

The purchase appears as investment spending in Cash Flow. It is not treated as a PHP 500 million operating loss on the purchase date because the company exchanged cash for a valuable aircraft.

Aircraft acquisition costs, delivery payments, deposits, financing, import costs, preparation, and entry-into-service treatment remain Aircraft Market and technical work.

## 12. Book Value and Depreciation

Aircraft book value uses simple straight-line depreciation initially.

Conceptually:

```text
Annual Depreciation
= (Capitalized Aircraft Cost - Expected Residual Book Value)
  / Accounting Useful Life
```

Depreciation gradually records the economic use and aging of the aircraft as an expense. It does not cause another cash payment when posted.

Major approved capital work—such as a substantial overhaul, life extension, or refurbishment—may add a capitalized value that depreciates over its own approved remaining life.

Routine maintenance is an expense rather than automatic asset appreciation.

Exact useful lives, residual values, capitalization thresholds, posting frequency, and overhaul treatment remain technical and balancing decisions.

## 13. Aircraft Market Value

Aircraft market value estimates what the aircraft could sell for under current conditions. It is separate from book value.

Market value may appreciate or depreciate according to factors such as:

- age;
- physical condition;
- accumulated flight hours and cycles;
- maintenance status and records;
- recent overhaul or refurbishment;
- cabin condition;
- damage or accident history;
- model reliability and desirability;
- fuel efficiency;
- parts and maintenance availability;
- manufacturer support;
- market supply and demand;
- regulation, certification, and noise limits;
- scarcity; and
- possible historical or collector value later.

An aircraft may therefore have:

```text
Book value:   PHP 300 million
Market value: PHP 360 million
```

or:

```text
Book value:   PHP 300 million
Market value: PHP 220 million
```

An unrealized market-value change does not create cash or ordinary operating profit. Sale settlement records the actual proceeds and resulting gain or loss under future technical rules.

Aircraft Market owns offers and market behavior. Maintenance owns condition and work history. Finance consumes those inputs for valuation and reporting.

## 14. Company Value

The game should present two useful company-value concepts.

### 14.1 Accounting net worth

Conceptually:

```text
Accounting Net Worth
= Cash
 + Aircraft Book Value
 + Fuel and Other Asset Value
 - Loans
 - Unflown Ticket Obligations
 - Other Liabilities
```

### 14.2 Estimated company market value

This estimate substitutes realistic current market values for assets where available.

```text
Estimated Company Market Value
= Cash
 + Estimated Aircraft Resale Value
 + Estimated Market Value of Other Assets
 - Debt and Other Liabilities
```

Market value is an estimate, not spendable cash. The player realizes it only through a sale, investment, acquisition, or other transaction.

## 15. Maintenance Cash and Accrued Cost

Actual maintenance cash is paid when maintenance services, parts, labor, or contracts require payment.

However, route and aircraft reports also need a long-term maintenance cost associated with the hours and cycles that create future maintenance requirements.

Reports should therefore distinguish:

```text
Actual Maintenance Cash Paid

Maintenance Cost Accrued from Flight Hours and Cycles
```

The accrual helps show whether a flight or route is economically sustainable before a major maintenance bill occurs. It must not charge the airline twice.

Maintenance owns work requirements, actual work, parts, labor, downtime, and release to service. Finance owns payment, accrual, expense recognition, and reporting.

Exact reserve or accrual formulas remain Maintenance and Economy technical design.

## 16. Leases, Loans, and Financing

Lease and financing obligations occur according to their contracts whether or not the aircraft is profitable, scheduled, grounded, or underused.

Possible obligations include:

- lease deposits;
- recurring lease payments;
- usage-based lease charges;
- maintenance reserves;
- loan principal;
- interest;
- arrangement fees;
- balloon payments; and
- collateral or covenant consequences.

Interest is an expense. Repaying borrowed principal reduces cash and debt but does not become an operating expense.

Taking a loan increases cash and debt. It does not create revenue or profit.

Loan availability and terms may depend on company assets, debt, cash flow, financial history, lender confidence, collateral, and economic conditions. Loans are possible but not guaranteed.

Exact financing products, approval, rates, security, defaults, and restructuring remain future Marketplace, Finance technical, and balancing work.

## 17. Fixed and Calendar-Based Costs

Some costs belong to the company or period rather than one flight.

Examples include:

- salaries and office staff;
- headquarters and office costs;
- insurance;
- software and system subscriptions;
- licenses and recurring access fees;
- Hub overhead;
- leases and financing;
- marketing departments and campaigns;
- administration;
- future taxes; and
- other corporate overhead.

These costs occur through contractual or calendar events under continuous simulation time. They must not be charged once per flight merely for convenience.

## 18. Flight Contribution and Company Profit

Reports distinguish flight economics from company-wide overhead.

```text
Flight Contribution
= flight revenue - flight-specific expenses

Operating Profit
= all operating contributions - company overhead

Net Profit
= operating profit
  - financing costs
  - depreciation
  - taxes and other non-operating effects when implemented
```

An optional future report may allocate overhead across routes for analysis. Such allocation does not alter actual accounts or create new expense.

## 19. Entities and Consolidated Reporting

Airlines, subsidiaries, sister airlines, and future airport businesses maintain separate accounts.

If one group owns both an airline and an airport:

```text
Airline records airport charge as an expense.
Airport records the same charge as revenue.
```

At consolidated group level, the internal charge cancels. Real external costs remain.

This provides honest entity-level performance while preventing the group from counting internal payments as new wealth.

Exact ownership hierarchy, transfer pricing, minority interests, dividends, and intercompany lending remain future Group Management and technical work.

## 20. Currency Architecture

Each transaction retains:

- original transaction currency;
- original amount;
- transaction date and time;
- exchange rate used for accounting conversion; and
- value in the entity's base accounting currency.

For example:

```text
Airport fee: JPY 1,000,000
Accounting value: equivalent amount in the airline's base currency
using the exchange rate at transaction time
```

Each financial entity has one base accounting currency. The player may select another display currency without changing the underlying accounts.

Later exchange-rate movements do not rewrite historical revenue or expense. They may affect unsettled foreign-currency balances and future transactions under later technical rules.

Exchange-rate history, generation, volatility, conversion spread, hedging, and currency gains or losses remain future Economy technical work.

## 21. Inflation and Historical Economy

The architecture preserves a world economy that may vary by historical game year.

Inflation may eventually influence:

- fares;
- aircraft prices;
- wages;
- fuel;
- airport and navigation fees;
- maintenance;
- insurance;
- construction;
- financing; and
- other costs.

Inflation does not automatically mean every price changes identically. Individual markets and contracts may behave differently.

Exact inflation indexes, historical data, rebasing, economic cycles, and world-event effects remain technical and Dynamic World work.

## 22. Financial Distress

Negative cash does not immediately end the game.

When cash becomes negative, the airline enters financial distress. Negative cash represents an unmet financing need, emergency overdraft, or other short-term obligation rather than free money.

Distress may create:

- warnings;
- emergency interest or penalties;
- reduced lender confidence;
- restricted investment;
- pressure to sell assets;
- schedule or route reductions;
- refinancing or new-loan attempts;
- outside investment or restructuring later; and
- eventual bankruptcy.

The player may attempt recovery through loans, aircraft or asset sales, reduced operations, revised schedules, route closure, investment, or other future tools.

## 23. Quarterly Bankruptcy Rule

At each quarter-end review:

```text
If cash is negative:
    add one consecutive negative-cash quarter

If cash is zero or positive:
    reset the consecutive counter to zero
```

If cash remains negative at three consecutive quarter-end reviews:

```text
Declare bankruptcy.
```

Quarterly losses alone do not trigger this rule. An airline may report a loss while still having positive cash and sufficient resources.

The bankruptcy trigger evaluates cash, not merely profit or accounting net worth.

Exact quarter calendar, emergency overdraft mechanics, lender intervention, administration, asset liquidation, rescue, restructuring, and bankruptcy endgame presentation remain technical and future gameplay design. The three-consecutive-quarter negative-cash trigger is the approved core rule.

## 24. Player-Facing Financial Reports

The player should not need formal accounting education. Reports use plain language and explain their relationships.

### 24.1 Cash Flow

Shows actual cash received and paid during the period.

Examples:

- advance ticket cash;
- ancillary purchases;
- aircraft purchases and sales;
- fuel purchases;
- loan proceeds and repayments;
- operating payments;
- refunds; and
- closing cash.

### 24.2 Profit and Loss

Shows revenue earned and expenses incurred during the period.

Examples:

- carried passenger revenue;
- delivered ancillary revenue;
- fuel consumed;
- handling and airport costs;
- maintenance expense and accrual;
- overhead;
- lease and interest expense;
- depreciation; and
- profit or loss.

### 24.3 Company Position

Shows what the company owns and owes.

Examples:

- cash;
- aircraft book value;
- estimated aircraft market value as a separate view;
- fuel inventory;
- other assets;
- loans;
- unflown-ticket obligations;
- other liabilities;
- accounting net worth; and
- estimated market value.

### 24.4 Operational profitability

Additional views may show:

- flight contribution;
- route contribution;
- aircraft contribution;
- Hub and network contribution;
- direct versus connecting revenue;
- ancillary revenue;
- actual versus forecast costs; and
- maintenance cost accrued by hours and cycles.

## 25. Forecasts Versus Actual Accounts

Scheduling, Route Management, Fleet Management, and airport investment screens may display forecasts.

Forecasts never create actual transactions.

The interface must distinguish:

```text
Forecast
Committed contract or obligation
Actual cash transaction
Recognized revenue or expense
```

Forecast accuracy may depend on available information, research, staff, and future management capability.

## 26. Transaction and Accounting Principles

The technical design should eventually use an auditable transaction or journal model rather than allowing unrelated systems to mutate totals invisibly.

At architecture level, every material financial event should identify:

- entity;
- time;
- source system and source event;
- original currency and amount;
- base-currency amount;
- affected cash, asset, liability, revenue, or expense category;
- related flight, aircraft, route, airport, contract, or passenger batch where applicable; and
- reversal or correction relationship when needed.

Exact ledger structure, double-entry implementation, aggregation, and schema remain technical decisions.

The player does not need to see accounting internals unless they request detailed reports.

## 27. Stable Implementation Stages

The complete economy must be introduced through stable playable stages.

### Stage 1 - Booking, flight, and cash separation

The first complete stage may provide:

- cash received at booking;
- unflown-ticket obligation;
- booked fare retained on booking batches;
- ticket revenue recognized per carried leg;
- basic ancillary revenue;
- actual flight fuel and operating expense;
- simple Cash Flow and Profit reports; and
- separation of booking, carriage, and settlement.

### Stage 2 - Assets and recurring costs

Add:

- aircraft purchase as investment spending and an asset;
- straight-line depreciation;
- simple market-value estimates;
- fuel inventory;
- leases and loan schedules;
- fixed calendar costs;
- maintenance cash and accrual; and
- Company Position reporting.

### Stage 3 - Entity and distress depth

Add:

- separate subsidiary and airport accounts;
- consolidated group reporting;
- multi-currency transactions;
- lender decisions and distress actions;
- quarterly negative-cash review; and
- bankruptcy endgame.

### Later stages

Later development may add:

- historical inflation and exchange markets;
- taxes;
- advanced financing;
- interline and alliance settlement;
- detailed passenger compensation;
- hedging;
- airport investment and ownership accounting;
- group restructuring;
- public markets or shareholders; and
- sophisticated valuation.

Every stage must remain small, stable, testable, and playable.

## 28. System Boundaries

| System | Responsibility |
|---|---|
| Economy Simulation | Owns economy-wide conditions, inflation direction, exchange environment, accounting principles, financial distress, and bankruptcy review. |
| Finance | Records transactions, cash, assets, liabilities, revenue, expenses, profit, entity accounts, and reports. |
| Booking | Owns confirmed booking batches, booked fares, products, passenger counts, and unflown reservation state. |
| Aircraft Operations | Owns actual carriage, operational timing, fuel-use and cost inputs, cancellations, and completed operational outcomes. |
| Passenger Service | Owns rebooking, credits, refunds, compensation eligibility, care, forfeiture, and passenger recovery decisions. |
| Scheduling | Owns the planned timetable and supplies forecasts; it does not post actual revenue or expense. |
| Fleet Management | Owns aircraft assets and configuration relationships; it displays financial facts supplied by Finance. |
| Aircraft Market | Owns purchase and sale offers, market conditions, counterparties, and estimated resale opportunities. |
| Maintenance | Owns condition, hours/cycles requirements, work, parts, labor, downtime, overhaul, and release; Finance records resulting value and cost. |
| Fuel Management | Owns suppliers, purchase decisions, storage, physical inventory, price, uplift, and consumption; Finance records monetary effects. |
| Airport Management and Operations | Supply fees, services, occupation, movement, passenger, handling, and investment events; Finance records them. |
| Ground Handling | Owns services, contracts, staff, equipment, and delivered handling work; Finance records cost. |
| Base & Hub Management | Owns roles, facilities, Hub overhead drivers, and connecting activity; Finance records fees and overhead. |
| Partnerships and Alliances | Future owner of interline fares, commission, protection, and revenue-sharing agreements. |
| Airline Group Management | Future owner of subsidiaries, ownership relationships, internal transactions, consolidation scope, and group strategy. |
| Dynamic World | Supplies historical economy, events, recessions, booms, policy, and market changes. |

Economy and Finance consume authoritative events from these systems. They must not duplicate or override operational ownership.

## 29. Preserved Spillover

The following must be preserved for later documents:

- **Economy Technical Specification:** transaction model, ledger, account categories, posting rules, revenue settlement, depreciation schedules, exchange conversion, quarter review, migrations, and tests.
- **Passenger Service:** refunds, credits, rebooking, compensation, passenger fault, no-shows, voluntary changes, and fare restrictions.
- **Aircraft Market:** offers, market-price calculation, resale, order payments, deposits, delivery, lessors, and financing products.
- **Maintenance:** maintenance events, reserves, accrual drivers, overhaul classification, condition, and value effects.
- **Fuel Management:** suppliers, storage, valuation, bulk purchases, hedging, uplift, and consumption.
- **Partnerships and Alliances:** through-fares, commissions, revenue sharing, settlement, codeshares, and protected itineraries.
- **Airline Group Management:** entity hierarchy, consolidation, internal charges, transfer pricing, minority ownership, and dividends.
- **Dynamic World:** inflation, exchange rates, economic cycles, events, taxes, and regulation.
- **Bankruptcy and Restructuring:** emergency funding, administration, rescue, liquidation, creditor behavior, and endgame presentation.

## 30. Non-Goals and Deferred Decisions

This architecture intentionally does not finalize:

- exact fare or ancillary prices;
- accounting account names or persistent schema fields;
- transaction-ledger implementation;
- ticket forfeiture, refund, or compensation formulas;
- fuel inventory valuation;
- airport, handling, navigation, crew, or maintenance prices;
- maintenance accrual formulas;
- depreciation life, residual value, or posting interval;
- aircraft market-value formula;
- lease and loan products, rates, approval, or security;
- overhead allocation methods;
- exchange-rate generation and currency gains or losses;
- inflation indexes;
- tax rules;
- quarter-calendar implementation;
- overdraft and emergency-credit mechanics;
- bankruptcy administration or liquidation;
- intercompany transfer pricing; or
- partnership revenue settlement.

New persistent fields must be approved in the canonical template/schema reference before code implementation.

## 31. Finalized Architecture

The following decisions should not change without redesigning Economy Simulation:

```text
Cash, revenue, expense, assets, liabilities, profit, book value, and market value
are separate concepts.

Ticket cash is received at booking. Until carriage, it remains an unflown-ticket
obligation rather than earned passenger revenue.

Every booking retains its actual fare. Passenger revenue is recognized per leg
only when that passenger is carried on the operated flight.

Prepaid extras create cash and an undelivered-service obligation. Revenue is
earned when the extra is delivered. Onboard purchases may create cash and
revenue during the flight.

Stage 1 connecting prices equal the sum of booked leg fares. Each leg earns its
own fare. Unpartnered airline changes remain separate tickets.

Network contribution is an analytical attribution and never duplicates revenue.

Costs follow actual cost-causing events. Cancellation retains costs already
incurred, while unearned ticket cash remains an obligation until resolved.

Fuel purchase reduces cash and creates inventory. Fuel consumption reduces
inventory and creates flight expense.

Aircraft purchase reduces cash and creates an asset. Straight-line depreciation
reduces book value and creates gradual expense rather than treating the entire
purchase as one operating loss.

Aircraft market value is separate and may appreciate or depreciate with age,
condition, hours, cycles, maintenance, overhaul, efficiency, support, regulation,
scarcity, and market demand. Unrealized value does not create cash.

Accounting net worth uses book values. Estimated company market value uses
estimated realizable asset values. Both remain distinct from cash.

Actual maintenance cash and accrued hours/cycles maintenance cost are reported
separately without charging the airline twice.

Flight contribution excludes company overhead. Company operating and net profit
include the relevant overhead, financing, depreciation, and later tax effects.

Loans increase cash and debt, not revenue. Principal repayment reduces cash and
debt; interest is expense. Lease and financing obligations remain due even when
an aircraft is grounded or unprofitable.

Fixed company costs occur on contractual calendar events rather than per flight.

Each airline, subsidiary, and future airport business keeps separate accounts.
Internal group transactions cancel only in consolidated reporting.

Transactions retain original currency and transaction-time exchange rate while
entity accounts use one base currency and interfaces may use a display currency.

Negative cash creates financial distress rather than immediate game over. Cash
below zero at three consecutive quarter-end reviews causes bankruptcy. Returning
to zero or positive cash at a quarter end resets the consecutive counter.

Player reports clearly separate Cash Flow, Profit and Loss, Company Position,
flight contribution, route contribution, and network contribution.

The architecture is introduced through small, stable, playable stages.
```

## Milestone 5A finance concurrency boundary

Schema-3 airlines add only a non-negative `finance_revision` optimistic-
concurrency token, initialized to zero. The strict future aggregate Booking
contract reserves a `finance_transaction_id`, and completed checkpoint topology
reserves transaction-ID ownership, but Milestone 5A creates no transaction,
changes no account balance, receives no cash, and recognizes no revenue.

Mixed-currency Booking competition is explicitly unsupported and must later
reject as `UNSUPPORTED_FARE_CURRENCY`; no exchange-rate or foreign-exchange
authority is added. Ticket cash receipt and the unflown-service obligation,
capacity commitment, refunds, and revenue recognition remain later execution
work. Existing accounts, balances, transactions, financial history, and
allocator positions are preserved by detached schema-2-to-3 migration.

## Milestone 5D ticket-sale posting

Each completed Booking checkpoint creates at most one positive ticket-sale
transaction per affected airline. Its immutable source is
`BOOKING_CHECKPOINT`, its source ID is the checkpoint ID, and its sorted source
Booking IDs include the paid Booking batches represented by the gross sale.
Under the debit-positive journal convention, cash is positive and the
unflown-ticket liability is equally negative, so entries sum to zero. Stored
category-normal balances for cash and the liability both increase by gross
sales. Passenger revenue is unchanged until later carriage.

An airline with only zero-fare confirmed Bookings receives no transaction and
no finance-revision increment; each such Booking has null transaction lineage
and still reserves capacity. A paid airline receives one transaction and one
finance-revision increment even when it also has zero-fare batches; only paid
batches appear in the transaction's source Booking IDs. Refunds, carriage,
revenue recognition, operating costs, cancellations, and disruption accounting
remain deferred.

## Milestone 6 flight-fulfilment settlement

Completion posts exactly one `FLIGHT_FULFILMENT` transaction. Paid carriage
debits unflown-ticket liability and credits passenger revenue; all flights
debit operating expenses and credit cash for the complete Balanced simplified
cost. Zero-revenue flights have two entries and paid flights have four. Cash
changes only for cost, liability falls only by recognized paid Booking value,
and negative cash remains permitted. Zero-fare passengers retain carriage and
result lineage without revenue lineage.

USD, PHP, and EUR use explicit immutable revision-1 profiles from the canonical
state schema. Their ratios are configuration calibration only: fulfilment never
reads legacy exchange rates, current markets, or runtime FX conversion.
