"""Selected-period operational reads of committed authority, never schedule patterns."""
from datetime import date, timedelta
from game.scheduling.local_time import airport_local
from .fulfilment import _build_confirmed_carriage_manifest


def _operational_context_owned(envelope, airline_id):
    world=envelope['world_state']
    base=world['airlines'][airline_id]['base_airport_ids'][0]
    today=airport_local(world,base,envelope['simulation']['time_utc']).date()
    return {'airport_id':base,'code':world['airports'][base]['reference_code'],
            'timezone':world['airports'][base]['timezone'],'today':today.isoformat(),
            'week_start':(today-timedelta(days=today.weekday())).isoformat()}


def _operational_period_owned(envelope, airline_id, start_date, days, indexes, lookup, market=None, include_spanning=False):
    first=date.fromisoformat(start_date);last=first+timedelta(days=days)
    world=envelope['world_state'];base=_operational_context_owned(envelope,airline_id)['airport_id']
    rows=[]
    for identity in indexes.by_airline.get(airline_id,()):
        f=world['dated_flights'][identity]
        if market and (f['origin_airport_id'],f['destination_airport_id']) != tuple(market):continue
        result=world['flight_results'].get(identity)
        active=world['active_aircraft_operations'].get(identity)
        source=result or active
        departure=source['actual_departure_utc'] if source else f['scheduled_off_block_utc']
        arrival=result['actual_arrival_utc'] if result else f['scheduled_in_block_utc']
        day=airport_local(world,base,departure).date()
        arrival_day=airport_local(world,base,arrival).date()
        if include_spanning:
            if not (day < last and arrival_day >= first):continue
        elif not first <= day < last:continue
        aircraft_id=source['actual_aircraft_id'] if source else f['planned_aircraft_id']
        aircraft=world['aircraft'][aircraft_id]
        if result:
            passengers=result['carried_passenger_count'];basis='CARRIED'
        elif active or (f['status']=='PLANNED' and f['service_type']=='PASSENGER'):
            manifest=_build_confirmed_carriage_manifest(envelope,identity,
                booking_ids=active['source_booking_ids'] if active else lookup.booking_ids_by_flight.get(identity,()))
            if not manifest.succeeded:raise ValueError('invalid confirmed carriage projection')
            passengers=manifest.carried_passenger_count;basis='LOCKED' if active else 'CONFIRMED'
        else:passengers=None;basis='NOT OPERATING'
        origin=f['origin_airport_id'];destination=f['destination_airport_id']
        rows.append({'id':identity,'operational_date':day.isoformat(),
            'departure':departure,'arrival':arrival,
            'departure_local':airport_local(world,origin,departure).isoformat(),
            'arrival_local':airport_local(world,destination,arrival).isoformat(),
            'origin_id':origin,'destination_id':destination,
            'origin':world['airports'][origin]['reference_code'],
            'destination':world['airports'][destination]['reference_code'],
            'aircraft_id':aircraft_id,'registration':aircraft['display_registration'],
            'model':aircraft['model_reference'],'status':f['status'],'service_type':f['service_type'],
            'passengers':passengers,'capacity':f['capacity'],'load_basis':basis,
            'load':passengers*10000//f['capacity'] if passengers is not None and f['capacity'] else None,
            'fare':f['fare_offer']['amount_minor'],
            'revenue':result['recognized_revenue_minor'] if result else None})
    return sorted(rows,key=lambda r:(r['departure'],r['id']))


def _service_markets_owned(envelope, airline_id, indexes):
    world=envelope['world_state'];markets=set()
    for identity in indexes.by_airline.get(airline_id,()):
        f=world['dated_flights'][identity]
        if f['service_type']=='PASSENGER' and f['status'] in {'PLANNED','OPERATIONALLY_LOCKED','COMPLETED'}:
            markets.add((f['origin_airport_id'],f['destination_airport_id']))
    return [{'origin_id':o,'destination_id':d,
             'label':world['airports'][o]['reference_code']+' -> '+world['airports'][d]['reference_code']}
            for o,d in sorted(markets)]
