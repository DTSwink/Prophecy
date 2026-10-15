"""Isolated deterministic checkpoint/physics experiments. Never contacts Unreal."""
from pathlib import Path
import os, sys, json, time, argparse
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('MIMICKIT_TRANSFER_OUT',ROOT/'Saved/MimicKitTransfer')).resolve()
SOURCE=OUT/'source'
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(SOURCE/'pipeline'),
             str(SOURCE/'MimicKit/mimickit'),str(ROOT/'Labs/PhysicalRecoveryLab')]
import numpy as np
import torch, yaml, warp as wp
import mujoco
from omni_walk import OmniWalkEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util

def setup():
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cpu')
    if mp_util.global_mp_device is None:mp_util.init(0,1,'cpu',6732)
    else:assert mp_util.global_mp_device=='cpu' and mp_util.global_num_procs==1
    os.chdir(SOURCE/'MimicKit')
    configs=[]
    for name in ('env','engine','agent'):
        text=(OUT/f'checkpoint/{name}_config.yaml').read_text()
        text=text.replace('/workspace/mimickit_trial',SOURCE.as_posix())
        configs.append(yaml.safe_load(text))
    env=OmniWalkEnv(configs[0],configs[1],1,'cpu',False)
    agent=OmniPPOAgent(configs[2],env,'cpu');agent.load(str(OUT/'checkpoint/model.pt'))
    agent.eval();agent.set_mode(AgentMode.TEST)
    return env,agent

def state(env):
    e=env._engine;c=env._get_char_id()
    return torch.cat([e.get_body_pos(c),e.get_body_rot(c),e.get_body_vel(c),e.get_body_ang_vel(c)],-1)[0].numpy().copy()

def physical_state(env):
    """Read actual generalized state, independently compute true rigid-body velocities."""
    solver=env._engine._solver;m=solver.mj_model;d=mujoco.MjData(m)
    d.qpos[:]=solver.mjw_data.qpos.numpy()[0];d.qvel[:]=solver.mjw_data.qvel.numpy()[0]
    mujoco.mj_forward(m,d);rows=[]
    for name in env._kin_char_model.get_body_names():
        ids=[i for i in range(1,m.nbody) if m.body(i).name==name or m.body(i).name.endswith('/'+name) or m.body(i).name.endswith('_'+name)]
        assert len(ids)==1,(name,ids)
        i=ids[0];jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jacBodyCom(m,d,jp,jr,i)
        rows.append(np.r_[d.xpos[i],np.roll(d.xquat[i],-1),jp@d.qvel,jr@d.qvel])
    return np.array(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--ticks',type=int,default=60);p.add_argument('--phases',type=int,default=1)
    p.add_argument('--tag',default='newton');p.add_argument('--zero-armature',action='store_true');a=p.parse_args()
    start=time.perf_counter();env,agent=setup();duration=float(env._motion_lib.get_motion_lengths()[0]);reports=[]
    if a.zero_armature:
        solver=env._engine._solver
        original=solver.mj_model.dof_armature.copy()
        assert np.count_nonzero(original)==34
        solver.mj_model.dof_armature[:]=0;solver.mjw_model.dof_armature.zero_()
        print('DIAGNOSTIC ONLY: removed generalized motor armature; all other settings unchanged',flush=True)
    for phase in np.arange(a.phases)/a.phases:
        env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.full((n,),float(phase*duration)))
        obs,info=env.reset();states=[state(env)];physical=[np.full((15,13),np.nan)];observations=[obs.numpy().copy()];actions=[];done=[];dist=[];targets=[]
        for tick in range(a.ticks):
            with torch.no_grad():action,_=agent._decide_action(obs,info)
            actions.append(action.numpy().copy());obs,reward,flag,info=env.step(action)
            states.append(state(env));physical.append(physical_state(env));observations.append(obs.numpy().copy());done.append(int(flag[0]));dist.append(env.target_distances_sq.sqrt().numpy().copy())
            targets.append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1)[0].numpy().copy())
            if flag[0]:break
        np.savez_compressed(OUT/f'{a.tag}_phase_{phase:.3f}.npz',states=states,physical=physical,obs=observations,actions=actions,done=done,dist=dist,targets=targets)
        report=dict(phase=float(phase),ticks=len(actions),done=done[-1],max_target_distance_m=float(np.max(dist)),elapsed_s=time.perf_counter()-start)
        reports.append(report);print('RESULT',json.dumps(report),flush=True)
    (OUT/f'{a.tag}_report.json').write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
