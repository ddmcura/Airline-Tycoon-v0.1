# Airline Tycoon
# Passenger Demand, Booking & Network Simulation Design Guide

> **Version:** Draft v1.0
>
> This document serves as the master design guide for Airline Tycoon's passenger demand and booking simulation.
>
> The objective is to simulate how people travel, not simply how routes fill with passengers.
>
> The philosophy is that **people have destinations; airlines merely provide ways to reach them.**

---

# Design Philosophy

Traditional airline games ask:

> "How much demand does this route have?"

Airline Tycoon instead asks:

> "Where do people want to go?"

This small difference changes the entire simulation.

Passengers exist independently of airlines.

Airlines simply compete to transport them.

This naturally creates:

- Hub-and-spoke systems
- Connecting passengers
- Tourism
- Business travel
- Domestic feeders
- International feeders
- Competition
- Network growth

without scripting every route individually.

---

# Core Architecture

One of the biggest discoveries during development was realizing that this is NOT one giant passenger system.

It is actually several independent systems working together.

```
Demand Generator
        │
        ▼
Booking Engine
        │
        ▼
Flight Simulation
        │
        ▼
Passenger Persistence
        │
        ▼
Future Demand
```

Each module has only one responsibility.

---

# 1. Demand Generator

Question answered:

> **Who wants to travel today?**

This system has absolutely no knowledge of airlines.

It simply creates travel intentions.

Example:

```
Origin:
Davao

Today's travel intentions

180 → Manila

140 → Cebu

50 → Tagbilaran

8 → Tokyo

1 → New York
```

Nobody has booked anything yet.

Passengers simply know where they want to go.

---

# Original Demand Formula

The original formula is still retained.

Every airport generates travel demand based on its characteristics.

Possible factors:

- Population
- GDP
- Tourism
- Business activity
- Airport importance
- Prestige
- Distance
- Historical demand

Conceptually:

```
Demand

=

Population

×

Travel Rate

×

Destination Attractiveness

×

Distance Modifier
```

Example:

```
MNL

Population

15,000,000

↓

8,000 travel intentions/day
```

```
DVO

Population

2,000,000

↓

1,000 travel intentions/day
```

Larger cities naturally create more travelers.

---

# Demand Belongs To City Pairs

Demand should NOT belong to routes.

Instead:

Every city contains destination weights.

Example:

```
DVO

Destination Weights

MNL
18%

CEB
14%

TAG
5%

NRT
0.8%

JFK
0.05%
```

When Davao generates 1000 travel attempts:

```
180

↓

MNL

140

↓

CEB

50

↓

TAG

8

↓

NRT

1

↓

JFK
```

Passengers now have destinations.

Still no bookings.

---

# The Hidden Origin-Destination Pool

Think of every city pair as having an invisible travel pool.

Example:

```
DVO

↓

NRT

Weight

0.8%
```

This does NOT mean passengers fly every day.

It means:

Whenever Davao generates travelers,

approximately 0.8%

want Tokyo.

Whether they actually book depends on the airline network.

---

# Booking Engine

Question answered:

> **Can the passenger actually reach the destination?**

Passenger wants:

```
DVO

↓

NRT
```

Possible airline itineraries:

```
Direct

DVO

↓

NRT
```

or

```
DVO

↓

MNL

↓

NRT
```

or

```
DVO

↓

CEB

↓

MNL

↓

NRT
```

or

```
No route exists.
```

Only AFTER an itinerary exists does booking occur.

---

# Itinerary Acceptance

Passengers dislike unnecessary connections.

Example acceptance:

```
Direct

100%
```

```
1 Connection

80%
```

```
2 Connections

50%
```

```
3 Connections

20%
```

```
4+

Almost nobody accepts.
```

Example:

```
8 passengers

want

DVO

↓

NRT
```

Available:

```
DVO

↓

MNL

↓

NRT
```

80% acceptance:

```
8

↓

6 bookings
```

Those six passengers occupy BOTH flights.

```
DVO

↓

MNL

+

MNL

↓

NRT
```

---

# Why Hubs Become Powerful

Initially:

```
MNL

↓

DVO
```

Only Manila passengers use it.

Later:

```
MNL

↓

NRT
```

Now possible:

```
DVO

↓

MNL

↓

NRT
```

The DVO→MNL route gains passengers without increasing local demand.

The network itself created traffic.

Exactly like real airline hubs.

---

# Demand Snowballs Naturally

Imagine adding:

```
MNL

↓

TAG
```

Now all of these become possible:

```
DVO

↓

MNL

↓

TAG
```

```
CEB

↓

MNL

↓

TAG
```

```
NRT

↓

MNL

↓

TAG
```

```
HKG

↓

MNL

↓

TAG
```

One new route unlocks demand from many cities.

---

# Tourism

Example itinerary:

```
USA

↓

MNL

↓

BOH

↓

PPS

↓

MNL

↓

USA
```

Domestic flights benefit from international arrivals.

Exactly like real airlines.

---

# Direct Flights Naturally Win

Initially:

```
A

↓

B

↓

D
```

Later:

```
A

↓

D
```

Passengers naturally switch.

No scripting required.

---

# Flight Simulation

Question answered:

> **Does the airplane actually transport the passenger?**

Responsibilities:

- Boarding
- Delays
- Aircraft movement
- Seat occupancy
- Arrival
- Fleet utilization

It never creates passengers.

It only transports bookings.

---

# Passenger Persistence

Question answered:

> **What happens after passengers arrive?**

Version 1:

Passengers disappear.

Future:

Passengers remain in the world.

Possible actions:

- Continue travelling
- Return home
- Stay longer
- Business trip
- Tourism
- Migration

This eventually creates realistic return demand.

---

# Visitor Pool Concept

Current concept.

Instead of tracking millions of passengers individually,

track population groups.

Example:

```
MNL

Visitors

USA

520

Japan

180

Australia

74
```

Every day:

Some return home.

Some continue elsewhere.

Flights simply move numbers.

No individual passenger objects.

---

# Benefits

Compared to traditional route demand:

✔ Real hubs

✔ Real tourism

✔ Connecting traffic

✔ Direct flights become valuable

✔ Domestic feeders

✔ International feeders

✔ Network effects

✔ Airlines compete naturally

---

# Unknowns

Still under discussion.

Questions:

- How long do tourists stay?
- How often do pools update?
- How are return trips scheduled?
- How do business travelers behave?
- How do migrants work?
- How much randomness is healthy?

These will evolve during development.

---

# Future Improvements

## Journey Types

Passengers can travel for different reasons.

Examples:

- Tourist
- Business
- Family Visit
- Student
- Worker
- Migration
- Cargo

Each behaves differently.

Example:

Tourist

```
USA

↓

MNL

↓

BOH

↓

PPS

↓

USA
```

Migration

```
USA

↓

DVO

(end)
```

---

## Itinerary Score

Instead of fixed acceptance percentages,

calculate a score.

Example:

```
100

-20 per connection

-5 per hour

-15 overnight layover

+15 direct

+10 airline reputation

+10 premium hub
```

Convert score into booking probability.

---

## Competing Airlines

Passengers compare:

- Price
- Connections
- Total time
- Reputation
- Reliability

The best itinerary wins.

---

## Seasonal Demand

Destination weights change.

Example:

```
Boracay

Summer

↑

Christmas

↑

Rainy Season

↓
```

---

## Dynamic World Events

Examples:

- Olympics
- Typhoons
- Expo
- Pandemics
- Wars

These temporarily alter destination weights.

---

## Loyalty

Passengers may prefer airlines they trust.

Example:

```
Preferred Airline

+

5%

booking chance
```

---

## Cargo

Cargo uses the exact same routing engine.

Only the demand generator changes.

---

# Recommended Implementation Roadmap

The final vision is ambitious.

Attempting to build everything immediately will significantly increase development complexity.

Instead, build the system in stages.

---

## Phase 1 — Stateless Booking Engine (Recommended for v1.0)

Goal:

Build a fun, playable airline game first.

Flow:

```
Generate Origin → Destination requests

↓

Search airline network

↓

Find itinerary

↓

Apply connection penalties

↓

Book seats

↓

Fly passenger

↓

Passenger disappears
```

Characteristics:

- No return trips
- No visitor tracking
- No persistent passengers
- Fast and simple

This validates that the network simulation itself is enjoyable.

---

## Phase 2 — Return Queue

Instead of tracking individuals,

store grouped return records.

Example:

```
Day 120

56 Tourists

Home:
USA

Current:
MNL

Stay:
5 Days
```

On Day 125:

Generate:

```
MNL

↓

USA
```

booking requests.

Benefits:

- Return demand exists.
- No passenger objects.
- Extremely lightweight.

---

## Phase 3 — Passenger Persistence Engine

Replace return queues with persistent world population.

Cities store population currently visiting.

Example:

```
MNL

Visitors

USA
520

Japan
180

Australia
74
```

Visitors may:

- Return home
- Continue travelling
- Stay longer
- Cancel
- Migrate

Flights simply move groups between cities.

This produces realistic tourism,

multi-city vacations,

business travel,

and domestic feeders.

---

# Why This Roadmap

Each phase builds directly upon the previous.

Nothing is thrown away.

The game remains playable throughout development.

Complexity grows gradually.

---

# Final Philosophy

The simulation should never ask:

> "How many passengers does this route have?"

Instead it should ask:

> "How many people want to travel from Origin A to Destination D?"

Then let the airline network solve that problem.

The stronger the network,

the more demand it captures.

Just like real airlines.

---

# Personal Notes

One of the most important realizations during development was that **there are actually two simulations running simultaneously.**

## Population Simulation

```
People

↓

Want to travel

↓

Choose destination

↓

Find itinerary

↓

Travel

↓

Stay

↓

Travel again
```

## Airline Simulation

```
Aircraft

↓

Routes

↓

Schedules

↓

Capacity

↓

Pricing

↓

Profit
```

These two simulations never directly control each other.

They communicate only through the **Booking Engine**.

This separation keeps the architecture modular, scalable, and easier to maintain while allowing future systems—tourism, migration, loyalty, cargo, alliances, and AI airlines—to plug into the same framework without major rewrites.

This design philosophy should guide all future development of Airline Tycoon's passenger simulation.