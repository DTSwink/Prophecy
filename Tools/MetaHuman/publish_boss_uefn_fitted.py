"""Publish a separate corrected Boss; never replace the original/shared skeleton."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
BASE = '/Game/_mygame/MetaHumans/BossUEFN/'
DEST = BASE + 'SKM_Boss_UEFN_Fitted'
SOURCE = BASE + 'Validation_20260907/UEFNAxes/SKM_Boss_UEFN_Fitted'

existing = unreal.load_asset(DEST) if unreal.EditorAssetLibrary.does_asset_exist(DEST) else None
assert existing is None or existing.skeleton.get_path_name().startswith(BASE+'Validation_20260907/UEFNAxes/'), 'Refusing overwrite of a finished keeper'
if existing is not None:
    # Only our unpublished duplicate is removable; reimport retains its old
    # Skeleton association even when a different Skeleton is requested.
    assert unreal.EditorAssetLibrary.delete_asset(DEST)
    existing=None
assert json.loads((ROOT/'Saved/BossUEFNCompatible/20260907/verification.json').read_text())['passed']
shared_file = ROOT/'Content/_mygame/SK_UEFN_Mannequin.uasset'
original_file = ROOT/'Content/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN.uasset'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = {str(p):digest(p) for p in (shared_file,original_file)}
native = unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
original = unreal.load_asset(BASE+'SKM_Boss_UEFN')
# Both meshes have the same 88 names and parents (verified before publication).
# The mesh keeps its own fitted bind transforms; do not update the Skeleton's rest pose.
options=unreal.FbxImportUI()
options.set_editor_properties(dict(import_mesh=True,import_as_skeletal=True,import_animations=False,
    import_materials=False,import_textures=False,create_physics_asset=False,skeleton=native.skeleton,
    mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH))
options.skeletal_mesh_import_data.set_editor_properties(dict(import_morph_targets=False,
    update_skeleton_reference_pose=False,use_t0_as_ref_pose=False,
    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS))
task=unreal.AssetImportTask()
task.set_editor_properties(dict(filename=str(ROOT/'Saved/BossUEFNCompatible/20260907/SKM_Boss_UEFN_Fitted.fbx'),
    destination_path=BASE.rstrip('/'),destination_name='SKM_Boss_UEFN_Fitted',
    automated=True,save=False,replace_existing=existing is not None,replace_existing_settings=True,options=options))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=unreal.load_asset(DEST)
assert mesh and mesh.skeleton==native.skeleton, 'Imported asset must use the canonical Skeleton'
mesh.set_editor_property('materials',list(original.materials))
assert unreal.EditorAssetLibrary.save_loaded_asset(mesh)
assert before == {str(p):digest(p) for p in (shared_file,original_file)}
audit={}
exec(compile((ROOT/'Tools/MetaHuman/audit_boss_unreal_20260907.py').read_text(),'boss_audit','exec'),audit)
audit['capture'](DEST,'unreal_keeper')
old=json.loads((ROOT/'Saved/BossBindAudit/20260907/unreal_uefn_fitted.json').read_text())
new=json.loads((ROOT/'Saved/BossBindAudit/20260907/unreal_keeper.json').read_text())
assert old['bones']==new['bones'] and old['positions']==new['positions'] and old['weights']==new['weights']
assert new['skeleton']==native.skeleton.get_path_name()
result={'path':DEST,'skeleton':new['skeleton'],'original_unchanged':True,'shared_skeleton_unchanged':True,
        'geometry_unchanged_on_skeleton_assignment':True,'protected_hashes':before,
        'physics_asset':mesh.physics_asset.get_path_name() if mesh.physics_asset else None}
(ROOT/'Saved/BossUEFNCompatible/20260907/publication.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
