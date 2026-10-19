"""One-time, named motor-cap overrides; no per-step work or gain changes."""
import math
import numpy as np


def apply_torque_envelope(model, requested):
    starts=model.joint_qd_start.numpy()
    original=model.joint_effort_limit.numpy()
    updated=original.copy()
    if len(model.body_label)+1 != len(starts):
        raise ValueError('Torque envelope requires one joint per articulated body')
    found={}
    for joint,label in enumerate(model.body_label):
        lo,hi=map(int,starts[joint:joint+2]);count=hi-lo
        if count==6:continue  # floating root has no motor
        if count not in (1,3):raise ValueError('Unsupported motor joint width')
        body=label.rsplit('/',1)[-1]
        for axis,index in enumerate(range(lo,hi)):
            key=body if count==1 else f'{body}:{axis}'
            if key not in requested:continue
            value=float(requested[key])
            if not math.isfinite(value) or value<=0:raise ValueError('Invalid torque cap: '+key)
            new=max(float(original[index]),value)
            updated[index]=new
            row=dict(previous_nm=float(original[index]),requested_nm=value,applied_nm=float(updated[index]))
            if key in found and found[key]!=row:raise ValueError('Inconsistent per-world motor limits: '+key)
            found[key]=row
    missing=set(requested)-set(found)
    if missing:raise ValueError('Unknown torque envelope axes: '+str(sorted(missing)))
    model.joint_effort_limit.assign(updated)
    return dict(axes=found,existing_limits_never_reduced=True,gains_changed=False)
