"""Calibrate one fixed lateral-foot penalty and test its physical/replay accounting."""
import os,sys,io,json,hashlib,zipfile,tempfile,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from amp_standing import register_network
from world_pose import WorldPoseEnv,world_pose_mse,height_band_mse,lateral_foot_separation,feet_lateral_mse
from util import torch_util
from observe import Recorder
from replay import convert,geometry


def main():
    source=Path(sys.argv[1]);destination=Path(sys.argv[2])
    receipt=json.loads((source.parent/'backup_status.json').read_text())
    assert receipt['key'].endswith('/'+source.name)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==receipt['sha256']
    with zipfile.ZipFile(source) as bundle:
        config=yaml.safe_load(bundle.read('env_config.yaml'))
        agent_config=yaml.safe_load(bundle.read('agent_config.yaml'))
        engine_config=yaml.safe_load(bundle.read('engine_config.yaml'))
        model=torch.load(io.BytesIO(bundle.read('model.pt')),map_location='cuda:0',weights_only=True)
    assert config['worst_body'] and 'height_band_weights' in config
    assert not config.get('height_bands_only') and 'feet_lateral_calibration' not in config
    torch.set_num_threads(1);torch.manual_seed(20261015)
    upstream.mp_util.init(0,1,'cuda:0',6741)
    register_network();os.chdir(ROOT/'MimicKit')
    # Unit geometry: exact boundary, lateral excess, crossing, sagittal/vertical
    # separation, and arbitrary whole-body rotation/translation invariance.
    left=torch.tensor([[0,.3,0],[0,.2,0],[9,.2,4],[0,-.3,0]],device='cuda:0')
    right=torch.tensor([[0,-.3,0],[0,-.2,0],[-9,-.2,-4],[0,.3,0]],device='cuda:0')
    q=torch.tensor([[0.,0.,0.,1.]],device='cuda:0').expand(4,-1)
    expected=torch.tensor([.04,0.,0.,.04],device='cuda:0')
    torch.testing.assert_close(feet_lateral_mse(left,right,q,.4),expected,atol=1e-7,rtol=1e-5)
    angles=torch.tensor([[.7,-1.2,2.1]],device='cuda:0').expand(4,-1)
    rotated=torch_util.exp_map_to_quat(angles)
    shift=torch.tensor([4.,-6.,2.],device='cuda:0')
    torch.testing.assert_close(feet_lateral_mse(torch_util.quat_rotate(rotated,left)+shift,
        torch_util.quat_rotate(rotated,right)+shift,rotated,.4),expected,atol=1e-6,rtol=1e-5)
    # Construct unchanged environment first to obtain exact reference FK width.
    env=WorldPoseEnv(config,engine_config,512,'cuda:0',False)
    names=env._engine.get_obj_body_names(env._get_char_id())
    li,ri,pi=[names.index(n) for n in ('left_foot','right_foot','pelvis')]
    width=float(lateral_foot_separation(env._target_positions[:,li],env._target_positions[:,ri],
        env._target_rotations[:,pi])[0]);limit=1.25*width
    assert width>0 and np.isfinite(width)
    agent=PPOAgent(agent_config,env,'cuda:0');agent.load_state_dict(model)
    agent.eval();agent.set_mode(AgentMode.TEST)
    batch_means=[];backs=[];active_ticks=0
    with torch.no_grad():
        for batch in range(4):
            obs,info=env.reset();assert obs.shape==(512,140)
            backs.append(int(env._starts_on_back.sum()))
            sums=torch.zeros((512,2),device='cuda:0')
            for tick in range(60):
                action,_=agent._decide_action(obs,info)
                obs,reward,done,info=env.step(action)
                assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
                assert (done==(3 if tick==59 else 0)).all()
                pos=env._engine.get_body_pos(env._get_char_id())
                rot=env._engine.get_body_rot(env._get_char_id())
                raw=feet_lateral_mse(pos[:,li],pos[:,ri],rot[:,pi],limit)
                sums[:,0]+=env.loss_terms.sum(-1)
                sums[:,1]+=raw/60
                active_ticks+=int((raw>0).sum())
            batch_means.append(sums.mean(0).cpu().tolist())
            env.take_completed_losses()
    means=np.mean(batch_means,axis=0)
    assert np.isfinite(means).all() and (means>0).all(),'Cannot calibrate zero/nonfinite mean loss'
    weight=float(.2*means[0]/means[1])
    report=dict(validated=False,checkpoint=receipt,generated_unix=time.time(),target_pose=config['target_pose'],
        reference_width_m=width,width_multiplier=1.25,max_width_m=limit,weight=weight,
        reference_frame='actual pelvis local Y, including tilt',distance='absolute projection of foot body-origin separation',
        calibration_mode='deterministic actor, unchanged noisy 50/50 floor resets',
        worlds=512,batches=4,episodes=2048,ticks_per_episode=60,back_counts=backs,
        batch_means=batch_means,existing_total_mean=float(means[0]),raw_feet_mean=float(means[1]),
        weighted_feet_mean=float(weight*means[1]),relative_contribution=.2,active_ticks=active_ticks)
    # Rebuild once with the production path, exercising all four loss buffers.
    config['feet_lateral_calibration']=report
    tested=WorldPoseEnv(config,engine_config,512,'cuda:0',False)
    checked=PPOAgent(agent_config,tested,'cuda:0');checked.load_state_dict(model)
    checked.eval();checked.set_mode(AgentMode.TEST)
    assert tested.loss_term_names==('body_pose_mse','head_height_band','pelvis_height_band','feet_lateral')
    with tempfile.TemporaryDirectory() as tmp,torch.no_grad():
        obs,info=tested.reset();assert obs.shape==(512,140)
        rec=Recorder(tested,tmp);rec.start();sums=torch.zeros((512,4),device='cuda:0')
        for tick in range(60):
            action,_=checked._decide_action(obs,info);obs,reward,done,info=tested.step(action)
            pos=tested._engine.get_body_pos(tested._get_char_id());rot=tested._engine.get_body_rot(tested._get_char_id())
            pose=world_pose_mse(pos,rot,tested._target_positions,tested._target_rotations,True).sum(-1)/60
            heights=height_band_mse(pos[:,tested._height_body_ids,2],tested._target_positions[:,tested._height_body_ids,2])*tested._height_weights/60
            # Independently invert the pelvis matrix and read local Y.
            local=torch.matmul(torch_util.quat_to_matrix(rot[:,pi]).transpose(-2,-1),(pos[:,li]-pos[:,ri]).unsqueeze(-1)).squeeze(-1)
            feet=(local[:,1].abs()-limit).clamp_min(0).square()*weight/60
            expected_terms=torch.cat((pose[:,None],heights,feet[:,None]),-1)
            torch.testing.assert_close(tested.loss_terms,expected_terms,atol=1e-6,rtol=1e-5)
            torch.testing.assert_close(reward,-expected_terms.sum(-1))
            assert torch.isfinite(obs).all() and (done==(3 if tick==59 else 0)).all()
            sums+=tested.loss_terms
        measured=tested.take_completed_losses()
        for i,key in enumerate(tested.loss_term_names):assert abs(measured[key]-float(sums[:,i].mean()))<1e-6
        rec.finish(0,0,dict(training_action_noise_std=.05,rollout_action_noise_std=0.))
        replay=convert(Path(tmp)/'replay.npz',geometry(Path(config['char_file'])),'feet-lateral-test')
        values=replay['metadata']['evaluation']['frame_losses']
        assert set(values)==set((*tested.loss_term_names,'total'))
        np.testing.assert_allclose(values['total'],np.sum([values[n] for n in tested.loss_term_names],axis=0),atol=1e-7)
        assert len(replay['positions'][0])==61
    tested.reset(torch.tensor([0],device='cuda:0'))
    assert tested._episode_losses[0].abs().max()==0 and tested._episode_losses[1:].abs().max()>0
    report.update(validated=True,tests=dict(rotation_translation_invariant=True,sagittal_separation_ignored=True,
        boundary=True,crossing=True,inputs_unchanged=True,existing_terms_unchanged=True,
        independent_matrix_reference=True,weighted_reward_accounting=True,per_tick_replay=True,partial_reset=True,finite=True))
    destination.write_text(json.dumps(report,indent=2));print('FEET_LATERAL_PASS',json.dumps(report),flush=True)


if __name__=='__main__':main()
