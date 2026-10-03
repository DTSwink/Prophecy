"""Missing self-contact pairs, reusing established collision detectors.

One batched CCD call checks left hand against head and three torso boxes.
Historical finite-segment leg capsules check all four opposite thigh/calf
pairs at each predicted frame. Harness thigh OBBs overlap at normal hip joints;
do not use those broad boxes as a leg-crossing penalty. Own blocking limb is
NEVER exempt from self-harm; external first-block protection cannot disable it.
"""
import torch
import train_slash_controller as slash
from transition_collision import pair_contacts
from collision_objective import interpolate_obb,sat_gap
from transition_geometry import harness_hand_obb,HAND_HALF_M,HAND_CENTER_OFFSET_M

CONTRACT='harness_hand_torso_ccd_and_legacy_four_leg_capsules_v1'
PAIR_NAMES=(('hand_l','head'),('hand_l','spine_01'),('hand_l','spine_03'),('hand_l','spine_05'),
            ('thigh_l','thigh_r'),('thigh_l','calf_r'),('calf_l','thigh_r'),('calf_l','calf_r'))
FULL_ARM_CONTRACT='harness_both_full_arm_chains_head_torso_ccd_and_legacy_four_leg_capsules_v2'
NO_UPPERARM_CONTRACT='harness_both_hand_forearm_head_torso_ccd_no_upperarms_in_self_harm_v3'
ARM_TARGETS=('head','spine_01','spine_03','spine_05')
FULL_ARM_PAIRS=tuple((part+'_'+side,target) for side in ('l','r')
    for part in ('hand','lowerarm','upperarm') for target in ARM_TARGETS)


def self_collision_obbs(positions,rotations,centers,axes,geometry):
    if 'hand_l' in geometry.names:return centers,axes
    hand,hand_axes=harness_hand_obb(positions,rotations,geometry,'l')
    return torch.cat((centers,hand.unsqueeze(-2)),-2),torch.cat((axes,hand_axes.unsqueeze(-3)),-3)


class SelfCollision(torch.nn.Module):
    def __init__(self,geometry,*,full_arms=False,exclude_upperarms=False):
        super().__init__();self.geometry=geometry
        if exclude_upperarms and not full_arms:raise ValueError('Upperarm exclusion requires bilateral arm self-harm')
        self.full_arms=full_arms
        self.arm_pairs=FULL_ARM_PAIRS if full_arms else PAIR_NAMES[:4]
        self.excluded_names=('upperarm_l','upperarm_r') if exclude_upperarms else ()
        self.arm_pairs=tuple(pair for pair in self.arm_pairs if not any(n in self.excluded_names for n in pair))
        self.pairs_per_side=len(self.arm_pairs)//2 if full_arms else len(self.arm_pairs)
        self.pair_names=self.arm_pairs+PAIR_NAMES[4:]
        self.contract=NO_UPPERARM_CONTRACT if exclude_upperarms else (FULL_ARM_CONTRACT if full_arms else CONTRACT)
        device=geometry.half_sizes_m.device
        # The sword check also had upperarm_l as a target. Filter only this
        # self-harm index buffer, never the external CCD catalog or its masks.
        self.register_buffer('blade_body_indices',torch.tensor([i for i in geometry.self_body_indices.tolist()
            if geometry.names[i] not in self.excluded_names],device=device,dtype=torch.long))
        self.names=geometry.names
        half=geometry.half_sizes_m;offset=geometry.center_offsets_local
        if 'hand_l' not in self.names:
            self.names+=('hand_l',)
            half=torch.cat((half,half.new_tensor([HAND_HALF_M])))
            offset=torch.cat((offset,offset.new_tensor([HAND_CENTER_OFFSET_M])))
        if full_arms and 'hand_r' not in self.names:
            self.names+=('hand_r',)
            half=torch.cat((half,half.new_tensor([HAND_HALF_M])))
            offset=torch.cat((offset,offset.new_tensor([HAND_CENTER_OFFSET_M])))
        self.register_buffer('half_sizes_m',half);self.register_buffer('offset',offset)
        for name,side in (('a',0),('b',1)):
            ids=torch.tensor([self.names.index(pair[side]) for pair in self.arm_pairs],device=device)
            self.register_buffer(name+'_ids',ids)
            self.register_buffer(name+'_half',half[ids])
            self.register_buffer(name+'_offset',offset[ids])

    def forward(self,positions,rotations,centers,axes,valid):
        centers,axes=self_collision_obbs(positions,rotations,centers,axes,self.geometry)
        if self.full_arms and 'hand_r' not in self.geometry.names:
            hand,hand_axes=harness_hand_obb(positions,rotations,self.geometry,'r')
            centers=torch.cat((centers,hand.unsqueeze(-2)),-2)
            axes=torch.cat((axes,hand_axes.unsqueeze(-3)),-3)
        # Skip 0->1: both poses are immutable primers. Intervals start at 1.
        c=centers[:,1:];r=axes[:,1:]
        ac,bc=c.index_select(2,self.a_ids),c.index_select(2,self.b_ids)
        aa,ba=r.index_select(2,self.a_ids),r.index_select(2,self.b_ids)
        batch,frames,pairs=ac.shape[:3];intervals=frames-1
        def flat(value):return value.reshape(batch*intervals*pairs,*value.shape[3:])
        def body(value):return flat(value).unsqueeze(1)
        def expand(value):return value[None,None].expand(batch,intervals,*value.shape)
        ah,bh=expand(self.a_half),expand(self.b_half)
        ao,bo=expand(self.a_offset),expand(self.b_offset)
        hit,time=pair_contacts(body(ac[:,:-1]),body(aa[:,:-1]),body(ac[:,1:]),body(aa[:,1:]),
            body(ah),body(ao),flat(bc[:,:-1]),flat(ba[:,:-1]),flat(bc[:,1:]),flat(ba[:,1:]),flat(bh),flat(bo))
        hit=hit.reshape(batch,intervals,pairs) & valid[:,:,None]
        time=time.reshape(batch,intervals,pairs)
        fraction=torch.where(hit,time,0.).detach()
        ap,ar=interpolate_obb(ac[:,:-1],aa[:,:-1],ac[:,1:],aa[:,1:],fraction,ao)
        bp,br=interpolate_obb(bc[:,:-1],ba[:,:-1],bc[:,1:],ba[:,1:],fraction,bo)
        gap=sat_gap(ap,ar,ah,bp,br,bh)
        penalty=torch.where(hit,torch.nn.functional.softplus(-gap/.01)*.01,0.)
        # Same metre-valued contact surrogate as existing self-harm; do not
        # dilute the hand/head collision by averaging it with clear torso boxes.
        # Preserve the maximum-per-side reduction and its existing coefficient;
        # adding clear arm pairs must not dilute an existing hand contact.
        hand=penalty[...,:self.pairs_per_side].amax(-1) if self.full_arms else penalty.amax(-1)
        right_arm=penalty[...,self.pairs_per_side:].amax(-1) if self.full_arms else torch.zeros_like(hand)
        p=positions[:,2:];j=self.geometry.body_indices;leg_overlaps=[]
        for left,right in PAIR_NAMES[4:]:
            end=lambda name:name.replace('thigh','calf') if name.startswith('thigh') else name.replace('calf','foot')
            radius=lambda name:.064 if name.startswith('thigh') else .052
            overlap=slash.capsule_pair_overlap_rows(p[:,:,j[left]],p[:,:,j[end(left)]],radius(left),
                p[:,:,j[right]],p[:,:,j[end(right)]],radius(right))
            leg_overlaps.append(overlap)
        leg_overlap=torch.where(valid[:,:,None],torch.stack(leg_overlaps,-1),0.)
        # Exact historical four-pair reduction: mean squared overlap (metres²).
        legs=leg_overlap.square().mean(-1)
        with torch.no_grad():
            end_gap=sat_gap(ac[:,1:],aa[:,1:],ah,bc[:,1:],ba[:,1:],bh)
            overlap=torch.cat((torch.where(valid[:,:,None],(-end_gap).clamp_min(0),0.),leg_overlap.detach()),-1)
            leg_hit=(leg_overlap>0).detach()
        return dict(left_hand_self_harm=hand,right_arm_self_harm=right_arm,leg_cross=legs,hits=torch.cat((hit,leg_hit),-1),
            fraction=torch.cat((fraction,leg_hit.to(fraction.dtype)),-1),
            overlap_m=overlap,centers=centers,axes=axes)
