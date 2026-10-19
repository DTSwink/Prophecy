"""Disposable same-checkpoint L4 attribution; never writes learned weights."""
import os, sys, json, time, argparse
from pathlib import Path
from collections import defaultdict
os.environ.setdefault('PYGLET_HEADLESS', 'true')
os.environ.setdefault('OMP_NUM_THREADS', '1')
ROOT = Path('/workspace/mimickit_trial')
sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'MimicKitTransfer'), str(ROOT/'MimicKit/mimickit')]
import torch, numpy as np, warp as wp, yaml
from recovery_omni import RecoveryOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from util import mp_util
from learning.base_agent import AgentMode

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['current','random_start','vanilla'])
    parser.add_argument('--run',required=True)
    parser.add_argument('--checkpoint',required=True)
    a=parser.parse_args()
    output=ROOT/'speed-audit-20261018';output.mkdir(exist_ok=True)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6792)
    folder=ROOT/'runs'/a.run
    cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    os.chdir(ROOT/'MimicKit')
    if a.mode=='random_start':cfg['idle_recovery']['start_at_frame_zero']=False
    if a.mode=='vanilla':
        from engines.newton_engine import NewtonEngine
        from torque_envelope import apply_torque_envelope
        class VanillaEngine(NewtonEngine):
            def _build_solver(self):
                apply_torque_envelope(self._sim_model,ec['uefn_motor_torque_caps_nm'])
                self._sim_model.joint_armature.zero_()
                super()._build_solver()
        RecoveryOmniEnv._build_engine=lambda self,*args,**kwargs:VanillaEngine(*args,**kwargs)
        cfg.pop('velocity_command_margin',None)
    torch.manual_seed(761);np.random.seed(761)
    env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
    if a.mode=='vanilla':
        bounds=torch.tensor(json.loads((output/'current-bounds.json').read_text()),device='cuda:0')
        env._action_bound_high.copy_(bounds);env._action_bound_low.copy_(-bounds)
        env._action_space.high[:]=bounds.cpu().numpy();env._action_space.low[:]=-bounds.cpu().numpy()
    else:(output/'current-bounds.json').write_text(json.dumps(env._action_bound_high.cpu().tolist()))
    agent=OmniPPOAgent(ac,env,'cuda:0');restore(agent,Path(a.checkpoint))
    agent._init_train();agent.set_mode(AgentMode.TRAIN)
    torch.manual_seed(761);np.random.seed(761)
    agent._curr_obs,agent._curr_info=agent._reset_envs()
    times=[];episodes=[]
    for i in range(5):
        torch.cuda.synchronize();start=time.perf_counter()
        result=agent._train_iter();torch.cuda.synchronize()
        times.append(time.perf_counter()-start);episodes.append(float(result['mean_ep_len']))
    ranges=defaultdict(lambda:dict(seconds=0.,calls=0));originals=[]
    def wrap(obj,name,label):
        old=getattr(obj,name);originals.append((obj,name,old))
        def call(*args,**kwargs):
            torch.cuda.synchronize();t=time.perf_counter();value=old(*args,**kwargs);torch.cuda.synchronize()
            ranges[label]['seconds']+=time.perf_counter()-t;ranges[label]['calls']+=1
            return value
        setattr(obj,name,call)
    for name in ['_rollout_train','_build_train_data','_update_actor','_update_critic','_update_normalizers','_decide_action','_reset_done_envs']:
        wrap(agent,name,name)
    wrap(env._engine,'step','physics');wrap(env,'_post_physics_step','observations_reward_done')
    wrap(env,'reset','resets')
    agent._train_iter()
    for obj,name,old in reversed(originals):setattr(obj,name,old)
    engine=env._engine
    counters={}
    if hasattr(engine,'transfer_contact'):
        p=engine.transfer_contact.p
        before={k:getattr(p,k).numpy().copy() for k in ['fallback_count','fallback_steps']}
    aggregate=defaultdict(float)
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as prof:
        for _ in range(4):wp.capture_launch(engine._graph)
        torch.cuda.synchronize()
    for event in prof.events():
        if str(event.device_type).endswith('CUDA'):aggregate[event.name]+=event.device_time_total/1000/4
    if hasattr(engine,'transfer_contact'):
        counters={k:int((getattr(p,k).numpy()-v).sum()) for k,v in before.items()}
        counters['contacts_mean']=float(p.ncontact.numpy().mean())
        counters['limits_mean']=float(p.nlimit.numpy().mean())
        counters['error_worlds']=int(np.count_nonzero(engine.transfer_contact.error.numpy()))
    report=dict(mode=a.mode,checkpoint=Path(a.checkpoint).name,worlds=512,policy_steps_per_update=agent._steps_per_iter,
        times=times,steady_median=float(np.median(times[2:])),episode_ticks=episodes,ranges=dict(ranges),
        physics_kernel_ms=sorted(aggregate.items(),key=lambda x:-x[1])[:35],counters=counters,
        note='Same checkpoint, body, timestep, network/PPO and seed. Vanilla uses upstream Newton/MJWarp constraints and motors, preserving zero armature and torque caps. Trajectories differ. Nested synchronized ranges overlap and add instrumentation overhead.')
    (output/(a.mode+'.json')).write_text(json.dumps(report,indent=2))
    print('AUDIT_RESULT '+json.dumps(report),flush=True)

if __name__=='__main__':main()
