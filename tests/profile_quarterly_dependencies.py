"""Repeatable dormant quarterly discovery/command measurements; no real saves."""
from copy import deepcopy
import argparse
import json
from statistics import median
from time import perf_counter
import tempfile
import sys
import subprocess
import types
from unittest.mock import patch
from collections.abc import Mapping

from app.session import Stage1Session
from tests.test_quarterly_foundation import FoundationTests
from game.world_state.construction import add_airline
from game.world_state.quarterly_construction import create_service, allocate_service_slot, create_weekly_plan
from game.world_state import validate_world
from game.aircraft_market.acquisition import preview_purchase, purchase_aircraft
from game.aircraft_market.reference_catalog import PH_AIRCRAFT_CATALOG_VERSION
from game.scheduling.quarterly_feasibility import temporal_sources
from game.scheduling.quarterly_commands import _sources, ReviseQuarterlyFare


def payload_bytes(index):
    """Reachable container estimate, excludes authoritative root bindings/RSS.

    Includes shared ID strings conservatively; mapping backing storage estimated
    using a same-sized ordinary dict. It is not additional process allocation.
    """
    seen = set()
    def size(value):
        if id(value) in seen:return 0
        seen.add(id(value))
        if isinstance(value, Mapping):
            return sys.getsizeof(dict(value))+sum(size(k)+size(v) for k,v in value.items())
        if isinstance(value,(tuple,list,set,frozenset)):
            return sys.getsizeof(value)+sum(size(v) for v in value)
        return sys.getsizeof(value)
    return sum(size(getattr(index,name)) for name in ('_maps','_plans','_quarters','_numbers','_endpoints','_ends','_departures'))


def fixture(unrelated):
    FoundationTests.setUpClass(); f = FoundationTests(); f.setUp()
    pid, sid, number, slot = f.plan('2027-Q1')
    if unrelated:
        owner = add_airline(f.world, 'Other', base_airport_id=f.origin, starting_money=100_000_000_000)
        rows = []
        for _ in range(unrelated):
            aid = purchase_aircraft(f.world, preview_purchase(f.world, airline_id=owner,
                model_id='airbus-a320neo', catalog_version=PH_AIRCRAFT_CATALOG_VERSION,
                delivery_airport_id=f.origin))
            f.state = f.world['world_state']
            service = create_service(f.world, owner, flight_number_prefix='OTH')
            allocate_service_slot(f.world, service)
            rows.append(f.slot(service, 1, planned_aircraft_id=aid, connection_id=None,
                service_type='DEADHEAD', capacity=0, fare_offer={'currency':'USD','amount_minor':0}))
        create_weekly_plan(f.world, owner, '2027-Q1', slots=rows)
    valid = validate_world(f.world)
    assert valid.is_valid, valid.errors[:1]
    return f.world, f.owner, f.aircraft, pid, sid


def timed(call, repeats=5):
    samples = []
    for _ in range(repeats):
        start = perf_counter(); call(); samples.append(perf_counter()-start)
    return median(samples)


def breakdown(world, owner, pid, sid, *, baseline=False):
    """Read-only committed baseline module; never archival stash code."""
    from game.scheduling import quarterly_commands as current
    from game.scheduling.quarterly_indexes import QuarterlyIndexOwner
    if baseline:
        name='game.scheduling._dependency_measurement_baseline'
        module=types.ModuleType(name);module.__package__='game.scheduling';sys.modules[name]=module
        source=subprocess.check_output(['git','show','9277d96d126f2c4dcf6351a6f2b1b41ca0e1fabc:game/scheduling/quarterly_commands.py'],text=True)
        exec(compile(source,name,'exec'),module.__dict__)
    else:module=current
    candidate=deepcopy(world);indexes=None if baseline else QuarterlyIndexOwner()
    if indexes is not None:indexes.get(candidate)  # warm coverage outside measurement
    gates=[];copies=[];entry=module._entry;copy=module.deepcopy
    def gate(value):
        start=perf_counter()
        try:return entry(value)
        finally:gates.append(perf_counter()-start)
    def clone(value):
        start=perf_counter();result=copy(value)
        if type(value) is dict and {'metadata','world_state','simulation'}<=value.keys():
            copies.append(perf_counter()-start)
        return result
    options={} if baseline else {'_indexes':indexes}
    with patch.object(module,'_entry',gate),patch.object(module,'deepcopy',clone):
        ready=module.prepare_quarterly_command(candidate,airline_id=owner,
            request=module.ReviseQuarterlyFare(pid,1,sid,1,{'currency':'USD','amount_minor':12345}),**options)
        result=module.apply_quarterly_command(candidate,airline_id=owner,prepared=ready.prepared,**options)
        assert result.succeeded,result.issues
    if baseline:del sys.modules[name]
    return {'gate_count':len(gates),'gate_seconds':sum(gates),'world_copy_count':len(copies),'world_copy_seconds':sum(copies)}


def measure(size):
    world, owner, aid, pid, sid = fixture(size)
    intent = {'kind':'FARE', 'weekly_plan_id':pid, 'expected_revision':1,
              'service_id':sid, 'slot_number':1, 'fare_offer':{'currency':'USD','amount_minor':11000}}
    discovery = timed(lambda: temporal_sources(world, {aid}))
    sources = timed(lambda: _sources(world, owner, intent))
    from game.scheduling.quarterly_indexes import QuarterlyDependencyIndex
    from game.world_state.quarterly_construction import append_weekly_plan_revision
    build = timed(lambda: QuarterlyDependencyIndex._build(world))
    index = QuarterlyDependencyIndex._build(world)
    indexed_discovery = timed(lambda: temporal_sources(world,{aid},index=index))
    indexed_sources = timed(lambda: _sources(world,owner,intent,index))
    candidate = deepcopy(world)
    rows = deepcopy(candidate['world_state']['weekly_plans'][pid]['revisions']['1']['slots'])
    rows[0]['fare_offer']['amount_minor'] = 11000
    append_weekly_plan_revision(candidate,pid,expected_revision=1,slots=rows)
    def maintain():
        proposed=index.updated(candidate,plan_id=pid,service_id=sid)
        index.verify_delta(proposed,candidate,plan_id=pid,service_id=sid)
        return proposed.rebound(candidate)
    maintenance = timed(maintain)
    with tempfile.TemporaryDirectory() as root:
        session = Stage1Session(save_root=root)
        # A validated cold load gives exclusive session ownership. No fixture
        # mutation is timed or treated as a supported production writer.
        session.world = deepcopy(world); session.career_id = session.save_store.new_career_id()
        session.save_manual(); session.load_saved(session.career_id)
        prepares = []; applies = []
        for revision in range(1, 4):
            request = ReviseQuarterlyFare(pid, revision, sid, 1, {'currency':'USD','amount_minor':11000+revision})
            start = perf_counter(); prepared = session.prepare_quarterly_command(request)
            prepares.append(perf_counter()-start); assert prepared.succeeded, prepared.issues
            start = perf_counter(); result = session.apply_quarterly_command(prepared.prepared)
            applies.append(perf_counter()-start); assert result.succeeded, result.issues
    return {'unrelated_services':size, 'temporal_discovery_seconds':discovery,
            'indexed_temporal_seconds':indexed_discovery, 'indexed_sources_seconds':indexed_sources,
            'index_build_seconds':build,'index_delta_and_rebind_seconds':maintenance,
            'index_payload_bytes_estimate':payload_bytes(index),
            'baseline_breakdown':breakdown(world,owner,pid,sid,baseline=True),
            'indexed_breakdown':breakdown(world,owner,pid,sid),
            'sources_seconds':sources, 'prepare_seconds':median(prepares), 'apply_seconds':median(applies)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--sizes', nargs='+', type=int, default=[0, 10, 100, 250])
    for size in parser.parse_args().sizes:
        print(json.dumps(measure(size)), flush=True)
