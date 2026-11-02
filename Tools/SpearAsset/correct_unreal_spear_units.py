import os,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Interchange.FeatureFlags.Import.FBX 0')
m=unreal.load_asset('/Game/_mygame/spear/SM_ImperialSpear')
stored=m.get_editor_property('asset_import_data')
stored.set_editor_property('convert_scene_unit',True)
stored.set_editor_property('remove_degenerates',False)
stored.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
t=unreal.AssetImportTask();t.filename=str(out.parents[2]/'Exports/ImperialSpear/SM_ImperialSpear.fbx')
t.destination_path='/Game/_mygame/spear';t.destination_name='SM_ImperialSpear';t.automated=True;t.replace_existing=True;t.save=True
o=unreal.FbxImportUI();o.import_mesh=True;o.import_as_skeletal=False;o.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH;o.automated_import_should_detect_type=False;o.import_materials=False;o.import_textures=False
d=o.static_mesh_import_data;d.combine_meshes=True;d.convert_scene_unit=True;d.remove_degenerates=False;d.auto_generate_collision=False;d.one_convex_hull_per_ucx=True;d.generate_lightmap_u_vs=False;d.vertex_color_import_option=unreal.VertexColorImportOption.REPLACE;d.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS;t.options=o
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
m=unreal.load_asset('/Game/_mygame/spear/SM_ImperialSpear');b=m.get_bounding_box();print('BOUNDS',b.min,b.max)
assert 200 < b.max.z-b.min.z < 250,'Expected centimetres after FBX metre conversion'
m.set_material(0,unreal.load_asset('/Game/_mygame/spear/M_ImperialSpear'))
unreal.EditorAssetLibrary.save_loaded_asset(m,only_if_is_dirty=False)
