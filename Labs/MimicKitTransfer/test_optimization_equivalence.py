"""Paired frozen-input physics and timing against the pre-optimization kernels."""
import argparse,json
from pathlib import Path
from benchmark_vanilla_transfer import (ROOT,probe,np,mujoco,mjw,wp,encode,
    install_limits,CoupledVelocityMotors,SequentialContactAdapter,SplitLimitProjection,
    joint_metadata,measure)
from optimization_reference import components


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seed-iterations',type=int,default=50)
    parser.add_argument('--reference-folder',type=Path)
    parser.add_argument('--components',action='store_true')
    parser.add_argument('--factor-candidate',action='store_true')
    parser.add_argument('--current-reference',action='store_true')
    parser.add_argument('--shared-candidate',action='store_true')
    parser.add_argument('--register-candidate',action='store_true')
    parser.add_argument('--accelerated-candidate',action='store_true')
    parser.add_argument('--preconditioned-candidate',action='store_true')
    args=parser.parse_args();out=args.out.resolve();assert not out.exists()
    folder=probe.OUT/'causal_transfer';wp.init();wp.set_device('cuda:0')
    source=np.load(folder/'body_velocity_engine_cpu_phase0.5625.npz')
    steps=np.arange(512)%24+8
    reference_adapter,reference_projection=(SequentialContactAdapter,SplitLimitProjection) if args.current_reference else components(args.reference_folder)
    results={};graphs={};objects=[]
    for name,adapter,projector in [('reference',reference_adapter,reference_projection),
                                   ('optimized',SequentialContactAdapter,SplitLimitProjection)]:
        m=mujoco.MjModel.from_binary_path(str(folder/'sequential_model.mjb'))
        m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
        wm=mjw.put_model(m);d=mjw.put_data(m,mujoco.MjData(m),nworld=512,nconmax=150,njmax=450)
        install_limits(m,wm);motor=CoupledVelocityMotors(wm,d,m);motor.install()
        custom=adapter(wm,d,m,motor,iterations=100,seed_iterations=50 if name=='reference' else args.seed_iterations,allow_soft_limits=True,relaxation=.5,
                       hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True)
        if args.factor_candidate and name=='optimized':
            import importlib.util,sys
            path=ROOT/'Saved/MimicKitEquipment/floor-recovery/block_contact_factor_candidate.py'
            spec=importlib.util.spec_from_file_location('block_contact_factor_candidate',path)
            candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
            custom.block_kernel=candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,reuse_factor=True)
            custom.retry_block_kernel=candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,retry=True,reuse_factor=True)
        if (args.register_candidate or args.accelerated_candidate or args.preconditioned_candidate) and name=='optimized':
            import importlib.util,sys
            from make_register_contact_candidate import generate
            path=generate(accelerated=args.accelerated_candidate or args.preconditioned_candidate,precondition=args.preconditioned_candidate)
            spec=importlib.util.spec_from_file_location('block_contact_register_candidate',path)
            candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
            custom.block_kernel=candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True)
            custom.retry_block_kernel=candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,retry=True)
            if args.preconditioned_candidate:
                metric=wp.zeros((512,custom.capacity,3),dtype=float)
                original_launch=wp.launch_tiled
                def launch(kernel,*a,**kw):
                    if kernel in (custom.block_kernel,custom.retry_block_kernel):kw['inputs']=kw['inputs']+[metric]
                    return original_launch(kernel,*a,**kw)
                wp.launch_tiled=launch
        if args.shared_candidate and name=='optimized':
            import importlib.util,sys
            from make_shared_contact_candidate import generate
            path=generate()
            spec=importlib.util.spec_from_file_location('block_contact_shared_candidate',path)
            candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
            custom.block_kernel=candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,shared_fallback=True)
            custom.retry_block_kernel=candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,retry=True,shared_fallback=True)
            pairs={custom.block_kernel:candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,shared_rows=True),
                   custom.retry_block_kernel:candidate.make_block_iteration(m.nv,custom.p.nmotor,warm_start=True,retry=True,shared_rows=True)}
            original_launch=wp.launch_tiled
            def launch(kernel,*a,**kw):
                if kernel in pairs:original_launch(pairs[kernel],*a,**kw)
                return original_launch(kernel,*a,**kw)
            wp.launch_tiled=launch
        custom.install();projection=projector(m,d,joint_metadata(m),'cuda:0')
        q,v=zip(*(encode(m,s) for s in source['subin'][steps]))
        q=wp.array(np.asarray(q,np.float32),device='cuda:0');v=wp.array(np.asarray(v,np.float32),device='cuda:0')
        ctrl=np.zeros((512,m.nu),np.float32);ctrl[:,motor.ids]=source['actions'][steps//8,0].clip(-2*np.pi,2*np.pi)
        d.ctrl.assign(ctrl);d.xfrc_applied.assign(source['forces'][steps].astype(np.float32))
        def step():
            wp.copy(d.qpos,q);wp.copy(d.qvel,v);d.qacc_warmstart.zero_()
            mjw.step(wm,d);projection.apply(custom.p.inv,shared=True)
        step()
        with wp.ScopedCapture(device='cuda:0') as cap:step()
        graphs[name]=cap.graph;wp.capture_launch(cap.graph)
        np.testing.assert_array_equal(custom.error.numpy(),0)
        results[name]=dict(qpos=d.qpos.numpy(),qvel=d.qvel.numpy())
        objects.append((custom,projection,motor,wm,d,q,v))
    differences={}
    for field in ('qpos','qvel'):
        a=results['optimized'][field];b=results['reference'][field]
        np.testing.assert_allclose(a,b,atol=2e-4 if field=='qvel' else 1e-5,rtol=2e-5)
        differences[field]=float(np.max(abs(a-b)))
    report=dict(worlds=512,distinct_inputs=24,solver_seed_iterations=args.seed_iterations,max_absolute_difference=differences,**measure(graphs))
    report['shared_bytes']={name:{stage:kernel.module.load('cuda:0',32).get_kernel_hooks(kernel).forward_smem_bytes
        for stage,kernel in [('seed',custom.iterate_kernel),('block',custom.block_kernel)]}
        for name,(custom,*_) in zip(graphs,objects)}
    if args.components:
        from sequential_contact_gpu import prepare_response,prepare_limit_response
        from contact_manifolds_gpu import prepare_response as prepare_manifold_response
        parts={}
        for name,(custom,projection,motor,wm,d,q,v) in zip(graphs,objects):
            def seed():
                if hasattr(custom,'retry_seed_kernel'):custom.p.warm_state.zero_()
                wp.launch(prepare_response,dim=(512,custom.capacity,3,m.nv),inputs=[custom.p],device='cuda:0')
                wp.launch(prepare_limit_response,dim=(512,custom.p.limit_J.shape[1],m.nv),inputs=[custom.p],device='cuda:0')
                wp.launch(prepare_manifold_response,dim=(512,custom.capacity,3,m.nv),inputs=[custom.p.manifold,custom.p.inv],device='cuda:0')
                wp.launch_tiled(custom.iterate_kernel,dim=512,inputs=[custom.p,50],block_dim=32,device='cuda:0')
            seed();seeded=wp.clone(custom.p.velocity)
            for part in ('contact','seed','block'):
                with wp.ScopedCapture(device='cuda:0') as cap:
                    if part=='contact':wp.copy(d.qvel,v);custom.solve(wm,d)
                    elif part=='seed':seed()
                    else:
                        if hasattr(custom,'retry_seed_kernel'):custom.p.warm_state.zero_()
                        wp.copy(custom.p.velocity,seeded)
                        wp.launch_tiled(custom.block_kernel,dim=512,inputs=[custom.p,d.qM,custom.identity,100,custom.error],block_dim=32,device='cuda:0')
                parts[name+'_'+part]=cap.graph
        # Adjacent before/after components alternate order on successive rounds.
        report['components']=measure({n+'_'+p:parts[n+'_'+p] for p in ('contact','seed','block') for n in graphs})
        report['component_scope']='Seed/block force a cold start; complete contact solve permits the checked cache.'
    for custom,*_ in objects:np.testing.assert_array_equal(custom.error.numpy(),0)
    out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
