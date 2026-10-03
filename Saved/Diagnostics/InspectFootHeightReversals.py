import json,pathlib
p=pathlib.Path(__file__).parent
for tag in ('foot-vibration','foot-vibration-fixed'):
 d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
 r=[x for x in d['rows'] if x['actor']=='BP_ProphecyManualPoseAgent_C_1']
 exits=[i for i in range(1,len(r)-60) if 'kick' in r[i-1]['attack'] and r[i]['attack']=='None']
 print(tag)
 for ei,i in enumerate(exits):
  z=[r[j]['meshes']['PhysicalMesh']['foot_r']['p'][2] for j in range(i,i+60)]
  peak=max(range(len(z)),key=z.__getitem__)
  turns=[j for j in range(1,len(z)-1) if (z[j]-z[j-1])*(z[j+1]-z[j])<0]
  print(ei,'peak',peak,'turns',[(j,round(z[j],4)) for j in turns],
    'tail',[(j,round(v,4)) for j,v in enumerate(z) if j>=36])
 print('row keys',r[exits[0]+45].keys(),'authored',r[exits[0]+45].get('authored'))
