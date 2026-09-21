import json,pathlib,runpy,numpy as np
root=pathlib.Path(__file__).parent
h=runpy.run_path(str(root/'CompareRecoveryLegs.py'))
ap,a,am=h['load']('PelvisHitch-20260920-202148')
bp,b,bm=h['load']('PelvisHitch-20260920-203359')
result={}
for key in ('lower_input','lower_delta','published_lower'):
    result[key+'_max_difference']=max(float(np.max(abs(np.array(a[t][key])-b[t][key]))) for t in a if t in b)
result['pelvis_target_max_cm']=max(float(np.linalg.norm(np.array(am[t]['bones']['pelvis']['target']['p'])-bm[t]['bones']['pelvis']['target']['p'])) for t in am if t in bm)
result['frames']=len(bm)
(bp/'final_capture_verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
