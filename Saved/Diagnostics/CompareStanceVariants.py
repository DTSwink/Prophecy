import pathlib,json,sys,contextlib,io
sys.argv=['x','stance-follow-variants']
with contextlib.redirect_stdout(io.StringIO()):import AnalyzeRecoveryKnee as a
p=pathlib.Path(__file__).parent;out={}
for tag in ('knee-variants-aligned','stance-follow-variants'):
 rows=[r for r in json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows'] if r['actor'].endswith('_C_1')]
 cases=[]
 for i in range(1,len(rows)-2):
  if rows[i]['attack']!='None' or rows[i-1]['attack']=='None' or rows[i]['t']<1.5:continue
  end=i
  while end<len(rows) and end<i+60 and rows[end]['attack']=='None':end+=1
  case={'attack':rows[i-1]['attack'],'time':rows[i]['t'],'frames':end-i,'legs':{}}
  for s in ('l','r'):
   values=[a.step(rows[j-1]['meshes']['PhysicalMesh'],rows[j]['meshes']['PhysicalMesh'],s) for j in range(i,end)]
   arc=[0.]
   for v in values:arc.append(arc[-1]+v['swivel'])
   case['legs'][s]={'thigh':max(v['thigh']for v in values),'swivel':max(abs(v['swivel'])for v in values),'calf':max(v['calf']for v in values),
    'swivel_excursion':max(arc)-min(arc)}
  cases.append(case)
 out[tag]=cases
 print(tag)
 for c in cases:print(c['attack'],c['frames'],{s:{k:round(v,2)for k,v in vs.items()}for s,vs in c['legs'].items()})
(p/'StanceFollow-variants.json').write_text(json.dumps(out,indent=2))
