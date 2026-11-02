"""Precompute each walk's maximum of the two foot collider support heights."""
import json,hashlib,zipfile,sys
from pathlib import Path
import torch,yaml
import deploy_locomotion_branch as d
from walking_airborne import foot_box_bottoms
from walking_height import height_excess,patch_source


def main():
    from prepare_perturbed_com2 import MJCFCharModel,MotionLib,mp_util
    torch.set_num_threads(1);mp_util.init(0,1,'cpu',6794)
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text());source=d.OUT/'walking-height-reference-source'
    with zipfile.ZipFile(plan['source']['local']) as z:
        for name in z.namelist():
            if name.startswith(('assets/uefn/','prepared/','motions/')):
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
        patch_source(z.read('pipeline/perturbed_omni.py').decode())
    for p in (source/'prepared').glob('*.yaml'):
        p.write_text(p.read_text().replace('/workspace/mimickit_trial',source.as_posix()))
    cfg=yaml.safe_load((source/'prepared/env_config.yaml').read_text())
    model=MJCFCharModel('cpu');model.load(cfg['char_file']);lib=MotionLib(cfg['motion_file'],model,'cpu')
    boxes=cfg['perturbed_motion']['walking_foot_boxes'];ids=[model.get_body_names().index(b['bone']) for b in boxes]
    centers=torch.tensor([b['center'] for b in boxes]);axes=torch.tensor([b['half_axes'] for b in boxes]);rows={}
    for i in range(lib.get_num_motions()):
        path=Path(lib.get_motion_file(i))
        if '_Walk_' not in path.stem:continue
        duration=float(lib.get_motion_length(i));times=torch.arange(0,duration,1/480.)
        root,rot,_,_,joints,_=lib.calc_motion_frame(torch.full(times.shape,i,dtype=torch.long),times)
        pos,rotation=model.forward_kinematics(root,rot,joints)
        bottom=foot_box_bottoms(pos[:,ids],rotation[:,ids],centers,axes)
        high=bottom.amax(-1);index=int(high.argmax());limit=float(high[index])
        assert limit>=0 and torch.isfinite(high).all()
        torch.testing.assert_close(height_excess(bottom,torch.full_like(high,limit),torch.ones_like(high,dtype=torch.bool)),torch.zeros_like(high))
        rows[path.stem]=dict(max_height_m=limit,peak_time_seconds=float(times[index]),per_foot_max_m=bottom.amax(0).tolist(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    # Independent threshold, higher-vs-lower-foot, and gait-mask semantics.
    feet=torch.tensor([[0.,.05],[0.,.10],[0.,.12],[.12,0.],[.2,.3]])
    torch.testing.assert_close(height_excess(feet,torch.full((5,),.1),torch.tensor([1,1,1,1,0],dtype=torch.bool)),torch.tensor([0.,0.,.0004,.0004,0.]))
    report=dict(sample_hz=480,measurement='Maximum over the whole reference clip of max(right foot lowest collider Z,left foot lowest collider Z); world Z, same actual foot boxes as runtime',motions=rows,
        source_sha256=plan['source']['sha256'],char_sha256=hashlib.sha256(Path(cfg['char_file']).read_bytes()).hexdigest(),reference_zero_penalty_verified=True)
    d.save('walking-height-reference',report);d.save('walking-height-before-plan',plan);d.save('walking-height-old-launch',json.loads((d.OUT/'launch.json').read_text()))
    active=json.loads((d.OUT/'active_run.json').read_text());d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod']))
    print(json.dumps(dict(motions=len(rows),min_cm=min(x['max_height_m'] for x in rows.values())*100,max_cm=max(x['max_height_m'] for x in rows.values())*100,verified=True)),flush=True)


if __name__=='__main__':main()
