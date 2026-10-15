"""Compare supported CG/Newton at identical varied physical states and inputs."""
import json
import numpy as np
import torch
import warp as wp
from scipy.spatial.transform import Rotation
from recovery_env import RecoveryEnv,OUT


def main():
    torch.set_num_threads(1);wp.init();rng=np.random.default_rng(861)
    meta=json.loads((OUT/'uefn.json').read_text());bank=np.load(OUT/'rig-passive.npz')
    q=[np.array(meta['reference_qpos'])];v=[np.zeros(meta['nv'])]
    q.extend(bank['qpos']);v.extend(np.zeros_like(bank['qvel']))
    for path in ('diagnose_05','fixed_prone_04'):
        prefix=np.load(OUT/'runs'/path/'failure-prefix.npz')
        q.extend(prefix['qpos']);v.extend(prefix['qvel'])
    q=np.array(q);v=np.array(v);actions=rng.normal(0,1,(len(q),54)).astype(np.float32)
    results={}
    for solver in ('newton','cg'):
        env=RecoveryEnv(len(q),auto_reset=False,native_motors=True,relative_targets=True,integrator='implicitfast',solver=solver)
        env.qpos.copy_(torch.tensor(q,device='cuda'));env.qvel.copy_(torch.tensor(v,device='cuda'))
        env.controller.actions.copy_(torch.tensor(actions,device='cuda'))
        wp.capture_launch(env.sim.step_graph)
        results[solver]=(env.qpos.cpu().numpy().copy(),env.qvel.cpu().numpy().copy())
    nq,nv=results['newton'];cq,cv=results['cg']
    angular=[]
    for start in [3]+list(range(7,meta['nq'],4)):
        a=Rotation.from_quat(nq[:,start:start+4][:,[1,2,3,0]])
        b=Rotation.from_quat(cq[:,start:start+4][:,[1,2,3,0]])
        angular.extend(np.degrees((a.inv()*b).magnitude()))
    dv=float(abs(nv-cv).max());pos=float(np.linalg.norm(nq[:,:3]-cq[:,:3],axis=1).max()*100)
    angle=float(max(angular))
    report={'passed':dv<.01 and pos<.01 and angle<.01,'states':len(q),
        'max_velocity_component_delta':dv,'max_root_position_delta_cm':pos,'max_joint_rotation_delta_deg':angle,
        'tolerances':{'velocity':.01,'root_position_cm':.01,'rotation_deg':.01},
        'rig_sha256':meta['rig_sha256'],'controller':env.controller.contract,
        'scope':'Single physical step at identical states, including both failure recordings. Not a long-trajectory identity claim.'}
    (OUT/'solver-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    assert report['passed'],report


if __name__=='__main__':main()
