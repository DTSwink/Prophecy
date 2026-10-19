"""Read-only frozen-policy comparison on identical motion/phase starts, locally."""
import os, sys, io, json, zipfile, argparse, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'Saved/MimicKitMotorAudit/source'
OUT = ROOT/'Saved/MimicKitEquipment/torque-regression'
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'), str(Path(__file__).parent),
               str(SOURCE/'MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
os.environ['OMP_NUM_THREADS']='1'
import numpy as np, torch, warp as wp, yaml
from omni_walk import OmniWalkEnv
from omni_policy import OmniPPOAgent
from envs.base_env import EnvMode
from learning.base_agent import AgentMode
from util import mp_util

class FixedStarts(OmniWalkEnv):
    def _reset_ref_motion(self, ids):
        if not hasattr(self, 'diagnostic_motions'):
            return super()._reset_ref_motion(ids)
        self._motion_ids[ids] = self.diagnostic_motions[ids]
        self._motion_time_offsets[ids] = self.diagnostic_times[ids]
        values = self._motion_lib.calc_motion_frame(self._motion_ids[ids], self.diagnostic_times[ids])
        for dest, value in zip((self._ref_root_pos, self._ref_root_rot, self._ref_root_vel,
                               self._ref_root_ang_vel, self._ref_joint_rot, self._ref_dof_vel), values):
            dest[ids] = value
        pos, rot = self._kin_char_model.forward_kinematics(self._ref_root_pos, self._ref_root_rot, self._ref_joint_rot)
        self._ref_body_pos.copy_(pos); self._ref_body_rot.copy_(rot)
        self._ref_dof_pos[ids] = self._motion_lib.joint_rot_to_dof(values[4])

def main():
    p=argparse.ArgumentParser();p.add_argument('--caps',choices=['old','new'],default='new')
    p.add_argument('--policy',type=int,nargs='+',default=[15762,15862]);p.add_argument('--ticks',type=int,default=300);a=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(711)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6787)
    os.chdir(SOURCE/'MimicKit')
    with zipfile.ZipFile(OUT/'models.zip') as z:
        cfg={n:yaml.safe_load(z.read('15762/'+n+'_config.yaml').decode().replace('/workspace/mimickit_trial',SOURCE.as_posix())) for n in ['env','engine','agent']}
        models={it:torch.load(io.BytesIO(z.read(str(it)+'/model.pt')),map_location='cuda:0',weights_only=True) for it in a.policy if it!=15661}
    if 15661 in a.policy:
        with zipfile.ZipFile(ROOT/'Saved/MimicKitEquipment/torque-resume-checkpoint.zip') as z:
            models[15661]=torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
    motionfile=OUT/'motions.yaml'
    motionfile.write_text((SOURCE/'prepared/motions.yaml').read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    cfg['env']['motion_file']=str(motionfile);cfg['env'].pop('adaptive_motion_rows',None)
    if a.caps=='old':cfg['engine'].pop('uefn_motor_torque_caps_nm',None)
    motions=yaml.safe_load(motionfile.read_text())['motions']
    admitted=[i for i,r in enumerate(motions) if r['weight']>0]
    cases=[(i,k/4) for i in admitted for k in range(4)]
    n=len(cases);begun=time.perf_counter()
    env=FixedStarts(cfg['env'],cfg['engine'],n*len(a.policy),'cuda:0',False)
    if a.caps=='old':
        # Isolate torque caps only: keep the CURRENT velocity-command bounds.
        envelope=json.loads((ROOT/'Saved/MimicKitMotorAudit/one_tick/calibration_all/envelope.json').read_text())
        peaks=env._motion_lib._frame_dof_vel.abs().amax(0)
        caps=torch.tensor(envelope['applied_caps_nm'],device='cuda:0')
        gains=torch.tensor(envelope['base_gains'],device='cuda:0')
        bounds=torch.maximum(env._action_bound_high,(peaks+caps/gains)*1.05)
        env._action_bound_high.copy_(bounds);env._action_bound_low.copy_(-bounds)
        env._action_space.high[:]=bounds.cpu().numpy();env._action_space.low[:]=-bounds.cpu().numpy()
    agents=[]
    for it in a.policy:
        agent=OmniPPOAgent(cfg['agent'],env,'cuda:0');agent.load_state_dict(models[it]);agent.eval();agent.set_mode(AgentMode.TEST);agents.append(agent)
    env.set_mode(EnvMode.TEST)
    mids=torch.tensor([c[0] for c in cases],device='cuda:0')
    phases=torch.tensor([c[1] for c in cases],device='cuda:0')
    env.diagnostic_motions=mids.repeat(len(a.policy));env.diagnostic_times=(phases*env._motion_lib.get_motion_length(mids)).repeat(len(a.policy))
    obs,info=env.reset()
    initial_obs=obs[:n].clone()
    for group in range(1,len(a.policy)):torch.testing.assert_close(initial_obs,obs[group*n:(group+1)*n],rtol=0,atol=2e-5)
    ticks=torch.full((n*len(a.policy),),a.ticks,device='cuda:0',dtype=torch.long)
    alive=torch.ones_like(ticks,dtype=torch.bool)
    reason=torch.zeros_like(ticks);point=torch.full_like(ticks,-1)
    distance=torch.zeros_like(ticks,dtype=torch.float32)
    first_actions=[];action_errors=[];cap_duty=torch.zeros((len(a.policy),34),device='cuda:0');cap_count=torch.zeros(len(a.policy),device='cuda:0')
    with torch.no_grad():
        for tick in range(1,a.ticks+1):
            actions=torch.cat([agent._decide_action(obs[g*n:(g+1)*n],{})[0] for g,agent in enumerate(agents)])
            if tick==1:first_actions=actions.clone()
            obs,r,done,info=env.step(actions)
            for g in range(len(a.policy)):
                live=alive[g*n:(g+1)*n]
                tor=wp.to_torch(env._engine._uefn_motors.torque)[g*n:(g+1)*n]
                caps=wp.to_torch(env._engine._uefn_motors.upper)
                cap_duty[g]+=((tor.abs()>=caps*.99)&live[:,None]).sum(0);cap_count[g]+=live.sum()
            failed=alive&(done!=0)
            ticks[failed]=tick;reason[failed]=done[failed].long()
            ds,pt=env.target_distances_sq.sqrt().max(-1)
            point[failed]=pt[failed];distance[failed]=ds[failed]
            alive&=~failed
            # Stop measurement on first termination. No policy updates, resets or reallocation.
            if tick%60==0:print('progress',tick,'surviving',alive.reshape(len(a.policy),n).sum(-1).tolist(),flush=True)
    names=[Path(env._motion_lib.get_motion_file(i)).stem for i in range(env._motion_lib.get_num_motions())]
    report=dict(caps=a.caps,phases=4,admitted_motions=len(admitted),policy_hz=30,seconds=a.ticks/30,
                learning=False,noise=0,adaptive=False,command_bounds='current for both torque conditions',elapsed=time.perf_counter()-begun,
                configs_equal=True,normalizers_equal=all(torch.equal(models[a.policy[0]][k],models[it][k]) for it in a.policy for k in models[it] if '_norm.' in k),results=[])
    for g,it in enumerate(a.policy):
        t=ticks[g*n:(g+1)*n].cpu().numpy();rs=reason[g*n:(g+1)*n].cpu().numpy()
        report['results'].append(dict(iteration=it,mean_seconds=float(t.mean()/30),completed_horizon=int((rs!=1).sum()),
            last_substep_cap_duty=(cap_duty[g]/cap_count[g]).cpu().tolist(),
            cases=[dict(motion=names[mid],phase=phase,seconds=float(t[j]/30),terminal=int(rs[j]),
                furthest_point=int(point[g*n+j]),distance_m=float(distance[g*n+j])) for j,(mid,phase) in enumerate(cases)]))
    label=a.caps+'_'+'_'.join(map(str,a.policy))
    torch.save(dict(obs=initial_obs.cpu(),actions=first_actions.cpu(),models=a.policy),OUT/(label+'_initial.pt'))
    (OUT/(label+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)
    print('RESULTS',[(r['iteration'],r['mean_seconds'],r['completed_horizon']) for r in report['results']],flush=True)

if __name__=='__main__':main()
