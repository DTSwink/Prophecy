"""Offline recovery of legacy target storage; never called inside inference.

Old NPZ target3 is in the exact authored/COM root at attacker Hit, NOT the
current root or the initial root. Recover the fixed point once on loading.
No interpolation/clamping guesses: use the exact stored sample or (Parry
only) its attested authored tail. New exports may supply target_world directly.
The resulting three numbers are an initial game attack command, not lookahead.
"""
import numpy as np


def recover_world_target(data):
    if 'target_world' in data:
        result=np.asarray(data['target_world'],dtype=np.float32)
    else:
        hit=float(data['hit_time'])
        indices=np.flatnonzero(np.abs(np.asarray(data['time'])-hit)<1e-8)
        if len(indices)==1:
            root=np.asarray(data['root'][indices[0]],dtype=np.float64)
        elif not len(indices) and int(data['motion_kind'])>=16:
            times=np.floor(data['time'][-1])+1+np.arange(len(data['root_tail']))
            indices=np.flatnonzero(np.abs(times-hit)<1e-8)
            if len(indices)!=1:raise ValueError('Exact target reference root missing; do not guess/interpolate')
            root=np.asarray(data['root_tail'][indices[0]],dtype=np.float64)
        else:
            raise ValueError('Exact target reference root missing; do not guess/interpolate')
        result=(np.asarray(data['target'],dtype=np.float64) @ root[3:].reshape(3,3)+root[:3]).astype(np.float32)
    if result.shape!=(3,) or not np.isfinite(result).all():raise ValueError('Invalid fixed world target')
    return result.copy()
