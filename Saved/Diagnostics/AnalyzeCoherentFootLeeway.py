import json,pathlib,re,numpy as np
p=pathlib.Path('Saved/Diagnostics/AttackFootSink')
base=json.loads((p/'baseline.json').read_text());fixed=json.loads((p/'fixed.json').read_text())
assert not fixed['error'],fixed['error']
assert base['rows'][:119]==fixed['rows'][:119],'Different pre-attack history'
report=dict(exact_prefix_frames=119,feet={},matrix=[])
for bone in ('foot_l','foot_r'):
    z=lambda r:r['physical'][bone]['transform']['p'][2]
    pre=np.mean([z(r) for r in fixed['rows'][99:119]])
    report['feet'][bone]=dict(entry_drop_mm=float((pre-min(z(r) for r in fixed['rows'][119:132]))*10))
matrix=json.loads((p/'matrix.json').read_text());assert not matrix['error'],matrix['error']
pattern=re.compile(r'time=([\d.]+) side=0 allowance=([\d.]+).*calf=([\d.]+) kick=([\d.]+)')
samples={}
for line in (p/'matrix-drive.log').read_text().splitlines():
    m=pattern.search(line)
    if m:samples[round(float(m[1])*60)]=[float(m[2]),float(m[3]),float(m[4])]
def recovery(ticks):
    a=ticks/60
    return 20+(2-20)*a*a*(3-2*a)
for f,calf in [(29,2),(31,5),(36,recovery(1)),(41,5),(46,3),(51,0),(56,0),(61,recovery(1)),(66,5),(76,recovery(1)),(86,recovery(11)),(91,recovery(16))]:
    r=matrix['rows'][f-1];drive=samples[round(r['t']*60)]
    assert abs(drive[1]-calf)<.00001,(f,drive,calf)
    if f==66:assert drive[2]==7,(f,drive)
    report['matrix'].append(dict(frame=f,state=r['state'],target_allowance=drive[0],calf_allowance=drive[1],kick_extension=drive[2]))
(p/'coherent-summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
