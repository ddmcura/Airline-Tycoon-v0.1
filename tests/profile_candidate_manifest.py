"""Stage 3D.3 controlled retained Booking growth; temporary valid worlds only.

python -B -m tests.profile_candidate_manifest --fixtures <temp> --build
Then run WITHOUT --build on each revision against these identical frozen inputs.
The measured manifest is the SAME completed flight/IDs at all three ages. New
history comes from real Booking checkpoints and flight events, never fake rows.
"""
import argparse
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
from game.aircraft_operations.fulfilment import _build_confirmed_carriage_manifest
from game.simulation.candidate_ownership import CandidateOwnership
from game.simulation.handlers import initialize_runtime_handlers
from game.simulation.resolver import resolve_until
from game.world_state import validate_world
from game.world_state.timestamps import format_utc, parse_canonical_utc
from tests.flight_fixtures import flight_world
from game.scheduling import WeeklyDraft
from tests.profile_scheduling import identities
from tests.profile_flight_proof import latency
from tests.profile_ph_runtime import memory_bytes
from tests.resolution_oracle import world_digest


def build_fixtures(root):
    root.mkdir(parents=True, exist_ok=True)
    world = flight_world(1, days=14)
    flights = sorted(world['world_state']['dated_flights'].values(), key=lambda f: f['scheduled_off_block_utc'])
    first_id = flights[0]['dated_flight_id']; reference = None
    start = parse_canonical_utc('2026-09-07T00:01:00Z')
    days_published = 14
    for age, additional_days in ((1, 0), (4, 14), (10, 28)):
        if additional_days:
            owner, aircraft, ports = identities(world)
            draft = WeeklyDraft(world, airline_id=owner, aircraft_id=aircraft)
            for day in range(days_published, days_published + additional_days):
                draft.add(ports['MNL'], ports['DVO'],
                          departure_utc=format_utc(start + timedelta(days=day)), fare_minor=11600)
                draft.add_return(fare_minor=11600)
            assert draft.save(world).succeeded
            days_published += additional_days
        target = format_utc(start + timedelta(days=age-1, hours=5))
        assert resolve_until(world, target, shared=True, max_batch_events=64, max_generated_events=10000).succeeded
        assert validate_world(world).is_valid
        manifest = _build_confirmed_carriage_manifest(world, first_id)
        assert manifest.succeeded
        assert reference is None or reference == manifest.as_dict(), 'relevant authority changed'
        reference = manifest.as_dict()
        upcoming = min((f for f in world['world_state']['dated_flights'].values() if f['status']=='PLANNED'),
                       key=lambda f: f['scheduled_off_block_utc'])
        row = dict(world=world, manifest_flight_id=first_id, target=upcoming['scheduled_in_block_utc'])
        (root / f'age-{age}.json').write_text(json.dumps(row), encoding='utf-8')


def measure(row, repeats):
    world = deepcopy(row['world']); flight_id = row['manifest_flight_id']
    assert validate_world(world).is_valid
    baseline = _build_confirmed_carriage_manifest(world, flight_id)
    owner = CandidateOwnership(world, _validated=True)
    cap = owner.begin({'dated_flights': {flight_id}})
    try:
        from game.aircraft_operations.manifest_lookup import CandidateManifestLookup
    except ImportError:
        CandidateManifestLookup = None
    def timed(fn):
        samples=[]
        for _ in range(repeats):
            start=perf_counter(); result=fn(); samples.append(perf_counter()-start)
            assert result == baseline
        return median(samples)
    canonical=timed(lambda: _build_confirmed_carriage_manifest(cap.envelope,flight_id))
    output=dict(bookings=len(world['world_state']['bookings']),relevant_ids=len(baseline.source_booking_ids),
                canonical_manifest_seconds=canonical,canonical_rows_per_lookup=len(world['world_state']['bookings']))
    if CandidateManifestLookup is not None:
        samples=[]; service=None
        for _ in range(repeats):
            if service is not None: service.close()
            start=perf_counter(); service=CandidateManifestLookup(world); samples.append(perf_counter()-start)
        output['build_seconds']=median(samples)
        output['build_rows']=2*len(world['world_state']['bookings'])  # build + independent coverage pass
        output['stored_ids']=sum(map(len,service._groups.values()))
        output['flight_groups']=len(service._groups)
        output['lookup_structural_bytes']=sum(map(sys.getsizeof,(service,vars(service),service._sources,service._sizes,service._groups,dict(service._groups))))+sum(map(sys.getsizeof,service._groups.values()))
        output['indexed_manifest_seconds']=timed(lambda: _build_confirmed_carriage_manifest(
            cap.envelope,flight_id,booking_ids=service.lookup(cap.envelope,flight_id)))
        start=perf_counter()
        for _ in range(100): assert service.lookup(cap.envelope,flight_id) == baseline.source_booking_ids
        output['id_lookup_seconds']=(perf_counter()-start)/100
        output['indexed_rows_per_lookup']=len(baseline.source_booking_ids)
        service.close()
    owner.close()
    initialize_runtime_handlers()
    output['shared_request']=latency(row['world'],row['target'],'shared',repeats)
    output['input_hash']=world_digest(row['world'])
    output['process_peak_bytes']=memory_bytes()
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if args.repeats<1: parser.error('repeats must be positive')
    if args.build: build_fixtures(args.fixtures)
    for path in sorted(args.fixtures.glob('age-*.json')):
        print(json.dumps(dict(case=path.stem,**measure(json.loads(path.read_text(encoding='utf-8')),args.repeats))),flush=True)

if __name__=='__main__': main()
