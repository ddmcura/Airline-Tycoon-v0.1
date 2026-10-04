"""Exact success predicate over one current, plain Booking authority graph.
Caller has proved JSON/aliases and earlier whole-world/checkpoint predicates.
An anomaly returns False for the original ordered diagnostic suffix. Derived
tuples contain source scalars/IDs and never escape this validation call.
Canonical UTC/non-bool minor-unit types inherit from the actual E.1 traversal;
required non-null values and domain ranges remain checked here.
Compatibility/unusual inputs use the detailed path, not a filtered graph.
"""
from .booking_validation import _currency, _date
from .schema import AGGREGATE_BOOKING_CONTRACT, DIRECT_ECONOMY_ITINERARY_CONTRACT


_ITINERARY_FIELDS = frozenset((
    'itinerary_id', 'contract', 'market_id', 'airline_id', 'origin_airport_id',
    'destination_airport_id', 'dated_flight_ids', 'scheduled_departure_utc',
    'scheduled_arrival_utc', 'cabin', 'fare_offer_snapshot', 'schedule_lineage', 'status',
))
_BOOKING_FIELDS = frozenset((
    'booking_id', 'contract', 'booking_checkpoint_id', 'cohort_key', 'desired_travel_date',
    'airline_id', 'itinerary_id', 'passenger_count', 'booked_at_utc', 'total_fare_minor',
    'currency', 'inventory_revision_at_commit', 'finance_transaction_id', 'booking_revision', 'status',
))
_LINEAGE_FIELDS = frozenset(('schedule_id', 'schedule_revision', 'occurrence_key'))
_FARE_FIELDS = frozenset(('currency', 'amount_minor'))
_TRANSACTION_FIELDS = frozenset((
    'transaction_id', 'airline_id', 'occurred_at_utc', 'description', 'source_type',
    'source_id', 'source_booking_ids', 'currency', 'entries',
))

class _ScalarRows:
    """Call-local flat source scalars, avoiding one GC-tracked node per record.

    Only immutable tuples leave a query. No record reference is retained; the
    backing list/ID-offset dictionary are private to this synchronous call.
    """
    __slots__ = ('_offsets', '_values', '_width')

    def __init__(self, width):
        self._offsets = {}
        self._values = []
        self._width = width

    def add(self, key, row):
        if key in self._offsets or len(row) != self._width:
            raise ValueError('duplicate/malformed validation-local row')
        self._offsets[key] = len(self._values)
        self._values.extend(row)

    def get(self, key):
        offset = self._offsets.get(key)
        return None if offset is None else tuple(self._values[offset:offset + self._width])

    def __getitem__(self, key):
        offset = self._offsets[key]
        return tuple(self._values[offset:offset + self._width])

    def __len__(self):
        return len(self._offsets)

    def __iter__(self):
        return iter(self._offsets)

    def values(self):
        for key in self._offsets:
            yield self[key]

def _itinerary_graph(world):
    """Visit ALL itineraries. Exact direct lineage, no valid-looking filtering."""
    graph = _ScalarRows(5)
    flights = world['dated_flights']
    airlines = world['airlines']
    markets = world['directional_markets']
    flight_facts = {}
    currencies = {}
    for itinerary_id, r in world['itineraries'].items():
        if (type(r) is not dict or r.keys() != _ITINERARY_FIELDS
                or r['contract'] != DIRECT_ECONOMY_ITINERARY_CONTRACT):
            return None
        ids = r['dated_flight_ids']
        market_id = r['market_id']
        airline_id = r['airline_id']
        if (type(ids) is not list or len(ids) != 1 or type(ids[0]) is not str
                or type(market_id) is not str or type(airline_id) is not str):
            return None
        flight_id = ids[0]
        market = markets.get(market_id)
        if type(market) is not dict or type(airlines.get(airline_id)) is not dict:
            return None
        facts = flight_facts.get(flight_id)
        if facts is None:
            f = flights.get(flight_id)
            if (type(f) is not dict or f.get('service_type') != 'PASSENGER'
                    or f.get('passenger_service_classification') != 'ECONOMY'
                    or type(f.get('fare_offer')) is not dict):
                return None
            facts = (f.get('airline_id'), f.get('origin_airport_id'), f.get('destination_airport_id'),
                f.get('scheduled_off_block_utc'), f.get('scheduled_in_block_utc'),
                f['fare_offer'].get('currency'), f.get('schedule_id'),
                f.get('schedule_revision'), f.get('occurrence_key'))
            flight_facts[flight_id] = facts
        snapshot = r['fare_offer_snapshot']
        lineage = r['schedule_lineage']
        if type(snapshot) is not dict or snapshot.keys() != _FARE_FIELDS:
            return None
        currency = snapshot['currency']
        if type(currency) is not str:
            return None
        if currency not in currencies:
            currencies[currency] = _currency(currency)
        if (r['cabin'] != 'ECONOMY' or r['status'] != 'CONFIRMED'
                or type(r['scheduled_departure_utc']) is not str
                or type(r['scheduled_arrival_utc']) is not str
                or not currencies[currency]
                or type(snapshot['amount_minor']) is not int or snapshot['amount_minor'] < 0
                or type(lineage) is not dict or lineage.keys() != _LINEAGE_FIELDS
                or type(lineage['schedule_id']) is not str
                or type(lineage['schedule_revision']) is not int or lineage['schedule_revision'] < 1):
            return None
        if ((airline_id, r['origin_airport_id'], r['destination_airport_id'],
                r['scheduled_departure_utc'], r['scheduled_arrival_utc'], snapshot['currency'],
                lineage['schedule_id'], lineage['schedule_revision'], lineage['occurrence_key']) != facts
                or (r['origin_airport_id'], r['destination_airport_id']) !=
                (market.get('origin_airport_id'), market.get('destination_airport_id'))):
            return None
        graph.add(itinerary_id, (airline_id, flight_id, snapshot['currency'], snapshot['amount_minor'], market_id))
    return graph
def _booking_graph(world, itineraries, valid_date=_date):
    """One ownership/association pass; derive immutable source facts."""
    graph = _ScalarRows(10)
    owners = set()
    passengers_by_flight = {}
    airlines = world['airlines']
    flights = world['dated_flights']
    transactions = world['transactions']
    state = world['booking_state']
    checkpoints = state['booking_checkpoints']
    revision = state['booking_revision']
    cohorts = world['demand_state']['processed_cohorts']
    for booking_id, r in world['bookings'].items():
        if (type(r) is not dict or r.keys() != _BOOKING_FIELDS
                or r['contract'] != AGGREGATE_BOOKING_CONTRACT):
            return None
        itinerary_id = r['itinerary_id']
        airline_id = r['airline_id']
        if type(itinerary_id) is not str or type(airline_id) is not str:
            return None
        i = itineraries.get(itinerary_id)
        count = r['passenger_count']
        amount = r['total_fare_minor']
        committed = r['inventory_revision_at_commit']
        checkpoint_id = r['booking_checkpoint_id']
        cohort = r['cohort_key']
        tx = r['finance_transaction_id']
        if (i is None or airline_id not in airlines or i[0] != airline_id
                or itinerary_id in owners or type(count) is not int or count < 1
                or type(amount) is not int or amount < 0 or r['currency'] != i[2]
                or amount != count * i[3] or r['status'] != 'CONFIRMED'
                or type(checkpoint_id) is not str or checkpoint_id not in checkpoints
                or type(cohort) is not str or cohort not in cohorts
                or not valid_date(r['desired_travel_date']) or type(r['booked_at_utc']) is not str
                or type(committed) is not int or committed < 0
                or type(r['booking_revision']) is not int or not 1 <= r['booking_revision'] <= revision):
            return None
        if tx is None:
            if amount != 0: return None
        elif (amount == 0 or type(tx) is not str or tx not in transactions
                or transactions[tx].get('airline_id') != airline_id):
            return None
        if committed > flights[i[1]]['inventory_revision']:
            return None
        owners.add(itinerary_id)
        passengers_by_flight[i[1]] = passengers_by_flight.get(i[1], 0) + count
        graph.add(booking_id, (checkpoint_id, cohort, r['desired_travel_date'], airline_id,
            i[4], count, r['booked_at_utc'], amount, tx, r['booking_revision']))
    if len(owners) != len(itineraries):
        return None
    for flight_id, count in passengers_by_flight.items():
        f = flights[flight_id]
        if type(f.get('capacity')) is int and count > f['capacity']:
            return None
    return graph
def _result_lineage(world, bookings):
    """Check every referenced ID, uniqueness, totals and exact paid journal."""
    owners = set()
    transactions = world['transactions']
    airlines = world['airlines']
    accounts = world['financial_accounts']
    for checkpoint_id, checkpoint in world['booking_state']['booking_checkpoints'].items():
        listed_transactions = set(checkpoint['financial_transaction_ids'])
        transaction_groups = {}
        desired_owners = set()
        for market_id, result in checkpoint['market_results'].items():
            for desired_date, desired in result['desired_date_results'].items():
                total = 0
                for booking_id in desired['booking_ids']:
                    b = bookings.get(booking_id)
                    if b is None or booking_id in desired_owners or b[2] != desired_date:
                        return False
                    desired_owners.add(booking_id)
                    total += b[5]
                if total != desired['booked_passenger_count']:
                    return False
            total = 0
            for booking_id in result['booking_ids']:
                b = bookings.get(booking_id)
                if (b is None or booking_id in owners or b[0] != checkpoint_id
                        or b[1] != result['cohort_key'] or b[4] != market_id
                        or b[6] != checkpoint['processed_at_utc']
                        or b[9] != checkpoint['booking_revision']):
                    return False
                owners.add(booking_id)
                total += b[5]
                tx = b[8]
                if tx is not None:
                    if tx not in listed_transactions: return False
                    transaction_groups.setdefault(tx, []).append(booking_id)
            if total != result['booked_passenger_count']:
                return False
        if transaction_groups.keys() != listed_transactions:
            return False
        transaction_airlines = set()
        for tx, ids in transaction_groups.items():
            t = transactions[tx]
            airline_id = t.get('airline_id')
            if t.keys() != _TRANSACTION_FIELDS or type(airline_id) is not str:
                return False
            airline = airlines.get(airline_id)
            if type(airline) is not dict or airline_id in transaction_airlines:
                return False
            transaction_airlines.add(airline_id)
            source = t['source_booking_ids']
            # Unique Booking ownership already proven. Exact sorted equality
            # proves source ordering, completeness and uniqueness together.
            if type(source) is not list or source != sorted(ids):
                return False
            gross = 0
            for booking_id in ids:
                b = bookings[booking_id]
                if b[3] != airline_id or b[7] <= 0: return False
                gross += b[7]
            by_code = {accounts[a].get('code'): a for a in airline['financial_account_ids']
                if type(a) is str and type(accounts.get(a)) is dict}
            if (t['transaction_id'] != tx or t['source_type'] != 'BOOKING_CHECKPOINT'
                    or t['source_id'] != checkpoint_id or t['currency'] != airline.get('base_currency')
                    or t['occurred_at_utc'] != checkpoint['processed_at_utc']
                    or t['entries'] != [{'account_id': by_code.get('cash'), 'amount_minor': gross},
                        {'account_id': by_code.get('unflown_tickets'), 'amount_minor': -gross}]):
                return False
    return len(owners) == len(bookings)
def valid_booking_relationships(world, *, valid_date=_date):
    """No retained proof; False requests original diagnostics, never repair."""
    for airline in world['airlines'].values():
        value = airline.get('finance_revision')
        if type(value) is not int or value < 0: return False
    for flight in world['dated_flights'].values():
        value = flight.get('inventory_revision')
        if (type(value) is not int or value < 0
                or 'remaining_capacity' in flight or 'booked_capacity' in flight):
            return False
    itineraries = _itinerary_graph(world)
    if itineraries is None: return False
    bookings = _booking_graph(world, itineraries, valid_date)
    return bookings is not None and _result_lineage(world, bookings)
