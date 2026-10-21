"""Read-only reproduction of the step79324 frame0 floor penetration."""
import ast, hashlib, json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import torch
from ground_random_phat_poses import ROOT, floor_heights, MJCFCharModel
from replay import WORLD_TO_VIEW

def main():
    torch.set_num_threads(1)
    out=ROOT/'Saved/MimicKitEquipment'
    path=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/mimickit_20261020_190959_uefn_limp_blend_balanced_512/debug/rollout_step_00079324.json')
    d=json.loads(path.read_text())
    bodies=json.loads((out/'limp-inits/data.json').read_text())['bodies']
    labels=[b['name'] for b in bodies for _ in b['shapes']]
    def pose(row):
        pos=np.array(d['positions'][row][0])@WORLD_TO_VIEW
        mat=(np.array(d['basis'][row][0])@WORLD_TO_VIEW).swapaxes(-1,-2)
        return np.concatenate((pos,R.from_matrix(mat).as_quat()),axis=-1)
    row=11;meta=d['rows'][row]['evaluation'];index=meta['limp_pose_index'];alpha=meta['whole_pose_blend']
    recorded=pose(row);vanilla=pose(0)
    # Normal row0 is unarmed; the selected row uses the drawn idle heading.
    yaw=R.from_euler('z',meta['getup_world_yaw_degrees']-d['rows'][0]['evaluation']['getup_world_yaw_degrees'],degrees=True)
    vanilla[:,:3]=yaw.apply(vanilla[:,:3])
    vanilla[:,3:]=(yaw*R.from_quat(vanilla[:,3:])).as_quat()
    corpus=out/'limp-inits/corpus.npz'
    assert hashlib.sha256(corpus.read_bytes()).hexdigest()==meta['limp_dataset_sha256']
    with np.load(corpus,allow_pickle=False) as data:
        limp=data['body_pose_xyz_xyzw'][index]
        target_dof=torch.tensor(data['dof'][index:index+1])
    model=MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    world=R.from_quat(vanilla[:,3:])
    local=[]
    for j in range(1,15):
        local.append((R.from_quat(model._local_rotation[j].numpy()).inv()
                      *world[model._parent_indices[j]].inv()*world[j]).as_quat())
    base_dof=model.rot_to_dof(torch.tensor(np.array(local)[None],dtype=torch.float32))
    tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
    helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='blend_root_pose')
    scope=dict(torch=torch)
    exec(compile(ast.Module(body=[helper],type_ignores=[]),'production_blend','exec'),scope)
    root,rot=scope['blend_root_pose'](
        torch.tensor(vanilla[None,0,:3],dtype=torch.float32),torch.tensor(vanilla[None,0,3:],dtype=torch.float32),
        torch.tensor(limp[None,0,:3]),torch.tensor(limp[None,0,3:]),torch.tensor([alpha]))
    pos,quat=model.forward_kinematics(root,rot,model.dof_to_rot(base_dof+alpha*(target_dof-base_dof)))
    reproduced=torch.cat((pos,quat),-1).numpy()[0]
    discrepancy=float(np.linalg.norm(reproduced[:,:3]-recorded[:,:3],axis=-1).max())
    assert discrepancy<2e-6,discrepancy
    report=dict(checkpoint_step=79324,row=row,limp_pose_index=index,blend=alpha,
                corpus_hash_verified=True,max_reconstruction_position_error_m=discrepancy)
    for label,p in [('vanilla_front',vanilla),('limp_endpoint',limp),('recorded_blend',recorded)]:
        h=floor_heights(p[None],bodies)[0]
        report[label]=dict(minimum_collider_height_cm=float(h.min()*100),
            deepest_body=labels[h.argmin()],head_minimum_cm=float(min(v for v,b in zip(h,labels) if b=='head')*100))
    heights=np.array([floor_heights(pose(i)[None],bodies).min() for i,r in enumerate(d['rows'])
                      if r['evaluation'].get('perturbed_row')])
    report['recorded_perturbed_starts']=dict(count=len(heights),
        over_5cm_penetration=int((heights<-.05).sum()),worst_cm=float(-heights.min()*100))
    report['cause']='Whole-pose interpolation changes collider support nonlinearly; interpolated pelvis height is not a floor-clearance guarantee. Present at reset before physics.'
    (out/'limp-blend-clipping-audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
