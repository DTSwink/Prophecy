"""Bounded, isolated reconstruction of one saved rollout; never alters training."""
import os,sys,io,json,zipfile,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from amp_standing import register_network
from world_pose import WorldPoseEnv
from util import torch_util

def main():
    started=time.perf_counter();archive=Path(sys.argv[1]);output=Path(sys.argv[2])
    with zipfile.ZipFile(archive) as z:
        cfg=yaml.safe_load(z.read('env_config.yaml'));ecfg=yaml.safe_load(z.read('engine_config.yaml'))
        acfg=yaml.safe_load(z.read('agent_config.yaml'))
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
        with np.load(io.BytesIO(z.read('replay.npz'))) as a:
            recorded=a['pose'].copy();meta=json.loads(str(a['metadata']))
    assert meta['iteration']==24137 and len(recorded)==14
    torch.set_num_threads(1);upstream.mp_util.init(0,1,'cuda:0',6745);register_network();os.chdir(ROOT/'MimicKit')
    env=WorldPoseEnv(cfg,ecfg,1,'cuda:0',False)
    agent=PPOAgent(acfg,env,'cuda:0');agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TEST)
    engine=env._engine;char=env._get_char_id();kin=env._kin_char_model
    first=torch.tensor(recorded[0],device='cuda:0');q=first[:,3:]
    joint=torch.stack([torch_util.quat_mul(torch_util.quat_conjugate(kin._local_rotation[j]),
        torch_util.quat_mul(torch_util.quat_conjugate(q[kin.get_parent_id(j)]),q[j]))
        for j in range(1,kin.get_num_joints())])[None]
    dofs=kin.rot_to_dof(joint)
    original_reset=env._reset_char
    def reset(ids):
        original_reset(ids)
        engine.set_root_pos(ids,char,first[None,0,:3]);engine.set_root_rot(ids,char,first[None,0,3:])
        engine.set_dof_pos(ids,char,dofs)
    env._reset_char=reset
    def rollout():
        obs,info=env.reset();poses=[torch.cat((engine.get_body_pos(char),engine.get_body_rot(char)),-1)[0].cpu().numpy().copy()]
        for tick in range(len(recorded)-1):
            action,_=agent._decide_action(obs,info);obs,_,_,info=env.step(action)
            poses.append(torch.cat((engine.get_body_pos(char),engine.get_body_rot(char)),-1)[0].cpu().numpy().copy())
        return np.stack(poses)
    with torch.no_grad():
        baseline=rollout()
        # Preserve solver stepping; read solved contacts after EACH physics substep.
        # Disable this isolated engine's graph so the Python recording hook executes.
        engine._graph=None;original_step=engine._solver.step;forces=[]
        def step(state0,state1,control,contacts,dt):
            result=original_step(state0,state1,control,contacts,dt)
            engine._solver.update_contacts(contacts,state1)
            engine._ground_contact_sensor.update(state1,contacts)
            forces.append(engine.get_ground_contact_forces(char)[0].cpu().numpy().copy())
            return result
        engine._solver.step=step
        measured=rollout()
    forces=np.stack(forces);assert len(forces)==104 and np.isfinite(forces).all()
    def deviation(actual,reference):
        pos=np.linalg.norm(actual[:,:,:3]-reference[:,:,:3],axis=-1)
        dot=np.abs((actual[:,:,3:]*reference[:,:,3:]).sum(-1)).clip(0,1)
        ang=np.degrees(2*np.arccos(dot))
        return dict(max_position_error_m=float(pos.max()),position_error_by_tick_m=pos.max(-1).tolist(),
            max_rotation_error_deg=float(ang.max()),rotation_error_by_tick_deg=ang.max(-1).tolist())
    arm={}
    for name in ['right_upper_arm','right_lower_arm','right_hand']:
        idx=meta['names'].index(name);mag=np.linalg.norm(forces[:,idx],axis=-1);peak=int(mag.argmax())
        arm[name]=dict(peak_force_N=float(mag[peak]),peak_normal_force_N=float(np.abs(forces[:,idx,2]).max()),
            peak_substep=peak+1,peak_time_s=(peak+1)/240,policy_tick=peak//8+1,
            impulse_magnitude_integral_Ns=float(mag.sum()/240),force_N_by_substep=mag.tolist())
    report=dict(checkpoint=archive.name,iteration=meta['iteration'],captured_unix=meta['generated_unix'],
        saved_contact_forces=False,worlds=1,physics_hz=240,policy_hz=30,
        baseline_vs_recording=deviation(baseline,recorded),instrumented_vs_recording=deviation(measured,recorded),
        instrumented_vs_baseline=deviation(measured,baseline),right_arm=arm,elapsed_seconds=time.perf_counter()-started)
    output.write_text(json.dumps(report,indent=2));np.savez_compressed(output.with_suffix('.npz'),recorded=recorded,baseline=baseline,measured=measured,ground_forces=forces)
    print('ARM_IMPACT_DIAGNOSIS',json.dumps({k:v for k,v in report.items() if k!='right_arm'}),flush=True)

if __name__=='__main__':main()
