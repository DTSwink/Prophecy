"""Compare every exported joint/frame and the user's known working FBX rig."""
import sys, json, hashlib
from pathlib import Path
import fbx
import numpy as np
sys.path.insert(0,'C:/Users/singerie/Documents/Cursor/stepper/fbx_npz_pipeline')
from fbx_to_npz import load_scene,collect_skeleton_nodes,make_sample_times

root=Path(__file__).resolve().parents[2]
audit=root/'Saved/Diagnostics/MixamoThrows20261024'
out=Path('C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024')
working=Path('C:/Users/singerie/Documents/cascadeur/Sitting_Idle_Anim1.FBX')
def matrix(m):return np.array([[m.Get(i,j) for j in range(4)] for i in range(4)])
def schema(scene):
    bones=collect_skeleton_nodes(scene)
    return {n.GetName():{'parent':n.GetParent().GetName(),
            'translation':list(n.LclTranslation.Get()),'rotation':list(n.LclRotation.Get()),'scale':list(n.LclScaling.Get()),
            'pre':list(n.GetPreRotation(fbx.FbxNode.EPivotSet.eSourcePivot)),
            'post':list(n.GetPostRotation(fbx.FbxNode.EPivotSet.eSourcePivot))} for n in bones}
wm,ws=load_scene(working);reference=schema(ws)
results=[]
for name,count in [('Throwing',168),('Throw_Object',147)]:
    old=out/('UEFN_'+name+'.fbx');new=out/('UEFN_'+name+'_AnimationOnly.fbx')
    if not old.exists():old=audit/'SupersededMeshExports'/old.name
    om,os=load_scene(old);nm,ns=load_scene(new)
    times,fps,_,_=make_sample_times(ns)
    assert len(times)==count and fps==30
    assert schema(ns)==reference, 'Rig differs from known working export'
    mesh_count=0
    def visit(node):
        global mesh_count
        mesh_count+=int(node.GetMesh() is not None)
        for i in range(node.GetChildCount()):visit(node.GetChild(i))
    visit(ns.GetRootNode())
    assert mesh_count==0 and ns.GetPoseCount()==0
    assert ns.GetRootNode().GetChildCount()==1 and ns.GetRootNode().GetChild(0).GetName()=='root'
    old_nodes={n.GetName():n for n in collect_skeleton_nodes(os)}
    new_nodes={n.GetName():n for n in collect_skeleton_nodes(ns)}
    max_error=0
    for t in times:
        for bone in new_nodes:
            a=matrix(old_nodes[bone].EvaluateGlobalTransform(t));b=matrix(new_nodes[bone].EvaluateGlobalTransform(t))
            assert np.isfinite(b).all()
            max_error=max(max_error,float(np.abs(a-b).max()))
    assert max_error<1e-6,max_error
    results.append({'file':str(new),'sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'frames':count,'fps':fps,'bones':len(new_nodes),
                    'rig_exactly_matches_working_export':True,'meshes':mesh_count,'bind_poses':ns.GetPoseCount(),
                    'max_all_frame_joint_transform_difference':max_error})
    om.Destroy();nm.Destroy()
wm.Destroy()
(audit/'animation-only-verification.json').write_text(json.dumps({'success':True,'working_reference':str(working),'exports':results,'cascadeur_ui_test':False},indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
