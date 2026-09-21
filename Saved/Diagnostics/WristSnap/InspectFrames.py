import unreal, pathlib
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=sub.get_game_world() or sub.get_editor_world()
a=list(unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent))[-1]
mesh=a.get_pose_reference_mesh()
asset=mesh.get_editor_property('physics_asset_override') or mesh.get_editor_property('skeletal_mesh_asset').get_editor_property('physics_asset')
items=asset.get_editor_property('constraint_setup')
rows=[]
for obj in items:
    inst=obj.get_editor_property('default_instance')
    if 'hand_l' in str(inst): rows.append(str(inst))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WristSnap/frames.txt').write_text('\n'.join(rows))
print('WRIST_FRAMES',len(rows))
