"""Compare live lab continuation against the user's immutable model-viewer export."""
import hashlib,json,urllib.request,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
EXPORT=ROOT.parents[1]/'Exports/WalkF_Rollout_20261027'
meta=json.loads((EXPORT/'metadata.json').read_text())
assert hashlib.sha256((EXPORT/'walkf_rollout.npz').read_bytes()).hexdigest()==meta['files']['walkf_rollout.npz']['sha256']
with np.load(EXPORT/'walkf_rollout.npz',allow_pickle=False) as z:
    names=z['bone_names'].tolist();points=z['positions_m'];axes=z['rotations'];roots=z['source_root_positions_m'];visible=z['visible_bone_indices']
    original_roots=roots.copy();count=len(points)-1
    period=len(roots)-1;delta=roots[-1]-roots[0]
    roots=np.array([roots[i%period]+delta*(i//period) for i in range(count+10)])
    seeds=[dict(points=[original_roots[i].tolist(),*points[i].tolist()],axes=[np.eye(3).tolist(),*axes[i].tolist()]) for i in (0,1)]
    request=dict(gait='walk',policy='run',direction='forward',frames=count,names=['root',*names],seeds=seeds,roots=roots.tolist(),verifyReference=True)
    matched='--matched-source' in sys.argv
    if matched:
        # Same checkpoint, source geometry and two-frame history as the export.
        # This changes only this audit process, never the live lab context.
        from nn_worker import ResumeLocomotion, runtime_data
        owner=ResumeLocomotion('run');old=owner.runtime;source=Path(meta['source'])
        assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['source_sha256']
        owner.runtime=runtime_data.CategoryRuntime('run',old.checkpoint,old.cfg,old.model,[source.name],owner.device,
            lower_source_paths=[source],full_source_paths_by_mode={-1.0:[source],1.0:[source]},cyclic_flags=[True])
        owner.gait='audit-walkf-source'
        result=owner.resume(request)
    else:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8890/resume',data=json.dumps(request).encode(),headers={'Content-Type':'application/json'}),timeout=100) as response: result=json.load(response)
    suffix='matched' if matched else 'lab'
    (ROOT/f'snapshots/model-viewer-walkf-{suffix}-resume.json').write_text(json.dumps(result,separators=(',',':')))
    lab=np.array([p['points'] for p in result['poses']]);rot=np.array([p['axes'] for p in result['poses']]);error=np.linalg.norm(lab[:,visible]-points[1:,visible],axis=-1)
    rows=[dict(frame=i+1,maxCm=float(error[i].max()*100)) for i in range(count)]
    report=dict(maxPositionCm=float(error.max()*100),perBoneCm={names[j]:float(np.linalg.norm(lab[:,j]-points[1:,j],axis=-1).max()*100) for j in visible},rotationMatrixMax=float(np.abs(rot[:,visible]-axes[1:,visible]).max()),referenceError=result['referenceError'],pin=result['pinDiagnostics'],rows=rows)
    (ROOT/f'snapshots/model-viewer-{suffix}-parity.json').write_text(json.dumps(report,indent=2))
    if matched:
        # Float32 recurrence/root rebasing: allow at most 0.1 mm over 4 s.
        assert report['maxPositionCm']<.01,report
        assert report['rotationMatrixMax']<.002,report
    print(json.dumps({**report,'rows':rows[:6]+rows[-3:]},indent=2))
