"""Contained corrected-MJ trace and native counterfactuals. No UE or training writes."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
for k in list(os.environ):
 if k.startswith('TRANSFER_'): del os.environ[k]
import probe
import json,time,numpy as np,torch,warp as wp,mujoco
from scipy.spatial.transform import Rotation as R
from native_probe import Native,actor,observation,names,keys,offsets
from coupled_velocity_motors import CoupledVelocityMotors
OUT=probe.OUT/'causal_transfer';OUT.mkdir(exist_ok=True)

def main():
 env,agent=probe.setup();e=env._engine;s=e._solver;m=s.mj_model;d=s.mjw_data
 motor=CoupledVelocityMotors(s.mjw_model,d,m);motor.install()
 env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.zeros(n))
 obs,info=env.reset();states=[];reported=[];actions=[];observations=[];targets=[];subin=[];subout=[];forces=[]
 model=dict(timestep=s.mjw_model.opt.timestep.numpy().tolist(),cone=int(m.opt.cone),iterations=m.opt.iterations,
  geom_names=[m.geom(i).name for i in range(m.ngeom)],geom_condim=m.geom_condim.tolist(),geom_friction=m.geom_friction.tolist(),
  geom_solref=m.geom_solref.tolist(),geom_solimp=m.geom_solimp.tolist(),mass=m.body_mass.tolist())
 (OUT/'model.json').write_text(json.dumps(model,indent=2),encoding='utf-8')
 original=s._mujoco_warp_step
 def capture():
  subin.append(probe.physical_state(env));forces.append(d.xfrc_applied.numpy()[0].copy())
  original();subout.append(probe.physical_state(env))
 s._mujoco_warp_step=capture
 try:
  for tick in range(32):
   observations.append(obs[0].numpy().copy())
   with torch.no_grad():a,_=agent._decide_action(obs,info)
   actions.append(a[0].numpy().copy());obs,_,flag,info=env.step(a)
   states.append(probe.physical_state(env));reported.append(probe.state(env))
   targets.append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1)[0].numpy())
   assert not flag[0]
   if tick%8==0:print('MJ tick',tick+1,flush=True)
 finally:s._mujoco_warp_step=original;motor.restore()
 np.savez_compressed(OUT/'reference.npz',states=states,reported=reported,actions=actions,obs=observations,targets=targets,subin=subin,subout=subout,forces=forces)
 states=np.array(states);actions=np.array(actions);observations=np.array(observations);targets=np.array(targets)
 run_native()

def run_native(contacts=False):
 data=np.load(OUT/'reference.npz')
 states=data['states'];actions=data['actions'];observations=data['obs'];targets=data['targets']
 rows=[]
 cases=[('closed',(),True),('open',(),False),('closed_no_drag',('NO_DRAG',),True),('open_no_drag',('NO_DRAG',),False),
  ('open_no_limits',('NO_LIMITS',),False),('open_training_contact',('TRAINING_CONTACT',),False),('open_high_iterations',('HIGH_ITERATIONS',),False)]
 if contacts:
  cases=[('closed_no_spec',('NO_SPECULATIVE',),True),('open_no_spec',('NO_SPECULATIVE',),False),('closed_no_spec_training',('NO_SPECULATIVE','TRAINING_CONTACT'),True),('closed_no_spec_high',('NO_SPECULATIVE','HIGH_ITERATIONS'),True)]
 for mode,flags,feedback in cases:
  for k in list(os.environ):
   if k.startswith('TRANSFER_'):del os.environ[k]
  for f in flags:os.environ['TRANSFER_'+f]='1'
  n=Native(states[0]);current=np.array(n.initial['bodies']);trace=[current];cmd=[];impulses=[];distance=[];refdistance=[]
  try:
   for tick in range(1,32):
    a=actor(observation(current,observations[tick,-5:])) if feedback else actions[tick]
    result=n.request('step '+' '.join(map(str,a)));current=np.array(result['bodies']);trace.append(current);cmd.append(a);impulses.append(result['ground_vertical_impulse_ns'])
    target=targets[tick].copy();target[:,:2]+=current[0,:2]-target[0,:2]
    actual=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
    desired=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
    distance.append(np.linalg.norm(actual-desired,axis=1))
    ref=states[tick].copy();ref[:,:2]+=current[0,:2]-ref[0,:2]
    refdistance.append(np.linalg.norm(current[:,:3]-ref[:,:3],axis=1))
  finally:n.close()
  distance=np.array(distance);refdistance=np.array(refdistance)
  exceeded=np.flatnonzero(distance.max(1)>.27)
  row=dict(mode=mode,first_failure_tick=int(exceeded[0]+1) if len(exceeded) else None,
   reference_error_cm_at_5_10_15_30=[float(refdistance[t-1].max()*100) for t in [5,10,15,30]],
   target_error_cm_at_5_10_15_30=[float(distance[t-1].max()*100) for t in [5,10,15,30]],
   command_rmse=float(np.sqrt(np.mean((np.array(cmd)-actions[1:32])**2))))
  rows.append(row);print('NATIVE '+json.dumps(row),flush=True)
  np.savez_compressed(OUT/(mode+'.npz'),states=trace,actions=cmd,impulse=impulses,dist=distance,refdist=refdistance)
 (OUT/('summary_no_spec.json' if contacts else 'summary.json')).write_text(json.dumps(rows,indent=2),encoding='utf-8')
 print('COMPLETE',flush=True)

if __name__=='__main__':
 import sys
 run_native('--contacts-only' in sys.argv) if ('--native-only' in sys.argv or '--contacts-only' in sys.argv) else main()
