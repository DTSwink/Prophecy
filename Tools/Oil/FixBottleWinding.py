"""Correct the RH manifold -> UE raster winding once, preserving outward normals.
Only authored oil-bottle render assets; no physics/collision changes or build.
"""
import unreal as u,json,shutil
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
root='/Game/_mygame/OilBottle';out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Studio'
backup=out/'before-winding';backup.mkdir(exist_ok=True)
assets=[root+'/Meshes/SM_OilBottle']+[root+f'/Debris/SM_OilFragment_{i:02}' for i in range(20)]
rows=[];A=u.GeometryScript_AssetUtils;N=u.GeometryScript_Normals;Q=u.GeometryScript_MeshQueries
for path in assets:
 mesh=u.load_asset(path);assert mesh
 if u.EditorAssetLibrary.get_metadata_tag(mesh,'OilWindingVersion')=='UE-CW-1':continue
 source=Path(u.Paths.project_content_dir())/(path.removeprefix('/Game/')+'.uasset')
 if not (backup/source.name).exists():shutil.copy2(source,backup/source.name)
 body=mesh.get_editor_property('body_setup');materials=list(mesh.get_editor_property('static_materials'))
 d=u.DynamicMesh();d,result=A.copy_mesh_from_static_mesh(mesh,d,u.GeometryScriptCopyMeshFromAssetOptions(apply_build_settings=False),u.GeometryScriptMeshReadLOD())
 assert result==u.GeometryScriptOutcomePins.SUCCESS
 count=d.get_triangle_count();bounds=str(Q.get_mesh_bounding_box(d))
 N.flip_normals(d)
 # flip_normals changes both winding and normals. The authored normals were
 # already outward; negate only the resulting normals to retain that lighting.
 for i in range(count):
  _,n1,n2,n3,valid=Q.get_triangle_normals(d,i);assert valid
  _,valid=N.set_mesh_triangle_normals(d,i,u.GeometryScriptTriangle(n1*-1,n2*-1,n3*-1),True);assert valid
 options=u.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=False,enable_recompute_tangents=True,replace_materials=False)
 _,result=A.copy_mesh_to_static_mesh(d,mesh,options,u.GeometryScriptMeshWriteLOD())
 assert result==u.GeometryScriptOutcomePins.SUCCESS
 assert mesh.get_editor_property('body_setup')==body
 assert len(mesh.get_editor_property('static_materials'))==len(materials)
 u.EditorAssetLibrary.set_metadata_tag(mesh,'OilWindingVersion','UE-CW-1')
 assert u.EditorAssetLibrary.save_loaded_asset(mesh,False)
 rows.append({'asset':path,'triangles':count,'bounds':bounds,'collision_body_preserved':True})
(out/'winding.json').write_text(json.dumps(rows,indent=2))
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
 if isinstance(a,u.ProphecyOilBottle):a.bottle.set_editor_property('reverse_culling',False)
print('OIL_WINDING_FIXED',len(rows))
