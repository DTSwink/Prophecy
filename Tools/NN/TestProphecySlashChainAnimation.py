"""Evaluate all 455 imported native frames in Unreal; no scene modifications."""
import json
import math
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
data=json.loads((root/'Saved/SlashChain/animation_tracks.json').read_text())
sequence=unreal.load_asset('/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference')
mesh=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin')
options=unreal.AnimPoseEvaluationOptions()
options.set_editor_property('optional_skeletal_mesh',mesh)
options.set_editor_property('should_retarget',False)
errors=[]
for frame in range(455):
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(sequence,frame/30,options)
    for b,name in enumerate(data['bone_names']):
        got=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD)
        v=got.translation; p=data['world_positions_cm'][frame][b]
        q=got.rotation; r=data['world_quaternions'][frame][b]
        dot=abs(q.x*r[0]+q.y*r[1]+q.z*r[2]+q.w*r[3])/math.sqrt((q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)*sum(v*v for v in r))
        errors.append({'frame':frame,'bone':name,'position_mm':math.sqrt(sum((a-c)**2 for a,c in zip((v.x,v.y,v.z),p)))*10,
                       'angle_degrees':math.degrees(2*math.acos(min(1.,dot)))})
worst=max(errors,key=lambda r:r['position_mm'])
report={'max_position_mm':worst['position_mm'],'max_angle_degrees':max(e['angle_degrees'] for e in errors),'worst':worst,
        'frames':455,'bones':25,'passed':worst['position_mm']<0.1}
(root/'Saved/SlashChain/animation_import_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
