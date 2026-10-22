"""Compact live and replay checks for the extremity-speed restart."""
import json
import sys
from pathlib import Path
import numpy as np
import deploy_locomotion_branch as d


def live():
    run=json.loads((d.OUT/'active_run.json').read_text())['run']
    code='''from pathlib import Path
import json
p=Path('/workspace/mimickit_trial/runs')/RUN
out={}
for name in ['status.json','backup_status.json','resume.json','error.json','finished.json']:
 if (p/name).exists():
  s=json.loads((p/name).read_text())
  if name=='status.json':s={k:s.get(k) for k in ['state','iteration','samples','recent_iteration_mean_seconds','training_transitions_per_second','updated_unix']}
  if name=='resume.json':s={k:s.get(k) for k in ['prior_samples','iteration_offset','optimizer_restored','normalizer_restored']}
  out[name]=s
print(json.dumps(out))
'''.replace('RUN',repr(run))
    result=json.loads(d.remote(code));d.save('extremity-speed-live-verification',dict(run=run,**result))
    print(json.dumps(result),flush=True)


def replay():
    run=json.loads((d.OUT/'active_run.json').read_text())['run']
    path=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+run)/'replay.npz'
    with np.load(path,allow_pickle=False) as z:
        m=json.loads(str(z['metadata']));rows=m['replay_rows'];names=m['names']
        body=[names.index(n) for n in ['right_foot','left_foot','right_hand','left_hand']]
        checked=[]
        for i,row in enumerate(rows):
            if not row.get('perturbed_row'):continue
            suffix='' if i==0 else '_'+str(i)
            p=z['pose'+suffix][...,:3];v=z['world_velocities'+suffix][...,:3];a=z['world_velocities'+suffix][...,3:6]
            speed=np.linalg.norm(v[:,body]-v[:,:1]-np.cross(a[:,:1],p[:,body]-p[:,:1]),axis=-1)
            limits=np.array(row['extremity_speed_limits_m_s'])
            crossed=(speed>limits).any(-1);crossed[0]=False
            hits=np.where(crossed)[0]
            flags=z['data'+suffix][:,0]
            # Recorder includes the terminal state as its final frame.
            if len(hits):
                assert hits[0]==len(speed)-1,(i,int(hits[0]),len(speed))
                assert flags[-1]==1,(i,flags[-1])
            checked.append(dict(row=i,motion=row['motion_file'],frames=len(speed)-1,
                speed_crossing=bool(len(hits)),terminal=int(flags[-1]),limits_m_s=limits.tolist(),
                final_speeds_m_s=speed[-1].tolist()))
        result=dict(run=run,iteration=m['iteration'],checked=checked)
        d.save('extremity-speed-replay-verification',result)
        print(json.dumps(result))


if __name__=='__main__':globals()[sys.argv[1]]()
