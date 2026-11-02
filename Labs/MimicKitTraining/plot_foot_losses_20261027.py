"""Plot measured costs on the user's exact two replay segments."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare_foot_losses_20261027 import OUT

d=json.loads((OUT/'calibration.json').read_text())
w=np.array(d['weights'])
fig,axes=plt.subplots(3,1,figsize=(12,9),constrained_layout=True)
turn=d['selected']['18'];idle=d['selected']['0']
x=np.arange(len(turn['raw']));cost=np.array(turn['raw'])*w
axes[0].plot(x,cost[:,0],label='Excess stepping, including prior fade')
axes[0].plot(x,turn['base_curve'],alpha=.6,label='Existing total loss')
axes[0].set_xlim(0,65)
axes[0].set_title('Turnaround walk: 7 lift-offs in first 40 frames; normal walk: 3')
for tick,foot in turn['events']:
    if tick<=60:axes[0].axvline(tick,color=['tab:blue','tab:orange'][foot],alpha=.15)
x=np.arange(len(idle['raw']));cost=np.array(idle['raw'])*w
for axis,j,label in [(axes[1],1,'Foot translation reversal'),(axes[2],2,'Foot rotation reversal')]:
    axis.plot(x,cost[:,j],label=label)
    axis.axvspan(126,135,color='gold',alpha=.2,label='Reported jitter')
    axis.set_xlim(110,150)
    axis.set_ylim(0,max(.001,cost[110:151,j].max())*1.1)
for axis in axes:
    axis.set_ylabel('Weighted loss');axis.legend();axis.grid(alpha=.2)
axes[2].set_xlabel('Replay frame (30 Hz)')
fig.suptitle('Step 245159 - measured penalties on the supplied rollouts')
fig.savefig(OUT/'foot-loss-audit.png',dpi=150)
