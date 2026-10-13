import argparse,csv,json,math,pathlib
p=argparse.ArgumentParser();p.add_argument('names',nargs='+');args=p.parse_args()
root=pathlib.Path('Saved/Diagnostics/ReachGrasp20261012');summary={}
def angle(a,b):return math.degrees(2*math.acos(min(1,abs(sum(x*y for x,y in zip(a[3:7],b[3:7]))))))
for name in args.names:
 d=json.loads((root/(name+'.json')).read_text());assert d['reason']=='captured',d['reason'];rows=d['rows'];result={'calls':d['calls'],'hands':[]}
 for side in range(2):
  active=[r for r in rows if r['hands'][side]['active'] and r['tick']>90]
  if not active:continue
  held=[r for r in active if r['hands'][side]['gripped']]
  stable=[r for r in held if 230<=r['tick']<=330]
  h={'side':side,'first_grip':held[0]['tick'] if held else None,'last_grip':held[-1]['tick'] if held else None}
  if stable:
   pos=[math.dist(r['hands'][side]['target'][:3],r['hands'][side]['physical'][:3]) for r in stable];rot=[angle(r['hands'][side]['target'],r['hands'][side]['physical']) for r in stable]
   h.update(max_wrist_error_cm=max(pos),max_wrist_error_deg=max(rot))
  result['hands'].append(h)
 native=root/(name+'-native');counts={}
 for file in native.glob('native-*.csv'):
  tick=int(file.stem.split('-')[-1]);lines=file.read_text().splitlines();parts=lines[0].split(',');counts[tick]={'joints':int(parts[1]),'pairs':int(parts[3])}
  if tick!=200:continue
  actual=list(csv.DictReader(lines[1:]));frame=next(r for r in rows if r['tick']==tick)
  for h in result['hands']:
   side=h['side'];values=[v for v in actual if int(v['side'])==side]
   if not values:continue
   h['finger_model_tracking_max_cm']=max(math.dist([float(v['model_'+x]) for x in 'xyz'],[float(v['actual_'+x]) for x in 'xyz']) for v in values)
   h['finger_collider_min_cm']=min(float(v['collider_distance_cm']) for v in values)
   if d['options']['kind']=='balls':
    center=frame['balls'][side][:3];h['finger_signed_sphere_clearance_min_cm']=min(math.dist([float(v['actual_'+x]) for x in 'xyz'],center)-d['options'].get('radius',6) for v in values)
 result['native_counts']=counts
 if (native/'performance.csv').exists():result['performance']=list(csv.DictReader((native/'performance.csv').read_text().splitlines()))[0]
 summary[name]=result
(root/'latest-validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
