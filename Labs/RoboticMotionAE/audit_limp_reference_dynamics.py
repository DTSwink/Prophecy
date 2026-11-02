"""Optimistic inverse-dynamics feasibility of the actual limp targets.

Uses deployed rigid-body inertias and joint coordinates. Contact forces can be
chosen freely inside generous friction pyramids at all eight collider corners,
including corners above the floor (an optimistic relaxation of real contact).
No contact-speed, actuator-speed, collision or limit restrictions are imposed:
infeasibility is diagnostic, feasibility alone is not a tracking proof. Omits
air drag; finite differences make demand approximate, so report slack too.
"""
import preflight_slow_policy as p
import mujoco,numpy as np,json
from scipy.optimize import linprog
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry

out=p.out/'limp-deep-audit-20261101';g=Geometry();m=mujoco.MjModel.from_binary_path(str(out/'actual-model.mjb'));d=mujoco.MjData(m)
assert m.nv==40 and not m.dof_armature.any() and not m.dof_damping.any()
caps=np.array([200]*3+[50]*3+[100]*3+[70]+[50]*3+[100]*3+[70]+[50]*3+[200]*3+[300]+[180]*3+[200]*3+[300]+[180]*3,float)
report={}
for name,passive in [('limpL',np.arange(27,34)),('limpR',np.arange(20,27))]:
    ref=np.load(out/(name+'-reference.npz'));sample=np.arange(0,len(ref['times']),8);fr=ref['frames'][sample];N=len(fr);dt=1/30
    qs=np.zeros((N,m.nq));qs[:,:3]=fr[:,:3];qs[:,3:7]=ref['root_quat'][sample][:,[3,0,1,2]]
    for body in range(1,15):
        adr=m.jnt_qposadr[body];j=g.k.get_joint(body)
        if j.get_dof_dim()==3:qs[:,adr:adr+4]=ref['joint_quat'][sample,body-1][:,[3,0,1,2]]
        else:qs[:,adr]=fr[:,6+j.dof_idx]
    qv=np.zeros((N,m.nv))
    for t in range(1,N-1):mujoco.mj_differentiatePos(m,qv[t],2*dt,qs[t-1],qs[t+1])
    qv[0]=qv[1];qv[-1]=qv[-2];qa=np.gradient(qv,dt,axis=0)
    results=[]
    for t in range(3,N-3):
        d.qpos[:]=qs[t];d.qvel[:]=qv[t];mujoco.mj_forward(m,d);M=np.empty((40,40));mujoco.mj_fullM(m,M,d.qM);demand=M@qa[t]+d.qfrc_bias
        # Runtime small-angle quaternion interpolation holds its midpoint;
        # MJ normalizes those quaternions. Accept sub-millimetre FK roundoff.
        np.testing.assert_allclose(d.xpos[1:],ref['pos'][sample[t]],atol=2e-4)
        points=[];support=[]
        for footindex,body in enumerate((11,14)):
            if ref['feet'][sample[t],footindex]>.01:continue
            geom=next(j for j,x in enumerate(g.gs) if g.gb[j]==body);sz=g.gs[geom]['size'];rot=R.from_quat(ref['quat'][sample[t],body]).as_matrix()
            for sx,sy,szsign in [(x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1)]:
                point=d.xpos[body+1]+rot@(g.gp[geom]+g.gr[geom]@np.array([sx*sz[0],sy*sz[1],szsign*sz[2]]));jac=np.zeros((3,40));mujoco.mj_jac(m,d,jac,None,point,body+1);points.append(jac.T);support.append(body)
        J=np.concatenate(points,axis=1) if points else np.zeros((40,0));nf=J.shape[1];A=np.c_[J,np.eye(40)[:,6:]];B=[]
        for k in range(nf//3):
            for axis in (0,1):
                for sign in (-1,1):
                    b=np.zeros(nf+34);b[3*k+axis]=sign;b[3*k+2]=-1.;B.append(b)
        ub=np.array(B).reshape(-1,nf+34);fb=[(None,None),(None,None),(0,None)]*(nf//3)
        def solve(mode):
            cc=caps.copy()
            if mode=='passive':cc[passive]=0
            if mode in ('huge_support','passive_ankle_free'):cc[:]=10000;cc[passive]=0
            if mode=='passive_ankle_free':cc[passive[4:]]=10000
            tb=[(-v,v) for v in cc]
            # L1 slack quantifies generalized residual in N (root translation)
            # and Nm (rotation/joints); weights scale force by a 1m lever arm.
            aa=np.c_[A,np.eye(40),-np.eye(40)]
            u=np.c_[ub,np.zeros((len(ub),80))]
            opt=linprog(np.r_[np.zeros(nf+34),np.ones(80)],A_ub=u,b_ub=np.zeros(len(ub)),A_eq=aa,b_eq=demand,bounds=fb+tb+[(0,None)]*80,method='highs')
            assert opt.success
            residual=A@opt.x[:nf+34]-demand
            return dict(residual_l1=float(opt.fun),passive_residual_nm=abs(residual[6+passive]).tolist(),base_force_residual_n=abs(residual[:3]).tolist(),motor_torques_nm=opt.x[nf:nf+34].tolist())
        results.append(dict(frame=int(sample[t]/8),time=float(ref['times'][sample[t]]),support_bodies=support[::8],joint_limit_violations=g.limits(fr[t]),passive=solve('passive'),huge_support=solve('huge_support'),passive_ankle_free=solve('passive_ankle_free'),both_powered=solve('both_powered')))
    report[name]=dict(method=__doc__,frames=results,summary={mode:dict(feasible_within_1_unit=sum(x[mode]['residual_l1']<1 for x in results),median_residual_l1=float(np.median([x[mode]['residual_l1'] for x in results])),max_residual_l1=max(x[mode]['residual_l1'] for x in results)) for mode in ['passive','huge_support','passive_ankle_free','both_powered']})
(out/'reference-dynamics.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v['summary'] for k,v in report.items()},indent=2))
