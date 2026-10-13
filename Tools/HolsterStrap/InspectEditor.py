import unreal,json,pathlib
r=pathlib.Path(unreal.Paths.project_dir());out=r/'Saved/Diagnostics/HolsterStrap20261013';out.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);lib=unreal.SubobjectDataBlueprintFunctionLibrary
rows=[]
for h in sub.k2_gather_subobject_data_for_blueprint(bp):
    c=lib.get_object_for_blueprint(lib.get_data(h),bp)
    if isinstance(c,unreal.StaticMeshComponent) and 'holster' in c.get_name().lower():
        rows.append({'name':c.get_name(),'mesh':c.static_mesh.get_path_name() if c.static_mesh else None,'relative':str(c.get_relative_transform()),'collision':str(c.get_collision_enabled())})
result={'playing':bool(ed.get_game_world()),'holsters':rows,'dirty':[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]}
(out/'editor-before.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
print('ADD_SUBOBJECT',unreal.AddNewSubobjectParams.__doc__)
print('ADD',sub.add_new_subobject.__doc__)
