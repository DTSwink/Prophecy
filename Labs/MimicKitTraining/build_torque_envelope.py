"""Build an auditable per-axis peak-plus-margin envelope from motor tests."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    parser.add_argument('--include',type=Path,action='append',default=[]);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    reports=[args.directory/'report.json']+[p/'report.json' for p in args.include]
    inputs=[];rows=[];base=None
    for path in reports:
        raw=path.read_bytes();data=json.loads(raw)
        if base is None:base=data
        else:
            np.testing.assert_array_equal(data['base_caps_nm'],base['base_caps_nm'])
            np.testing.assert_array_equal(data['base_gains'],base['base_gains'])
        selected=[r for r in data['rows'] if r['profile']=='uncapped']
        if not selected or any(r['optimized']['numerical_error'] for r in selected):
            raise ValueError('Missing or invalid uncapped evidence: '+str(path))
        if any(max(r['optimized']['torque_cap_duty'])>0 for r in selected):
            raise ValueError('Diagnostic ceiling was active; demand is censored')
        rows.extend(selected)
        inputs.append(dict(path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),cases=len(selected)))
    names=[r['joint'] for r in json.loads((root/'Saved/MimicKitMotorAudit/command-envelope.json').read_text())['rows']]
    old=np.array(base['base_caps_nm']);torque=np.array([r['optimized']['torque_peak'] for r in rows])
    if not np.isfinite(torque).all() or np.any(torque<0):raise ValueError('Invalid measured torque')
    indices=torque.argmax(0);peak=torque.max(0)
    support=args.directory/'axis_probe.json'
    support_decisions=[]
    if support.exists():
        raw=support.read_bytes();probe=json.loads(raw);j=names.index(probe['axis'])
        accepted=[r for r in probe['probes'] if not r['numerical_error'] and r['old']>r['full']]
        if not accepted:raise ValueError('No supported torque increase for '+probe['axis'])
        chosen=max(accepted,key=lambda r:r['peak_nm'])
        match=next(i for i,r in enumerate(rows) if r['motion']==chosen['motion'] and r['phase']==chosen['phase'])
        assert abs(torque[match,j]-chosen['peak_nm'])<1e-6
        support_decisions.append(dict(axis=probe['axis'],unfiltered_peak_nm=float(peak[j]),selected=chosen))
        peak[j]=chosen['peak_nm'];indices[j]=match
        inputs.append(dict(path=str(support.resolve()),sha256=hashlib.sha256(raw).hexdigest()))
    new=np.where(peak>old,peak*1.05,old)
    axes=[]
    for j,name in enumerate(names):
        case=rows[int(indices[j])]
        axes.append(dict(axis=name,old_nm=float(old[j]),peak_nm=float(peak[j]),cap_nm=float(new[j]),
            changed=bool(new[j]>old[j]),motion=case['motion'],phase=case['phase']))
    result=dict(formula='if measured_peak > existing_cap: 1.05 * measured_peak; otherwise preserve existing_cap',margin=.05,
        interpretation='Torque used by the optimized reference-start next-tick commands; not a global minimum or sustained-running proof.',
        inputs=inputs,support_decisions=support_decisions,cases=len(rows),motions=len(set(r['motion'] for r in rows)),axes=axes,
        base_gains=base['base_gains'],base_caps_nm=old.tolist(),applied_caps_nm=new.tolist(),
        overrides_nm={r['axis']:r['cap_nm'] for r in axes if r['changed']},
        worst_next_tick_body_error_cm=max(r['optimized']['max_body_error_cm'] for r in rows))
    (args.directory/'envelope.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('axes','inputs','base_gains','base_caps_nm','applied_caps_nm')},indent=2))


if __name__=='__main__':main()
