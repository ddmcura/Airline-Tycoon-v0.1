"""Repeatable Patch 4 before/after; baseline code read from Git, no checkout writes."""
from copy import deepcopy
from statistics import median
from time import perf_counter
from types import ModuleType
from unittest.mock import patch
import json
import subprocess
from game.scheduling import weekly
from game.world_state import create_stage1_new_game

BASELINE='0623a621835f2a8d6ca10d06f19d26b55cd42fff'

def main():
    old=ModuleType('game.scheduling.patch4_control');old.__package__='game.scheduling'
    exec(compile(subprocess.check_output(['git','show',BASELINE+':game/scheduling/weekly.py']),'<Patch3 weekly>','exec'),old.__dict__)
    base=create_stage1_new_game(scenario_id='stage1-philippines-v1',ceo_display_name='CEO',airline_display_name='Profile',base_airport_reference_code='MNL')
    w=base['world_state'];ports={r['reference_code']:k for k,r in w['airports'].items()}
    for name,days,ret,origin in [('daily-one-way',range(7),False,'DVO'),('mwf-one-way',(0,2,4),False,'DVO'),('daily-return',range(7),True,'MNL')]:
        results={}
        for version,module in [('before',old),('after',weekly)]:
            samples=[]
            for _ in range(3):
                d=module.WeeklyDraft(deepcopy(base),airline_id=w['player']['primary_airline_id'],aircraft_id=next(iter(w['aircraft'])))
                with patch.object(module,'validate_world',wraps=module.validate_world) as validations:
                    start=perf_counter()
                    try:
                        d.add_weekdays(ports[origin],ports['MNL' if origin=='DVO' else 'DVO'],[f'2026-09-{7+n:02d}' for n in days],'08:00',return_flight=ret)
                        outcome='accepted'
                    except ValueError as exc:outcome=str(exc)
                    samples.append(perf_counter()-start)
                assert base==d._base
            results[version]={'median_s':median(samples),'outcome':outcome,'whole_world_validations_during_add':validations.call_count,'legs':len(d.legs)}
        print(json.dumps({'case':name,**results}),flush=True)

if __name__=='__main__':main()
