"""One-shot checkpoint evaluation and fixed height-band weight calibration."""
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
from world_pose import WorldPoseEnv,height_band_mse
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
    assert config['worst_body'] and 'height_band_weights' not in config
    config['height_band_weights']=[1.,1.]
    torch.set_num_threads(1);torch.manual_seed(20261014)
    upstream.mp_util.init(0,1,'cuda:0',6741)
    register_network();os.chdir(ROOT/'MimicKit')
    # Boundary and outside-band tests; high AND low excursions must be penalized.
    h=torch.tensor([.7,.8,.9,1.,1.1,1.2],device='cuda:0')
    torch.testing.assert_close(height_band_mse(h,torch.ones_like(h)),
        torch.tensor([.01,0,0,0,0,.01],device='cuda:0'),atol=1e-7,rtol=0)
    env=WorldPoseEnv(config,engine_config,512,'cuda:0',False)
    agent=PPOAgent(agent_config,env,'cuda:0');agent.load_state_dict(model)
    agent.eval();agent.set_mode(AgentMode.TEST)
    targets=env._target_positions[0,env._height_body_ids,2]
    assert torch.all(targets>0)
    batch_means=[];backs=[]
    with torch.no_grad():
        for batch in range(4):
            obs,info=env.reset();assert obs.shape==(512,140)
            backs.append(int(env._starts_on_back.sum()))
            sums=torch.zeros((512,3),device='cuda:0')
            for tick in range(60):
                action,_=agent._decide_action(obs,info)
                obs,reward,done,info=env.step(action)
                assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
                assert (done==(3 if tick==59 else 0)).all()
                torch.testing.assert_close(reward,-env.loss_terms.sum(-1))
                sums+=env.loss_terms
            measured=env.take_completed_losses()
            means=sums.mean(0)
            for i,key in enumerate(env.loss_term_names):assert abs(measured[key]-float(means[i]))<1e-6
            batch_means.append(means.cpu().tolist())
    means=np.mean(batch_means,axis=0)
    assert np.isfinite(means).all() and (means>0).all(), 'Cannot scale a zero/nonfinite calibration loss'
    weights=.25*means[0]/means[1:]
    assert np.isfinite(weights).all() and (weights>0).all()
    np.testing.assert_allclose(weights*means[1:]/means[0],[.25,.25],rtol=1e-12)
    env.height_band_weights=weights.tolist()
    env._height_weights.copy_(torch.as_tensor(weights,device='cuda:0',dtype=torch.float32))
    env.loss_weights=dict(zip(env.loss_term_names,[1.,*weights.tolist()]))
    # Exercise weighted training reward and actual replay recording end to end.
    with tempfile.TemporaryDirectory() as tmp,torch.no_grad():
        obs,info=env.reset();rec=Recorder(env,tmp);rec.start()
        for tick in range(60):
            action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
            pos=env._engine.get_body_pos(env._get_char_id())[:,env._height_body_ids,2]
            independent=(torch.maximum(.8*targets-pos,pos-1.1*targets).clamp_min(0).square()
                *env._height_weights/60)
            torch.testing.assert_close(env.loss_terms[:,1:],independent)
            torch.testing.assert_close(reward,-env.loss_terms.sum(-1))
        rec.finish(0,0,dict(training_action_noise_std=.05,rollout_action_noise_std=0.))
        replay=convert(Path(tmp)/'replay.npz',geometry(Path(config['char_file'])),'height-band-test')
        values=replay['metadata']['evaluation']['frame_losses']
        assert set(values)==set((*env.loss_term_names,'total'))
        np.testing.assert_allclose(values['total'],np.sum([values[n] for n in env.loss_term_names],axis=0),atol=1e-7)
        assert len(replay['positions'][0])==61
    report=dict(validated=True,checkpoint=receipt,generated_unix=time.time(),
        target_pose=config['target_pose'],target_heights=targets.cpu().tolist(),
        fractions=[.8,1.1],calibration_mode='deterministic actor, unchanged noisy floor resets',
        worlds=512,batches=4,episodes=2048,ticks_per_episode=60,back_counts=backs,
        raw_loss_names=list(env.loss_term_names),batch_means=batch_means,raw_means=means.tolist(),
        weights=weights.tolist(),relative_contributions=[.25,.25],
        tests=dict(band_boundaries=True,both_sides=True,inputs_unchanged=True,
            weighted_reward_accounting=True,per_tick_replay=True,finite=True))
    destination.write_text(json.dumps(report,indent=2));print('HEIGHT_BANDS_PASS',json.dumps(report),flush=True)


if __name__=='__main__':main()
