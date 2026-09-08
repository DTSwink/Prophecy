"""Import only fresh isolated validation assets; no production replacements."""
import unreal
from pathlib import Path

ROOT = Path(unreal.Paths.project_dir()).resolve()
DEST = '/Game/_mygame/MetaHumans/BossUEFN/Validation_20260907'

def import_candidate(fbx, name, source_materials):
    path = DEST + '/' + name
    assert not unreal.EditorAssetLibrary.does_asset_exist(path), 'Refusing overwrite: ' + path
    options = unreal.FbxImportUI()
    options.set_editor_properties(dict(import_mesh=True, import_as_skeletal=True,
        import_animations=False, import_materials=False, import_textures=False,
        create_physics_asset=False, mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH))
    data = options.skeletal_mesh_import_data
    data.set_editor_properties(dict(import_morph_targets=False, update_skeleton_reference_pose=False,
        use_t0_as_ref_pose=False,
        normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS))
    task = unreal.AssetImportTask()
    task.set_editor_properties(dict(filename=str(fbx), destination_path=DEST, destination_name=name,
        automated=True, save=True, replace_existing=False, options=options))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(path)
    assert isinstance(mesh, unreal.SkeletalMesh), list(task.imported_object_paths)
    assert mesh.skeleton.get_path_name().startswith(DEST), 'Must use isolated skeleton'
    mesh.set_editor_property('materials', source_materials)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    print('IMPORTED', path, list(task.imported_object_paths))
    return mesh

if __name__ == '__main__':
    old = unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN')
    import_candidate(ROOT / 'Saved/BlenderExchange/BossUEFN/SKM_Boss_UEFN.fbx',
                     'SKM_Boss_NativeExport_Test', list(old.materials))
