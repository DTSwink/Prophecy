"""Summarize matched checkpoint and target-support diagnostics."""
from pathlib import Path
import json,numpy as np
from scipy.signal import savgol_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[2];out=root/'Saved/MimicKitSlowLoco/limp-deep-audit-20261101'
a=np.load(out/'policy9189.npz');b=np.load(out/'policy9597.npz');assert np.array_equal(a['initial_obs'],b['initial_obs'])
summary=json.loads((out/'tracking-summary.json').read_text());dynamics=json.loads((out/'reference-dynamics.json').read_text());result={}
fig,axs=plt.subplots(3,2,figsize=(12,10))
for col,(motion,mid,foot,passive) in enumerate([('limpL',4,0,[12,13,14]),('limpR',5,1,[9,10,11])]):
    r=np.load(out/(motion+'-reference.npz'));t=r['times'];air=r['feet'][:,foot]>.01
    key=np.arange(0,len(t),8);acc=savgol_filter(r['com'][key,2],7,3,deriv=2,delta=1/30);force=1+acc/9.81
    # Interior swing samples avoid seam/boundary derivative artifacts.
    swing=(t[key]>=.1)&(t[key]<=.167)
    ii=np.flatnonzero(b['motion_ids']==mid);phase=b['initial_phase'][ii];sample=ii[np.argmin(abs(phase-.75))]
    first=np.flatnonzero(b['done'][:,sample]!=0);end=int(first[0]+1) if len(first) else 90
    tx=(np.arange(end)+1)/30
    axs[0,col].plot(t,r['feet'][:,foot]*100,label='Enabled foot target',color='#1565c0')
    axs[0,col].plot(t,r['feet'][:,1-foot]*100,label='Disabled foot target',color='#d84315')
    axs[0,col].set_title(motion);axs[0,col].set_ylabel('Lowest foot point (cm)');axs[0,col].set_ylim(-.3,6)
    axs[1,col].plot(t[key],force,color='#6a1b9a',label='Required net ground support')
    axs[1,col].axhline(0,color='k',ls=':',label='Ballistic flight: no support');axs[1,col].set_ylabel('Ground force / body weight');axs[1,col].set_ylim(-.1,1.5)
    for ax in axs[:2,col]:
        ax.fill_between(t,0,1,where=air,transform=ax.get_xaxis_transform(),color='#ffb300',alpha=.18,label='Enabled foot above 1 cm');ax.set_xlabel('Reference cycle time (s)');ax.set_xlim(0,float(t[-1]))
    axs[2,col].plot(tx,b['target_feet'][:end,sample,foot]*100,label='Enabled foot target',color='#1565c0')
    axs[2,col].plot(tx,b['feet'][:end,sample,foot]*100,label='Latest policy',color='#d84315')
    axs[2,col].set_ylabel('Lowest enabled foot point (cm)');axs[2,col].set_xlabel('Matched rollout time (s), until reset')
    for ax in axs[:,col]:ax.grid(alpha=.2);ax.legend(fontsize=8,loc='best')
    result[motion]=dict(required_disabled_support_bodyweights_frames3to5=force[swing].tolist(),mean_required_disabled_support_bodyweight=float(force[swing].mean()),initial_phase_of_plotted_rollout=float(b['initial_phase'][sample]),old=summary['policy9189'][motion],latest=summary['policy9597'][motion],inverse_dynamics_summary=dynamics[motion]['summary'],inverse_limit_caveat='Most small residuals during double support can disappear with passive ankle moments; critical swing frames3-5 remain inconsistent even allowing arbitrary passive ankle moments, and those frames have no joint limit violation.')
fig.suptitle('Limp target asks the disabled leg to support the body during the good foot’s swing\nLatest checkpoint still misses almost all requested foot lifts',fontsize=14);fig.tight_layout();fig.savefig(out/'target-support-and-policy.png',dpi=160)
(out/'diagnosis.json').write_text(json.dumps(dict(matched_starts=True,starts_per_motion=32,older_checkpoint=9189,latest_checkpoint=9597,additional_training_samples=408*65536,results=result,conclusion='Strong evidence of a target/actuation conflict, not simply inadequate good-hip torque. Generic hop feasibility does not establish feasibility of tracking this limp reference. No production changes.'),indent=2))
print(json.dumps({k:v['mean_required_disabled_support_bodyweight'] for k,v in result.items()}))
