"""Bounded numerical and 512-world resumed-policy checks; no optimization."""
import os, sys, json, tempfile, zipfile, time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch, yaml, numpy as np
import run as upstream
from learning.base_agent import AgentMode
from absolute_walk import AbsoluteWalkEnv, aligned_positions, world_velocities, errors
from observe import Recorder
from resume import restore
from util import torch_util as q


def main():
    begun=time.perf_counter(); torch.set_num_threads(1); os.chdir(ROOT/'MimicKit')
    cp=Path(sys.argv[1])
    with zipfile.ZipFile(cp) as z:
        config=yaml.safe_load(z.read('env_config.yaml'))
        engine=yaml.safe_load(z.read('engine_config.yaml'))
        agent_config=z.read('agent_config.yaml')
    config['absolute_world_body_objective']='four_equal_mse_exp_reward_xy_position_only'
    calibration=json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv)>2 else None
    if calibration:config['absolute_loss_calibration']=calibration
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'env.yaml').write_text(yaml.safe_dump(config));(d/'engine.yaml').write_text(yaml.safe_dump(engine));(d/'agent.yaml').write_bytes(agent_config)
        args=upstream.load_args(['train','--env_config',str(d/'env.yaml'),'--engine_config',str(d/'engine.yaml'),
            '--agent_config',str(d/'agent.yaml'),'--rand_seed','20261014','--visualize','false','--logger','tb'])
        upstream.mp_util.init(0,1,'cuda:0',6742);upstream.set_rand_seed(args)
        env=AbsoluteWalkEnv(config,engine,512,'cuda:0',False)
        agent=upstream.build_agent(args,env,'cuda:0');resumed=restore(agent,cp)
        agent.eval();agent.set_mode(AgentMode.TEST)
        # Reference derivative check strictly within source interpolation segments.
        lib=env._motion_lib;kin=env._kin_char_model
        ids=torch.zeros(128,device='cuda:0',dtype=torch.long)
        count=int(lib._motion_num_frames[0]);fps=lib._motion_fps[0]
        times=((torch.arange(128,device='cuda:0')%(count-1))+.37)/fps
        p,r,v,w,j,dv=lib.calc_motion_frame(ids,times)
        bp,br=kin.forward_kinematics(p,r,j)
        bv,bw=env._world_reference_velocities(bp,br,v,w,dv,ids,times)
        dt=1e-3
        pm,rm,_,_,jm,_=lib.calc_motion_frame(ids,times-dt)
        pp,rp,_,_,jp,_=lib.calc_motion_frame(ids,times+dt)
        bm,qm=kin.forward_kinematics(pm,rm,jm);be,qe=kin.forward_kinematics(pp,rp,jp)
        numeric_v=(be-bm)/(2*dt);numeric_w=q.quat_to_exp_map(q.quat_diff(qm,qe))/(2*dt)
        linear_error=float((bv-numeric_v).abs().max());angular_error=float((bw-numeric_w).abs().max())
        assert linear_error<.015,(linear_error,'world linear FK derivative')
        assert angular_error<.025,(angular_error,'world angular FK derivative')
        # XY follows character; Z/orientation/velocity remain authored world values.
        shifted=bp+torch.tensor([12.,-7.,0.],device='cuda:0')
        target=aligned_positions(shifted,bp)
        torch.testing.assert_close(target,shifted)
        zero=errors(shifted,br,bv,bw,target,br,bv,bw)
        assert float(zero.abs().max())<1e-10
        torch.testing.assert_close(errors(shifted,-br,bv,bw,target,br,bv,bw),zero)
        lowered=shifted.clone();lowered[:,0,2]-=.3
        height=errors(lowered,br,bv,bw,aligned_positions(lowered,bp),br,bv,bw)
        assert (height[:,0]>0).all() and (height[:,1:]==0).all()
        yaw=q.exp_map_to_quat(torch.tensor([0.,0.,1.],device='cuda:0').expand_as(v))
        turned=q.quat_mul(yaw[:,None].expand_as(br),br)
        assert (errors(shifted,turned,bv,bw,target,br,bv,bw)[:,2]>0).all()
        faster=bv.clone();faster[:,0,0]+=1
        assert (errors(shifted,br,faster,bw,target,br,bv,bw)[:,1]>0).all()
        with torch.no_grad():
            obs,info=env.reset();rec=Recorder(env,d);rec.start();rollout=time.perf_counter()
            for tick in range(305):
                action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
                assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
                assert torch.isfinite(env.loss_terms).all()
                torch.testing.assert_close(reward,torch.exp(-env.loss_terms.sum(-1)))
                reset=(done!=0).nonzero().flatten()
                obs,info=env.reset(reset)
            elapsed=time.perf_counter()-rollout
            meta=rec.finish(3210,resumed['prior_samples'],dict(worlds=512,rollout_action_noise_std=0.,training_action_noise_std=.05))
        with np.load(d/'replay.npz') as z:
            pose=torch.tensor(z['pose'][1:],device='cuda:0');ref=torch.tensor(z['reference_pose'][1:],device='cuda:0')
            vel=torch.tensor(z['world_velocities'][1:],device='cuda:0')
            computed=errors(pose[:,:,:3],pose[:,:,3:],vel[:,:,:3],vel[:,:,3:6],ref[:,:,:3],ref[:,:,3:],vel[:,:,6:9],vel[:,:,9:12])
            torch.testing.assert_close(computed*env._loss_weights,torch.tensor(z['loss_terms'][1:],device='cuda:0'),atol=2e-6,rtol=2e-5)
            torch.testing.assert_close(ref[:,0,:2],pose[:,0,:2])
            assert meta['reward_from_loss']=='exp_negative_sum' and len(meta['loss_term_names'])==4
        output='absolute-balanced-smoke' if calibration else 'absolute-smoke'
        (ROOT/(output+'-replay.npz')).write_bytes((d/'replay.npz').read_bytes())
        report=dict(passed=True,worlds=512,finite_ticks=305,optimizer_steps=0,resumed=resumed,
            max_linear_derivative_error_m_s=linear_error,max_angular_derivative_error_rad_s=angular_error,
            exact_recorded_target_and_four_losses=True,xy_translation_invariant=True,pelvis_height_and_world_heading_penalized=True,
            quaternion_sign_invariant=True,rollout_seconds=elapsed,elapsed_seconds=time.perf_counter()-begun,
            replay_seconds=meta['duration_seconds'],sample_loss=env.take_completed_losses())
        if calibration:
            contributions=[calibration['baseline_means'][k]*env.loss_weights[k] for k in env.loss_term_names]
            assert max(abs(x-calibration['target_contribution']) for x in contributions)<1e-7, contributions
            report['equal_initial_contributions']=contributions
            report['fixed_weights']=env.loss_weights
            assert abs(sum(contributions)-sum(calibration['baseline_means'].values()))<2e-5
        (ROOT/(output+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
