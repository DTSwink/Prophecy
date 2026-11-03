import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitSlowLoco/body-jiggle-audit-20261103';OUT.mkdir(exist_ok=True)
PATH=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/mimickit_20261103_164528_uefn_slowloco_disabled_curriculum_jiggle_termination_2048/debug/rollout_step_00024524.json')
def body_features(pos,basis,relative=False):
 p=np.asarray(pos);r=np.asarray(basis).swapaxes(-1,-2)
 if relative:p=p-p[:,0:1]
 v=np.diff(p,axis=0)*30
 a=(Rotation.from_matrix(r[1:].reshape(-1,3,3))*Rotation.from_matrix(r[:-1].reshape(-1,3,3)).inv()).as_rotvec().reshape(-1,p.shape[1],3)*30
 out=np.zeros((len(p),p.shape[1],4))
 for f in range(15,len(p)):
  for k,(x,speed) in enumerate(((v,.04),(a,.4))):
   z=x[f-15:f];mean=z.mean(0);n=np.linalg.norm(z,axis=-1)
   c=n.mean(0)-np.linalg.norm(mean,axis=-1);u=z-mean;un=np.linalg.norm(u,axis=-1)
   rev=((u[1:]*u[:-1]).sum(-1)<-.25*un[1:]*un[:-1])&(un[1:]>speed)&(un[:-1]>speed)
   out[f,:,k*2]=c;out[f,:,k*2+1]=rev.sum(0)
 return out,v,a

def main():
 z=json.loads(PATH.read_text());r=0;e=z['rows'][r]['evaluation'];names=e['names']
 for relative in (False,True):
  x,v,a=body_features(z['positions'][r],z['basis'][r],relative)
  print('PEL VIS RELATIVE',relative)
  for b in (0,1,2,3,4,5,6,7,8):
   w=x[30:81,b];print(names[b], 'max LC/REV/AC/REV',np.round(w.max(0),3).tolist(), 'frame45',np.round(x[45,b],3).tolist())
  np.savez_compressed(OUT/('row0_relative.npz' if relative else 'row0_world.npz'),features=x,linear=v,angular=a)
 d=dict(source=str(PATH),row=0,frames=len(z['positions'][0])-1,max_existing_streak=max(e['frame_crawl_jiggle_streak']),terminal=e['terminal_flag'],pelvis_gap_cm=e.get('frame_pelvis_window',[])[-1:] )
 (OUT/'row0.json').write_text(json.dumps(d,indent=2))
if __name__=='__main__':main()
