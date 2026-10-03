import json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
audit=json.loads((p/'model-audit.json').read_text())
baseline={r['tick']:r for r in json.loads((p/'baseline.json').read_text())['rows']}
summary={}
for name,v in audit.items():
 data=json.loads((p/(name+'.json')).read_text());rows={r['tick']:r for r in data['rows']}
 window=[r for r in v['metrics'] if 218<=r['tick']<=250]
 prefix={'return_off':195,'later_turn_stop':210,'kinematic_late':210,'no_feedback':210,'no_lower_tempering':179}.get(name)
 pe=None
 if prefix is not None:
  pe=max(np.linalg.norm(np.array(r['bones'][b]['presented']['p'])-baseline[t]['bones'][b]['presented']['p']) for t,r in rows.items() if t<=prefix for b in r['bones'])
 summary[name]=dict(reason=data['reason'],samples=len(rows),owned=data['owned'],graph_sha256=hashlib.sha256((p/(name+'-graph.txt')).read_bytes()).hexdigest(),prefix_through=prefix,prefix_max_bone_position_difference_cm=pe,
  head_peak=max(window,key=lambda r:r['presented_head_local_deg']),position_peak=max(window,key=lambda r:r['presented_head_displacement_cm']),torch_max_error=v['torch_unreal_max_delta_error'],core_max_error_deg=max(r['core_error_deg'] for r in v['core_parity'] if 218<=r['tick']<=250),modes_after_211=sorted(set(r['simulation_mode'] for t,r in rows.items() if t>=212)))
viewer=[]
for name in sorted(z.stem for z in p.glob('viewer_*.npz')):
 z=np.load(p/(name+'.npz'));names=list(z['names']);h=names.index('head');n=names.index('neck_02')
 root=R.from_matrix(z['root_rotations'].transpose(0,2,1));rs=np.degrees((root[:-1].inv()*root[1:]).magnitude())*30
 stop=int(np.where(rs>10)[0][-1]+2);entry=dict(name=name,turn_end_frame=stop)
 for tag,arr in [('generated',z['rotations']),('authored',z['target_rotations'])]:
  local=R.from_matrix(arr[:,n].transpose(0,2,1)).inv()*R.from_matrix(arr[:,h].transpose(0,2,1))
  speed=np.degrees((local[:-1].inv()*local[1:]).magnitude())/2
  end=min(stop+8,len(arr)-1)
  entry[tag]=dict(peak_after_authored_seed_deg_per_60hz_tick=float(speed[2:].max()),peak_first_8_policy_steps_after_turn=float(speed[stop:stop+8].max()),head_net_turn_first_8_policy_steps_deg=float(np.degrees((local[stop].inv()*local[end]).magnitude())))
 viewer.append(entry)
out=dict(runtime=summary,viewer=viewer)
(p/'summary.json').write_text(json.dumps(out,indent=2))
for n,v in summary.items():print(n,'head',round(v['head_peak']['presented_head_local_deg'],4),'tick',v['head_peak']['tick'],'prefix',v['prefix_max_bone_position_difference_cm'])
for z in viewer:
 if 'gaze0' in z['name'] and '_sword_' in z['name']:print(z)
