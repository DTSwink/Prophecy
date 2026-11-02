"""Validate saved mechanical witnesses and plot physical evidence."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[2]
out=root/'Saved/MimicKitSlowLoco/limp-mechanical-capacity-20261101'
r=json.loads((out/'verification.json').read_text());d=np.load(out/'verification-trajectories.npz');mass=d['mass'].sum();dt=r['dt']
results=[];fig,ax=plt.subplots(2,2,figsize=(11,7),sharex=True)
for col,motion in enumerate(('limpL','limpR')):
    i=next(i for i,x in enumerate(r['reports']) if x['motion']==motion and x['group']=='single_foot_powered')
    off=next(j for j,x in enumerate(r['reports']) if x['motion']==motion and x['group']=='single_foot_motors_off')
    x=r['reports'][i]
    assert x['disabled_peak_torque_nm']==0 and x['disabled_impulse_ns']==0
    assert x['torque_over_cap_nm']<1e-4 and x['max_up_speed_m_s']>1
    assert not any(x['initial_geometry']['limits'].values())
    assert x['initial_geometry']['lowest_m']>=0 and x['initial_geometry']['self_collision_min_m']>0
    assert np.max(abs(d['velocity'][0,i]))<1e-6
    assert r['reports'][off]['airborne_samples']==0 and r['reports'][off]['com_rise_m']==0
    air=(d['feet'][:,i].min(1)>.01)&(d['floor'][:,i]>.005)
    longest=run=0
    for value in air:run=run+1 if value else 0;longest=max(longest,run)
    assert longest>=20
    impulse=float(d['force'][1:49,i,:,2].sum()*dt)
    required=float(mass*(d['velocity'][48,i,2]+9.81*.2))
    discrepancy=abs(impulse-required)/required
    assert discrepancy<.01
    position_error=float(np.max(abs(np.diff(d['com'][:55,i,2])-d['velocity'][1:55,i,2]*dt)))
    assert position_error<.0002
    result=dict(motion=motion,peak_com_up_speed_m_s=x['max_up_speed_m_s'],continuous_airborne_seconds=(longest-1)*dt,max_simultaneous_foot_clearance_m=x['max_both_feet_clearance_m'],com_rise_from_crouch_m=x['com_rise_m'],support_impulse_first_200ms_ns=impulse,passive_ground_impulse_first_200ms_ns=0.,momentum_balance_relative_error=discrepancy,max_com_position_integration_error_m=position_error,disabled_motor_torque_nm=0.,hip_cap_nm_per_axis=200,knee_cap_nm=300,ankle_cap_nm_per_axis=180)
    results.append(result)
    t=np.arange(len(d['com']))*dt
    ax[0,col].plot(t,d['velocity'][:,i,2],label='Direct motor commands',color='#1565c0')
    ax[0,col].plot(t,d['velocity'][:,off,2],label='Motors off',color='#777777',ls='--')
    ax[0,col].axhline(0,color='k',lw=.6);ax[0,col].set_ylim(-2,2);ax[0,col].set_title(motion+' — one powered leg')
    ax[0,col].set_ylabel('Whole-body upward velocity (m/s)')
    ax[1,col].plot(t,d['feet'][:,i,0]*100,label='Right foot',color='#ef6c00')
    ax[1,col].plot(t,d['feet'][:,i,1]*100,label='Left foot',color='#00897b')
    ax[1,col].axhline(1,color='k',ls=':',lw=.8,label='1 cm clearance')
    ax[1,col].set_ylabel('Lowest foot point above floor (cm)');ax[1,col].set_xlabel('Time from rest (seconds)');ax[1,col].set_ylim(-1,20)
    for a in ax[:,col]:
        a.fill_between(t,0,1,where=air,transform=a.get_xaxis_transform(),alpha=.13,color='green',label='Both feet airborne')
        a.set_xlim(0,.5);a.grid(alpha=.2);a.legend(fontsize=8,loc='lower left' if a is ax[0,col] else 'upper right')
fig.suptitle('Current actuator limits can produce a hop — no neural network\n78.25 kg body · hip 200 / knee 300 / ankle 180 Nm · passive leg torque = 0',fontsize=13)
fig.tight_layout();fig.savefig(out/'capacity-proof.png',dpi=160)
(out/'conclusion.json').write_text(json.dumps(dict(passed=True,method='Direct bounded velocity commands in actual 240 Hz simulator, independent of policy. Passive foot initially lifted by knee flexion; no ground contact contribution during push-off; initial pose collision-free and within joint limits. Motors-off negative controls. Two repetitions per condition.',limitations='Existence of a feasible takeoff, not optimal strength sizing, stable repeated hopping, exact reference tracking or learned-policy competence.',results=results),indent=2))
print(json.dumps(results,indent=2))
