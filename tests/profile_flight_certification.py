"""Repeatable Stage 3C/3D fixtures in a caller-supplied TEMP directory only."""
import argparse
import json
from pathlib import Path
from tests.flight_fixtures import flight_world, window
from tests.resolution_oracle import world_digest


def measure(base, target, repeats, shared):
    # Direct wrappers do not retain full candidates or per-event witness bytes.
    from tests.profile_flight_proof import latency, profile
    mode='shared' if shared else 'strict'
    timed=latency(base,target,mode,repeats)
    instrumented=profile(base,target,shared)
    assert instrumented['world_hash']==timed['world_hash']
    assert instrumented['batches']==timed['batches'], "instrumentation changed execution boundaries"
    return dict(median_seconds=timed['median_seconds'],samples_seconds=timed['samples_seconds'],
        max_step_seconds=timed['max_step_seconds'],events=timed['events'],
        events_per_commit=timed['batches'],world_hash=timed['world_hash'],
        full_validations=instrumented['calls'].get('full_world_validation',0),
        world_clones=instrumented['calls'].get('clone',0),
        latency_lifetime_peak_bytes=timed['process_peak_bytes'],
        lifetime_peak_bytes=instrumented['process_peak_bytes'],
        instrumented_calls=instrumented['calls'],exclusive_seconds=instrumented['exclusive_seconds'],
        work=instrumented['work'],collection_sizes=instrumented['collection_sizes'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--mode',choices=('strict','shared','both'),default='both')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--case',default='all')
    parser.add_argument('--observed-fixture',type=Path)
    args=parser.parse_args()
    assert args.repeats>0
    args.fixtures.mkdir(parents=True,exist_ok=True)
    cases=[('one-departure',1,'departure',{}),('one-completion',1,'completion',{}),
        ('round-trip',1,'round-trip',{}),('dense-departure',10,'departure',{}),
        ('dense-completion',10,'completion',{}),('mixed-ten',10,'round-trip',{'stagger_seconds':600}),
        ('representative-ten',10,'round-trip',{'stagger_seconds':180,'days':2}),
        ('aged-ten',10,'round-trip',{'history':1000}),('dense-25',25,'round-trip',{})]
    if args.observed_fixture:
        cases.extend([('divine-next-departure',0,'departure',{}),('divine-short',0,'short',{})])
    for name,count,kind,options in cases:
        if args.case not in ('all',name): continue
        path=args.fixtures/(name+'.json')
        if path.exists(): row=json.loads(path.read_text(encoding='utf-8'))
        else:
            if count:
                base=flight_world(count,**options); target=window(base,kind)
            else:
                from datetime import timedelta
                from game.world_state import validate_world
                from game.world_state.timestamps import format_utc,parse_canonical_utc
                base=json.loads(args.observed_fixture.read_text(encoding='utf-8'))
                assert validate_world(base).is_valid
                departure=min(e['due_at_utc'] for e in base['world_state']['pending_events'].values()
                    if e['event_type']=='STAGE1_FLIGHT_DEPARTURE')
                target=departure if kind=='departure' else format_utc(parse_canonical_utc(departure)+timedelta(hours=4))
            row=dict(world=base,target=target)
            path.write_text(json.dumps(row),encoding='utf-8')
            print(json.dumps(dict(built=name,world_hash=world_digest(base))),flush=True)
        modes=(False,True) if args.mode=='both' else (args.mode=='shared',)
        report={}
        for shared in modes:
            report['shared' if shared else 'strict']=measure(row['world'],row['target'],args.repeats,shared)
        if len(modes)==2: assert report['strict']['world_hash']==report['shared']['world_hash']
        print(json.dumps(dict(case=name,input_hash=world_digest(row['world']),**report)),flush=True)

if __name__=='__main__': main()
