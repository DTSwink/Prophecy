"""Collect owned-PIE lifecycle checks, preserving every result and user assets."""
import pathlib,subprocess,sys,time,json,argparse
p=argparse.ArgumentParser();p.add_argument('--label',default='lifecycle');p.add_argument('--output',default='Saved/Diagnostics/SwordOvernight20261011');args=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];out=root/args.output/args.label;out.mkdir(parents=True,exist_ok=True)
cases=[]
for action,phase,drawing,custom in [('complete',1,False,False),('complete',1,False,True),('hide',1,False,False),('hide',2,False,False),('hide',4,False,False),('drop',2,False,False),('mode',4,False,False),('sword_destroy',1,False,False),('hide',2,True,True)]:
 name=f"{action}-{phase}-{'draw' if drawing else 'sheathe'}"+('-custom' if custom else '')
 opts=['--action',action,'--phase',str(phase)]+(['--drawing'] if drawing else [])+(['--custom'] if custom else [])
 cases.append((name,'VerifyNeckLimits.py',opts))
for name,opts in [('repeat-sim',['--repeat','2','--pause','--walk']),('repeat-kinematic',['--repeat','2','--pause','--walk','--kinematic','--switch-back'])]:cases.append((name,'VerifyPlay.py',['--name',name,*opts]))
results=[]
for name,script,opts in cases:
 f=out/(name+'.json');assert not f.exists(),f
 run=subprocess.run([sys.executable,'Tools/RunUnrealRemote.py','Tools/SwordHolster/'+script,'--output',str(out.relative_to(root)),*opts],cwd=root,capture_output=True,text=True,timeout=40)
 (out/(name+'.dispatch.log')).write_text(run.stdout+run.stderr)
 deadline=time.monotonic()+210
 while not f.exists() and time.monotonic()<deadline:time.sleep(.5)
 assert f.exists(),run.stdout+run.stderr
 d=json.loads(f.read_text());results.append(dict(name=name,reason=d['reason']));(out/'summary.json').write_text(json.dumps(results,indent=2));print(name,d['reason'],flush=True);time.sleep(2)
sys.exit(any(not r['reason'].startswith('passed') for r in results))
