"""Import only the new Imperial Spear assets; never replace the sword or maps."""
import os, json, pathlib, unreal

def main():
    root = pathlib.Path(unreal.Paths.project_dir())
    out = root / 'Saved/Diagnostics/SpearPike20261030'
    assert os.getpid() == int((out/'editor.pid').read_text().strip())
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not ed.get_game_world(), 'Preserve active Play'
    dest = '/Game/_mygame/spear'
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mesh_path = dest+'/SM_ImperialSpear'
    assert not unreal.EditorAssetLibrary.does_asset_exist(mesh_path), 'Already imported; inspect instead of replacing'
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Interchange.FeatureFlags.Import.FBX 0')
    task = unreal.AssetImportTask()
    task.filename = str(root/'Exports/ImperialSpear/SM_ImperialSpear.fbx')
    task.destination_path = dest
    task.destination_name = 'SM_ImperialSpear'
    task.automated = True
    task.save = False
    opts = unreal.FbxImportUI()
    opts.import_mesh = True
    opts.import_as_skeletal = False
    opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    opts.automated_import_should_detect_type = False
    opts.import_materials = False
    opts.import_textures = False
    data = opts.static_mesh_import_data
    data.combine_meshes = True
    data.convert_scene_unit = True
    data.remove_degenerates = False
    data.auto_generate_collision = False
    data.one_convex_hull_per_ucx = True
    data.generate_lightmap_u_vs = False
    data.vertex_color_import_option = unreal.VertexColorImportOption.REPLACE
    data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
    task.options = opts
    tools.import_asset_tasks([task])
    mesh = unreal.load_asset(mesh_path)
    assert isinstance(mesh, unreal.StaticMesh), task.imported_object_paths
    textures = {}
    for suffix in ('BaseColor', 'ORM', 'NormalDX'):
        t = unreal.AssetImportTask()
        t.filename = str(root/'Exports/ImperialSpear/Textures'/('T_ImperialSpear_'+suffix+'.png'))
        t.destination_path = dest+'/Textures'
        t.automated = True
        t.save = False
        tools.import_asset_tasks([t])
        tex = unreal.load_asset(t.imported_object_paths[0])
        tex.set_editor_property('srgb', suffix == 'BaseColor')
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP if suffix == 'NormalDX' else (unreal.TextureCompressionSettings.TC_MASKS if suffix == 'ORM' else unreal.TextureCompressionSettings.TC_DEFAULT))
        textures[suffix] = tex
    mat = tools.create_asset('M_ImperialSpear', dest, unreal.Material, unreal.MaterialFactoryNew())
    mel = unreal.MaterialEditingLibrary
    samples = {}
    for i, (suffix, tex) in enumerate(textures.items()):
        sample = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -650, i*260)
        sample.set_editor_property('parameter_name', suffix)
        sample.set_editor_property('texture', tex)
        sample.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if suffix == 'NormalDX' else (unreal.MaterialSamplerType.SAMPLERTYPE_MASKS if suffix == 'ORM' else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR))
        samples[suffix] = sample
    vertex = mel.create_material_expression(mat, unreal.MaterialExpressionVertexColor, -650, -200)
    multiply = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -250, 0)
    mel.connect_material_expressions(samples['BaseColor'], 'RGB', multiply, 'A')
    mel.connect_material_expressions(vertex, 'RGB', multiply, 'B')
    mel.connect_material_property(multiply, '', unreal.MaterialProperty.MP_BASE_COLOR)
    for channel, prop in [('R', 'MP_AMBIENT_OCCLUSION'), ('G', 'MP_ROUGHNESS'), ('B', 'MP_METALLIC'), ('A', 'MP_SPECULAR')]:
        mel.connect_material_property(samples['ORM'], channel, getattr(unreal.MaterialProperty, prop))
    mel.connect_material_property(samples['NormalDX'], 'RGB', unreal.MaterialProperty.MP_NORMAL)
    mel.recompile_material(mat)
    mesh.set_material(0, mat)
    bp = unreal.EditorAssetLibrary.duplicate_asset('/Game/_mygame/sword/A_Sword', dest+'/A_Spear')
    assert bp
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    seen = set()
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
        obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)
        if obj.get_path_name() in seen: continue
        seen.add(obj.get_path_name())
        if obj.get_name() == 'sword_GEN_VARIABLE':
            obj.set_editor_property('static_mesh', mesh)
            obj.set_editor_property('override_materials', [mat])
            obj.set_editor_property('relative_scale3d', unreal.Vector(0.8623427588789339,0.8834927125312151,0.7619161867885869))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = unreal.get_default_object(bp.generated_class())
    for key, value in [('debug mode',False), ('freeze tick',-1), ('unfreeze tick',0), ('enable gravity',True), ('Optimised',True)]:
        cdo.set_editor_property(key,value)
    cdo.set_editor_property('tags', [unreal.Name('Prophecy.Spear.PassThrough')])
    bounds = mesh.get_bounding_box()
    result = {'mesh':mesh.get_path_name(), 'bounds_min':str(bounds.min), 'bounds_max':str(bounds.max), 'assets':task.imported_object_paths}
    for asset in [mesh,mat,bp,*textures.values()]:
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    (out/'import.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

main()
