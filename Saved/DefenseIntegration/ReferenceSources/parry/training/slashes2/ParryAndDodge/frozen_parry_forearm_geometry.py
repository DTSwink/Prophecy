"""Parry-only collider cross-section override; anatomical geometry is untouched."""
import torch

CONTRACT = 'parry_lowerarm_cross_section_0p6_long_axis_unchanged_v1'


def thin_forearms(geometry):
    if getattr(geometry, 'forearm_override', None) is not None:
        raise ValueError('Forearm override already applied')
    before = geometry.half_sizes_m.clone()
    half = before.clone()
    rows = {}
    for name in ('lowerarm_l', 'lowerarm_r'):
        i = geometry.names.index(name)
        axis = int(before[i].argmax())
        half[i] *= .6
        half[i, axis] = before[i, axis]
        rows[name] = dict(long_axis=axis, before_half_m=before[i].tolist(), after_half_m=half[i].tolist())
    geometry.half_sizes_m = half
    # The legacy base owns a separate tensor when anatomical EE boxes are added.
    geometry.base.half_sizes_m.copy_(half[:len(geometry.base.names)])
    geometry.forearm_override = dict(contract=CONTRACT, cross_section_scale=.6, colliders=rows)
    return geometry
