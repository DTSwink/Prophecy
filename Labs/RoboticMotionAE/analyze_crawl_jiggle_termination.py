"""Offline temporal-rule calibration on archived normal and recent crawl rollouts."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitSlowLoco/jiggle-termination-20261103';OUT.mkdir(exist_ok=True)
RUNS=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')
def features(pos,basis):
    p=np.asarray(pos);rot=np.asarray(basis).swapaxes(-1,-2)
    v=np.diff(p[:,[5,8]]-p[:,0:1],axis=0)*30
    r=Rotation.from_matrix(rot[:,[5,8]].reshape(-1,3,3))
    a=(Rotation.from_matrix(rot[1:,[5,8]].reshape(-1,3,3))*Rotation.from_matrix(rot[:-1,[5,8]].reshape(-1,3,3)).inv()).as_rotvec().reshape(-1,2,3)*30
    out=np.zeros((len(p),2,4))
    for f in range(15,len(p)):
        for k,(x,speed) in enumerate(((v,.04),(a,.4))):
            z=x[f-15:f];n=np.linalg.norm(z,axis=-1)
            cancellation=n.mean(0)-np.linalg.norm(z.mean(0),axis=-1)
            u=z-z.mean(0);un=np.linalg.norm(u,axis=-1)
            rev=((u[1:]*u[:-1]).sum(-1)<-.25*un[1:]*un[:-1])&(un[1:]>speed)&(un[:-1]>speed)
            out[f,:,k*2]=cancellation;out[f,:,k*2+1]=rev.sum(0)
    return out

def first_trigger(x,linear,angular,reversals,persistence=6):
    high=(((x[:,:,0]>linear)&(x[:,:,1]>=reversals))|((x[:,:,2]>angular)&(x[:,:,3]>=reversals))).any(1)
    high[:30]=False;streak=0
    for f,b in enumerate(high):
        streak=streak+1 if b else 0
        if streak>=persistence:return f
    return None

def load():
    records=[]
    for key in ('20261102_140858','20261102_192728','20261103_081246'):
        folder=next(RUNS.glob('mimickit_'+key+'*'))
        files=sorted((folder/'debug').glob('rollout_step_*.json'))
        if key.endswith('081246'):files=files[-10:]
        for file in files:
            data=json.loads(file.read_text())
            for i,row in enumerate(data['rows']):
                meta=row['evaluation'];name=meta.get('motion_name');code=meta.get('disabled_limb_code',0)
                if name not in ('crawl','crawl_idle'):continue
                kind='current' if key.endswith('081246') else ('normal' if code==0 else 'one_leg' if name=='crawl' and code in (4,8) else 'other')
                if kind=='other':continue
                x=features(data['positions'][i],data['basis'][i])
                records.append(dict(source=str(file),row=i,kind=kind,motion=name,frames=len(x),features=x))
                if 'mse_target_positions' in data:
                    x=features(data['mse_target_positions'][i],data['mse_target_basis'][i])
                    records.append(dict(source=str(file),row=i,kind='reference',motion=name,frames=len(x),features=x))
    with np.load(ROOT/'Saved/MimicKitSlowLoco/jolt-vibration-20261103/replay.npz') as z:
        for i in (0,2,5,7):
            suffix='' if i==0 else '_'+str(i)
            pose=z['pose'+suffix]
            x=features(pose[:,:,:3],Rotation.from_quat(pose[:,:,3:].reshape(-1,4)).as_matrix().reshape(-1,15,3,3).swapaxes(-1,-2))
            records.append(dict(source='known vibrating checkpoint22054',row=i,kind='known_bad',motion='crawl',frames=len(x),features=x))
    return records

def main():
    records=load();np.savez_compressed(OUT/'features.npz',**{str(i):r.pop('features') for i,r in enumerate(records)})
    (OUT/'records.json').write_text(json.dumps(records,indent=2))
    z=np.load(OUT/'features.npz');counts={k:sum(r['kind']==k for r in records) for k in ('normal','one_leg','reference','current','known_bad')};print(counts)
    grid=[]
    for lin,ang in ((.04,.4),(.06,.6),(.08,.8),(.10,1.)):
        for rev in (3,4,5):
            hits={k:[] for k in counts}
            for i,r in enumerate(records):
                f=first_trigger(z[str(i)],lin,ang,rev)
                if f is not None:hits[r['kind']].append(f)
            result=dict(linear=lin,angular=ang,reversals=rev,counts={k:len(v) for k,v in hits.items()},current_median_frame=float(np.median(hits['current'])) if hits['current'] else None)
            grid.append(result);print(result)
    (OUT/'grid.json').write_text(json.dumps(dict(counts=counts,grid=grid),indent=2))
if __name__=='__main__':main()
