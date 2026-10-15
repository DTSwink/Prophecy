"""Paired CPU full-physics-step timings at an identical captured running state."""
import json,time
import numpy as np
import torch,warp as wp,mujoco_warp as mjw,mujoco
import probe
from coupled_velocity_motors import CoupledVelocityMotors

def main(gpu=False):
    env,agent=probe.setup();s=env._engine._solver;wm=s.mjw_model;d=s.mjw_data
    env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.zeros(n))
    obs,info=env.reset()
    with torch.no_grad():action,_=agent._decide_action(obs,info)
    frozen=[]
    def snapshot(obj):
        for key,value in vars(obj).items():
            if isinstance(value,wp.array):frozen.append((value,wp.clone(value)))
            elif key in ('contact','efc'):snapshot(value)
    original=s._mujoco_warp_step
    def capture():
        if not frozen:snapshot(d)
        original()
    s._mujoco_warp_step=capture
    try:env.step(action)
    finally:s._mujoco_warp_step=original
    motor=CoupledVelocityMotors(wm,d,s.mj_model)
    measurements={'original':[],'coupled':[]};iterations={k:[] for k in measurements}
    try:
        for repeat in range(25):
            for mode in (('original','coupled') if repeat%2==0 else ('coupled','original')):
                motor.restore()
                if mode=='coupled':motor.install()
                for dest,source in frozen:wp.copy(dest,source)
                start=time.perf_counter_ns();mjw.step(wm,d);wp.synchronize_device('cpu')
                elapsed=(time.perf_counter_ns()-start)/1e6
                if repeat>=5:
                    measurements[mode].append(elapsed)
                    iterations[mode].append(int(d.solver_niter.numpy()[0]))
    finally:motor.restore()
    result=dict(device='cpu',worlds=1,scope='full MuJoCo Warp physics step, same captured state and command; excludes state restoration, actor and diagnostics',
        warning='Desktop CPU timings; not a GPU throughput benchmark',
        samples_ms=measurements,solver_iterations=iterations,
        median_ms={k:float(np.median(v)) for k,v in measurements.items()})
    result['median_ratio']=result['median_ms']['coupled']/result['median_ms']['original']
    (probe.OUT/'capped_integrator/cpu_paired_benchmark.json').write_text(json.dumps(result,indent=2))
    print('BENCHMARK '+json.dumps({k:v for k,v in result.items() if k not in ('samples_ms','solver_iterations')}),flush=True)
    if gpu:
        gpu_benchmark(s,env,frozen,motor)

def gpu_benchmark(cpu_solver,env,frozen,cpu_motor):
    """512 identical real states, paired captured graphs; no policy/training."""
    cpu_data=cpu_solver.mjw_data;m=cpu_solver.mj_model
    refs={}
    for mode in ('original','coupled'):
        for dest,source in frozen:wp.copy(dest,source)
        if mode=='coupled':cpu_motor.install()
        try:
            mjw.step(cpu_solver.mjw_model,cpu_data)
            refs[mode]=cpu_data.qvel.numpy()[0].copy()
        finally:cpu_motor.restore()
    for dest,source in frozen:wp.copy(dest,source)
    md=mujoco.MjData(m)
    for field in ('qpos','qvel','ctrl','act','qacc_warmstart','qfrc_applied','xfrc_applied'):
        getattr(md,field)[:]=getattr(cpu_data,field).numpy()[0].reshape(getattr(md,field).shape)
    # State copies below are device-to-device and included equally in timings.
    with wp.ScopedDevice('cuda:0'):
        gm=mjw.put_model(m);gd=mjw.put_data(m,md,nworld=512,nconmax=150,njmax=450)
        # Newton updates the Warp timestep at step(), not its CPU model copy.
        gm.opt.timestep.fill_(float(cpu_solver.mjw_model.opt.timestep.numpy()[0]))
        metadata=json.loads((probe.SOURCE/'assets/uefn/limits.json').read_text())
        gm.uefn_compound_limits=type(cpu_solver.mjw_model.uefn_compound_limits)(m,gm,metadata)
        preserved=[(getattr(gd,k),wp.clone(getattr(gd,k))) for k in ('qpos','qvel','ctrl','act','qacc_warmstart','qfrc_applied','xfrc_applied')]
        gmotor=CoupledVelocityMotors(gm,gd,m)
        def step():
            for dest,source in preserved:wp.copy(dest,source)
            mjw.step(gm,gd)
        graphs={};errors={}
        try:
            for mode in ('original','coupled'):
                if mode=='coupled':gmotor.install()
                step();wp.synchronize()
                error=float(abs(gd.qvel.numpy()-refs[mode]).max());errors[mode]=error
                assert error<0.003,(mode,error)
                with wp.ScopedCapture() as capture:step()
                graphs[mode]=capture.graph
                wp.capture_launch(graphs[mode]);wp.synchronize()
                assert np.isfinite(gd.qvel.numpy()).all()
                np.testing.assert_allclose(gd.qvel.numpy(),np.broadcast_to(refs[mode],(512,m.nv)),atol=0.003,rtol=1e-5)
                gmotor.restore()
            samples={k:[] for k in graphs}
            start=wp.Event(enable_timing=True);end=wp.Event(enable_timing=True)
            for repeat in range(12):
                for mode in (('original','coupled') if repeat%2==0 else ('coupled','original')):
                    wp.record_event(start)
                    for _ in range(10):wp.capture_launch(graphs[mode])
                    wp.record_event(end)
                    elapsed=wp.get_event_elapsed_time(start,end)/10
                    if repeat>=2:samples[mode].append(elapsed)
            result=dict(device=wp.get_device().name,worlds=512,physics_dt=1/240,cuda_graph_replay=True,
                scope='512 copies of the same captured initial RunLR state; physics step plus identical device-state restore, excludes actor/rollout/PPO',
                warning='Local GPU with desktop/Unreal left open; not cloud L4 or whole-training throughput',
                max_cpu_gpu_qvel_error=errors,samples_ms=samples,median_ms={k:float(np.median(v)) for k,v in samples.items()})
            result['median_ratio']=result['median_ms']['coupled']/result['median_ms']['original']
            (probe.OUT/'capped_integrator/gpu_paired_benchmark.json').write_text(json.dumps(result,indent=2))
            print('GPU BENCHMARK '+json.dumps({k:v for k,v in result.items() if k!='samples_ms'}),flush=True)
        finally:gmotor.restore()

if __name__=='__main__':main()
