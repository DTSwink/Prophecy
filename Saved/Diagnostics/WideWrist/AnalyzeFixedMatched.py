import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
mode=__import__('sys').argv[1] if len(__import__('sys').argv)>1 else 'true'
def read(m):
    d=json.loads((p/f'bool_{m}.json').read_text());assert d['reason']=='Complete';return [r for r in d['rows'] if r['actor'].endswith('_C_1')]
a,b=read('false_beforefix'),read(mode)
def angle(q1,q2):return float(np.degrees((R.from_quat(q1).inv()*R.from_quat(q2)).magnitude()))
by_t={round(r['t'],5):r for r in a}
pairs=[(by_t[round(r['t'],5)],r) for r in b if round(r['t'],5) in by_t]
result={'pairs':len(pairs),'bones':{},'limits_changes':[]}
prev=None
for r in b:
    if r['limits']!=prev:result['limits_changes'].append({'t':r['t'],'limits':r['limits']});prev=r['limits']
for bone in ['upperarm_r','lowerarm_r','hand_r','upperarm_l','lowerarm_l','hand_l']:
    rs=[]
    for x,y in pairs:
        if bone not in x['bones'] or bone not in y['bones']:continue
        aa,bb=x['bones'][bone],y['bones'][bone]
        rs.append({'t':x['t'],'physical_diff':angle(aa['q'],bb['q']),'target_diff':angle(aa['target'],bb['target']),
          'false_err':angle(aa['q'],aa['target']),'true_err':angle(bb['q'],bb['target']),
          'pos_diff':float(np.linalg.norm(np.array(aa['p'])-bb['p']))})
    result['bones'][bone]={'before_max':max(r['physical_diff'] for r in rs if r['t']<10),'max_physical_diff':max(r['physical_diff'] for r in rs),
      'false_max_err':max(r['false_err'] for r in rs if r['t']>=10),'true_max_err':max(r['true_err'] for r in rs if r['t']>=10),
      'first_001':next((r for r in rs if r['physical_diff']>0.01),None),
      'first_1':next((r for r in rs if r['physical_diff']>1),None),
      'near_switch':[r for r in rs if 9.97<r['t']<10.2]}
(p/f'bool_{mode}_analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
