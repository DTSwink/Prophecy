"""Ensure the collision-only FBX roundtrip did not alter visible mesh attributes."""
import fbx,hashlib,json,pathlib
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/SpearPike20261030'
def snapshot(path):
    manager=fbx.FbxManager.Create();scene=fbx.FbxScene.Create(manager,'Verify')
    reader=fbx.FbxImporter.Create(manager,'Read')
    assert reader.Initialize(str(path),-1,manager.GetIOSettings()) and reader.Import(scene)
    data={}
    def value(v):
        if isinstance(v,fbx.FbxColor):return [v.mRed,v.mGreen,v.mBlue,v.mAlpha]
        if isinstance(v,fbx.FbxObject):return v.GetName()
        try:return list(v)
        except TypeError:
            assert isinstance(v,(int,float,str,bool)),type(v)
            return v
    for i in range(scene.GetRootNode().GetChildCount()):
        n=scene.GetRootNode().GetChild(i)
        if n.GetName().startswith('UCX_'):continue
        row={'translation':list(n.LclTranslation.Get()),'rotation':list(n.LclRotation.Get()),'scale':list(n.LclScaling.Get()),
             'materials':[n.GetMaterial(j).GetName() for j in range(n.GetMaterialCount())]}
        m=n.GetMesh()
        if m:
            row['vertices']=[list(m.GetControlPointAt(j)) for j in range(m.GetControlPointsCount())]
            row['faces']=[[m.GetPolygonVertex(j,k) for k in range(m.GetPolygonSize(j))] for j in range(m.GetPolygonCount())]
            row['layers']={}
            for kind in ('Normal','Tangent','Binormal','UV','VertexColor','Material'):
                layers=[]
                for j in range(getattr(m,'GetElement'+kind+'Count')()):
                    layer=getattr(m,'GetElement'+kind)(j)
                    layers.append({'mapping':str(layer.GetMappingMode()),'reference':str(layer.GetReferenceMode()),
                        'direct':[value(layer.GetDirectArray().GetAt(k)) for k in range(layer.GetDirectArray().GetCount())],
                        'index':[layer.GetIndexArray().GetAt(k) for k in range(layer.GetIndexArray().GetCount())]})
                row['layers'][kind]=layers
        data[n.GetName()]=row
    reader.Destroy();manager.Destroy()
    return data
a=snapshot(root/'Exports/ImperialSpear/SM_ImperialSpear.fbx')
b=snapshot(root/'Exports/ImperialSpear/Unreal/SM_ImperialSpear.fbx')
assert a==b,'Render mesh, shading attributes, sockets or transforms changed'
result={'render_and_socket_data_equal':True,'nodes':list(a),'sha256':hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest(),
        'checked':['control points','polygons','normals','tangents','binormals','UVs','vertex colors','material slots','transforms','sockets']}
(out/'collision-render-parity.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
