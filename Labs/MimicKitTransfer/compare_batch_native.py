"""Compare a saved four-world MJ replay to unchanged native Jolt feedback."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np
from scipy.spatial.transform import Rotation as R
from native_probe import Native,actor,observation,keys,offsets


def main(label,frictionless_self=False,no_limits=False,high_iterations=False,rig_iterations=None,tag=''):
    assert not tag or tag in ('point','baseline')
    folder=probe.OUT/'causal_transfer'
    # NpzFile decompresses an entire member on each lookup. Materialize once;
    # per-frame accesses must not unpack the complete recording repeatedly.
    with np.load(folder/(label+'.npz')) as saved:data={key:saved[key] for key in saved.files}
    for key in ('states','obs','actions','targets','dist'):
        assert np.isfinite(data[key]).all(), f'Reject invalid source {key}'
    for key in list(os.environ):
        if key.startswith('TRANSFER_'):del os.environ[key]
    # Same material isolates response-law differences from coefficient changes.
    os.environ['TRANSFER_TRAINING_CONTACT']='1'
    if frictionless_self: os.environ['TRANSFER_FRICTIONLESS_SELF']='1'
    if no_limits: os.environ['TRANSFER_NO_LIMITS']='1'
    if high_iterations: os.environ['TRANSFER_HIGH_ITERATIONS']='1'
    os.environ['TRANSFER_NO_CONTACT_OBSERVATIONS']='1'
    if rig_iterations:
        os.environ['TRANSFER_RIG_VELOCITY_STEPS']=str(rig_iterations[0])
        os.environ['TRANSFER_RIG_POSITION_STEPS']=str(rig_iterations[1])
    reports=[]; captures={};mapping_error=0.
    for world in range(data['states'].shape[1]):
        for tick in range(len(data['states'])-1):
            reconstructed=observation(data['states'][tick,world],data['obs'][tick+1,world,-5:])
            mapping_error=max(mapping_error,float(abs(reconstructed-data['obs'][tick+1,world]).max()))
        assert mapping_error<1e-3,('Observation mismatch',mapping_error)
        first_tick=0 if 'initial' in data else 1
        initial=data['initial'][world] if first_tick==0 else data['states'][0,world]
        if first_tick==0:
            reconstructed=observation(initial,data['obs'][0,world,-5:])
            mapping_error=max(mapping_error,float(abs(reconstructed-data['obs'][0,world]).max()))
            assert mapping_error<1e-3,('Reset observation mismatch',mapping_error)
        n=Native(initial);current=np.array(n.initial['bodies'])
        distances=[];deviations=[];impulses=[];history=[current.copy()];commands=[];timings=[];defects=[];anchors=[];loads=[]
        try:
            for tick in range(first_tick,len(data['states'])):
                command=actor(observation(current,data['obs'][tick,world,-5:]))
                response=n.request('step '+' '.join(map(str,command)))
                if 'physics_update_seconds' in response:timings.append(response['physics_update_seconds'])
                if 'motor_defect_nm' in response:defects.append(response['motor_defect_nm'])
                if 'anchor_error_m' in response:anchors.append(response['anchor_error_m'])
                loads.append(response['ground_vertical_impulse_ns'])
                current=np.array(response['bodies']);impulses.append(sum(response['ground_vertical_impulse_ns']))
                assert np.isfinite(current).all()
                history.append(current.copy());commands.append(command.copy())
                target=data['targets'][tick,world].copy();target[:,:2]+=current[0,:2]-target[0,:2]
                actual=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
                expected=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
                distances.append(float(np.linalg.norm(actual-expected,axis=1).max()))
                ref=data['states'][tick,world].copy();ref[:,:2]+=current[0,:2]-ref[0,:2]
                deviations.append(float(np.linalg.norm(current[:,:3]-ref[:,:3],axis=1).max()))
                if distances[-1]>.27:break
        finally:n.close()
        row=dict(phase=world/data['states'].shape[1],ticks=len(distances),target_failure=distances[-1]>.27,
                 max_target_distance_m=max(distances),mj_deviation_m=deviations[-1],
                 solved_ground_impulse_ns=sum(impulses),material='ground friction1/rest0; MJ self contact frictionless',
                 native_self_friction=0 if frictionless_self else 1,
                 initial_state='animation reset before physics' if first_tick==0 else 'after first MJ policy tick',
                 no_limits_diagnostic=no_limits,high_iterations_diagnostic=high_iterations,
                 observation_mapping_max_error=mapping_error)
        if rig_iterations:row['rig_iterations']=rig_iterations
        if timings:row['physics_update_ms_mean']=float(np.mean(timings)*1000)
        if defects:row['motor_defect_nm_max']=max(defects)
        if anchors:row['anchor_error_m_max']=max(anchors)
        row['foot_ground_impulse_fraction']=float(np.array(loads)[:,keys[-2:]].sum()/max(sum(impulses),1e-10))
        reports.append(row);print(json.dumps(row),flush=True)
        captures['world'+str(world)]=history;captures['actions'+str(world)]=commands
        captures['ground_impulses'+str(world)]=loads
    name=label+('_self0' if frictionless_self else '')+('_nolimits' if no_limits else '')+('_highiter' if high_iterations else '')+'_native'
    if rig_iterations:name+='_v'+str(rig_iterations[0])+'p'+str(rig_iterations[1])
    if tag:name+='_'+tag
    (folder/(name+'.json')).write_text(json.dumps(reports,indent=2),encoding='utf-8')
    np.savez_compressed(folder/(name+'.npz'),**captures)


if __name__=='__main__':main(sys.argv[1],'--frictionless-self' in sys.argv,'--no-limits' in sys.argv,'--high-iterations' in sys.argv)
