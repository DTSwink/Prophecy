"""Banked-Dodge setup and dynamic row loading; old training paths unchanged."""
import json
from pathlib import Path
import torch
from transition_batch import MotionBank
from transition_objective import load_prior
from transition_antistatuing import load_statue_prior
from transition_self_collision import SelfCollision
from frozen_parry_prior import UpperRoutedPrior,UpperRoutedStatuePrior
from dodge_banked_agent import BankedDodge
from dodge_movement_banks import limits_for_families
from transition_agents import native
from dodge_banked_objective import BankedObjective,DIAGONAL_SLASHES

DODGE_TYPES=('dodge_regular',)
PRIMER_CONTRACT='unperturbed_authored_locomotion_two_primers_v1'
HEIGHT_CONTRACT='dodge_target_height_50_volume_25_head_25_spine05_v1'


def lower_categories(data,rows):
    """Production packs carry their attested routes, never a mutable manifest."""
    embedded=[entry.get('lower_category') for entry in rows]
    if any(value is not None for value in embedded) or data.get('banked_dodge'):
        if any(value not in ('walk','run') for value in embedded):
            raise ValueError('Every banked Dodge row needs an attested walk/run category')
        return [int(value=='run') for value in embedded]
    # Retired packs are permitted solely for explicitly requested diagnostics.
    preview=json.loads((native.HERE/'neural_preview_manifest.json').read_text())['cases']
    return [int(preview[r['record']['scene']['locomotionIndex']]['category']=='run') for r in rows]


def validate_training_pack(data,diagnostic=False):
    """An old defended/COM-root pack is never silently a production dataset."""
    if diagnostic:return
    provenance=data.get('banked_dodge',{})
    if (provenance.get('height_contract')!=HEIGHT_CONTRACT or
            provenance.get('primer_contract')!=PRIMER_CONTRACT or
            not provenance.get('audit_passed') or not provenance.get('attacker_manifest_sha256')):
        raise ValueError('Production banked Dodge requires the audited height bank and unperturbed two-frame primers')


@torch.no_grad()
def check_dynamic_rows(bank,runner,indices):
    """Same captured graph with both lower checkpoints and unequal endpoints."""
    from transition_rollout import rollout
    selected=[int(indices[0])]
    for category in (0,1):
        found=torch.nonzero(bank.categories==category)
        if len(found):selected.append(int(found[0]))
    selected += [min(range(len(bank.rows)),key=lambda i:bank.rows[i]['length']),
                 max(range(len(bank.rows)),key=lambda i:bank.rows[i]['length'])]
    selected += [i for i,r in enumerate(bank.rows) if r['record']['scene']['attack']=='spear'][:1]
    if getattr(bank.objective,'diagonal_loss_scaling',False):
        selected += [next(i for i,r in enumerate(bank.rows) if r['record']['scene']['attack']==name) for name in DIAGONAL_SLASHES]
    checks=[]
    for index in dict.fromkeys(selected):
        bank.select([index]*len(indices));runner.backward_graph.replay()
        oracle=rollout(bank.agent,bank.selected);loss=bank.objective(oracle,bank.selected)
        torch.testing.assert_close(runner.loss['total'],loss['total'],atol=3e-6,rtol=2e-5)
        if getattr(bank.objective,'diagonal_loss_scaling',False):
            diagonal=bank.rows[index]['record']['scene']['attack'] in DIAGONAL_SLASHES
            assert bool(torch.all(bank.objective.diagonal_slash_rows==diagonal))
            bank.objective.diagonal_loss_scaling=False
            try:baseline=bank.objective(oracle,bank.selected)
            finally:bank.objective.diagonal_loss_scaling=True
            for key,value in baseline['weighted'].items():
                factor=({'bank_usage':.5,'ccd':1.5}.get(key,1.) if diagonal else 1.)
                torch.testing.assert_close(loss['weighted'][key],value*factor,atol=0,rtol=0)
                torch.testing.assert_close(runner.loss['weighted'][key],loss['weighted'][key],atol=3e-6,rtol=2e-5)
        for key in ('positions','rotations','roots','lower','upper','movement_banks','root_shifts_world','root_yaw_offsets'):
            torch.testing.assert_close(getattr(runner.result,key),getattr(oracle,key),atol=2e-6,rtol=2e-5)
        floor_minimum=None
        if bank.agent.foot_floor:
            from dodge_leg_feedback import foot_box_lowest_y
            sk=bank.agent.skeleton;clip=sk.runtime.lower_clip;start=9+clip.Jcore*6
            minima=[]
            for frame in range(2,oracle.positions.shape[1]):
                for i,(limb,spec) in enumerate(zip(clip.ik_limb_specs,clip.ik_payload_slices)):
                    if limb['kind']!='leg':continue
                    foot=int(limb['end']);toe=spec['toe_float']
                    height=foot_box_lowest_y(sk.lower_store,i,oracle.positions[:,frame,foot],
                        oracle.rotations[:,frame,foot],oracle.lower[:,frame,start+toe.start:start+toe.stop])
                    minima.append(height[bank.selected.valid[:,frame]])
            floor_minimum=float(torch.cat(minima).min())
            assert floor_minimum>=-2e-6,('Foot crossed floor after final FK',index,floor_minimum)
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in runner.parameters)
        checks.append(dict(index=index,category=int(bank.agent.category[0]),length=bank.rows[index]['length'],
            attack=bank.rows[index]['record']['scene']['attack'],diagonal_loss_scaling_checked=getattr(bank.objective,'diagonal_loss_scaling',False),
            final_foot_floor_min_y_m=floor_minimum))
    bank.select(indices)
    return checks


class BankedMotionBank(MotionBank):
    objective_class=BankedObjective
    def __init__(self,path,device='cuda',overrides=None):
        super().__init__(path,device)
        if self.kind!='dodge':raise ValueError('This experiment is Dodge only')
        # Latest user decision: all attacks use the REGULAR upper prior. Keep
        # the old label as provenance only, never as routing/conditioning.
        for entry in self.rows:
            entry['row']=dict(entry['row'],original_motion_kind=entry['row']['motion_kind'],
                original_type=entry['row']['type'],motion_kind=0,type='dodge_regular')
        self.types=DODGE_TYPES
        self.type_ids.zero_()
        scenes=[r['record']['scene'] for r in self.rows]
        self.diagonal_slashes=torch.tensor([s['attack'] in DIAGONAL_SLASHES for s in scenes],device=device,dtype=torch.bool)
        self.categories=torch.tensor(lower_categories(self.data,self.rows),device=device,dtype=torch.long)
        self.budgets=limits_for_families([s['attack'] for s in scenes],overrides,device=device)

    def setup(self,indices,weights,priors_root,seed,run,statue_root=None,*,full_arm_self_harm=True,recipe=None,exclude_upperarm_self_harm=False,foot_floor=True):
        if weights.predictive_pin or weights.anti_pin_slide or weights.required_block:
            raise ValueError('No learned pin head and no required-block loss in banked Dodge')
        _,episode,objective=super().setup(indices,weights,priors_root,seed,run,statue_root=statue_root)
        self.load_graph=None
        objective.register_buffer('diagonal_slash_rows',self.diagonal_slashes.index_select(0,self.indices).clone())
        self.agent=BankedDodge(objective.skeleton,self.categories[self.indices],self.budgets[self.indices],recipe=recipe,foot_floor=foot_floor)
        priors={name:load_prior(Path(priors_root)/name/'best.pt',name,self.device) for name in self.types}
        options=dict(allowed_types=DODGE_TYPES,detach_lower=False)
        objective.routed_prior=UpperRoutedPrior(priors,**options)
        if weights.anti_statuing>0:
            statue={name:load_statue_prior(Path(statue_root)/name/'best.pt',name,self.device) for name in self.types}
            objective.routed_statue=UpperRoutedStatuePrior(statue,**options)
        objective.banked_dodge=True;objective.full_arm_self_harm=full_arm_self_harm
        objective.self_collision=SelfCollision(objective.geometry,full_arms=full_arm_self_harm,
            exclude_upperarms=exclude_upperarm_self_harm)
        self._load()
        if self.device.type=='cuda':
            stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):self._load()
            torch.cuda.current_stream().wait_stream(stream)
            self.load_graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.load_graph,stream=stream):self._load()
        return self.agent,episode,objective

    @torch.no_grad()
    def _load(self):
        super()._load()
        if hasattr(self.objective,'diagonal_slash_rows'):
            self.objective.diagonal_slash_rows.copy_(self.diagonal_slashes.index_select(0,self.indices))
        if hasattr(self.agent,'category'):
            self.agent.category.copy_(self.categories.index_select(0,self.indices))
            self.agent.limits.copy_(self.budgets.index_select(0,self.indices))
