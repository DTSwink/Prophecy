"""Live accepted lower networks, with external causal root-window conditioning."""
import copy
import json
from pathlib import Path
import torch
from torch import nn
from transition_agents import native
from dodge_movement_banks import root_window,next_root
from frozen_parry_lower import ACCEPTED


def validate_lower_identities(identities):
    actual={key:str(value).lower() for key,value in identities.items()}
    if actual!=ACCEPTED:raise ValueError('Live lower must use the accepted dataset walk/run checkpoints')
    return actual


class CommandStore:
    """Unmodified projection geometry; accepted checkpoint config, causal roots."""
    def __init__(self,base,cfg,state):
        self.base=base;self.cfg=cfg;self.state=state
    def __getattr__(self,key):return getattr(self.base,key)
    def get_input_root_features(self,clip_ids,cur_idx):
        s=self.state
        return root_window(s.previous_root,s.previous_axes,s.current_root,s.current_axes,
            s.initial_delta_world,s.initial_delta_yaw,int(self.cfg.future_window),
            self.cfg.max_speed_scale_final,self.cfg.max_turn_rate_scale_final,s.root_yaw_offset)[0]


class LiveLower(nn.Module):
    def __init__(self,skeleton,device,checkpoints=None,identities=None):
        super().__init__();self.skeleton=skeleton;self.configs={};self.checkpoints={}
        preview=native.neural_previews
        identity=(json.loads((native.HERE/'neural_preview_manifest.json').read_text())['source_identity']
                  if checkpoints is None else None)
        if checkpoints is not None and (set(checkpoints)!= {'walk','run'} or
                identities is None or set(identities)!= {'walk','run'}):
            raise ValueError('Embedded walk/run models require both checkpoint identities')
        self.identities=validate_lower_identities(
            {kind:identity[kind+'_checkpoint']['sha256'] for kind in ('walk','run')}
            if identity is not None else identities)
        self.models=nn.ModuleDict()
        for kind,path in (('walk',preview.WALK_CHECKPOINT),('run',preview.RUN_CHECKPOINT)):
            if checkpoints is None:
                if preview.file_sha256(path).lower()!=identity[kind+'_checkpoint']['sha256'].lower():
                    raise ValueError(f'Unaccepted frozen {kind} checkpoint')
                checkpoint=torch.load(path,map_location='cpu',weights_only=False)
            else:checkpoint=checkpoints[kind]
            cfg=native.frozen_runtime_data.apply_checkpoint_config(checkpoint,torch.device(device))
            model=preview.visualize.load_model(checkpoint,skeleton.runtime.lower_clip,cfg,torch.device(device))
            model.eval().requires_grad_(False)
            self.models[kind]=model;self.configs[kind]=cfg;self.checkpoints[kind]=checkpoint

    def forward(self,state,category):
        """category 0=walk/idle/turn, 1=run; both fixed graph branches are live."""
        ctl=native.ik_ctl;tl=native.tl
        candidates=[];pins=[]
        for kind in ('walk','run'):
            checkpoint=self.checkpoints[kind]
            root,prediction=native.neural_previews.visualize.checkpoint_output_contract(checkpoint)
            tl.OUTPUT_REFERENCE_ROOT=root;tl.OUTPUT_PREDICTION_MODE=prediction
            native.neural_previews.visualize.apply_simple_controller_policy(checkpoint)
            store=CommandStore(self.skeleton.lower_store,self.configs[kind],state)
            previous,current=state.previous_lower,state.current_lower
            ids=torch.arange(len(current),device=current.device)
            index=torch.ones_like(ids)
            payload=ctl.payload_slice(store)
            inputs=ctl.build_controller_input(store,ids,index,previous,current,previous[:,:3],current[:,:3],
                previous[:,payload],current[:,payload])
            raw=ctl.model_raw_output(self.models[kind],inputs,current,store.cfg)
            transition,_,pin=ctl.clean_output_vector_pair_with_pin_prob(raw,store,current,previous,apply_foot_projection=True)
            if not tl.output_reference_uses_current_root():
                point,axes=next_root(state.current_root,state.current_axes,state.initial_delta_world,
                    state.initial_delta_yaw,current.new_zeros((len(current),2)),root_yaw_offset=state.root_yaw_offset)
                transition=ctl.rebase_output_vector_root(store,transition,point,axes,state.current_root,state.current_axes)
            candidates.append(transition);pins.append(pin)
        mask=category[:,None].bool()
        return torch.where(mask,candidates[1],candidates[0]),torch.where(mask,pins[1],pins[0])
