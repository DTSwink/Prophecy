"""Summarize completed isolated probes; no provider or training mutations."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).resolve().parents[2]/'Saved/MimicKitSlowLoco/crawl-capacity-20261102'
meta=json.loads((P/'metadata.json').read_text());physics=json.loads((P/'physics-details.json').read_text())
mass=np.asarray(meta['mass_kg']);caps=np.asarray(meta['caps_nm']);z=np.load(P/'selective/pull.npz')
caseinfo=json.loads((P/'selective/pull-metadata.json').read_text())
pos=z['pos'];rot=Rotation.from_quat(z['rot'].reshape(-1,4)).as_matrix().reshape(*pos.shape[:3],3,3)
com=((pos+np.einsum('tnbij,bj->tnbi',rot,physics['body_com']))*mass[None,None,:,None]).sum(2)/mass.sum()
assert np.isfinite(com).all() and np.max(np.abs(z['torque'][:,:,20:]))==0
groups={'torso':[0,1,2],'neck':[3,4,5],'shoulders':[6,7,8,13,14,15],'elbows':[9,16],'wrists':[10,11,12,17,18,19]}
rows=[]
for row in range(64):
    case=caseinfo['cases'][row//4];f=z['force'][:,row];t=z['torque'][:,row]
    cap=caps[:20]*np.array(case['joint_scale'])
    predicted=((599.5-np.arange(600))[:,None]*f.sum(1)[:,:2]).sum(0)/240**2/mass.sum()
    actual=com[-1,row,:2]-com[0,row,:2]
    rows.append(dict(case=case['kind'],multiplier=float(max(case['joint_scale'])),phase_seed=row%4,
        com_displacement_0033_to_25s_m=(com[-1,row]-com[0,row]).tolist(),
        pelvis_displacement_0_to_25s_m=(pos[-1,row,0]-z['initial_pos'][row,0]).tolist(),
        minimum_pelvis_head_height_m=pos[:,row,[0,2],2].min(0).tolist(),
        torso_pelvis_head_ground_impulse_ns=float(f[:,:3,2].sum()/240),
        arm_ground_force_mean_n=f[:,3:9].sum(1).mean(0).tolist(),
        leg_ground_force_mean_n=f[:,9:].sum(1).mean(0).tolist(),
        upper_positive_motor_work_j=float(np.maximum(t[:,:20]*z['qvel'][:,row,:20],0).sum()/240),
        torque_peak_nm=np.abs(t[:,:20]).max(0).tolist(),
        cap_saturation_fraction=((np.abs(t[:,:20])>=.95*np.maximum(cap,1e-6)).mean(0)).tolist(),
        force_integral_predicted_com_xy_m=predicted.tolist(),
        force_integral_vs_measured_xy_error_m=(predicted-actual).tolist(),
        ik_endpoint_errors_m=caseinfo['ik_errors_m'][row]))
selected={name:rows[i] for name,i in [('current',2),('shoulders2',6),('all_upper2',42),('hold',50),('off',54)]}
report=dict(checkpoint=18486,mass_kg=float(mass.sum()),passive_leg_mass_kg=float(mass[9:].sum()),
    upper_caps_nm={name:caps[indices].tolist() for name,indices in groups.items()},
    selected=selected,all_selective_trials=rows,
    completed_tests=dict(authored_12s=128,planted_hand_25s=64,selective_joint_25s=64),
    limitations=[
        'These are isolated controllers and matched starts, not additional policy training.',
        'No learned-policy or reference-servo condition established sustained 12-second legless crawling.',
        'Short pull establishes mechanical displacement, not a repeatable gait or target-speed feasibility.',
        'Both legs retain their masses, contacts and joint limits; only actuator torque is disabled.',
        'Four selective starts are from the reference; results do not cover arbitrary randomized passive-leg poses.',
        'The random-passive 12-second follow-up hit the 900-second audit watchdog before output; no result claimed.',
        'Thirty-Hz authored campaign torque samples may miss peaks; selective trials record all 240-Hz substeps.',
        'Stock ground-contact sensor in this solver exposes normals only. Selective ground forces reconstruct actual normal and manifold tangential impulses, excluding self-contact.',
        'Force-integral comparison includes a 33ms offset in measured COM and finite-step projection corrections.',
        'Repeated high-amplitude pulls showed sensitivity, including a late sideways collapse; 17cm COM example is a capacity witness, not a robustness claim.'
    ],conclusion='Current caps can support and produce an arm-driven pull with both leg torques zero. Sustained target-speed crawling remains unproven. Selective shoulder increases offer little gain in the tested stroke; contact/loading/coordination are stronger current suspects than a blanket torque shortage.')
(P/'analysis.json').write_text(json.dumps(report,indent=2))
fig,ax=plt.subplots(1,2,figsize=(11,4.4));time=np.arange(1,76)/30
colors=['#008d9c','#d5921e','#c64d69','#777777'];ids=[2,6,42,50];labels=['Current strength','Shoulders ×2','Whole upper body ×2','Hold pose control']
for row,label,color in zip(ids,labels,colors):
    ax[0].plot(time,(com[:,row,0]-com[0,row,0])*100,label=label,color=color,lw=2)
    ax[1].plot(time,pos[:,row,0,2]*100,color=color,lw=2,label=label)
for a in ax:
    a.axvspan(0,1,color='#999999',alpha=.09);a.set_xlabel('Time (seconds)');a.grid(alpha=.2);a.set_xlim(0,2.5)
ax[0].set_ylabel('Forward COM displacement (cm)');ax[0].axhline(0,color='black',lw=.5);ax[0].legend(fontsize=8)
ax[1].set_ylabel('Pelvis height (cm)')
fig.suptitle('Both legs passive: same initial pose, target and feedback controller',fontsize=13)
fig.text(.5,.01,'Shaded: 1-second pull command. Short-stroke capacity test; not sustained crawling. No training changes.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.045,1,.95));fig.savefig(P/'capacity-comparison.png',dpi=160);plt.close(fig)
print(json.dumps({k:{'COM_cm':v['com_displacement_0033_to_25s_m'][0]*100,'pelvis_cm':v['pelvis_displacement_0_to_25s_m'][0]*100,'min_height':v['minimum_pelvis_head_height_m']} for k,v in selected.items()},indent=2))
