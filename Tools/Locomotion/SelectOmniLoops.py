"""Select unmodified full-stride intervals from recorded NN poses, at 60 Hz.

No synthesis, blending, time warp or writes to the original recordings.
Foot-contact labels below are kinematic proxies, not measured forces.
"""
from pathlib import Path
import json
import numpy as np
from scipy.signal import find_peaks
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Saved/Diagnostics/OmniRecord20261015'

def select(record):
    names = record['names']
    raw = np.asarray([r['pose'] for r in record['rows']])
    pos = raw[:, :, :3].copy()
    # Preserve height and world heading; remove accumulated horizontal travel.
    pos[:, :, :2] -= pos[:, :1, :2]
    quat = raw[:, :, 3:]
    vel = np.gradient(pos, 1/60, axis=0)
    rot = Rotation.from_quat(quat.reshape(-1, 4)).as_matrix().reshape(len(pos), len(names), 3, 3)
    step = rot[1:] @ rot[:-1].transpose(0, 1, 3, 2)
    omega_step = Rotation.from_matrix(step.reshape(-1, 3, 3)).as_rotvec().reshape(len(pos)-1, len(names), 3)*60
    omega = np.concatenate([omega_step[:1], (omega_step[:-1]+omega_step[1:])/2, omega_step[-1:]])
    feet = [names.index(n) for n in ['foot_l', 'ball_l', 'foot_r', 'ball_r']]
    # Same named feet must recur: a left/right exchange cannot count as a cycle.
    lag_error = np.array([np.mean((pos[k:, feet]-pos[:-k, feet])**2) for k in range(18, 97)])
    minima = find_peaks(-lag_error, prominence=np.ptp(lag_error)*.1)[0]+18
    if not len(minima):
        raise ValueError('No full-stride recurrence: '+record['asset'])
    period = int(minima[0])  # Later minima can be two or three strides.
    body = np.arange(1, len(names))
    height = raw[:, feet, 2].reshape(len(pos), 2, 2).min(axis=2)
    low = height <= np.percentile(height, 15, axis=0)+2
    # Near the floor and not rising/falling quickly. Not a collision assertion.
    support = low & (np.abs(np.gradient(height, 1/60, axis=0)) < 35)

    def metrics(a, b):
        delta = pos[b]-pos[a]
        angles = np.degrees(2*np.arccos(np.clip(np.abs(np.sum(quat[a]*quat[b], axis=-1)), 0, 1)))
        dv = vel[b]-vel[a]
        dw = np.degrees(omega[b]-omega[a])
        return {
            'position_rms_cm': float(np.sqrt(np.mean(np.sum(delta[body]**2, axis=-1)))),
            'rotation_rms_deg': float(np.sqrt(np.mean(angles[body]**2))),
            'velocity_rms_cm_s': float(np.sqrt(np.mean(np.sum(dv[body]**2, axis=-1)))),
            'angular_velocity_rms_deg_s': float(np.sqrt(np.mean(np.sum(dw[body]**2, axis=-1)))),
            'foot_max_cm': float(np.max(np.linalg.norm(delta[feet], axis=-1))),
            'pelvis_height_cm': float(abs(delta[names.index('pelvis'), 2])),
            'support_mismatch': int(np.count_nonzero(support[a] != support[b])),
            'max_rotation_deg': float(angles[body].max()),
        }

    def score(m):
        return ((m['position_rms_cm']/2)**2 + (m['rotation_rms_deg']/5)**2
                + (m['velocity_rms_cm_s']/25)**2 + (m['angular_velocity_rms_deg_s']/90)**2
                + (m['foot_max_cm']/2)**2 + (m['pelvis_height_cm']/1)**2
                + 2*m['support_mismatch'])

    candidates = []
    for span in range(round(period*.88), round(period*1.12)+1):
        for start in range(2, len(pos)-span-2):
            end = start+span
            m = metrics(start, end)
            # Include adjacent phases to avoid a coincidental one-frame match.
            cost = .6*score(m)+.2*score(metrics(start-1,end-1))+.2*score(metrics(start+1,end+1))
            candidates.append((cost,start,end,m))
    cost,start,end,m = min(candidates,key=lambda x:x[0])
    # Practical screening thresholds, not a claim of a mathematically seamless loop.
    limits = {'position_rms_cm':3, 'foot_max_cm':4, 'rotation_rms_deg':8,
              'max_rotation_deg':20, 'pelvis_height_cm':2,
              'velocity_rms_cm_s':60, 'angular_velocity_rms_deg_s':180, 'support_mismatch':0}
    warnings = [k for k,v in limits.items() if m[k]>v]
    return {'start':start,'end':end,'duration':(end-start)/60,
            'strideEstimateTicks':period,'score':cost,'metrics':m,
            'rootDisplacementCm':(raw[end,0,:3]-raw[start,0,:3]).tolist(),
            'warning':bool(warnings),'warningReasons':warnings}

if __name__ == '__main__':
    cuts = {}
    for path in sorted(SOURCE.glob('M_Neutral_*.json')):
        cuts[path.stem] = cut = select(json.loads(path.read_text()))
        print(path.stem, cut['start'], cut['end'], round(cut['score'],3), cut['warningReasons'])
    (SOURCE/'loop-cuts.json').write_text(json.dumps(cuts,indent=2))
