"""Contact-constrained inverse dynamics SCREEN, not a playback or controller.

No state is advanced, no force is applied to a simulator. Tests whether forces
could instantaneously support reference acceleration. Feet within a stated gap
may provide unilateral frictional support: this is explicitly optimistic and
does not prove that the engine's actual contact impulses realize the solution.
"""
import json,time,itertools
from pathlib import Path
import numpy as np
import torch
import mujoco
from scipy.optimize import linprog,lsq_linear


class Dynamics:
    def __init__(self,env):
        self.env=env;self.e=env._engine;self.m=self.e._solver.mj_model
        self.d=mujoco.MjData(self.m);self.kin=env._kin_char_model
        self.names=self.kin.get_body_names()
        self.bids=[next(i for i in range(1,self.m.nbody) if self.m.body(i).name.endswith(n)) for n in self.names]
        self.dofs=self.e._uefn_motors.dof_ids
        self.caps=self.e._uefn_motors.upper.numpy();self.gains=self.e._uefn_motors.gains.numpy()
        self.props=json.loads((self.e._uefn_directory/'physics.json').read_text())['bodies']
        self.act=np.eye(self.m.nv)[:,self.dofs]
        self.feet=[g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] in [self.bids[self.names.index(n)] for n in ['right_foot','left_foot']]]
        self.mass=np.zeros((self.m.nv,self.m.nv))
        assert self.m.nv==40 and len(self.dofs)==34
        self.max_fk_error=0.

    def poses(self,motion,times):
        times=torch.as_tensor(times,dtype=torch.float32,device=self.env._device)
        ids=torch.full(times.shape,int(motion),device=times.device,dtype=torch.long)
        values=self.env._motion_lib.calc_motion_frame(ids,times)
        root,rot,_,_,joint,_=values
        dof=self.kin.rot_to_dof(joint).cpu().numpy()
        out=np.tile(self.m.qpos0,(len(times),1))
        out[:,:3]=root.cpu().numpy();out[:,3:7]=np.roll(rot.cpu().numpy(),1,axis=-1)
        jrots=joint.cpu().numpy()
        for k,b in enumerate(self.bids[1:],1):
            j=self.m.body_jntadr[b];start=self.m.jnt_qposadr[j]
            if self.m.jnt_type[j]==mujoco.mjtJoint.mjJNT_BALL:out[:,start:start+4]=np.roll(jrots[:,k-1],1,axis=-1)
            else:
                assert self.m.jnt_type[j]==mujoco.mjtJoint.mjJNT_HINGE
                out[:,start]=dof[:,self.kin.get_joint(k).dof_idx]
        # Independently verify generalized-coordinate mapping against training FK.
        expected=self.kin.forward_kinematics(root,rot,joint)[0].cpu().numpy()
        for k in range(len(times)):
            self.d.qpos[:]=out[k];mujoco.mj_kinematics(self.m,self.d)
            self.max_fk_error=max(self.max_fk_error,float(np.max(np.abs(expected[k]-self.d.xpos[self.bids]))))
        # The deployed float32 rotation->hinge conversion has a small-angle
        # dead zone. Record its actual spatial error; reject mapping mistakes.
        assert self.max_fk_error<5e-4,self.max_fk_error
        return out

    def reference(self,motion,time,dt=1/30):
        # A finite control-interval acceleration, not a claim of a smooth
        # derivative at every knot in the piecewise interpolated motion.
        poses=self.poses(motion,[time-dt,time,time+dt])
        before=np.zeros(self.m.nv);after=before.copy()
        mujoco.mj_differentiatePos(self.m,before,dt,poses[0],poses[1])
        mujoco.mj_differentiatePos(self.m,after,dt,poses[1],poses[2])
        return poses[1],(before+after)*.5,(after-before)/dt

    def required(self,pos,vel,acc):
        m,d=self.m,self.d;d.qpos[:]=pos;d.qvel[:]=vel
        mujoco.mj_forward(m,d);mujoco.mj_fullM(m,self.mass,d.qM)
        external=np.zeros(m.nv)
        for name,b in zip(self.names,self.bids):
            row=self.props[name];r=d.xmat[b].reshape(3,3)
            jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jacBodyCom(m,d,jp,jr,b)
            v=jp@vel;w=jr@vel;s=r@row['drag_first']
            force=-row['drag_mass']*v-np.cross(w,s)
            torque=-np.cross(s,v)-r@np.array(row['drag_second'])@r.T@w+np.cross(w,r@np.array(row['inertia'])@r.T@w)
            external+=jp.T@force+jr.T@torque
        # No MuJoCo constraint or actuator force is included: they are the
        # unknowns. Joint passive springs/damping must be absent in this runtime.
        assert np.max(np.abs(d.qfrc_passive))<1e-7,np.max(np.abs(d.qfrc_passive))
        return self.mass@acc+d.qfrc_bias-external

    def support(self,gap):
        m,d=self.m,self.d;columns=[];points=[];heights=[]
        for g in self.feet:
            assert m.geom_type[g]==mujoco.mjtGeom.mjGEOM_BOX
            r=d.geom_xmat[g].reshape(3,3)
            corners=np.array(list(itertools.product([-1,1],repeat=3)))*m.geom_size[g]
            world=corners@r.T+d.geom_xpos[g]
            heights.append(float(world[:,2].min()))
            for point in world[world[:,2]<=gap]:
                jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jac(m,d,jp,jr,point,int(m.geom_bodyid[g]))
                # Circumscribed 8-ray friction cone: optimistic by <=8.24%.
                # The deployed MJ pair mix takes the maximum geom friction.
                floor=[i for i in range(m.ngeom) if m.geom_type[i]==mujoco.mjtGeom.mjGEOM_PLANE]
                assert len(floor)==1
                mu=max(m.geom_friction[g,0],m.geom_friction[floor[0],0])
                for angle in np.arange(8)*np.pi/4:
                    ray=np.array([mu*np.cos(angle)/np.cos(np.pi/8),mu*np.sin(angle)/np.cos(np.pi/8),1.])
                    columns.append(jp.T@ray)
                points.append(point.tolist())
        return np.array(columns).T if columns else np.zeros((m.nv,0)),points,heights

    def solve(self,required,gap,vel):
        support,points,heights=self.support(gap)
        ns=support.shape[1];na=len(self.caps)
        # Minimize a single multiplier of motor caps, enforcing all 40 equations
        # of motion, including the unactuated pelvis. No fictitious root wrench.
        Aeq=np.column_stack([self.act*self.caps,support,np.zeros(self.m.nv)])
        Aub=np.zeros((2*na,na+ns+1));Aub[:na,:na]=np.eye(na);Aub[na:,:na]=-np.eye(na);Aub[:,-1]=-1
        c=np.zeros(na+ns+1);c[-1]=1
        result=linprog(c,A_ub=Aub,b_ub=np.zeros(2*na),A_eq=Aeq,b_eq=required,
            bounds=[(None,None)]*na+[(0,None)]*(ns+1),method='highs')
        row=dict(feasible=bool(result.success),foot_min_z=heights,support_points=len(points),status=int(result.status),gap=gap)
        if result.success:
            torque=result.x[:na]*self.caps
            row.update(cap_multiplier=float(result.x[-1]),torque=torque.tolist(),
                needed_command=(vel[self.dofs]+torque/self.gains).tolist(),
                equation_residual=float(np.max(np.abs(Aeq@result.x-required))))
        return row

    def validate(self):
        gravity=self.required(self.m.qpos0,np.zeros(self.m.nv),np.zeros(self.m.nv))
        expected=-self.m.opt.gravity*self.m.body_mass.sum()
        np.testing.assert_allclose(gravity[:3],expected,atol=1e-7)
        assert np.linalg.eigvalsh(self.mass)[0]>0
        _,_,heights=self.support(.002)
        gap=max(heights)+.2
        support,_,_=self.support(gap)
        assert support.shape[1]>0
        torque=.25*self.caps*np.sin(np.arange(34))
        force=self.act@torque+support@np.full(support.shape[1],10.)
        known=self.solve(force,gap,np.zeros(self.m.nv))
        assert known['feasible'] and known['cap_multiplier']<=.25+1e-6,known
        force[2]=-abs(force[2])
        impossible=self.solve(force,gap,np.zeros(self.m.nv))
        assert not impossible['feasible']
        return dict(gravity_force_n=gravity[:3].tolist(),mass_kg=float(self.m.body_mass.sum()),
            known_supported_force_reconstructed=True,negative_ground_normal_rejected=True,
            geom_friction=self.m.geom_friction.tolist(),explicit_contact_pairs=int(self.m.npair))


def screen(env,selected,names,result,args):
    begun=time.perf_counter();dyn=Dynamics(env);validation=dyn.validate();rows=[]
    for mid in selected:
        length=float(env._motion_lib.get_motion_lengths()[mid]);samples=max(8,round(length*30))
        phases=np.arange(samples)/samples
        for phase in phases:
            # Second cycle avoids negative-time ambiguity at phase zero.
            pos,vel,acc=dyn.reference(mid,length*(1+phase))
            required=dyn.required(pos,vel,acc)
            rows.append(dict(motion=names[mid],phase=float(phase),required_root_wrench=required[:6].tolist(),
                screens=[dyn.solve(required,gap,vel) for gap in [.002,.02]]))
        print('SCREEN',names[mid],samples,flush=True)
    summary=[]
    for name in [names[i] for i in selected]:
        group=[r for r in rows if r['motion']==name]
        stats=[]
        for idx,gap in enumerate([.002,.02]):
            values=[r['screens'][idx] for r in group];feasible=[v for v in values if v['feasible']]
            stats.append(dict(gap=gap,samples=len(values),support_feasible=len(feasible),
                within_caps=sum(v['cap_multiplier']<=1+1e-6 for v in feasible),
                cap_multiplier_quantiles=np.quantile([v['cap_multiplier'] for v in feasible],[.5,.9,1]).tolist() if feasible else []))
        summary.append(dict(motion=name,stats=stats))
    report=dict(summary=summary,rows=rows,validation=validation,elapsed_seconds=time.perf_counter()-begun,
        max_fk_error=dyn.max_fk_error,settings=vars(args),
        method='Finite-30Hz-interval reference acceleration, full floating-root dynamics, unilateral optimistic foot support and circumscribed friction cone. Minimum motor torque-cap multiplier.',
        limitations='Screen only. Near-floor points may support before actual collision. Does not enforce contact acceleration/complementarity or joint-limit reactions. Exact reference feasibility is stricter than 27cm training tolerance. No successful physical playback is implied.')
    result.write_text(json.dumps(report,indent=2));print('SUMMARY',json.dumps(summary),flush=True)


class WholeBodyController:
    """Diagnostic bounded inverse-dynamics feedback with real forward physics.

The optimization predicts supporting forces but NEVER applies them. Its only
output is the same 34 velocity commands accepted by the real training motors.
"""
    def __init__(self,env):
        self.env=env;self.dyn=Dynamics(env);self.e=env._engine
        self.steps=[]

    def command(self,active,tick):
        env=self.env;e=self.e;dyn=self.dyn;m=dyn.m
        e._sim_state.pre_step_update()
        e._solver._update_mjc_data(e._solver.mjw_data,e._sim_model,e._sim_state.raw_state)
        positions=e._solver.mjw_data.qpos.numpy();velocities=e._solver.mjw_data.qvel.numpy()
        motions=env._motion_ids.cpu().numpy();times=env._get_motion_times().cpu().numpy()
        enabled=active.cpu().numpy();cmd=np.zeros((len(motions),34))
        for world in np.flatnonzero(enabled):
            pos=positions[world].astype(float);vel=velocities[world].astype(float)
            ref,rv,ra=dyn.reference(motions[world],float(times[world])+float(env._motion_lib.get_motion_lengths()[motions[world]]))
            # Same horizontal following as training targets; no positional
            # demand to return to an authored world-space origin.
            ref[:2]=pos[:2]
            error=np.zeros(m.nv);mujoco.mj_differentiatePos(m,error,1.,pos,ref)
            kp=np.full(m.nv,100.);kd=np.full(m.nv,20.)
            kp[:6]=80.;kd[:6]=18.
            desired=ra+kp*error+kd*(rv-vel)
            bias=dyn.required(pos,vel,np.zeros(m.nv))
            support,points,_=dyn.support(.02)
            nc=support.shape[1]
            forces=np.column_stack((dyn.act*dyn.caps,support*200.))
            response=np.linalg.solve(dyn.mass,forces);free=np.linalg.solve(dyn.mass,-bias)
            weight=np.ones(m.nv);weight[:3]=10.;weight[3:6]=5.
            A=weight[:,None]*response;b=weight*(desired-free)
            # Keep a loaded stance foot from accelerating through the floor.
            # This is only an objective; the real contacts enforce nonpenetration.
            for point in points:
                # Retrieve closest supporting foot for the point Jacobian.
                g=min(dyn.feet,key=lambda g:np.linalg.norm(dyn.d.geom_xpos[g]-point))
                jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jac(m,dyn.d,jp,jr,np.asarray(point),int(m.geom_bodyid[g]))
                speed=jp@vel;desired_contact=-20*speed
                desired_contact[2]-=200*min(point[2],0.)
                A=np.vstack((A,3*jp@response));b=np.r_[b,3*(desired_contact-jp@free)]
            A=np.vstack((A,.01*np.eye(forces.shape[1])));b=np.r_[b,np.zeros(forces.shape[1])]
            fit=lsq_linear(A,b,bounds=(np.r_[-np.ones(34),np.zeros(nc)],np.r_[np.ones(34),np.full(nc,np.inf)]),method='bvls',tol=1e-6,max_iter=200)
            torque=fit.x[:34]*dyn.caps
            acceleration=free+response@fit.x
            cmd[world]=vel[dyn.dofs]+acceleration[dyn.dofs]/60+torque/dyn.gains
            self.steps.append(dict(world=int(world),tick=tick,fit_success=bool(fit.success),torque_max_fraction=float(np.max(np.abs(fit.x[:34]))),support_points=len(points)))
        return torch.as_tensor(cmd,dtype=torch.float32,device=env._device)
