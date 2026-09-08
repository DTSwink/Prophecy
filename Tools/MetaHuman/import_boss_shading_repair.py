"""Apply the normals-only fitted Boss export in memory; do not save packages."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
DEST='/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted'
OUT=ROOT/'Saved/BossShading/20260908'
mesh=unreal.load_asset(DEST)
materials=list(mesh.materials)
physics=mesh.physics_asset
skeleton=mesh.skeleton
protected=[ROOT/'Content/_mygame/SK_UEFN_Mannequin.uasset',
           ROOT/'Content/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN.uasset',
           Path(r'C:/Users/singerie/Documents/Blender/bossfinalsave.blend')]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before_hashes={str(p):digest(p)for p in protected}
audit={}
exec(compile((ROOT/'Tools/MetaHuman/audit_boss_unreal_20260907.py').read_text(),'boss_audit','exec'),audit)
audit['OUT']=OUT
audit['capture'](DEST,'bind_before_shading')

options=unreal.FbxImportUI()
options.set_editor_properties(dict(import_mesh=True,import_as_skeletal=True,import_animations=False,
    import_materials=False,import_textures=False,create_physics_asset=False,skeleton=skeleton,
    mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH))
options.skeletal_mesh_import_data.set_editor_properties(dict(import_morph_targets=False,
    update_skeleton_reference_pose=False,use_t0_as_ref_pose=False,
    normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS))
task=unreal.AssetImportTask()
task.set_editor_properties(dict(filename=str(ROOT/'Saved/BossUEFNCompatible/20260908_Shading/SKM_Boss_UEFN_Fitted.fbx'),
    destination_path=DEST.rsplit('/',1)[0],destination_name=DEST.rsplit('/',1)[1],
    automated=True,save=False,replace_existing=True,replace_existing_settings=True,options=options))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh=unreal.load_asset(DEST)
assert mesh.skeleton==skeleton
mesh.set_editor_property('materials',materials)
mesh.set_editor_property('physics_asset',physics)
audit['capture'](DEST,'bind_after_shading')
a=json.loads((OUT/'bind_before_shading.json').read_text())
b=json.loads((OUT/'bind_after_shading.json').read_text())
assert a['bones']==b['bones'] and a['weights']==b['weights'] and a['positions']==b['positions']
assert before_hashes=={str(p):digest(p)for p in protected}
result={'bones_weights_positions_unchanged':True,'saved':False,'protected_hashes':before_hashes,
        'imported_paths':list(task.imported_object_paths)}
(OUT/'shading_import.json').write_text(json.dumps(result,indent=2))
print('BOSS_SHADING_IMPORTED_UNSAVED',json.dumps(result))
