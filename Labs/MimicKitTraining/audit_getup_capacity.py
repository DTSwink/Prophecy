"""CPU command optimization from reference pose+velocity, fixed 240/30 Hz."""
import audit_getup_strength as base
from audit_getup_strength import np,torch,mujoco,R,OUT
import json,time,sys
from scipy.optimize import least_squares

def main():
    env,agent=base.setup();e=env._engine;m=e._solver.mj_model;d=mujoco.MjData(m)
    bodies=[next(b for b in range(1,m.nbody) if m.body(b).name.endswith(n)) for n in e.get_obj_body_names(0)]
    weights=env._loss_weights.numpy();bounds=env._action_bound_high.numpy().copy()
    if bounds.ndim>1:bounds=bounds[0]
    np.testing.assert_equal(len(bounds),34)
    mapping_errors=[]
    def state(motion,t,reset=False):
        ids=torch.tensor([motion]);times=torch.tensor([t],dtype=torch.float32)
        lib=env._recovery_reset_lib if reset else env._recovery_lib
        values=lib.calc_motion_frame(ids,times)
        # A common yaw/XY translation leaves this flat-floor test invariant.
        root,rot,vel,ang,joints,dof=values
        k=env._kin_char_model
        pos,rotation=k.forward_kinematics(root,rot,joints)
        bodyv,bodyw=env._recovery_velocities(pos,rotation,vel,ang,dof,ids,times)
        # Direct world-body encoding avoids two float32 quaternion/exp-map conversions.
        rotations=R.from_quat(rotation[0].numpy());angular=bodyw[0].numpy()
        d.qpos[:]=m.qpos0;d.qvel[:]=0
        d.qpos[:3]=root[0].numpy();d.qpos[3:7]=np.roll(rot[0].numpy(),1)
        d.qvel[:3]=vel[0].numpy();d.qvel[3:6]=rotations[0].inv().apply(angular[0])
        for i,b in enumerate(bodies[1:],1):
            parent=bodies.index(m.body_parentid[b]);j=m.body_jntadr[b]
            qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j]
            relative=R.from_quat(np.roll(m.body_quat[b],-1)).inv()*rotations[parent].inv()*rotations[i]
            velocity=rotations[i].inv().apply(angular[i]-angular[parent])
            if m.jnt_type[j]==1:
                d.qpos[qa:qa+4]=np.roll(relative.as_quat(),1);d.qvel[va:va+3]=velocity
            else:
                d.qpos[qa]=relative.as_rotvec()@m.jnt_axis[j];d.qvel[va]=velocity@m.jnt_axis[j]
        mujoco.mj_forward(m,d)
        mapping_errors.append(float(abs(d.xpos[bodies]-pos[0].numpy()).max()))
        # Retargeted float32 kinematic data and compiled articulation differ
        # submillimetrically; report it rather than interpret it as motor weakness.
        np.testing.assert_allclose(d.xpos[bodies],pos[0].numpy(),atol=1e-3)
        return d.qpos.copy(),d.qvel.copy(),pos[0].numpy(),rotation[0].numpy(),bodyv[0].numpy(),bodyw[0].numpy()
    isolate='--isolate' in sys.argv
    dynamics='--dynamics' in sys.argv
    if dynamics:isolate=True
    confirm='--confirm' in sys.argv or isolate
    report_file='capacity-dynamics.json' if dynamics else 'capacity-isolate.json' if isolate else 'capacity-confirm.json' if confirm else 'capacity.json'
    commands_file='capacity-isolate-commands.json' if isolate else 'capacity-confirm-commands.json' if confirm else 'capacity-commands.json'
    prior=json.loads((OUT/'capacity.json').read_text()) if confirm else None
    prior_commands=json.loads((OUT/'capacity-commands.json').read_text()) if confirm else None
    rows=[];solutions=[];begun=time.time()
    # Cover initial support and active lifting, not duplicated worlds.
    for motion in (0,1):
        for tick in (0,4,8,12,16,20,26,32):
            if isolate and (motion,tick)!=(1,20):continue
            if confirm:
                old={r['profile']:r for r in prior['rows'] if r['motion']==motion and r['tick']==tick}
                if old['torque2']['cost']>=old['current']['cost']*.95:continue
            t=tick/30;start=state(motion,t,reset=(tick==0));target=state(motion,t+1/30)
            targetmat=R.from_quat(target[3]).as_matrix()
            baseline=None
            profiles=[('current',1,1),('torque2',1,2),('gain2',2,1),('both2',2,2)]
            if confirm:profiles=[('current_refit',1,1),('torque2',1,2),('torso2',1,1),('arms2',1,1)]
            if isolate:profiles=[('current',1,1),('torque2',1,2)]+[(n,1,1) for n in ('torso','right_upper_arm','right_lower_arm','right_hand','left_upper_arm','left_lower_arm','left_hand','left_hand:0','left_hand:1','left_hand:2')]
            if dynamics:profiles=[('current',1,1),('left_hand:0',1,1),('no_contact',1,1),('no_limits',1,1),('no_gravity',1,1),('free',1,1)]
            for tag,gain,torque in profiles:
                e.profile(gain,torque)
                m.opt.disableflags=e.original.opt.disableflags
                if tag in ('no_contact','free'):m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
                if tag in ('no_limits','free'):m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_LIMIT)
                if tag in ('no_gravity','free'):m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_GRAVITY)
                if tag in ('torso2','arms2'):
                    for a,name in zip(e.motors,e.names):
                        if (name=='torso' if tag=='torso2' else ('arm' in name or 'hand' in name)):
                            if m.actuator_forcelimited[a]:m.actuator_forcerange[a]*=2
                            else:m.jnt_actfrcrange[m.actuator_trnid[a,0]]*=2
                if isolate and tag not in ('current','torque2'):
                    for a,name in zip(e.motors,e.names):
                        if name==tag or (':' in tag and name==tag.split(':')[0] and int(np.argmax(abs(m.actuator_gear[a,:3])))==int(tag.split(':')[1])):
                            if m.actuator_forcelimited[a]:m.actuator_forcerange[a]*=2
                            else:m.jnt_actfrcrange[m.actuator_trnid[a,0]]*=2
                maxforce=np.zeros(34);last={}
                def evaluate(x,capture=False):
                    mujoco.mj_resetData(m,d);d.qpos[:]=start[0];d.qvel[:]=start[1]
                    d.ctrl[e.motors]=x*bounds
                    peak=np.zeros(34);duty=np.zeros(34);wrist_trace=[]
                    for _ in range(8):
                        mujoco.mj_step(m,d);force=abs(d.qfrc_actuator[e.dofs]);peak=np.maximum(peak,force)
                        duty+=force>=.99*e._uefn_motors.upper.numpy()
                        if capture:wrist_trace.append(dict(torque=float(d.qfrc_actuator[e.dofs[17]]),velocity=float(d.actuator_velocity[e.motors[17]]),command=float(d.ctrl[e.motors[17]])))
                    mujoco.mj_forward(m,d)
                    pos=d.xpos[bodies].copy();mat=d.xmat[bodies].reshape(-1,3,3)
                    velocity=[];angular=[]
                    for b in bodies:
                        jp=np.zeros((3,m.nv));jr=np.zeros_like(jp);mujoco.mj_jacBody(m,d,jp,jr,b)
                        velocity.append(jp@d.qvel);angular.append(jr@d.qvel)
                    tar=target[2].copy();tar[:,:2]+=pos[0,:2]-tar[0,:2]
                    parts=[pos-tar,np.asarray(velocity)-target[4],mat-targetmat,np.asarray(angular)-target[5]]
                    residual=np.concatenate([p.ravel()*np.sqrt(w/p.size) for p,w in zip(parts,weights)])
                    if capture:
                        last.update(cost=float(residual@residual),max_body_error_cm=float(np.linalg.norm(parts[0],axis=1).max()*100),
                            loss_components=[float(np.mean(p*p)*w) for p,w in zip(parts,weights)],
                            left_wrist_axis0_substeps=wrist_trace,
                            head_height_error_cm=float((pos[2,2]-tar[2,2])*100),
                            head_rise_cm=float((pos[2,2]-start[2][2,2])*100),
                            target_head_rise_cm=float((tar[2,2]-start[2][2,2])*100),
                            peak_torque_nm=peak.tolist(),cap_duty=(duty/8).tolist(),
                            floor_depth_m=max([0.]+[-float(c.dist) for c in d.contact if m.geom_bodyid[c.geom1]==0 or m.geom_bodyid[c.geom2]==0]))
                    return residual
                # A direct joint-error command supplies a stronger seed than zero.
                delta=np.zeros(m.nv);mujoco.mj_differentiatePos(m,delta,1/30,start[0],target[0])
                x0=np.clip(delta[e.dofs]/bounds,-.999,.999) if baseline is None else baseline
                if confirm:
                    x0=np.array(next(s['command'] for s in prior_commands if s['motion']==motion and s['tick']==tick and s['profile']=='torque2'))/bounds
                before=evaluate(x0);fit=least_squares(evaluate,x0,bounds=(-np.ones(34),np.ones(34)),
                    diff_step=2e-4,max_nfev=1 if isolate else 50 if confirm else 28,ftol=2e-4,xtol=2e-4,gtol=2e-4)
                chosen=fit.x if np.linalg.norm(fit.fun)<=np.linalg.norm(before) else x0
                evaluate(chosen,True)
                if tag=='current':baseline=chosen.copy()
                row=dict(motion=motion,tick=tick,profile=tag,nfev=fit.nfev,same_command_cost=float(before@before),**last);rows.append(row)
                solutions.append(dict(motion=motion,tick=tick,profile=tag,command=(chosen*bounds).tolist()))
            print(json.dumps(dict(motion=motion,tick=tick,costs={r['profile']:round(r['cost'],4) for r in rows[-4:]},
                error_cm={r['profile']:round(r['max_body_error_cm'],2) for r in rows[-4:]})),flush=True)
            (OUT/report_file).write_text(json.dumps(dict(rows=rows,seconds=time.time()-begun,complete=False),indent=2))
    (OUT/report_file).write_text(json.dumps(dict(rows=rows,seconds=time.time()-begun,complete=True,max_mapping_error_m=max(mapping_errors),
        note='34 velocity commands optimized independently for each 1/30s interval; free root, contacts and joint limits active. A local optimizer failing is not an impossibility proof.'),indent=2))
    (OUT/commands_file).write_text(json.dumps(solutions))

if __name__=='__main__':main()
