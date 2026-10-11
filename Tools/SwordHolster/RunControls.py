import pathlib,subprocess,sys,time,json
root=pathlib.Path(__file__).resolve().parents[2];out=root/'Saved/Diagnostics/SwordOvernight20261011/controls-v2';out.mkdir(exist_ok=True)
cases=[('run-no-neck-contact',['--motion','run','--gaze',str(-24/170),'--cycles','1','--control-at','144','--no-head-contacts']),('run-free-neck-exit',['--motion','run','--gaze',str(-24/170),'--cycles','1','--free-neck-on-exit']),('run-no-action',['--motion','run','--gaze',str(-24/170),'--no-action']),('turn-inputs',['--motion','turn','--gaze-change','--gaze','0','--cycles','1','--pose-detail'])]
for name,opts in cases:
 f=out/(name+'.json');assert not f.exists()
 run=subprocess.run([sys.executable,'Tools/RunUnrealRemote.py','Tools/SwordHolster/ProbeHeadFps.py','--name',name,'--fps','60','--ticks','370','--arm','--output',str(out.relative_to(root)),*opts],cwd=root,capture_output=True,text=True,timeout=40)
 (out/(name+'.log')).write_text(run.stdout+run.stderr)
 end=time.monotonic()+210
 while not f.exists() and time.monotonic()<end:time.sleep(.5)
 assert f.exists(),run.stdout+run.stderr
 print(name,json.loads(f.read_text())['reason'],flush=True);time.sleep(2)
