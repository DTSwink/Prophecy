"""Read back final Unreal FBXs with Autodesk SDK and verify animation/rig integrity."""
import hashlib
import json
import sys
from pathlib import Path
import fbx
import numpy as np
sys.path.insert(0, 'C:/Users/singerie/Documents/Cursor/stepper/fbx_npz_pipeline')
from fbx_to_npz import load_scene, collect_skeleton_nodes, make_sample_times, get_system_unit

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'Saved/Diagnostics/MixamoThrows20261024'
OUT = Path('C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024')
result = json.loads((AUDIT / 'unreal-result.json').read_text(encoding='utf-8'))
assert result.get('success'), result
records = []
poses = []
for row, expected in zip(result['exports'], [168, 147]):
    path = Path(row['file'])
    manager, scene = load_scene(path)
    nodes = collect_skeleton_nodes(scene)
    names = [n.GetName() for n in nodes]
    times, fps, first, last = make_sample_times(scene)
    assert len(times) == expected and abs(fps-30) < 1e-6, (len(times), fps)
    assert {'root', 'pelvis', 'spine_05', 'neck_02', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r'} <= set(names), names
    assert not any('mixamo' in n.lower() for n in names)
    positions=[]
    max_scale_error=0
    for time in times:
        frame=[]
        for node in nodes:
            transform=node.EvaluateGlobalTransform(time)
            p=np.array([transform.GetT()[i] for i in range(3)])
            q=np.array([transform.GetQ()[i] for i in range(4)])
            scale=np.array([transform.GetS()[i] for i in range(3)])
            assert np.isfinite(np.r_[p,q,scale]).all()
            max_scale_error=max(max_scale_error,float(np.max(np.abs(scale-1))))
            frame.append(p)
        positions.append(frame)
    positions=np.array(positions)
    assert max_scale_error < 0.001, max_scale_error
    motion=float(np.ptp(positions[:, names.index('hand_r')],axis=0).max())
    assert motion > 10, motion
    meshes=[]
    def visit(node):
        mesh=node.GetMesh()
        if mesh:
            skins = sum(mesh.GetDeformer(i).GetClassId().GetName() == 'FbxSkin' for i in range(mesh.GetDeformerCount()))
            meshes.append({'name':node.GetName(),'vertices':mesh.GetControlPointsCount(),'skins':skins})
        for i in range(node.GetChildCount()):
            visit(node.GetChild(i))
    visit(scene.GetRootNode())
    assert meshes and all(m['skins'] > 0 for m in meshes), meshes
    record={**row,'frames':len(times),'fps':fps,'bones':len(names),'unit':get_system_unit(scene),
            'max_scale_error':max_scale_error,'hand_motion_cm':motion,'meshes':meshes,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    records.append(record)
    poses.append((path.stem,names,positions))
    manager.Destroy()
for source in json.loads((AUDIT/'source-receipt.json').read_text(encoding='utf-8')):
    assert hashlib.sha256(Path(source['source']).read_bytes()).hexdigest()==source['sha256']
(AUDIT/'verification.json').write_text(json.dumps({'success':True,'exports':records,'original_downloads_unchanged':True},indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig=plt.figure(figsize=(18,7))
chains=[['pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head'],
        ['spine_05','clavicle_l','upperarm_l','lowerarm_l','hand_l'],
        ['spine_05','clavicle_r','upperarm_r','lowerarm_r','hand_r'],
        ['pelvis','thigh_l','calf_l','foot_l','ball_l'],['pelvis','thigh_r','calf_r','foot_r','ball_r']]
for row,(name,names,values) in enumerate(poses):
    for column,frame in enumerate(np.linspace(0,len(values)-1,6,dtype=int)):
        ax=fig.add_subplot(2,6,row*6+column+1,projection='3d')
        value=values[frame]  # Unreal exporter writes Z-up FBX.
        centre=value[names.index('pelvis')]
        for chain,color in zip(chains,['#555555','#1685d1','#dd6b20','#1685d1','#dd6b20']):
            points=value[[names.index(b) for b in chain]]
            ax.plot(points[:,0],points[:,1],points[:,2],color=color,linewidth=2,marker='o',markersize=3)
        ax.set(xlim=(centre[0]-110,centre[0]+110),ylim=(centre[1]-110,centre[1]+110),zlim=(0,220),title=f'{name}\nframe {frame}')
        ax.set_box_aspect((1,1,1))
        ax.view_init(elev=12,azim=-65)
fig.tight_layout()
fig.savefig(AUDIT/'pose-review.png',dpi=120)
