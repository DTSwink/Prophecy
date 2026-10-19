"""Batch-copy selected worlds during the existing noiseless evaluation."""
import copy
import json
import time

import numpy as np
import torch
from observe import Recorder


def select_replay_worlds(motions, idle_rows, equipment, rows, selection_round):
    """Balance equipment and cover clips, regardless of ordered world allocation."""
    selected=[]
    states=sorted(set(bool(equipment[m]) for m in motions))
    for state_index,state in enumerate(states):
        quota=rows//len(states)+(state_index==selection_round%len(states) and rows%len(states)>0)
        worlds=[w for w,m in enumerate(motions) if bool(equipment[m])==state]
        idle=[w for w in worlds if w<idle_rows]
        chosen=[]
        if idle and quota:
            chosen.append(idle[selection_round%len(idle)])
        clips={}
        for w in worlds:
            if w>=idle_rows:clips.setdefault(motions[w],[]).append(w)
        groups=list(clips.values());count=min(quota-len(chosen),len(groups))
        for i in range(count):
            group=groups[(i*len(groups)//count+selection_round)%len(groups)]
            chosen.append(group[selection_round%len(group)])
        chosen.extend(w for w in worlds if w not in chosen)
        selected.extend(chosen[:quota])
    # Handle a missing/small cohort without duplicates or changing any resets.
    selected.extend(w for w in range(len(motions)) if w not in selected)
    return selected[:min(rows,len(motions))]


class MultiRecorder(Recorder):
    def __init__(self,env,directory,rows=20):
        super().__init__(env,directory)
        self.row_count=min(rows,env._motion_ids.numel())
        self.selection_round=0
        for name in ('pose','reference_pose','absolute_velocities','data','components','impacts','phase_values'):
            value=getattr(self,name)
            if value is not None:
                setattr(self,name,torch.empty((self.capacity,self.row_count,*value.shape[1:]),device=value.device,dtype=value.dtype))

    def start(self):
        motions=self.env._motion_ids.cpu().tolist()
        idle=self.env._idle_rows
        equipment=self.env._equipment.cpu().tolist()
        selected=select_replay_worlds(motions,idle,equipment,self.row_count,self.selection_round)
        if getattr(self.env,'_recovery_ready',False):
            membership=self.env._recovery_rows.cpu().tolist()
            recovery_motion=self.env._recovery_motion.cpu().tolist()
            random_start=self.env._recovery_random_start_rows.cpu().tolist()
            examples={}
            for w in range(idle):
                key=(bool(equipment[motions[w]]),recovery_motion[w] if membership[w] else -1,
                     bool(random_start[w]) if membership[w] else False)
                examples.setdefault(key,w)
            priority=list(examples.values())
            selected=(priority+[w for w in selected if w not in priority])[:self.row_count]
        self.selection_round+=1
        self.ids=torch.tensor(selected,device=self.env._device,dtype=torch.long)
        self.row_metadata=[]
        arms=self.env._arm_enabled[self.ids].cpu().tolist()
        for i,w in enumerate(selected):
            self.row_metadata.append(dict(sword_drawn=bool(equipment[motions[w]]),arm_enabled=arms[i],
                idle_row=w<idle,idle_rows=idle,motion_file=self.env._motion_lib.get_motion_file(motions[w]),
                auto_phase_feedback=False))
            if getattr(self.env,'_recovery_ready',False):
                self.row_metadata[-1].update(self.env.recovery_row_metadata(w))
                if self.row_metadata[-1]['recovery_row']:
                    self.row_metadata[-1]['idle_motion_file']=self.row_metadata[-1]['motion_file']
                    self.row_metadata[-1]['motion_file']=self.row_metadata[-1]['recovery_motion_file']
        self.count=0;self.enabled=True;self.capture()

    def capture(self):
        i=self.count;ids=self.ids
        self.pose[i,:,:,:3].copy_(self.engine.get_body_pos(self.char)[ids])
        self.pose[i,:,:,3:].copy_(self.engine.get_body_rot(self.char)[ids])
        self.reference_pose[i,:,:,:3].copy_(self.env.reward_target_pos[ids])
        self.reference_pose[i,:,:,3:].copy_(self.env._ref_body_rot[ids])
        from util import torch_util as q
        angular=self.engine.get_body_ang_vel(self.char)[ids]
        velocity=self.engine.get_body_vel(self.char)[ids]-torch.cross(angular,q.quat_rotate(self.pose[i,:,:,3:],self.env._body_com[ids]),dim=-1)
        self.absolute_velocities[i].copy_(torch.cat((velocity,angular,self.env.reward_target_vel[ids],self.env.reward_target_ang[ids]),-1))
        self.data[i,:,0].copy_(self.env._done_buf[ids])
        self.data[i,:,1].copy_(self.env._time_buf[ids])
        self.data[i,:,2].copy_(self.env._reward_buf[ids])
        self.components[i].copy_(self.env.loss_terms[ids])
        if self.phase_agent is not None:
            obs=self.env._compute_obs(ids)
            with torch.no_grad():prediction=self.phase_agent._model.eval_phase(self.phase_agent._obs_norm.normalize(obs))
            self.phase_values[i].copy_(torch.cat((obs[:,-2:],prediction,self.env.next_phase_target()[ids]),-1))
        self.count+=1

    def finish(self,iteration,samples,extra_metadata=None):
        self.enabled=False;started=time.perf_counter();arrays={};metas=[]
        for i,w in enumerate(self.ids.cpu().tolist()):
            row=copy.copy(self);row.world=w;row.equipment_metadata=self.row_metadata[i]
            for name in ('pose','reference_pose','absolute_velocities','data','components','impacts','phase_values'):
                value=getattr(self,name)
                if value is not None:setattr(row,name,value[:,i])
            meta,values=Recorder.finish(row,iteration,samples,extra_metadata,_arrays_only=True)
            metas.append(meta)
            for key,value in values.items():arrays[key+('' if i==0 else '_'+str(i))]=value
        metadata=dict(metas[0],replay_rows=metas)
        temp=self.directory/'replay.tmp.npz'
        np.savez_compressed(temp,metadata=json.dumps(metadata),**arrays)
        temp.replace(self.directory/'replay.npz')
        (self.directory/'replay_capture.json').write_text(json.dumps(dict(rows=len(metas),
            archive_bytes=(self.directory/'replay.npz').stat().st_size,export_seconds=time.perf_counter()-started)))
        return metadata
