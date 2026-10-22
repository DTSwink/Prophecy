"""Bounded frozen-policy calibration and axis/reward checks for pelvis speed."""
import os,sys,json,time,zipfile,hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');SIDE=ROOT/'pelvis-calibration'
os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(SIDE/'pipeline'),str(SIDE/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util,torch_util as q
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv,getup_pelvis_horizontal_cost
from omni_policy import OmniPPOAgent
from resume import restore

torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
torch.manual_seed(20261022);torch.cuda.manual_seed_all(20261022)
os.chdir(SIDE/'MimicKit');cp=ROOT/'resume.zip'
with zipfile.ZipFile(cp) as z:ac=yaml.safe_load(z.read('agent_config.yaml'))
cfg=yaml.safe_load((SIDE/'prepared/env_config.yaml').read_text());ec=yaml.safe_load((SIDE/'prepared/engine_config.yaml').read_text())
env=PerturbedOmniEnv(cfg,ec,256,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0');restored=restore(agent,cp)
agent.eval();agent.set_mode(AgentMode.TRAIN)
started=time.time();totals=torch.zeros(2,device='cuda:0');count=0;exceeded=0
counts={'normal':int((~env._perturbed_rows).sum()),'ordinary':int((env._perturbed_getup&~env._perturbed_plus).sum()),'plus':int(env._perturbed_plus.sum())}
# Pure vertical speed, negative/positive vertical variation, both horizontal axes,
# below/exactly/above threshold. Vertical motion must never contribute.
v=torch.tensor([[0,0,100],[.6,.8,0],[.6,.8,-100],[2,0,0],[0,-2,100]],device='cuda:0')
torch.testing.assert_close(getup_pelvis_horizontal_cost(v,torch.tensor(1.,device='cuda:0')),torch.tensor([0.,0.,0.,1.,1.],device='cuda:0'))
with torch.no_grad():
    obs,info=env.reset()
    for tick in range(192):
        action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        mask=env._perturbed_getup;base=env.loss_terms[:,:-1].sum(-1);raw=env.loss_terms[:,-1]
        assert (raw[~mask]==0).all()
        char=env._get_char_id();rot=env._engine.get_body_rot(char)[:,0];ang=env._engine.get_body_ang_vel(char)[:,0]
        origin=env._engine.get_body_vel(char)[:,0]-torch.cross(ang,q.quat_rotate(rot,env._body_com[:,0]),dim=-1)
        speed=(origin[:,0].square()+origin[:,1].square()).sqrt()
        expected_raw=(speed-env._pelvis_horizontal_limits[env._recovery_motion]).clamp_min(0).square()
        torch.testing.assert_close(raw[mask],expected_raw[mask])
        # Deliberately enormous changed Z must leave cost bit-for-bit identical.
        changed=origin.clone();changed[:,2]=1000.
        torch.testing.assert_close(getup_pelvis_horizontal_cost(changed,env._pelvis_horizontal_limits[env._recovery_motion]),expected_raw)
        expected=1.-env.loss_terms.sum(-1)-(done==1)*100.+(done==2)*99.
        torch.testing.assert_close(reward[mask],expected[mask],atol=3e-5,rtol=3e-5)
        totals+=torch.stack((base,raw),-1)[mask].sum(0);count+=int(mask.sum());exceeded+=int((raw[mask]>0).sum())
        ids=torch.where(done!=0)[0]
        if len(ids):obs,info=env.reset(ids)
    means=(totals/count).cpu().tolist();assert all(x>0 for x in means)
    weight=.07/.93*means[0]/means[1];fraction=weight*means[1]/(means[0]+weight*means[1]);assert abs(fraction-.07)<1e-8
    env._pelvis_horizontal_weight=weight
    for _ in range(4):
        action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
        assert (env.loss_terms[~mask,-1]==0).all()
        expected=1.-env.loss_terms.sum(-1)-(done==1)*100.+(done==2)*99.
        torch.testing.assert_close(reward[mask],expected[mask],atol=3e-5,rtol=3e-5)
        ids=torch.where(done!=0)[0]
        if len(ids):obs,info=env.reset(ids)
report=dict(checkpoint_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),restored=restored,worlds=256,ticks=192,cohorts=counts,samples=count,
    means=dict(existing_loss=means[0],pelvis_excess_raw=means[1]),weight=weight,fraction=fraction,exceedance_fraction=exceeded/count,
    calibration='Frozen latest policy with existing exploration; real native MJ physics; perturbed and perturbed+ only; terminal rewards excluded',
    fixed_weight=True,elapsed_seconds=time.time()-started,gravity=env._engine.get_gravity().tolist(),
    reference=cfg['perturbed_motion']['getup_pelvis_horizontal_regularizer']['motions'],axis_and_reward_verified=True)
(ROOT/'getup-pelvis-calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
