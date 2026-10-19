"""Bounded Run LR wiring check and fresh-policy loss calibration, no saved learner."""
import os,sys,json,time,random,argparse,hashlib
from pathlib import Path
import numpy as np
import torch,yaml
import warp as wp
ROOT=Path('/workspace/mimickit_trial')
LOCAL=Path(__file__).resolve().parents[2]
if os.name=='nt':
    sys.path[:0]=[str(LOCAL/'Saved/MimicKitUEFN/dependencies')]
    ROOT=LOCAL/'Saved/MimicKitOmni/package'
REPO=(LOCAL/'Saved/MimicKit/vendor/MimicKit') if os.name=='nt' else ROOT/'MimicKit'
sys.path.insert(0,str(REPO/'mimickit'))
from omni_config import configure
from omni_walk import OmniWalkEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util
from observe import Recorder

def main():
    p=argparse.ArgumentParser();p.add_argument('--worlds',type=int,default=512);p.add_argument('--device',default='cuda:0');p.add_argument('--calibrate',action='store_true');p.add_argument('--prepared',type=Path);p.add_argument('--replay-rows',type=int,default=1);a=p.parse_args()
    if a.prepared:a.prepared=a.prepared.resolve()
    os.chdir(REPO);torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device(a.device)
    mp_util.init(0,1,a.device,6741)
    random.seed(20261014);np.random.seed(20261014);torch.manual_seed(20261014)
    if a.device.startswith('cuda'):torch.cuda.manual_seed_all(20261014)
    cfg=yaml.safe_load((REPO/'data/envs/deepmimic_humanoid_env.yaml').read_text())
    ec=yaml.safe_load((REPO/'data/engines/newton_engine.yaml').read_text())
    ac=yaml.safe_load((REPO/'data/agents/deepmimic_humanoid_ppo_agent.yaml').read_text())
    configure(cfg,ec,ac,ROOT)
    if a.prepared:
        cfg,ec,ac=[yaml.safe_load((a.prepared/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    output=(a.prepared/'preflight') if a.prepared else ROOT/'preflight';output.mkdir(exist_ok=True)
    begun=time.perf_counter();env=OmniWalkEnv(cfg,ec,a.worlds,a.device,False)
    agent=OmniPPOAgent(ac,env,a.device);agent._curr_obs,agent._curr_info=agent._reset_envs();agent._init_train()
    if a.prepared:
        assert env.get_obs_space().shape==(154,) and env._motion_lib.get_num_motions()==54
        assert env._idle_rows==max(1,int(a.worlds*.06+.5))
        def check_rows():
            assert torch.all(env._gaits[env._motion_ids[:env._idle_rows]]==-1)
            assert torch.all(env._gaits[env._motion_ids[env._idle_rows:]]!=-1)
        check_rows()
        for ids in (torch.arange(a.worlds-1,-1,-1,device=a.device),torch.arange(0,a.worlds,2,device=a.device)):
            env.reset(ids);check_rows()
        agent._curr_obs,agent._curr_info=agent._reset_envs()
    assert agent._curr_obs.shape==(a.worlds,env.get_obs_space().shape[0])
    assert env.get_action_space().shape==(34,)
    before={k:v.clone() for k,v in agent._model.state_dict().items()}
    agent.eval();agent.set_mode(AgentMode.TRAIN)
    start=time.perf_counter()
    with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
    env._engine.validate_transfer_solver()
    if a.prepared:check_rows()
    if a.device.startswith('cuda'):torch.cuda.synchronize()
    rollout_seconds=time.perf_counter()-start
    for k,v in before.items():torch.testing.assert_close(v,agent._model.state_dict()[k],rtol=0,atol=0)
    losses=env.take_completed_losses();means=np.array([losses[n] for n in env.loss_term_names])
    assert np.isfinite(means).all() and (means>0).all()
    for value in agent._exp_buffer._buffers.values():assert torch.isfinite(value).all()
    if a.calibrate:
        assert a.worlds==512 and a.device.startswith('cuda')
        calibration=dict(initialization='fresh_uefn_runLR_seed20261014',worlds=a.worlds,ticks=agent._steps_per_iter,
            raw_means=dict(zip(env.loss_term_names,means.tolist())),weights=dict(zip(env.loss_term_names,(means.sum()/4/means).tolist())),
            asset_sha256=hashlib.sha256((ROOT/'assets/uefn/humanoid_uefn.xml').read_bytes()).hexdigest(),
            limits_sha256=hashlib.sha256((ROOT/'assets/uefn/limits.json').read_bytes()).hexdigest(),optimizer_steps=0)
        (ROOT/'omni-calibration.json').write_text(json.dumps(calibration,indent=2))
    # Independent disposable optimization verifies phase labels/gradients and finite PPO.
    agent._build_train_data();update=agent._update_model()
    assert all(torch.isfinite(p).all() for p in agent.parameters())
    assert 'phase_prediction_mse' in update
    if a.replay_rows>1:
        from observe_many import MultiRecorder
        recorder=MultiRecorder(env,output,a.replay_rows)
    else:recorder=Recorder(env,output)
    recorder.phase_agent=agent
    agent.test_model(1) # Warm deterministic path; reset done by upstream.
    original=agent._rollout_test
    def record(n):
        recorder.start()
        try:return original(n)
        finally:recorder.enabled=False
    agent._rollout_test=record
    recording_start=time.perf_counter()
    result=agent.test_model(1)
    recording_seconds=time.perf_counter()-recording_start
    replay=recorder.finish(0,0,dict(worlds=a.worlds,training_action_noise_std=ac['model']['action_std'],rollout_action_noise_std=0.))
    assert replay
    report=dict(passed=True,device=a.device,worlds=a.worlds,observations=env.get_obs_space().shape[0],motors=34,phase_outputs=2,
                rollout_seconds=rollout_seconds,transitions_per_second=a.worlds*agent._steps_per_iter/rollout_seconds,
                raw_losses=losses,phase_mse=float(update['phase_prediction_mse']),evaluation=result,
                elapsed_seconds=time.perf_counter()-begun,disposable_optimizer_update=True,production_checkpoint_created=False,
                replay_rows=a.replay_rows,recording_evaluation_seconds=recording_seconds,
                replay_archive_bytes=(output/'replay.npz').stat().st_size)
    (output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
