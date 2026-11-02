"""Bounded standalone parity/timing probe using the current native model."""
import json,time,traceback
from pathlib import Path
import numpy as np
import torch,warp as wp,mujoco,mujoco_warp as mjw
from sparse_actuator_probe import SparseActuators
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'

def main():
    torch.set_num_threads(1);wp.init();wp.set_device('cuda:0')
    mm=mujoco.MjModel.from_binary_path(str(OUT/'native-model.mjb'))
    cpu=mujoco.MjData(mm);mujoco.mj_forward(mm,cpu)
    m=mjw.put_model(mm);d=mjw.put_data(mm,cpu,nworld=2048,nconmax=150,njmax=450)
    sp=SparseActuators(mm,m,d);q=wp.to_torch(d.qvel);vel=wp.zeros((d.nworld,m.nu),dtype=float)
    v1=wp.zeros_like(d.actuator_velocity);v2=wp.zeros_like(v1)
    y1=wp.zeros_like(d.qM);y2=wp.zeros_like(y1)
    def original():
        wp.launch_tiled(sp.old_velocity,dim=(d.nworld,m.nu),inputs=[d.qvel,d.actuator_moment],outputs=[v1],block_dim=m.block_dim.actuator_velocity)
        wp.launch(sp.old_derivative,dim=(d.nworld,m.qM_fullm_i.size),inputs=[m.nu,d.actuator_moment,vel,m.qM_fullm_i,m.qM_fullm_j],outputs=[y1])
    def optimized():sp.velocity(v2);sp.deriv(vel,y2)
    checks=[]
    for i in range(8):
        # Different orientations do not change JOINT-transmission support.
        pos=wp.to_torch(d.qpos)
        for j,kind in enumerate(mm.jnt_type):
            start=int(mm.jnt_qposadr[j]);width=7 if kind==mujoco.mjtJoint.mjJNT_FREE else 4 if kind==mujoco.mjtJoint.mjJNT_BALL else 1
            if width>1:
                start+=3 if width==7 else 0
                quat=torch.randn((2048,4),device='cuda');pos[:,start:start+4]=quat/quat.norm(dim=1,keepdim=True)
        mjw.kinematics(m,d);mjw.com_pos(m,d);mjw.transmission(m,d)
        moment=wp.to_torch(d.actuator_moment)
        support=torch.zeros_like(moment,dtype=torch.bool)
        support[:,torch.arange(m.nu),torch.as_tensor(sp.mapping)]=True
        assert torch.count_nonzero(moment[~support])==0
        q.normal_(0,10**(i%4-1));wp.to_torch(vel).normal_(0,100)
        wp.to_torch(vel)[:,i::3]=0
        original();optimized();wp.synchronize()
        check=dict(trial=i,velocity_equal=torch.equal(wp.to_torch(v1),wp.to_torch(v2)),derivative_equal=torch.equal(wp.to_torch(y1),wp.to_torch(y2)),velocity_max=float((wp.to_torch(v1)-wp.to_torch(v2)).abs().max()),derivative_max=float((wp.to_torch(y1)-wp.to_torch(y2)).abs().max()))
        checks.append(check);(OUT/'sparse-actuator-checks.json').write_text(json.dumps(checks,indent=2))
        assert check['velocity_equal'] and check['derivative_equal'],check
    graphs=[]
    for call in [original,optimized]:
        with wp.ScopedCapture() as cap:
            for _ in range(32):call()
        graphs.append(cap.graph)
    times=[]
    for mode in [0,1,1,0]*3:
        wp.capture_launch(graphs[mode]);wp.synchronize();start=time.perf_counter()
        for _ in range(10):wp.capture_launch(graphs[mode])
        wp.synchronize();times.append(dict(optimized=bool(mode),seconds_per_pair=(time.perf_counter()-start)/320))
    result=dict(checks=checks,timings=times,worlds=d.nworld,nu=m.nu,nv=m.nv)
    (OUT/'sparse-actuator-complete.json').write_text(json.dumps(result,indent=2));print('RESULT'+json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'sparse-actuator-failure.txt').write_text(traceback.format_exc());raise
