"""Isolated upper-only experiment bank; original Dodge/Parry loaders unchanged."""
import json
from pathlib import Path
import torch
import prepare_transition_corpus as corpus
from transition_batch import MotionBank, geometry_tensors
from transition_rollout import Episode
from transition_geometry import load_geometry
from transition_objective import load_prior
from transition_antistatuing import load_statue_prior
from defense_labels import RAW_TO_TYPE
from frozen_parry_lower import load_cache
from frozen_parry_agent import FrozenUpperParry
from frozen_parry_objective import UpperObjective, upper_block_masks
from frozen_parry_prior import UpperRoutedPrior, UpperRoutedStatuePrior, UPPER_PARRY_TYPES
from frozen_parry_blade_plane import prepare_planes
from frozen_parry_forearm_geometry import thin_forearms


class FrozenMotionBank(MotionBank):
    def __init__(self, path, lower_cache, device='cuda'):
        super().__init__(path, device)
        if self.kind != 'parry':
            raise ValueError('This experiment is Parry only')
        self.cache_path = Path(lower_cache)
        self.cache = load_cache(lower_cache, path)
        self.cached = {k: v.to(device) for k, v in self.cache['tensors'].items()}
        self.cache_slots = torch.full((len(self.rows),), -1, device=device, dtype=torch.long)
        self.cache_slots[torch.tensor(self.cache['indices'], device=device)] = torch.arange(
            len(self.cache['indices']), device=device)
        self.available = frozenset(self.cache['indices'])
        self.types = UPPER_PARRY_TYPES
        # Training-only timing target; never appended to policy observations.
        self.hit_times=torch.tensor([r['hit_time'] for r in self.rows],device=device,dtype=torch.float32)
        if not torch.isfinite(self.hit_times).all():raise ValueError('Nonfinite attacker hit metadata')
        drawn=[r['record']['scene']['drawn'] for r in self.rows]
        if any(type(v) is not bool for v in drawn):raise ValueError('Explicit defender drawn state required')
        # Harness dhDefenderSwordVisible: weapon parries always carry a sword;
        # the saved drawn checkbox only controls melee scenes.
        drawn=[v or r['row']['motion_kind'] in (16,17) for v,r in zip(drawn,self.rows)]
        self.drawn=torch.tensor(drawn,device=device,dtype=torch.float32)
        self.type_ids = torch.tensor([self.types.index(
            'block_standard' if r['row']['motion_kind'] in (22, 23)
            else RAW_TO_TYPE[r['row']['motion_kind']]) for r in self.rows], device=device)
        normals,valid=prepare_planes(self.data['episode'],[r['row']['motion_kind'] for r in self.rows])
        self.blade_planes={'blade_plane_normals':normals.to(device),'blade_plane_valid':valid.to(device)}

    def setup(self, indices, weights, priors_root, seed, run, statue_root=None,required_block_timing='free',full_arm_self_harm=False):
        if required_block_timing not in ('free','authored_or_previous'):
            raise ValueError('Unknown required-block timing')
        if required_block_timing=='authored_or_previous':
            from frozen_parry_timed_block import validate_block_times
            validate_block_times(self.data['episode']['times'],self.data['episode']['valid'],self.data['extra']['block_time'])
        if not set(map(int, indices)) <= self.available:
            raise ValueError('A sampled row has no attested frozen lower cache')
        prototype = self.data['prototype']; run = Path(run)
        assets = run / 'runtime_assets'; assets.mkdir(parents=True, exist_ok=True)
        source = assets / 'skeleton_source.npz'; source.write_bytes(prototype['source_bytes'])
        catalog = assets / 'colliders.json'; catalog.write_text(json.dumps(prototype['collider_catalog']))
        case = corpus.native.MotionCase(0, prototype['data'], prototype['record'], prototype['manifest'],
            source, prototype['data'], Path('.'))
        skeleton = corpus.native.build_skeleton([case] * len(indices), self.device)
        self.indices = torch.as_tensor(indices, device=self.device).clone()
        self.static_geometry = geometry_tensors(skeleton)
        selected_geometry = self.geometry_ids.index_select(0, self.indices)
        for key, target in self.static_geometry.items():
            target.copy_(self.geometry[key].index_select(0, selected_geometry))
        values = {k: v.index_select(0, self.indices).clone() for k, v in self.episode.items()}
        values.setdefault('authored_roots', None)
        self.selected = Episode(**values)
        slots = self.cache_slots.index_select(0, self.indices)
        selected_cache = {k: v.index_select(0, slots).clone() for k, v in self.cached.items()}
        torch.manual_seed(seed)
        if self.device.type == 'cuda': torch.cuda.manual_seed_all(seed)
        self.agent = FrozenUpperParry(skeleton, selected_cache,
            defender_drawn=self.drawn.index_select(0,self.indices).clone()).to(self.device)
        priors = {name: load_prior(Path(priors_root)/name/'best.pt', name, self.device) for name in self.types}
        prior = UpperRoutedPrior(priors)
        statue = None
        if weights.anti_statuing > 0:
            if statue_root is None: raise ValueError('Upper anti-statuing prior checkpoints required')
            statue = UpperRoutedStatuePrior({name: load_statue_prior(
                Path(statue_root)/name/'best.pt', name, self.device) for name in self.types})
        geometry = load_geometry(skeleton.body_names, parry=True, path=catalog, device=self.device)
        geometry.harness_identity = prototype['harness']
        thin_forearms(geometry)
        raw = [r['row']['motion_kind'] for r in self.rows]
        self.masks = {k: v.to(self.device) for k, v in zip(('present', 'blocking', 'harmful'),
            upper_block_masks(raw, geometry.names, 'cpu',drawn=self.drawn.cpu()))}
        self.objective = UpperObjective(skeleton, geometry, [raw[int(i)] for i in indices], weights,
            self.selected, prior, statue, self.type_ids.index_select(0, self.indices).clone(),
            self.extra['block_time'].index_select(0,self.indices).clone() if required_block_timing=='authored_or_previous' else None,
            full_arm_self_harm)
        for key,value in self.blade_planes.items():
            setattr(self.objective,key,value.index_select(0,self.indices).clone())
        self.objective.attacker_hit_time=self.hit_times.index_select(0,self.indices).clone()
        self._load(); self.load_graph = None
        if self.device.type == 'cuda':
            stream = torch.cuda.Stream(); stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream): self._load()
            torch.cuda.current_stream().wait_stream(stream)
            self.load_graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.load_graph, stream=stream): self._load()
        return self.agent, self.selected, self.objective

    @torch.no_grad()
    def _load(self):
        self.agent.defender_drawn.copy_(self.drawn.index_select(0,self.indices))
        for key, source in self.episode.items():
            getattr(self.selected, key).copy_(source.index_select(0, self.indices))
        geometry = self.geometry_ids.index_select(0, self.indices)
        for key, target in self.static_geometry.items():
            target.copy_(self.geometry[key].index_select(0, geometry))
        slots = self.cache_slots.index_select(0, self.indices)
        for key, source in self.cached.items():
            getattr(self.agent, 'cached_'+key).copy_(source.index_select(0, slots))
        for key, source in self.masks.items():
            getattr(self.objective, key).copy_(source.index_select(0, self.indices))
        self.objective.prior_type_ids.copy_(self.type_ids.index_select(0, self.indices))
        self.objective.attacker_hit_time.copy_(self.hit_times.index_select(0,self.indices))
        for key,source in self.blade_planes.items():
            getattr(self.objective,key).copy_(source.index_select(0,self.indices))
        if self.objective.block_time is not None:
            self.objective.block_time.copy_(self.extra['block_time'].index_select(0,self.indices))

    def select(self, indices):
        if not set(map(int, indices)) <= self.available:
            raise ValueError('A sampled row has no attested frozen lower cache')
        super().select(indices)
