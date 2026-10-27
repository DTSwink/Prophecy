"""Read only the two authored FBXs; cache their original samples for the lab."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import fbx
sys.path.insert(0, 'C:/Users/singerie/Documents/Cursor/stepper/fbx_npz_pipeline')
from fbx_to_npz import load_scene, collect_skeleton_nodes, make_sample_times, normalize_scene_axis_system
ROOT = Path(__file__).resolve().parent
SOURCE = Path('C:/Users/singerie/Documents/Cursor/stepper/ue5/slashes/recoveries')

def export():
    names = json.loads((ROOT.parent/'BodyflipLab/data/manifest.json').read_text())['names']
    clips=[]
    for label in ['big throw', 'small throw']:
        source=SOURCE/(label+'.fbx'); before=hashlib.sha256(source.read_bytes()).hexdigest()
        manager, scene=load_scene(source)
        try:
            original, normalized, converted=normalize_scene_axis_system(scene)
            nodes={n.GetName():n for n in collect_skeleton_nodes(scene)}
            assert all(n in nodes for n in names), 'Missing UEFN bones'
            parents=[]
            for name in names:
                parent=nodes[name].GetParent()
                while parent and parent.GetName() not in names: parent=parent.GetParent()
                parents.append(names.index(parent.GetName()) if parent else -1)
            times,fps,start,end=make_sample_times(scene)
            scale=scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor()*.01
            frames=[]
            for time in times:
                row=[]
                for name in names:
                    tr=nodes[name].EvaluateGlobalTransform(time)
                    row.append([*[float(x)*scale for x in list(tr.GetT())[:3]], *list(tr.GetQ())])
                frames.append(row)
            assert np.isfinite(frames).all() and len(frames)>1
            assert before==hashlib.sha256(source.read_bytes()).hexdigest()
            clips.append(dict(id=label.replace(' ','-'),name=label,fps=fps,duration=(end-start)/fps,
                source=str(source),sha256=before,startFrame=start,frames=frames,sourceAxis=original))
        finally: manager.Destroy()
    result=dict(schema='throw-lab-y-up-metres-quaternion-v1',names=names,parents=parents,clips=clips)
    (ROOT/'data/clips.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(json.dumps([dict(name=c['name'],frames=len(c['frames']),fps=c['fps'],duration=c['duration'],sha256=c['sha256']) for c in clips],indent=2))

if __name__=='__main__': export()
