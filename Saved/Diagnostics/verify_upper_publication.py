import contextlib,io,json,numpy as np
with contextlib.redirect_stdout(io.StringIO()):
 exec(open('Saved/Diagnostics/analyze_run_thigh.py').read())
before=rows
data=json.loads((folder/'frame_fixed.json').read_text());after=data['rows']
assert not data['error'],data['error']
fixed_traces=[json.loads(s) for s in (folder/'frame_fixed_nn.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
fixed_traces=[t for t in fixed_traces if t['actor']==after[0]['actor']]
base_traces=[t for t in traces if t['actor']==before[0]['actor']]
def yaw(a):
 s,c=np.sin(a),np.cos(a)
 return np.array([[c,0,s],[0,1,0],[-s,0,c]])
errors=[];forearms=[]
for t in fixed_traces:
 r=min(after,key=lambda r:abs(r['time']-t['time']))
 u=np.array(t['upper_input'][90:180])+t['upper_delta']
 roots=t['roots'];delta=(np.array(roots[8:11])-roots[4:7])@yaw(roots[7]);turn=yaw(roots[11]-roots[7])
 for o in (60,75):
  u[o:o+3]=(u[o:o+3]-delta)@turn
  for k in (o+3,o+9):u[k:k+6]=(rot6(u[k:k+6])@turn)[:2].flatten()
 p,q=decode(t,u);worldq=Rotation.from_quat(r['future']['pelvis']['q']).as_matrix()
 def world(v):return (v-p[0])@q[0].T@mirror@worldq.T*100+np.array(r['future']['pelvis']['p'])
 for i,side in enumerate(('l','r')):
  h=names.index('hand_'+side);e=names.index('lowerarm_'+side)
  expected=world(p[e]+unit(p[h]-p[e])*c['arm_limb_lengths_m'][i][1])
  actual=np.array(r['future']['hand_'+side]['p'])
  errors.append(float(np.linalg.norm(expected-actual)))
  forearms.append(abs(float(np.linalg.norm(actual-r['future']['lowerarm_'+side]['p']))-c['arm_limb_lengths_m'][i][1]*100))
def clearance(rs,phase):
 return min((segdist(np.array(r[phase]['hand_l']['p']),np.array(r[phase]['thigh_l']['p']),np.array(r[phase]['calf_l']['p'])),r['tick']) for r in rs)
report=dict(frames=len(after),nn_frames=len(fixed_traces),attack_states=sorted(set(r['attack'] for r in after)),
 before=clearance(before,'future'),after=clearance(after,'future'),presented=clearance(after,'presented'),mesh=clearance(after,'mesh'),
 maximum_expected_pose_error_cm=max(errors),maximum_forearm_length_error_cm=max(forearms))
if len(base_traces)==len(fixed_traces):
 report['maximum_upper_input_difference']=max(float(np.max(np.abs(np.array(a['upper_input'])-b['upper_input']))) for a,b in zip(base_traces,fixed_traces))
 report['maximum_lower_output_difference']=max(float(np.max(np.abs(np.array(a['published_lower'])-b['published_lower']))) for a,b in zip(base_traces,fixed_traces))
assert all(np.isfinite(x) for x in errors)
assert max(errors)<.01,report
assert report['after'][0]>12,report
(folder/'frame_fixed_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
