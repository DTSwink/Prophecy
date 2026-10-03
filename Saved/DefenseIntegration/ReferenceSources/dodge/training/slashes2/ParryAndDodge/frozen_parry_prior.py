"""Upper-only energies from the existing frozen, whole-body parry priors.

The checkpoint inputs and normalization remain unchanged: lower-body motion is
still useful context. Only the final output rows for upper channels [41:131]
are evaluated/scored. Lower context is detached, but upper history/current and
conditioning remain differentiable. There is no new predictor or retraining.

As with RoutedPrior/RoutedStatuePrior, type_ids index sorted ``names``. The
experiment's batch loader must remap former leg rows to block_standard first.
"""
import torch
from torch import nn
from torch.nn import functional as F
from transition_features import FEATURE_DIM, LOWER_DIM, MOTION_DIM, UPPER_DIM


UPPER_PARRY_TYPES = ('block_alt1', 'block_alt2', 'block_standard', 'parry_weapon')


def detached_lower_context(rows):
    """Detach lower delta/history/current only; preserve every upper path."""
    pieces = []
    for start in (0, MOTION_DIM, 2 * MOTION_DIM):
        pieces.extend((rows[..., start:start + LOWER_DIM].detach(),
                       rows[..., start + LOWER_DIM:start + MOTION_DIM]))
    return torch.cat((*pieces, rows[..., 3 * MOTION_DIM:]), -1)


class _UpperRouted(nn.Module):
    def __init__(self, priors, network_name, *, allowed_types=UPPER_PARRY_TYPES, detach_lower=True):
        super().__init__()
        if not priors or set(priors) - set(allowed_types):
            raise ValueError('Expected upper parry priors; remap leg rows to block_standard')
        self.detach_lower=detach_lower
        self.names = tuple(sorted(priors))
        values = [priors[name] for name in self.names]
        self.register_buffer('mean', torch.stack([p.mean.detach() for p in values]))
        self.register_buffer('std', torch.stack([p.std.detach() for p in values]))
        if self.mean.shape != (len(values), FEATURE_DIM) or self.std.shape != self.mean.shape:
            raise ValueError('Wrong upper-prior normalization shape')
        networks = [getattr(p.model, network_name) for p in values]
        if any(len(n) != len(networks[0]) for n in networks):
            raise ValueError('Upper-prior architectures differ')
        last_index = len(networks[0]) - 1
        last = networks[0][-1]
        if not isinstance(last, nn.Linear) or last.out_features != MOTION_DIM:
            raise ValueError('Expected a final linear motion131 output')
        self.layers = []
        for i, layer in enumerate(networks[0]):
            peers = [network[i] for network in networks]
            if any(type(p) is not type(layer) for p in peers):
                raise ValueError('Upper-prior architectures differ')
            if isinstance(layer, (nn.Linear, nn.LayerNorm)):
                for field in ('weight', 'bias'):
                    tensors = [getattr(p, field) for p in peers]
                    if any(t is None for t in tensors):
                        raise ValueError('Expected affine checkpoint layers')
                    if any(t.shape != tensors[0].shape for t in tensors):
                        raise ValueError('Upper-prior layer shapes differ')
                    # Copy only scored output rows, not unused lower predictions.
                    selected = [t[LOWER_DIM:MOTION_DIM] if i == last_index else t for t in tensors]
                    self.register_buffer(f'layer_{i}_{field}', torch.stack([t.detach() for t in selected]))
            if isinstance(layer, nn.Linear):
                self.layers.append(('linear', i, None))
            elif isinstance(layer, nn.LayerNorm):
                if any(p.eps != layer.eps or p.normalized_shape != layer.normalized_shape for p in peers):
                    raise ValueError('Upper-prior LayerNorm settings differ')
                self.layers.append(('norm', i, (layer.normalized_shape, layer.eps)))
            elif isinstance(layer, nn.GELU):
                if any(p.approximate != layer.approximate for p in peers):
                    raise ValueError('Upper-prior GELU settings differ')
                self.layers.append(('gelu', i, layer.approximate))
            else:
                raise ValueError(f'Unsupported upper-prior layer: {layer}')

    def _normalize(self, rows, type_ids):
        if rows.ndim < 2 or rows.shape[-1] != FEATURE_DIM or type_ids.shape != (rows.shape[0],):
            raise ValueError('Expected rows [batch, ..., features] and one type index per batch row')
        shape = rows.shape[:-1]
        rows = (detached_lower_context(rows) if self.detach_lower else rows).reshape(rows.shape[0], -1, FEATURE_DIM)
        normalized = (rows - self.mean.index_select(0, type_ids)[:, None]) / self.std.index_select(0, type_ids)[:, None]
        return normalized, shape

    def _predict(self, x, type_ids):
        for kind, i, options in self.layers:
            if kind == 'gelu':
                x = F.gelu(x, approximate=options)
                continue
            weight = getattr(self, f'layer_{i}_weight').index_select(0, type_ids)
            bias = getattr(self, f'layer_{i}_bias').index_select(0, type_ids)
            if kind == 'linear':
                x = torch.bmm(x, weight.transpose(1, 2)) + bias[:, None]
            else:
                shape, eps = options
                x = F.layer_norm(x, shape, eps=eps) * weight[:, None] + bias[:, None]
        return x


class UpperRoutedPrior(_UpperRouted):
    """Normalized upper delta error; all existing predictor context retained."""
    def __init__(self, priors, **options):
        super().__init__(priors, 'projector', **options)

    def forward(self, rows, type_ids):
        normalized, shape = self._normalize(rows, type_ids)
        expected = self._predict(normalized[..., MOTION_DIM:], type_ids)
        return (normalized[..., LOWER_DIM:MOTION_DIM] - expected).square().mean(-1).reshape(shape)


class UpperRoutedStatuePrior(_UpperRouted):
    """Candidate-aware denoising energy averaged over the 90 upper channels."""
    def __init__(self, priors, **options):
        super().__init__(priors, 'correction', **options)

    def forward(self, rows, type_ids):
        normalized, shape = self._normalize(rows, type_ids)
        return self._predict(normalized, type_ids).square().mean(-1).reshape(shape)
