import json, math
from pathlib import Path
import unreal
out=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab/idle-unreal-audit.json')
def vec(v):return [v.x,v.y,v.z]
def axes(q):
 x,y,z,w=q.x,q.y,q.z,q.w
 return [[1-2*(y*y+z*z),2*(x*y+w*z),2*(x*z-w*y)],[2*(x*y-w*z),1-2*(x*x+z*z),2*(y*z+w*x)],[2*(x*z+w*y),2*(y*z-w*x),1-2*(x*x+y*y)]]
names=json.loads((out.parent/'data/manifest.json').read_text())['names']
report={}
for asset in ['/Game/_mygame/M_Neutral_Stand_Idle_Loop','/Game/_mygame/_bossM_Neutral_Stand_Idle_Loop']:
 clip=unreal.load_asset(asset)
 if not clip:continue
 rows={}
 for retarget in [False,True]:
  opts=unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=retarget)
  pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(clip,0.,opts)
  bones={}
  for name in names:
   bones[name]={}
   for label,space in [('local',unreal.AnimPoseSpaces.LOCAL),('world',unreal.AnimPoseSpaces.WORLD)]:
    t=unreal.AnimPoseExtensions.get_bone_pose(pose,name,space)
    bones[name][label]={'p':vec(t.translation),'axes':axes(t.rotation)}
  rows[str(retarget)]=bones
 report[asset]={'skeleton':clip.get_editor_property('skeleton').get_path_name(),'poses':rows}
out.write_text(json.dumps(report,indent=2))
print('IDLE AUDIT WRITTEN '+str(out))
