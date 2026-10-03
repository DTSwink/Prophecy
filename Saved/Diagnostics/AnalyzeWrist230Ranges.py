import json,re,pathlib
p=pathlib.Path('Saved/Diagnostics/Knee202')
s=pathlib.Path('Saved/Logs/GameAnimationSample3.log').read_text(errors='replace')
s=s[s.rfind('KNEE202_STARTED wrist230_final'):]
a=[dict(t=float(t),allowance=float(a),calf=float(c),kick=float(k)) for t,a,c,k in re.findall(r'FootRecoveryTarget actor=.*?time=([\d.]+) side=0 allowance=([\d.]+).*?calf=([\d.]+) kick=([\d.]+)',s)]
assert len(a)==270,len(a)
for i in [149,150,151,152,156,160,165,166,173,174,175,180,185,190,200,210,220,230,240,250,260,269]:print(i+1,a[i])
assert all(a[i+1]['calf']<=a[i]['calf'] for i in range(151,166))
assert a[151]['calf']==2 and a[166]['calf']==0
assert all(a[i+1]['calf']<=a[i]['calf'] for i in range(175,269))
assert a[269]['calf']==2
assert 'Error:' not in s
(p/'wrist230_final_ranges.json').write_text(json.dumps(a,indent=2))
print('RANGE_TRANSITIONS_VERIFIED')
