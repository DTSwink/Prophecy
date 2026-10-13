import unreal,json,pathlib,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Existing Play left untouched'
folder='/Game/_mygame/assets/holster/Animated'
material=unreal.load_asset('/Game/Fab/Sword_in_scabbard/sword_in_scabbard/Materials/SwordMat1')
assert material
tasks=[]
for name,skel in [('HolsterRigid',False),('HolsterStrap',True)]:
    replace='--replace-generated' in sys.argv
    assert replace or not unreal.EditorAssetLibrary.does_asset_exist(folder+'/'+name),'Refuse to replace existing asset'
    opt=unreal.FbxImportUI();opt.set_editor_properties(dict(import_mesh=True,import_as_skeletal=skel,import_animations=False,import_materials=False,import_textures=False,create_physics_asset=False,automated_import_should_detect_type=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH if skel else unreal.FBXImportType.FBXIT_STATIC_MESH))
    imp=opt.skeletal_mesh_import_data if skel else opt.static_mesh_import_data
    imp.set_editor_property('convert_scene_unit',True)
    imp.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    if not skel:imp.set_editor_property('auto_generate_collision',False)
    if skel and replace:
        old=unreal.load_asset(folder+'/'+name)
        if old:opt.set_editor_property('skeleton',old.skeleton)
    task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=f'C:/Users/singerie/Downloads/HolsterStrap/{name}.fbx',destination_path=folder,destination_name=name,automated=True,save=False,replace_existing=replace,options=opt,factory=unreal.FbxFactory()))
    tasks.append(task)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
result=[]
for task in tasks:
    paths=list(task.imported_object_paths)
    for p in paths:
        obj=unreal.load_asset(p)
        if isinstance(obj,(unreal.StaticMesh,unreal.SkeletalMesh)):
            if isinstance(obj,unreal.SkeletalMesh):
                slots=list(obj.materials);slots[0].material_interface=material;obj.set_editor_property('materials',slots)
                assert not obj.get_editor_property('physics_asset')
                modifier=unreal.SkeletonModifier();assert modifier.set_skeletal_mesh(obj)
                bones=[str(x) for x in modifier.get_all_bone_names()]
                assert all(f'strap_{i:02d}' in bones for i in range(1,6)),bones
                result.append({'path':p,'bones':bones})
            else:obj.set_material(0,material);result.append({'path':p,'bounds':str(obj.get_bounds())})
        assert unreal.EditorAssetLibrary.save_loaded_asset(obj,only_if_is_dirty=True)
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/HolsterStrap20261013'
(out/'import.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
