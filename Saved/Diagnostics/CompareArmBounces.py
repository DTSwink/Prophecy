import pathlib,json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
src=pathlib.Path('Saved/Diagnostics/AnalyzeArmBounces.py').read_text()
exec(src[:src.index('exits=')])
fig,axes=plt.subplots(4,2,figsize=(12,12));summary={}
for tag in ['arm_bounces_current','arm_bounces_fixed']:
 d=json.load(open(p/(tag+'.json')));rr=d['rows'];lookup={r['tick']:r for r in rr}
 exits=[r['tick'] for a,r in zip(rr,rr[1:]) if a['attack']!='None' and r['attack']=='None']
 print(tag,d['reason'],'exits',exits);summary[tag]=[]
 for row in rr:
  for bone in row['raw'].values():
   for k in ['future','presented']:assert np.isfinite(bone[k]['p']+bone[k]['q']).all()
 for j,end in enumerate(exits[:4]):
  window=[lookup[t] for t in range(end-8,min(end+61,max(lookup))+1) if t in lookup]
  ts=np.array([r['tick']-end for r in window]);e=np.array([geometry(r,'presented')['elbow'][0] for r in window]);h=np.array([geometry(r,'presented')['hand'][0] for r in window])
  # Maximum outward retracing of the already-inward path, early recovery only.
  chosen=e[(ts>=0)&(ts<=15)];low=np.minimum.accumulate(chosen);rebound=float(np.max(chosen-low))
  item=dict(exit=end,early_elbow_rebound_cm=rebound);summary[tag].append(item);print('attack',j+1,item)
  for k,y in enumerate([e,h]):
   ax=axes[j,k];ax.plot(ts,y,label=tag.removeprefix('arm_bounces_'));ax.axvline(0,color='black',ls=':');ax.set(xlabel='ticks after upper end',ylabel='cm outward from left shoulder',title=f'Attack {j+1}: '+['elbow','hand'][k]);ax.grid(alpha=.3);ax.legend()
fig.tight_layout();fig.savefig(p/'arm_bounces_comparison.png',dpi=140);(p/'arm_bounces_comparison.json').write_text(json.dumps(summary,indent=2))
