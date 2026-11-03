"""CPU calibration, independent replay reconstruction and reset/isometry checks."""
import os,sys,json
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'))
import numpy as np,torch
from scipy.spatial.transform import Rotation
from crawl_jiggle import HandJiggle,recorded_cost,SPEC,cancellation_cost
torch.set_num_threads(1)
out=Path(os.environ.get('CRAWL_JIGGLE_TEST_OUT',str(ROOT/'Saved/MimicKitSlowLoco/crawl-jiggle-20261103')))
z=np.load(ROOT/'Saved/MimicKitSlowLoco/jolt-vibration-20261103/replay.npz')
rows=[]
for row in (0,2,5,7):
    suffix='' if row==0 else '_'+str(row)
    p=z['pose'+suffix].astype(np.float64);target=z['reference_pose'+suffix].astype(np.float64)
    cost=recorded_cost(p,[5,8],0,30);ref=recorded_cost(target,[5,8],0,30)
    h=HandJiggle(1,'cpu');ids=torch.tensor([0]);pt=torch.tensor(p,dtype=torch.float32)
    h.reset(ids,pt[0:1,[5,8],:3]-pt[0:1,0:1,:3],pt[0:1,[5,8],3:7]);actual=[0.]
    for frame in range(1,len(p)):
        c,_,_=h.update(pt[frame:frame+1,[5,8],:3]-pt[frame:frame+1,0:1,:3],pt[frame:frame+1,[5,8],3:7],1/30)
        actual.append(float(c[0]))
    np.testing.assert_allclose(actual,cost,atol=2e-4,rtol=2e-4)
    # Common translation/yaw changes neither cancellation nor score.
    yaw=Rotation.from_euler('z',1.1);pp=p.copy();pp[:,:,:3]=yaw.apply(p[:,:,:3].reshape(-1,3)).reshape(p.shape[0],15,3)+[10,20,3]
    pp[:,:,3:]=(yaw*Rotation.from_quat(p[:,:,3:].reshape(-1,4))).as_quat().reshape(-1,15,4)
    np.testing.assert_allclose(recorded_cost(pp,[5,8],0,30),cost,atol=1e-9)
    rows.append(dict(row=row,bad_mean_150_230=float(cost[150:231].mean()),bad_max=float(cost.max()),reference_max=float(ref.max()),torch_numpy_max_error=float(np.max(abs(np.array(actual)-cost)))))
v=torch.zeros(2,6,2,3);a=torch.zeros_like(v)
v[0,:,:,0]=2.;v[1,::2,:,0]=.3;v[1,1::2,:,0]=-.3
c,_,_=cancellation_cost(v,a);assert c[0]==0 and c[1]==5
h=HandJiggle(2,'cpu');h.count[:]=9;h.linear[:]=1;h.reset(torch.tensor([0]),torch.zeros(1,2,3),torch.tensor([[[0.,0,0,1],[0.,0,0,1]]]))
assert h.count.tolist()==[0,9] and not h.linear[0].any() and h.linear[1].all()
result=dict(passed=True,spec=SPEC,rows=rows,constant_motion_zero=True,partial_reset_isolated=True,yaw_translation_invariant=True)
(out/'calibration.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
