"""Per-row disabled-limb curriculum; original SlowLocoEnv remains the vanilla path."""
import math
import numpy as np
import torch
from pathlib import Path
from slow_loco_env import SlowLocoEnv
from absolute_walk import AbsoluteWalkEnv
from omni_walk import phase_at
from flat_com import expanded_band,band_loss
from util import torch_util as q
from disabled_limb_rules import LIMBS,limb_bodies,valid_codes,crawl_rate,cohorts

@torch.jit.script
def crawl_forward_bonus(velocity: torch.Tensor, target: torch.Tensor):
    """Independent 0..5 speed reward: zero at rest, peak at target, no overspeed bonus."""
    speed = torch.linalg.vector_norm(target, dim=-1).clamp_min(1e-6)
    return 5. * (1. - torch.linalg.vector_norm(velocity-target, dim=-1)/speed).clamp(0., 1.)

@torch.jit.script
def signed_crawl_progress(velocity: torch.Tensor, target: torch.Tensor):
    """Concave signed progress: any zero-net-displacement cycle earns <= zero."""
    speed = torch.linalg.vector_norm(target, dim=-1).clamp_min(1e-6)
    return 5. * (1. - torch.linalg.vector_norm(velocity-target, dim=-1)/speed)

class DisabledSlowLocoEnv(SlowLocoEnv):
    def _build_sim_tensors(self,config):
        super()._build_sim_tensors(config)
        cfg=config['slow_loco_disabled_curriculum']
        assert cfg['version']==1 and cfg['fractions']==[.1,.3,.3,.3]
        assert cfg['crawl_mixed_rule']=='slower_factor'
        assert self.failure_penalty==100. and self._motion_subset is None
        self.disabled_curriculum=dict(cfg,moving_crawl_disabled_limbs=['right_leg','left_leg'],moving_crawl_disabled_counts=[1,2])
        self._cohort=self._prepared_cohort
        self._injured=self._cohort>0
        self._target_radii_sq[self._injured] *= 4.
        self._pelvis_window.radius[self._injured] *= 2.
        n=self.get_num_envs(); names=self._kin_char_model.get_body_names()
        self._codes=torch.zeros(n,dtype=torch.long,device=self._device)
        self._rates=torch.ones(n,device=self._device)
        choices=np.zeros((10,4,14),np.int64);lengths=np.ones((10,4),np.int64)
        for m,name in enumerate(self.motion_labels):
            choices[m,0,0]=8 if name.startswith('limpL') else 4 if name.startswith('limpR') else 0
            for count in (1,2,3):
                vals=valid_codes(name,count)
                if not vals:
                    assert not ((self._fixed_motion_ids==m)&(self._cohort==count)).any(), (name,count)
                    continue
                choices[m,count,:len(vals)]=vals;lengths[m,count]=len(vals)
        self._code_choices=torch.tensor(choices,device=self._device)
        self._choice_counts=torch.tensor(lengths,device=self._device)
        flags=torch.tensor([[0. if c&(1<<l) else 1. for l in range(4)] for c in range(16)],device=self._device)
        self._flags_by_code=flags
        self._body_by_code=torch.ones((16,len(names),1),dtype=torch.bool,device=self._device)
        self._motor_by_code=torch.ones((16,34),device=self._device)
        self._termination_by_code=torch.ones((16,len(self._termination_points)),dtype=torch.bool,device=self._device)
        for l in range(4):
            dead=flags[:,l]==0
            for body in limb_bodies(l):
                b=names.index(body);j=self._kin_char_model.get_joint(b)
                self._body_by_code[dead,b]=False
                self._motor_by_code[dead,j.dof_idx:j.dof_idx+j.get_dof_dim()]=0.
            for i,p in enumerate(self._termination_points):
                if p['body'] in limb_bodies(l):self._termination_by_code[dead,i]=False
        rates=torch.ones((10,16),device=self._device)
        rates[:2]=torch.tensor([crawl_rate(c) for c in range(16)],device=self._device)
        self._rates_by_motion_code=rates
        bank=Path(config['motion_file']).parent/cfg['init_bank']
        import hashlib
        assert hashlib.sha256(bank.read_bytes()).hexdigest()==cfg['init_bank_sha256']
        with np.load(bank,allow_pickle=False) as z:
            self._init_dofs=torch.tensor(z['dof_pos'],device=self._device)
            self._init_times=torch.tensor(z['times'],device=self._device)
        assert self._init_dofs.shape[:2]==(10,16) and self._init_dofs.shape[-1]==34
        self._init_selection=torch.zeros(n,dtype=torch.long,device=self._device)
        self._all_worlds=torch.arange(n,device=self._device)
        # Defaults valid even before the first reset/observation shape probe.
        codes=self._code_choices[self._fixed_motion_ids,self._cohort,0]
        self._apply_codes(self._all_worlds,codes)
        if self._flat_com_config:self._build_disabled_com_bands()
        crawl_id = self.motion_labels.index('crawl')
        ids = torch.tensor([crawl_id, crawl_id], device=self._device)
        length = self._motion_lib.get_motion_length(ids[:1])
        times = torch.cat((torch.zeros_like(length), length))
        roots = self._motion_lib.calc_motion_frame(ids, times)[0]
        self._crawl_cycle_velocity = (roots[1, :2]-roots[0, :2])/length[0]
        assert torch.linalg.vector_norm(self._crawl_cycle_velocity) > .01
        self._crawl_forward_values = torch.zeros(n, device=self._device)
        self._crawl_forward_totals = torch.zeros(5, device=self._device)
        self._crawl_previous_xy = self._engine.get_body_pos(self._get_char_id())[:, self._pelvis_id, :2].clone()
        self.motion_sampling['cohort_counts']={('vanilla' if k==0 else f'perturbed_{k}'):
            int((self._cohort==k).sum()) for k in range(4)}
        self.motion_sampling['by_motion_cohort']={name:[int(((self._fixed_motion_ids==m)&(self._cohort==k)).sum())
            for k in range(4)] for m,name in enumerate(self.motion_labels)}

    def _apply_codes(self,ids,codes):
        self._codes[ids]=codes
        self._limb_enabled[ids]=self._flags_by_code[codes]
        self._arm_enabled[ids]=self._flags_by_code[codes,:2]
        self._mse_body_enabled[ids]=self._body_by_code[codes]
        self._motor_enabled_binary[ids]=self._motor_by_code[codes]
        self._target_termination_enabled[ids]=self._termination_by_code[codes]
        exempt=(self._fixed_motion_ids[ids]==2)|(self._fixed_motion_ids[ids]==3)
        self._target_termination_enabled[ids] &= ~exempt[:,None]
        self._pelvis_window.ready[ids] = ~exempt
        rates=self._rates_by_motion_code[self._fixed_motion_ids[ids],codes]
        self._rates[ids]=torch.where(self._injured[ids],rates,torch.ones_like(rates))

    def _reset_ref_motion(self,env_ids):
        if not hasattr(self,'_cohort'):return super()._reset_ref_motion(env_ids)
        mids=self._fixed_motion_ids[env_ids];group=self._cohort[env_ids]
        choice=(torch.rand(len(env_ids),device=self._device)*self._choice_counts[mids,group]).long()
        codes=self._code_choices[mids,group,choice]
        self._apply_codes(env_ids,codes)
        super()._reset_ref_motion(env_ids)
        ids=env_ids[self._injured[env_ids]]
        if len(ids):
            idx=torch.randint(self._init_dofs.shape[2],(len(ids),),device=self._device)
            self._init_selection[ids]=idx
            times=self._init_times[self._motion_ids[ids],self._codes[ids],idx]
            self._motion_time_offsets[ids]=times
            vals=self._motion_lib.calc_motion_frame(self._motion_ids[ids],times)
            for dest,v in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),vals):dest[ids]=v
            self._ref_dof_pos[ids]=self._motion_lib.joint_rot_to_dof(vals[4])
            pos,rot=self._kin_char_model.forward_kinematics(vals[0],vals[1],vals[4])
            self._ref_body_pos[ids]=pos;self._ref_body_rot[ids]=rot
        for dest in (self._ref_root_vel,self._ref_root_ang_vel,self._ref_dof_vel):dest[env_ids]*=self._rates[env_ids,None]

    def _ref_state_init(self,env_ids):
        super()._ref_state_init(env_ids)
        if not hasattr(self,'_cohort'):return
        ids=env_ids[self._injured[env_ids]]
        if len(ids):
            bank=self._init_dofs[self._motion_ids[ids],self._codes[ids],self._init_selection[ids]]
            # Only replace disabled DOFs: enabled joints use the exact library
            # reset, not the bank's quantised copy. No root/body teleport.
            enabled=self._motor_enabled_binary[ids]>0
            self._engine.set_dof_pos(ids,self._get_char_id(),torch.where(enabled,self._ref_dof_pos[ids],bank))
            self._engine.set_dof_vel(ids,self._get_char_id(),torch.where(enabled,self._ref_dof_vel[ids],torch.zeros_like(bank)))

    def _get_motion_times(self,env_ids=None):
        if not hasattr(self,'_rates'):return super()._get_motion_times(env_ids)
        if env_ids is None:return self._time_buf*self._rates+self._motion_time_offsets
        return self._time_buf[env_ids]*self._rates[env_ids]+self._motion_time_offsets[env_ids]

    def _update_ref_motion(self):
        super()._update_ref_motion()
        if hasattr(self,'_rates'):
            for dest in (self._ref_root_vel,self._ref_root_ang_vel,self._ref_dof_vel):dest.mul_(self._rates[:,None])

    def _command_phase(self,env_ids=None,dt=0.):
        if not hasattr(self,'_rates'):return super()._command_phase(env_ids,dt)
        ids=self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        rate=self._rates if env_ids is None else self._rates[env_ids]
        return ids,phase_at(self._get_motion_times(env_ids),self._motion_lib.get_motion_length(ids),self._phase_offsets[ids],dt*rate)

    def _compute_obs(self,env_ids=None):
        physical=AbsoluteWalkEnv._compute_obs(self,env_ids)
        ids,phase=self._command_phase(env_ids)
        flags=self._limb_enabled if env_ids is None else self._limb_enabled[env_ids]
        return torch.cat((physical,self._motion_onehot[ids],flags,phase),-1)

    @torch.no_grad()
    def _build_disabled_com_bands(self):
        weights=self._body_by_code[:,self._flat_com_ids,0]*self._flat_com_masses[None]
        self._disabled_com_masses=weights/weights.sum(-1,keepdim=True)
        bands=[]
        for m in range(10):
            length=float(self._motion_lib.get_motion_length(m))
            times=torch.arange(math.ceil(length*240),device=self._device)/240
            times=times[times<length];ids=torch.full_like(times,m,dtype=torch.long)
            root,rotation,velocity,angular,joints,dof=self._motion_lib.calc_motion_frame(ids,times)
            pos,rot=self._kin_char_model.forward_kinematics(root,rotation,joints)
            vel,ang=self._world_reference_velocities(pos,rot,velocity,angular,dof,ids,times)
            com=vel+torch.cross(ang,q.quat_rotate(rot,self._body_com[:1].expand_as(pos)),dim=-1)
            by_code=torch.einsum('tbj,cb->tcj',com[:,self._flat_com_ids,:2],self._disabled_com_masses)
            lo=by_code.amin(0);hi=by_code.amax(0);pad=(hi-lo)*float(self._flat_com_config['leeway'])
            bands.append(torch.stack((lo-pad,hi+pad),1)*self._rates_by_motion_code[m,:,None,None])
        self._disabled_com_bands=torch.stack(bands)

    def _tracking_losses(self,pos,rot,vel,ang,target_vel,target_ang):
        terms=super()._tracking_losses(pos,rot,vel,ang,target_vel,target_ang)
        if self._flat_com_config and hasattr(self,'_disabled_com_bands'):
            velocity=self._engine.get_body_vel(self._get_char_id())[:,self._flat_com_ids,:2]
            velocity=(velocity*self._disabled_com_masses[self._codes,:,None]).sum(1)
            extra=band_loss(velocity,self._disabled_com_bands[self._motion_ids,self._codes])*self._flat_com_weight
            extra.masked_fill_(self._static_motion[self._motion_ids],0.)
            terms[:,4]=torch.where(self._injured,extra,terms[:,4])
        return terms

    def _update_reward(self):
        super()._update_reward()
        # Physical pelvis-origin velocity, matching the recorded body-origin MSE
        # velocities. The independent bonus is never exponentiated with pose loss.
        char = self._get_char_id(); b = self._pelvis_id
        rot = self._engine.get_body_rot(char)[:, b]
        ang = self._engine.get_body_ang_vel(char)[:, b]
        velocity = self._engine.get_body_vel(char)[:, b] - torch.cross(
            ang, q.quat_rotate(rot, self._body_com[:, b].expand_as(ang)), dim=-1)
        active = (self._motion_ids == 0) & (self._codes == 12) & self._injured
        target = self._crawl_cycle_velocity[None] * self._rates[:, None]
        if self._crawl_only_experiment:
            xy = self._engine.get_body_pos(char)[:, b, :2]
            movement = (xy-self._crawl_previous_xy)/self._engine.get_timestep()
            self._crawl_previous_xy.copy_(xy)
            bonus = signed_crawl_progress(movement, target)
        else:
            movement = velocity[:, :2]
            bonus = crawl_forward_bonus(movement, target)
        self._crawl_forward_values.copy_(torch.where(active, bonus, 0.))
        direction = self._crawl_cycle_velocity / torch.linalg.vector_norm(self._crawl_cycle_velocity)
        self._crawl_forward_totals.add_(torch.stack((self._crawl_forward_values.sum(),
            (self._reward_buf*active).sum(), ((movement*direction).sum(-1)*active).sum(),
            (torch.linalg.vector_norm(target, dim=-1)*active).sum(), active.sum())))
        self._reward_buf.add_(self._crawl_forward_values)

    def _reset_envs(self, ids):
        super()._reset_envs(ids)
        if hasattr(self, '_crawl_previous_xy'):
            self._crawl_previous_xy[ids] = self._engine.get_body_pos(self._get_char_id())[ids, self._pelvis_id, :2]
            self._crawl_forward_values[ids] = 0.

    def take_reward_diagnostics(self):
        values = self._crawl_forward_totals.cpu().tolist()
        self._crawl_forward_totals.zero_()
        if not values[-1]: return {}
        return dict(zip(('crawl_forward', 'crawl_pose', 'crawl_forward_speed_m_s', 'crawl_target_speed_m_s'),
                        (v/values[-1] for v in values[:-1])))

    def select_disabled_replay_worlds(self,limit,selection_round):
        if self._crawl_only_experiment:
            count=min(limit,self.get_num_envs())
            return [(selection_round+k*self.get_num_envs()//count)%self.get_num_envs() for k in range(count)]
        motions=self._motion_ids.cpu().tolist();groups=self._cohort.cpu().tolist();selected=[]
        for m in range(10):
            for k in range(4):
                candidates=[w for w in range(len(motions)) if motions[w]==m and groups[w]==k]
                if candidates:selected.append(candidates[selection_round%len(candidates)])
        return selected[:limit]

    def disabled_row_metadata(self,w):
        name=self.motion_labels[int(self._motion_ids[w])];count=int(self._cohort[w]);code=int(self._codes[w])
        disabled=[LIMBS[l] for l in range(4) if code&(1<<l)]
        excluded=[b for l in range(4) if code&(1<<l) for b in limb_bodies(l)]
        radii={p['body']:(float(self._target_radii_sq[w,i].sqrt()) if self._target_termination_enabled[w,i] else None)
            for i,p in enumerate(self._termination_points)}
        label='vanilla' if count==0 else f'perturbed {count} disabled'
        return dict(row_type=label,disabled_limb_count=len(disabled),disabled_limbs=disabled,
            crawl_forward_reward=dict(enabled=name=='crawl' and code==12 and count>0, maximum=5.,
                form='signed_displacement_v1' if self._crawl_only_experiment else 'clipped_velocity_v1',
                target_velocity_xy_m_s=(self._crawl_cycle_velocity*self._rates[w]).cpu().tolist(),
                definition=('5 * (1 - norm(delta_pelvis_xy / dt - target_xy) / norm(target_xy)); signed, no lower clipping; added outside exp(-loss)'
                    if self._crawl_only_experiment else '5 * clamp(1 - norm(pelvis_origin_velocity_xy - target_xy) / norm(target_xy), 0, 1); added outside exp(-loss)'),
                target='cycle-average world translation scaled by row playback rate'),
            disabled_limb_code=code,motion_playback_rate=float(self._rates[w]),
            replay_row_label=f'{name} | {label} | {", ".join(disabled) or "all enabled"} | {float(self._rates[w])*100:.0f}%',
            row_target_radii_m=radii,excluded_mse_bodies=excluded,
            loco_failure_penalty=float(self._failure_penalty_by_row[w]),
            pelvis_reset_every_ticks=int(self._pelvis_window.windows[w]),
            failure_termination_enabled=name not in ('agonising','agonising_idle'),
            termination_radius_multiplier=2. if count else 1.,
            cohort_index=count,perturbed_row=count>0,
            initial_pose_bank_index=int(self._init_selection[w]) if count else None)

    def replay_loss_metadata(self):
        result=super().replay_loss_metadata()
        result.update(perturbations=True,disabled_limb_curriculum=self.disabled_curriculum,
            limb_semantics='0 = zero motor torque for entire limb; all four MSEs and limb termination excluded; mass/collisions retained')
        result['disabled_leg_mse']=dict(self.disabled_leg_mse,per_row_exclusions_field='excluded_mse_bodies',
            flat_com_velocity_unchanged=False,perturbed_flat_com='mass weights and reference bands exclude disabled bodies')
        return result
