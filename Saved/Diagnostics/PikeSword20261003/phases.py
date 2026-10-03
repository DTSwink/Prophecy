import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent;root=p.parents[2]
meta=json.loads((root/'Content/locomotion/NN/prophecy_slash_runtime.json').read_text());names=meta['bone_names'];hi=names.index('hand_r');ei=names.index('lowerarm_r');pi=names.index('pelvis')
b=json.loads((p/'baseline.json').read_text());grip=b['metadata']['sword_grip'];tip=np.array([0,0,json.loads((p/'geometry.json').read_text())['max'][2]]);tip_hand=R.from_quat(grip['q']).apply(tip*grip['s'])+grip['p'];mirror=np.diag([1,-1,1])
def metric(pos,target):
 direction=target-pos[0];direction/=np.linalg.norm(direction);delta=pos-pos[0];along=delta@direction;side=delta-along[:,None]*direction
 vel=np.diff(pos,axis=0);cross=vel-(vel@direction)[:,None]*direction
 return dict(lateral_max_cm=float(np.linalg.norm(side,axis=1).max()),lateral_travel_cm=float(np.linalg.norm(cross,axis=1).sum()),path_cm=float(np.linalg.norm(vel,axis=1).sum()),end_error_cm=float(np.linalg.norm(pos[-1]-target)),velocity_change_max=float(np.linalg.norm(np.diff(vel,axis=0),axis=1).max()) if len(vel)>1 else 0)
def summarize(outputs,inputs,apply_fixed=False):
 out=np.array(outputs);pos=out[:,131:206].reshape(-1,25,3);rot=out[:,206:431].reshape(-1,25,3,3)
 hand=pos[:,hi].copy()
 if apply_fixed:
  d=hand-pos[:,ei];hand=pos[:,ei]+d/np.linalg.norm(d,axis=1)[:,None]*.22349242866
 pts=hand+np.einsum('i,nij->nj',tip_hand@mirror/100,rot[:,hi])
 target=np.array(inputs)[:,262:265];armed=np.where(out[:,431]>.5)[0];hit=np.where(out[:,432]>.5)[0]
 ar=int(armed[0]) if len(armed) else 0;ht=int(hit[0]) if len(hit) else len(out)-1
 return dict(frames=len(out),armed_index=ar,hit_index=ht,full=metric(pts*100,target[0]*100),strike=metric(pts[ar:ht+1]*100,target[ar]*100),opening=metric(pts[:ar+1]*100,target[0]*100),pelvis_target_distance_cm=float(np.linalg.norm(target[0]-pos[0,pi])*100),start_blade_to_target_angle_deg=float(np.degrees(np.arccos(np.clip(np.dot((pts[0]-hand[0])/np.linalg.norm(pts[0]-hand[0]),(target[0]-hand[0])/np.linalg.norm(target[0]-hand[0])),-1,1)))))
reports={}
for file in p.glob('*-nn.jsonl'):
 name=file.name.removesuffix('-nn.jsonl');tr=[r for r in map(json.loads,file.read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0'];gs=[]
 for r in tr:
  if not gs or r['frame']<=gs[-1][-1]['frame']:gs.append([])
  gs[-1].append(r)
 entries=[]
 for g in gs:
  entry=summarize([r['output'] for r in g],[r['input'] for r in g]);entry['fixed_wrist']=summarize([r['output'] for r in g],[r['input'] for r in g],True);entries.append(entry)
 reports[name]=entries
ref=json.loads((root/'Saved/SlashTrain2223/chain_audit.json').read_text());entries=[]
for seg in ref['segments']:
 if seg['family'].lower()!='pike':continue
 lo=seg['startFrame']-2;hi2=seg['finalFrame']-1
 entries.append(summarize(ref['expected'][lo:hi2],ref['inputs'][lo:hi2]));entries[-1]['fixed_wrist']=summarize(ref['expected'][lo:hi2],ref['inputs'][lo:hi2],True)
reports['slash_train']=entries
(p/'phases.json').write_text(json.dumps(reports,indent=2))
for k,v in reports.items():
 for i,z in enumerate(v):
  if k in ('baseline','slash_train') or i==1:print(k,i+1,'distance',round(z['pelvis_target_distance_cm'],1),'initial blade angle',round(z['start_blade_to_target_angle_deg'],1),'strike',z['strike'],'fixed lateral',round(z['fixed_wrist']['strike']['lateral_max_cm'],2))
