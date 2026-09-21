import pathlib,json,re,statistics
folder=pathlib.Path(__file__).resolve().parent
log=(folder.parents[1]/'Logs/GameAnimationSample3.log').read_text(errors='replace')
out={}
for f in folder.glob('*.json'):
 if f.name in ('summary.json',):continue
 d=json.loads(f.read_text())
 if 'rows' not in d:continue
 name=f.stem
 rows={str(r['n']):r for r in d['rows'] if r['agent']=='BP_ProphecyManualPoseAgent_C_1'}
 found=re.findall(r'CONTACT_EXP,'+re.escape(name)+r'_BP_ProphecyManualPoseAgent_C_1_(\d+),joint,(\w+),([0-9.e+-]+),([0-9.e+-]+),(\d+),(\d+)',log)
 samples=[{'n':int(n),'joint':joint,'gap_cm':float(g),'lambda':float(l),'v':int(v),'p':int(p),'attack':rows.get(n,{}).get('attack')} for n,joint,g,l,v,p in found if int(n)>=60]
 (folder/(name+'.native.json')).write_text(json.dumps(samples))
 report={'mode':d.get('mode'),'error':d.get('error'),'joints':{}}
 for joint in ['upperarm_l','lowerarm_l','hand_l']:
  s=[r for r in samples if r['joint']==joint]
  if not s:continue
  v=sorted(r['gap_cm'] for r in s)
  report['joints'][joint]={'count':len(s),'max_cm':v[-1],'mean_cm':statistics.mean(v),'p95_cm':v[int(.95*(len(v)-1))],'worst':max(s,key=lambda r:r['gap_cm'])}
 out[name]=report
(folder/'summary.json').write_text(json.dumps(out,indent=2))
for k,v in out.items():print(k,v['mode'],v['error'], {j:{key:d[key] for key in ['max_cm','mean_cm','p95_cm']} for j,d in v['joints'].items()})
