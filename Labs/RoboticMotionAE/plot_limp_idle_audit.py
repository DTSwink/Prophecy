from pathlib import Path
import numpy as np,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'Saved/MimicKitSlowLoco/idle-asymmetry-audit-20261101'
z=np.load(out/'matched-phase-probe.npz');fig,axs=plt.subplots(1,3,figsize=(13,3.9),layout='constrained');t=np.arange(301)/30
for mid,name,color in [(8,'Left leg disabled','#2976b5'),(9,'Right leg disabled','#d66c21')]:
 ix=np.flatnonzero(z['motion_ids']==mid);err=np.linalg.norm(z['pos'][:,ix][:,:,[5,8]]-z['target_pos'][:,ix][:,:,[5,8]],axis=-1).mean(-1)*100;loss=z['loss'][:,ix].sum(-1)
 for ax,val in [(axs[0],err),(axs[1],np.exp(-loss))]:
  ax.plot(t,val.mean(-1),color=color,label=name);ax.fill_between(t,val.min(-1),val.max(-1),color=color,alpha=.15)
# Third panel is a direct diagnostic survival comparison; stop at first failure.
axs[2].clear()
a=np.load(out/'arms-servo-probe.npz')
for mid,name,color in [(8,'Left: restore target arms','#2976b5'),(9,'Right: restore target arms','#d66c21')]:
 ix=np.flatnonzero(a['motion_ids']==mid);failed=np.maximum.accumulate(a['done'][:,ix]==1,axis=0);axs[2].plot(t,(~failed).sum(-1),color=color,label=name,drawstyle='steps-post')
axs[2].axvline(2,color='#888',lw=1,ls=':');axs[2].set(title='Arm-only intervention at 2 seconds',xlabel='Seconds',ylabel='Trials not yet failed (of 8)',ylim=(-.2,8.5));axs[2].legend(fontsize=7);axs[2].grid(alpha=.2)
for ax,title,ylabel in zip(axs[:2],['Hands drift away from the target','Imitation reward becomes nearly flat'],['Mean hand error (cm)','Reward per tick (log scale)']):
 ax.set(title=title,xlabel='Seconds',ylabel=ylabel);ax.grid(alpha=.2)
axs[1].set_yscale('log');axs[0].legend(fontsize=7);fig.suptitle('Checkpoint 13788 — eight matched starting phases per idle; shaded range across phases',fontsize=11)
fig.savefig(out/'comparison.png',dpi=150);plt.close(fig)
