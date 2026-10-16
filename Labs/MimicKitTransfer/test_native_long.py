"""Continuous native running with the original motion clock, never episode resets."""
import argparse,os,json,hashlib,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe,native_probe
import numpy as np,torch,yaml
from scipy.spatial.transform import Rotation as R
from anim.mjcf_char_model import MJCFCharModel
from anim.motion_lib import MotionLib
from omni_walk import phase_at
from native_probe import Native,actor,observation,keys,offsets


def extended_floor_fixture():
    """Only enlarge the finite diagnostic floor; preserve the accepted DLL/rig."""
    source=probe.OUT/'point-contact/profile'
    destination=source/'long-floor';destination.mkdir(exist_ok=True)
    text=(source/'fixture.cpp').read_text()
    anchor='new BoxShape(Vec3(100,100,.1f),0)'
    assert text.count(anchor)==1
    text=text.replace(anchor,'new BoxShape(Vec3(1000,1000,.1f),0)')
    (destination/'fixture.cpp').write_text(text)
    script=(source/'build.ps1').read_text()
    for suffix in ('cpp','obj','exe'):
        script=script.replace(str(source/('fixture.'+suffix)),str(destination/('fixture.'+suffix)))
    (destination/'build.ps1').write_text(script)
    subprocess.run(['pwsh','-NoProfile','-File',str(destination/'build.ps1')],check=True)
    dll='ProphecyJolt_5_6_Development.dll'
    shutil.copy2(source/dll,destination/dll)
    receipt=dict(only_change='floor half extent 100m -> 1000m',
        dll_sha256=hashlib.sha256((destination/dll).read_bytes()).hexdigest(),
        original_source_sha256=hashlib.sha256((source/'fixture.cpp').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256((destination/'fixture.cpp').read_bytes()).hexdigest())
    (destination/'build.json').write_text(json.dumps(receipt,indent=2))
    return destination/'fixture.exe'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worlds',type=int,nargs='+',default=[0,4,8,12])
    parser.add_argument('--label',default='long_run4013_native40_floor1000')
    parser.add_argument('--reuse-fixture',action='store_true')
    parser.add_argument('--onnx',type=Path,help='Verify exported inference inside the same physical loop')
    args=parser.parse_args()
    assert len(set(args.worlds))==len(args.worlds) and all(0<=w<16 for w in args.worlds)
    directory=ROOT/'Saved/MimicKitLocal/runs/2026-10-16_02-00_transfer_finetune_512'
    out=probe.OUT/'causal_transfer'
    cfg=yaml.safe_load((directory/'env_config.yaml').read_text())
    char=MJCFCharModel('cpu');char.load(cfg['char_file'])
    probe.mp_util.init(0,1,'cpu',6732)
    lib=MotionLib(cfg['motion_file'],char,'cpu')
    duration=float(lib.get_motion_length(torch.zeros(1,dtype=torch.long))[0])
    manifest=json.loads(Path(cfg['omni_manifest']).read_text())
    row=next(r for r in manifest['motions'] if r['id']==Path(cfg['motion_file']).stem)
    initial=np.load(out/'local_finetune4013_phases16.npz')['initial']
    native_probe.load_actor(directory/'model.pt')
    inference=actor
    if args.onnx:
        import onnxruntime as ort
        metadata=json.loads(args.onnx.with_suffix('.json').read_text())
        assert metadata['checkpoint_model_sha256']==hashlib.sha256((directory/'model.pt').read_bytes()).hexdigest()
        assert metadata['onnx_sha256']==hashlib.sha256(args.onnx.read_bytes()).hexdigest()
        options=ort.SessionOptions();options.intra_op_num_threads=options.inter_op_num_threads=1
        session=ort.InferenceSession(str(args.onnx),sess_options=options,providers=['CPUExecutionProvider'])
        inference=lambda obs:session.run(['joint_velocity_rad_s'],{'observations':np.asarray(obs,np.float32)[None]})[0][0]
    label=args.label
    assert not (out/(label+'.npz')).exists(),'Preserve previous evaluation'
    native_probe.fixture_path=(probe.OUT/'point-contact/profile/long-floor/fixture.exe'
        if args.reuse_fixture else extended_floor_fixture())
    assert native_probe.fixture_path.is_file()
    for key in list(os.environ):
        if key.startswith('TRANSFER_'):del os.environ[key]
    os.environ.update(TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1',
        TRANSFER_RIG_VELOCITY_STEPS='40',TRANSFER_RIG_POSITION_STEPS='8',TRANSFER_NO_CONTACT_OBSERVATIONS='1')
    ticks=1800;clock=np.zeros(ticks+1,np.float32)
    for t in range(ticks):clock[t+1]=clock[t]+np.float32(1/30)
    reports=[];captures={}
    for world in args.worlds:
        times=torch.from_numpy(clock+np.float32(world/16*duration))
        ids=torch.zeros(ticks+1,dtype=torch.long)
        rp,rq,_,_,jq,_=lib.calc_motion_frame(ids,times)
        pos,rot=char.forward_kinematics(rp,rq,jq)
        targets=torch.cat([pos,rot],-1).numpy()
        phase=phase_at(times,torch.full_like(times,duration),torch.full_like(times,row['phase_offset'])).numpy()
        commands=np.c_[np.full(ticks+1,row['gait']),np.tile(row['direction'],(ticks+1,1)),phase]
        n=Native(initial[world]);state=np.array(n.initial['bodies']);history=[state];distances=[];ground=[]
        try:
            for tick in range(ticks):
                action=inference(observation(state,commands[tick]))
                result=n.request('step '+' '.join(map(str,action)))
                state=np.array(result['bodies']);assert np.isfinite(state).all()
                assert np.abs(state[:,:2]).max()<999,'Diagnostic floor boundary reached'
                history.append(state);ground.append(result['ground_vertical_impulse_ns'])
                target=targets[tick+1].copy();target[:,:2]+=state[0,:2]-target[0,:2]
                actual=state[keys,:3]+R.from_quat(state[keys,3:7]).apply(offsets)
                expected=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
                distances.append(float(np.linalg.norm(actual-expected,axis=1).max()))
                if distances[-1]>.27:break
        finally:n.close()
        ground=np.array(ground)
        report=dict(start_phase=world/16,ticks=len(distances),seconds=len(distances)/30,
            resets=0,target_failure=distances[-1]>.27,max_target_m=max(distances),
            foot_ground_fraction=float(ground[:,keys[-2:]].sum()/ground.sum()),ground_impulse_ns=float(ground.sum()),
            floor_half_extent_m=1000,root_initial=history[0][0,:3].tolist(),root_final=history[-1][0,:3].tolist(),
            inference='onnxruntime_cpu' if args.onnx else 'pytorch_cpu')
        reports.append(report);captures['world'+str(world)]=history
        print(json.dumps(report),flush=True)
    (out/(label+'.json')).write_text(json.dumps(reports,indent=2))
    np.savez_compressed(out/(label+'.npz'),**captures)


if __name__=='__main__':main()
