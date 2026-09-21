import unreal,json,pathlib
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RuntimeBoneMaterials'
root.mkdir(parents=True,exist_ok=True)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
result={'map':world.get_path_name(),
    'pie':bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()),
    'nodes':{n:hasattr(unreal.ProphecyAgent,n) for n in ('set_jolt_bodies_physical_material_override','reset_jolt_bodies_physical_material_override')},
    'dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    'dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(root/'reflection.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
assert all(result['nodes'].values())
assert not result['pie']
