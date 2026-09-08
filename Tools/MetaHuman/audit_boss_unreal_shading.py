"""Read Unreal imported corner normals/tangents; no mesh edits."""
import json
import math
from collections import defaultdict
from pathlib import Path
import unreal

OUT=Path(unreal.Paths.project_saved_dir()).resolve()/'BossShading/20260908'
def capture(mesh,label,component=None):
    dm=unreal.DynamicMesh()
    if component is None:
        _,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh,dm,
            unreal.GeometryScriptCopyMeshFromAssetOptions(),
            unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL,lod_index=0))
    else:
        _,_,outcome=unreal.GeometryScript_SceneUtils.copy_mesh_from_component(component,dm,
            unreal.GeometryScriptCopyMeshFromComponentOptions(want_tangents=True),False)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
    xyz=lambda v:[v.x,v.y,v.z]
    positions=[xyz(unreal.GeometryScript_MeshQueries.get_vertex_position(dm,i)[0])
        for i in range(unreal.GeometryScript_MeshQueries.get_vertex_count(dm))]
    normals=defaultdict(list)
    corners=[]
    for i in range(unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm)):
        ids,valid=unreal.GeometryScript_MeshQueries.get_triangle_indices(dm,i)
        if not valid: continue
        _,valid,ns,ts,bs=unreal.GeometryScript_MeshQueries.get_triangle_normal_tangents(dm,i)
        assert valid
        uv0,uv1,uv2,uvvalid=unreal.GeometryScript_MeshQueries.get_triangle_u_vs(dm,0,i)
        for j,(vi,uv) in enumerate(zip((ids.x,ids.y,ids.z),(uv0,uv1,uv2))):
            n=xyz(getattr(ns,'vector'+str(j)))
            normals[vi].append(n)
            corners.append([vi,[uv.x,uv.y],n,xyz(getattr(ts,'vector'+str(j))),xyz(getattr(bs,'vector'+str(j)))])
    angle=lambda a,b:math.degrees(math.acos(max(-1.,min(1.,sum(x*y for x,y in zip(a,b))))))
    splits=[]
    for vi,ns in normals.items():
        maximum=max((angle(a,b) for a in ns for b in ns),default=0.)
        if maximum>1.: splits.append({'vertex':vi,'position':positions[vi],'degrees':maximum})
    sub=unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    sections=[{'section':i,'recompute':sub.get_section_recompute_tangent(mesh,0,i),
        'mask':str(sub.get_section_recompute_tangents_vertex_mask_channel(mesh,0,i))}
        for i in range(sub.get_num_sections(mesh,0))]
    result={'path':mesh.get_path_name(),'positions':positions,'corners':corners,'sections':sections,
        'split_normal_vertex_count':len(splits),'worst_splits':sorted(splits,key=lambda x:-x['degrees'])[:40]}
    (OUT/(label+'.json')).write_text(json.dumps(result))
    print(label,'vertices',len(positions),'corner_splits',len(splits),'sections',sections,'worst',result['worst_splits'][:3])

if __name__=='__main__':
    capture(unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted'),'unreal_before')
