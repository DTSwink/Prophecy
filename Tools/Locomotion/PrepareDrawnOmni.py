"""Separate drawn dataset: original capture/cut/retarget/foot-lift pipeline.

Never edits PHAT, accepted references, or active training configuration. Current
limits are audited and violations reported rather than clamped or widened.
"""
import argparse,hashlib,json,pickle,shutil,sys
from pathlib import Path
import numpy as np
import yaml
from SelectOmniLoops import select
from PrepareMimicKitOmni import main as retarget,ROOT


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(out,original_paths):
    baseline=[]
    for path in (ROOT/'Saved/MimicKitUEFN/omni/manifest.json',ROOT/'Saved/MimicKitUEFN/idle/retarget/manifest.json'):
        baseline.extend(json.loads(path.read_text())['motions'])
    metadata={m['id']:m for m in baseline};entries=[]
    unarmed=out/'unarmed';unarmed.mkdir(exist_ok=True)
    for p in original_paths:
        identifier=p.stem+'_Unarmed';dest=unarmed/(identifier+'.pkl')
        shutil.copyfile(p,dest);assert digest(dest)==digest(p)
        old=unarmed/p.name
        if old.exists():
            assert digest(old)==digest(p),'Do not remove a changed duplicate'
            old.unlink()
        entries.append(dict(metadata[p.stem],id=identifier,source_id=p.stem,file=str(dest),weight=1.,sword_drawn=False))
    manifest_path=out/'drawn/manifest.json';manifest=json.loads(manifest_path.read_text())
    for row in manifest['motions']:
        original=row.get('source_id',row['id']);identifier=original+'_Drawn'
        source=out/'drawn'/(original+'.pkl');dest=out/'drawn'/(identifier+'.pkl')
        if source.exists():source.replace(dest)
        assert dest.is_file()
        row.update(id=identifier,source_id=original,sword_drawn=True)
        entries.append(dict(row,file=str(dest),weight=1.))
    assert len(entries)==54 and len({m['id'] for m in entries})==54
    manifest_path.write_text(json.dumps(manifest,indent=2))
    for folder,items in ((out,entries),(out/'drawn',[m for m in entries if m['sword_drawn']]),(unarmed,[m for m in entries if not m['sword_drawn']])):
        (folder/'motions.yaml').write_text(yaml.safe_dump(dict(motions=[dict(file=m['file'],weight=m['weight']) for m in items])))
    (out/'dataset.json').write_text(json.dumps(dict(status='candidate_for_review',motions=entries),indent=2))
    return entries


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=ROOT/'Saved/Diagnostics/OmniDrawn20261016')
    parser.add_argument('--output',type=Path,default=ROOT/'Saved/MimicKitUEFN/equipment')
    args=parser.parse_args();source=args.source.resolve();out=args.output.resolve()
    gallery=json.loads((ROOT/'Labs/OmniLocomotionViewer/data.json').read_text())['clips']
    expected=[dict(id=c['id'],gait=c['gait'],label=c['label']) for c in gallery]
    expected.append(dict(id='M_Neutral_Stand_Idle_Loop',gait='idle',label='Idle'))
    assert len(expected)==27
    missing=[c['id'] for c in expected if not (source/(c['id']+'.json')).exists()]
    assert not missing,('Missing drawn captures',missing)
    original=yaml.safe_load((ROOT/'Saved/MimicKitLocal/prepared/motions.yaml').read_text())['motions']
    assert len(original)==27
    original_paths=[Path(m['file']) for m in original]
    protected={str(p):digest(p) for p in original_paths}
    protected[str(ROOT/'Labs/MimicKitUEFN/limits.json')]=digest(ROOT/'Labs/MimicKitUEFN/limits.json')
    cuts={};capture_reports=[];clips=[]
    for clip in expected:
        path=source/(clip['id']+'.json');raw=json.loads(path.read_text());rows=raw['rows']
        assert raw['sword_drawn'] is True and raw['mode']=='kinematic'
        assert len(rows)==raw['record_ticks']+1
        assert [r['elapsed'] for r in rows]==list(range(120,121+raw['record_ticks']))
        assert all(b['engine_frame']==a['engine_frame']+1 for a,b in zip(rows,rows[1:]))
        assert np.isfinite(np.asarray([r['pose'] for r in rows])).all()
        assert all(abs(r['weights'][1]-float(raw['run']))<1e-5 for r in rows)
        expected_speed=min(raw['requested_speed'],raw['unscaled_target_speed'])
        speed_error=max(abs(np.linalg.norm(r['velocity_cm_s'])-expected_speed) for r in rows)
        if clip['gait']=='idle':assert max(np.linalg.norm(r['move_input']) for r in rows)<1e-8
        else:assert speed_error<1.5
        if clip['gait']=='idle':
            # Idle has no alternating stride. Keep its complete authored-length
            # NN recording; report its endpoint mismatch without inventing a cut.
            pose=np.asarray([r['pose'] for r in rows]);delta=pose[-1,:,:3]-pose[0,:,:3]
            delta[:,:2]-=delta[:1,:2]
            seam=float(np.max(np.linalg.norm(delta,axis=1)))
            cut=dict(start=0,end=len(rows)-1,duration=(len(rows)-1)/60,
                idle_endpoint_max_cm=seam,warning=seam>4,warningReasons=['idle endpoint >4cm'] if seam>4 else [])
        else:cut=select(raw)
        cuts[clip['id']]=cut
        clips.append(dict(clip,label=clip['label']+' · drawn',cut=cut))
        capture_reports.append(dict(id=clip['id'],sha256=digest(path),samples=len(rows),
            speed_error_cm_s=speed_error,contracts=raw['contracts']))
    out.mkdir(parents=True,exist_ok=True)
    (source/'loop-cuts.json').write_text(json.dumps(cuts,indent=2))
    preview=ROOT/'Labs/MimicKitUEFN/omni-drawn-preview.json'
    retarget(clips,out/'drawn',source,preview_path=preview)
    sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
    from fit_motion_limits import sampled_coordinates,inflate,violation,MJCFCharModel
    model=MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    limits=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    checks=[]
    for clip in clips:
        frames=pickle.loads((out/'drawn'/(clip['id']+'.pkl')).read_bytes())['frames']
        rows=[]
        for joint in limits['joints']:
            values,_=sampled_coordinates(model,joint,frames,128)
            rows.append(dict(body=joint['body'],samples=len(values),
                outside=int(violation(values,joint).sum()),
                outside_margin=int(violation(inflate(values,1.05),joint).sum())))
        checks.append(dict(id=clip['id'],joints=rows))
    entries=assemble(out,original_paths)
    failures=[dict(id=c['id'],**j) for c in checks for j in c['joints'] if j['outside'] or j['outside_margin']]
    report=dict(status='candidate_for_review',clips=len(entries),unarmed=27,drawn=27,
        limits_passed=not failures,limit_failures=failures,checks=checks,captures=capture_reports,
        cut_warnings=[dict(id=c['id'],cut=c['cut']) for c in clips if c['cut'].get('warning')],
        notes='No PHAT expansion/clamping; active training unchanged. Equipment flag needs explicit policy integration before mixing both styles.')
    (out/'validation.json').write_text(json.dumps(report,indent=2))
    (out/'dataset.json').write_text(json.dumps(dict(status=report['status'],motions=entries),indent=2))
    for p,h in protected.items():assert digest(Path(p))==h,('Protected input changed',p)
    (out/'protected-inputs.json').write_text(json.dumps(protected,indent=2))
    print(json.dumps({k:report[k] for k in ('clips','unarmed','drawn','limits_passed','limit_failures','cut_warnings')},indent=2))


if __name__=='__main__':main()
