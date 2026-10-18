import unreal,json,pathlib
root=pathlib.Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');out=root/'Saved/Diagnostics/BombFuseFlexible'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,'Preserve user Play'
folder='/Game/_mygame/BombGenerated';name='SK_BombFuse'
opt=unreal.FbxImportUI();opt.set_editor_properties(dict(import_mesh=True,import_as_skeletal=True,import_animations=False,import_materials=False,import_textures=False,create_physics_asset=False,automated_import_should_detect_type=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH))
imp=opt.skeletal_mesh_import_data;imp.set_editor_property('convert_scene_unit',True);imp.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
old=unreal.load_asset(folder+'/'+name)
if old:opt.set_editor_property('skeleton',old.skeleton)
task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=str(out/(name+'.fbx')),destination_path=folder,destination_name=name,automated=True,save=False,replace_existing=bool(old),options=opt,factory=unreal.FbxFactory()))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
sk=unreal.load_asset(folder+'/'+name);assert sk
slots=list(sk.materials);assert len(slots)==2
slots[0].material_interface=unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/Materials/Bomb')
slots[1].material_interface=unreal.load_asset(folder+'/MI_BombBurn');sk.set_editor_property('materials',slots)
assert sk.get_editor_property('physics_asset') is None
modifier=unreal.SkeletonModifier();assert modifier.set_skeletal_mesh(sk)
report={'bones':{str(n):str(modifier.get_bone_transform(n,False)) for n in modifier.get_all_bone_names()},'bounds':str(sk.get_bounds())}
for p in task.imported_object_paths:assert unreal.EditorAssetLibrary.save_loaded_asset(unreal.load_asset(p))
assert unreal.EditorAssetLibrary.save_loaded_asset(sk.skeleton)
(out/'import.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
