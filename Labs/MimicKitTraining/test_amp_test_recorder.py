import tempfile,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np,torch
from test_amp_cohort_recorder import Env
from observe import AMPTestCohortRecorder
with tempfile.TemporaryDirectory() as directory:
 env=Env();env._disc_obs_buf=torch.zeros(2,3);calls=[]
 def score(obs):calls.append(len(obs));return obs[:,0]
 agent=SimpleNamespace(_disc_obs_norm=SimpleNamespace(normalize=lambda v:v),_calc_disc_rewards=score,
                       _task_reward_weight=0.,_disc_reward_weight=1.)
 recorder=AMPTestCohortRecorder(env,directory,agent,lambda:0)
 env.reset();env.step(None)
 assert all(r.count==0 for r in recorder.rows),'Training must not be captured'
 env.reset();recorder.start()
 for tick in range(4):
  env._disc_obs_buf[:,0]=torch.tensor([tick+1,(tick+1)*10])
  if tick==0:env._done_buf[1]=1
  if tick==3:env._done_buf[0]=3
  env.step(None)
  if tick==0:env.reset(torch.tensor([1]))
 assert recorder.ready
 recorder.finish(10,100,dict(training_action_noise_std=.05))
 assert calls==[4,1],'Only the two recorded episode batches are scored'
 with np.load(Path(directory)/'replay.npz') as z:
  m=json.loads(str(z['metadata']))
  for r in m['replay_rows']:
   assert r['mode']=='deterministic evaluation' and r['rollout_action_noise_std']==0 and r['training_action_noise_std']==.05
  np.testing.assert_equal(z['data'][:,2],[0,1,2,3,4])
  np.testing.assert_equal(z['data_1'][:,2],[0,10])
 recorder.suspend();env.reset();env.step(None)
 assert all(not r.enabled and not r.pending for r in recorder.rows)
print('PASS: test-only two-row capture, early terminals, zero replay noise metadata, exact discriminator scoring, training isolation')

# A floor-only experiment must not fabricate an upright row or index an empty cohort.
with tempfile.TemporaryDirectory() as directory:
 env=Env();env._upright_cohort[:]=False;env._disc_obs_buf=torch.zeros(2,3)
 recorder=AMPTestCohortRecorder(env,directory,agent,lambda:0)
 assert len(recorder.rows)==1 and recorder.rows[0].world==0
 env.reset();recorder.start();env._done_buf[0]=3;env.step(None);env.reset(torch.tensor([0]))
 result=recorder.finish(0,0,dict(training_action_noise_std=.05))
 assert len(result['replay_rows'])==1 and result['cohort']=='floor'
print('PASS: floor-only recorder has no fabricated upright row')
