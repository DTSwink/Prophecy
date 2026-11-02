"""Compare tiled/register finite solves on identical captured constraints."""
from getup_transfer import *
sys.path.insert(0,str(SOURCE/'assets/MimicKitTransfer'))
sys.path.insert(0,str(ASSET))
import mujoco,mujoco_warp as mjw,warp as wp
from sequential_contact_adapter import SequentialContactAdapter
from velocity_motors import CoupledVelocityMotors
from runtime import install_limits
from prepare_bounded_kernel import generate
from staged_contact_candidate import module_from_file

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--iterations',type=int,default=80);parser.add_argument('--relaxation',type=float,default=.5);args=parser.parse_args()
    wp.init();wp.set_device('cuda:0');n=1024;dev='cuda:0'
    incoming=np.load(OUT/'recovery-benchmark-inputs.npz');indices=np.arange(n)%len(incoming['qpos'])
    model=mujoco.MjModel.from_binary_path(str(OUT/'recovery-benchmark.mjb'))
    wm=mjw.put_model(model);d=mjw.put_data(model,mujoco.MjData(model),nworld=n,nconmax=150,njmax=450)
    install_limits(model,wm);motor=CoupledVelocityMotors(wm,d,model);motor.install()
    p=SequentialContactAdapter(wm,d,model,motor,iterations=args.iterations,allow_soft_limits=True,relaxation=args.relaxation,hard_limit_control=True,block_motors=False,manifolds=True,jolt_limit_axes=True);p.install()
    initial={key:wp.array(incoming[key][indices],device=dev,dtype=getattr(d,key).dtype) for key in incoming.files}
    def step():
        for key,value in initial.items():wp.copy(getattr(d,key),value)
        d.qacc_warmstart.zero_();p.error.zero_();mjw.step(wm,d)
    graphs={};values={};times={};kernels={}
    for name in ('tiled','register'):
        if name=='register':p.iterate_kernel=module_from_file('bounded_contact_gpu',generate()).make_iteration(p.p.nv)
        kernels[name]=p.iterate_kernel
        step()
        with wp.ScopedCapture(device=dev) as capture:step()
        graphs[name]=capture.graph
        wp.capture_launch(capture.graph);wp.synchronize()
        values[name]={'qpos':d.qpos.numpy(),'qvel':d.qvel.numpy(),'motor_impulse':p.p.motor_impulse.numpy()}
        assert not p.error.numpy().any(),np.unique(p.error.numpy())
        assert all(np.isfinite(v).all() for v in values[name].values())
        print(name,'built',flush=True)
    start=wp.Event(enable_timing=True);end=wp.Event(enable_timing=True)
    for name in graphs:times[name]=[]
    for repeat in range(8):
        for name in (list(graphs) if repeat%2==0 else list(reversed(graphs))):
            wp.record_event(start)
            for _ in range(4):wp.capture_launch(graphs[name])
            wp.record_event(end);ms=wp.get_event_elapsed_time(start,end)/4
            if repeat>=2:times[name].append(ms)
    delta={key:float(np.max(abs(values['tiled'][key]-values['register'][key]))) for key in values['tiled']}
    direct={}
    for name,kernel in kernels.items():
        wp.launch_tiled(kernel,dim=n,inputs=[p.p,args.iterations],block_dim=32,device=dev);wp.synchronize()
        direct[name]=p.p.velocity.numpy()
    direct_difference=float(np.max(abs(direct['tiled']-direct['register'])))
    report=dict(worlds=n,iterations=args.iterations,relaxation=args.relaxation,distinct_inputs=len(incoming['qpos']),milliseconds={k:float(np.median(v)) for k,v in times.items()},samples_ms=times,max_difference=delta,same_constraints_velocity_difference=direct_difference)
    original_free=p.p.free.numpy()
    p.error.fill_(1);wp.launch_tiled(kernels['register'],dim=n,inputs=[p.p,args.iterations],block_dim=32,device=dev);wp.synchronize()
    np.testing.assert_array_equal(p.error.numpy(),1)
    p.error.zero_();p.p.free.fill_(float('nan'));wp.launch_tiled(kernels['register'],dim=n,inputs=[p.p,args.iterations],block_dim=32,device=dev);wp.synchronize()
    np.testing.assert_array_equal(p.error.numpy(),4)
    p.p.free.assign(original_free)
    report.update(unsupported_error_preserved=True,nonfinite_rejected=True)
    (OUT/f'matched-bounded-timing-{args.iterations}-{args.relaxation}.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    assert direct_difference<.002,report

if __name__=='__main__':main()
