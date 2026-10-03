import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=pathlib.Path('Saved/Diagnostics/Knee202')
data=json.loads((p/'arm_bounces_current.json').read_text());rows=data['rows']
def bones(row,kind):
 return row['meshes']['PhysicalMesh'] if kind=='physical' else {n:v[kind] for n,v in row['raw'].items()}
def geometry(row,kind):
 b=bones(row,kind);v=lambda n:np.array(b[n]['p']);s=v('upperarm_l');e=v('lowerarm_l');h=v('hand_l')
 out=s-v('upperarm_r');out/=np.linalg.norm(out)
 up=v('spine_05')-v('pelvis');up-=out*np.dot(up,out);up/=np.linalg.norm(up)
 fwd=np.cross(out,up);frame=np.array([out,fwd,up])
 return dict(elbow=frame@(e-s),hand=frame@(h-s),upper=np.linalg.norm(e-s),lower=np.linalg.norm(h-e))
exits=[r['tick'] for a,r in zip(rows,rows[1:]) if a['attack']!='None' and r['attack']=='None']
print('capture',data['reason'],'exits',exits)
fig,axes=plt.subplots(len(exits),3,figsize=(15,3.3*len(exits)),squeeze=False)
report=[]
for j,exit in enumerate(exits):
 window=[r for r in rows if exit-12<=r['tick']<=exit+65]
 t=np.array([r['tick'] for r in window]);item={'exit':exit}
 for kind in ['presented','physical']:
  g=[geometry(r,kind) for r in window];e=np.array([v['elbow'] for v in g]);h=np.array([v['hand'] for v in g])
  axes[j,0].plot(t,e[:,0],label=kind+' elbow');axes[j,1].plot(t,h[:,0],label=kind+' hand');axes[j,2].plot(t,e[:,1],label=kind+' elbow')
  if kind=='presented':
   sel=(t>=exit)&(t<=exit+35);ix=np.where(sel)[0];turns=[]
   for i in ix:
    if 0<i<len(t)-1 and (e[i,0]-e[i-1,0])*(e[i+1,0]-e[i,0])<0:turns.append([int(t[i]),float(e[i,0])])
   item.update(extrema=turns,samples=[{'tick':int(t[i]),'elbow':e[i].tolist(),'hand':h[i].tolist(),'length':g[i]['lower']} for i in range(len(t))])
   print('exit',exit,'outward extrema',np.round(turns,3))
   print('tick,out,forward,up,forearm',[(int(t[i]),*np.round(e[i],2),round(g[i]['lower'],2)) for i in ix if (t[i]-exit)%2==0])
 for k,title in enumerate(['Elbow outward from left shoulder','Hand outward from left shoulder','Elbow forward from left shoulder']):
  a=axes[j,k];a.axvline(exit,color='black',ls=':');a.set(title=f'End {exit}: {title}',xlabel='tick',ylabel='cm');a.grid(alpha=.3);a.legend()
 report.append(item)
fig.tight_layout();fig.savefig(p/'arm_bounces_current.png',dpi=135)
(p/'arm_bounces_current_analysis.json').write_text(json.dumps(report,indent=2))
