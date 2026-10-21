"""Independent collider-support validation across the full limp corpus."""
import ast,json
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import torch
from ground_random_phat_poses import ROOT, floor_heights, MJCFCharModel
from replay import WORLD_TO_VIEW as V
from util import torch_util as q

torch.set_num_threads(1)
tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
       ['floor_support_points','floor_reset_lift','blend_root_pose']]
scope=dict(torch=torch,np=np,ET=ET,q=q)
exec(compile(ast.Module(body=nodes,type_ignores=[]),'production_floor_reset','exec'),scope)
out=ROOT/'Saved/MimicKitEquipment'
corpus=np.load(out/'limp-inits/corpus.npz')
bodies=json.loads((out/'limp-inits/data.json').read_text())['bodies']
model=MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
support=scope['floor_support_points'](ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml',model.get_body_names(),'cpu')
replay=json.loads(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/mimickit_20261020_190959_uefn_limp_blend_balanced_512/debug/rollout_step_00079324.json').read_text())
def pose(row):
    pos=np.array(replay['positions'][row][0])@V
    rot=R.from_matrix((np.array(replay['basis'][row][0])@V).swapaxes(-1,-2)).as_quat()
    return np.concatenate([pos,rot],-1)
def validate(pos,rot):
    original=pos.clone()
    lift=scope['floor_reset_lift'](pos,rot,support)
    pos=pos.clone();pos[:,:,2]+=lift[:,None]
    actual=floor_heights(torch.cat([pos,rot],-1).numpy(),bodies,corners=True).min(axis=1)
    assert actual.min()>=-1e-7,actual.min()
    np.testing.assert_allclose(pos[:,:,:2],original[:,:,:2],atol=0)
    # Every translated body receives exactly the same vertical correction.
    torch.testing.assert_close(pos-original,torch.stack([torch.zeros_like(lift),torch.zeros_like(lift),lift],-1)[:,None].expand_as(pos),atol=2e-7,rtol=1e-5)
    assert np.max(actual[lift.numpy()>0],initial=0)<5e-6
    return float(actual.min()),float(lift.max())
count=0;minimum=1.;maxlift=0.
for row in [0,1]:
    base=pose(row);world=R.from_quat(base[:,3:])
    joints=np.array([(R.from_quat(model._local_rotation[j]).inv()*world[model._parent_indices[j]].inv()*world[j]).as_quat() for j in range(1,15)])
    dof=model.rot_to_dof(torch.tensor(joints[None],dtype=torch.float32))
    for strength in np.linspace(0,1,21):
        alpha=torch.full((1000,),float(strength))
        root,rotation=scope['blend_root_pose'](
            torch.tensor(base[None,0,:3],dtype=torch.float32).expand(1000,-1),
            torch.tensor(base[None,0,3:],dtype=torch.float32).expand(1000,-1),
            torch.tensor(corpus['root_position']),torch.tensor(corpus['root_quaternion_xyzw']),alpha)
        pos,rot=model.forward_kinematics(root,rotation,model.dof_to_rot(dof+strength*(torch.tensor(corpus['dof'])-dof)))
        m,l=validate(pos,rot);minimum=min(minimum,m);maxlift=max(maxlift,l);count+=1000
p=np.stack([pose(i) for i in range(20)])
validate(torch.tensor(p[:,:,:3],dtype=torch.float32),torch.tensor(p[:,:,3:],dtype=torch.float32))
lift=scope['floor_reset_lift'](torch.tensor(p[11:12,:,:3],dtype=torch.float32),torch.tensor(p[11:12,:,3:],dtype=torch.float32),support)
# Empty batch must work for resets containing only normal rows.
assert scope['floor_reset_lift'](torch.empty(0,15,3),torch.empty(0,15,4),support).shape==(0,)
report=dict(cases=count+20,min_floor_clearance_m=minimum,max_lift_m=maxlift,screenshot_lift_m=lift.item(),
            joint_pose_and_xy_preserved=True,validation='Independent double-precision box corners/capsule endpoints')
(out/'limp-floor-tests.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
