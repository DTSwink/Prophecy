import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics')
a=json.loads((p/'CalfAnkleConnection-pelvis159-baseline.json').read_text())['rows'];a={round(x['t']*60):x for x in a if x['possessed']}
print('frame mode attack physicalXYZ deltaXYZ targetXYZ alpha')
for f in range(150,170):
 r=a[f];p0=np.array(r['meshes']['PhysicalMesh']['pelvis']['p']);last=np.array(a[f-1]['meshes']['PhysicalMesh']['pelvis']['p']);t=r['targets']['pelvis']
 print(f,r['mode'],r['attack'][:30],np.round(p0,3),np.round(p0-last,3),np.round(t['target']['p'],3),round(t['alpha'],3))
n=[json.loads(l) for l in (p/'FootVibration-nn-pelvis159-baseline.jsonl').read_text().splitlines()];n=[r for r in n if r['actor']==a[159]['actor']]
print('keys',list(n[0]))
for r in n:
 if 148<=round(r['time']*60)<=170:
  print('NN',round(r['time']*60),{k:r.get(k) for k in ('attack','walk_weight','left_walk_weight','right_walk_weight','tempering','right_foot_tempering')},'prev',np.round(r['previous_lower'][:3],5),'delta',np.round(r['lower_delta'][:3],5),'published',np.round(r['published_lower'][:3],5))
