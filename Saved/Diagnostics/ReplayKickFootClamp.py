import numpy as np,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); cfg=json.loads(pathlib.Path('Content/locomotion/NN/prophecy_slash_native.json').read_text())
rows=[json.loads(l) for l in (p/'metrics.jsonl').read_text().splitlines()]
steps=[json.loads(l) for l in (p/'slash.jsonl').read_text().splitlines()]
def rot(q,v):
 q=np.array(q);v=np.array(v);return v+2*np.cross(q[:3],np.cross(q[:3],v)+q[3]*v)
def wp(s,b):
 i=cfg['bone_names'].index(b)
 local=(np.array(s['output'][131+3*i:134+3*i])-cfg['root_position'])@np.array(cfg['root_rotation']).T
 return rot(s['anchor'][3:],local*np.array([100,-100,100]))+s['anchor'][:3]
out=[]
for s in steps:
 for side in ['l','r']:
  r=next((r for r in rows if r['agent']==s['actor'] and r['side']==side and abs(r['time']-s['time'])<1e-6),None)
  if not r:continue
  ref=np.array([-42.561031,.107739,.42919]) if side=='l' else np.array([42.561165,-.107729,-.429205])
  pose=r['poses']['future'];knee=np.array(pose['points'][1]); foot=np.array(pose['points'][2])
  raw=wp(s,'foot_'+side);nominal=rot(pose['rotations'][1],ref);axis=nominal/np.linalg.norm(nominal)
  origin=knee+nominal;extension=float(np.dot(raw-origin,axis));end=origin+axis*np.clip(extension,0,5)
  out.append({'t':s['time'],'side':side,'frame':r['frame'],'phase':r['attack'],'raw_foot_z':float(raw[2]),'final_foot_z':float(foot[2]),'shift_z':float(foot[2]-raw[2]),'requested_extension':extension,'clamp_replay_error':float(np.linalg.norm(foot-end)),'knee_error':float(np.linalg.norm(knee-wp(s,'calf_'+side)))})
for side in ['l','r']:
 v=[x for x in out if x['side']==side]; worst=min(v,key=lambda x:x['shift_z']); print(side,'worst downshift',worst,'max_replay_error',max(x['clamp_replay_error'] for x in v))
(p/'clamp-replay.json').write_text(json.dumps(out,indent=2))
