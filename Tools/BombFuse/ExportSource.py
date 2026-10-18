"""Read-only original LOD0 export, run through Tools/RunUnrealRemote.py."""
import unreal,json,pathlib
mesh=unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/StaticMeshes/cc0_bomb')
v,t,n,uv,tan=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh,0,0)
data={'vertices':[[p.x,p.y,p.z] for p in v],'triangles':list(t),'normals':[[p.x,p.y,p.z] for p in n],
 'uv':[[p.x,p.y] for p in uv],'tangents':[[p.tangent_x.x,p.tangent_x.y,p.tangent_x.z,p.flip_tangent_y] for p in tan]}
path=pathlib.Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics/BombFuse/mesh.json')
path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data),encoding='utf-8')
print('Read-only LOD0 export:',len(v),'vertices;',len(t)//3,'triangles')
