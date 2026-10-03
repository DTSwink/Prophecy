import pathlib,json,numpy as np
p=pathlib.Path('Saved/Diagnostics');data=json.loads((p/'Pelvis380-capture.json').read_text());r=data['rows'];print(data['reason'],len(r))
for i,x in enumerate(r):
 if i and (x['attack']=='None')!=(r[i-1]['attack']=='None'):print('transition',x['tick'],r[i-1]['attack'],x['attack'])
for i,x in enumerate(r):
 if not 357<=x['tick']<=407 or i<2:continue
 positions=[np.array(v['targets']['pelvis']['target']['p']) for v in r[i-2:i+1]];d=positions[2]-positions[1];acc=d-(positions[1]-positions[0]);row=[x['tick'],*[round(v,3) for v in d],round(np.linalg.norm(d[:2]),3),round(np.linalg.norm(acc),3)]
 for m in ('Mesh','PhysicalMesh'):
  if 'pelvis' not in x['meshes'][m]:continue
  a=np.array(x['meshes'][m]['pelvis']['p'])-r[i-1]['meshes'][m]['pelvis']['p'];row += [round(np.linalg.norm(a[:2]),3),round(a[2],3)]
 print(row)
nn=[json.loads(x) for x in (p/'Pelvis380-nn.jsonl').read_text().splitlines()];nn=[x for x in nn if x['actor']==r[0]['actor']]
print('NN keys',list(nn[0]));
for x in nn:
 t=round(x['time']*60)
 if 365<=t<=397:print('nn',t,'walk',x.get('walk_weight'),x.get('tempering'),'pelvisdelta',np.round(np.array(x['lower_delta'][:3])*100,3).tolist())

