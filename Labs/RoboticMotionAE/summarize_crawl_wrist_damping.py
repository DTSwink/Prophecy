"""Summarize saved wrist-damping probes, without starting a simulator."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitSlowLoco/wrist-damping-20261103'
results=json.loads((OUT/'results.json').read_text())
paired=[]
for row in (0,2,5,7):
    baseline=next(r for r in results if r['row']==row and r['damping']==0)
    damped=next(r for r in results if r['row']==row and r['damping']==20)
    paired.append(dict(row=row,progress_retained=damped['forward_m']/baseline['forward_m'],
        wrist_change_reduction=1-damped['wrist_relative_omega_change_rms_rad_s']/baseline['wrist_relative_omega_change_rms_rad_s'],
        shoulder_change_reduction=1-damped['shoulder_omega_change_rms_rad_s']/baseline['shoulder_omega_change_rms_rad_s'],
        hand_cancellation_reduction=1-np.mean(damped['hand_cancellation_m_s'])/np.mean(baseline['hand_cancellation_m_s'])))
data=np.load(ROOT/'Saved/MimicKitSlowLoco/jolt-vibration-20261103/replay.npz')
p=data['reference_pose'][150:231]
rot=Rotation.from_quat(p[:,:,3:].reshape(-1,4))
q=rot.as_quat().reshape(81,15,4)
w=(Rotation.from_quat(q[1:].reshape(-1,4))*Rotation.from_quat(q[:-1].reshape(-1,4)).inv()).as_rotvec().reshape(80,15,3)*30
rel=w[:,[5,8]]-w[:,[4,7]]
speed=np.linalg.norm(rel,axis=-1)
summary=dict(paired=paired,reference_wrist_speed_rms_rad_s=float(np.sqrt(np.mean(speed**2))),
    reference_wrist_speed_p95_rad_s=float(np.percentile(speed,95)),
    reference_c20_damper_torque_rms_nm=float(20*np.sqrt(np.mean(speed**2))),
    note='Recorded-reference kinematics only; torque estimate is c times relative angular speed, not a capability test.',
    limitation='Frozen checkpoint22054, four warm starts150,80ticks, installed Jolt DLL; no retraining or production solver changes. No episode-reset success claim.')
(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
fig,axs=plt.subplots(3,1,figsize=(10,8),sharex=True,layout='constrained')
for c,color in [(0,'#c24b21'),(20,'#007e9f'),(100,'#7633ad')]:
    path=OUT/f'row0-c{c}.npz'
    if not path.exists():continue
    s=np.load(path)['states'];frames=np.arange(150,231)
    axs[0].plot(frames,(s[:,0,0]-s[0,0,0])*100,label=f'Wrist damping {c} N m s/rad',color=color)
    v=np.diff(s[:,5,:3]-s[:,0,:3],axis=0)*30
    axs[1].plot(frames[1:],v[:,0],color=color,alpha=.85)
    wr=s[:,5,10:13]-s[:,4,10:13]
    axs[2].plot(frames,np.linalg.norm(wr,axis=-1),color=color,alpha=.85)
axs[0].set_ylabel('Forward travel (cm)');axs[0].legend(fontsize=9)
axs[1].set_ylabel('Right hand forward velocity\nrelative to pelvis (m/s)')
axs[2].set_ylabel('Right wrist relative\nangular speed (rad/s)');axs[2].set_xlabel('Matched replay frame (30 Hz)')
for ax in axs:ax.grid(alpha=.2)
fig.suptitle('Passive wrist damping: rotation falls, hand translation still oscillates\nFrozen checkpoint22054, row0, same frame150 initial state; Jolt, no training change')
fig.savefig(OUT/'comparison.png',dpi=140)
print(json.dumps(summary,indent=2))
