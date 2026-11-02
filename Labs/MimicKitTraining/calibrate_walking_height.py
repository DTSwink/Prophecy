"""Bounded frozen-policy calibration on the stopped locomotion GPU."""
import os,sys,json,zipfile,hashlib,time
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from envs.base_env import EnvMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore,migrate_physical_observation_scales
from walking_airborne import foot_box_bottoms

torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6795)
torch.manual_seed(20261022);torch.cuda.manual_seed_all(20261022)
os.chdir(ROOT/'MimicKit');checkpoint=ROOT/'resume.zip'
with zipfile.ZipFile(checkpoint) as z:ac=yaml.safe_load(z.read('agent_config.yaml'))
cfg=yaml.safe_load((ROOT/'prepared/env_config.yaml').read_text());ec=yaml.safe_load((ROOT/'prepared/engine_config.yaml').read_text())
reference=json.loads((ROOT/'walking-height-reference.json').read_text())
env=PerturbedOmniEnv(cfg,ec,256,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
restored=restore(agent,checkpoint);migrate_physical_observation_scales(agent)
agent.eval();agent.set_mode(AgentMode.TRAIN);env.set_mode(EnvMode.TRAIN)
limits=torch.tensor([reference['motions'].get(Path(env._motion_lib.get_motion_file(i)).stem,{}).get('max_height_m',0.) for i in range(env._motion_lib.get_num_motions())],device='cuda:0')
total=torch.zeros(3,device='cuda:0');count=0;start=time.time()
columns=[i for i,n in enumerate(env.loss_term_names) if n!='auto_phase']
with torch.no_grad():
 obs,info=env.reset()
 for tick in range(256):
  action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
  char=env._get_char_id();ids=env._walking_foot_ids
  bottoms=foot_box_bottoms(env._engine.get_body_pos(char)[:,ids],env._engine.get_body_rot(char)[:,ids],env._walking_foot_centers,env._walking_foot_half_axes)
  walking=(env._gaits[env._motion_ids]==0)&~env._recovery_rows
  raw=(bottoms.amax(-1)-limits[env._motion_ids]).clamp_min(0).square()*walking
  if tick>=32:
   total+=torch.stack((env.loss_terms[:,columns].sum(),raw.sum(),(raw>0).sum()))
   count+=256
  reset=torch.where(done!=0)[0]
  if len(reset):obs,info=env.reset(reset)
 base,raw,exceeded=(total/count).cpu().tolist()
 assert base>0 and raw>0 and torch.isfinite(total).all()
 weight=.02*base/raw
report=dict(checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),restored=restored,worlds=256,ticks=256,warmup_ticks=32,samples=count,
 existing_loss_mean=base,raw_height_excess_mean=raw,exceedance_fraction=exceeded,weight=weight,weighted_mean=weight*raw,
 fraction_of_existing_loss=.02,elapsed_seconds=time.time()-start,
 method='Frozen latest policy, current exploration, actual native MuJoCo; full-batch physical loss including existing airborne term; terminal adjustments excluded; fixed weight')
(ROOT/'walking-height-calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
