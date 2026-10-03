"""Foot-local pole, fixed-length leg feedback using the existing native IK/FK.

The 41D controller stores thigh orientation, not knee coordinates. Write the
solved thigh rotation back into that state so inference and rendering agree.
No separate animated foot, calf scale, pose cache, or screen-space repair.
"""
import math
import torch
from transition_agents import native
from dodge_movement_banks import horizontal_world

LEG_CONTRACT='fixed_length_foot_local_swing_reach_projection_v4'
FOOT_FLOOR_CONTRACT='final_world_foot_toe_box_floor_fixed_length_foot_local_pole_v1'
FOOT_FLOOR_MARGIN_M=1e-5


def configure_hinge_fk(skeleton):
    """Explicit per-runtime opt-in; existing trainers keep their exact codec."""
    skeleton.runtime.lower_clip.leg_rotation_contract='signed_hinge_normal_v1'
    skeleton.runtime.full_clip.leg_rotation_contract='signed_hinge_normal_v1'

def foot_local_hinge_pole(source_axis,source_bend,source_foot_axes,target_axis,target_foot_axes):
    """Swing the foot-local knee frame onto the requested chain direction.

    Same minimal-swing convention as native swing_only_transport, expressed
    without acos so identity has finite backward derivatives. No forbidden
    cone around the foot-local hinge. At the exact antipode, use the original
    knee hinge for the half turn (the shortest swing axis is not unique).
    """
    tl=native.tl
    hinge=tl.normalize(torch.cross(source_axis,source_bend,dim=-1))
    change=source_foot_axes.transpose(-1,-2)@target_foot_axes
    carried=(hinge.unsqueeze(-2)@change).squeeze(-2)
    a=tl.normalize((source_axis.unsqueeze(-2)@change).squeeze(-2))
    p=tl.project_to_plane((source_bend.unsqueeze(-2)@change).squeeze(-2),a)
    b=tl.normalize(target_axis)
    c=(a*b).sum(-1,keepdim=True).clamp(-1.,1.)
    # For p perpendicular to a, the Rodrigues result simplifies to this.
    regular=p-(p*b).sum(-1,keepdim=True)*(a+b)/(1.+c).clamp_min(1e-6)
    transported=torch.where(c < -1.+1e-6,-p,regular)
    pole=tl.project_to_plane(transported,b)
    return pole,carried,torch.ones_like(c[...,0],dtype=torch.bool)


def reachable_ankle(hip,target,l1,l2,fallback_axis):
    """Project only the endpoint radius; never reject the complete pose."""
    raw=target-hip;distance=torch.linalg.vector_norm(raw,dim=-1,keepdim=True)
    axis=torch.where(distance>1e-8,raw/distance.clamp_min(1e-8),fallback_axis)
    radius=torch.maximum(torch.minimum(distance,(l1+l2)[...,None]-2e-5),
        (l1-l2).abs()[...,None]+2e-5)
    return hip+axis*radius


def foot_box_lowest_y(store,limb_index,ankle,rotation,toe):
    """Exact eight-corner minimum of the existing rendered foot AND toe boxes.

    Reuse the native foot geometry, but not its smoothed rolling-contact point:
    that point can sit above the lowest box corner. Inputs are in WORLD space.
    """
    ctl=native.ik_ctl
    fc,ff,fs,fu,tc,tf,ts,tu=ctl._foot_toe_box_axes(store,limb_index,ankle,rotation,toe,up_axis=1)
    fh=store.foot_roll_foot_half_dims.to(dtype=ankle.dtype,device=ankle.device)
    th=store.foot_roll_toe_half_dims.to(dtype=ankle.dtype,device=ankle.device)
    foot=fc[...,1]-(torch.stack((ff,fs,fu),-2)[...,1].abs()*fh).sum(-1)
    ball=tc[...,1]-(torch.stack((tf,ts,tu),-2)[...,1].abs()*th).sum(-1)
    return torch.minimum(foot,ball)


def floor_reachable_ankle(hip,ankle,l1,l2,fallback_axis,minimum_y):
    """Lift an already reach-clamped endpoint; constrain reach on the floor plane.

    Unlike lift->radial-clamp, this cannot pull the foot below the floor again.
    The anatomy/pelvis-height constraints guarantee the plane intersects reach.
    Safe endpoints are returned bit-for-bit. No remembered rejected target.
    """
    below=ankle[...,1]<minimum_y
    dy=minimum_y-hip[...,1]
    # A strided view is graph-safe; a tuple index builds a CPU index tensor.
    horizontal=ankle[..., ::2]-hip[..., ::2]
    radius=torch.linalg.vector_norm(horizontal,dim=-1,keepdim=True)
    backup=fallback_axis[..., ::2]
    backup_length=torch.linalg.vector_norm(backup,dim=-1,keepdim=True)
    unit_x=torch.stack((torch.ones_like(dy),torch.zeros_like(dy)),-1)
    backup=torch.where(backup_length>1e-8,backup/backup_length.clamp_min(1e-8),unit_x)
    direction=torch.where(radius>1e-8,horizontal/radius.clamp_min(1e-8),backup)
    low2=((l1-l2).abs()+2e-5).square()-dy.square()
    high2=(l1+l2-2e-5).square()-dy.square()
    # Guard the inactive sqrt derivative at zero (including exact full reach).
    low=torch.where(low2>0,low2.clamp_min(1e-12).sqrt(),torch.zeros_like(low2))
    high=high2.clamp_min(1e-12).sqrt()
    clamped=torch.maximum(torch.minimum(radius,high[...,None]),low[...,None])
    xz=hip[..., ::2]+direction*clamped
    lifted=torch.stack((xz[...,0],minimum_y,xz[...,1]),-1)
    return torch.where(below[...,None],lifted,ankle),below


def rotvec_matrix(vector):
    """Row-vector Rodrigues with finite, nonzero derivatives at identity."""
    x,y,z=vector.unbind(-1);zero=torch.zeros_like(x)
    skew=torch.stack((zero,z,-y,-z,zero,x,y,-x,zero),-1).reshape(*vector.shape[:-1],3,3)
    angle=torch.linalg.vector_norm(vector,dim=-1)
    a=torch.sinc(angle/math.pi)[...,None,None]
    b=(.5*torch.sinc(angle/(2*math.pi)).square())[...,None,None]
    eye=torch.eye(3,device=vector.device,dtype=vector.dtype)
    return eye+a*skew+b*(skew@skew)


def solve(skeleton, baseline, control, root, axes,*,foot_floor=False):
    tl=native.tl;clip=skeleton.runtime.lower_clip
    geometry=skeleton.runtime.lower_fk_geometry
    batch=len(baseline);pose,_=tl.output_to_pose(baseline,clip)
    positions,rotations,_=tl.fk_from_pose(clip,root,axes,pose,baseline.device,geometry_tensors=geometry)
    inverse=axes.transpose(-1,-2)
    pelvis=clip.pelvis
    shift=horizontal_world(control.pelvis_horizontal,axes)
    up=torch.zeros_like(shift);up[:,1]=control.drop[:,0]
    pelvis_point=positions[:,pelvis]+shift-up
    pelvis_rotation=tl.rotation_6d_to_matrix(baseline[:,3:9])@rotvec_matrix(control.pelvis_rotation)@axes
    result=baseline.clone()
    result[:,:3]=((pelvis_point-root).unsqueeze(-2)@inverse).squeeze(-2)
    result[:,3:9]=tl.rotmat_to_6d(pelvis_rotation@inverse)
    tensors={**clip.tensors(baseline.device),**geometry}
    def batched(key,ndim):
        value=tensors[key]
        return value[None].expand(batch,*value.shape) if value.ndim==ndim else value
    offsets=batched('local_offsets',2);lengths=batched('ik_limb_lengths',2)
    local_poles=batched('ik_local_pole_axis',3)
    payload_offset=9+clip.Jcore*6
    floor_applied=torch.zeros(batch,device=baseline.device,dtype=torch.bool)
    for i,(limb,spec) in enumerate(zip(clip.ik_limb_specs,clip.ik_payload_slices)):
        if limb['kind']!='leg':continue
        hip,knee,foot=(int(limb[key]) for key in ('start','mid','end'))
        move=control.left_foot if str(spec['side'])=='l' else control.right_foot
        ankle=positions[:,foot]+(move.unsqueeze(-2)@axes).squeeze(-2)
        new_hip=pelvis_point+(offsets[:,hip].unsqueeze(-2)@pelvis_rotation).squeeze(-2)
        old_axis=tl.normalize(positions[:,foot]-positions[:,hip])
        raw_bend=positions[:,knee]-positions[:,hip]
        raw_bend=raw_bend-old_axis*(raw_bend*old_axis).sum(-1,keepdim=True)
        encoded_pole=(local_poles[:,i,0,None,:]@rotations[:,hip]).squeeze(-2)
        old_pole=torch.where(torch.linalg.vector_norm(raw_bend,dim=-1,keepdim=True)>1e-5,
            tl.normalize(raw_bend),tl.project_to_plane(encoded_pole,old_axis))
        l1=torch.linalg.vector_norm(offsets[:,knee],dim=-1);l2=lengths[:,i,1]
        ankle=reachable_ankle(new_hip,ankle,l1,l2,old_axis)
        if foot_floor:
            toe=spec['toe_float']
            toe_value=baseline[:,payload_offset+toe.start:payload_offset+toe.stop]
            lowest=foot_box_lowest_y(skeleton.lower_store,i,positions[:,foot],rotations[:,foot],toe_value)
            minimum_y=positions[:,foot,1]-lowest+FOOT_FLOOR_MARGIN_M
            ankle,corrected=floor_reachable_ankle(new_hip,ankle,l1,l2,old_axis,minimum_y)
            floor_applied=floor_applied|corrected
        pole,_,_=foot_local_hinge_pole(old_axis,old_pole,rotations[:,foot],
            tl.normalize(ankle-new_hip),rotations[:,foot])
        solved=tl.solve_two_bone_with_pole_vector(new_hip,ankle,l1,l2,pole)
        # Transport the COMPLETE oriented hinge frame. Reusing a forward ray
        # here would cause a separate thigh-twist flip in deeply folded poses.
        old_upper=tl.normalize(positions[:,knee]-positions[:,hip])
        new_upper=tl.normalize(solved-new_hip)
        old_normal=tl.normalize(torch.cross(old_axis,old_pole,dim=-1))
        new_normal=tl.normalize(torch.cross(tl.normalize(ankle-new_hip),pole,dim=-1))
        old_basis=torch.stack((old_upper,tl.normalize(torch.cross(old_normal,old_upper,dim=-1)),old_normal),-2)
        new_basis=torch.stack((new_upper,tl.normalize(torch.cross(new_normal,new_upper,dim=-1)),new_normal),-2)
        thigh=rotations[:,hip]@old_basis.transpose(-1,-2)@new_basis
        # Disabled controls keep the entire original state bit-for-bit.
        p=spec['pos'];s=spec['start_rot6']
        result[:,payload_offset+p.start:payload_offset+p.stop]=((ankle-root).unsqueeze(-2)@inverse).squeeze(-2)
        result[:,payload_offset+s.start:payload_offset+s.stop]=tl.rotmat_to_6d(thigh@inverse)
    # Select on gates, not nonzero displacement: positive enabled gates must
    # permit an action gradient at exactly zero displacement during startup.
    applied=control.enabled|floor_applied
    return torch.where(applied[:,None],result,baseline),applied
