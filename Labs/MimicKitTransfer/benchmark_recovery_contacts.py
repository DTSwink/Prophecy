"""Matched-input custom-solver timing; no policy updates and no cloud use."""
from getup_transfer import *
sys.path.insert(0,str(SOURCE/'assets/MimicKitTransfer'))
sys.path.insert(0,str(ASSET))
import mujoco,mujoco_warp as mjw,warp as wp
from sequential_contact_adapter import SequentialContactAdapter
from velocity_motors import CoupledVelocityMotors
from runtime import install_limits
from split_contact_candidate import load,generate_full

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--budget',action='store_true');parser.add_argument('--shared-response',action='store_true');parser.add_argument('--staged',action='store_true');args=parser.parse_args()
    wp.init();wp.set_device('cuda:0');n=1024;dev='cuda:0'
    incoming=np.load(OUT/'recovery-benchmark-inputs.npz');indices=np.arange(n)%len(incoming['qpos'])
    model=mujoco.MjModel.from_binary_path(str(OUT/'recovery-benchmark.mjb'))
    wm=mjw.put_model(model);d=mjw.put_data(model,mujoco.MjData(model),nworld=n,nconmax=150,njmax=450)
    install_limits(model,wm);motor=CoupledVelocityMotors(wm,d,model);motor.install()
    p=SequentialContactAdapter(wm,d,model,motor,iterations=100,allow_soft_limits=True,relaxation=.5,hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True);p.install()
    initial={key:wp.array(incoming[key][indices],device=dev,dtype=getattr(d,key).dtype) for key in incoming.files}
    def step():
        for key,value in initial.items():wp.copy(getattr(d,key),value)
        d.qacc_warmstart.zero_();p.p.warm_state.zero_();p.error.zero_()
        mjw.step(wm,d)
    original_launch=wp.launch_tiled;graphs={};values={};times={};adapters=[p]
    module=load(generate_full());work=module.Work()
    work.guess=wp.zeros((n,p.p.nv),dtype=float,device=dev);work.status=wp.zeros((n,p.p.nmotor),dtype=int,device=dev)
    for key in ('active','warm','outer'):setattr(work,key,wp.zeros(n,dtype=int,device=dev))
    kernels={p.block_kernel:module.make_full(p.p.nv,p.p.nmotor),p.retry_block_kernel:module.make_full(p.p.nv,p.p.nmotor,retry=True)}
    def launch(kernel,*args,**kwargs):
        if kernel in kernels:
            begin,prepare,sweep=kernels[kernel]
            original_launch(begin,dim=n,inputs=[p.p,work],block_dim=32,device=dev)
            for _ in range(60):
                original_launch(prepare,dim=n,inputs=[p.p,d.qM,work],block_dim=32,device=dev)
                original_launch(sweep,dim=n,inputs=[p.p,p.iterations,p.error,work],block_dim=32,device=dev)
        else:return original_launch(kernel,*args,**kwargs)
    candidate='staged' if args.staged else ('shared_response' if args.shared_response else ('budget24' if args.budget else 'split'))
    original_kernels=(p.block_kernel,p.retry_block_kernel)
    if args.shared_response:
        from shared_response_candidate import load_candidate
        shared=load_candidate(SOURCE/'assets/MimicKitTransfer/block_contact_gpu.py',OUT/'shared_response_block.py')
    for name in ('baseline',candidate):
        wp.launch_tiled=launch if name=='split' else original_launch
        p.iterations=24 if name=='budget24' else 100;p.seed_iterations=16 if name=='budget24' else 50
        if name=='staged':
            from staged_contact_candidate import adapter_class
            cls=adapter_class(SOURCE/'assets/MimicKitTransfer',OUT)
            p=cls(wm,d,model,motor,allow_soft_limits=True,relaxation=.5,hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True)
            adapters.append(p)
            wm.transfer_contact_test=None;p.install()
        if name=='shared_response':
            p.block_kernel=shared.make_block_iteration(p.p.nv,p.p.nmotor,warm_start=True)
            p.retry_block_kernel=shared.make_block_iteration(p.p.nv,p.p.nmotor,warm_start=True,retry=True)
        step()
        with wp.ScopedCapture(device=dev) as capture:step()
        graphs[name]=capture.graph
        wp.capture_launch(capture.graph);wp.synchronize()
        values[name]={'qpos':d.qpos.numpy(),'qvel':d.qvel.numpy()}
        assert not p.error.numpy().any(),np.unique(p.error.numpy())
        print(name,'built',flush=True)
    wp.launch_tiled=original_launch
    start=wp.Event(enable_timing=True);end=wp.Event(enable_timing=True)
    for name in graphs:times[name]=[]
    for repeat in range(8):
        for name in (list(graphs) if repeat%2==0 else list(reversed(graphs))):
            wp.record_event(start)
            for _ in range(4):wp.capture_launch(graphs[name])
            wp.record_event(end);ms=wp.get_event_elapsed_time(start,end)/4
            if repeat>=2:times[name].append(ms)
    delta={key:float(np.max(abs(values['baseline'][key]-values[candidate][key]))) for key in values['baseline']}
    report=dict(worlds=n,distinct_inputs=len(incoming['qpos']),milliseconds={k:float(np.median(v)) for k,v in times.items()},samples_ms=times,max_difference=delta)
    (OUT/f'matched-contact-timing-{candidate}.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
