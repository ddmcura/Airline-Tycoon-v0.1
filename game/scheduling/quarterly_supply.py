"""Call-local published supply lookup; unsold descriptors never enter saves."""
from datetime import date, timedelta
from game.world_state.quarterly_consumers import projected_flight
from game.world_state.timestamps import parse_canonical_utc
from game.utils.quarters import parse_quarter_id


class QuarterlySupply:
    def __init__(self, envelope, *, sales=True):
        self.envelope = envelope
        self.world = envelope['world_state']
        self.sales = sales
        self.slots = []
        self.by_identity = {}
        self.by_market_slots = {}
        self.by_aircraft_slots = {}
        self.rows = {f['occurrence_key']: f for f in self.world['dated_flights'].values()}
        self.aliases = {f['dated_flight_id']: f for f in self.world['dated_flights'].values()}
        for plan in sorted(self.world['weekly_plans'].values(), key=lambda p: p['weekly_plan_id']):
            revision = plan['revisions'][str(plan['current_revision'])]
            if revision['published_at_utc'] is None:
                continue
            for slot in revision['slots']:
                if sales and (slot['service_type'] != 'PASSENGER'
                        or self.world['services'][slot['service_id']]['retired_at_utc'] is not None):
                    continue
                self.slots.append((plan, revision, slot))
                item = (plan, revision, slot)
                self.by_identity.setdefault((slot['service_id'], slot['slot_number']), []).append(item)
                self.by_aircraft_slots.setdefault(slot['planned_aircraft_id'], []).append(item)
                if slot['connection_id'] is not None:
                    market = self.world['connections'][slot['connection_id']]['market_id']
                    self.by_market_slots.setdefault(market, []).append(item)

    def on_date(self, utc_date, *, market_id=None, aircraft_id=None):
        """One explicit UTC day; convert at most three local dates per frequency."""
        from game.booking.shopping import _airport_available_on
        from game.world_state.timezones import load_named_timezone
        from datetime import datetime, time, timezone
        day = date.fromisoformat(utc_date)
        if self.sales:
            today = parse_canonical_utc(self.envelope['simulation']['time_utc']).date()
            if not today <= day <= today + timedelta(days=365):
                return ()
        start = datetime.combine(day, time(), timezone.utc)
        end = start + timedelta(days=1)
        now = self.envelope['simulation']['time_utc']
        output = []
        selected = (self.by_market_slots.get(market_id, ()) if market_id is not None
                    else self.by_aircraft_slots.get(aircraft_id, ()) if aircraft_id is not None
                    else self.slots)
        for plan, revision, slot in selected:
            if aircraft_id is not None and slot['planned_aircraft_id'] != aircraft_id:
                continue
            connection = self.world['connections'].get(slot['connection_id'])
            if market_id is not None and (connection is None or connection['market_id'] != market_id):
                continue
            quarter = parse_quarter_id(plan['quarter_id'])
            if end <= quarter.start_utc or start >= quarter.end_exclusive_utc:
                continue
            zone = load_named_timezone(self.world['airports'][slot['origin_airport_id']]['timezone'])
            local = start.astimezone(zone).date()
            for offset in (-1, 0, 1):
                operating_date = local + timedelta(days=offset)
                if not quarter.start_utc.astimezone(zone).date() <= operating_date <= (
                        quarter.end_exclusive_utc - timedelta(seconds=1)).astimezone(zone).date():
                    continue
                if operating_date.weekday() not in slot['weekdays']:
                    continue
                lineage = dict(weekly_plan_id=plan['weekly_plan_id'],
                    revision=plan['current_revision'], service_id=slot['service_id'],
                    slot_number=slot['slot_number'], operating_date=operating_date.isoformat(),
                    published_at_utc=revision['published_at_utc'])
                try:
                    row = projected_flight(self.world, lineage)
                except ValueError as exc:
                    if str(exc) == 'date outside published UTC quarter':
                        continue
                    raise
                if row['scheduled_off_block_utc'] < now or row['scheduled_off_block_utc'][:10] != utc_date:
                    continue
                stored = self.rows.get(row['occurrence_key'])
                if stored is not None:
                    row = stored
                if self.sales:
                    if (row['status'] != 'PLANNED' or connection is None
                            or connection['status'] != 'ACTIVE' or row['capacity'] < 1
                            or not _airport_available_on(self.world['airports'][row['origin_airport_id']], utc_date)
                            or not _airport_available_on(self.world['airports'][row['destination_airport_id']],
                                                       row['scheduled_in_block_utc'][:10])):
                        continue
                # Use canonical dated identity in shopping, even after allocating an alias.
                self.rows[row['occurrence_key']] = row
                output.append(row)
        return tuple(sorted(output, key=lambda f: (f['scheduled_off_block_utc'], f['occurrence_key'])))

    def get(self, key):
        row = self.rows.get(key) or self.aliases.get(key)
        if row is not None:
            return row
        # Parsing selects candidates only; selected membership/publication proves authority.
        service, tail = key.rsplit('@', 1)
        operating_date, number = tail.split('#', 1)
        for plan, revision, slot in self.by_identity.get((service, int(number)), ()):
            lineage = dict(weekly_plan_id=plan['weekly_plan_id'], revision=plan['current_revision'],
                service_id=service, slot_number=int(number), operating_date=operating_date,
                published_at_utc=revision['published_at_utc'])
            try:
                row = projected_flight(self.world, lineage)
            except ValueError as exc:
                if str(exc) == 'date outside published UTC quarter':
                    continue
                raise
            if row['occurrence_key'] == key:
                self.rows[key] = row
                return row
        raise ValueError('offer no longer has eligible published quarterly lineage')



class _DateLookup:
    def __init__(self, owner):
        self.owner = owner
        self.cache = {}

    def get(self, pair, default=()):
        if pair not in self.cache:
            market, utc_date = pair
            rows = self.owner.supply.on_date(utc_date, market_id=market)
            self.cache[pair] = tuple(self.owner.add(row, market) for row in rows)
        return self.cache[pair] or default


class QuarterlyActivationProvider:
    def active_market_ids(self, envelope, window, *, dated_flight_indexes=None):
        # Activation selects market work only; Model 4 still owns one daily pool.
        return tuple(sorted(QuarterlyShoppingIndexes(envelope).by_market))


class QuarterlyShoppingIndexes:
    def __init__(self, envelope):
        self.supply = QuarterlySupply(envelope)
        self.by_dated_flight_id = {}
        self.by_market_and_departure_date = _DateLookup(self)
        self.by_market = {}
        today = parse_canonical_utc(envelope['simulation']['time_utc']).date()
        for _, _, slot in self.supply.slots:
            market = self.supply.world['connections'][slot['connection_id']]['market_id']
            if market in self.by_market:
                continue
            for lead in range(366):
                if self.supply.on_date((today + timedelta(days=lead)).isoformat(), market_id=market):
                    self.by_market[market] = (True,)
                    break
    @property
    def indexed_flight_count(self):
        return len(self.by_dated_flight_id)

    def add(self, row, market):
        from game.booking.shopping import DirectFlightShoppingIndexEntry, ShoppingQuarterlyLineage
        key = row['occurrence_key']
        self.by_dated_flight_id[key] = DirectFlightShoppingIndexEntry(
            market, key, row['airline_id'], row['origin_airport_id'], row['destination_airport_id'],
            row['scheduled_off_block_utc'], row['scheduled_in_block_utc'],
            row['scheduled_off_block_utc'][:10],
            int((parse_canonical_utc(row['scheduled_in_block_utc']) -
                 parse_canonical_utc(row['scheduled_off_block_utc'])).total_seconds()),
            row['fare_offer']['currency'], row['fare_offer']['amount_minor'],
            None, None, key, row['status'], row['capacity'], row['inventory_revision'],
            ShoppingQuarterlyLineage(**row['quarterly_lineage']))
        return key
