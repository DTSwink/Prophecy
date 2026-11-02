"""Exact box support height, two feet only; no contact queries or corner expansion."""
import torch


@torch.jit.script
def foot_box_bottoms(pos: torch.Tensor, rot: torch.Tensor, centers: torch.Tensor,
                     half_axes: torch.Tensor) -> torch.Tensor:
    # XYZW quaternion. Third row of the rotation matrix: world Z is vertical.
    x, y, z, w = rot.unbind(-1)
    up = torch.stack((2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)), -1)
    center_z = pos[..., 2] + (up*centers).sum(-1)
    extent_z = (up.unsqueeze(-2)*half_axes).sum(-1).abs().sum(-1)
    return center_z-extent_z


@torch.jit.script
def airborne_cost(bottoms: torch.Tensor, walking: torch.Tensor) -> torch.Tensor:
    # The lower foot must also clear 1 cm. A raised swing foot alone costs zero.
    return (bottoms.amin(-1)-.01).clamp_min(0.).square()*walking


def patch_source(source):
    assert 'walking_airborne' not in source
    source='from walking_airborne import foot_box_bottoms, airborne_cost\n'+source
    init='''        self._walking_airborne_weight = float(cfg.get('walking_airborne_weight', 0.))
        if not math.isfinite(self._walking_airborne_weight) or self._walking_airborne_weight < 0:
            raise ValueError('Walking airborne weight must be finite and nonnegative')
        if self._walking_airborne_weight:
            boxes = cfg['walking_foot_boxes']
            self._walking_foot_ids = torch.tensor([names.index(b['bone']) for b in boxes], device=self._device)
            self._walking_foot_centers = torch.tensor([b['center'] for b in boxes], device=self._device, dtype=torch.float32)
            self._walking_foot_half_axes = torch.tensor([b['half_axes'] for b in boxes], device=self._device, dtype=torch.float32)
            self.loss_term_names = (*self.loss_term_names, 'walking_airborne')
            self.loss_weights['walking_airborne'] = self._walking_airborne_weight
'''
    anchor='        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)\n'
    assert source.count(anchor)==1;source=source.replace(anchor,init+anchor)
    method='''    def _append_walking_airborne_loss(self, terms, pos, rot):
        if not self._walking_airborne_weight:
            return terms
        ids = self._walking_foot_ids
        bottoms = foot_box_bottoms(pos[:, ids], rot[:, ids], self._walking_foot_centers, self._walking_foot_half_axes)
        walking = (self._gaits[self._motion_ids] == 0) & ~self._recovery_rows
        cost = airborne_cost(bottoms, walking) * self._walking_airborne_weight
        return torch.cat((terms, cost[:, None]), -1)

'''
    anchor='    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):\n'
    assert source.count(anchor)==1;source=source.replace(anchor,method+anchor)
    for middle in ('terms, ae[:, None]', 'terms, ae[:, None], head_loss[:, None]'):
        old=f'return self._append_extremity_speed_loss(torch.cat(({middle}), -1), pos, vel, ang)'
        new=f'return self._append_walking_airborne_loss(self._append_extremity_speed_loss(torch.cat(({middle}), -1), pos, vel, ang), pos, rot)'
        assert source.count(old)==1;source=source.replace(old,new)
    compile(source,'perturbed_omni.py','exec')
    return source
