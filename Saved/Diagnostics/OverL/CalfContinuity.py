import sys,pathlib,json,numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from CompareRecoveryLegs import load,OFF,rot

def audit(name):
 p,q,m=load(name); exits=[t for t in sorted(m) if t-1 in m and m[t-1]['attack'] and not m[t]['attack']]
 out=[]
 for ex in exits:
  end=next((t for t in sorted(m) if t>ex and m[t]['attack']),max(m)+1)
  records=[]
  for t in range(ex-4,end):
   if t not in m:continue
   r=m[t];rec={'tick':t,'attack':r['attack'],'tempering':q.get(t,{}).get('tempering'),'legs':{}}
   for i,side in enumerate(('l','r')):
    c=r['bones']['calf_'+side];f=r['bones']['foot_'+side];offset=OFF[19+4*i]*[100,-100,100]
    leg={}
    for kind in ('future','target','visible'):
     knee=np.array(c[kind]['p']);foot=np.array(f[kind]['p']);endpoint=knee+Rotation.from_quat(c[kind]['q']).apply(offset)
     leg[kind+'_gap']=float(np.linalg.norm(foot-endpoint));leg[kind+'_length']=float(np.linalg.norm(foot-knee))
     if t-1 in m:
      old=m[t-1]['bones']['calf_'+side][kind]
      leg[kind+'_calf_turn']=float(np.degrees((Rotation.from_quat(c[kind]['q'])*Rotation.from_quat(old['q']).inv()).magnitude()))
    rec['legs'][side]=leg
   records.append(rec)
  out.append({'exit':ex,'frames':records})
 (p/'calf-continuity.json').write_text(json.dumps(out,indent=2))
 print(p.name)
 for ex in out:
  print('EXIT',ex['exit'])
  for side in ('l','r'):
   records=ex['frames']; top=sorted(records,key=lambda r:r['legs'][side].get('target_calf_turn',0),reverse=True)[:4]
   print(side,'first',[(r['tick'],round(r['legs'][side]['future_gap'],3),round(r['legs'][side]['target_gap'],3),round(r['legs'][side].get('target_calf_turn',0),2)) for r in records[:8]],'top',[(r['tick'],round(r['legs'][side].get('target_calf_turn',0),2),round(r['legs'][side]['future_gap'],3)) for r in top])
 return out
if __name__=='__main__':
 for n in sys.argv[1:]:audit(n)
