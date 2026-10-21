"""Bake only the rigid shell, preserving original static-mesh vertex attributes."""
import unreal,pathlib,json
root=pathlib.Path(unreal.Paths.project_dir()).resolve()
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,'Preserve user Play'
data=json.loads((root/'Tools/BombFuse/Geometry.json').read_text())
whole=data['meshes'][0]
points=[v[:3] for v in whole['vertices'] if v[12]>0]
out=root/'Saved/Diagnostics/BombStartup20261019';out.mkdir(parents=True,exist_ok=True)
source=out/'shell-input.json'
source.write_text(json.dumps({'source':data['source'],'meshes':[{'name':'SM_BombShell','fuse_positions':points}]}))
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyBombLibrary'))
meshes=api.call_method('PrepareBombMeshes',(str(source),));assert len(meshes)==1
shell=meshes[0]
original=unreal.load_asset(data['source'])
# Match the original build as well as its imported attributes: this asset uses
# MikkTSpace tangent recomputation, so imported FBX tangents alone differ.
editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
editor.set_lod_build_settings(shell,0,editor.get_lod_build_settings(original,0))
ov,ot,on,ou,ox=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(original,0,0)
sv,st,sn,su,sx=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(shell,0,0)
assert len(st)<len(ot) and len(st)>0
# Compare rendered shading data, not just material pointers.
def key(p):return tuple(round(x,4) for x in (p.x,p.y,p.z))
by_position={}
for i,p in enumerate(ov):by_position.setdefault(key(p),[]).append(i)
for j,p in enumerate(sv):
 candidates=by_position.get(key(p),[])
 assert any((on[i]-sn[j]).length()<.002 and (ou[i]-su[j]).length()<.002 and (ox[i].tangent_x-sx[j].tangent_x).length()<.002 and ox[i].flip_tangent_y==sx[j].flip_tangent_y for i in candidates),('shading mismatch',j)
assert unreal.EditorAssetLibrary.save_loaded_asset(shell,only_if_is_dirty=False)
report={'shell':shell.get_path_name(),'triangles':len(st)//3,'source_triangles':len(ot)//3,'source_normals_tangents_uv0_match':True}
(out/'shell-verification.json').write_text(json.dumps(report,indent=2));print(report)
