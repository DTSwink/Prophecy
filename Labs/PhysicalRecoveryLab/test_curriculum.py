"""Standing practice initialization and separation from floor recovery metrics."""
import json
import numpy as np
import torch
import warp as wp
import mujoco
from recovery_env import RecoveryEnv,OUT


def main():
    torch.set_num_threads(1);torch.manual_seed(561);wp.init()
    env=RecoveryEnv(128,standing_fraction=.4,native_motors=True,relative_targets=True,integrator='implicitfast')
    standing=env.started_standing.clone();count=int(standing.sum())
    assert 30<count<75,count
    torch.testing.assert_close(env.qpos[standing],env.standing_start[None,:].expand(count,-1))
    torch.testing.assert_close(env.qpos[~standing],env.bank[0][None,:].expand(128-count,-1))
    assert torch.count_nonzero(env.qvel)==0
    m=env.sim.mj_model;d=mujoco.MjData(m);d.qpos[:]=env.standing_start.cpu().numpy();mujoco.mj_kinematics(m,d)
    bottoms=[]
    for name in ('foot_l_shape0','foot_r_shape0'):
        g=m.geom(name).id;bottoms.append(float(d.geom_xpos[g,2]-abs(d.geom_xmat[g].reshape(3,3)[2])@m.geom_size[g]))
    assert abs(min(bottoms)-.001)<1e-6,bottoms
    result=env.step(torch.zeros_like(env.controller.actions))
    expected=float(env.qpos[~standing,2].mean());actual=float(result[3]['log']['Recovery/pelvis_z'])
    assert abs(expected-actual)<1e-6,(expected,actual)
    env.standing_fraction=1;env.reset(torch.ones(128,device='cuda',dtype=torch.bool));env.ever_stood.fill_(True)
    result=env.step(torch.zeros_like(env.controller.actions))
    assert float(result[3]['log']['Recovery/stood_1s'])==0
    assert float(result[3]['log']['Practice/stood_1s'])==1
    report={'passed':True,'standing_starts':count,'floor_starts':128-count,'foot_clearance_m':bottoms,
        'zero_reset_velocity':True,'floor_metrics_exclude_standing_practice':True,'rig_sha256':env.metadata['rig_sha256']}
    (OUT/'curriculum-tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
