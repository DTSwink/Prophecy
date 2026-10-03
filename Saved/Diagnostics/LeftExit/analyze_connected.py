import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
folder=Path('Saved/Diagnostics/RunHandThigh')
result={}
for tag in ['left_exit_base','left_exit_final_blend','left_exit_kin_trace','left_exit_connected_kin','left_exit_connected_sim']:
 p=folder/(tag+'.json')
 if not p.exists():continue
 doc=json.loads(p.read_text());assert not doc['error'],doc['error'];rows={r['tick']:r for r in doc['rows']}
 bends=[]
 for t in range(175,220,2):
  p=rows[t]['future'];u=np.array(p['lowerarm_l']['p'])-p['upperarm_l']['p'];v=np.array(p['hand_l']['p'])-p['lowerarm_l']['p'];bend=float(np.degrees(np.arccos(np.clip(u@v/(np.linalg.norm(u)*np.linalg.norm(v)),-1,1))))
  bends.append({'tick':t,'bend_deg':bend})
 out={'bends':bends,'first_bend_change_deg':bends[4]['bend_deg']-bends[3]['bend_deg']}
 out['max_bend_change_exit_183_213_deg']=max(abs(b['bend_deg']-a['bend_deg']) for a,b in zip(bends,bends[1:]) if 183<=b['tick']<=213)
 out['forearm_lengths_cm']={side:[min(v),max(v)] for side in ['l','r'] for v in [[float(np.linalg.norm(np.array(r['future']['hand_'+side]['p'])-r['future']['lowerarm_'+side]['p'])) for t,r in rows.items() if 183<=t<=215]]}
 result[tag]=out
 print(tag,[(b['tick'],round(b['bend_deg'],2)) for b in bends[:11]],'max step',out['max_bend_change_exit_183_213_deg'])
Path('Saved/Diagnostics/LeftExit/connected_verification.json').write_text(json.dumps(result,indent=2))
