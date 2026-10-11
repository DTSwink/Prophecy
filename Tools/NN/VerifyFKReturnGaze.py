import ast,json,math,types,hashlib
from pathlib import Path
import torch
source=Path('C:/Users/singerie/Documents/Cursor/stepper/training/ik/train_upper_pose_autoencoder.py')
tree=ast.parse(source.read_text(encoding='utf-8'))
functions={'_rotate_vectors_about_axis','_descendants','_subtree_index_tensors','_rotate_pose_subtree','_correct_pose_subtree_frame','apply_gaze_overlay_global_pose'}
module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in functions],type_ignores=[])
context=dict(torch=torch,math=math,tl=types.SimpleNamespace(normalize=lambda x:x/torch.linalg.vector_norm(x,dim=-1,keepdim=True).clamp_min(1e-12)),GAZE_DIM=2,GAZE_CHAIN=['spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head'],GAZE_YAW_LIMIT_DEG=170.,GAZE_PITCH_LIMIT_DEG=85.,GAZE_BODY_PITCH_MULTIPLIER=1.,_SUBTREE_INDEX_CACHE={})
exec(compile(ast.fix_missing_locations(module),str(source),'exec'),context)
p=Path('Saved/Diagnostics/AttackFKGaze20261011');d=json.loads((p/'native.json').read_text(encoding='utf-8'));clip=types.SimpleNamespace(body_names=d['names'],parents_body_list=d['parents'])
def axes(q):
 x,y,z,w=q
 return [[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w)],[2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)],[2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)]]
def training_pose(rows):
 return (torch.tensor([[[r[4]/100,-r[5]/100,r[6]/100] for r in rows]],dtype=torch.float64),torch.tensor([[axes([-r[0],r[1],-r[2],r[3]]) for r in rows]],dtype=torch.float64))
pos,rot=training_pose(d['source']);position_error=axis_error=0
for r in d['cases']:
 a,b=context['apply_gaze_overlay_global_pose'](clip,pos,rot,torch.tensor([[r['yaw'],r['pitch']]],dtype=torch.float64))
 ap,bp=training_pose(r['pose']);position_error=max(position_error,float((a-ap).abs().max())*100);axis_error=max(axis_error,float((b-bp).abs().max()))
result=dict(cases=len(d['cases']),native_failures=d['failures'],checks=d['checks'],position_max_component_cm=position_error,axis_max_component=axis_error,source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
(p/'oracle.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
assert d['failures']==0 and position_error<1e-4 and axis_error<1e-6
