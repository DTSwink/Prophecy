"""Disposable matched-start strength/servo audit; never modifies the live trainer."""
import os,sys,json,time,hashlib,zipfile
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'crawl-capacity-20261102'
sys.path[:0]=[str(OUT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import numpy as np
import torch,warp as wp,yaml,mujoco
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util,torch_util as qu

def main():
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6787)
    os.chdir(ROOT/'MimicKit');started=time.time()
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg['capacity_probe_all_crawl']=True
    cfg['motion_file']=str(ROOT/'prepared/motions.yaml');cfg['omni_manifest']=str(ROOT/'prepared/manifest.json')
    cases=[dict(kind='policy',scale=s,kp=0) for s in (1.,2.,4.)]
    cases += [dict(kind='servo',scale=s,kp=k) for s in (1.,2.,4.) for k in (5.,15.,40.)]
    cases += [dict(kind='hold',scale=s,kp=15.) for s in (1.,4.)]
    cases += [dict(kind='off',scale=0.,kp=0.),dict(kind='all_powered_servo',scale=1.,kp=15.)]
    S=8;N=S*len(cases);env=DisabledSlowLocoEnv(cfg,ec,N,'cuda:0',False)
    eng=env._engine;c=env._get_char_id();ids=torch.arange(N,device='cuda:0')
    agent=OmniPPOAgent(ac,env,'cuda:0');pin=json.loads((OUT/'pinned.json').read_text())
    assert hashlib.sha256(Path(pin['checkpoint']).read_bytes()).hexdigest()==pin['checkpoint_sha256']
    with zipfile.ZipFile(pin['checkpoint']) as z:(OUT/'model.pt').write_bytes(z.read('model.pt'))
    agent.load(str(OUT/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
    mass=eng._sim_model.body_mass.numpy().reshape(N,15)[0].copy()
    mass_t=torch.tensor(mass,device='cuda:0');names=env._kin_char_model.get_body_names()
    armids=[i for i,n in enumerate(names) if 'arm' in n or 'hand' in n]
    legids=[i for i,n in enumerate(names) if 'thigh' in n or 'shin' in n or 'foot' in n]
    caps=wp.to_torch(eng._uefn_motors.upper).clone()
    scales=torch.tensor([v['scale'] for v in cases for _ in range(S)],device='cuda:0')
    kp=torch.tensor([v['kp'] for v in cases for _ in range(S)],device='cuda:0')[:,None]
    original_strength=env._update_head_strength
    def strength():
        original_strength();env._motor_mask[:,:20].mul_(scales[:,None])
    env._update_head_strength=strength
    mujoco.mj_saveModel(eng._solver.mj_model,str(OUT/'actual-model.mjb'))
    joint_map={names[b]:list(range(env._kin_char_model.get_joint(b).dof_idx,
        env._kin_char_model.get_joint(b).dof_idx+env._kin_char_model.get_joint(b).get_dof_dim())) for b in range(1,15)}
    duration=float(env._motion_lib.get_motion_length(0));phases=torch.arange(S,device='cuda:0')/S*duration
    meta=dict(cases=cases,seeds=S,worlds=N,names=names,joint_dofs=joint_map,mass_kg=mass.tolist(),
        caps_nm=caps.cpu().tolist(),action_low=env._action_bound_low.cpu().tolist(),action_high=env._action_bound_high.cpu().tolist(),
        source=pin,reference_cycle_seconds=duration,reference_rate=.5,sample_hz=30,
        note='No resets inside 12-second trials. Torque/contact samples at last 240Hz substep of each 30Hz frame. All starts zero velocity. Extra-strength conditions change torque caps only, not gains or policy weights.')
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2))
    summaries={}
    with torch.no_grad():
      for init_kind in ('authored','random_passive'):
        torch.manual_seed(20261102);env.reset()
        env._time_buf.zero_();env._timestep_buf.zero_();env._done_buf.zero_()
        times=phases if init_kind=='authored' else env._init_times[0,12,torch.arange(S,device='cuda:0')]
        env._motion_time_offsets.copy_(times.repeat(len(cases)));env._update_ref_motion()
        vals=env._motion_lib.calc_motion_frame(env._motion_ids,env._motion_time_offsets)
        q0=env._motion_lib.joint_rot_to_dof(vals[4])
        if init_kind=='random_passive':
            # The same validated passive-leg poses in every actuator/controller condition.
            bank=env._init_dofs[0,12,torch.arange(S,device='cuda:0')].repeat(len(cases),1)
            q0[:,20:]=bank[:,20:]
        eng.set_root_pos(ids,c,vals[0]);eng.set_root_rot(ids,c,vals[1]);eng.set_dof_pos(ids,c,q0)
        eng.set_root_vel(ids,c,0.);eng.set_root_ang_vel(ids,c,0.);eng.set_dof_vel(ids,c,0.)
        eng._sim_state.pre_step_update();eng._sim_state.eval_fk();eng._body_velocity.update(eng._sim_state.raw_state)
        env._motor_enabled_binary[:,:20]=1.;env._motor_enabled_binary[:,20:]=0.
        env._motor_enabled_binary[-S:,20:]=1.  # explicitly labelled independent-controller control
        env._pelvis_window.reset(ids,eng.get_body_pos(c)[:,0],env._ref_body_pos[:,0])
        env._update_observations();env._update_info();obs=env._obs_buf;info=env._info
        firstpos=eng.get_body_pos(c).clone();data={k:[] for k in ('pos','rot','com','comvel','torque','qvel','command','contact','done','target')}
        for tick in range(360):
            action,_=agent._decide_action(obs,info)
            future=env._motion_lib.calc_motion_frame(env._motion_ids,env._get_motion_times()+.5/30)
            cur=env._kin_char_model.dof_to_rot(eng.get_dof_pos(c))
            # Quaternion relative rotation for ball joints, rather than exp-map subtraction.
            delta=env._kin_char_model.compute_dof_vel(cur,future[4],1.)
            servo=delta*kp+future[5]*.5
            holdrot=env._kin_char_model.dof_to_rot(q0)
            hold=env._kin_char_model.compute_dof_vel(cur,holdrot,1.)*kp
            for j,case in enumerate(cases):
                sl=slice(j*S,(j+1)*S)
                if case['kind'] in ('servo','all_powered_servo'):action[sl]=servo[sl]
                elif case['kind']=='hold':action[sl]=hold[sl]
                elif case['kind']=='off':action[sl]=0.
            action=action.clamp(env._action_bound_low,env._action_bound_high)
            obs,reward,done,info=env.step(action)
            pos=eng.get_body_pos(c);rot=eng.get_body_rot(c)
            com=((pos+qu.quat_rotate(rot,env._body_com))*mass_t[None,:,None]).sum(1)/mass_t.sum()
            comvel=(eng.get_body_vel(c)*mass_t[None,:,None]).sum(1)/mass_t.sum()
            for key,value in zip(data,(pos,rot,com,comvel,eng._dof_forces[0],eng.get_dof_vel(c),action,eng.get_ground_contact_forces(c),done,env._ref_body_pos[:,0])):
                data[key].append(value.cpu().numpy().copy())
        data={k:np.array(v) for k,v in data.items()};np.savez_compressed(OUT/(init_kind+'.npz'),**data,initial_pos=firstpos.cpu().numpy(),initial_q=q0.cpu().numpy())
        results=[]
        for j,case in enumerate(cases):
            sl=slice(j*S,(j+1)*S);pos=data['pos'][:,sl];torque=data['torque'][:,sl];vel=data['qvel'][:,sl]
            progress=pos[-1,:,0,0]-pos[59,:,0,0];lat=pos[-1,:,0,1]-pos[59,:,0,1]
            upcaps=caps[:20].cpu().numpy()*case['scale'];sat=np.abs(torque[60:,:,:20])>=.95*np.maximum(upcaps,1e-6)
            result=dict(**case,forward_speed_2_to_12_s=(progress/10).tolist(),lateral_drift_2_to_12_s=lat.tolist(),
                min_head_height=pos[60:,:,names.index('head'),2].min(0).tolist(),min_pelvis_height=pos[60:,:,0,2].min(0).tolist(),
                upper_saturation_fraction_by_dof=sat.mean((0,1)).tolist(),upper_peak_torque=np.abs(torque[:,:,:20]).max((0,1)).tolist(),
                disabled_peak_torque=float(abs(torque[:,:,:][...,20:]).max()) if case['kind']!='all_powered_servo' else None,
                positive_motor_work_j=np.maximum(torque*vel,0).sum((0,2)).tolist(),
                hand_contact_fraction=(data['contact'][60:,sl][:,:, [names.index('right_hand'),names.index('left_hand')],2]>5).mean((0,1)).tolist(),
                arm_ground_force_mean=data['contact'][60:,sl][:,:,armids].sum(2).mean((0,1)).tolist(),
                leg_ground_force_mean=data['contact'][60:,sl][:,:,legids].sum(2).mean((0,1)).tolist())
            result['positive_motor_work_j']=[x/30 for x in result['positive_motor_work_j']]
            results.append(result)
        summaries[init_kind]=results;(OUT/'summary.json').write_text(json.dumps(summaries,indent=2))
        print('PASS',init_kind,[(r['kind'],r['scale'],r['kp'],round(float(np.median(r['forward_speed_2_to_12_s'])),3)) for r in results],flush=True)
    print('COMPLETE seconds',time.time()-started,flush=True)

if __name__=='__main__': main()
