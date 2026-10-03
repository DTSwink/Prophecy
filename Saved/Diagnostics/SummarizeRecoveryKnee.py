import sys,json,pathlib,contextlib,io
with contextlib.redirect_stdout(io.StringIO()):
 import AnalyzeRecoveryKnee as a
p=pathlib.Path(__file__).parent
tags=sys.argv[1:] or ['knee-regression','knee-no-length-return','knee-source-off']
summary={}
for tag in tags:
 d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
 rows=[r for r in d['rows'] if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
 cases=[]
 for i in range(1,len(rows)-60):
  if 'kick' not in rows[i-1]['attack'] or 'kick' in rows[i]['attack']:continue
  case={'time':rows[i]['t'],'attack':rows[i-1]['attack'],'legs':{}}
  for side in ('l','r'):
   v=[a.step(rows[j-1]['meshes']['PhysicalMesh'],rows[j]['meshes']['PhysicalMesh'],side) for j in range(i,i+60)]
   total=0;arc=[0]
   for x in v:total+=x['swivel'];arc.append(total)
   case['legs'][side]={'thigh_step':max(x['thigh'] for x in v),'calf_step':max(x['calf'] for x in v),'swivel_step':max(abs(x['swivel']) for x in v),'swivel_excursion':max(arc)-min(arc)}
  cases.append(case)
 summary[tag]=cases
 print(tag,'exits',len(cases))
 for side in ('l','r'):
  print(side,{k:round(max(c['legs'][side][k] for c in cases),3) for k in ('thigh_step','calf_step','swivel_step','swivel_excursion')})
(p/'RecoveryKnee-episode-comparison.json').write_text(json.dumps(summary,indent=2))
