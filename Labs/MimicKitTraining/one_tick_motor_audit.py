"""Local next-tick motor diagnostic; never alters the paid trainer or its files.

Reference pose AND velocity starts, real free-root/contact dynamics, eight physics
steps per 30Hz command. Compare optimized commands with changed gains/caps only.
Failure to optimize is not a proof of physical impossibility.
"""
import os,sys,json,io,time,math,zipfile,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Saved/MimicKitMotorAudit/source'
OUT=ROOT/'Saved/MimicKitMotorAudit/one_tick'
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(Path(__file__).parent),str(SOURCE/'MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true';os.environ['OMP_NUM_THREADS']='1'
import numpy as np,torch,warp as wp,yaml
from omni_walk import OmniWalkEnv
from omni_policy import OmniPPOAgent
from envs.base_env import EnvMode
from learning.base_agent import AgentMode
from util import torch_util as q,mp_util


@wp.kernel(enable_backward=False)
def record_torque(torque:wp.array2d(dtype=float),caps:wp.array(dtype=float),
                  peaks:wp.array2d(dtype=float),duty:wp.array2d(dtype=int)):
    w,j=wp.tid()
    value=wp.abs(torque[w,j]);peaks[w,j]=wp.max(peaks[w,j],value)
    duty[w,j]+=int(value>=.99*caps[j])


class TickEnv(OmniWalkEnv):
    def _build_engine(self,config,*args,**kwargs):
        sys.path.insert(0,str(Path(config['uefn_asset_directory']).parent/'MimicKitTransfer'))
        from contact_engine import ContactTransferEngine
        class Instrumented(ContactTransferEngine):
            def _build_solver(engine):
                super(Instrumented,engine)._build_solver()
                motor=engine._uefn_motors;n=engine.get_num_envs()
                engine.audit_peak=wp.zeros((n,34),device=engine._device)
                engine.audit_duty=wp.zeros((n,34),dtype=int,device=engine._device)
                original=engine._solver._mujoco_warp_step
                def step():
                    original()
                    wp.launch(record_torque,dim=(n,34),inputs=[motor.torque,motor.upper,engine.audit_peak,engine.audit_duty],device=engine._device)
                engine._solver._mujoco_warp_step=step
        return Instrumented(config,*args,**kwargs)

    def _reset_ref_motion(self,ids):
        if not hasattr(self,'audit_motions'):return super()._reset_ref_motion(ids)
        self._motion_ids[ids]=self.audit_motions[ids]
        self._motion_time_offsets[ids]=self.audit_times[ids]
        values=self._motion_lib.calc_motion_frame(self._motion_ids[ids],self.audit_times[ids])
        for dest,value in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,
                self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),values):dest[ids]=value
        pos,rot=self._kin_char_model.forward_kinematics(self._ref_root_pos,self._ref_root_rot,self._ref_joint_rot)
        self._ref_body_pos.copy_(pos);self._ref_body_rot.copy_(rot)
        self._ref_dof_pos[ids]=self._motion_lib.joint_rot_to_dof(values[4])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--iterations',type=int,default=12)
    parser.add_argument('--smoke',action='store_true');parser.add_argument('--rollout',action='store_true')
    parser.add_argument('--torque-calibration',action='store_true');parser.add_argument('--all-motions',action='store_true')
    parser.add_argument('--batch-cases',type=int,default=4);parser.add_argument('--uncapped-only',action='store_true')
    parser.add_argument('--verify-envelope',type=Path);parser.add_argument('--probe-axis');args=parser.parse_args()
    if args.verify_envelope:args.verify_envelope=args.verify_envelope.resolve()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(711)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6767);os.chdir(SOURCE/'MimicKit')
    with zipfile.ZipFile(OUT/'checkpoint.zip') as z:
        cfg={n:yaml.safe_load(z.read(n+'_config.yaml').decode().replace('/workspace/mimickit_trial',SOURCE.as_posix())) for n in ['env','engine','agent']}
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
    verification=None
    if args.verify_envelope:
        verification=args.verify_envelope.resolve()
        envelope=json.loads((verification/'envelope.json').read_text())
        cfg['engine']['uefn_motor_torque_caps_nm']=envelope['overrides_nm']
        verified_solutions=json.loads((verification/'solutions.json').read_text())
        all_solutions=verified_solutions
        # Validate every changed axis at its measured peak, plus forward and
        # backward controls. The user ended the broad scan; no new search here.
        peak_cases={(r['motion'],r['phase']) for r in envelope['axes'] if r['changed']}
        selected=[s for s in verified_solutions if (s['case']['motion'],s['case']['phase']) in peak_cases]
        selected.extend([s for s in verified_solutions if s['case']['motion'] in ('M_Neutral_Run_Loop_F_Unarmed','M_Neutral_Run_Loop_B_Unarmed')][::8])
        unique={(s['case']['motion'],s['case']['phase']):s for s in selected}
        verified_solutions=list(unique.values())
        while len(verified_solutions)%args.batch_cases:verified_solutions.append(verified_solutions[-1])
    motionfile=OUT/'motions.yaml';motionfile.write_text((SOURCE/'prepared/motions.yaml').read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    cfg['env']['motion_file']=str(motionfile);cfg['env'].pop('adaptive_motion_rows',None)
    cases_per_batch=args.batch_cases;variants=76;n=cases_per_batch*variants
    begun=time.perf_counter();env=TickEnv(cfg['env'],cfg['engine'],n,'cuda:0',False)
    e=env._engine;motor=e._uefn_motors;char=env._get_char_id();lib=env._motion_lib
    gains=motor.gains.numpy().copy();caps=motor.upper.numpy().copy();bounds=env._action_bound_high.clone()
    agent=OmniPPOAgent(cfg['agent'],env,'cuda:0');agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TEST)
    env.set_mode(EnvMode.TEST)
    names=[Path(lib.get_motion_file(i)).stem for i in range(lib.get_num_motions())]
    requested=[('M_Neutral_Run_Loop_F_Unarmed',16),('M_Neutral_Run_Loop_F_Drawn',16),
               ('M_Neutral_Run_Loop_B_Unarmed',8),('M_Neutral_Run_Loop_LR_Unarmed',8)]
    cases=[dict(motion=name,id=names.index(name),phase=float(phase)) for name,count in requested for phase in np.arange(count)/count]
    if args.all_motions:
        # Every policy-rate sample, rounded up to complete four-case batches.
        cases=[dict(motion=name,id=i,phase=float(k/count)) for i,name in enumerate(names)
               for count in [max(4,4*math.ceil(float(lib.get_motion_length(i))*30/4))]
               for k in range(count)]
    if args.smoke:cases=cases[:4]
    profiles=[('current',1.,1.),('gain_2x',2.,1.),('torque_2x',1.,2.),('both_2x',2.,2.)]
    output=OUT
    if args.torque_calibration:
        profiles=[('current',1.,1.),('uncapped',1.,1000.)]
        if args.uncapped_only:profiles=profiles[1:]
        output=OUT/('calibration_all' if args.all_motions else 'calibration');output.mkdir(exist_ok=True)
    rows=[];solutions=[]

    if args.rollout:
        # Frozen-policy trajectories from distinct reference phases. No optimization
        # or automatic resets: stop each measurement at its first task failure.
        trajectories=[]
        for motion_name in (requested[0][0],requested[1][0],requested[2][0],requested[3][0]):
            mid=names.index(motion_name)
            env.audit_motions=torch.full((n,),mid,device='cuda:0',dtype=torch.long)
            env.audit_times=torch.tensor([0.,.25,.5,.75],device='cuda:0').repeat_interleave(variants)*float(lib.get_motion_length(mid))
            for tag,gs,ts in profiles:
                motor.gains.assign(gains*gs);motor.upper.assign(caps*ts);motor.lower.assign(-caps*ts)
                obs,_=env.reset();alive=torch.ones(cases_per_batch,dtype=torch.bool,device='cuda:0')
                indices=torch.arange(cases_per_batch,device='cuda:0')*variants
                traces=[[] for _ in range(cases_per_batch)]
                for tick in range(90):
                    with torch.no_grad():commands,_=agent._decide_action(obs,{})
                    e.audit_peak.zero_();e.audit_duty.zero_();e.transfer_contact.error.zero_()
                    obs,reward,done,info=env.step(commands)
                    pos=e.get_body_pos(char);vel=e.get_body_vel(char)
                    data=dict(tick=tick+1)
                    metrics=dict(done=done[indices],max_body_error_cm=(pos-env.reward_target_pos).norm(dim=-1).amax(-1)[indices]*100,
                        pelvis_velocity=vel[indices,0],target_pelvis_velocity=env.reward_target_vel[indices,0],
                        torque_cap_duty=(wp.to_torch(e.audit_duty).float()/8)[indices],
                        numerical_error=wp.to_torch(e.transfer_contact.error)[indices],
                        body_error_cm=((pos-env.reward_target_pos).norm(dim=-1)*100)[indices])
                    for i in range(cases_per_batch):
                        if bool(alive[i]):traces[i].append(dict(**data,**{k:v[i].cpu().tolist() for k,v in metrics.items()}))
                    alive &= done[indices]==0
                    if not bool(alive.any()):break
                for i,trace in enumerate(traces):trajectories.append(dict(motion=motion_name,phase=i/4,profile=tag,trace=trace))
                print('ROLLOUT',motion_name,tag,[len(t)/30 for t in traces],flush=True)
                (OUT/'rollout.json').write_text(json.dumps(dict(checkpoint=json.loads((OUT/'checkpoint-receipt.json').read_text()),trajectories=trajectories)))
        print('ROLLOUT DONE',time.perf_counter()-begun,flush=True)
        return

    def evaluate(commands,capture=False):
        env.reset();e.audit_peak.zero_();e.audit_duty.zero_();e.transfer_contact.error.zero_()
        e.transfer_contact.p.convergence_metrics.zero_()
        env.step(commands.reshape(n,34))
        pos=e.get_body_pos(char);rot=e.get_body_rot(char);ang=e.get_body_ang_vel(char)
        vel=e.get_body_vel(char)-torch.cross(ang,q.quat_rotate(rot,env._body_com),dim=-1)
        parts=[pos-env.reward_target_pos,vel-env.reward_target_vel,
               q.quat_to_matrix(rot)-q.quat_to_matrix(env.reward_target_rot),ang-env.reward_target_ang]
        residual=torch.cat([part.reshape(n,-1)*torch.sqrt(env._loss_weights[i]/part[0].numel()) for i,part in enumerate(parts)],-1)
        if env._flat_com_config:
            from flat_com import flat_com_velocity
            v=flat_com_velocity(e.get_body_vel(char)[:,env._flat_com_ids],env._flat_com_masses)
            band=env._flat_com_bands[env._motion_ids]
            excess=torch.minimum(v-band[:,0],torch.zeros_like(v))+torch.maximum(v-band[:,1],torch.zeros_like(v))
            residual=torch.cat((residual,excess*math.sqrt(env._flat_com_weight/2)),dim=-1)
        bad=(wp.to_torch(e.transfer_contact.error)!=0)|~torch.isfinite(residual).all(-1)
        if capture and not bool(bad.any()):
            torch.testing.assert_close(residual.square().sum(-1),env.loss_terms.sum(-1),atol=1e-5,rtol=2e-5)
        residual=torch.where(bad[:,None],torch.full_like(residual,1e3),residual)
        result=residual.reshape(cases_per_batch,variants,-1)
        if not capture:return result
        angle=q.quat_to_exp_map(q.quat_diff(env.reward_target_rot,rot)).norm(dim=-1)*180/math.pi
        metrics=dict(cost=residual.square().sum(-1),max_body_error_cm=parts[0].norm(dim=-1).amax(-1)*100,
            max_rotation_error_deg=angle.amax(-1),max_speed_error_m_s=parts[1].norm(dim=-1).amax(-1),
            max_angular_speed_error_rad_s=parts[3].norm(dim=-1).amax(-1),
            pelvis_height_error_cm=parts[0][:,0,2]*100,pelvis_forward_velocity=vel[:,0,0],
            target_pelvis_forward_velocity=env.reward_target_vel[:,0,0],
            torque_peak=wp.to_torch(e.audit_peak).clone(),torque_cap_duty=wp.to_torch(e.audit_duty).float()/8,
            numerical_error=bad,loss_terms=env.loss_terms.clone(),
            solver_metrics=wp.to_torch(e.transfer_contact.p.convergence_metrics).clone(),
            body_pose=torch.cat((pos,rot),-1).clone(),target_pose=torch.cat((env.reward_target_pos,env.reward_target_rot),-1).clone())
        return result,{k:v.reshape(cases_per_batch,variants,*v.shape[1:]) for k,v in metrics.items()}

    if verification:
        checks=[]
        # This path exercises the normal engine configuration, not direct cap
        # assignment alone. Simulator limits, CPU model and actual motor agree.
        expected=np.array(envelope['applied_caps_nm'])
        np.testing.assert_allclose(caps,expected,rtol=1e-6)
        np.testing.assert_allclose(e.get_obj_torque_limits(0,0),expected,rtol=1e-6)
        cpu=e._solver.mj_model
        # MuJoCo stores hinge caps on the scalar joint, ball caps per actuator.
        cpu_caps=[]
        for actuator in motor.ids:
            cap=cpu.actuator_forcerange[actuator,1] if cpu.actuator_forcelimited[actuator] else np.inf
            joint=cpu.actuator_trnid[actuator,0]
            if cpu.jnt_actfrclimited[joint]:cap=min(cap,cpu.jnt_actfrcrange[joint,1])
            cpu_caps.append(cap)
        np.testing.assert_allclose(cpu_caps,expected,rtol=1e-6)
        if args.probe_axis:
            j=next(i for i,r in enumerate(envelope['axes']) if r['axis']==args.probe_axis)
            rows=json.loads((verification/'report.json').read_text())['rows']
            bycase={(s['case']['motion'],s['case']['phase']):s for s in all_solutions}
            ranked=sorted(rows,key=lambda r:r['optimized']['torque_peak'][j],reverse=True)[:16]
            probes=[]
            for begin in range(0,len(ranked),cases_per_batch):
                batch=ranked[begin:begin+cases_per_batch]
                solutions=[bycase[(r['motion'],r['phase'])] for r in batch]
                env.audit_motions=torch.tensor([s['case']['id'] for s in solutions],device='cuda:0').repeat_interleave(variants)
                env.audit_times=torch.tensor([s['case']['phase']*float(lib.get_motion_length(s['case']['id'])) for s in solutions],device='cuda:0').repeat_interleave(variants)
                commands=torch.tensor([s['command'] for s in solutions],device='cuda:0')[:,None].expand(-1,variants,-1)
                full,fm=evaluate(commands,True)
                reduced=caps.copy();reduced[j]=envelope['base_caps_nm'][j]
                motor.upper.assign(reduced);motor.lower.assign(-reduced)
                old,om=evaluate(commands,True)
                motor.upper.assign(caps);motor.lower.assign(-caps)
                for i,r in enumerate(batch):
                    probes.append(dict(motion=r['motion'],phase=r['phase'],peak_nm=r['optimized']['torque_peak'][j],
                        full=float(full[i].square().sum(-1).median()),old=float(old[i].square().sum(-1).median()),
                        numerical_error=bool(fm['numerical_error'][i].any() or om['numerical_error'][i].any())))
            (verification/'axis_probe.json').write_text(json.dumps(dict(axis=args.probe_axis,probes=probes),indent=2))
            print('AXIS PROBE',json.dumps(probes),flush=True)
            return
        for begin in range(0,len(verified_solutions),cases_per_batch):
            batch=verified_solutions[begin:begin+cases_per_batch]
            env.audit_motions=torch.tensor([x['case']['id'] for x in batch],device='cuda:0').repeat_interleave(variants)
            env.audit_times=torch.tensor([x['case']['phase']*float(lib.get_motion_length(x['case']['id'])) for x in batch],device='cuda:0').repeat_interleave(variants)
            commands=torch.tensor([x['command'] for x in batch],device='cuda:0')[:,None].expand(-1,variants,-1)
            motor.upper.assign(caps*1000);motor.lower.assign(-caps*1000)
            ref,rm=evaluate(commands,True)
            motor.upper.assign(caps);motor.lower.assign(-caps)
            finite,fm=evaluate(commands,True)
            motor.upper.assign(np.array(envelope['base_caps_nm'],dtype=np.float32));motor.lower.assign(-np.array(envelope['base_caps_nm'],dtype=np.float32))
            original,om=evaluate(commands,True)
            motor.upper.assign(caps);motor.lower.assign(-caps)
            for i,x in enumerate(batch):
                checks.append(dict(case=x['case'],cost_uncapped=float(ref[i,0].square().sum()),cost_capped=float(finite[i,0].square().sum()),
                    cost_original_caps=float(original[i].square().sum(-1).median()),
                    cost_new_caps_median=float(finite[i].square().sum(-1).median()),
                    max_position_difference_m=float((rm['body_pose'][i,0,:,:3]-fm['body_pose'][i,0,:,:3]).norm(dim=-1).max()),
                    peak_torque_nm=fm['torque_peak'][i,0].cpu().tolist(),
                    maximum_cap_duty=float(fm['torque_cap_duty'][i,0].max()),
                    numerical_error=bool(rm['numerical_error'][i].any() or fm['numerical_error'][i].any() or om['numerical_error'][i].any())))
            if begin%80==0:print('VERIFY',begin+len(batch),'/',len(verified_solutions),flush=True)
        ablations=[]
        # At each raised axis's peak-demand pose, restore only that axis's old
        # cap. This separates a measurable restriction from an unused high cap.
        for j,axis in enumerate(envelope['axes']):
            if not axis['changed']:continue
            matches=[s for s in verified_solutions if s['case']['motion']==axis['motion'] and abs(s['case']['phase']-axis['phase'])<1e-8]
            if not matches:raise ValueError('Peak case absent from verification solutions')
            x=matches[0];mid=x['case']['id']
            env.audit_motions=torch.full((n,),mid,device='cuda:0',dtype=torch.long)
            env.audit_times=torch.full((n,),x['case']['phase']*float(lib.get_motion_length(mid)),device='cuda:0')
            command=torch.tensor(x['command'],device='cuda:0').expand(cases_per_batch,variants,-1)
            full,fm=evaluate(command,True)
            reduced=caps.copy();reduced[j]=envelope['base_caps_nm'][j]
            motor.upper.assign(reduced);motor.lower.assign(-reduced)
            reduced_res,dm=evaluate(command,True)
            motor.upper.assign(caps);motor.lower.assign(-caps)
            full_cost=full.square().sum(-1).flatten();drop_cost=reduced_res.square().sum(-1).flatten()
            ablations.append(dict(axis=axis['axis'],case=x['case'],full_cost_median=float(full_cost.median()),
                restored_old_cap_cost_median=float(drop_cost.median()),
                full_cost_range=[float(full_cost.min()),float(full_cost.max())],
                old_cost_range=[float(drop_cost.min()),float(drop_cost.max())],
                numerical_error=bool(fm['numerical_error'].any() or dm['numerical_error'].any())))
        result=dict(checks=checks,engine_report=e.torque_envelope_report,
            individual_cap_ablations=ablations,
            gains_unchanged=bool(np.array_equal(gains,envelope['base_gains'])),
            numerical_errors=sum(x['numerical_error'] for x in checks),
            max_position_difference_m=max(x['max_position_difference_m'] for x in checks),
            maximum_cap_duty=max(x['maximum_cap_duty'] for x in checks),elapsed_seconds=time.perf_counter()-begun)
        (verification/'verification.json').write_text(json.dumps(result,indent=2))
        print('VERIFY DONE',json.dumps({k:v for k,v in result.items() if k not in ('checks','engine_report')}),flush=True)
        return

    for batchstart in range(0,len(cases),cases_per_batch):
        batch=cases[batchstart:batchstart+cases_per_batch]
        assert len(batch)==cases_per_batch
        env.audit_motions=torch.tensor([c['id'] for c in batch],device='cuda:0').repeat_interleave(variants)
        env.audit_times=torch.tensor([c['phase']*float(lib.get_motion_length(c['id'])) for c in batch],device='cuda:0').repeat_interleave(variants)
        obs,_=env.reset()
        with torch.no_grad():policy,_=agent._decide_action(obs,{})
        policy=policy.reshape(cases_per_batch,variants,34)[:,0].clone()
        future=lib.calc_motion_frame(env.audit_motions,env.audit_times+1/30)
        feed=env._ref_dof_vel.reshape(cases_per_batch,variants,34)[:,0].clone()
        nextfeed=future[5].reshape(cases_per_batch,variants,34)[:,0]
        previous_best=None
        for tag,gs,ts in profiles:
            motor.gains.assign(gains*gs);motor.upper.assign(caps*ts);motor.lower.assign(-caps*ts)
            # Identical actual training command bounds in every comparison.
            torch.testing.assert_close(env._action_bound_high,bounds,rtol=0,atol=0)
            policy_res,policy_metrics=evaluate(policy[:,None].expand(-1,variants,-1),True)
            repeated=evaluate(policy[:,None].expand(-1,variants,-1))
            reset_repeat_error=(policy_res-repeated).abs().amax((1,2)).cpu().tolist()
            repeats=policy_res.square().sum(-1)
            repeat_spread=(repeats.max(-1).values-repeats.min(-1).values).cpu().tolist()
            torch.manual_seed(711+batchstart)
            seeds=feed[:,None]+torch.randn(cases_per_batch,variants,34,device='cuda:0')*2.
            seeds[:,0]=policy;seeds[:,1]=feed;seeds[:,2]=nextfeed;seeds[:,3]=2*nextfeed-feed
            if previous_best is not None:seeds[:,4]=previous_best
            seeds=torch.maximum(torch.minimum(seeds,bounds),-bounds)
            residual=evaluate(seeds);cost=residual.square().sum(-1);bestidx=cost.argmin(-1)
            best=seeds[torch.arange(cases_per_batch,device='cuda:0'),bestidx].clone()
            history=[];identity=torch.eye(34,device='cuda:0');step=.25
            for iteration in range(args.iterations):
                trial=best[:,None].expand(-1,variants,-1).clone()
                trial[:,1:35]+=identity*step;trial[:,35:69]-=identity*step
                trial=trial.clamp(-bounds,bounds)
                residual=evaluate(trial);center=residual[:,0];cost=center.square().sum(-1)
                denominator=(trial[:,1:35]-trial[:,35:69]).diagonal(dim1=-2,dim2=-1).clamp_min(1e-6)
                jac=((residual[:,1:35]-residual[:,35:69])/denominator[:,:,None]).transpose(1,2)
                # Damped local least squares; line search accepts improvements only.
                lhs=jac.transpose(1,2)@jac
                damp=.0005 if iteration<6 else .00005
                delta=torch.linalg.solve(lhs+damp*identity,-(jac.transpose(1,2)@center[:,:,None])).squeeze(-1).clamp(-3.,3.)
                candidates=best[:,None].expand(-1,variants,-1).clone()
                for k,alpha in enumerate([1.,.5,.25,.125],1):candidates[:,k]+=alpha*delta
                # Independent small perturbations protect against a poor local derivative.
                candidates[:,5:]=best[:,None]+torch.randn(cases_per_batch,variants-5,34,device='cuda:0')*(.5 if iteration<6 else .15)
                candidates=candidates.clamp(-bounds,bounds)
                result=evaluate(candidates);costs=result.square().sum(-1);index=costs.argmin(-1)
                best=candidates[torch.arange(cases_per_batch,device='cuda:0'),index].clone()
                history.append(costs.min(-1).values.cpu().tolist())
            final,metrics=evaluate(best[:,None].expand(-1,variants,-1),True)
            previous_best=best.clone()
            for i,c in enumerate(batch):
                def values(source):return {k:v[i,0].cpu().tolist() for k,v in source.items() if k not in ('body_pose','target_pose')}
                row=dict(**c,profile=tag,gain_scale=gs,torque_scale=ts,policy=values(policy_metrics),optimized=values(metrics),
                         repeated_initial_cost_spread=repeat_spread[i],optimization_cost=[h[i] for h in history])
                row['reset_repeat_residual_error']=reset_repeat_error[i]
                rows.append(row);solutions.append(dict(case=c,profile=tag,command=best[i].cpu().tolist(),
                    actual=metrics['body_pose'][i,0].cpu().tolist(),target=metrics['target_pose'][i,0].cpu().tolist()))
            print('BATCH',batchstart,tag,'policy',policy_res[:,0].square().sum(-1).cpu().tolist(),'optimized',final[:,0].square().sum(-1).cpu().tolist(),flush=True)
            progress=dict(rows=rows,elapsed_seconds=time.perf_counter()-begun)
            if args.all_motions:
                progress=dict(completed=len(rows),total=len(cases)*len(profiles),
                    peak_torque_nm=np.max([r['optimized']['torque_peak'] for r in rows],axis=0).tolist(),
                    numerical_errors=sum(r['optimized']['numerical_error'] for r in rows),
                    elapsed_seconds=time.perf_counter()-begun,last_rows=rows[-cases_per_batch:])
            (output/'progress.json').write_text(json.dumps(progress))
            # Preserve completed measurements if a long local audit is interrupted.
            with (output/'measurements.jsonl').open('a') as stream:
                for row,solution in zip(rows[-len(batch):],solutions[-len(batch):]):
                    stream.write(json.dumps(dict(row=row,solution=solution))+'\n')
    report=dict(checkpoint=json.loads((OUT/'checkpoint-receipt.json').read_text()),rows=rows,settings={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        dt=1/30,physics_dt=1/240,commands_constant_during_tick=True,command_limits=bounds.cpu().tolist(),
        base_gains=gains.tolist(),base_caps_nm=caps.tolist(),elapsed_seconds=time.perf_counter()-begun,
        limitation='Independent reference-state one-tick tests, not sustained running. Failed optimization is not proof of impossibility; current-limit comparison and both controls retained.')
    (output/('smoke.json' if args.smoke else 'report.json')).write_text(json.dumps(report,indent=2))
    (output/'solutions.json').write_text(json.dumps(solutions))
    print('DONE',report['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
