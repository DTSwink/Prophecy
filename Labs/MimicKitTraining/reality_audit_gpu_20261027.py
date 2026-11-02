"""Bounded isolated checkpoint audit; never attaches to the live trainer."""
import os,sys,json,traceback,zipfile,io,time
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'reality-audit-20261027'
OUT.mkdir(exist_ok=True);sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml,numpy as np,mujoco
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from lossless_runtime import install

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6891)
    torch.manual_seed(20261027)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    e=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    with zipfile.ZipFile(ROOT/'reality-audit-20261027.zip') as z:
        a.load_state_dict(torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True))
        checkpoint=json.loads(z.read('checkpoint.json'))
    a._init_train();a.set_mode(AgentMode.TRAIN);obs,info=a._reset_envs();a._sample_count=10**10
    dispatch=install(a,e);c=e._get_char_id();eng=e._engine;s=eng._solver
    labels=np.where(e._final.minus.cpu(),'idle perturbed-',np.where(e._final.plus.cpu(),'perturbed+',np.where(e._final.pushed.cpu(),'perturbed','normal')))
    selected=[int(np.flatnonzero(labels==k)[0]) for k in np.unique(labels)]
    checks=[];clip=[];actions=[];counts=[];donecounts={};errors=[]
    # A horizontal translation must not affect any of the physical inputs.
    ph=e._graphed_physical_observations;values=tuple(v.clone() for v in ph.inputs());moved=list(values)
    shift=torch.tensor([11.,-7.,0.],device=e._device);moved[0]=values[0]+shift;moved[6]=values[6]+shift
    translation_error=float((ph.calculate(values)-ph.calculate(moved)).abs().max())
    old_obs=obs.clone();e._compute_obs();assert torch.equal(old_obs,obs),'Observation storage alias'
    for tick in range(181):
        eager=e._reference_compute_obs();fast=e._compute_obs();err=float((eager-fast).abs().max())
        if tick in [0,1,59,60,61,79,80,81,129,130,150,180]:
            checks.append(dict(tick=tick,observation_error=err))
            ids=torch.tensor([3,1,0],device=e._device);torch.testing.assert_close(e._compute_obs(ids),fast[ids],atol=2e-6,rtol=2e-6)
        assert err<2e-5,err
        normalized=(fast-a._obs_norm._mean)/a._obs_norm._std;clip.append((normalized.abs()>10).cpu().numpy())
        action,_=a._decide_action(fast,info);actions.append(action.detach().cpu().numpy())
        if tick in [0,60,81,130]:
            # Independent CPU MuJoCo Jacobians use current qpos/qvel, not engine body-velocity buffers.
            eng._sim_state.pre_step_update();s._update_mjc_data(s.mjw_data,eng._sim_model,eng._sim_state.raw_state)
            qpos=wp.to_torch(s.mjw_data.qpos)[selected].cpu().numpy();qvel=wp.to_torch(s.mjw_data.qvel)[selected].cpu().numpy()
            actual=eng.get_body_vel(c)[selected].cpu().numpy();angular=eng.get_body_ang_vel(c)[selected].cpu().numpy()
            names=e._kin_char_model.get_body_names();bodies=[next(b for b in range(1,s.mj_model.nbody) if s.mj_model.body(b).name.endswith(n)) for n in names]
            for k,row in enumerate(selected):
                d=mujoco.MjData(s.mj_model);d.qpos[:]=qpos[k];d.qvel[:]=qvel[k];mujoco.mj_kinematics(s.mj_model,d);mujoco.mj_comPos(s.mj_model,d)
                linear=[];ang=[]
                for b in bodies:
                    jp=np.zeros((3,s.mj_model.nv));jr=np.zeros_like(jp);mujoco.mj_jacBodyCom(s.mj_model,d,jp,jr,b)
                    linear.append(jp@d.qvel);ang.append(jr@d.qvel)
                errors.append(dict(tick=tick,cohort=str(labels[row]),linear_error=float(np.max(np.abs(actual[k]-linear))),angular_error=float(np.max(np.abs(angular[k]-ang)))))
        before=fast.clone();nxt,reward,done,info=e.step(action)
        assert torch.equal(fast,before),'Step overwrote policy input storage'
        assert torch.isfinite(nxt).all() and torch.isfinite(reward).all()
        # Actual actuator command must match clamped actions in the same 34-DOF order.
        command=eng._controls.target_vel[c];expected=action.clamp(e._action_bound_low,e._action_bound_high)
        assert torch.equal(command,expected),'Action mapping differs'
        ids=torch.where(done!=0)[0]
        for flag in [1,2,3]:donecounts[str(flag)]=donecounts.get(str(flag),0)+int((done==flag).sum())
        if len(ids):e.reset(ids)
        obs=e._compute_obs()
    clips=np.stack(clip);acts=np.stack(actions);lo=e._action_bound_low.cpu().numpy();hi=e._action_bound_high.cpu().numpy()
    report=dict(checkpoint=checkpoint,worlds=128,ticks=181,frames=int(clips.shape[0]*clips.shape[1]),dispatch=dispatch,
        graph_checks=checks,velocity_jacobian_checks=errors,translation_error=translation_error,
        observation_storage_independent=True,action_mapping_exact=True,action_low=lo.tolist(),action_high=hi.tolist(),
        action_clipped_fraction=float(((acts<lo)|(acts>hi)).mean()),normalizer_count=a._obs_norm._count.cpu().tolist(),
        clip_per_channel=clips.mean((0,1)).tolist(),cohorts={str(k):dict(worlds=int((labels==k).sum()),clipped_fraction=float(clips[:,labels==k].mean()),any_clipped_frame_fraction=float(clips[:,labels==k].any(-1).mean())) for k in np.unique(labels)},donecounts=donecounts)
    (OUT/'complete.json').write_text(json.dumps(report,indent=2));print('AUDIT COMPLETE',flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'failure.txt').write_text(traceback.format_exc());raise
