import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent)
out=[]
for a in actors:
 mesh=a.get_pose_reference_mesh()
 asset=mesh.get_editor_property('physics_asset_override') or mesh.get_editor_property('skeletal_mesh_asset').get_editor_property('physics_asset')
 for obj in asset.get_editor_property('constraint_setup'):
  inst=str(obj.get_editor_property('default_instance'))
  if any(b in inst for b in ['hand_r','lowerarm_r']):out.append(dict(actor=a.get_name(),asset=asset.get_path_name(),constraint=inst))
 break
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/Knee202/right_hand128_constraints.json').write_text(json.dumps(out,indent=2))
print('RIGHT_ARM_CONSTRAINTS',len(out))
