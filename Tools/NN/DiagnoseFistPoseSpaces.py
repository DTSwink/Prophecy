"""Compare actual animation-editor local transforms to extraction and keeper bind."""
import json
import math
import unreal

clip=unreal.load_asset('/Game/_mygame/closed_fist')
preview=next(o for o in unreal.ObjectIterator(unreal.DebugSkelMeshComponent)
             if 'AnimationEditorPreviewActor' in o.get_path_name() and o.get_anim_instance()
             and o.get_anim_instance().get_animation_asset()==clip)
keeper=unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted')
src=unreal.SkeletonModifier(); src.set_skeletal_mesh(preview.get_skeletal_mesh_asset())
dst=unreal.SkeletonModifier(); dst.set_skeletal_mesh(keeper)
ext=unreal.AnimPoseExtensions
raw=ext.get_anim_pose_at_time(clip,0,unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=False))
retarget=ext.get_anim_pose_at_time(clip,0,unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=True))

def angle(a,b):
    a=a.normalized(); b=b.normalized()
    return math.degrees(2*math.acos(min(1,abs(a.x*b.x+a.y*b.y+a.z*b.z+a.w*b.w))))

rows=[]
for name in src.get_all_bone_names():
    n=str(name)
    if not (n.startswith(('index_','thumb_','middle_','ring_','pinky_')) or n in ('hand_l','hand_r')): continue
    a=src.get_bone_transform(n,False); b=dst.get_bone_transform(n,False)
    parent=preview.get_socket_transform(str(src.get_parent_name(n)),unreal.RelativeTransformSpace.RTS_COMPONENT)
    child=preview.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_COMPONENT)
    q=parent.rotation.inversed()*child.rotation
    p=parent.inverse_transform_location(child.translation)
    r=ext.get_bone_pose(raw,n,unreal.AnimPoseSpaces.LOCAL)
    t=ext.get_bone_pose(retarget,n,unreal.AnimPoseSpaces.LOCAL)
    rows.append({'bone':n,'bind_angle':angle(a.rotation,b.rotation),'bind_cm':(a.translation-b.translation).length(),
                 'preview_vs_raw_angle':angle(q,r.rotation),'preview_vs_raw_cm':(p-r.translation).length(),
                 'preview_vs_retarget_angle':angle(q,t.rotation),'preview_vs_retarget_cm':(p-t.translation).length()})
print(json.dumps({'preview_mesh':preview.get_skeletal_mesh_asset().get_path_name(),
                  'keeper_skeleton':keeper.get_editor_property('skeleton').get_path_name(), 'rows':rows}))
