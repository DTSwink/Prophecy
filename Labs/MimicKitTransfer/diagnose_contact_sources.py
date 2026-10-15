"""Same-state force-source ablation against live-timestep corrected MJ."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import json,numpy as np,torch,warp as wp,mujoco,mujoco_warp as mjw
from scipy.spatial.transform import Rotation as R
import native_probe
from native_probe import Native,names,parents,local
from coupled_velocity_motors import CoupledVelocityMotors
OUT=probe.OUT/'causal_transfer'

def main(friction=False,law=False):
 env,agent=probe.setup();e=env._engine;s=e._solver;m=s.mj_model;wm=s.mjw_model;d=s.mjw_data
 wm.opt.timestep.fill_(1/240)
 motor=CoupledVelocityMotors(wm,d,m);motor.install()
 data=np.load(OUT/'reference.npz');rows=[]
 body_ids=[next(i for i in range(1,m.nbody) if m.body(i).name.endswith(n)) for n in names]
 joints=[int(m.body_jntadr[i]) for i in body_ids]
 def encode(state):
  q=m.qpos0.copy();v=np.zeros(m.nv);rot=R.from_quat(state[:,3:7])
  q[:3]=state[0,:3];q[3:7]=np.roll(state[0,3:7],1)
  v[:3]=state[0,7:10]-np.cross(state[0,10:13],rot[0].apply(m.body_ipos[body_ids[0]]))
  v[3:6]=rot[0].inv().apply(state[0,10:13])
  for i in range(1,15):
   j=joints[i];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j]
   rel=local[i].inv()*rot[parents[i]].inv()*rot[i]
   vel=rot[i].inv().apply(state[i,10:13]-state[parents[i],10:13])
   if m.jnt_type[j]==1:q[qa:qa+4]=np.roll(rel.as_quat(),1);v[va:va+3]=vel
   else:q[qa]=rel.as_rotvec()[2];v[va]=vel[2]
  return q,v
 def err(a,b):
  return dict(position_cm=float(np.linalg.norm(a[:,:3]-b[:,:3],axis=1).max()*100),
   angle_deg=float(np.rad2deg((R.from_quat(a[:,3:7])*R.from_quat(b[:,3:7]).inv()).magnitude()).max()),
   velocity=float(np.linalg.norm(a[:,7:10]-b[:,7:10],axis=1).max()),
   angvel=float(np.linalg.norm(a[:,10:13]-b[:,10:13],axis=1).max()))
 cases=[('complete',(),False),('no_contact',('CONTACT',),False),('no_limit',('LIMIT',),False),('no_contact_limit',('CONTACT','LIMIT'),False),
  ('no_contact_limit_high',('CONTACT','LIMIT','HIGH_ITERATIONS'),False),('complete_high',('HIGH_ITERATIONS',),False),
  ('stationary_contact',('LIMIT','GRAVITY','MOTORS','DRAG'),True),('stationary_free',('LIMIT','GRAVITY','MOTORS','DRAG','CONTACT'),True),
  ('complete_exact_forces',('EXACT_FORCES',),False)]
 if friction:
  native_probe.fixture_path=probe.OUT/'contact-observation.exe'
  cases=[('contact_default',(),False),('contact_training_material',('TRAINING_CONTACT',),False),('contact_zero_friction',('ZERO_FRICTION',),False),('contact_zero_friction_high',('ZERO_FRICTION','HIGH_ITERATIONS'),False),('contact_no_spec',('NO_SPECULATIVE',),False),('contact_no_spec_training',('NO_SPECULATIVE','TRAINING_CONTACT'),False)]
 if law:
  friction=True;native_probe.fixture_path=probe.OUT/'contact-observation.exe'
  cases=[('normal_soft',('ZERO_FRICTION','NO_SPECULATIVE','LIMIT','HIGH_ITERATIONS'),False),('normal_hard',('ZERO_FRICTION','HARD_CONTACT','NO_SPECULATIVE','LIMIT','HIGH_ITERATIONS'),False),('hard_friction',('HARD_CONTACT','NO_SPECULATIVE','LIMIT','HIGH_ITERATIONS','TRAINING_CONTACT'),False),('hard_elliptic',('ELLIPTIC','HARD_CONTACT','NO_SPECULATIVE','LIMIT','HIGH_ITERATIONS','TRAINING_CONTACT'),False)]
 original_solref=wm.geom_solref.numpy().copy();original_solimp=wm.geom_solimp.numpy().copy()
 original_friction=wm.geom_friction.numpy().copy();original_dim=wm.geom_condim.numpy().copy()
 baseflags=wm.opt.disableflags;basecone=wm.opt.cone
 for step in ([8,160] if law else [8,24,48,80,112,160]):
  initial=data['subin'][step].copy();cmd=data['actions'][step//8].clip(-2*np.pi,2*np.pi)
  for label,disabled,zero in cases:
   for k in list(os.environ):
    if k.startswith('TRANSFER_'):del os.environ[k]
   os.environ['TRANSFER_SUBSTEPS']='1'
   for flag in disabled:
    if flag in ('EXACT_FORCES','ZERO_FRICTION','HARD_CONTACT','ELLIPTIC'):continue
    os.environ['TRANSFER_'+{'LIMIT':'NO_LIMITS','HIGH_ITERATIONS':'HIGH_ITERATIONS','TRAINING_CONTACT':'TRAINING_CONTACT','NO_SPECULATIVE':'NO_SPECULATIVE'}.get(flag,'NO_'+flag)]='1'
   wm.geom_friction.assign(original_friction);wm.geom_condim.assign(original_dim)
   if 'ZERO_FRICTION' in disabled:
    os.environ['TRANSFER_FRICTION']='0';os.environ['TRANSFER_RESTITUTION']='0';wm.geom_friction.zero_();wm.geom_condim.fill_(1)
   wm.geom_solref.assign(original_solref);wm.geom_solimp.assign(original_solimp)
   if 'HARD_CONTACT' in disabled:
    sr=original_solref.copy();si=original_solimp.copy();sr[...,0]=0;sr[...,1]=-240;si[...,0:2]=.9999
    wm.geom_solref.assign(sr);wm.geom_solimp.assign(si)
   st=initial.copy()
   if zero:st[:,7:]=0
   q,v=encode(st);d.qpos.assign(q[None].astype('float32'));d.qvel.assign(v[None].astype('float32'));d.qacc_warmstart.zero_()
   reconstructed=probe.physical_state(env);np.testing.assert_allclose(reconstructed,st,atol=2e-5,rtol=1e-5)
   ctrl=np.zeros_like(d.ctrl.numpy());ctrl[0,motor.ids]=cmd;d.ctrl.assign(ctrl)
   wm.opt.disableflags=baseflags;wm.opt.cone=int(mujoco.mjtCone.mjCONE_ELLIPTIC) if 'ELLIPTIC' in disabled else basecone
   for flag in disabled:
    if flag in ('CONTACT','LIMIT','GRAVITY','MOTORS'):wm.opt.disableflags|=int(getattr(mujoco.mjtDisableBit,'mjDSBL_'+('ACTUATION' if flag=='MOTORS' else flag)))
   f=data['forces'][step].copy()
   if zero or 'EXACT_FORCES' in disabled:
    rotation=R.from_quat(st[:,3:7]).as_matrix();vel=st[:,7:10];w=st[:,10:13]
    inertia=e._sim_model.body_inertia.numpy();gyro=np.cross(w,np.einsum('bij,bj->bi',rotation@inertia@rotation.transpose(0,2,1),w))
    force=np.zeros_like(gyro);torque=gyro
    if 'DRAG' not in disabled:
     moment=np.einsum('bij,bj->bi',rotation,e._drag_first.numpy());second=rotation@e._drag_second.numpy()@rotation.transpose(0,2,1)
     force=-e._drag_coeff.numpy()[:,None]*vel-np.cross(w,moment)
     torque=gyro-np.cross(moment,vel)-np.einsum('bij,bj->bi',second,w)
    f[1:]=np.concatenate([force,torque],axis=1)
   d.xfrc_applied.assign(f[None]);d.qfrc_applied.zero_()
   mjw.step(wm,d);actual=probe.physical_state(env)
   native=Native(st)
   np.testing.assert_allclose(native.initial['bodies'],st,atol=2e-5,rtol=1e-5)
   try:result=native.request('step '+' '.join(map(str,cmd)));pred=np.array(result['bodies'])
   finally:native.close()
   assert np.isfinite(actual).all() and np.isfinite(pred).all()
   row=dict(step=step,case=label,error=err(actual,pred),jolt_normal_impulse=sum(result['ground_vertical_impulse_ns']),
    mj_total_contact_impulse=(d.qfrc_constraint.numpy()[0,:3]/240).tolist(),
    mj_change=err(st,actual),jolt_change=err(st,pred))
   row['jolt_momentum_change_z']=float(np.sum(m.body_mass[1:]*(pred[:,9]-st[:,9])))
   row['mj_momentum_change_z']=float(np.sum(m.body_mass[1:]*(actual[:,9]-st[:,9])))
   row['mj_force_gravity_impulse_z']=float((f[1:,2].sum()-9.81*m.body_mass.sum())/240)
   if friction:
    count=int(d.nacon.numpy()[0]);row['jolt_contacts']=result['contacts']
    row['mj_contacts']={k:getattr(d.contact,k).numpy()[:count].tolist() for k in ('dist','pos','geom','dim','friction','solref','solimp')}
   if label=='complete':row['mj_reference_replay_error']=err(actual,data['subout'][step])
   rows.append(row);print(json.dumps(row),flush=True)
   (OUT/('contact_law.json' if law else 'contact_friction.json' if friction else 'same_state.json')).write_text(json.dumps(rows,indent=2),encoding='utf-8')
 (OUT/('contact_law.json' if law else 'contact_friction.json' if friction else 'same_state.json')).write_text(json.dumps(rows,indent=2),encoding='utf-8')
 motor.restore()

if __name__=='__main__':
 import sys
 main('--friction' in sys.argv,'--law' in sys.argv)
