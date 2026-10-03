import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
exec((p/'AnalyzeFootFramePole.py').read_text().split('out=[]')[0].replace("mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'","mode='final'"))
report={}
for mode in ('old','final'):
 d=json.loads((p/f'RecoveryIsolationMix-{mode}-capture.json').read_text());rows=d['rows'];print(mode,d['reason'],len(rows),rows[-1]['tick']);assert d['reason']=='Complete'
 allvals=np.array([b['target']['p']+b['target']['q'] for x in rows for b in x['targets'].values()]);assert np.isfinite(allvals).all()
 def bone(x,n):return x['targets'][n]['target']
 def pole(x,s):
  h,k,f=[np.array(bone(x,n+'_'+s)['p']) for n in ('thigh','calf','foot')];ax=u(f-h);return R.from_quat(bone(x,'foot_'+s)['q']).inv().apply(u(k-h-ax*np.dot(k-h,ax)))
 def bend(x,s):
  h,k,f=[np.array(bone(x,n+'_'+s)['p']) for n in ('thigh','calf','foot')];return float(np.degrees(np.arccos(np.clip(u(k-h)@u(f-k),-1,1))))
 episodes=[]
 for i,x in enumerate(rows):
  if not i or x['attack']!='None' or rows[i-1]['attack']=='None':continue
  end=i+1
  while end<len(rows) and rows[end]['attack']=='None':end+=1
  if end-i<4:continue
  rec={'tick':x['tick'],'attack':rows[i-1]['attack'],'length':end-i}
  for s in ('l','r'):
   angles=[float(np.degrees(np.arccos(np.clip(pole(rows[j-1],s)@pole(rows[j],s),-1,1)))) for j in range(i+1,end)]
   bends=[bend(rows[j],s) for j in range(i,end)]
   rec[s]={'pole_peak':max(angles),'bend_step_peak':float(max(abs(np.diff(bends)))),'bend_min':min(bends),'bend_max':max(bends)}
  episodes.append(rec);print(mode,rec)
 checks=[]
 for line in (p/f'RecoveryIsolationMix-{mode}-frozen.jsonl').read_text().splitlines():
  r=json.loads(line);pr,b,a=[np.array(r[n]) for n in ('previous','before','after')];o=r['offset'];hp,ap,up,pp,rp=geom(pr,r);hb,axis,ub,pb,rb=geom(b,r);ha,aa,ua,pa,ra=geom(a,r)
  if rb<1e-5:continue
  if rp<1e-5:
   raw=np.array(r['pole'])@rot(pr,o+9);pp=u(raw-ap*np.dot(raw,ap))
  change=rot(pr,o+3).T@rot(a,o+3);ca=u(ap@change);cp=u(pp@change);c=np.clip(ca@axis,-1,1)
  transport=-cp if c<-1+1e-6 else cp-(ca+axis)*(np.dot(cp,axis)/max(1e-6,1+c));fr=u(transport-axis*np.dot(transport,axis))
  after=abs(signed(fr,pa,axis));budget=np.degrees(r['max_turn'])
  assert after<=budget+.002,(r['time'],after,budget)
  mask=np.ones(41,dtype=bool);mask[o+9:o+15]=False;assert np.array_equal(b[mask],a[mask])
  err=abs(np.linalg.norm(b[o:o+3]-hb-ub)-np.linalg.norm(a[o:o+3]-ha-ua))*100;assert err<.0001,err
  checks.append(err)
 print(mode,'connected pole samples',len(checks),'max calf error',max(checks))
 report[mode]={'episodes':episodes,'pole_samples':len(checks),'max_calf_error_cm':max(checks)}
(p/'RecoveryIsolationMix-summary.json').write_text(json.dumps(report,indent=2))
