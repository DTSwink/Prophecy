"""CPU static-equilibrium audit of the exported standing reference.

Uses exact foot box corners, Coulomb contact forces and PHAT locked-axis
reactions. This checks motor strength at one pose, not dynamic get-up ability.
"""
import itertools
import argparse
import json
import numpy as np
import mujoco
from scipy.optimize import linprog, least_squares
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from joint_pd import OUT, motor_gains_for


def coords(q):
    w,x,y,z=q;n=np.hypot(w,x)
    return np.array([(2*np.arctan2(x,w)+np.pi)%(2*np.pi)-np.pi,
                     (w*y-x*z)/n,(x*y+w*z)/n])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pelvis-height',type=float)
    parser.add_argument('--output',default='standing-strength-audit');args=parser.parse_args()
    meta=json.loads((OUT/'uefn.json').read_text())
    model=mujoco.MjModel.from_xml_path(str(OUT/'uefn.xml'));data=mujoco.MjData(model)
    data.qpos[:]=meta['reference_qpos'];mujoco.mj_forward(model,data)
    foot_adjustments={}
    # The reference soles tilt ~0.66deg. For a meaningful strength check,
    # flatten them using only the two authored ankle axes. This diagnostic
    # pose does not change the asset, training reset or reward reference.
    for name in ('foot_l','foot_r'):
        j=next(j for j in meta['joints'] if j['body']==name)
        ja=model.joint(j['name']).id;qa=model.jnt_qposadr[ja]
        geom=model.geom(name+'_shape0').id;before=data.qpos[qa:qa+4].copy()
        sign=np.sign(data.geom_xmat[geom].reshape(3,3)[2,0])
        def residual(x):
            data.qpos[qa:qa+4]=[np.sqrt(1-x@x),0,*x]
            mujoco.mj_kinematics(model,data)
            return data.geom_xmat[geom].reshape(3,3)[:2,0]*sign
        bounds=np.sin(np.array(j['limits_rad'][1:])/2)
        fit=least_squares(residual,coords(before)[1:],bounds=(-bounds,bounds),gtol=1e-13,xtol=1e-13,ftol=1e-13)
        residual(fit.x)
        assert np.linalg.norm(fit.x/bounds)<=1 and np.linalg.norm(fit.fun)<1e-9
        after=data.qpos[qa:qa+4]
        foot_adjustments[name]=float(np.rad2deg(2*np.arccos(np.clip(abs(before@after),0,1))))
    squat_fit=None
    if args.pelvis_height is not None:
        mujoco.mj_forward(model,data)
        geoms=[model.geom(n+'_shape0').id for n in ('foot_l','foot_r')]
        target_positions=data.geom_xpos[geoms].copy();target_rotations=Rotation.from_matrix(data.geom_xmat[geoms].reshape(-1,3,3))
        base=data.qpos.copy();root=Rotation.from_quat(base[[4,5,6,3]]);entries=[];start=[base[0],base[1],0.];lower=[-1.,-1.,-1.2];upper=[1.,1.,1.2]
        pitch_axis=data.xmat[model.body('calf_l').id].reshape(3,3)[:,2].copy()
        leg_joints=[j for j in meta['joints'] if j['body'].startswith(('thigh','calf','foot'))]
        for j in leg_joints:
            qa=int(model.joint(j['name']).qposadr[0]);value=coords(base[qa:qa+4])
            for axis,mode in enumerate(j['modes']):
                if mode==2:continue
                limit=j['limits_rad'][axis] if axis==0 else np.sin(j['limits_rad'][axis]/2)
                entries.append((j,qa,axis));start.append(value[axis]);lower.append(-limit);upper.append(limit)
        initial=np.array(start);solution=initial.copy()
        def apply(x,height):
            data.qpos[:]=base;data.qpos[:3]=[x[0],x[1],height]
            data.qpos[3:7]=(Rotation.from_rotvec(pitch_axis*x[2])*root).as_quat()[[3,0,1,2]]
            values={j['body']:np.zeros(3) for j in leg_joints}
            for (j,qa,axis),value in zip(entries,x[3:]):values[j['body']][axis]=value
            excess=[]
            for j in leg_joints:
                qa=int(model.joint(j['name']).qposadr[0]);c=values[j['body']]
                radius=np.linalg.norm(c[1:]/np.sin(np.asarray(j['limits_rad'][1:])/2));excess.append(max(0,radius-1))
                if c[1:]@c[1:]>=1:raise ValueError('Invalid swing coordinates')
                swing=Rotation.from_quat([0,*c[1:],np.sqrt(1-c[1:]@c[1:])]);twist=Rotation.from_rotvec([c[0],0,0])
                data.qpos[qa:qa+4]=(swing*twist).as_quat()[[3,0,1,2]]
            mujoco.mj_forward(model,data)
            return np.array(excess)
        def residual(x,height):
            excess=apply(x,height)
            rotations=Rotation.from_matrix(data.geom_xmat[geoms].reshape(-1,3,3))
            return np.r_[10*(data.geom_xpos[geoms]-target_positions).ravel(),(target_rotations.inv()*rotations).as_rotvec().ravel(),
                         5*(data.subtree_com[1,:2]-target_positions[:,:2].mean(0)),20*excess,.002*(x-initial)]
        for height in np.linspace(base[2],args.pelvis_height,max(2,int(abs(base[2]-args.pelvis_height)/.05)+1)):
            fit=least_squares(residual,solution,args=(height,),bounds=(lower,upper),max_nfev=200,ftol=1e-10,gtol=1e-10,xtol=1e-10)
            solution=fit.x
        excess=apply(solution,args.pelvis_height)
        pos_error=float(np.linalg.norm(data.geom_xpos[geoms]-target_positions,axis=1).max())
        angle_error=float((target_rotations.inv()*Rotation.from_matrix(data.geom_xmat[geoms].reshape(-1,3,3))).magnitude().max())
        squat_fit={'pelvis_height_m':args.pelvis_height,'pelvis_pitch_axis_world':pitch_axis.tolist(),'foot_position_error_m':pos_error,'foot_rotation_error_deg':float(np.rad2deg(angle_error)),
            'limit_normalized_excess':float(excess.max()),'max_self_penetration_m':float(max((-c.dist for c in data.contact if all(g>0 for g in c.geom)),default=0))}
        if pos_error>.001 or angle_error>.005 or excess.max()>.001:
            report={'feasible':False,'reason':'No acceptable planted-foot pose found by this local optimizer','squat_fit':squat_fit,'rig_sha256':meta['rig_sha256']}
            (OUT/(args.output+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return
    mujoco.mj_forward(model,data)
    support=[];columns=[];bounds=[];names=[];locked=[]
    for name in ('foot_l','foot_r'):
        geom=model.geom(name+'_shape0').id;body=model.geom_bodyid[geom]
        points=np.array(list(itertools.product((-1,1),repeat=3)))*model.geom_size[geom]
        points=points@data.geom_xmat[geom].reshape(3,3).T+data.geom_xpos[geom]
        for p in points:
            # Only corners lying on the common ground plane can support weight.
            if p[2]>points[:,2].min()+.0001:continue
            support.append(p)
            jp=np.zeros((3,model.nv));jr=jp.copy();mujoco.mj_jac(model,data,jp,jr,p,body)
            columns.extend(jp);bounds.extend([(None,None),(None,None),(0,None)])
    nforces=len(columns)
    for j in meta['joints']:
        joint=model.joint(j['name']).id;da=model.jnt_dofadr[joint]
        q=data.qpos[model.jnt_qposadr[joint]:model.jnt_qposadr[joint]+4];base=Rotation.from_quat(q[[1,2,3,0]])
        gradient=np.empty((3,3));h=1.e-6
        for axis in range(3):
            delta=np.eye(3)[axis]*h
            a=(base*Rotation.from_rotvec(delta)).as_quat()[[3,0,1,2]]
            b=(base*Rotation.from_rotvec(-delta)).as_quat()[[3,0,1,2]]
            gradient[:,axis]=(coords(a)-coords(b))/(2*h)
        for axis,mode in enumerate(j['modes']):
            if mode==2:
                col=np.zeros(model.nv);col[da:da+3]=gradient[axis]
                columns.append(col);bounds.append((None,None));locked.append(j['body']+':'+str(axis))
    nmotor_start=len(columns);caps=[]
    for j in meta['joints']:
        joint=model.joint(j['name']).id;da=model.jnt_dofadr[joint]
        for axis,mode in enumerate(j['modes']):
            if mode==2:continue
            col=np.zeros(model.nv);col[da+axis]=1
            columns.append(col);bounds.append((None,None))
            caps.append(motor_gains_for(j['body'])[2]/np.sqrt(3))
            names.append(j['body']+':'+str(axis))
    # Final variable is maximum motor-cap utilization, minimized by the LP.
    A=np.array(columns).T;A=np.column_stack((A,np.zeros(model.nv)))
    inequalities=[]
    for start in range(0,nforces,3):
        # Inscribed eight-sided friction cone: conservative vs circular cone.
        for theta in np.linspace(0,2*np.pi,8,endpoint=False):
            row=np.zeros(A.shape[1]);row[start:start+3]=[np.cos(theta),np.sin(theta),-.7*np.cos(np.pi/8)]
            inequalities.append(row)
    for k,cap in enumerate(caps):
        for sign in (-1,1):
            row=np.zeros(A.shape[1]);row[nmotor_start+k]=sign;row[-1]=-cap;inequalities.append(row)
    objective=np.zeros(A.shape[1]);objective[-1]=1
    result=linprog(objective,A_ub=inequalities,b_ub=np.zeros(len(inequalities)),
                   A_eq=A,b_eq=data.qfrc_bias,bounds=bounds+[(0,None)],method='highs')
    support=np.array(support);hull=ConvexHull(support[:,:2]);com=data.subtree_com[1].copy()
    report={'rig_sha256':meta['rig_sha256'],'feasible':bool(result.success),
            'scope':'Static reference with soles flattened using authored ankle axes; exact lowest foot corners, friction 0.7 conservative polygon, locked-joint reactions. No dynamic recovery claim.',
            'ankle_rotation_to_flatten_degrees':foot_adjustments,
            'support_points_m':support.tolist(),'com_m':com.tolist(),
            'com_inside_support':bool(np.all(hull.equations[:,:2]@com[:2]+hull.equations[:,2]<=1e-8)),
            'solver_message':result.message}
    if squat_fit is not None:
        report['squat_fit']=squat_fit
        report['scope']='Optimized planted-foot squat within original PHAT limits; conservative friction support, no dynamics or recovery claim. Self-penetration is reported separately.'
    if result.success:
        ratios=np.abs(result.x[nmotor_start:-1])/caps
        report.update(max_motor_utilization=float(result.x[-1]),balance_residual=float(np.abs(A@result.x-data.qfrc_bias).max()),
            highest_motor_utilizations=sorted(zip(names,ratios.tolist()),key=lambda x:-x[1])[:10])
    (OUT/(args.output+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
