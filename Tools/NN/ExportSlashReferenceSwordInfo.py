"""Editor readback only: existing sword geometry and skeleton rest offsets."""
import json
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
sword=unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01')
reference=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
               if a.get_actor_label()=='SlashChain30_Reference_Looping')
mesh=reference.get_component_by_class(unreal.SkeletalMeshComponent)
description=sword.get_static_mesh_description(0)
vertices=[]
for index in range(description.get_vertex_count()):
    p=description.get_vertex_position(unreal.VertexID(index))
    vertices.append([p.x,p.y,p.z])
rest={}
for name in ('hand_l','hand_r'):
    p=mesh.get_ref_pose_position(mesh.get_bone_index(name))
    rest[name]=[p.x,p.y,p.z]
info={'sword_mesh':sword.get_path_name(),'vertices_cm':vertices,'hand_rest_local_cm':rest}
(root/'Saved/SlashChain/sword_mesh_info.json').write_text(json.dumps(info))
print({'vertices':len(vertices),'rest_offsets':rest})
