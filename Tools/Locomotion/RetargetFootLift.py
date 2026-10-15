"""Independent vertical foot correction with a fixed hip and preserved pole.

Solves the asset's actual hinge/rest frames, including non-collinear offsets.
No pelvis adjustment, horizontal foot movement or bone stretch.
"""
import numpy as np
from scipy.spatial.transform import Rotation as R


def unit(v):
    length=np.linalg.norm(v)
    if length<1e-10:raise ValueError('Degenerate leg/pole; refusing an arbitrary bend direction')
    return v/length


def solve_leg(hip,knee,foot,target,upper_offset,lower_offset,knee_rest,axis,current_angle):
    """Return hip rotation, hinge angle, shin rotation and desired knee point."""
    hip,knee,foot,target,upper_offset,lower_offset,knee_rest,axis=[np.asarray(x,dtype=np.float64) for x in (hip,knee,foot,target,upper_offset,lower_offset,knee_rest,axis)]
    axis=unit(axis);distance=np.linalg.norm(target-hip)
    # Exact hip-to-foot distance of this hinge chain: C+A*cos(q)+B*sin(q).
    axial=axis*np.dot(axis,lower_offset);perp=lower_offset-axial
    c=np.dot(upper_offset,upper_offset)+np.dot(lower_offset,lower_offset)+2*np.dot(upper_offset,knee_rest@axial)
    a=2*np.dot(upper_offset,knee_rest@perp)
    b=2*np.dot(upper_offset,knee_rest@np.cross(axis,lower_offset))
    radius=np.hypot(a,b);value=(distance**2-c)/radius
    if abs(value)>1+1e-9:raise ValueError(f'Raised foot is unreachable: hinge cosine {value}')
    phi=np.arctan2(b,a);delta=np.arccos(np.clip(value,-1,1))
    candidates=np.array([phi+delta,phi-delta])
    candidates=current_angle+(candidates-current_angle+np.pi)%(2*np.pi)-np.pi
    angle=candidates[np.argmin(abs(candidates-current_angle))]
    old_direction=unit(foot-hip)
    old_pole=unit((knee-hip)-old_direction*np.dot(knee-hip,old_direction))
    direction=unit(target-hip)
    pole=unit(old_pole-direction*np.dot(old_pole,direction))
    hinge=knee_rest@R.from_rotvec(axis*angle).as_matrix()
    total=upper_offset+hinge@lower_offset
    local_direction=unit(total)
    local_pole=unit(upper_offset-local_direction*np.dot(upper_offset,local_direction))
    source=np.column_stack((local_direction,local_pole,np.cross(local_direction,local_pole)))
    dest=np.column_stack((direction,pole,np.cross(direction,pole)))
    hip_rotation=dest@source.T
    knee_position=hip+hip_rotation@upper_offset
    np.testing.assert_allclose(knee_position+hip_rotation@hinge@lower_offset,target,atol=1e-8)
    return hip_rotation,float(angle),hip_rotation@hinge,knee_position


def box_bottom(position,rotation,local_position,local_rotation,size):
    center=position+rotation@local_position
    return center[2]-np.abs((rotation@local_rotation)[2])@size


def lift_feet(model,names,meta,wanted,positions,rotations,dof):
    """Remove only extra floor penetration introduced by the reduction."""
    local_rot=R.from_quat(model._local_rotation.numpy()).as_matrix()
    local_pos=model._local_translation.numpy()
    rows=[]
    for side in ('right','left'):
        hi,ki,fi=[names.index(side+'_'+part) for part in ('thigh','shin','foot')]
        hj,kj,fj=[model.get_joint(j) for j in (hi,ki,fi)]
        frame=meta['body_frames'][side+'_foot']
        body_rest=R.from_quat(frame['quaternion']).as_matrix()
        geom=next(g for g in meta['geometry'] if g['body']==side+'_foot')
        assert geom['type']=='box'
        gp=body_rest.T@(np.array(geom['position'])-frame['position'])
        gr=body_rest.T@R.from_quat(geom['quaternion']).as_matrix();size=np.array(geom['size'])
        for tick in range(len(dof)):
            pos=positions[tick];rot=rotations[tick]
            original=box_bottom(wanted[tick,fi,:3,3],wanted[tick,fi,:3,:3],gp,gr,size)
            before=box_bottom(pos[fi],rot[fi],gp,gr,size)
            lift=max(0.,min(original,0.)-before)
            if lift<1e-8:continue
            target=pos[fi].astype(np.float64).copy();target[2]+=lift
            try:
                hr,angle,kr,kp=solve_leg(pos[hi],pos[ki],pos[fi],target,local_pos[ki],local_pos[fi],local_rot[ki],kj.axis.numpy(),dof[tick,kj.dof_idx])
            except ValueError as e:raise ValueError(f'{side} leg tick {tick}: {e}') from e
            parent=int(model._parent_indices[hi])
            dof[tick,hj.dof_idx:hj.dof_idx+3]=R.from_matrix(local_rot[hi].T@rot[parent].T@hr).as_rotvec()
            dof[tick,kj.dof_idx]=angle
            dof[tick,fj.dof_idx:fj.dof_idx+3]=R.from_matrix(local_rot[fi].T@kr.T@rot[fi]).as_rotvec()
            rows.append(dict(side=side,tick=tick,lift_cm=lift*100,
                             target=target.tolist(),knee=kp.tolist()))
    return rows
