"""Walking swing-height envelope, sharing the existing exact foot support query."""
import torch


@torch.jit.script
def height_excess(bottoms: torch.Tensor, limits: torch.Tensor, walking: torch.Tensor) -> torch.Tensor:
    return (bottoms.amax(-1)-limits).clamp_min(0.).square()*walking


def patch_source(source):
    assert '_walking_height_weight' not in source
    source='from walking_height import height_excess\n'+source
    init='''        self._walking_height_weight = float(cfg.get('walking_height_weight', 0.))
        if not math.isfinite(self._walking_height_weight) or self._walking_height_weight < 0:
            raise ValueError('Walking height weight must be finite and nonnegative')
        if self._walking_height_weight:
            if not self._walking_airborne_weight:
                raise ValueError('Walking height requires the configured foot-box detector')
            table = cfg['walking_height_reference']['motions']
            limits = []
            for i in range(self._motion_lib.get_num_motions()):
                path = Path(self._motion_lib.get_motion_file(i))
                entry = table.get(path.stem)
                if self._gaits[i] == 0:
                    if entry is None or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                        raise ValueError('Walking height reference is stale: ' + str(path))
                    limits.append(entry['max_height_m'])
                else:
                    limits.append(0.)
            self._walking_height_limits = torch.tensor(limits, device=self._device)
            self.loss_term_names = (*self.loss_term_names, 'walking_height_excess')
            self.loss_weights['walking_height_excess'] = self._walking_height_weight
'''
    anchor='        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)\n'
    assert source.count(anchor)==1;source=source.replace(anchor,init+anchor)
    old='''        cost = airborne_cost(bottoms, walking) * self._walking_airborne_weight
        return torch.cat((terms, cost[:, None]), -1)'''
    new='''        cost = airborne_cost(bottoms, walking) * self._walking_airborne_weight
        if self._walking_height_weight:
            high = height_excess(bottoms, self._walking_height_limits[self._motion_ids], walking) * self._walking_height_weight
            return torch.cat((terms, cost[:, None], high[:, None]), -1)
        return torch.cat((terms, cost[:, None]), -1)'''
    assert source.count(old)==1;source=source.replace(old,new)
    compile(source,'perturbed_omni.py','exec');return source
