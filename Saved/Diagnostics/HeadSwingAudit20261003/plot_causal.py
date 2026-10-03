import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent;a=json.loads((p/'model-audit.json').read_text())
fig,axs=plt.subplots(2,1,figsize=(12,8),sharex=True,constrained_layout=True)
colors={'baseline':'#222222','later_turn_stop':'#de7b16','no_feedback':'#3072bd','return_off':'#369055'}
for name,label in [('baseline','Normal replay'),('later_turn_stop','Facing target extended 45 degrees'),('no_feedback','Physical feedback disabled'),('return_off','FK return disabled')]:
 rows=[r for r in a[name]['metrics'] if 212<=r['tick']<=252]
 axs[1].plot([r['tick'] for r in rows],[r['presented_head_local_deg'] for r in rows],label=label,color=colors[name],lw=2)
 if name in ('baseline','later_turn_stop'):
  tr=[r for r in map(json.loads,(p/(name+'-inputs.jsonl')).read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0' and 210<=round(r['time']*60)<=252]
  axs[0].plot([round(r['time']*60) for r in tr],[abs(r['upper_input'][209])*24*30 for r in tr],color=colors[name],label=label,lw=2)
axs[0].set_title('The head response moves when the end of the root turn moves',loc='left',fontsize=16)
axs[0].set_ylabel('Root yaw speed (degrees / game second)')
axs[1].set_ylabel('Head relative to neck (degrees / game tick)');axs[1].set_xlabel('Game tick (60 ticks per game second)')
for ax in axs:ax.grid(alpha=.2);ax.legend(loc='upper right');ax.set_xlim(212,252)
fig.savefig(p/'causal-comparison.png',dpi=160)
