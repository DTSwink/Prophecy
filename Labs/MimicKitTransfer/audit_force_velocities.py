"""Diagnostic only: substitute measured rigid-body velocities in drag/gyro forces.

No policy observations, rewards, asset or shared training source are changed.
Enable only after the first physics tick so reset caches cannot enter the test.
"""
import json,types,time
import numpy as np
import torch,warp as wp
from scipy.spatial.transform import Rotation
import probe
from engines.newton_engine import NewtonEngine

def main():
    env,agent=probe.setup();e=env._engine;original=e._pre_sim_step
    coeff=e._drag_coeff.numpy();first=e._drag_first.numpy();second=e._drag_second.numpy()
    inertia=e._sim_model.body_inertia.numpy();report=[];errors=[]
    def corrected(self,raw,control):
        NewtonEngine._pre_sim_step(self,raw,control)
        actual=probe.physical_state(env)
        # Detect stale or differently ordered states instead of silently comparing.
        np.testing.assert_allclose(raw.body_q.numpy()[:,:3],actual[:,:3],atol=1e-5)
        reported=raw.body_qd.numpy()
        errors.append(np.max(np.abs(reported-actual[:,7:13]),axis=0).tolist())
        rot=Rotation.from_quat(actual[:,3:7]).as_matrix();v=actual[:,7:10];w=actual[:,10:13]
        moment=np.einsum('bij,bj->bi',rot,first)
        drag=-coeff[:,None]*v-np.cross(w,moment)
        world_second=rot@second@rot.transpose(0,2,1);world_inertia=rot@inertia@rot.transpose(0,2,1)
        torque=-np.cross(moment,v)-np.einsum('bij,bj->bi',world_second,w)+np.cross(w,np.einsum('bij,bj->bi',world_inertia,w))
        raw.body_f.assign(raw.body_f.numpy()+np.concatenate([drag,torque],axis=1).astype('float32'))
    duration=float(env._motion_lib.get_motion_lengths()[0]);start=time.perf_counter()
    for phase in (0.,.25,.5,.75):
        e._pre_sim_step=original
        env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.full((n,),float(phase*duration)))
        obs,info=env.reset();dist=[];flag=None
        for tick in range(60):
            with torch.no_grad():action,_=agent._decide_action(obs,info)
            obs,reward,flag,info=env.step(action)
            dist.append(float(env.target_distances_sq.sqrt().max()))
            e._pre_sim_step=types.MethodType(corrected,e)
            if flag[0]:break
        row=dict(phase=phase,ticks=tick+1,done=int(flag[0]),max_distance_m=max(dist))
        report.append(row);print(json.dumps(row),flush=True)
    result=dict(diagnostic_only=True,changed='drag/gyro force input velocities only',phases=report,
        reported_velocity_max_error_by_channel=np.max(errors,axis=0).tolist(),seconds=time.perf_counter()-start)
    (probe.OUT/'force-velocity-ablation.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
