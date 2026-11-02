"""Check the staged production path, including mode changes and invalid velocities."""
import json,os,sys,traceback,copy
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024/cached48-deployment'
sys.path[:0]=[str(OUT/'candidate/pipeline'),str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from kl_guard import Snapshot
from lossless_runtime import install,REWARD_BUFFERS

def reward_buffers(e):
    return [getattr(e,n) for n in REWARD_BUFFERS]+[getattr(e._prior,n) for n in ['positions','rotations','valid']]
def save(e):return [v.clone() for v in reward_buffers(e)]
def put(e,values):
    for a,b in zip(reward_buffers(e),values):a.copy_(b)
def equal(a,b):
    if isinstance(a,torch.Tensor):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6849)
    cfg=yaml.safe_load((ROOT/'prepared/env_config.yaml').read_text())
    ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ['engine','agent']]
    e=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs();a._train_iter()
    old_reward=e._update_reward
    old_loss={k:getattr(a,'_compute_'+k+'_loss') for k in ['actor','critic']}
    old_step={k:getattr(a,'_'+k+'_optimizer').step for k in ['actor','critic']}
    installed=install(a,e);checks=[]
    assert installed['cached_cholesky_blocks'] and installed['cached_cholesky_intercepts']==16
    for mode in [AgentMode.TRAIN,AgentMode.TEST,AgentMode.TRAIN]:
        a.set_mode(mode)
        for tick in [1,29,30,31,45,60,80,130,150]:
            a._curr_obs,a._curr_info=a._reset_envs();e._time_buf.fill_(tick/30)
            previous=save(e);e._dispatch_no_getups=False;old_reward();expected=save(e);put(e,previous)
            e._dispatch_no_getups=True;e._update_reward();actual=save(e);put(e,previous)
            assert equal(expected,actual),(mode,tick)
            checks.append(dict(mode=str(mode),tick=tick,all_buffers_exact=True))
    optimizer_checks=[]
    for kind,size in [('actor',512),('critic',256)]:
        o=getattr(a,'_'+kind+'_optimizer');batch=a._exp_buffer.sample(size);snap=Snapshot(o)
        info=old_loss[kind](batch);expected_loss={k:v.detach().clone() for k,v in info.items()};old_step[kind](info[kind+'_loss'])
        expected=([p.detach().clone() for p in o._param_list],copy.deepcopy(o._optimizer.state_dict()))
        snap.restore();actual_loss=getattr(a,'_compute_'+kind+'_loss')(batch)
        assert equal(expected_loss,actual_loss)
        o.step(actual_loss[kind+'_loss']);actual=([p.detach() for p in o._param_list],o._optimizer.state_dict())
        assert equal(expected,actual),kind
        optimizer_checks.append(dict(kind=kind,loss_weights_optimizer_exact=True));snap.restore()
    sp,_=e._engine._dispatch_resources;d=sp.d;m=sp.m
    original_qvel=wp.to_torch(d.qvel).clone();left=wp.zeros_like(d.actuator_velocity);right=wp.zeros_like(left);invalid_checks=[]
    for bad in [float('nan'),float('inf'),-float('inf')]:
        for columns in [[0],[6],[6,7]]:
            wp.to_torch(d.qvel).copy_(original_qvel);wp.to_torch(d.qvel)[:,columns]=bad
            wp.launch_tiled(sp.old_velocity,dim=(d.nworld,m.nu),inputs=[d.qvel,d.actuator_moment],outputs=[left],block_dim=m.block_dim.actuator_velocity)
            sp.velocity(right);wp.synchronize()
            torch.testing.assert_close(wp.to_torch(left),wp.to_torch(right),rtol=0,atol=0,equal_nan=True)
            invalid_checks.append(dict(value=str(bad),columns=columns,classification_exact=True))
    wp.to_torch(d.qvel).copy_(original_qvel)
    a._curr_obs,a._curr_info=a._reset_envs()
    for _ in range(3):a._train_iter()
    a.set_mode(AgentMode.TEST);a._curr_obs,a._curr_info=a._reset_envs()
    with torch.no_grad():
        for _ in range(160):
            action,_=a._decide_action(a._curr_obs,a._curr_info);obs,reward,done,info=a._step_env(action)
            assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
            a._curr_obs,a._curr_info=a._reset_done_envs(done)
    result=dict(installed=installed,reward_checks=checks,optimizer_checks=optimizer_checks,nonfinite_checks=invalid_checks,training_updates=3,evaluation_ticks=160,checkpoint=b)
    (OUT/'preflight-complete.json').write_text(json.dumps(result,indent=2));print('Runtime preflight passed',flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'preflight-failure.txt').write_text(traceback.format_exc());raise
