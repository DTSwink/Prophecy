"""Paired GPU full-substep costs at identical recorded inputs, without training."""
import os,json,time,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco,mujoco_warp as mjw,warp as wp
from probe_sequential_contacts import encode
from coupled_velocity_motors import CoupledVelocityMotors
from sequential_contact_adapter import SequentialContactAdapter
from limit_projection_gpu import SplitLimitProjection
from probe_limit_projection import joint_metadata
sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
from runtime import install_limits


def measure(graphs,rounds=10,replays=8):
    samples={name:[] for name in graphs}
    start=wp.Event(enable_timing=True);end=wp.Event(enable_timing=True)
    for repeat in range(rounds+2):
        order=list(graphs) if repeat%2==0 else list(reversed(graphs))
        for name in order:
            wp.record_event(start)
            for _ in range(replays):wp.capture_launch(graphs[name])
            wp.record_event(end)
            ms=wp.get_event_elapsed_time(start,end)/replays
            if repeat>=2:samples[name].append(ms)
    return dict(median_ms={k:float(np.median(v)) for k,v in samples.items()},samples_ms=samples)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'Saved/MimicKitLocal/performance_vanilla')
    parser.add_argument('--seed-iterations',type=int,default=50)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    assert not (out/'physics.json').exists(),'Preserve previous benchmark'
    folder=probe.OUT/'causal_transfer';wp.init();wp.set_device('cuda:0')
    with np.load(folder/'body_velocity_engine_cpu_phase0.5625.npz') as z:source=dict(z)
    steps=np.arange(512)%24+8
    m=mujoco.MjModel.from_binary_path(str(folder/'sequential_model.mjb'))
    m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
    wm=mjw.put_model(m);d=mjw.put_data(m,mujoco.MjData(m),nworld=512,nconmax=150,njmax=450)
    q,v=zip(*(encode(m,s) for s in source['subin'][steps]))
    q=wp.array(np.asarray(q,np.float32),device='cuda:0');v=wp.array(np.asarray(v,np.float32),device='cuda:0')
    # Discover actuator channels without activating the motor adapter.
    install_limits(m,wm);limits=wm.uefn_compound_limits
    motor=CoupledVelocityMotors(wm,d,m)
    ctrl=np.zeros((512,m.nu),np.float32);ctrl[:,motor.ids]=source['actions'][steps//8,0].clip(-2*np.pi,2*np.pi)
    d.ctrl.assign(ctrl);d.xfrc_applied.assign(source['forces'][steps].astype(np.float32))
    projection=SplitLimitProjection(m,d,joint_metadata(m),'cuda:0')
    custom=None;graphs={};finite={};preprojection=wp.empty_like(d.qpos)
    for mode in ('vanilla_mj','mj_phat_limits','mj_phat_bounded_motors','jolt_profile'):
        wm.uefn_compound_limits=None if mode=='vanilla_mj' else limits
        if mode=='mj_phat_bounded_motors':motor.install()
        if mode=='jolt_profile':
            custom=SequentialContactAdapter(wm,d,m,motor,iterations=100,allow_soft_limits=True,
                relaxation=.5,hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True,seed_iterations=args.seed_iterations)
            custom.install()
        def step():
            wp.copy(d.qpos,q);wp.copy(d.qvel,v);d.qacc_warmstart.zero_()
            mjw.step(wm,d)
            if mode=='jolt_profile':
                wp.copy(preprojection,d.qpos);projection.apply(custom.p.inv,shared=True)
        step()
        with wp.ScopedCapture(device='cuda:0') as capture:step()
        graphs[mode]=capture.graph
        wp.capture_launch(capture.graph);wp.synchronize_device('cuda:0')
        finite[mode]=bool(np.isfinite(d.qpos.numpy()).all() and np.isfinite(d.qvel.numpy()).all())
        assert finite[mode],mode
        if custom:np.testing.assert_array_equal(custom.error.numpy(),0)
    result=dict(device=wp.get_device().name,worlds=512,physics_dt=1/240,
        scope='Identical 24 recorded impact substeps repeated across512 worlds; full physics plus identical GPU reset; no policy/reward/PPO/state conversion or drag computation. Different physical equations, not a learning-efficiency claim.',
        cuda_graph=True,compilation_included=False,finite=finite,**measure(graphs))
    parts={}
    for name in ('contact_motor_solve','angular_position_projection'):
        def component():
            if name=='contact_motor_solve':wp.copy(d.qvel,v);custom.solve(wm,d)
            else:wp.copy(d.qpos,preprojection);projection.apply(custom.p.inv,shared=True)
        with wp.ScopedCapture(device='cuda:0') as capture:component()
        parts[name]=capture.graph
    result['components']=measure(parts)
    np.testing.assert_array_equal(custom.error.numpy(),0)
    result['fallbacks']=int(custom.p.fallback_count.numpy().sum())
    result['seed_iterations']=args.seed_iterations
    from sequential_contact_gpu import prepare_response,prepare_limit_response
    from contact_manifolds_gpu import prepare_response as prepare_manifold_response
    def seed():
        wp.launch(prepare_response,dim=(512,custom.capacity,3,m.nv),inputs=[custom.p],device='cuda:0')
        wp.launch(prepare_limit_response,dim=(512,custom.p.limit_J.shape[1],m.nv),inputs=[custom.p],device='cuda:0')
        wp.launch(prepare_manifold_response,dim=(512,custom.capacity,3,m.nv),inputs=[custom.p.manifold,custom.p.inv],device='cuda:0')
        wp.launch_tiled(custom.iterate_kernel,dim=512,inputs=[custom.p,args.seed_iterations],block_dim=32,device='cuda:0')
    seed();seeded=wp.clone(custom.p.velocity)
    stages={}
    for name in ('initial_estimate','block_solve'):
        with wp.ScopedCapture(device='cuda:0') as capture:
            if name=='initial_estimate':seed()
            else:
                wp.copy(custom.p.velocity,seeded)
                wp.launch_tiled(custom.block_kernel,dim=512,inputs=[custom.p,d.qM,custom.identity,100,custom.error],block_dim=32,device='cuda:0')
        stages[name]=capture.graph
    result['solve_stages']=measure(stages)
    result['unassisted_block_failures']=int(np.count_nonzero(custom.error.numpy()))
    result['profile_to_vanilla_ratio']=result['median_ms']['jolt_profile']/result['median_ms']['vanilla_mj']
    (out/'physics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
