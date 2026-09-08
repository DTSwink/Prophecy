"""Back up and import the stitched Boss; retain materials, PHAT and shared rig."""
import hashlib
import json
import shutil
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/BossUEFNCompatible/20260908_Stitched'
dest='/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted'
mesh=unreal.load_asset(dest)
materials=list(mesh.materials);physics=mesh.physics_asset;skeleton=mesh.skeleton
assert len(mesh.get_editor_property('morph_targets'))==0
assert unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).get_lod_count(mesh)==1
backup=out/'Backup/SKM_Boss_UEFN_Fitted.uasset'
assert not backup.exists(), 'Existing pre-stitch backup: do not overwrite'
backup.parent.mkdir(parents=True,exist_ok=True)
# Preserve the current mesh, including any recovered in-memory edits, before reimport.
assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,False)
shutil.copy2(root/'Content/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted.uasset',backup)
protected=[root/'Content/_mygame/SK_UEFN_Mannequin.uasset',
           root/'Content/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN.uasset',
           Path(r'C:/Users/singerie/Documents/Blender/bossfinalsave.blend')]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before_hashes={str(p):digest(p) for p in protected}
audit={}
exec(compile((root/'Tools/MetaHuman/audit_boss_unreal_20260907.py').read_text(),'audit_bind','exec'),audit)
audit['OUT']=out
audit['capture'](dest,'bind_before')
options=unreal.FbxImportUI()
options.set_editor_properties(dict(import_mesh=True,import_as_skeletal=True,import_animations=False,
    import_materials=False,import_textures=False,create_physics_asset=False,skeleton=skeleton,
    mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH))
options.skeletal_mesh_import_data.set_editor_properties(dict(import_morph_targets=False,
    update_skeleton_reference_pose=False,use_t0_as_ref_pose=False,
    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS))
task=unreal.AssetImportTask()
task.set_editor_properties(dict(filename=str(out/'SKM_Boss_UEFN_Fitted.fbx'),
    destination_path=dest.rsplit('/',1)[0],destination_name=dest.rsplit('/',1)[1],
    automated=True,save=False,replace_existing=True,replace_existing_settings=True,options=options))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=unreal.load_asset(dest)
assert mesh.skeleton==skeleton
mesh.set_editor_property('materials',materials)
mesh.set_editor_property('physics_asset',physics)
audit['capture'](dest,'bind_after')
a=json.loads((out/'bind_before.json').read_text());b=json.loads((out/'bind_after.json').read_text())
assert a['bones']==b['bones'], 'Reference rig changed unexpectedly'
assert before_hashes=={str(p):digest(p) for p in protected}
shade={}
exec(compile((root/'Tools/MetaHuman/audit_boss_unreal_shading.py').read_text(),'audit_normals','exec'),shade)
shade['OUT']=out
shade['capture'](mesh,'unreal_stitched')
print('STITCH_IMPORTED_NOT_YET_SAVED',len(a['positions']),len(b['positions']),str(backup))
