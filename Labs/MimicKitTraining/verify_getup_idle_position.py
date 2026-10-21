"""Bounded isolated integration check; never changes the running trainer."""
import sys,json,hashlib,time
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
STAGE=ROOT/'idle-position-check'
sys.path[:0]=[str(STAGE/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore,migrate_physical_observation_scales
from omni_policy import OmniPPOAgent

torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6798)
cfg,ec,ac=[yaml.safe_load((STAGE/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
run=ROOT/'runs/20261019_170826_uefn_perturbed_headadd_512'
backup=json.loads((run/'backup_status.json').read_text())
cp=run/Path(backup['key']).name
assert hashlib.sha256(cp.read_bytes()).hexdigest()==backup['sha256']
env=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0');restored=restore(agent,cp);agent._init_train()
agent.eval();agent.set_mode(AgentMode.TEST)
torch.manual_seed(491);torch.cuda.manual_seed_all(491)
obs,info=agent._reset_envs();oldstd=agent._obs_norm._std.clone()
oldnorm=agent._obs_norm.normalize(obs)
raw=(obs-agent._obs_norm._mean)/oldstd
# Inputs inside the original clipping interval must preserve actor/critic maps.
synthetic=agent._obs_norm._mean+torch.randn_like(obs).clamp(-3,3)*oldstd
with torch.no_grad():
    before=[getattr(agent._model,'_'+name+'_layers')(agent._obs_norm.normalize(synthetic)) for name in ('actor','critic')]
report=migrate_physical_observation_scales(agent)
with torch.no_grad():
    after=[getattr(agent._model,'_'+name+'_layers')(agent._obs_norm.normalize(synthetic)) for name in ('actor','critic')]
errors=[float((a-b).abs().max()) for a,b in zip(before,after)]
for a,b in zip(before,after):torch.testing.assert_close(a,b,atol=2e-4,rtol=2e-4)
newraw=(obs-agent._obs_norm._mean)/agent._obs_norm._std
rows=env._perturbed_getup
clipping=dict(before=int((raw[rows,:146].abs()>10).sum()),after=int((newraw[rows,:146].abs()>10).sum()),max_after=float(newraw[rows,:146].abs().max()))
assert clipping['after']==0,clipping
assert torch.equal(oldstd[146:],agent._obs_norm._std[146:])
assert migrate_physical_observation_scales(agent)['changed_channels']==0
height=agent._obs_norm._mean.repeat(2,1);height[:,0]=torch.tensor([.2,.5],device='cuda')
encoded=agent._obs_norm.normalize(height)[:,0]
assert encoded[0]!=encoded[1] and (encoded.abs()<10).all()
term_max=0.;position_error=0.;target_error=0.;normal_rows_unchanged=True
with torch.no_grad():
    for tick in range(64):
        action,_=agent._decide_action(obs,info)
        obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        actual=env._engine.get_body_pos(0)
        source=env._idle_frame0_pos[env._motion_ids]
        shift=actual[:,:1]-source[:,:1];shift=shift*torch.tensor([1.,1.,0.],device='cuda')
        expected=source+shift
        target_error=max(target_error,float((env.reward_target_pos[rows]-expected[rows]).abs().max()))
        expected_loss=(actual[rows]-expected[rows]).square().mean((1,2))*env._getup_position_weight
        position_error=max(position_error,float((expected_loss-env.loss_terms[rows,0]).abs().max()))
        term_max=max(term_max,float(env.loss_terms[rows,1:].abs().max()))
        torch.testing.assert_close(reward[rows],1/(1+expected_loss),atol=2e-6,rtol=2e-6)
        assert not (done[rows]==1).any()
        normal=~rows
        assert torch.equal(env.reward_target_rot[normal],env._ref_body_rot[normal])
        assert torch.equal(env.reward_target_rot[rows],env._idle_frame0_rot[env._motion_ids[rows]])
        ids=torch.where(done!=0)[0]
        if len(ids):obs,info=agent._reset_envs(ids)
    assert term_max==0 and target_error<1e-6 and position_error<1e-6
    # Probe only this isolated environment: emulate a head crossing the threshold.
    pos=env._engine.get_body_pos(0);saved=pos[:,env._head_id,2].clone()
    pos[rows,env._head_id,2]=env._head_reset_height[env._motion_ids[rows]]+.01
    env._time_buf[rows]=1.;env._update_done()
    assert (env._done_buf[rows]==3).all(),env._done_buf[rows]
    pos[:,env._head_id,2]=saved
agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
updates=[]
for i in range(8):
    agent._iter=i;result=agent._train_iter()
    updates.append({k:float(result[k]) for k in ['actor_loss','critic_loss','policy_kl','policy_kl_proposed','actor_learning_rate','actor_steps_accepted','actor_steps_rejected']})
    print(json.dumps(updates[-1]),flush=True)
    if len(updates)>=2 and all(u['actor_steps_accepted']>0 for u in updates[-2:]):break
assert all(torch.isfinite(p).all() for p in agent.parameters())
result=dict(checkpoint=backup,restored=restored,normalization=report,
    affine_hidden_max_error=errors,initial_getup_clipping=clipping,
    pelvis_height_20cm_50cm_inputs=encoded.cpu().tolist(),
    other_getup_terms_max=term_max,position_loss_max_error=position_error,target_max_error=target_error,
    head_reset_flag=3,normal_target_rotations_preserved=True,ppo_updates=updates,
    passed=sum(u['actor_steps_accepted']>0 for u in updates)>=2)
(STAGE/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('normalization','checkpoint','restored')}),flush=True)
