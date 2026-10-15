"""Disposable single-update probe; never modifies the live trainer/checkpoints."""
import os,sys,json,argparse
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true';os.environ['OMP_NUM_THREADS']='1'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,yaml
import run as upstream
from recovery_pose import RecoveryPoseEnv
from resume import restore
p=argparse.ArgumentParser();p.add_argument('iteration',type=int);a=p.parse_args()
torch.set_num_threads(1);torch.set_num_interop_threads(1);os.chdir(root/'MimicKit')
run=root/'runs'/json.loads((root/'sweep.json').read_text())['trials'][1]['name']
args=upstream.load_args(['train','--env_config',str(run/'env_config.yaml'),'--engine_config',str(run/'engine_config.yaml'),
    '--agent_config',str(run/'agent_config.yaml'),'--rand_seed','9017','--visualize','false','--logger','tb'])
upstream.mp_util.init(0,1,'cuda:0',6741);upstream.set_rand_seed(args)
env=RecoveryPoseEnv(yaml.safe_load((run/'env_config.yaml').read_text()),yaml.safe_load((run/'engine_config.yaml').read_text()),128,'cuda:0',False)
agent=upstream.build_agent(args,env,'cuda:0')
restore(agent,run/f'checkpoint_{a.iteration:07d}.zip');agent._init_train();agent._curr_obs,agent._curr_info=env.reset()
stages={};original_model=agent._update_model;original_norm=agent._update_normalizers
def sample():
    with torch.no_grad():return agent._model.eval_actor(agent._obs_norm.normalize(agent._exp_buffer.get_data_flat('obs'))).mode.clone()
def model():
    stages['before']=sample();result=original_model();stages['after_optimizer']=sample();return result
def norm():
    result=original_norm();stages['after_normalizer']=sample();return result
agent._update_model=model;agent._update_normalizers=norm
result=agent._train_iter()
report=dict(checkpoint=a.iteration,scope='one copied optimizer update on fresh physical episodes, not live-update trace',
    clip_fraction=float(result['clip_frac']),sigma=.005)
for label,first,last in [('optimizer','before','after_optimizer'),('normalizer','after_optimizer','after_normalizer')]:
    delta=stages[last]-stages[first]
    report[label]=dict(mean_action_shift_rms=float(delta.square().mean().sqrt()),
        gaussian_kl_mean=float((delta.square().sum(-1)/(2*.005**2)).mean()))
out=root/'regression_diagnosis';(out/f'update_probe_{a.iteration}.json').write_text(json.dumps(report,indent=2))
print('UPDATE_PROBE',json.dumps(report),flush=True)
