import json,sys
from pathlib import Path
import numpy as np,torch
from idle_wobble import IdleWobble
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path('Saved/MimicKitLocomotion/idle-settle-20261030')
z=np.load(out/'latest-replay.npz');rows=json.loads(str(z['metadata']))['replay_rows'];results=[];series=[]
for i,m in enumerate(rows):
    if not m.get('idle_row'):continue
    s='' if i==0 else '_'+str(i);wv=z['world_velocities'+s];terms=z['loss_terms'+s];T=len(wv)
    obj=IdleWobble(1,15,'cpu');values=[];target_values=[];ref=IdleWobble(1,15,'cpu')
    active=torch.tensor([True]);kick=torch.tensor([-1])
    for t in range(T):
        if m['final_phase_cohort']=='idle perturbed-' and t>0 and t%60==0:kick.fill_(t)
        if m['final_phase_cohort']=='perturbed' and t==80:kick.fill_(t)
        values.append(float(obj.append(torch.tensor(wv[t:t+1,:,:3]),torch.tensor(wv[t:t+1,:,3:6]),kick,active)))
        target_values.append(float(ref.append(torch.tensor(wv[t:t+1,:,6:9]),torch.tensor(wv[t:t+1,:,9:12]),kick,active)))
    cost=np.array(values);total=terms.sum(-1)-terms[:,m['loss_term_names'].index('auto_phase')]
    # Exclude unavailable/terminal frames; per-push windows remain in the report.
    valid=(np.arange(T)>=8)&(np.arange(T)<T-1)
    windows={}
    for name,mask in [('prepush',(np.arange(T)>=10)&(np.arange(T)<60)),('postpush',(np.arange(T)>=60)&valid)]:
        windows[name]={'raw_mean':float(cost[mask].mean()),'head_reversal_mean':float(terms[mask,m['loss_term_names'].index('head_reversal')].mean()),'count':int(mask.sum())}
    results.append(dict(row=i,cohort=m['final_phase_cohort'],iteration=m['iteration'],raw_mean=float(cost[valid].mean()),base_loss_mean=float(total[valid].mean()),reference_raw_max=float(max(target_values)),windows=windows))
    series.append((m,cost,total,terms,wv))
weight=sum(r['base_loss_mean'] for r in results)/sum(r['raw_mean'] for r in results)/9
for r in results:r['calibrated_weight']=weight
(out/'audit.json').write_text(json.dumps(results,indent=2))
fig,axes=plt.subplots(3,len(series),figsize=(13,8),squeeze=False)
for col,(m,cost,total,terms,wv) in enumerate(series):
    axes[0,col].set_title(m['final_phase_cohort']+' / step '+str(m['iteration']))
    axes[0,col].plot(np.linalg.norm(wv[:,1,3:6],axis=-1)*180/np.pi,label='Torso angular speed (deg/s)')
    axes[1,col].plot(cost*weight,label='Candidate idle wobble')
    axes[1,col].plot(terms[:,m['loss_term_names'].index('head_reversal')],label='Existing head reversal',alpha=.7)
    axes[2,col].plot(total,label='Existing additive loss',alpha=.7);axes[2,col].plot(cost*weight,label='Candidate added cost')
    for ax in axes[:,col]:
        ax.legend();ax.grid(alpha=.25)
        for tick in ([60,120,180,240] if m['final_phase_cohort']=='idle perturbed-' else [80]):ax.axvline(tick,color='red',ls='--',alpha=.3)
    axes[2,col].set_xlabel('Frame; dashed lines are pushes')
fig.tight_layout();fig.savefig(out/'candidate.png',dpi=140)
print(json.dumps(results,indent=2))
