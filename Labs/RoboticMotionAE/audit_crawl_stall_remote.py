"""Read-only learning-signal audit: actual checkpoint, resets, noise, no updates."""
import os,sys,json,time,zipfile,hashlib
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'crawl-stall-audit-20261102'
sys.path[:0]=[str(OUT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import numpy as np,torch,warp as wp,yaml
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util,torch_util as qu
from flat_com import band_loss

def main():
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261103)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6791);os.chdir(ROOT/'MimicKit')
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg.update(capacity_probe_all_crawl=True,motion_file=str(ROOT/'prepared/motions.yaml'),omni_manifest=str(ROOT/'prepared/manifest.json'))
    N=96;env=DisabledSlowLocoEnv(cfg,ec,N,'cuda:0',False);eng=env._engine;c=env._get_char_id()
    prescribed=torch.tensor([4]*32+[8]*32+[12]*32,device='cuda:0')
    env._cohort[:64]=1;env._cohort[64:]=2
    apply=env._apply_codes
    def fixed(ids,codes):apply(ids,prescribed[ids])
    env._apply_codes=fixed
    agent=OmniPPOAgent(ac,env,'cuda:0');pin=json.loads((OUT/'pinned.json').read_text())
    assert hashlib.sha256(Path(pin['checkpoint']).read_bytes()).hexdigest()==pin['checkpoint_sha256']
    with zipfile.ZipFile(pin['checkpoint']) as z:(OUT/'model.pt').write_bytes(z.read('model.pt'))
    agent.load(str(OUT/'model.pt'));agent.eval();agent._init_train();agent._sample_count=2000000000
    agent.set_mode(AgentMode.TRAIN);obs,info=env.reset();agent._curr_obs,agent._curr_info=obs,info
    meta=dict(checkpoint=pin,codes=prescribed.cpu().tolist(),sample_hz=30,action_noise_std=.05,
        bands=env._disabled_com_bands[0].cpu().tolist(),enabled=env._limb_enabled.cpu().tolist(),
        normalizer_mean_tail=agent._obs_norm._mean[146:].cpu().tolist(),normalizer_std_tail=agent._obs_norm._std[146:].cpu().tolist(),
        action_std_physical=(agent._a_norm._std*.05).cpu().tolist(),loss_weights=env._loss_weights.cpu().tolist(),
        fail_bootstrap=float(agent._compute_fail_val()),note='No optimizer steps; actual TRAIN noise. PPO advantage normalization here is a diagnostic crawl-only batch, not production full-batch normalization.')
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2))
    history={k:[] for k in ('loss','reward','done','age','codes','root','root_velocity','target_velocity','value','action','action_mode','joint_velocity','terms_best_drift','reward_best_drift','sphere_ratio','obs_tail','torque','phase','head_hand_velocity')}
    ppo=[]
    with torch.no_grad():
      for tick in range(256):
        norm=agent._obs_norm.normalize(obs);dist=agent._model.eval_actor(norm)
        value=agent._model.eval_critic(norm).squeeze(-1)
        mode=agent._a_norm.unnormalize(dist.mode)
        action,ai=agent._decide_action(obs,info);agent._record_data_pre_step(obs,info,action,ai)
        ob2,r,done,inf2=env.step(action)
        agent._record_data_post_step(ob2,r,done,inf2)
        pos=eng.get_body_pos(c);rot=eng.get_body_rot(c);ang=eng.get_body_ang_vel(c)
        velocity=eng.get_body_vel(c)-torch.cross(ang,qu.quat_rotate(rot,env._body_com),dim=-1)
        weights=env._mse_body_enabled[:,:,0].float();weights[:,env._head_id]*=3.
        residual=velocity-env.reward_target_vel
        drift=-(residual[:,:,:2]*weights[:,:,None]).sum(1)/weights.sum(1)[:,None]
        corrected=residual.clone();corrected[:,:,:2]+=drift[:,None]
        linear=(corrected.square()*weights[:,:,None]).mean((1,2))*env._loss_weights[1]
        core=(eng.get_body_vel(c)[:,env._flat_com_ids,:2]*env._disabled_com_masses[env._codes,:,None]).sum(1)
        comloss=band_loss(core+drift,env._disabled_com_bands[env._motion_ids,env._codes])*env._flat_com_weight
        newterms=env.loss_terms.clone();newterms[:,1]=linear;newterms[:,4]=comloss
        radii=env._target_radii_sq.sqrt();ratio=env.target_distances_sq.sqrt()/radii
        ratio.masked_fill_(~env._target_termination_enabled,0)
        # Pelvis uses its independently configured world radius, not the old point-array value.
        ratio[:,-1]=torch.linalg.vector_norm(pos[:,0]-env._pelvis_target_world,dim=-1)/env._pelvis_window.radius
        values=(env.loss_terms,r,done,env._timestep_buf,env._codes,pos[:,0],velocity[:,0],env.reward_target_vel[:,0],value,action,mode,eng.get_dof_vel(c),newterms,torch.exp(-newterms.sum(-1)),ratio,obs[:,146:],eng._dof_forces[0],env._command_phase()[1],velocity[:,[2,5,8]])
        for k,v in zip(history,values):history[k].append(v.cpu().numpy().copy())
        obs,info=env.reset(torch.where(done!=0)[0]);agent._curr_obs,agent._curr_info=obs,info;agent._exp_buffer.inc()
        if (tick+1)%32==0:
            stats=agent._build_train_data();normobs=agent._obs_norm.normalize(agent._exp_buffer.get_data('obs'))
            vals=agent._model.eval_critic(normobs).squeeze(-1)
            ppo.append(dict(tick=tick+1,stats={k:float(v) for k,v in stats.items()},
                value=vals.cpu().tolist(),return_target=agent._exp_buffer.get_data('tar_val').cpu().tolist(),
                advantage=agent._exp_buffer.get_data('adv').cpu().tolist(),done=agent._exp_buffer.get_data('done').cpu().tolist()))
            np.savez_compressed(OUT/'rollout.npz',**{k:np.array(v) for k,v in history.items()})
            (OUT/'ppo.json').write_text(json.dumps(ppo));print('AUDIT',tick+1,flush=True)
    # Demonstrate whether hidden sphere error is available to the networks.
    a=env._compute_obs().clone();saved=env._pelvis_target_world.clone();env._pelvis_target_world[:,0]+=2.
    b=env._compute_obs();hidden=dict(max_observation_change=float((a-b).abs().max()),failure_if_shifted=env._pelvis_window.sphere_failed(eng.get_body_pos(c)[:,0]).cpu().tolist())
    env._pelvis_target_world.copy_(saved)
    meta['hidden_sphere_state_test']=hidden;meta['completed_ticks']=256
    meta['passive_leg_torque_max']={str(code):float(np.abs(np.array(history['torque'])[:,np.array(meta['codes'])==code][:,:,(slice(20,27) if code==4 else slice(27,34) if code==8 else slice(20,34))]).max()) for code in (4,8,12)}
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2));print('COMPLETE',flush=True)

if __name__=='__main__':main()
