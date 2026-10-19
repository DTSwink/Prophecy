"""Read-only local CPU forks from exact recorded states; no live trainer edits."""
import audit_getup_strength as base
from audit_getup_strength import *
from envs.base_env import EnvMode
OUT=ROOT/'Saved/MimicKitEquipment/left-foot-bounce'
SOURCE=OUT/'source'

def setup():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cpu')
    mp_util.init(0,1,'cpu',6787)
    SOURCE.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT/'Saved/MimicKitEquipment/mixed-position-leeway-source.zip') as z:
        for name in z.namelist():
            if name.startswith(('assets/','motions/','prepared/')):
                p=SOURCE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    for p in (SOURCE/'prepared').glob('*.yaml'):
        p.write_text(p.read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    cfg,ec,ac=[yaml.safe_load((SOURCE/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    original=omni_walk.row_motion_weights
    omni_walk.row_motion_weights=lambda g,w,f,n:(1,original(g,w,f,2)[1])
    env=base.CpuEnv(cfg,ec,1,'cpu',False)
    agent=OmniPPOAgent(ac,env,'cpu')
    with zipfile.ZipFile(OUT/'checkpoint.zip') as z:agent.load_state_dict(torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=True))
    agent.eval();agent.set_mode(AgentMode.TEST);env.set_mode(EnvMode.TEST)
    env.reset()
    return env,agent

def main():
    env,agent=setup();e=env._engine;s=e._solver;m=s.mj_model;d=s.mj_data
    bodies=[next(b for b in range(1,m.nbody) if m.body(b).name.endswith(n)) for n in e.get_obj_body_names(0)]
    names=e.get_obj_body_names(0);left=names.index('left_foot');bid=bodies[left]
    geoms=np.flatnonzero(m.geom_bodyid==bid)
    original=copy.copy(m)
    z=np.load(OUT/'replay.npz');meta=json.loads(str(z['metadata']))
    reports=[];traces={}
    def load_record(row,tick):
        suf='' if row==0 else '_'+str(row);pose=z['pose'+suf][tick];vel=z['world_velocities'+suf][tick]
        rotations=R.from_quat(pose[:,3:]);omega=vel[:,3:6]
        mujoco.mj_resetData(m,d);d.qpos[:]=m.qpos0
        d.qpos[:3]=pose[0,:3];d.qpos[3:7]=np.roll(pose[0,3:],1)
        d.qvel[:3]=vel[0,:3];d.qvel[3:6]=rotations[0].inv().apply(omega[0])
        for i,b in enumerate(bodies[1:],1):
            parent=bodies.index(m.body_parentid[b]);j=m.body_jntadr[b];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j]
            relative=R.from_quat(np.roll(m.body_quat[b],-1)).inv()*rotations[parent].inv()*rotations[i]
            velocity=rotations[i].inv().apply(omega[i]-omega[parent])
            if m.jnt_type[j]==1:d.qpos[qa:qa+4]=np.roll(relative.as_quat(),1);d.qvel[va:va+3]=velocity
            else:d.qpos[qa]=relative.as_rotvec()@m.jnt_axis[j];d.qvel[va]=velocity@m.jnt_axis[j]
        mujoco.mj_forward(m,d)
        native=d.qpos.copy()
        for a,r in e.balls:d.qpos[a:a+4]=np.roll((r.inv()*R.from_quat(np.roll(d.qpos[a:a+4],-1))).as_quat(),1)
        s._update_newton_state(e._sim_model,e._sim_state.raw_state,d,e._sim_state.raw_state)
        d.qpos[:]=native;e._sim_state.post_step_update()
        # Exact recorded body-origin velocities -> Newton body-COM velocities.
        com=wp.to_torch(e._sim_model.body_com).numpy()
        vcom=vel[:,:3]+np.cross(omega,rotations.apply(com))
        e.get_body_vel(0)[0]=torch.from_numpy(vcom.astype(np.float32))
        e.get_body_ang_vel(0)[0]=torch.from_numpy(omega.copy())
        # Root COM velocity is mirrored in joint_qd as well.
        e._sim_state._torch_joint_qd[:3]=torch.from_numpy(vcom[0].astype(np.float32))
        e._sim_state._torch_joint_qd[3:6]=torch.from_numpy(omega[0].copy())
        rmeta=meta['replay_rows'][row]
        ids=torch.where((env._gaits==-1)&(env._equipment==float(rmeta['sword_drawn'])))[0]
        env._motion_ids[0]=ids[0];env._fixed_motion_ids[0]=ids[0]
        env._feedback_phase[0]=torch.tensor(rmeta['frame_phase'][tick][:2])
        env._time_buf[0]=tick/30
        obs=env._compute_obs()
        with torch.no_grad():
            pred=agent._model.eval_phase(agent._obs_norm.normalize(obs))[0].numpy()
            action,_=agent._decide_action(obs,{})
        target=np.asarray(rmeta['frame_phase'][tick][2:4]);phase_error=float(abs(pred-target).max())
        e.set_cmd(0,action);s._apply_mjc_control(e._sim_model,e._sim_state.raw_state,e._controls.control,d)
        return d.qpos.copy(),d.qvel.copy(),d.ctrl.copy(),phase_error,float(abs(d.xpos[bodies]-pose[:,:3]).max())
    def record():
        mujoco.mj_forward(m,d)
        low=min(float(d.geom_xpos[g,2]-abs(d.geom_xmat[g].reshape(3,3)[2])@m.geom_size[g]) for g in geoms)
        jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jacBody(m,d,jp,jr,bid)
        contacts=[]
        for c in range(d.ncon):
            co=d.contact[c]
            if (co.geom1 in geoms and m.geom_bodyid[co.geom2]==0) or (co.geom2 in geoms and m.geom_bodyid[co.geom1]==0):
                force=np.zeros(6);mujoco.mj_contactForce(m,d,c,force);contacts.append(float(force[0]))
        return dict(z=float(d.xpos[bid,2]),sole_z=low,vz=float((jp@d.qvel)[2]),floor_normal_n=sum(contacts),
            command=d.ctrl[e.motors].tolist(),torque=d.qfrc_actuator[e.dofs].tolist(),velocity=d.actuator_velocity[e.motors].tolist())
    for row in (0,3):
        rmeta=meta['replay_rows'][row];suf='' if row==0 else '_'+str(row)
        commands=[];states=[];pe=[];mapping=[]
        for tick in range(8,21):
            qp,qv,ctrl,err,geo=load_record(row,tick);states.append((qp,qv));commands.append(ctrl);pe.append(err);mapping.append(geo)
        if '--post-impact' in sys.argv:
            variants=[]
            # Preserve the actual collision approach, then change ONLY forces
            # at/after impact. Earlier pre-impact forks cannot answer this.
            for fork_tick in ((12.,12.375,12.5,13.,13.25) if row==0 else (12.,17.,17.5)):
                frame=int(fork_tick);sub=round((fork_tick-frame)*8)
                mujoco.mj_resetData(m,d);d.qpos[:],d.qvel[:]=states[frame-8];d.ctrl[:]=commands[frame-8]
                for _ in range(sub):mujoco.mj_step(m,d)
                record();saved=(d.qpos.copy(),d.qvel.copy(),d.qacc_warmstart.copy())
                for mode in ('normal','left_leg_off','all_motors_off','left_foot_contact_off'):
                    for key in ('actuator_gainprm','actuator_biasprm','geom_contype','geom_conaffinity'):getattr(m,key)[:]=getattr(original,key)
                    if mode in ('left_leg_off','all_motors_off'):
                        selected=e.motors if mode=='all_motors_off' else [a for a,n in zip(e.motors,e.names) if n in ('left_thigh','left_shin','left_foot')]
                        m.actuator_gainprm[selected]=0;m.actuator_biasprm[selected]=0
                    if mode=='left_foot_contact_off':m.geom_contype[geoms]=0;m.geom_conaffinity[geoms]=0
                    mujoco.mj_resetData(m,d);d.qpos[:],d.qvel[:],d.qacc_warmstart[:]=saved;d.ctrl[:]=commands[frame-8]
                    trace=[record()]
                    for k in range(min(24,(20-frame)*8-sub)):
                        d.ctrl[:]=commands[frame+(sub+k)//8-8]
                        mujoco.mj_step(m,d);trace.append(record())
                    z0=trace[0]['z'];v0=trace[0]['vz']
                    variants.append(dict(fork_tick=fork_tick,mode=mode,initial_vz=v0,
                        first_step_accel=(trace[1]['vz']-v0)*240,
                        max_rise_cm=100*(max(v['z'] for v in trace)-z0),
                        vz_after_1_tick=trace[min(8,len(trace)-1)]['vz'],
                        initial_floor_n=trace[0]['floor_normal_n'],
                        z_after_3_ticks_cm=100*(trace[-1]['z']-z0)))
                    traces[str(row)+'_'+str(fork_tick)+'_'+mode]=trace
                for key in ('actuator_gainprm','actuator_biasprm','geom_contype','geom_conaffinity'):getattr(m,key)[:]=getattr(original,key)
            reports.append(dict(row=row,variants=variants))
            continue
        one_tick=[]
        for idx,tick in enumerate(range(8,20)):
            mujoco.mj_resetData(m,d);d.qpos[:],d.qvel[:]=states[idx];d.ctrl[:]=commands[idx]
            for _ in range(8):mujoco.mj_step(m,d)
            rec=record();actual=z['pose'+suf][tick+1,left,2]
            one_tick.append(dict(frame=tick+1,predicted_z=rec['z'],actual_z=float(actual),error_m=rec['z']-float(actual)))
        variants=[]
        for mode in ('normal','left_leg_off','all_motors_off','contact_damping_x2','no_floor'):
            for key in ('actuator_gainprm','actuator_biasprm','geom_solref','geom_contype','geom_conaffinity'):getattr(m,key)[:]=getattr(original,key)
            if mode in ('left_leg_off','all_motors_off'):
                selected=e.motors if mode=='all_motors_off' else [a for a,n in zip(e.motors,e.names) if n in ('left_thigh','left_shin','left_foot')]
                m.actuator_gainprm[selected]=0;m.actuator_biasprm[selected]=0
            if mode=='contact_damping_x2':m.geom_solref[:,0]=.00875;m.geom_solref[:,1]=4.
            if mode=='no_floor':
                floor=m.geom_bodyid==0;m.geom_contype[floor]=0;m.geom_conaffinity[floor]=0
            # Fork immediately before the visible impact; identical recorded command sequence.
            mujoco.mj_resetData(m,d);d.qpos[:],d.qvel[:]=states[3];trace=[record()]
            for frame in range(11,19):
                d.ctrl[:]=commands[frame-8]
                for _ in range(8):mujoco.mj_step(m,d);trace.append(record())
            zz=np.array([v['z'] for v in trace]);first=int(np.argmin(zz[:25]));rise=float(zz[first:].max()-zz[first])
            variants.append(dict(mode=mode,lowest_tick=11+first/8,rise_after_low_m=rise,z_at_ticks=zz[::8].tolist(),max_floor_normal_n=max(v['floor_normal_n'] for v in trace)))
            traces[str(row)+'_'+mode]=trace
        for key in ('actuator_gainprm','actuator_biasprm','geom_solref','geom_contype','geom_conaffinity'):getattr(m,key)[:]=getattr(original,key)
        reports.append(dict(row=row,motion=rmeta['motion_file'],max_phase_prediction_error=max(pe),max_geometry_mapping_error=max(mapping),one_tick_validation=one_tick,variants=variants))
    report=dict(iteration=meta['iteration'],floor_solref=original.geom_solref[0].tolist(),motor_names=e.names,rows=reports)
    stem='post-impact' if '--post-impact' in sys.argv else 'diagnosis'
    (OUT/(stem+'.json')).write_text(json.dumps(report,indent=2));(OUT/(stem+'-traces.json')).write_text(json.dumps(traces))
    print('RESULT '+json.dumps(report),flush=True)
if __name__=='__main__':main()
