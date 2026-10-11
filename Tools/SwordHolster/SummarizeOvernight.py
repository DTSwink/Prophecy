"""Compact evidence receipt; motion completion is distinct from smoothness."""
import csv,json,pathlib,statistics,math
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/SwordOvernight20261011'
def read(p):return json.loads((out/p).read_text(encoding='utf-8-sig'))
native=read('native-final/automation/index.json')
lab=read('lab-verified/summary.json');life=read('lifecycle/summary.json')
matrix=read('rebuilt-matrix/analysis.json');repeat=read('repeated-final/analysis.json')
turn=read('repeated-turn-final/analysis.json')
assert native['succeeded']==12 and native['failed']==0
assert len(lab)==25 and all(x['exit']==0 for x in lab)
assert len(life)==11 and all(x['reason'].startswith('passed') for x in life)
assert len(matrix)==13 and len(repeat)==2 and len(turn)==1
for case in matrix+repeat+turn:
 assert case['reason']=='cycles completed' and case['missing_ticks']==0,case['name']
 assert all(abs(t-1/60)<1e-8 for t in case['dt_range'])
 assert all(a['nonfinite']==0 for a in case['actors'].values())
for case in repeat+turn:assert all(a['action']['cycles']==3 for a in case['actors'].values())

def compare(a,b):
 a=read(a);b=read(b);br={r['tick']:r for r in b['rows']}
 result={'samples':0,'actors':{},'rows':[len(a['rows']),len(b['rows'])]}
 for row in a['rows']:
  if row['tick'] not in br:continue
  result['samples']+=1
  for name,v in row['actors'].items():
   dest=result['actors'].setdefault(name,{'first_difference':None,'max_component_difference':0,'phase_differences':0})
   w=br[row['tick']]['actors'][name]
   dest['phase_differences']+=v['fields']['phase']!=w['fields']['phase']
   for channel in ['future','target','physical','equipment','equipment_scale']:
    for bone,transform in v[channel].items():
     delta=max(abs(x-y) for x,y in zip(transform,w[channel][bone]))
     dest['max_component_difference']=max(dest['max_component_difference'],delta)
     if delta and dest['first_difference'] is None:dest['first_difference']=[row['tick'],channel,bone,delta]
 return result

rows=list(csv.DictReader((out/'native-final/stagger-benchmark.csv').open(encoding='utf-8-sig')))
performance=[]
for n,name in enumerate(['idle D','idle S','walk D','walk S','mixed simultaneous','mixed arrivals']):
 samples=[r for r in rows if int(r['scenario'])==n and r['stagger']=='1'];assert len(samples)==7
 performance.append(dict(name=name,mean_ms=statistics.median(float(r['total_ms'])/int(r['frames']) for r in samples),peak_ms=statistics.median(float(r['peak_ms']) for r in samples),admission_peak_ms=statistics.median(float(r['start_peak_ms']) for r in samples),worst_ms=max(float(r['peak_ms']) for r in samples)))
geometry=list(csv.DictReader((out/'geometry-benchmark.csv').open(encoding='utf-8-sig')))
assert len(geometry)==21
geometry_values=[float(r['microseconds_per_sample']) for r in geometry]
result={
 'status':'Controller regressions pass; physical constraints, folded-arm geometry and crowd contacts remain documented limitations.',
 'native':{k:native[k] for k in ['succeeded','failed']},
 'native_details':[{ 'name':t['fullTestPath'],'messages':[e['event']['message'] for e in t['entries']]} for t in native['tests']],
 'lab':lab,'lifecycle':life,'matrix':matrix,'repeated_runs':repeat+turn,
 'postflight':read('postflight-final.json'),
 'fps_compare':compare('repeated-final/sim-run-60--0.141.json','repeated-final/sim-run-20--0.141.json'),
 'performance_100_agents':performance,
 'performance_scope':'Procedural admission/math only; excludes NN, skeleton discovery, cache publication, equipment, physics and rendering. Seven repeats; peak is median of per-run maxima, worst also retained.',
 'geometry_sampling_us':{'median':statistics.median(geometry_values),'max':max(geometry_values),'samples_per_repeat':1000,'agents':3,'repeats':7},
 'raw_evidence':'Saved/Diagnostics/SwordOvernight20261011',
 'limitations':['Original obstacle-destruction fixture was unreliable; repeated run fixture explicitly disables Cube collision in owned PIE only.','Restoring saved neck limits causes physical kicks at extreme gaze; authored whole-neck handoff is continuous.','Closest-shoulder objective can produce near-fully-folded elbows and fast arm rotation.','Crowd equipment contact can delay actual-world sheath acceptance.','No human visual motion acceptance and no whole-game FPS performance claim.']}
(root/'Tools/SwordHolster/Overnight20261011.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'native':result['native'],'lab':len(lab),'lifecycle':len(life),'matrix':len(matrix),'repeated':len(repeat),'fps':result['fps_compare'],'performance':performance,'geometry':result['geometry_sampling_us']},indent=2))
