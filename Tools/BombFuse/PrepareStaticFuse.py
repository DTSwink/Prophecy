"""Extract original fuse polygons without rigging, retaining shading and UV0."""
import unreal,pathlib,json
root=pathlib.Path(unreal.Paths.project_dir()).resolve();out=root/'Saved/Diagnostics/BombStaticFuse20261019';out.mkdir(parents=True,exist_ok=True)
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,'Preserve user Play'
data=json.loads((root/'Tools/BombFuse/Geometry.json').read_text());whole=data['meshes'][0]
source=out/'static-fuse-input.json'
source.write_text(json.dumps({'source':data['source'],'meshes':[{'name':'SM_BombFuse','fuse_positions':[v[:3]+[v[12]] for v in whole['vertices'] if v[12]>0]}]}))
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyBombLibrary'))
meshes=api.call_method('PrepareBombMeshes',(str(source),));assert len(meshes)==1
fuse=meshes[0];original=unreal.load_asset(data['source'])
editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
settings=editor.get_lod_build_settings(original,0)
settings.set_editor_property('generate_lightmap_u_vs',False) # UV1 stores burn distance.
editor.set_lod_build_settings(fuse,0,settings)
ov,ot,on,ou,ox=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(original,0,0)
fv,ft,fn,fu,fx=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(fuse,0,0)
assert len(ft)==470*3,('Expected original 470 fuse triangles',len(ft)//3)
def key(p):return tuple(round(x,4) for x in (p.x,p.y,p.z))
by_position={}
for i,p in enumerate(ov):by_position.setdefault(key(p),[]).append(i)
for j,p in enumerate(fv):
 assert any((on[i]-fn[j]).length()<.002 and (ou[i]-fu[j]).length()<.002 and (ox[i].tangent_x-fx[j].tangent_x).length()<.002 and ox[i].flip_tangent_y==fx[j].flip_tangent_y for i in by_position.get(key(p),[])),('Original fuse shading mismatch',j)
assert unreal.EditorAssetLibrary.save_loaded_asset(fuse,only_if_is_dirty=False)
receipt={'asset':fuse.get_path_name(),'triangles':len(ft)//3,'source_positions_normals_tangents_uv0_match':True}
(out/'mesh-verification.json').write_text(json.dumps(receipt,indent=2));print(receipt)
