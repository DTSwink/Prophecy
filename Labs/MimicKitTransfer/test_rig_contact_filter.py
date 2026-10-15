"""Compare per-rig filtering with global speculative distance zero on saved rig states."""
import os,json,subprocess,tempfile,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/no-armature-3913'
os.environ['MIMICKIT_TRANSFER_OUT']=str(OUT)
contact_only='--contact-only' in sys.argv
os.environ['MIMICKIT_TRANSFER_FIXTURE']=str(OUT/('contact-fixture.exe' if contact_only else 'rig-contact-filter.exe'))
os.environ['TRANSFER_SUBSTEPS']='1'
os.environ['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+os.environ.get('PATH','')

def step(initial,commands):
    with tempfile.NamedTemporaryFile(mode='w',suffix='.txt',delete=False) as f:
        path=Path(f.name)
        for row in initial:f.write(' '.join(format(x,'.12g') for x in row)+'\n')
    try:
        result=subprocess.run([os.environ['MIMICKIT_TRANSFER_FIXTURE'],str(path)],
            input='step '+' '.join(map(str,commands))+'\nquit\n',text=True,capture_output=True,check=True,timeout=15)
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        assert max(abs(a-b) for x,y in zip(rows[0]['bodies'],initial) for a,b in zip(x,y))<1e-5
        return rows[1]
    finally:path.unlink()

data=json.loads((OUT/'contact-substeps.json').read_text())
commands=json.loads((OUT/'baseline-motor-inputs.json').read_text())['commands']
results={}
for name,flag in [('stock',None),('global_zero','TRANSFER_NO_SPECULATIVE'),('rig_only','TRANSFER_RIG_NO_SPECULATIVE')]:
    for key in ('TRANSFER_NO_SPECULATIVE','TRANSFER_RIG_NO_SPECULATIVE','TRANSFER_RIG_ALLOW_SPECULATIVE'):os.environ.pop(key,None)
    if contact_only and name!='rig_only':os.environ['TRANSFER_RIG_ALLOW_SPECULATIVE']='1'
    if flag:os.environ[flag]='1'
    rows=[]
    for initial in data['inputs']:
        rows.append(step(initial,commands))
    results[name]=rows
comparisons=[]
for index,(rig,glob) in enumerate(zip(results['rig_only'],results['global_zero'])):
    a=rig['bodies'];b=glob['bodies']
    def angle(x,y):
        if x[3:7]==y[3:7]:return 0.
        dot=sum(u*v for u,v in zip(x[3:7],y[3:7]))
        norm=math.sqrt(sum(u*u for u in x[3:7])*sum(u*u for u in y[3:7]))
        return math.degrees(2*math.acos(min(1.,abs(dot/norm))))
    comparisons.append(dict(substep=index,position_cm=100*max(math.dist(x[:3],y[:3]) for x,y in zip(a,b)),
        rotation_deg=max(angle(x,y) for x,y in zip(a,b)),
        velocity_max=max(abs(u-v) for x,y in zip(a,b) for u,v in zip(x[7:],y[7:])),
        ground_impulse_difference_ns=max(abs(u-v) for u,v in zip(rig['ground_vertical_impulse_ns'],glob['ground_vertical_impulse_ns']))))
baseline_matches=None
if contact_only:
    for key in ('TRANSFER_NO_SPECULATIVE','TRANSFER_RIG_NO_SPECULATIVE','TRANSFER_RIG_ALLOW_SPECULATIVE'):os.environ.pop(key,None)
    # Original fixture always advances eight substeps; use its diagnostic
    # counterpart with the same controller and one-substep option.
    os.environ['MIMICKIT_TRANSFER_FIXTURE']=str(OUT/'ablation-fixture.exe')
    baseline=[step(initial,commands) for initial in data['inputs']]
    baseline_matches=all(a['bodies']==b['bodies'] for a,b in zip(baseline,results['stock']))
    assert baseline_matches,'Disabled filter changed the baseline physics'
report=dict(comparisons=comparisons,results=results,disabled_filter_matches_baseline=baseline_matches)
(OUT/('contact-only-snapshots.json' if contact_only else 'rig-contact-snapshots.json')).write_text(json.dumps(report,indent=2))
assert all(math.isfinite(value) for row in comparisons for value in row.values())
print(json.dumps(comparisons),flush=True)
