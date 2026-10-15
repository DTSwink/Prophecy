"""Read-only matched checkpoint/normalizer diagnostic, never updates a policy."""
import os,sys,json,io,zipfile,argparse,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true';os.environ['OMP_NUM_THREADS']='1'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from recovery_pose import RecoveryPoseEnv
from learning.base_agent import AgentMode

p=argparse.ArgumentParser();p.add_argument('--actor',type=int,required=True);p.add_argument('--norm',type=int,required=True);a=p.parse_args()
torch.set_num_threads(1);torch.set_num_interop_threads(1);os.chdir(root/'MimicKit')
run=root/'runs'/json.loads((root/'sweep.json').read_text())['trials'][1]['name']
out=root/'regression_diagnosis';out.mkdir(exist_ok=True)
cfg=yaml.safe_load((run/'env_config.yaml').read_text());engine=yaml.safe_load((run/'engine_config.yaml').read_text())
args=upstream.load_args(['train','--env_config',str(run/'env_config.yaml'),'--engine_config',str(run/'engine_config.yaml'),
    '--agent_config',str(run/'agent_config.yaml'),'--rand_seed','9017','--visualize','false','--logger','tb'])
upstream.mp_util.init(0,1,'cuda:0',6741);upstream.set_rand_seed(args)
env=RecoveryPoseEnv(cfg,engine,128,'cuda:0',False);agent=upstream.build_agent(args,env,'cuda:0')
def load(it):
    with zipfile.ZipFile(run/f'checkpoint_{it:07d}.zip') as z:return torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
model=load(a.actor)
if a.norm!=a.actor:
    normalizer=load(a.norm)
    for key in model:
        if key.startswith('_obs_norm.'):model[key]=normalizer[key]
agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TRAIN)
torch.manual_seed(7719);torch.cuda.manual_seed_all(7719)
obs,info=env.reset();back=env._starts_on_back.clone();initial=env._engine.get_body_pos(env._get_char_id()).clone()
errors=[];positions=[];actions=[];clamped=[];observations=[];means=[];values=[]
with torch.no_grad():
    for step in range(45):
        observations.append(obs.clone())
        norm_obs=agent._obs_norm.normalize(obs)
        means.append(agent._model.eval_actor(norm_obs).mode.clone())
        values.append(agent._model.eval_critic(norm_obs).flatten())
        action,_=agent._decide_action(obs,info);actions.append(action.clone())
        applied=action.clamp(env._action_bound_low,env._action_bound_high)
        clamped.append((applied!=action).float().mean(-1))
        obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        errors.append(env._pose_mse().clone());positions.append(env._engine.get_body_pos(env._get_char_id()).clone())
err=torch.stack(errors);pos=torch.stack(positions);act=torch.stack(actions);clip=torch.stack(clamped);per=err.mean(0)
report=dict(actor_checkpoint=a.actor,normalizer_checkpoint=a.norm,worlds=128,back=int(back.sum()),front=int((~back).sum()),
    mse_mean=float(per.mean()),mse_back=float(per[back].mean()),mse_front=float(per[~back].mean()),
    final_mse=float(err[-1].mean()),action_bound_fraction=float(clip.mean()),raw_action_abs_max=float(act.abs().max()),
    head_peak_mean_m=float(pos[:,:,env._engine.get_obj_body_names(env._get_char_id()).index('head'),2].amax(0).mean()),
    pelvis_peak_mean_m=float(pos[:,:,0,2].amax(0).mean()),noise=.005,seed=7719,finite=True)
stem=f'actor{a.actor}_norm{a.norm}'
(out/(stem+'.json')).write_text(json.dumps(report,indent=2))
np.savez_compressed(out/(stem+'.npz'),mse=err.cpu().numpy(),back=back.cpu().numpy(),initial=initial.cpu().numpy(),
    obs=torch.stack(observations).cpu().numpy(),mean=torch.stack(means).cpu().numpy(),value=torch.stack(values).cpu().numpy())
print('MATCHED_DIAGNOSIS',json.dumps(report),flush=True)
