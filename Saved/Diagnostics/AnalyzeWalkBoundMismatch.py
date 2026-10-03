import json,pathlib,re,math
p=pathlib.Path(__file__).parent
for name in ['WalkBoundMismatch-before.json','WalkBoundMismatch.json']:
 d=json.loads((p/name).read_text());rows=[]
 for r in d['rows']:
  if not r['roots'] or 'walk_policy: True' not in r['pin'] or 'applies_to_visible_feet: True' not in r['pin']:continue
  root=r['roots'][0];a=math.radians(root['yaw']);h=(-math.sin(a),math.cos(a))
  m=next((m for m in r['meshes'] if m['name']=='PhysicalMesh'),None)
  if not m:continue
  eff=[float(v) for v in re.search(r'effective_pinning: \{x: ([-\d.]+), y: ([-\d.]+)',r['pin']).groups()]
  for side,foot in enumerate(m['feet']):
   back=sum((root['p'][i]-foot[i])*h[i] for i in range(2))
   if 25<back<55 and eff[side]>0:rows.append(dict(t=r['t'],side=side,back=back,pin=eff[side]))
 print(name,d['reason'],'rows',len(d['rows']),'inside',len(rows),'full',sum(r['pin']>=.9999 for r in rows))
 print(rows[:5])
