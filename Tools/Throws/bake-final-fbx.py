"""Write final no-aim animation into copies of the original complete UEFN FBXs.

Run bake-final.mjs first. FBX SDK round-trip verifies every baked lab bone/frame.
Source hierarchy, skin and ancillary bone local motion are retained.
"""
import hashlib
import json
import sys
from pathlib import Path
import fbx
import numpy as np

sys.path.insert(0, 'C:/Users/singerie/Documents/Cursor/stepper/fbx_npz_pipeline')
from fbx_to_npz import load_scene, normalize_scene_axis_system, collect_skeleton_nodes

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Exports/Throws/FinalNoAim'
DATA = json.loads((OUT / 'clips.json').read_text(encoding='utf-8'))
MANIFEST = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
PIVOT = fbx.FbxNode.EPivotSet.eSourcePivot


def children(node):
    for i in range(node.GetChildCount()):
        child = node.GetChild(i)
        yield child
        yield from children(child)


def at(frame):
    t = fbx.FbxTime()
    t.SetSecondDouble(frame / 60)
    return t


def matrix(row, units):
    m = fbx.FbxAMatrix()
    m.SetQ(fbx.FbxQuaternion(*row[3:]))
    m.SetT(fbx.FbxVector4(*(v / units for v in row[:3])))
    return m


receipts = []
for clip, meta in zip(DATA['clips'], MANIFEST['clips']):
    source = Path(meta['source'])
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    assert before == meta['sourceSha256'], 'Cached source and FBX do not match'
    manager, scene = load_scene(source)
    try:
        normalize_scene_axis_system(scene)
        units = scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor() * .01
        nodes = list(children(scene.GetRootNode()))
        names = DATA['names']
        selected = {name: i for i, name in enumerate(names)}
        skeleton_names = [n.GetName() for n in collect_skeleton_nodes(scene)]
        assert len(set(n.GetName() for n in nodes)) == len(nodes)
        tracks = {n.GetName(): [] for n in nodes}
        expected = []
        # Fail rather than flatten a nontrivial pivot silently.
        for n in nodes:
            for getter in ('GetRotationPivot',
                           'GetScalingPivot', 'GetRotationOffset', 'GetScalingOffset'):
                assert np.max(np.abs(list(getattr(n, getter)(PIVOT))[:3])) < 1e-8, (n.GetName(), getter)
        for f, rows in enumerate(clip['frames']):
            t = at(f)
            wanted = {name: matrix(rows[j], units) for name, j in selected.items()}
            globals_at_frame = {}
            for n in nodes:
                name = n.GetName()
                parent = n.GetParent()
                parent_world = globals_at_frame.get(parent.GetName(), parent.EvaluateGlobalTransform(t))
                local = parent_world.Inverse() * wanted[name] if name in selected else n.EvaluateLocalTransform(t)
                globals_at_frame[name] = parent_world * local
                pre, post, rotation = fbx.FbxAMatrix(), fbx.FbxAMatrix(), fbx.FbxAMatrix()
                pre.SetR(n.GetPreRotation(PIVOT))
                post.SetR(n.GetPostRotation(PIVOT))
                rotation.SetQ(local.GetQ())
                euler = (pre.Inverse() * rotation * post).GetR()
                tracks[name].append([list(local.GetT())[:3], list(euler)[:3], list(local.GetS())[:3]])
            expected.append({name: (list(m.GetT())[:3], list(m.GetQ())) for name, m in globals_at_frame.items()})
        criteria = fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId)
        while scene.GetSrcObjectCount(criteria):
            scene.GetSrcObject(criteria, 0).Destroy()
        stack = fbx.FbxAnimStack.Create(scene, clip['id'] + '_Final_NoAim')
        layer = fbx.FbxAnimLayer.Create(scene, 'Baked')
        stack.AddMember(layer)
        scene.SetCurrentAnimationStack(stack)
        scene.GetGlobalSettings().SetTimeMode(fbx.FbxTime.EMode.eFrames60)
        span = fbx.FbxTimeSpan(at(0), at(len(clip['frames']) - 1))
        stack.SetLocalTimeSpan(span)
        stack.SetReferenceTimeSpan(span)
        scene.GetGlobalSettings().SetTimelineDefaultTimeSpan(span)
        for n in nodes:
            values = np.asarray(tracks[n.GetName()])
            values[:, 1, :] = np.rad2deg(np.unwrap(np.deg2rad(values[:, 1, :]), axis=0))
            for index, prop in enumerate((n.LclTranslation, n.LclRotation, n.LclScaling)):
                for axis, channel in enumerate('XYZ'):
                    curve = prop.GetCurve(layer, channel, True)
                    curve.KeyModifyBegin()
                    for f, value in enumerate(values[:, index, axis]):
                        key = curve.KeyAdd(at(f))[0]
                        curve.KeySetValue(key, float(value))
                        curve.KeySetInterpolation(key, fbx.FbxAnimCurveDef.EInterpolationType.eInterpolationLinear)
                    curve.KeyModifyEnd()
        path = OUT / meta['file']
        exporter = fbx.FbxExporter.Create(manager, '')
        assert exporter.Initialize(str(path), -1, manager.GetIOSettings()), exporter.GetStatus().GetErrorString()
        assert exporter.Export(scene), exporter.GetStatus().GetErrorString()
        exporter.Destroy()
    finally:
        manager.Destroy()

    # Reopen the actual deliverable, not the pre-export scene.
    manager, scene = load_scene(path)
    max_pos = max_rot = max_all_pos = max_all_rot = 0.
    try:
        normalize_scene_axis_system(scene)
        actual = {n.GetName(): n for n in children(scene.GetRootNode())}
        assert skeleton_names == [n.GetName() for n in collect_skeleton_nodes(scene)]
        factor = scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor() * .01
        for f, rows in enumerate(clip['frames']):
            for name, n in actual.items():
                m = n.EvaluateGlobalTransform(at(f))
                p, q = np.array(list(m.GetT())[:3]), np.array(list(m.GetQ()))
                ep, eq = expected[f][name]
                max_all_pos = max(max_all_pos, float(np.linalg.norm((p - ep) * factor)))
                max_all_rot = max(max_all_rot, float(1 - abs(q @ eq)))
                if name in selected:
                    row = rows[selected[name]]
                    max_pos = max(max_pos, float(np.linalg.norm(p * factor - row[:3])))
                    max_rot = max(max_rot, float(1 - abs(q @ row[3:])))
        # SDK animation keys store floats; sub-millimeter error is expected.
        assert max_pos < 2e-5 and max_rot < 1e-10, (max_pos, max_rot)
        assert max_all_pos < 2e-5 and max_all_rot < 1e-10, (max_all_pos, max_all_rot)
    finally:
        manager.Destroy()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    receipts.append(dict(file=path.name,frames=len(clip['frames']),skeletonBones=len(skeleton_names),
                         maxLabPositionErrorMeters=max_pos,maxLabQuaternionError=max_rot,
                         maxAllNodePositionErrorMeters=max_all_pos,maxAllNodeQuaternionError=max_all_rot,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sourceUnchanged=True))
(OUT / 'verification.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
print(json.dumps(receipts, indent=2))
