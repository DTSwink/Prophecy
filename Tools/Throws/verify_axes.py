"""Check the runtime conversion against UE5's actual FBX import convention.

Read-only SDK inspection; no UE imports or user asset edits.
"""
import json, sys
from pathlib import Path
import numpy as np
import fbx
from scipy.spatial.transform import Rotation
sys.path.insert(0, 'C:/Users/singerie/Documents/Cursor/stepper/fbx_npz_pipeline')
from fbx_to_npz import load_scene, collect_skeleton_nodes, make_sample_times, normalize_scene_axis_system
root=Path(__file__).resolve().parents[2]
clips=json.loads((root/'Labs/ThrowLab/data/clips.json').read_text(encoding='utf-8'))
rx=Rotation.from_rotvec([np.pi/2,0,0])
max_position=max_rotation=0.
for clip in clips['clips']:
    manager,scene=load_scene(Path(clip['source']))
    try:
        normalize_scene_axis_system(scene)
        nodes={n.GetName():n for n in collect_skeleton_nodes(scene)}
        times,_,_,_=make_sample_times(scene)
        factor=scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor()
        normalized=[]
        for t in times:
            normalized.append([(np.array(list(nodes[n].EvaluateGlobalTransform(t).GetT())[:3])*factor,
                                np.array(list(nodes[n].EvaluateGlobalTransform(t).GetQ()))) for n in clips['names']])
        # FbxMainImport.cpp, bForceFrontXAxis=false; FbxUtilsImport.cpp mirrors Y.
        axis=fbx.FbxAxisSystem.MayaZUp
        assert axis.GetUpVector()==(fbx.FbxAxisSystem.EUpVector.eZAxis,1)
        assert axis.GetFrontVector()==(fbx.FbxAxisSystem.EFrontVector.eParityOdd,-1)
        assert axis.GetCoorSystem()==fbx.FbxAxisSystem.ECoordSystem.eRightHanded
        axis.ConvertScene(scene)
        scene.GetAnimationEvaluator().Reset()
        for i,t in enumerate(times):
            for j,n in enumerate(clips['names']):
                m=nodes[n].EvaluateGlobalTransform(t)
                p=np.array(list(m.GetT())[:3])*factor*[1,-1,1]
                q=np.array(list(m.GetQ()))*[-1,1,-1,1]
                lp,lq=normalized[i][j]
                expected_p=lp[[0,2,1]]
                expected_q=(rx*Rotation.from_quat(lq)).as_quat()*[-1,1,-1,1]
                max_position=max(max_position,float(np.linalg.norm(p-expected_p)))
                max_rotation=max(max_rotation,float(1-abs(q@expected_q)))
    finally:
        manager.Destroy()
assert max_position<1e-6 and max_rotation<1e-12,(max_position,max_rotation)
receipt=dict(success=True,maxPositionCm=max_position,maxQuaternionError=max_rotation,
             convention='UE5.7 FBX Z-up/-Y-forward conversion, then Y reflection; all raw bones and frames')
(root/'Saved/Diagnostics/ThrowPort20261029/axes.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
