"""Keep original Mixamo downloads intact; remove their empty template take in copies."""
import hashlib
import json
import sys
from pathlib import Path
import fbx
sys.path.insert(0, 'C:/Users/singerie/Documents/Cursor/stepper/fbx_npz_pipeline')
from fbx_to_npz import load_scene, collect_skeleton_nodes

root = Path(__file__).resolve().parents[2]
out = root / 'Saved/Diagnostics/MixamoThrows20261024/PreparedSources'
out.mkdir(parents=True, exist_ok=True)
records = []
for filename in ['Throwing.fbx', 'Throw Object.fbx']:
    source = Path('C:/Users/singerie/Downloads') / filename
    manager, scene = load_scene(source)
    criteria = fbx.FbxCriteria.ObjectType(fbx.FbxAnimStack.ClassId)
    stacks = [scene.GetSrcObject(criteria, i) for i in range(scene.GetSrcObjectCount(criteria))]
    record = {'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'removed_empty_takes': []}
    for stack in stacks:
        layer = stack.GetMember(fbx.FbxCriteria.ObjectType(fbx.FbxAnimLayer.ClassId), 0)
        has_keys = any(curve and curve.KeyGetCount() for node in collect_skeleton_nodes(scene)
                       for prop in [node.LclTranslation, node.LclRotation, node.LclScaling]
                       for axis in ['X', 'Y', 'Z'] for curve in [prop.GetCurve(layer, axis)])
        if not has_keys:
            record['removed_empty_takes'].append(stack.GetName())
            stack.Destroy()
        else:
            scene.SetCurrentAnimationStack(stack)
            scene.GetGlobalSettings().SetTimelineDefaultTimeSpan(stack.GetLocalTimeSpan())
            record['seconds'] = stack.GetLocalTimeSpan().GetDuration().GetSecondDouble()
    assert scene.GetSrcObjectCount(criteria) == 1
    output = out / filename
    exporter = fbx.FbxExporter.Create(manager, '')
    assert exporter.Initialize(str(output), -1, manager.GetIOSettings())
    assert exporter.Export(scene)
    exporter.Destroy()
    manager.Destroy()
    record['prepared'] = str(output)
    records.append(record)
(out.parent / 'source-receipt.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print(json.dumps(records, indent=2))
