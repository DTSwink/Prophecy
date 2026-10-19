"""Bounded real-engine GPU smoke before resuming the user's checkpoint."""
import os,sys,json,time
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
import torch,numpy as np,warp as wp,yaml,mujoco
from recovery_omni import RecoveryOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from util import mp_util
from learning.base_agent import AgentMode

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6792)
    os.chdir(ROOT/'MimicKit')
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    env=RecoveryOmniEnv(cfg,ec,32,'cuda:0',False)
    engine=env._engine;assert not hasattr(engine,'transfer_contact')
    assert not getattr(engine._solver.mjw_model,'uefn_compound_limits',None)
    agent=OmniPPOAgent(ac,env,'cuda:0');receipt=restore(agent,ROOT/'resume.zip')
    agent._init_train();agent.set_mode(AgentMode.TEST)
    obs,info=env.reset();assert bool((env._recovery_start_frame==0).all())
    assert env._reset_after_getup and env._recovery_sphere_only and not env._absolute_recovery
    m=engine._solver.mj_model;d=mujoco.MjData(m)
    names=engine.get_obj_body_names(0)
    ids=[next(i for i in range(1,m.nbody) if m.body(i).name.endswith(name)) for name in names]
    peak=0.;episodes=0
    for tick in range(24):
        with torch.no_grad():action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        torch.testing.assert_close(reward,1/(1+env.loss_terms.sum(-1)))
        if tick in (0,7,23):
            d.qpos[:]=engine._solver.mjw_data.qpos.numpy()[0]
            mujoco.mj_kinematics(m,d)
            actual=engine.get_body_pos(0)[0].cpu().numpy()
            error=float(abs(actual-d.xpos[ids]).max());peak=max(peak,error)
            if error>2e-5:raise ValueError('Native/Newton body coordinate mismatch '+str(error))
        reset=torch.nonzero(done,as_tuple=False).flatten();episodes+=len(reset)
        obs,info=env.reset(reset)
    # One real PPO update validates gradients and auto-phase with the new backend.
    agent._curr_obs,agent._curr_info=env.reset()
    started=time.perf_counter();result=agent._train_iter();torch.cuda.synchronize()
    assert all(torch.isfinite(p).all() for p in agent.parameters())
    assert np.isfinite(result['mean_return'])
    report=dict(passed=True,worlds=32,ticks=24,episodes=episodes,restored=receipt,
                max_body_mapping_error_m=peak,smoke_update_seconds=time.perf_counter()-started,
                engine=engine.native_profile_report,torch_peak_memory_bytes=torch.cuda.max_memory_allocated(),
                discarded_optimizer_update=True)
    (ROOT/'native-preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
