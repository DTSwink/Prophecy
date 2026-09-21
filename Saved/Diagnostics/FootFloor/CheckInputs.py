import json,pathlib,math
root=pathlib.Path(__file__).parent
baseline=json.loads((root/'jolt-053343.json').read_text())['rows']
for name in ('chaos-053514.json','jolt_ignore_floor-054100.json','jolt_bounce200-054421.json','jolt_zero_friction-054741.json','jolt_spec01-054954.json','jolt_slop01-055109.json','jolt_zero_restitution-055429.json'):
    rows=json.loads((root/name).read_text())['rows']
    assert len(rows)==len(baseline)
    max_root=max(math.dist(a['root'],b['root']) for a,b in zip(baseline,rows))
    max_target=max(math.dist(a['feet'][bone]['target'],b['feet'][bone]['target']) for a,b in zip(baseline,rows) if a['actor'].endswith('_1') and a['t']>=4 for bone in ('foot_l','foot_r'))
    print(name,'maximum_root_difference_cm',max_root,'maximum_target_difference_cm',max_target)
