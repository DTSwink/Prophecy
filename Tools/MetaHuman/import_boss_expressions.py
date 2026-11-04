"""Reimport the Boss keeper with the 14 baked expression morph targets.

Run inside the live editor (remote Python):
  & 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Tools/MetaHuman/import_boss_expressions.py

Mirrors import_boss_stitched_collar.py: backs up the current uasset, keeps materials, PHAT and the
shared Skeleton, audits the mesh reference rig + vertices before/after, and does NOT save the asset.
Save it yourself after looking at the morphs (Skeletal Mesh editor > Morph Target Preview).
Source FBX was built in the cloud from Saved/BossUEFNCompatible/20260908_Stitched/SKM_Boss_UEFN_Fitted.fbx;
only shape keys were added (see roundtrip_verification.json next to the FBX).
"""
import hashlib, json, shutil
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
out = root / 'Saved/BossUEFNCompatible/20261104_Expressions'
fbx = out / 'SKM_Boss_UEFN_Fitted_Expressions.fbx'
dest = '/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted'
EXPECTED = ['Blink_L', 'Blink_R', 'JawOpen', 'Effort', 'Pain', 'Shout', 'Anger', 'Fear', 'Grin', 'Dead',
            'LookLeft', 'LookRight', 'LookUp', 'LookDown']

game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert game is None, 'Play session active: stop Play first (golden rule 6)'
assert fbx.exists(), fbx
mesh = unreal.load_asset(dest)
materials = list(mesh.materials); physics = mesh.physics_asset; skeleton = mesh.skeleton
backup = out / 'Backup/SKM_Boss_UEFN_Fitted.uasset'
assert not backup.exists(), 'Backup already exists: do not overwrite'
backup.parent.mkdir(parents=True, exist_ok=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
shutil.copy2(root / 'Content/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted.uasset', backup)
protected = [root / 'Content/_mygame/SK_UEFN_Mannequin.uasset',
             root / 'Content/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN.uasset']
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before_hashes = {str(p): digest(p) for p in protected}

audit = {}
exec(compile((root / 'Tools/MetaHuman/audit_boss_unreal_20260907.py').read_text(), 'audit_bind', 'exec'), audit)
audit['OUT'] = out
audit['capture'](dest, 'bind_before')

options = unreal.FbxImportUI()
options.set_editor_properties(dict(import_mesh=True, import_as_skeletal=True, import_animations=False,
    import_materials=False, import_textures=False, create_physics_asset=False, skeleton=skeleton,
    mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH))
options.skeletal_mesh_import_data.set_editor_properties(dict(import_morph_targets=True,
    update_skeleton_reference_pose=False, use_t0_as_ref_pose=False,
    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS))
task = unreal.AssetImportTask()
task.set_editor_properties(dict(filename=str(fbx), destination_path=dest.rsplit('/', 1)[0],
    destination_name=dest.rsplit('/', 1)[1], automated=True, save=False, replace_existing=True,
    replace_existing_settings=True, options=options))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

mesh = unreal.load_asset(dest)
assert mesh.skeleton == skeleton
mesh.set_editor_property('materials', materials)
mesh.set_editor_property('physics_asset', physics)
audit['capture'](dest, 'bind_after')
a = json.loads((out / 'bind_before.json').read_text()); b = json.loads((out / 'bind_after.json').read_text())
assert a['bones'] == b['bones'], 'Reference rig changed unexpectedly'
pos_err = max(max(abs(x - y) for x, y in zip(p, q)) for p, q in zip(a['positions'], b['positions']))
assert len(a['positions']) == len(b['positions']) and pos_err < 1e-3, ('Base mesh moved', pos_err)
morphs = sorted(m.get_name() for m in mesh.get_editor_property('morph_targets'))
assert morphs == sorted(EXPECTED), morphs
assert before_hashes == {str(p): digest(p) for p in protected}
(out / 'import_report.json').write_text(json.dumps(dict(morphs=morphs, base_position_max_cm=pos_err,
    backup=str(backup), saved=False), indent=1))
print('BOSS_EXPRESSIONS_IMPORTED_NOT_SAVED', morphs, 'base max cm', pos_err)
