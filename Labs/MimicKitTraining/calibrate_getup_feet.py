"""Bounded GPU calibration; frozen policy, real physics, no learner updates."""
import os,sys,json,time,zipfile,hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
SIDE=ROOT/'foot-calibration'
os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(SIDE/'pipeline'),str(SIDE/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv,getup_foot_costs
from omni_policy import OmniPPOAgent
from resume import restore

torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
torch.manual_seed(20261022);torch.cuda.manual_seed_all(20261022)
os.chdir(SIDE/'MimicKit')
cp=ROOT/'resume.zip'
with zipfile.ZipFile(cp) as z:ac=yaml.safe_load(z.read('agent_config.yaml'))
cfg=yaml.safe_load((SIDE/'prepared/env_config.yaml').read_text())
ec=yaml.safe_load((SIDE/'prepared/engine_config.yaml').read_text())
env=PerturbedOmniEnv(cfg,ec,256,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0');restored=restore(agent,cp)
agent.eval();agent.set_mode(AgentMode.TRAIN)
started=time.time();totals=torch.zeros(3,device='cuda:0');count=0
counts={'normal':int((~env._perturbed_rows).sum()),'ordinary':int((env._perturbed_getup&~env._perturbed_plus).sum()),'plus':int(env._perturbed_plus.sum())}
with torch.no_grad():
    obs,info=env.reset()
    for tick in range(192):
        action,_=agent._decide_action(obs,info)
        obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        mask=env._perturbed_getup
        base=env.loss_terms[:,:-2].sum(-1)
        raw=env.loss_terms[:,-2:]
        assert (raw[~mask]==0).all()
        # Independently reconstruct the requested command cost from the action.
        command=action.clamp(env._action_bound_low,env._action_bound_high)[:,env._foot_command_ids]
        torch.testing.assert_close(raw[mask,0],command[mask].square().mean(-1))
        expected=1.-env.loss_terms.sum(-1)
        expected=expected-(done==1)*cfg['perturbed_motion']['getup_failure_penalty']
        expected=expected+(done==2)*cfg['perturbed_motion']['getup_success_value']*cfg['perturbed_motion']['getup_success_discount']
        torch.testing.assert_close(reward[mask],expected[mask],atol=2e-5,rtol=2e-5)
        totals+=torch.cat((base[:,None],raw),-1)[mask].sum(0);count+=int(mask.sum())
        reset_ids=torch.where(done!=0)[0]
        if len(reset_ids):obs,info=env.reset(reset_ids)
    means=(totals/count).cpu().tolist()
    assert all(x>0 for x in means)
    weights=[.07/.86*means[0]/raw for raw in means[1:]]
    weighted=[w*v for w,v in zip(weights,means[1:])]
    fractions=[v/(means[0]+sum(weighted)) for v in weighted]
    assert all(abs(x-.07)<1e-8 for x in fractions)
    # Check actual weighted runtime and normal-row masking after calibration.
    env._foot_cost_weights.copy_(torch.tensor(weights,device='cuda:0'))
    for _ in range(4):
        action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
        raw=env._foot_regularizer_raw(env._engine.get_body_rot(env._get_char_id()))
        torch.testing.assert_close(env.loss_terms[mask,-2:],raw[mask]*env._foot_cost_weights)
        assert (env.loss_terms[~mask,-2:]==0).all()
        expected=1.-env.loss_terms.sum(-1)-(done==1)*100.+(done==2)*99.
        torch.testing.assert_close(reward[mask],expected[mask],atol=2e-5,rtol=2e-5)
        reset_ids=torch.where(done!=0)[0]
        if len(reset_ids):obs,info=env.reset(reset_ids)
report=dict(checkpoint_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),restored=restored,
    worlds=256,ticks=192,cohorts=counts,samples=count,means=dict(existing_pose_plus_ae=means[0],velocity_raw=means[1],rotation_raw=means[2]),
    velocity_weight=weights[0],rotation_weight=weights[1],fractions=fractions,
    calibration='Frozen resumed policy with existing exploration noise; real native MJ physics; perturbed and perturbed+ only; terminal rewards excluded',
    fixed_weights=True,elapsed_seconds=time.time()-started,foot_body_ids=env._foot_cost_ids,
    calf_body_ids=env._foot_calf_ids,command_dof_ids=env._foot_command_ids,
    actual_command_mapping_and_reward_verified=True)
(ROOT/'getup-foot-calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
