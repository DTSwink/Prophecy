import json,pathlib,numpy as np,sys
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from CompareKnee1089Fixed import geom,step,load
p=pathlib.Path('Saved/Diagnostics');rs=load(sys.argv[1] if len(sys.argv)>1 else 'Knee1089FullFix');out=[];attacks=set();exits=0
for n,r in rs.items():
 if r['attack']!='None':attacks.add(r['attack'].split('policy_frame')[0])
 for b in r['targets'].values():
  for k in ('previous','future','target'):
   assert np.isfinite(b[k]['p']+b[k]['q']).all(),(n,k)
 if n-1 not in rs:continue
 if rs[n-1]['attack']!='None' and r['attack']=='None':exits+=1
 if r['attack']!='None' or rs[n-1]['attack']!='None':continue
 for side in ('l','r'):
  x=step(rs[n-1],r,side,'target');out.append(dict(tick=n,side=side,**x))
print('ticks',len(rs),'ends',min(rs),max(rs),'attack exits',exits)
for key in ('pole_turn','knee_step','thigh_turn'):
 print(key,[(x['tick'],x['side'],round(x[key],3),round(x['bend'],2)) for x in sorted(out,key=lambda x:x[key],reverse=True)[:8]])
print('local1089',[(x['tick'],x['side'],round(x['pole_turn'],2),round(x['knee_step'],2)) for x in out if 1087<=x['tick']<=1091])
(p/((sys.argv[1] if len(sys.argv)>1 else 'Knee1089FullFix')+'-summary.json')).write_text(json.dumps({'ticks':len(rs),'exits':exits,'locomotion_metrics':out},indent=2),encoding='utf-8')
