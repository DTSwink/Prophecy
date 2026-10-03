import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics');rows=json.loads((p/'KneeHistorical8-capture.json').read_text())['rows'];metrics=json.loads((p/'KneeHistorical8-metrics.json').read_text())
for t in range(438,452):
 r=next(r for r in rows if r['clock']==t)
 print(t,'alpha',r['targets']['foot_r']['alpha'],'pin',r['pin'])
 for kind in ('target','future'):
  m=next(x for x in metrics if x['tick']==t and x['side']=='r' and x['kind']==kind)
  pts=[np.array(r['targets'][b+'_r'][kind]['p']) for b in ('thigh','calf','foot')];h,k,f=pts
  print(kind, {key:round(m[key],3) for key in ('radius','bend','poleturn','thighturn','kneestep','footstep')},'lengths',*[round(np.linalg.norm(x),4) for x in (k-h,f-k,f-h)],'foot',f.round(2))
