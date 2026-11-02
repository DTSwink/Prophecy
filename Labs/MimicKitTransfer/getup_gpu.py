"""Paired frozen-policy GPU physics tests from recorded recovery starts."""
from getup_transfer import *
import warp as wp
from util import mp_util
from anim.mjcf_char_model import MJCFCharModel
from engines.engine import ObjType
from uefn_engine import build_uefn_engine

def main():
    parser=argparse.ArgumentParser();parser.add_argument('backend',choices=['native','custom']);parser.add_argument('--checkpoint',default='native')
    parser.add_argument('--rows',default='3,8,9,16');parser.add_argument('--worlds',type=int,default=0);parser.add_argument('--ticks',type=int,default=180)
    parser.add_argument('--engine-file',type=Path)
    parser.add_argument('--shared-response',action='store_true')
    parser.add_argument('--staged',action='store_true')
    parser.add_argument('--scalar-iterations',type=int,default=0)
    parser.add_argument('--register-scalar',action='store_true')
    parser.add_argument('--scalar-relaxation',type=float,default=.5)
    parser.add_argument('--require-reset-hook',action='store_true')
    parser.add_argument('--contact-iterations',type=int,default=100);parser.add_argument('--seed-iterations',type=int,default=50);parser.add_argument('--projection-iterations',type=int,default=20)
    parser.add_argument('--profile',action='store_true');parser.add_argument('--instrument',action='store_true');parser.add_argument('--split',action='store_true');parser.add_argument('--full-split',action='store_true');parser.add_argument('--save-inputs',action='store_true');parser.add_argument('--label',default='baseline');a=parser.parse_args()
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6783)
    config=yaml.safe_load((a.engine_file or OUT/a.backend/'engine_config.yaml').read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    engine=build_uefn_engine(config,a.worlds or len(a.rows.split(',')),'cuda:0',False)
    n=engine.get_num_envs()
    for w in range(n):
        i=engine.create_env();engine.create_obj(i,ObjType.articulated,str(ASSET/'humanoid_uefn.xml'),'character',enable_self_collisions=True)
    engine.initialize_sim()
    if a.backend=='custom' and (a.contact_iterations,a.seed_iterations,a.projection_iterations)!=(100,50,20):
        p=engine.transfer_contact;p.iterations=a.contact_iterations;p.seed_iterations=a.seed_iterations
        apply=engine.transfer_projection.apply
        engine.transfer_projection.apply=lambda inv,**kw:apply(inv,**(kw|{'iterations':a.projection_iterations}))
        engine._build_graphs()
    if a.split:
        from split_contact_candidate import install
        install(engine)
    if a.shared_response:
        from shared_response_candidate import install
        install(engine,SOURCE/'assets/MimicKitTransfer/block_contact_gpu.py',OUT/'shared_response_block.py')
    if a.staged:
        from staged_contact_candidate import install
        install(engine,SOURCE/'assets/MimicKitTransfer',OUT)
    if a.scalar_iterations:
        from finite_contact_candidate import install
        install(engine,a.scalar_iterations,a.register_scalar,a.scalar_relaxation)
    if a.full_split:
        from split_contact_candidate import install_full
        install_full(engine)
    if a.instrument:
        import importlib.util
        p=engine.transfer_contact
        src=(SOURCE/'assets/MimicKitTransfer/block_contact_gpu.py').read_text()
        src=src.replace('for outer in range(60):','for outer in range(60):\n            if lane==0:p.stats[w,1]+=1.')
        src=src.replace('for it in range(iterations):','for it in range(iterations):\n                if lane==0:p.stats[w,2]+=1.')
        path=OUT/'instrumented_block.py';path.write_text(src)
        spec=importlib.util.spec_from_file_location('instrumented_block',path);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
        p.p.stats=wp.zeros((n,3),dtype=float,device='cuda:0')
        p.block_kernel=mod.make_block_iteration(p.p.nv,p.p.nmotor,warm_start=True)
        p.retry_block_kernel=mod.make_block_iteration(p.p.nv,p.p.nmotor,warm_start=True,retry=True)
        engine._build_graphs();p.p.stats.zero_()
    kin=MJCFCharModel('cpu');kin.load(str(ASSET/'humanoid_uefn.xml'))
    selected=list(map(int,a.rows.split(',')));meta=[];states=[]
    for w in range(n):
        row,s=replay(a.checkpoint,selected[w%len(selected)]);meta.append(row);states.append(s[0])
    states=np.array(states);joints,vel=zip(*(joint_state(s) for s in states))
    def gpu(x):return tensor(x).cuda()
    engine.set_root_pos(None,0,gpu(states[:,0,:3]));engine.set_root_rot(None,0,gpu(states[:,0,3:7]))
    engine.set_root_vel(None,0,gpu(states[:,0,7:10]));engine.set_root_ang_vel(None,0,gpu(states[:,0,10:13]))
    engine.set_dof_pos(None,0,kin.rot_to_dof(tensor(np.array(joints))).cuda());engine.set_dof_vel(None,0,gpu(np.array(vel)))
    engine._sim_state.pre_step_update();engine._sim_state.eval_fk()
    if a.require_reset_hook:assert hasattr(engine,'refresh_body_velocities')
    if hasattr(engine,'refresh_body_velocities'):engine.refresh_body_velocities()
    else:engine._body_velocity.update(engine._sim_state.raw_state)
    def read():
        return np.concatenate([engine.get_body_pos(0).cpu().numpy(),engine.get_body_rot(0).cpu().numpy(),
            engine.get_body_vel(0).cpu().numpy(),engine.get_body_ang_vel(0).cpu().numpy()],-1).copy()
    actual=read();initial_pos_error=float(np.max(abs(actual[:,:,:3]-states[:,:,:3])));assert initial_pos_error<2e-5,initial_pos_error
    initial_velocity_error=float(np.max(abs(actual[:,:,7:]-states[:,:,7:])))
    if a.require_reset_hook:assert initial_velocity_error<1e-3,initial_velocity_error
    pol=Policy(a.checkpoint);phase=np.array([r['frame_phase'][0][:2] for r in meta]);hist=[actual];act=[];phases=[phase.copy()];ends=np.zeros(n,int);endticks=np.zeros(n,int)
    timings=[];p=getattr(engine,'transfer_contact',None)
    frozen={key:[] for key in ('qpos','qvel','ctrl','xfrc_applied')}
    if a.save_inputs:
        import mujoco
        mujoco.mj_saveModel(engine._solver.mj_model,str(OUT/'recovery-benchmark.mjb'),None)
    for tick in range(1,a.ticks+1):
        obs=observation_batch(actual,meta,phase)
        if tick==1:
            reference=torch.cat([observation(s,r,ph) for s,r,ph in zip(actual[:6],meta[:6],phase[:6])])
            torch.testing.assert_close(obs[:6],reference,rtol=0,atol=1e-6)
        action,phase=pol(obs);engine.set_cmd(0,gpu(action))
        if a.save_inputs:
            for key in frozen:frozen[key].append(getattr(engine._solver.mjw_data,key).numpy().copy())
        torch.cuda.synchronize();start=time.perf_counter();engine.step();torch.cuda.synchronize();timings.append(time.perf_counter()-start)
        actual=read();hist.append(actual);act.append(action);phases.append(phase.copy())
        assert np.isfinite(actual).all()
        for w in range(n):
            if not ends[w]:
                ends[w]=outcome(actual[w],tick,meta[w])
                if ends[w]:endticks[w]=tick
        if tick%20==0:print(json.dumps(dict(tick=tick,physics_ms=1000*np.mean(timings[-20:]),ended=int(np.count_nonzero(ends)))),flush=True)
        if np.all(ends) and not a.profile:break
    report=dict(backend=a.backend,checkpoint=a.checkpoint,label=a.label,worlds=n,initial_position_error=initial_pos_error,initial_velocity_error=initial_velocity_error,
        physics_ms_mean=1000*np.mean(timings[2:]),seconds=sum(timings),batched_observation_driver=True,
        results=[dict(row=selected[w%len(selected)],terminal=int(ends[w]),ticks=int(endticks[w])) for w in range(n)])
    if p:
        report['counters']={k:np.asarray(getattr(p.p,k).numpy()).sum(axis=0).tolist() for k in ['fallback_count','fallback_steps','stats','ncontact','nlimit','convergence_warnings','roundoff_warnings']}
        if hasattr(p,'coupled_problem'):report['coupled']=p.coupled_problem.result.numpy().sum(axis=0).tolist()
        report['errors']=np.unique(p.error.numpy(),return_counts=True)[0].tolist()
    if a.profile:
        from collections import defaultdict
        aggregate=defaultdict(float)
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as prof:
            engine.step();torch.cuda.synchronize()
        for event in prof.events():
            if str(event.device_type).endswith('CUDA'):aggregate[event.name]+=event.device_time_total/1000
        report['kernel_ms']=sorted(aggregate.items(),key=lambda x:-x[1])[:30]
    dest=OUT/f'{a.checkpoint}-{a.backend}-{a.label}-{n}'
    if a.save_inputs:np.savez_compressed(OUT/'recovery-benchmark-inputs.npz',**{key:np.concatenate(value,axis=0) for key,value in frozen.items()})
    np.savez_compressed(dest.with_suffix('.npz'),states=np.array(hist),actions=act,phase=phases,terminal=ends,endticks=endticks)
    dest.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
