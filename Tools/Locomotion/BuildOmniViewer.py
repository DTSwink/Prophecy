"""Validate captures and write compact viewer data; no smoothing or cycle fitting."""
from pathlib import Path
import json,math,hashlib
ROOT=Path(__file__).resolve().parents[2];src=ROOT/'Saved/Diagnostics/OmniRecord20261015'
base=json.loads((ROOT/'Labs/SwordHolsterLab/data/motions.json').read_text());clips=[];reports=[]
cuts=json.loads((src/'loop-cuts.json').read_text()) if (src/'loop-cuts.json').exists() else {}
# User removed these lateral duplicates from the gallery; retain raw captures.
excluded={f'M_Neutral_{gait}_Loop_{direction}' for gait in ('Run','Walk') for direction in ('LL','RR')}
for f in sorted(src.glob('M_Neutral*.json')):
 if f.stem in excluded:continue
 d=json.loads(f.read_text());rows=d['rows'];assert len(rows)==181
 assert [r['elapsed'] for r in rows]==list(range(120,301))
 assert all(b['tick']==a['tick']+1 for a,b in zip(rows,rows[1:]))
 if 'engine_frame' in rows[0]:assert all(b['engine_frame']==a['engine_frame']+1 for a,b in zip(rows,rows[1:]))
 assert d['names']==base['names']
 assert not any(not math.isfinite(v) for r in rows for b in r['pose'] for v in b)
 speed=[math.sqrt(sum(v*v for v in r['velocity_cm_s'])) for r in rows]
 expected=min(d['requested_speed'],d['unscaled_target_speed'])
 assert max(abs(x-expected) for x in speed)<1.5
 assert all(abs(r['weights'][1]-float(d['run']))<1e-5 for r in rows)
 gait='run' if d['run'] else 'walk';label=f.stem.replace('M_Neutral_','').replace('_Loop_',' · ').replace('_',' ')
 clips.append({'id':f.stem,'label':label,'gait':gait,'speed':sum(speed)/len(speed),'sourceSpeed':d['requested_speed'],'capSpeed':d['unscaled_target_speed'],'frames':[[[round(v,6) for v in b] for b in r['pose']] for r in rows]})
 reports.append({'clip':f.stem,'samples':181,'source_speed_cm_s':d['requested_speed'],'native_target_speed_cm_s':expected,'max_speed_error_cm_s':max(abs(x-expected) for x in speed),'raw_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'contracts':d['contracts']})
provenance={}
for c in clips:
 if c['id'] in cuts:c['cut']=cuts[c['id']]
if reports:
 for key,path in reports[0]['contracts'].items():
  if key.endswith('contract_path'):
   contract=json.loads((ROOT/path).read_text());provenance[key]={k:contract.get(k) for k in ['checkpoint_path','checkpoint_sha256','onnx_sha256']}
result={'provenance':provenance,'names':base['names'],'parents':base['parents'],'clips':clips,'fps':60,'seconds':3}
(ROOT/'Labs/OmniLocomotionViewer/data.json').write_text(json.dumps(result,separators=(',',':')))
(src/'validation.json').write_text(json.dumps(reports,indent=2));print('Validated',len(clips),'recordings')
