"""Bounded local physics check for reciprocal reward and frame-zero resets."""
from diagnose_floor_guard_speed import *
import zipfile
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(57)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796)
out=ROOT/'Saved/MimicKitEquipment'
cfg,ec,ac=[yaml.safe_load((out/'recovery-preflight'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
with zipfile.ZipFile(out/'getup-cleaning-latest.zip') as z:remote=yaml.safe_load(z.read('env_config.yaml'))
cfg['idle_row_fraction']=remote['idle_row_fraction'];cfg['target_radius_m']=remote['target_radius_m']
for k,v in remote['idle_recovery'].items():
 if k not in ('motion_file','reset_motion_file'):cfg['idle_recovery'][k]=v
cfg['tracking_reward_form']='reciprocal_sum';cfg['idle_recovery']['start_at_frame_zero']=True
os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
env=RecoveryOmniEnv(cfg,ec,64,'cuda:0',False)
assert env._recovery_sphere_only and env._reset_after_getup and not env._absolute_recovery
clips=[]
for repeat in range(3):
 obs,info=env.reset()
 assert bool((env._recovery_start==0).all()) and bool((env._recovery_start_frame==0).all())
 torch.testing.assert_close(env._feedback_phase,torch.tensor([1.,0.],device='cuda:0').expand(64,-1))
 clips+=env._recovery_motion.cpu().tolist()
 for tick in range(8):
  obs,reward,done,info=env.step(torch.zeros((64,34),device='cuda:0'))
  torch.testing.assert_close(reward,1/(1+env.loss_terms.sum(-1)))
  assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
assert set(clips)=={0,1}
report=dict(passed=True,worlds=64,resets=3,ticks_each=8,start_frame=0,reward_form=env._reward_form,front_count=clips.count(0),back_count=clips.count(1),min_reward=float(reward.min()))
(out/'reciprocal-smoke.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
