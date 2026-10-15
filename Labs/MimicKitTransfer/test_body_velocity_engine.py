"""Current shared UEFN engine: reset/substep/report velocity reference checks."""
import os, sys, json, importlib.util, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT'] = str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np, torch, warp as wp, yaml, mujoco
from probe_sequential_contacts import decode


def main(device='cpu', ticks=12, contact_trial=False, relaxed=False, worlds=4, trace_phase=None, hard_project=False, block=False, tiled_project=False, shared_project=False, manifolds=False, jolt_axes=False,debug_solver=False):
    assert worlds>=4
    assert not block or contact_trial
    assert not tiled_project or hard_project
    assert not shared_project or hard_project
    assert not manifolds or contact_trial
    torch.set_num_threads(1)
    wp.init(); wp.set_device(device)
    probe.mp_util.init(0, 1, device, 6732)
    spec = importlib.util.spec_from_file_location('current_uefn', ROOT/'Labs/MimicKitTraining/uefn_engine.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine_class=module.UefnNewtonEngine
    if contact_trial:
        import newton
        from sequential_contact_adapter import SequentialContactAdapter
        class ContactTrialEngine(engine_class):
            def _build_graphs(self):
                if debug_solver:self._graph=None
                else:super()._build_graphs()

            def _build_solver(self):
                # Test-process-only constructor override selects the dense mass
                # representation required by the prototype; no physics setting
                # or default source file is changed.
                original_build=module.NewtonEngine._build_solver
                def dense(engine):
                    engine._solver=newton.solvers.SolverMuJoCo(engine._sim_model,
                        solver='newton',njmax=450,nconmax=150,impratio=10,
                        iterations=100,ls_iterations=50,jacobian='dense')
                try:
                    module.NewtonEngine._build_solver=dense
                    super()._build_solver()
                finally:module.NewtonEngine._build_solver=original_build
                s=self._solver
                self._trial_contact=SequentialContactAdapter(s.mjw_model,s.mjw_data,s.mj_model,
                    self._uefn_motors,iterations=100 if block else (1000 if relaxed else 100),allow_soft_limits=True,
                    relaxation=.5 if relaxed else 1.,hard_limit_control=hard_project,block_motors=block,manifolds=manifolds,jolt_limit_axes=jolt_axes)
                self._trial_contact.install()
                if debug_solver:
                    custom=self._trial_contact;solve=custom.solve
                    def exact_failure(m,d):
                        solve(m,d)
                        if np.any(custom.error.numpy()):
                            fields=('inv','free','commands','J','diagonal','ncontact','nlimit','limit_J',
                                'limit_diagonal','limit_target','limit_compliance','limit_bilateral','friction',
                                'velocity','motor_impulse','contact_impulse','limit_impulse','stats','dofs','gains','caps','dt')
                            capture={name:getattr(custom.p,name).numpy() for name in fields}
                            if custom.p.manifold.enabled:
                                for name in ('count','group','size','radius','J','diagonal','impulse'):
                                    capture['manifold_'+name]=getattr(custom.p.manifold,name).numpy()
                            capture.update(qpos=d.qpos.numpy(),qvel=d.qvel.numpy(),mass=d.qM.numpy(),errors=custom.error.numpy())
                            np.savez_compressed(probe.OUT/'causal_transfer/contact_first_solver_failure.npz',**capture)
                            raise RuntimeError('Exact first failed physics equation preserved; no later substep advanced')
                    custom.solve=exact_failure
                if hard_project:
                    from limit_projection_gpu import SplitLimitProjection
                    from probe_limit_projection import joint_metadata
                    projection=SplitLimitProjection(s.mj_model,s.mjw_data,joint_metadata(s.mj_model),device)
                    before_projection=s._mujoco_warp_step
                    def projected_step():
                        before_projection()
                        projection.apply(self._trial_contact.p.inv,tiled=tiled_project,shared=shared_project)
                    s._mujoco_warp_step=projected_step
                    self._trial_projection=projection
                if device=='cpu':
                    custom=self._trial_contact;original=custom.solve
                    def traced(m,d):
                        original(m,d)
                        if not np.isfinite(custom.p.velocity.numpy()).all():
                            fields=('inv','free','commands','J','diagonal','ncontact','nlimit',
                                    'limit_J','limit_diagonal','limit_target','limit_compliance','velocity')
                            capture={name:getattr(custom.p,name).numpy() for name in fields}
                            capture.update(qpos=d.qpos.numpy(),qvel=d.qvel.numpy(),mass=d.qM.numpy(),
                                           rows=custom.rowmap.numpy(),efcJ=d.efc.J.numpy(),
                                           contactrows=d.contact.efc_address.numpy(),worldid=d.contact.worldid.numpy(),
                                           nacon=d.nacon.numpy(),efctypes=d.efc.type.numpy(),
                                           contactdist=d.contact.dist.numpy(),contactmargin=d.contact.includemargin.numpy())
                            np.savez_compressed(probe.OUT/'causal_transfer/contact_first_invalid.npz',**capture)
                            raise RuntimeError('First invalid contact solve preserved; rejecting replay')
                    custom.solve=traced
        engine_class=ContactTrialEngine
    sys.modules[probe.OmniWalkEnv.__module__].UefnNewtonEngine = engine_class
    os.chdir(probe.SOURCE/'MimicKit')
    configs = [yaml.safe_load((probe.OUT/f'checkpoint/{name}_config.yaml').read_text().replace(
        '/workspace/mimickit_trial', probe.SOURCE.as_posix())) for name in ('env', 'engine', 'agent')]
    configs[1]['uefn_asset_directory'] = str(ROOT/'Labs/MimicKitUEFN')
    env = probe.OmniWalkEnv(configs[0], configs[1], worlds, device, False)
    agent = probe.OmniPPOAgent(configs[2], env, device)
    agent.load(str(probe.OUT/'checkpoint/model.pt')); agent.eval(); agent.set_mode(probe.AgentMode.TEST)
    e = env._engine; s = e._solver; m = s.mj_model
    errors = []; substeps = []; pose_errors = []

    def check(raw, reset=False):
        assert np.isfinite(raw.body_q.numpy()).all(), 'Invalid body pose; reject replay'
        assert np.isfinite(raw.body_qd.numpy()).all(), 'Invalid body velocity; reject replay'
        # MJ cache is stale after reset. Independently convert current Newton
        # generalized state for the reference; this does not advance physics.
        if reset: s._update_mjc_data(s.mjw_data, s.model, raw)
        qq = s.mjw_data.qpos.numpy(); vv = s.mjw_data.qvel.numpy()
        expected = []
        for world in range(worlds):
            d = mujoco.MjData(m); d.qpos[:] = qq[world]; d.qvel[:] = vv[world]
            expected.append(decode(m, d))
        expected = np.array(expected)
        position = raw.body_q.numpy().reshape(worlds,15,7)[:,:,:3]
        pose_errors.append(float(abs(position-expected[:,:,:3]).max()))
        # Control-boundary exp-map/quaternion conversion in upstream Newton
        # introduces tens of micrometres; report it separately from velocity.
        np.testing.assert_allclose(position, expected[:,:,:3], atol=1e-4)
        actual = raw.body_qd.numpy().reshape(worlds,15,6)
        error = float(abs(actual-expected[:,:,7:]).max())
        np.testing.assert_allclose(actual, expected[:,:,7:], atol=1e-3, rtol=3e-5,equal_nan=False)
        errors.append(error)

    # Inspect actual physics boundaries on CPU; CUDA verifies the captured
    # execution via final tensors and multiple partial resets instead.
    original = e._pre_sim_step
    if device == 'cpu':
        def checked(raw, control):
            original(raw, control)
            check(raw, reset=True)
            substeps.append(1)
        e._pre_sim_step = checked
    duration = float(env._motion_lib.get_motion_lengths()[0])
    phases = torch.arange(worlds, device=device)/worlds
    traces={key:[] for key in ('subin','subout','forces')}
    if trace_phase is not None:
        assert device=='cpu' and 0<=trace_phase<1
        phases.fill_(trace_phase)
        original_step=s._mujoco_warp_step
        def trace_step():
            capture=len(traces['subin'])<ticks*8
            if capture:
                traces['subin'].append(probe.physical_state(env))
                traces['forces'].append(s.mjw_data.xfrc_applied.numpy()[0].copy())
            original_step()
            if capture:traces['subout'].append(probe.physical_state(env))
        s._mujoco_warp_step=trace_step
    env._sample_motion_times = lambda n: (torch.zeros(n,dtype=torch.long,device=device), phases[:n]*duration)
    obs, info = env.reset(); first_done = [0]*worlds; distances = []
    # Save the actual reset state too. Native comparisons can now start before
    # the first MJ tick, without borrowing an MJ-corrected initial pose.
    e._sim_state.pre_step_update();e._body_velocity.update(e._sim_state.raw_state)
    check(e._sim_state.raw_state,reset=True)
    initial=np.concatenate([e._sim_state.raw_state.body_q.numpy().reshape(worlds,15,7),
                            e._sim_state.raw_state.body_qd.numpy().reshape(worlds,15,6)],-1)
    states=[];observations=[];actions=[];targets=[];defects=[];worst={};worst_defect=-1.
    started = time.perf_counter()
    for tick in range(ticks):
        with torch.no_grad(): action, _ = agent._decide_action(obs, info)
        observations.append(obs.cpu().numpy().copy());actions.append(action.cpu().numpy().copy())
        obs, _, done, info = env.step(action)
        check(e._sim_state.raw_state)
        states.append(np.concatenate([e._sim_state.raw_state.body_q.numpy().reshape(worlds,15,7),
                                      e._sim_state.raw_state.body_qd.numpy().reshape(worlds,15,6)],-1))
        targets.append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1).cpu().numpy().copy())
        if contact_trial:
            failure=e._trial_contact.error.numpy()
            if np.any(failure):
                p=e._trial_contact.p
                fields=('inv','free','commands','J','diagonal','ncontact','nlimit','limit_J',
                    'limit_target','limit_compliance','velocity','motor_impulse','contact_impulse','stats')
                capture={name:getattr(p,name).numpy() for name in fields}
                capture.update(tick=np.array(tick),errors=failure,qpos=s.mjw_data.qpos.numpy(),qvel=s.mjw_data.qvel.numpy(),
                    configuration=np.array([int(block),int(manifolds),int(jolt_axes)]))
                np.savez_compressed(probe.OUT/'causal_transfer/contact_rejected_motion.npz',**capture)
            np.testing.assert_array_equal(failure,0)
            defects.append(e._trial_contact.p.stats.numpy().copy())
            if float(defects[-1].max())>worst_defect:
                worst_defect=float(defects[-1].max());p=e._trial_contact.p
                fields=('ncontact','nlimit','inv','free','dofs','gains','caps','commands','friction','J',
                        'limit_J','limit_target','limit_compliance','limit_bilateral','dt','velocity','stats')
                worst={field:getattr(p,field).numpy().copy() for field in fields}
                worst.update(tick=np.array(tick),world=np.array(np.argmax(defects[-1])))
        distances.append(env.target_distances_sq.sqrt().cpu().numpy())
        for i, value in enumerate(done.cpu().tolist()):
            if value and not first_done[i]: first_done[i] = tick+1
        if tick % 30 == 29: print('PROGRESS', tick+1, first_done, flush=True)
        if contact_trial and all(first_done):break
    # Reset two of four worlds after nonzero dynamics; unchanged worlds must
    # retain their state and the first force call must use the new joint values.
    before = e._sim_state.raw_state.joint_qd.numpy().reshape(worlds,-1).copy()
    env.reset(torch.tensor([0,2],device=device))
    np.testing.assert_array_equal(e._sim_state.raw_state.joint_qd.numpy().reshape(worlds,-1)[[1,3]], before[[1,3]])
    e._sim_state.pre_step_update()
    e._body_velocity.update(e._sim_state.raw_state)
    check(e._sim_state.raw_state, reset=True)
    env.step(torch.zeros((worlds,34),device=device)); check(e._sim_state.raw_state)
    report = dict(device=device, ticks=ticks, worlds=worlds, max_velocity_error=max(errors),
                  checked_substeps=len(substeps), max_position_roundtrip_m=max(pose_errors), first_done=first_done,
                  max_distance=np.max(distances,axis=(0,2)).tolist(), partial_reset_verified=True,
                  cuda_graph=bool(e._graph), seconds=time.perf_counter()-started)
    label=('contact_soft_limit_trial' if contact_trial else 'body_velocity_engine')+'_'+device.replace(':','_')
    if relaxed:label+='_relaxed'
    if hard_project:label+='_hard_project'
    if block:label+='_block'
    if tiled_project:label+='_tiled'
    if shared_project:label+='_shared'
    if manifolds:label+='_manifolds'
    if jolt_axes:label+='_jolt_axes'
    if worlds!=4:label+='_worlds'+str(worlds)
    if hard_project and ticks!=90:label+='_ticks'+str(ticks)
    if trace_phase is not None:label+='_phase'+str(trace_phase)
    if contact_trial:
        report.update(diagnostic_only=True,changed='hard sequential contact friction; '+('hard limit velocity + split position' if hard_project else 'original soft MJ limits retained'),
                      max_motor_defect_nm=float(np.max(defects)),actual_ticks=len(states))
        np.savez_compressed(probe.OUT/('causal_transfer/contact_worst_equations'+('_relaxed' if relaxed else '')+('_block' if block else '')+'.npz'),**worst)
    np.savez_compressed(probe.OUT/f'causal_transfer/{label}.npz',initial=initial,states=states,obs=observations,actions=actions,targets=targets,dist=distances,**traces)
    (probe.OUT/f'causal_transfer/{label}.json').write_text(
        json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__ == '__main__': main(sys.argv[1] if len(sys.argv)>1 else 'cpu', int(sys.argv[2]) if len(sys.argv)>2 else 12,
                               '--contact-trial' in sys.argv, '--relaxed' in sys.argv,
                               int(next((s.split('=')[1] for s in sys.argv if s.startswith('--worlds=')),4)),
                               float(next(s.split('=')[1] for s in sys.argv if s.startswith('--trace-phase=')))
                               if any(s.startswith('--trace-phase=') for s in sys.argv) else None,
                               '--hard-project' in sys.argv,'--block' in sys.argv,'--tiled-project' in sys.argv,
                               '--shared-project' in sys.argv,'--manifolds' in sys.argv,'--jolt-axes' in sys.argv,'--debug-solver' in sys.argv)
