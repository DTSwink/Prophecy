import json,numpy as np,onnx
from onnx.reference import ReferenceEvaluator
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/Head24520261003')
def load(m):return {round(r['time']*60):r for r in map(json.loads,(p/(m+'-inputs.jsonl')).read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0'}
a=load('return_baseline');b=load('later_turn_stop');e=ReferenceEvaluator(onnx.load('Content/locomotion/NN/prophecy_upper_body_dynamic.onnx'))
def clean(x):
 y=x.reshape(10,6).copy();v=y[:,:3];v/=np.linalg.norm(v,axis=1)[:,None];w=y[:,3:];w-=v*np.sum(v*w,axis=1)[:,None];w/=np.linalg.norm(w,axis=1)[:,None];return y.reshape(60)
def rot(x):
 v=clean(np.tile(x,10))[:6];return R.from_matrix(np.array([v[:3],v[3:],np.cross(v[:3],v[3:])]).T)
out={}
for mode,sections in [('baseline',[]),('root_only',[(207,242)]),('pelvis_only',[(180,207)]),('feet_only',[(243,279)]),('lower_all',[(180,242),(243,279)])]:
 prev=cur=None;rr={}
 for t in range(232,281,2):
  x=np.array(a[t]['upper_input'],dtype=np.float32)
  if cur is not None:x[:60]=prev;x[90:150]=cur
  for lo,hi in sections:x[lo:hi]=b[t]['upper_input'][lo:hi]
  y=e.run(None,{e.input_names[0]:x[None]})[0][0];n=clean((x[90:150]+y[:60]).copy())
  q0=rot(x[132:138]);q1=rot(n[42:48]);speed=float(np.degrees((q1*q0.inv()).magnitude())/2)
  rr[t]=speed;prev=x[90:150].copy();cur=n
 out[mode]=rr
print('tick',*out)
for t in range(238,257,2):print(t,*[round(v[t],3) for v in out.values()])
(p/'causal-core-rollout.json').write_text(json.dumps(out,indent=2))
