"""Run owned PIE cases sequentially; collect failures without aborting the matrix."""
import subprocess, sys, pathlib, json, time, argparse
p=argparse.ArgumentParser();p.add_argument('--label',default='initial');p.add_argument('--extended',action='store_true');p.add_argument('--only');p.add_argument('--clear-lane',action='store_true');p.add_argument('--cycles',type=int,default=1);p.add_argument('--output',default='Saved/Diagnostics/SwordOvernight20261011');p.add_argument('--gaze',type=float,default=-24/170);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];out=root/a.output/a.label
out.mkdir(parents=True,exist_ok=True)
cases=[(mode,motion,60,a.gaze,False) for mode in ['kinematic','sim'] for motion in ['idle','walk','run']]
if a.extended: cases += [(mode,motion,60,0,True) for mode in ['kinematic','sim'] for motion in ['transition','turn']]+[('sim','run',20,-24/170,False),('sim','walk',60,.95,False),('sim','walk',60,-.95,False)]
results=[]
for mode,motion,fps,gaze,change in cases:
    name=f'{mode}-{motion}-{fps}-{gaze:.3f}'+('-gaze' if change else '')
    if a.only and a.only not in name: continue
    file=out/(name+'.json')
    if file.exists(): raise RuntimeError(f'Refusing to overwrite evidence {file}')
    args=['Tools/SwordHolster/ProbeHeadFps.py','--name',name,'--fps',str(fps),'--ticks',str(720*a.cycles),'--arm','--cycles',str(a.cycles),'--motion',motion,'--gaze',str(gaze),'--output',str(out.relative_to(root))]
    if mode=='kinematic': args+=['--kinematic']
    if change: args+=['--gaze-change']
    if a.clear_lane: args+=['--clear-lane']
    run=subprocess.run([sys.executable,'Tools/RunUnrealRemote.py',*args],cwd=root,capture_output=True,text=True,timeout=40)
    (out/(name+'.dispatch.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
    deadline=time.monotonic()+210
    while not file.exists() and time.monotonic()<deadline: time.sleep(.5)
    if not file.exists(): raise RuntimeError('Capture did not finish; inspect owned session before proceeding.')
    data=json.loads(file.read_text(encoding='utf-8'))
    results.append(dict(name=name,reason=data['reason'],rows=len(data['rows']),actions=data.get('actions')))
    (out/'matrix.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(name,data['reason'],flush=True)
    # Wait for the asynchronous EndPlay teardown before starting another owned run.
    time.sleep(2)
sys.exit(any(r['reason']!='cycles completed' for r in results))
