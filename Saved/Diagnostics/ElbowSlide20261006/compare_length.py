import json,math,pathlib
import numpy as np
p=pathlib.Path(__file__).parent
out={}
for mode in ['length_before','length_after']:
 d=json.loads((p/(mode+'.json')).read_text());rs={r['tick']:r for r in d['rows'] if r['player']}
 def bend(r,side,kind):
  u,e,h=[np.array(r['bones'][b+'_'+side][kind]['p']) for b in ['upperarm','lowerarm','hand']]
  a=e-u;b=h-e
  return float(np.degrees(np.arccos(np.clip(a@b/np.linalg.norm(a)/np.linalg.norm(b),-1,1))))
 out[mode]={'reason':d['reason'],'ticks':{}}
 for t in [960,961,962,963,964,965,966,968,970,972,974,976,978,980,982,984]:
  r=rs[t];out[mode]['ticks'][t]={'attack':r['attack'],'sides':{}}
  for side in ['l','r']:
   e,h=[r['bones'][b+'_'+side] for b in ['lowerarm','hand']]
   q0,q1=rs[t-1]['bones']['lowerarm_'+side]['presented']['q'],e['presented']['q']
   out[mode]['ticks'][t]['sides'][side]={'future_bend':bend(r,side,'future'),'presented_bend':bend(r,side,'presented'),'body_bend':bend(r,side,'body'),'forearm_length':math.dist(e['future']['p'],h['future']['p']),'elbow_step_degrees':math.degrees(2*math.acos(min(1,abs(sum(a*b for a,b in zip(q0,q1))))))}
 print(mode)
 for t,r in out[mode]['ticks'].items():print(t,r['attack'],{s:[round(v['future_bend'],2),round(v['body_bend'],2),round(v['forearm_length'],3)] for s,v in r['sides'].items()})
(p/'length-comparison.json').write_text(json.dumps(out,indent=2))
