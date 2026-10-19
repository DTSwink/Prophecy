"""Frozen-checkpoint local audit. No cloud or training mutation."""
from diagnose_floor_guard_speed import *
import types,zipfile,math
from omni_policy import circular_phase
from omni_walk import centre_distances

torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(57)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796)
OUT=ROOT/'Saved/MimicKitEquipment/getup-start-audit';OUT.mkdir(exist_ok=True)
cp=ROOT/'Saved/MimicKitEquipment/getup-diagnosis-checkpoint.zip'
folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
with zipfile.ZipFile(cp) as z:
 remote=yaml.safe_load(z.read('env_config.yaml'));ac=yaml.safe_load(z.read('agent_config.yaml'))
cfg['idle_row_fraction']=remote['idle_row_fraction'];cfg['target_radius_m']=remote['target_radius_m']
for k,v in remote['idle_recovery'].items():
 if k not in ('motion_file','reset_motion_file'):cfg['idle_recovery'][k]=v
os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
env=RecoveryOmniEnv(cfg,ec,64,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0');receipt=restore(agent,cp)
agent.eval();agent.set_mode(AgentMode.TEST)
ids=torch.arange(64,device='cuda:0');clips=(ids%32)//16;fractions=(ids%16).float()/16
original_reset=env._reset_ref_motion
def fixed_reset(self,which):
 original_reset(which)
 self._recovery_motion[which]=clips[which]
 count=self._recovery_lib._motion_num_frames[clips[which]]
 frames=torch.floor(fractions[which]*(count-1)).long()
 self._recovery_start_frame[which]=frames
 self._recovery_start[which]=frames*self._recovery_lib.get_motion_length(clips[which])/(count-1)
 phase=circular_phase(self._recovery_start[which]/self._recovery_lib.get_motion_length(clips[which]))
 self._feedback_phase[which]=phase;self._pending_phase[which]=phase
 self._replace_recovery_reference()
 self._ref_dof_pos[which]=self._motion_lib.joint_rot_to_dof(self._ref_joint_rot[which])
env._reset_ref_motion=types.MethodType(fixed_reset,env)
motor=env._engine._uefn_motors;caps=wp.to_torch(motor.upper);gains=wp.to_torch(motor.gains)
names=env._kin_char_model.get_body_names()
def axis_names():
 result=[]
 for i in range(1,len(names)):
  j=env._kin_char_model.get_joint(i);n=j.get_dof_size() if hasattr(j,'get_dof_size') else None
  # Name from the actual generalized-velocity mapping, avoiding guessed ordering.
  indices=torch.where(env._velocity_mapping[:,(i-1)*3:i*3].abs().sum(-1)>0)[0]
  for a in range(len(indices)):result.append(names[i]+(':'+str(a) if len(indices)>1 else ''))
 return result
axis=axis_names()
peaks=env._recovery_lib._frame_dof_vel.abs().amax(0)
bounds=env._action_bound_high
report=dict(checkpoint=receipt,names=names,axes=axis,clips=[env._recovery_lib.get_motion_file(i) for i in range(2)],
 reference_velocity_peak=peaks.cpu().tolist(),command_bounds=bounds.cpu().tolist(),caps=caps.cpu().tolist(),gains=gains.cpu().tolist(),
 missing_command_headroom=torch.clamp((peaks+caps/gains)*1.05-bounds,min=0).cpu().tolist(),loss_weights=env.loss_weights,modes={})
if '--corrections' in sys.argv:
 from diagnose_getup_corrections import run
 run(env,agent,OUT)
 raise SystemExit
for mode in ['policy_phase','clock_phase']:
 torch.manual_seed(57);np.random.seed(57)
 obs,info=env.reset();initial_pos=env._engine.get_body_pos(0).clone()
 env._update_reward();env._update_done()
 initial=dict(loss=env.loss_terms.cpu().tolist(),distances=env.target_distances_sq.sqrt().cpu().tolist())
 steps=[]
 for tick in range(46):
  with torch.no_grad():
   action,_=agent._decide_action(obs,info)
   if mode=='clock_phase':env.queue_phase_prediction(env.next_phase_target())
   prediction=env._pending_phase.clone()
   obs,reward,done,info=env.step(action)
   phase_err=torch.atan2(prediction[:,1],prediction[:,0])/(2*math.pi)-(env._time_buf+env._recovery_start)/env._recovery_lib.get_motion_length(clips)
   phase_err=torch.remainder(phase_err+.5,1)-.5
   steps.append(dict(reward=reward.cpu().tolist(),done=done.cpu().tolist(),loss=env.loss_terms.cpu().tolist(),dist=env.target_distances_sq.sqrt().cpu().tolist(),
    phase_err=phase_err.cpu().tolist(),action=action.cpu().tolist(),torque_ratio=(wp.to_torch(motor.torque).abs()/caps).cpu().tolist(),
    pelvis_z=env._engine.get_body_pos(0)[:,0,2].cpu().tolist()))
 data=dict(initial=initial,steps=steps,start=env._recovery_start.cpu().tolist(),clip=clips.cpu().tolist(),fraction=fractions.cpu().tolist(),
  duration=env._recovery_lib.get_motion_length(clips).cpu().tolist(),equipment=env._equipment[env._motion_ids].cpu().tolist())
 (OUT/(mode+'.json')).write_text(json.dumps(data))
 rows=[]
 for w in range(64):
  duration=data['duration'][w]-data['start'][w];required=round(duration*30)
  fail=next((t for t,x in enumerate(steps[:required]) if x['done'][w]==1),None)
  observed=steps[:min(required,(fail+1 if fail is not None else required))]
  rows.append(dict(world=w,clip=int(clips[w]),fraction=float(fractions[w]),equipment=data['equipment'][w],
    start=data['start'][w],required_seconds=duration,survived_seconds=(fail+1)/30 if fail is not None else duration,completed=fail is None,
    failing_body=['head','right_hand','left_hand','right_foot','left_foot'][int(np.argmax(observed[-1]['dist'][w]))] if fail is not None else None,
    reward_mean=float(np.mean([s['reward'][w] for s in observed])),reward_below_1e_4=float(np.mean([s['reward'][w]<1e-4 for s in observed])),
    loss_mean=np.mean([s['loss'][w] for s in observed],axis=0).tolist(),
    peak_phase_error=float(max(abs(s['phase_err'][w]) for s in observed)),
    saturation=np.mean([np.asarray(s['torque_ratio'][w])>.98 for s in observed],axis=0).tolist(),
    initial_max_distance=max(initial['distances'][w]),initial_losses=initial['loss'][w]))
 report['modes'][mode]=rows
 (OUT/'report.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(dict(mode=mode,completed=sum(r['completed'] for r in rows),early_completed=sum(r['completed'] for r in rows if r['fraction']<.25),late_completed=sum(r['completed'] for r in rows if r['fraction']>=.75))),flush=True)
print('Audit complete',flush=True)
