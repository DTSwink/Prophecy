"""Resident motion bank, exact row geometry, balanced labels and graph loading."""
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import torch
from torch import nn
import prepare_transition_corpus as corpus
from transition_agents import VanillaDefense
from transition_rollout import Episode
from transition_geometry import load_geometry
from transition_objective import Objective,load_prior
from transition_routed_prior import RoutedPrior
from defense_labels import RAW_TO_TYPE
from pack_transition_training import SCHEMA,geometry_tensors


class BalancedSampler:
    """Equal type frequency over cycles; uniform random motion within type."""
    def __init__(self,rows,seed):
        self.names=tuple(sorted({r['row']['type'] for r in rows}))
        self.pools=[np.array([i for i,r in enumerate(rows) if r['row']['type']==name]) for name in self.names]
        self.rng=np.random.default_rng(seed);self.offset=0

    def sample(self,batch):
        types=(self.offset+np.arange(batch))%len(self.names)
        self.offset=(self.offset+batch)%len(self.names)
        return np.array([self.rng.choice(self.pools[t]) for t in types],dtype=np.int64)

    def state_dict(self):return dict(offset=self.offset,rng=self.rng.bit_generator.state)
    def load_state_dict(self,state):self.offset=state['offset'];self.rng.bit_generator.state=state['rng']


class MotionBank:
    objective_class=Objective
    def __init__(self,path,device='cuda'):
        self.path=Path(path);self.device=torch.device(device)
        self.data=torch.load(path,map_location='cpu',weights_only=False)
        d=self.data
        if d['schema']!=SCHEMA or d['feature_schema']!=corpus.features.SCHEMA:raise ValueError('Stale training pack')
        self.kind=d['kind'];self.rows=d['rows'];self.maximum=d['maximum']
        self.episode={k:v.to(device) for k,v in d['episode'].items()}
        self.extra={k:v.to(device) for k,v in d['extra'].items()}
        self.geometry={k:v.to(device) for k,v in d['geometry'].items()}
        self.geometry_ids=d['geometry_ids'].to(device)
        self.types=tuple(sorted({r['row']['type'] for r in self.rows}))
        self.type_ids=torch.tensor([self.types.index(r['row']['type']) for r in self.rows],device=device)
        if any(RAW_TO_TYPE[r['row']['motion_kind']]!=r['row']['type'] for r in self.rows):raise ValueError('Label mapping mismatch')

    def setup(self,indices,weights,priors_root,seed,run,statue_root=None,pin_checkpoint=None,*,pin_command_mode=None):
        d=self.data;prototype=d['prototype'];run=Path(run)
        assets=run/'runtime_assets';assets.mkdir(parents=True,exist_ok=True)
        source=assets/'skeleton_source.npz';source.write_bytes(prototype['source_bytes'])
        catalog=assets/'colliders.json';catalog.write_text(json.dumps(prototype['collider_catalog']))
        case=corpus.native.MotionCase(0,prototype['data'],prototype['record'],prototype['manifest'],
            source,prototype['data'],Path('.'))
        skeleton=corpus.native.build_skeleton([case]*len(indices),self.device)
        self.indices=torch.as_tensor(indices,device=self.device).clone()
        chosen_geometry=self.geometry_ids.index_select(0,self.indices)
        self.static_geometry=geometry_tensors(skeleton)
        for key,target in self.static_geometry.items():target.copy_(self.geometry[key].index_select(0,chosen_geometry))
        values={k:v.index_select(0,self.indices).clone() for k,v in self.episode.items()}
        values.setdefault('authored_roots',None)
        self.selected=Episode(**values)
        self.selected_extra={k:v.index_select(0,self.indices).clone() for k,v in self.extra.items()}
        torch.manual_seed(seed)
        if self.device.type=='cuda':torch.cuda.manual_seed_all(seed)
        from transition_agents import LEGACY_PIN_MODE
        self.agent=VanillaDefense(self.kind,skeleton,pin_command_mode=pin_command_mode or LEGACY_PIN_MODE).to(self.device)
        priors={name:load_prior(Path(priors_root)/name/'best.pt',name,self.device) for name in self.types}
        geometry=load_geometry(skeleton.body_names,parry=self.kind=='parry',path=catalog,device=self.device)
        geometry.harness_identity=prototype['harness']
        raw=[self.rows[int(i)]['row']['motion_kind'] for i in indices]
        e=self.selected_extra
        self.objective=self.objective_class(self.kind,skeleton,geometry,raw,priors,weights,self.selected,
            e.get('block_time'),e['foot_local'],e['foot_override'])
        self.objective.pin_command_mode=self.agent.pin_command_mode
        self.objective.routed_prior=RoutedPrior(priors)
        self.objective.register_buffer('prior_type_ids',self.type_ids.index_select(0,self.indices).clone())
        self.objective.priors=nn.ModuleDict();self.objective.groups=[]
        if statue_root is not None:
            from transition_antistatuing import load_statue_prior,RoutedStatuePrior
            statue={name:load_statue_prior(Path(statue_root)/name/'best.pt',name,self.device) for name in self.types}
            self.objective.routed_statue=RoutedStatuePrior(statue)
            if self.objective.routed_statue.names!=self.types:raise ValueError('Anti-statuing routing mismatch')
        elif weights.anti_statuing>0:raise ValueError('Positive anti-statuing weight requires models')
        if pin_checkpoint is not None:
            from transition_foot_pin import load_teacher
            self.objective.pin_teacher=load_teacher(pin_checkpoint,self.kind,self.device)
        elif weights.predictive_pin>0 or weights.anti_pin_slide>0:
            raise ValueError('Positive foot loss requires a pin predictor')
        self._load()
        self.load_graph=None
        if self.device.type=='cuda':
            stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):self._load()
            torch.cuda.current_stream().wait_stream(stream)
            self.load_graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.load_graph,stream=stream):self._load()
        return self.agent,self.selected,self.objective

    @torch.no_grad()
    def _load(self):
        for key,source in self.episode.items():getattr(self.selected,key).copy_(source.index_select(0,self.indices))
        for key,source in self.extra.items():self.selected_extra[key].copy_(source.index_select(0,self.indices))
        geometry=self.geometry_ids.index_select(0,self.indices)
        for key,target in self.static_geometry.items():target.copy_(self.geometry[key].index_select(0,geometry))
        for key in ('present','blocking','harmful'):
            getattr(self.objective,key).copy_(self.selected_extra[key])
        self.objective.prior_type_ids.copy_(self.type_ids.index_select(0,self.indices))

    def select(self,indices):
        if len(indices)!=self.indices.numel():raise ValueError('Cannot resize a captured batch')
        self.indices.copy_(torch.as_tensor(indices,device=self.device))
        if self.load_graph is None:self._load()
        else:self.load_graph.replay()

    def cases(self,indices):
        result=[]
        for index in indices:
            i=int(index);entry=self.rows[i];length=entry['length']
            data=dict(root=self.data['extra']['authored_display'][i,:length].numpy(),
                motion_kind=entry['row']['motion_kind'],hit_time=entry['hit_time'])
            result.append(SimpleNamespace(data=data,record=entry['record'],motion_id=entry['row']['id'],source_row=entry['row']))
        return result
