"""Scale the existing jiggle cost to ~500 per observed complete episode."""
import json,sys,shutil
import deploy_crawl_jiggle as j
BASE=j.D
D=j.d.OUT/'crawl-jiggle-episode500-20261103'
j.D=D;j.c.D=D;j.x.D=D

def inventory():j.inventory()

def prepare():
    import ast,numpy as np
    previous=json.loads((D/'previous-inventory.json').read_text())
    assert all(j.d.sha(j.d.P/n)==h for n,h in previous.items())
    src=j.d.ROOT/'Labs/RoboticMotionAE/crawl_jiggle.py'
    text=src.read_text();shutil.copy2(src,D/'crawl_jiggle.before.py')
    for a,b in [('coefficient=2.','coefficient=9.'),('min(5, 2 *','min(5, 9 *'),('cost=2.*','cost=9.*'),('min(5.,2.*','min(5.,9.*')]:
        assert text.count(a)==1,(a,text.count(a));text=text.replace(a,b)
    ast.parse(text);src.write_text(text);shutil.copy2(src,j.d.P/'pipeline/crawl_jiggle.py')
    diff=[n for n,h in previous.items() if j.d.sha(j.d.P/n)!=h]
    assert diff==['pipeline/crawl_jiggle.py'],diff
    # Re-score the user's latest captures with the exact capped scaling law.
    run=json.loads((D/'previous-run.json').read_text())['run']
    from pathlib import Path
    folder=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+run)/'debug'
    capture=sorted(folder.glob('rollout_step_*.json'))[-1];data=json.loads(capture.read_text())
    rows=[]
    for i,row in enumerate(data['rows']):
        v=np.asarray(row['evaluation']['frame_crawl_jiggle_penalty'])
        if len(v)==301:rows.append(dict(row=i,before=float(v.sum()),after=float(np.minimum(5,v*4.5).sum())))
    assert len(rows)>=4
    j.d.write(D/'episode-calibration.json',dict(source=str(capture),rows=rows,mean_after=float(np.mean([r['after'] for r in rows])),median_after=float(np.median([r['after'] for r in rows])),factor=4.5,cap=5,termination_penalty=500,discount=.99))
    print(json.dumps(dict(rows=len(rows),mean_after=np.mean([r['after'] for r in rows]),changed=diff)),flush=True)

def check():
    import os
    os.environ['CRAWL_JIGGLE_TEST_OUT']=str(D)
    import test_crawl_jiggle as t
    report=json.loads((D/'calibration.json').read_text())
    assert report['passed'] and report['spec']['coefficient']==9
    j.d.write(D/'calibration.json',report)
    old=json.loads((BASE/'preflight-verified.json').read_text())
    old.update(change='coefficient only 2 -> 9; max5 unchanged',coefficient_cpu_checks=True,inherited_full_gpu_preflight=str(BASE/'preflight-verified.json'))
    j.d.write(D/'preflight-verified.json',old)

def stage():j.stage()
def stop():j.stop()
def launch():j.launch()
def audit():return j.audit()
def verify():j.verify()

if __name__=='__main__':globals()[sys.argv[1]]()
