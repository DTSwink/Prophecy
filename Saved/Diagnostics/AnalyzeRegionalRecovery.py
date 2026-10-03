import json,pathlib,re
root=pathlib.Path(__file__).parent/'RegionalRecovery'
data=json.loads((root/'live.json').read_text());assert not data['error'],data['error']
log=(root/'live.log').read_text(encoding='utf-8',errors='replace')
current=None;events={}
for line in log.splitlines():
    m=re.search(r'REGION_CASE (\w+) BEGIN',line)
    if m:current=m[1];events[current]=[]
    m=re.search(r'SpecialRegion actor=(\S+) region=(upper|lower) special=(\d+) attack=(\S+) half=(\d) returning=(\d)',line)
    if m and current:
        events[current].append(dict(region=m[2],special=int(m[3]),attack=m[4],half=int(m[5]),returning=int(m[6])))
expected={'half':['upper'],'full':['lower','upper'],'full_half':['lower','upper'],'half_full':['lower','upper'],'full_half_full_half':['lower','lower','upper']}
for case,wanted in expected.items():
    assert [r['region'] for r in events.get(case,[])]==wanted,(case,events.get(case))
    assert all(r['returning']==1 for r in events[case]),events
stopped=next(e for e in data['events'] if e['case']=='half' and e['action']=='stop')
assert stopped['root_before']==stopped['root_after']
assert stopped['before']==stopped['after']
summary=dict(events=events,pure_half_exit_root_and_lower_pose_unchanged=True)
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
