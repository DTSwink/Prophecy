"""Instrument exact local physics, with frozen-policy and zero-command controls."""
import json,numpy as np,torch,warp as wp,mujoco

@wp.kernel
def record(q:wp.array2d(dtype=float),out:wp.array3d(dtype=float),counter:wp.array(dtype=int)):
 w,k=wp.tid()
 if counter[0]<out.shape[0]:out[counter[0],w,k]=q[w,k]

@wp.kernel
def increment(counter:wp.array(dtype=int)):
 counter[0]+=1

def run(env,agent,out):
 engine=env._engine;s=engine._solver;d=s.mjw_data
 counter=wp.zeros(1,dtype=int,device=engine._device)
 before=wp.zeros((48,*d.qpos.shape),dtype=float,device=engine._device)
 after=wp.zeros_like(before)
 torques=wp.zeros((48,*engine._uefn_motors.torque.shape),dtype=float,device=engine._device)
 projection=engine.transfer_projection;apply=projection.apply;advance=s._mujoco_warp_step
 def projected(*a,**kw):
  wp.launch(record,dim=d.qpos.shape,inputs=[d.qpos,before,counter])
  return apply(*a,**kw)
 projection.apply=projected
 def step():
  advance()
  wp.launch(record,dim=d.qpos.shape,inputs=[d.qpos,after,counter])
  wp.launch(record,dim=engine._uefn_motors.torque.shape,inputs=[engine._uefn_motors.torque,torques,counter])
  wp.launch(increment,dim=1,inputs=[counter])
 s._mujoco_warp_step=step;engine._build_graphs()
 caps=engine._uefn_motors.upper.numpy();summaries={}
 for mode in ('policy','zero_command'):
  torch.manual_seed(57);np.random.seed(57);obs,info=env.reset();counter.zero_();ticks=[]
  for _ in range(6):
   with torch.no_grad():
    action,_=agent._decide_action(obs,info)
    if mode=='zero_command':action.zero_()
    obs,reward,done,info=env.step(action)
    ticks.append(dict(reward=reward.cpu().tolist(),done=done.cpu().tolist(),distance=env.target_distances_sq.sqrt().cpu().tolist()))
  a,b,t=before.numpy(),after.numpy(),torques.numpy()
  np.savez_compressed(out/(mode+'-physics.npz'),before_projection=a,after_projection=b,torque=t)
  rows=[];md=mujoco.MjData(s.mj_model)
  for w in (0,8,16,24,32,40,48,56):
   delta=[]
   for tick in range(48):
    md.qpos[:]=a[tick,w];mujoco.mj_kinematics(s.mj_model,md);p=md.xpos.copy()
    md.qpos[:]=b[tick,w];mujoco.mj_kinematics(s.mj_model,md)
    delta.append(np.linalg.norm(md.xpos-p,axis=1))
   delta=np.array(delta);ratios=abs(t[:,w])/caps
   rows.append(dict(world=w,projection_max_body_shift_m=float(delta.max()),projection_body=s.mj_model.body(int(np.unravel_index(delta.argmax(),delta.shape)[1])).name,
    max_torque_ratio=float(ratios.max()),saturated_axis_substeps=int((ratios>=.999).sum()),total_axis_substeps=int(ratios.size),
    first_failure_tick=next((i+1 for i,x in enumerate(ticks) if x['done'][w]==1),None),
    final_distance_m=max(ticks[-1]['distance'][w])))
  summaries[mode]=rows;print(mode,json.dumps(rows),flush=True)
 (out/'corrections.json').write_text(json.dumps(summaries,indent=2))
