"""Bounded real-physics crawl wiring and PPO smoke test; no production learner."""
import os
os.environ['PYGLET_HEADLESS']='true'
from pathlib import Path
import sys,json,time,random,argparse
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitCrawl'
PACKAGE=OUT/'package'
sys.path[:0]=[str(PACKAGE/'pipeline'),str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(PACKAGE/'MimicKit/mimickit')]
import numpy as np
import torch,yaml,warp as wp
from crawl_env import CrawlEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util
from observe_many import MultiRecorder

def main():
    from current_phat import verify_current_phat, sha
    meta=verify_current_phat(PACKAGE/'assets/uefn')
    parser=argparse.ArgumentParser();parser.add_argument('--worlds',type=int,default=16);args=parser.parse_args()
    os.chdir(PACKAGE/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6742)
    random.seed(20261014);np.random.seed(20261014);torch.manual_seed(20261014);torch.cuda.manual_seed_all(20261014)
    cfg,ec,ac=[yaml.safe_load((OUT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    output=OUT/'preflight';output.mkdir(exist_ok=True);start=time.time()
    env=CrawlEnv(cfg,ec,args.worlds,'cuda:0',False)
    agent=OmniPPOAgent(ac,env,'cuda:0');agent._curr_obs,agent._curr_info=agent._reset_envs();agent._init_train()
    assert env.get_obs_space().shape==(153,) and env.get_action_space().shape==(34,)
    assert env._motion_lib.get_num_motions()==2 and torch.all(env._limb_enabled==1)
    assert env._adaptive_rows is None and not env._enable_early_termination and not env._pose_termination
    # Exercise the real termination path after crossing both clip lengths,
    # with the just-reset zero-error physics state still matching its target.
    env._time_buf.fill_(5.)
    env._update_done();assert torch.all(env._done_buf==0), 'Clip end caused a reset'
    head=env._kin_char_model.get_body_names().index('head')
    env.reward_target_pos[:,head,2].add_(.271)
    env._update_done();assert torch.all(env._done_buf==1), '27cm failure stopped working'
    env.reward_target_pos[:,head,2].sub_(.271)
    env._time_buf.fill_(env._episode_length)
    env._update_done();assert torch.all(env._done_buf==3), 'Timeout changed'
    agent._curr_obs,agent._curr_info=agent._reset_envs()
    from util import torch_util as q
    geometry=json.loads((OUT/'geometry.json').read_text())
    positions=env._engine.get_body_pos(env._get_char_id())[:env._idle_rows]
    rotations=q.quat_to_matrix(env._engine.get_body_rot(env._get_char_id())[:env._idle_rows])
    gaps=[]
    for name in ('right_hand','left_hand'):
        j=env._kin_char_model.get_body_names().index(name)
        shape=next(s for s in geometry['shapes'] if s['bone']==name)
        tensor=lambda x:torch.tensor(x,device='cuda:0',dtype=positions.dtype)
        bottom=positions[:,j,2]+(rotations[:,j]@tensor(shape['position']))[:,2]-(rotations[:,j]@tensor(shape['axes']))[:,2,:].abs()@(tensor(shape['dimensions'])/2)
        gaps.append(float(bottom.abs().max()))
    assert max(gaps)<.001, ('Initial hand floor gap',gaps)
    def check():
        assert torch.all(env._gaits[env._motion_ids[:env._idle_rows]]==-1)
        assert torch.all(env._gaits[env._motion_ids[env._idle_rows:]]==0)
        obs=env._compute_obs();torch.testing.assert_close(obs[:,-6:-2],torch.ones_like(obs[:,-6:-2]))
        torch.testing.assert_close(obs[:,-7],env._gaits[env._motion_ids])
        subset=torch.arange(0,args.worlds,2,device='cuda:0')
        torch.testing.assert_close(env._compute_obs(subset),obs[subset])
        assert torch.isfinite(obs).all()
    check()
    for ids in (torch.arange(args.worlds-1,-1,-1,device='cuda:0'),torch.arange(0,args.worlds,2,device='cuda:0')):
        env.reset(ids);check()
    agent._curr_obs,agent._curr_info=agent._reset_envs()
    agent.eval();agent.set_mode(AgentMode.TRAIN)
    before={k:v.clone() for k,v in agent._model.state_dict().items()}
    with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
    try:env._engine.validate_transfer_solver()
    except FloatingPointError:
        stamp=str(int(time.time()))
        env._engine.failure_capture.save(output/('failed-equation-'+stamp+'.npz'))
        raise
    check()
    for k,v in before.items():torch.testing.assert_close(v,agent._model.state_dict()[k],rtol=0,atol=0)
    losses=env.take_completed_losses()
    for value in agent._exp_buffer._buffers.values():assert torch.isfinite(value).all()
    agent._build_train_data();update=agent._update_model()
    assert all(torch.isfinite(p).all() for p in agent.parameters())
    recorder=MultiRecorder(env,output,min(args.worlds,8));recorder.phase_agent=agent
    original=agent._rollout_test
    def record(n):
        recorder.start()
        try:return original(n)
        finally:recorder.enabled=False
    agent._rollout_test=record
    evaluation=agent.test_model(1)
    replay=recorder.finish(0,0,dict(worlds=args.worlds,training_action_noise_std=.05,rollout_action_noise_std=0.))
    from replay import convert
    geometry=json.loads((OUT/'geometry.json').read_text())
    converted=convert(output/'replay.npz',geometry,'crawl_preflight')
    (output/'replay.json').write_text(json.dumps(converted))
    env._engine.validate_transfer_solver()
    problem=env._engine.transfer_contact.p
    active_limits=np.arange(problem.limit_J.shape[1])[None,:]<problem.nlimit.numpy()[:,None]
    locked_count=((problem.limit_bilateral.numpy()==1)&active_limits).sum(-1)
    expected_locked=sum(j['modes'][0]==2 for j in meta['joints'] if j['kind']=='ball')
    np.testing.assert_array_equal(locked_count,expected_locked)
    report=dict(passed=True,worlds=args.worlds,observations=153,motors=34,phase_outputs=2,
        idle_rows=env._idle_rows,limbs_all_enabled=True,direction_and_equipment_inputs=False,ae_reward=False,
        losses=losses,loss_names=env.loss_term_names,evaluation=evaluation,
        phase_mse=float(update['phase_prediction_mse']),elapsed_seconds=time.time()-start,
        current_phat=True,limits_sha256=sha(PACKAGE/'assets/uefn/limits.json'),
        locked_ball_twist_rows_per_world=expected_locked,adaptive_sampling=False,
        only_failure='head/hands/feet collider-target distance >27cm',
        policy_clips=['crawl','crawl_idle'],clip_end_reset=False,
        termination_regression_passed=True,initial_idle_hand_floor_gap_m=gaps,
        disposable_optimizer_update=True,production_learner_saved=False,
        replay_rows=len(replay['replay_rows']))
    (output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
