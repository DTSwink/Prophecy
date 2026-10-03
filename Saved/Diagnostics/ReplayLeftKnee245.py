import json,pathlib,numpy as np,sys
from ReplayTemperedLeg import clean,rot,mixrot,points,info
p=pathlib.Path(__file__).parent
ns={'__file__':str(p/'ReplayWalkKneeGeometry.py')}
exec((p/'ReplayWalkKneeGeometry.py').read_text().split('rows=[r for r in map(json.loads')[0],ns)
tag=sys.argv[1] if len(sys.argv)>1 else 'left-knee-245'
actor=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows'][0]['actor']
rows=[json.loads(x) for x in (p/('FootVibration-nn-'+tag+'.jsonl')).read_text().splitlines()]
print('time rawdist temperdist pubdist rawbend pubbend rawcalf pubcalf pinoutputs')
for x in rows:
 if x['actor']!=actor or not 4.15<x['time']<4.55:continue
 raw=clean(np.array(x['lower_input'][:41])+x['lower_delta'][:41]);prev=np.array(x['previous_lower']);pub=np.array(x['published_lower']);tmp=raw.copy();s=x.get('tempering',[1]*6)
 for o,xy,z,r in ((0,s[2],s[5],s[3]),(9,s[0],s[4],s[1])):
  tmp[o:o+3]=prev[o:o+3]+(tmp[o:o+3]-prev[o:o+3])*[xy,xy,z]
  tmp[o+3:o+9]=mixrot(rot(prev,o+3),rot(tmp,o+3),r)[:2].ravel()
 vals=[]
 for q in (raw,tmp,pub):
  h,k,f,t=points(q);vals.append(np.linalg.norm(f-h)*100)
 print(round(x['time'],4),*[round(v,4) for v in vals],*[round(info(q)[z],4) for z in ('bend_cm','calf_cm') for q in (raw,pub)],x['lower_delta'][41:], 'sole clearance cm',round((pub[11]-ns['minimum'](pub,0))*100,4))
