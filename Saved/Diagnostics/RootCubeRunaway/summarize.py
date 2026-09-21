import json,math,collections,pathlib,sys
base=pathlib.Path(__file__).parent
result={}
for name in sys.argv[1:]:
 data=json.loads((base/(name+'.json')).read_text()); groups=collections.defaultdict(list)
 for row in data['rows']:groups[row['a']].append(row)
 report={}
 for actor,rows in groups.items():
  samples=list(zip(rows,rows[1:]))
  report[actor]={
   'root_net_travel_cm':math.dist(rows[0]['root'][:2],rows[-1]['root'][:2]),
   'max_physical_pelvis_speed_cm_s':max(math.dist(r['pv'],[0,0,0]) for r in rows),
   'max_pelvis_z_cm':max(r['pelvis'][2] for r in rows),
   'max_planar_pelvis_root_gap_cm':max(math.dist(r['pelvis'][:2],r['root'][:2]) for r in rows),
   'max_measured_planar_root_speed_cm_s':max(math.dist(r['root'][:2],p['root'][:2])/(r['t']-p['t']) for p,r in samples),
   'max_reported_root_speed_cm_s':max(math.dist(r['rv'][0],[0,0,0]) for r in rows if r['rv']),
   'final_target':rows[-1].get('target'),
   'final_root':rows[-1]['root'],
   'bounds_enabled_samples':sum(r['bounds'][0] for r in rows),
   'speed_cap_enabled_samples':sum(r['caps'][0] for r in rows),
  }
 result[name]={'reason':data['reason'],'actors':report}
print(json.dumps(result,indent=2))
(base/'comparison.json').write_text(json.dumps(result,indent=2))
