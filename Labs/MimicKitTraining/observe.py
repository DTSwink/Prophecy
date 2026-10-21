"""Record world zero during upstream's existing deterministic evaluation only."""
import json
import time
from pathlib import Path
import numpy as np
import torch
from envs.deepmimic_env import DeepMimicEnv

def first_episode_end(done):
    terminal=np.flatnonzero(done[1:] != 0)+1
    if not len(terminal):
        raise ValueError('No completed episode in recording; refusing partial replay')
    return int(terminal[0])+1

class Recorder:
    def __init__(self, env, directory, world=0, filename="replay.npz"):
        self.world=world
        self.filename=filename
        self.env=env
        self.directory=Path(directory)
        self.engine=env._engine
        self.char=env._get_char_id()
        self.names=list(self.engine.get_obj_body_names(self.char))
        self.fps=1/self.engine.get_timestep()
        self.capacity=int(round(env._episode_length*self.fps))+3
        shape=(self.capacity,len(self.names))
        self.pose=torch.empty((*shape,7),device=env._device)
        self.reference_pose = torch.empty_like(self.pose) if isinstance(env, DeepMimicEnv) else None
        self.absolute_velocities=torch.empty((*shape,12),device=env._device) if hasattr(env,'replay_loss_metadata') else None
        self.data=torch.empty((self.capacity,3),device=env._device)
        self.components=torch.empty((self.capacity,env.loss_terms.shape[1]),device=env._device) if hasattr(env,'loss_terms') else None
        self.impacts=torch.empty((self.capacity,3),device=env._device) if getattr(env,'floor_impact_limit_n',None) is not None else None
        self.count=0
        self.enabled=False
        self.capture_seconds=0.0
        self.phase_agent=None
        self.phase_values=torch.empty((self.capacity,6),device=env._device) if hasattr(env,'next_phase_target') else None
        self.prior_values=torch.empty((self.capacity,3),device=env._device) if getattr(env,'_perturb_ready',False) else None
        original_step=env.step
        def step(action):
            result=original_step(action)
            if self.enabled and self.count<self.capacity:
                self.capture()
            return result
        env.step=step

    def capture(self):
        i=self.count
        self.pose[i,:,:3].copy_(self.engine.get_body_pos(self.char)[self.world])
        self.pose[i,:,3:].copy_(self.engine.get_body_rot(self.char)[self.world])
        if self.reference_pose is not None:
            self.reference_pose[i,:,:3].copy_((self.env.reward_target_pos if hasattr(self.env,'reward_target_pos') else self.env._ref_body_pos)[self.world])
            self.reference_pose[i,:,3:].copy_(getattr(self.env, 'reward_target_rot', self.env._ref_body_rot)[self.world])
        if self.absolute_velocities is not None:
            from util import torch_util as q
            ang=self.engine.get_body_ang_vel(self.char)[self.world]
            vel=self.engine.get_body_vel(self.char)[self.world]-torch.cross(ang,q.quat_rotate(self.pose[i,:,3:],self.env._body_com[self.world]),dim=-1)
            self.absolute_velocities[i].copy_(torch.cat([vel,ang,self.env.reward_target_vel[self.world],self.env.reward_target_ang[self.world]],-1))
        self.data[i,0].copy_(self.env._done_buf[self.world])
        self.data[i,1].copy_(self.env._time_buf[self.world])
        self.data[i,2].copy_(self.env._reward_buf[self.world])
        if self.prior_values is not None:
            self.prior_values[i].copy_(torch.stack((self.env._prior_raw[self.world],self.env._tracking_mix[self.world],self.env._reset_reason[self.world].float())))
        if self.components is not None:self.components[i].copy_(self.env.loss_terms[self.world])
        if self.phase_values is not None and self.phase_agent is not None:
            ids=torch.tensor([self.world],device=self.env._device)
            obs=self.env._compute_obs(ids)
            with torch.no_grad():
                prediction=self.phase_agent._model.eval_phase(self.phase_agent._obs_norm.normalize(obs))[0]
            self.phase_values[i].copy_(torch.cat((obs[0,-2:],prediction,self.env.next_phase_target()[self.world])))
        if self.impacts is not None:
            self.impacts[i,0].copy_(self.env.floor_peak_n[self.world])
            self.impacts[i,1].copy_(self.env.floor_peak_body[self.world])
            self.impacts[i,2].copy_(self.env.failure_reason[self.world])
        self.count+=1

    def start(self):
        self.count=0
        self.enabled=True
        self.equipment_metadata={}
        if getattr(self.env,'_equipment_conditioning',False):
            motion=int(self.env._motion_ids[self.world])
            self.equipment_metadata=dict(sword_drawn=bool(self.env._equipment[motion]),
                arm_enabled=self.env._arm_enabled[self.world].cpu().tolist(),
                idle_row=self.world<self.env._idle_rows,idle_rows=self.env._idle_rows,
                motion_file=self.env._motion_lib.get_motion_file(motion),auto_phase_feedback=False)
        self.start_side=('back' if bool(self.env._starts_on_back[self.world]) else 'front') if hasattr(self.env,'_starts_on_back') else None
        # Called after the vanilla test reset. Initial reward may be from previous
        # episode; it is replaced with zero in the archive, never used for training.
        self.capture()

    def finish(self, iteration, samples, extra_metadata=None, _arrays_only=False):
        self.enabled=False
        if self.count<2:
            return None
        data=self.data[:self.count].cpu().numpy()
        n=first_episode_end(data[:,0])
        pose=self.pose[:n].cpu().numpy()
        data=data[:n];data[0,0]=0;data[0,2]=0
        assert np.isfinite(pose).all() and np.isfinite(data).all()
        temp=self.directory/(self.filename+'.tmp.npz')
        metadata=dict(iteration=iteration,samples=samples,fps=self.fps,names=self.names,
            mode='deterministic evaluation',world=self.world,complete_episode=True,
            duration_seconds=float(data[-1,1]),terminal_flag=int(data[-1,0]),
            generated_unix=time.time(),capture_source='actual_newton_physics')
        if getattr(self.env,'task_name',None):
            metadata['task']=self.env.task_name
            metadata['terminal_meaning']='fixed finite horizon, not recovery success'
        if getattr(self.env,'task_name',None)in ('neutral_pose_mse','continuous_neutral_pose_mse','best_neutral_pose_mse'):
            metadata['neutral_body_positions']=self.env._neutral_positions[0].cpu().tolist()
            metadata['objective']='negative final body-position MSE in meters squared; current root XY/heading alignment'
            if self.env.task_name=='continuous_neutral_pose_mse':
                metadata['objective']='negative mean of per-frame body-position MSE; current root XY/heading alignment'
                metadata['loss_aggregation']='mean over all 45 frames'
                metadata['start_side']=self.start_side
            if self.env.task_name=='best_neutral_pose_mse':
                metadata['objective']='negative minimum body-position MSE over the episode including starting pose; current root XY/heading alignment'
                metadata['loss_aggregation']='minimum over starting pose and all 45 frames'
        if extra_metadata:
            metadata.update(extra_metadata)
        metadata.update(getattr(self,'equipment_metadata',{}))
        arrays={}
        if self.prior_values is not None:
            prior=self.prior_values[:n].cpu().numpy()
            metadata.update(frame_ae_raw=prior[:,0].tolist(),frame_tracking_mix=prior[:,1].tolist(),
                frame_reset_reason=prior[:,2].astype(int).tolist(),
                reset_reason_codes={'0':'none or normal-cohort rules','1':'failure','2':'head-height reset','3':'time reset (bootstrap)'})
        if getattr(self.env, '_additive_head_reward', False):
            # Reconstruct the exact independent term from recorded world-Z and tick;
            # this also avoids any extra per-physics-step recorder copy.
            target = float(self.env._idle_head_height[self.env._motion_ids[self.world]])
            active = bool(self.env._perturbed_getup[self.world]) & (np.rint(data[:,1]*self.fps) > 60)
            height_reward = np.clip(pose[:,self.env._head_id,2]/target, 0., 1.)*active
            height_reward[0] = 0.
            metadata['frame_head_height_reward'] = height_reward.tolist()
            metadata['frame_rewards'] = data[:,2].tolist()
            metadata['episode_return'] = float(data[1:,2].sum())
        if self.phase_values is not None and self.phase_agent is not None:
            metadata['frame_phase']=self.phase_values[:n].cpu().tolist()
            metadata['phase_columns']=['current_cos','current_sin','predicted_next_cos','predicted_next_sin','target_next_cos','target_next_sin']
        if self.reference_pose is not None:
            arrays['reference_pose'] = self.reference_pose[:n].cpu().numpy()
        if self.absolute_velocities is not None:
            arrays['world_velocities']=self.absolute_velocities[:n].cpu().numpy()
        if self.impacts is not None:
            impacts=self.impacts[:n].cpu().numpy();impacts[0]=[0.,-1.,0.]
            arrays['floor_impacts']=impacts
            metadata.update(floor_impact_limit_n=self.env.floor_impact_limit_n,
                floor_impact_scope='Peak normal floor force over all physics substeps for the explicitly listed bodies',
                floor_impact_bodies=self.env.floor_impact_bodies,
                frame_floor_peak_n=impacts[:,0].tolist(),frame_floor_peak_body=impacts[:,1].astype(int).tolist(),
                frame_failure_reason=impacts[:,2].astype(int).tolist(),
                failure_reason_codes={'0':'none','1':'foot distance','2':'floor impact','3':'foot distance and floor impact'})
        if getattr(self,'actual_amp_rewards',False):
            score=data[:,2]
            arrays['loss_terms']=-score[:,None]
            metadata.update(loss_term_names=['negative_imitation_reward'],
                rollout_losses={'negative_imitation_reward':float(-score.sum()),'total':float(-score.sum())},
                loss_weights={'negative_imitation_reward':1.},
                reward_measurement=('Stock discriminator evaluated on recorded test observations; no optimization' if metadata.get('mode')=='deterministic evaluation' else 'Exact AMP rewards copied after stock reward computation, before PPO optimization'))
        if self.components is not None:
            terms=self.components[:n].cpu().numpy();terms[0]=0
            arrays['loss_terms']=terms
            totals=terms.sum(axis=0)
            if hasattr(self.env,'replay_loss_metadata'):
                metadata.update(self.env.replay_loss_metadata())
                # Per-row reward overrides must survive the shared cohort metadata.
                row_info = getattr(self, 'equipment_metadata', {})
                metadata['normal_getup_failure_penalty'] = row_info.get('normal_getup_failure_penalty', 0.)
                if row_info.get('getup_position_reward_form') == 'linear_cost':
                    metadata.update(reward_from_loss='linear_cost',
                                    getup_failure_penalty=row_info.get('getup_failure_penalty',0.),
                                    getup_success_bonus=row_info.get('getup_success_bonus',0.),
                                    reward_definition='1 - weighted position MSE - terminal failure penalty + head-reset success bonus')
                if 'target_radius_m' in metadata and 'target_deviation' in metadata:
                    radii = metadata.get('target_radii_m', {})
                    active_bodies = metadata.get('target_termination_bodies')
                    metadata['target_deviation'] = dict(metadata['target_deviation'], radius_m=metadata['target_radius_m'],
                        points=[dict(point, radius_m=radii.get(point['body'], metadata['target_radius_m']))
                                for point in metadata['target_deviation']['points']
                                if active_bodies is None or point['body'] in active_bodies])
                metadata['rollout_losses']=dict(zip((*self.env.loss_term_names,'total'),[*map(float,totals),float(totals.sum())]))
            elif hasattr(self.env,'loss_term_names'):
                names=self.env.loss_term_names
                metadata.update(loss_term_names=list(names),
                    rollout_losses=dict(zip((*names,'total'),[*map(float,totals),float(totals.sum())])),
                    loss_weights=getattr(self.env,'loss_weights',dict.fromkeys(names,1.)),
                    objective=('Worst body per tick: equal-weight world position plus orientation-matrix MSE; both displayed components from that body' if getattr(self.env,'worst_body',False) else 'Equal-weight world position and orientation-matrix MSE')+'; fixed heading; current root XY alignment',
                    body_reduction='maximum_combined_error' if getattr(self.env,'worst_body',False) else 'mean',
                    loss_aggregation=f'Mean over all {self.env._episode_steps} ticks',
                    per_tick_coefficient=1/self.env._episode_steps,
                    target_body_positions=self.env._target_positions[0].cpu().tolist(),
                    target_body_rotations=self.env._target_rotations[0].cpu().tolist())
                if getattr(self.env,'height_band_weights',None) is not None:
                    metadata['objective']+='; plus fixed-weight head/pelvis squared distance outside 80-110% target-height bands'
                    metadata['height_band_fractions']=[.8,1.1]
                    metadata['height_band_targets']=self.env._target_positions[0,self.env._height_body_ids,2].cpu().tolist()
                if getattr(self.env,'height_bands_only',False):
                    metadata['objective']='Fixed-weight head and pelvis squared distance outside 80-110% target world-height bands; no body pose MSE'
                    metadata['body_reduction']='none'
                if getattr(self.env,'feet_lateral',None) is not None:
                    metadata['feet_lateral_max_width_m']=self.env._feet_max_width
                    metadata['feet_lateral_reference_width_m']=self.env.feet_lateral['reference_width_m']
                    if self.env.feet_lateral_termination:
                        metadata['objective']+='; early failure above pelvis-lateral foot separation limit, no foot loss or added failure cost'
                        metadata['terminal_meaning']='1=feet spread exceeds pelvis-lateral limit; 3=two-second timeout; no extra failure cost'
                        metadata['feet_lateral_termination']=True
                        metadata['loss_aggregation']=f'Sum of actual ticks until termination, each divided by the original {self.env._episode_steps}-tick horizon'
                        if self.env.termination_remaining_cost:
                            metadata['objective']=metadata['objective'].replace('no foot loss or added failure cost','no foot loss; charge failure-tick pose cost for remaining ticks')
                            metadata['terminal_meaning']='1=feet spread failure with remaining-tick cost; 3=two-second timeout'
                            metadata['loss_aggregation']+='; termination_remaining = failure-tick weighted loss times unplayed ticks'
                            metadata['termination_remaining_cost']=True
                    else:
                        metadata['objective']+='; plus squared excess foot separation along actual pelvis lateral axis'
                if getattr(self.env,'valid_reset_pose_pool',False):
                    metadata['reset_pose_pool']=self.env.reset_pose_pool_report
                if getattr(self.env,'feet_distance_multiple',None) is not None:
                    metadata.pop('feet_lateral_max_width_m',None)
                    metadata.pop('feet_lateral_reference_width_m',None)
                    metadata['feet_separation_metric']='3D Euclidean distance between foot body origins'
                    metadata['feet_reference_distance_m']=self.env._feet_reference_distance
                    metadata['feet_max_distance_m']=self.env._feet_max_width
                    metadata['feet_distance_multiple']=self.env.feet_distance_multiple
                    metadata['objective']=metadata['objective'].replace('pelvis-lateral foot separation','3D foot distance')
                    metadata['terminal_meaning']=metadata['terminal_meaning'].replace('feet spread','3D foot distance')
                if self.impacts is not None:
                    metadata['objective']+='; selected-body floor impact above threshold also terminates with the same remaining-tick cost'
                    metadata['terminal_meaning']='1=foot distance or selected-body floor impact failure with remaining-tick cost; 3=timeout'
            else:
                metadata['rollout_losses']=dict(zip(('early_pose','tail_mse','joint_velocity','total'),[*map(float,totals),float(totals.sum())]))
                metadata['objective']='Timing-weighted best-pose improvement plus weighted mean tail pose MSE and squared joint velocity'
                metadata['loss_weights']=dict(early_pose=1.0,tail_mse=self.env.tail_multiplier,joint_velocity=self.env.tail_multiplier*self.env.tail_velocity_weight)
                metadata['velocity_includes_pelvis']=self.env.include_pelvis_velocity
                metadata['neutral_body_positions']=self.env._neutral_positions[0].cpu().tolist()
        if self.phase_agent is not None and getattr(self.phase_agent._model,'_unit_phase',False):
            phase=self.phase_values[:n].cpu().numpy()
            weighted=((phase[:,2:4]-phase[:,4:6])**2).mean(-1)*self.phase_agent._phase_weight
            weighted[0]=0
            supervised = metadata.get('auto_phase_supervised', True)
            if not supervised:
                weighted[:] = 0
            arrays['loss_terms']=np.column_stack((arrays['loss_terms'],weighted))
            metadata['loss_term_names'].append('auto_phase')
            metadata['loss_weights']['auto_phase']=self.phase_agent._phase_weight if supervised else 0.
            metadata['rollout_losses']['auto_phase']=float(weighted.sum())
            metadata['rollout_losses']['total']+=float(weighted.sum())
            metadata['auto_phase_scope']='Supervised next-tick prediction at displayed state; clock input, no feedback'
            if metadata.get('auto_phase_feedback'):
                metadata['auto_phase_scope']='Next-tick phase feedback input; authored get-up target clock, then idle target follows prior-tick prediction'
            if metadata.get('perturbed_row'):
                metadata['auto_phase_scope']='Previous prediction supplies current input and current MSE target; next prediction supervises one nominal phase step forward'
            if not supervised:
                metadata['auto_phase_scope']='Autoregressive phase input; phase supervision disabled, loss exactly zero'
        if _arrays_only:return metadata,dict(pose=pose,data=data,**arrays)
        np.savez_compressed(temp,pose=pose,data=data,metadata=json.dumps(metadata),**arrays)
        temp.replace(self.directory/self.filename)
        return metadata


class TrainingRecorder(Recorder):
    """Capture one real training episode without extra steps or resets."""
    def __init__(self, env, directory, iteration, world=0, filename="replay.npz"):
        self.iteration=iteration
        self.pending=True
        self.ready=False
        self.first_action_iteration=None
        super().__init__(env,directory,world,filename)
        original_reset=env.reset
        def reset(env_ids=None):
            result=original_reset(env_ids)
            if (self.pending or self.enabled) and (env_ids is None or
                    (env_ids.numel()>0 and bool((env_ids==self.world).any()))):
                if self.enabled and self.count > 1 and getattr(self, 'actual_amp_rewards', False):
                    # End at this world's own terminal, before its next reset.
                    self.enabled=False
                    self.ready=True
                else:
                    self.pending=False
                    self.first_action_iteration=None
                    self.start()
            return result
        env.reset=reset

    def arm(self):
        if not self.enabled and not self.ready:self.pending=True

    def capture(self):
        if self.count==1:self.first_action_iteration=self.iteration()
        super().capture()
        if self.count==self.capacity-2:
            self.enabled=False
            self.ready=True

    def finish(self,iteration,samples,extra_metadata=None):
        assert self.ready
        extra=dict(extra_metadata or {},mode='actual training episode',
                   first_action_iteration=self.first_action_iteration,
                   last_action_iteration=iteration,evaluation_disabled=(extra_metadata or {}).get('evaluation_disabled',True))
        value=super().finish(iteration,samples,extra)
        self.ready=False
        return value


class AMPTrainingRecorder(TrainingRecorder):
    """Copy already-computed training rewards; no extra discriminator inference."""
    actual_amp_rewards=True

    def __init__(self,env,directory,agent,iteration,world=0,filename="replay.npz"):
        self.agent=agent
        self.reward_indices=[]
        super().__init__(env,directory,iteration,world,filename)
        original=agent._compute_rewards
        def rewards():
            result=original()
            if self.reward_indices:
                capture,steps=zip(*self.reward_indices)
                self.data[list(capture),2]=agent._exp_buffer.get_data('reward')[list(steps),self.world]
                self.reward_indices.clear()
            return result
        agent._compute_rewards=rewards

    def start(self):
        self.reward_indices.clear()
        super().start()

    def capture(self):
        i=self.count
        super().capture()
        if i>0:self.reward_indices.append((i,self.agent._exp_buffer._buffer_head))

    def finish(self,iteration,samples,extra_metadata=None):
        upright=bool(self.env._upright_cohort[self.world]) if hasattr(self.env,'_upright_cohort') else False
        extra=dict(extra_metadata or {},task='amp_standing',start_side='upright' if upright else self.start_side,
            cohort='upright' if upright else 'floor',
            terminal_meaning='1=failure (upright only); 3=timeout, not recovery success',
            evaluation_disabled=False)
        value=super().finish(iteration,samples,extra)
        return value


class AMPCohortRecorder:
    """One complete training episode per cohort; independent reset/terminal times."""
    def __init__(self,env,directory,agent,iteration):
        self.directory=Path(directory)
        upright=int(torch.nonzero(env._upright_cohort).flatten()[0])
        floor=int(torch.nonzero(~env._upright_cohort).flatten()[0])
        self.rows=[AMPTrainingRecorder(env,directory,agent,iteration,world,filename)
                   for world,filename in [(floor,'replay_floor.npz'),(upright,'replay_upright.npz')]]

    @property
    def ready(self):
        return all(row.ready for row in self.rows)

    def arm(self):
        for row in self.rows: row.arm()

    def suspend(self):
        for row in self.rows:
            row.enabled=False;row.pending=False;row.ready=False
            row.reward_indices.clear()

    def finish(self,iteration,samples,extra_metadata=None):
        assert self.ready
        metas=[row.finish(iteration,samples,extra_metadata) for row in self.rows]
        arrays={}
        for i,row in enumerate(self.rows):
            with np.load(self.directory/row.filename,allow_pickle=False) as data:
                suffix='' if i==0 else '_'+str(i)
                for key in ('pose','data','loss_terms'): arrays[key+suffix]=data[key]
        meta=dict(metas[0],replay_rows=metas)
        temp=self.directory/'replay.tmp.npz'
        np.savez_compressed(temp,metadata=json.dumps(meta),**arrays)
        temp.replace(self.directory/'replay.npz')
        return meta


class AMPTestRow(TrainingRecorder):
    """Capture existing TEST-mode motion, then score it in one small batch."""
    actual_amp_rewards=True

    def __init__(self,env,directory,agent,iteration,world,filename):
        self.agent=agent
        self.reward_indices=[]  # Shared suspend interface; no training reward hooks.
        super().__init__(env,directory,iteration,world,filename)
        self.pending=False
        self.disc_obs=torch.empty((self.capacity,*env._disc_obs_buf.shape[1:]),device=env._device)

    def capture(self):
        i=self.count
        super().capture()
        self.disc_obs[i].copy_(self.env._disc_obs_buf[self.world])

    def finish(self,iteration,samples,extra_metadata=None):
        assert self.ready
        with torch.no_grad():
            values=self.agent._calc_disc_rewards(self.agent._disc_obs_norm.normalize(self.disc_obs[1:self.count]))
            self.data[1:self.count,2]=self.agent._task_reward_weight*self.data[1:self.count,2]+self.agent._disc_reward_weight*values
        upright=bool(self.env._upright_cohort[self.world])
        extra=dict(extra_metadata or {},mode='deterministic evaluation',task='amp_standing',
            rollout_action_noise_std=0.,cohort='upright' if upright else 'floor',
            start_side='upright' if upright else self.start_side,evaluation_disabled=False,
            terminal_meaning='1=failure (upright only); 3=timeout, not recovery success')
        value=Recorder.finish(self,iteration,samples,extra)
        self.ready=False
        return value


class AMPTestCohortRecorder(AMPCohortRecorder):
    def __init__(self,env,directory,agent,iteration):
        self.directory=Path(directory)
        worlds=[]
        for mask,filename in [(~env._upright_cohort,'replay_floor.npz'),(env._upright_cohort,'replay_upright.npz')]:
            indices=torch.nonzero(mask).flatten()
            if indices.numel(): worlds.append((int(indices[0]),filename))
        self.rows=[AMPTestRow(env,directory,agent,iteration,world,filename)
                   for world,filename in worlds]

    def start(self):
        self.suspend()
        for row in self.rows:row.start()
