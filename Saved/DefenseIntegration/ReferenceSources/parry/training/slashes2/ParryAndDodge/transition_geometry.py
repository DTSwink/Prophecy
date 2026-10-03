"""Existing body OBBs plus the harness's anatomical hand/foot/toe boxes.

Legacy collider hand_r is named blade here. Parry adds actual end-effectors so
any member of its blocking chain can contact; Dodge retains its old 13 boxes.
The EE formulas are the harness render/admission formulas, not new dimensions.
"""
from dataclasses import dataclass
import json
import hashlib
from pathlib import Path
import torch
from collision_objective import load_collider_geometry,defender_obbs,COLLIDERS_PATH


@dataclass
class DefenseGeometry:
    base: object
    names: tuple
    half_sizes_m: torch.Tensor
    center_offsets_local: torch.Tensor
    body_indices: dict
    self_body_indices: torch.Tensor
    self_torso_indices: torch.Tensor
    harness_identity: dict | None = None

    @property
    def count(self):return len(self.names)
    @property
    def radii_m(self):return torch.linalg.vector_norm(self.half_sizes_m,dim=-1)


def load_geometry(bone_names,*,parry,path=COLLIDERS_PATH,device='cpu'):
    count=len(json.loads(path.read_text(encoding='utf-8'))['limbs'])
    if count not in ((13,14) if parry else (13,)):
        raise ValueError('Unexpected defense collider topology')
    base=load_collider_geometry(list(bone_names),path,expected_count=count).to(torch.device(device))
    names=tuple('blade' if name=='hand_r' else name for name in base.names)
    halves,offsets=base.half_sizes_m,base.center_offsets_local
    if parry:
        names+=('hand_l','hand_r','foot_l','ball_l','foot_r','ball_r')
        # Center offsets in each proper OBB's own axes (anchor is the toe for
        # both foot boxes; for hands it is the wrist).
        dimensions=((.145,.090,.045),(.145,.090,.045),(.175,.120,.051),
                    (.048,.120,.049),(.175,.120,.051),(.048,.120,.049))
        extra_offsets=((.0725,0,-.0025),(.0725,0,-.0025),(-.0875,0,-.006),
                       (.024,0,-.006),(-.0875,0,-.006),(.024,0,-.006))
        halves=torch.cat((halves,torch.tensor(dimensions,device=device)/2))
        offsets=torch.cat((offsets,torch.tensor(extra_offsets,device=device)))
    judged=('head','spine_01','spine_03','spine_05','upperarm_l','lowerarm_l','thigh_l','thigh_r')
    torso=('head','spine_01','spine_03','spine_05')
    return DefenseGeometry(base,names,halves,offsets,{name:i for i,name in enumerate(bone_names)},
        torch.tensor([names.index(name) for name in judged],device=device),
        torch.tensor([names.index(name) for name in torso],device=device))


def load_harness_geometry(cases,device='cpu'):
    """Production entry: never silently use the other harness/editor catalog."""
    identities=[]
    for case in cases:
        frozen=Path(case.manifest['frozen_inputs'])
        proof=json.loads((frozen/'proof.json').read_text(encoding='utf-8'))
        digest=hashlib.sha256((frozen/'colliders.json').read_bytes()).hexdigest()
        if proof['files']['colliders.json']!=digest:raise ValueError('Attested harness collider catalog changed')
        identities.append(dict(catalog_sha256=digest,html_sha256=proof['files']['index.html']))
    if not identities or any(value!=identities[0] for value in identities):
        raise ValueError('A training batch must use one attested harness geometry')
    geometry=load_geometry(cases[0].manifest['bone_names'],parry=int(cases[0].data['motion_kind'])>=16,
        path=Path(cases[0].manifest['frozen_inputs'])/'colliders.json',device=device)
    geometry.harness_identity=identities[0]
    return geometry


def normalize(value):return value/torch.linalg.vector_norm(value,dim=-1,keepdim=True).clamp_min(1e-12)
def flip_negative_dot(value,reference):
    return torch.where((value*reference).sum(-1,keepdim=True)<0,-value,value)
def upward(value):return torch.where(value[...,1:2]<0,-value,value)


def proper_box(forward,up):
    # A symmetric OBB is unchanged by negating its side axis. Use a proper
    # right-handed frame so quaternion CCD cannot interpolate a reflection.
    forward=normalize(forward)
    side=normalize(torch.cross(up,forward,dim=-1))
    up=normalize(torch.cross(forward,side,dim=-1))
    return torch.stack((forward,side,up),-2)


HAND_HALF_M=(.0725,.045,.0225)
HAND_CENTER_OFFSET_M=(.0725,0.,-.0025)


def harness_hand_obb(positions,rotations,geometry,side):
    """Shared native retargetHandBoxSpec; actual hand, never the blade alias."""
    hand=geometry.body_indices['hand_'+side]
    rows=rotations[...,hand,:,:]
    forward=normalize(rows[...,0,:])
    up=normalize(rows[...,1,:]-(rows[...,1,:]*forward).sum(-1,keepdim=True)*forward)
    if side=='r':forward=-forward
    box=proper_box(forward,up)
    center=positions[...,hand,:]+forward*.0725+up*(-.0025)
    return center,box


def harness_body_obbs(positions,rotations,geometry):
    """Native labObb including its final elbow->hand forearm override."""
    base=geometry.base
    points=positions.index_select(-2,base.bone_indices)
    frames=rotations.index_select(-3,base.bone_indices)
    frames=frames.clone()
    for side in ('l','r'):
        index=geometry.names.index('lowerarm_'+side)
        old=frames[...,index,:,:].clone()
        segment=positions[...,geometry.body_indices['hand_'+side],:]-points[...,index,:]
        length=torch.linalg.vector_norm(segment,dim=-1,keepdim=True)
        sign=torch.where(base.offsets_m[index,0]<0,-1.,1.)
        first=segment*sign/length.clamp_min(1e-12)
        second=old[...,1,:]-(old[...,1,:]*first).sum(-1,keepdim=True)*first
        backup=old[...,2,:]-(old[...,2,:]*first).sum(-1,keepdim=True)*first
        second=normalize(torch.where(torch.linalg.vector_norm(second,dim=-1,keepdim=True)<1e-8,backup,second))
        third=normalize(torch.cross(first,second,dim=-1))
        flip=(third*old[...,2,:]).sum(-1,keepdim=True)<0
        fitted=torch.stack((first,torch.where(flip,-second,second),torch.where(flip,-third,third)),-2)
        frames[...,index,:,:]=torch.where((length<1e-8)[...,None],old,fitted)
    centers=points+torch.einsum('ci,...cij->...cj',base.offsets_m,frames)
    axes=normalize(torch.einsum('cai,...cij->...caj',base.local_axes,frames))
    return centers,axes


def defense_obbs(positions,rotations,geometry,foot_local=None,foot_override=None):
    centers,axes=harness_body_obbs(positions,rotations,geometry)
    if geometry.count==geometry.base.count:return centers,axes
    joints=geometry.body_indices;ee_centers=[];ee_axes=[]
    for side in ('l','r'):
        center,box=harness_hand_obb(positions,rotations,geometry,side)
        ee_centers.append(center);ee_axes.append(box)
    for ordinal,side in enumerate(('l','r')):
        ankle,toe=joints['foot_'+side],joints['ball_'+side]
        toe_point=positions[...,toe,:]
        foot_rows=rotations[...,ankle,:,:];toe_rows=rotations[...,toe,:,:]
        forward=flip_negative_dot(foot_rows[...,1,:],toe_point-positions[...,ankle,:])
        up=upward(foot_rows[...,0,:])
        toe_forward=flip_negative_dot(toe_rows[...,0,:],forward)
        toe_up=upward(toe_rows[...,1,:]);reference=toe_rows[...,2,:]
        cross=torch.cross(toe_forward,toe_up,dim=-1)
        toe_side=torch.where(torch.linalg.vector_norm(cross,dim=-1,keepdim=True)<1e-6,reference,normalize(cross))
        toe_side=flip_negative_dot(toe_side,reference)
        toe_up=upward(normalize(torch.cross(toe_side,toe_forward,dim=-1)))
        if foot_local is not None:
            if foot_override is None:raise ValueError('Foot attachment data requires an explicit active mask')
            # Exact harness metadata is calf-local, not an authored world box.
            # Therefore colliders follow the predicted leg, not the GT motion.
            calf=rotations[...,joints['calf_'+side],:,:]
            attached=normalize(foot_local[...,ordinal,:,:,:] @ calf[...,None,:,:])
            use=foot_override[...,ordinal,None]
            forward=torch.where(use,attached[...,0,0,:],forward)
            up=torch.where(use,attached[...,0,1,:],up)
            toe_forward=torch.where(use,attached[...,1,0,:],toe_forward)
            toe_up=torch.where(use,attached[...,1,1,:],toe_up)
        ee_centers.append(toe_point-forward*.0875-up*.006)
        ee_axes.append(proper_box(forward,up))
        ee_centers.append(toe_point+toe_forward*.024-toe_up*.006)
        ee_axes.append(proper_box(toe_forward,toe_up))
    return torch.cat((centers,torch.stack(ee_centers,-2)),-2),torch.cat((axes,torch.stack(ee_axes,-3)),-3)
