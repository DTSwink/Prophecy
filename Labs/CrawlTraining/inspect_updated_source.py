"""Read a freshly converted source crawl; audit authored and reduced shoulders separately."""
import json, os, pickle, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Labs/RoboticCrawlAE'))
import prepare as ae
from current_phat import verify_current_phat, sha
from fit_motion_limits import sampled_coordinates, fit
from test_model import coords, violation


def main():
    folder=Path(json.loads((ROOT/'Saved/MimicKitCrawl/updated-source.json').read_text())['folder'])
    meta=verify_current_phat(ROOT/'Saved/MimicKitCrawl/package/assets/uefn')
    rig=json.loads((ROOT/'Saved/MimicKitCrawl/current-phat-analysis/live-rig.json').read_text())
    assert rig==json.loads((ROOT/'Saved/MimicKitUEFN/source-rig.json').read_text())
    motion=ae.read_motion(folder/'crawl.bvh');rt=ae.rt
    rotations=rt.WORLD@rt.source_rotations(motion)@np.diag([1.,-1.,1.])
    positions=motion.positions@rt.WORLD.T
    model=rt.MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    import repair_references as rr
    wanted=rr.wanted_poses(folder/'crawl.bvh',model,meta,rig)
    dof,actual=rt.project(model,wanted)
    frames=np.concatenate((wanted[:,0,:3,3],R.from_matrix(actual[:,0]).as_rotvec(),dof),-1).astype(np.float32)
    (folder/'projected_robot.pkl').write_bytes(pickle.dumps(dict(frames=frames,fps=motion.fps,loop_mode=0)))
    report=[];probe=[]
    for side in ('right','left'):
        j=next(j for j in meta['joints'] if j['body']==side+'_upper_arm')
        source=next(s for s in rig['joints'] if s['name']==j['source_joint'])
        parent=rig['bodies'][source['parent']]['name'];child=rig['bodies'][source['child']]['name']
        pr=rotations[:,motion.names.index(parent)]@R.from_quat(source['parent_frame']['rotation_xyzw']).as_matrix()
        cr=rotations[:,motion.names.index(child)]@R.from_quat(source['child_frame']['rotation_xyzw']).as_matrix()
        local=R.from_matrix(pr.transpose(0,2,1)@cr)
        q=Slerp(np.arange(motion.count),local)(np.linspace(0,motion.count-1,(motion.count-1)*8+1)).as_quat()[:,[3,0,1,2]]
        for stage,values,quats in [('authored',coords(q),q),('robot_projection',*sampled_coordinates(model,j,frames,8))]:
            v=values;bad=violation(v,j)
            peak=int(np.argmax(abs(v[:,0])));plan=fit(j,v,margin=1.)
            start=len(probe)
            for quat in quats:probe.append([len(probe),*j['modes'],*j['limits_rad'],*quat])
            report.append(dict(side=side,stage=stage,samples=len(v),outside=int(bad.sum()),outside_percent=float(bad.mean()*100),
                limits_deg=np.rad2deg(j['limits_rad']).tolist(),twist_range_deg=np.rad2deg([v[:,0].min(),v[:,0].max()]).tolist(),
                max_abs_coordinates_deg=np.rad2deg(np.r_[abs(v[:,0]).max(),2*np.arcsin(np.clip(abs(v[:,1:]).max(0),0,1))]).tolist(),
                required_containing_limits_deg=plan['new_degrees'],peak_twist_frame=peak/8,peak_twist_seconds=peak/(8*motion.fps),probe_begin=start))
    np.savetxt(folder/'jolt-input.csv',probe,delimiter=',',header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='',fmt='%.12g')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(folder/'jolt-input.csv'),str(folder/'jolt-output.csv')],env=env,check=True,capture_output=True)
    result=np.genfromtxt(folder/'jolt-output.csv',names=True,delimiter=',')
    for row in report:
        count=int(np.count_nonzero(result['mask'][row['probe_begin']:row['probe_begin']+row['samples']]))
        assert count==row['outside'];print(json.dumps(row),flush=True)
    conversion=json.loads((folder/'fbx-conversion.json').read_text())
    original=Path(conversion['original_source']);assert sha(original)==conversion['source_fbx_sha256']
    doc=dict(source=str(original),source_sha256=sha(original),source_modified=conversion['modified_at'],frames=motion.count,fps=motion.fps,
        current_phat_sha256=sha(ROOT/'Saved/MimicKitCrawl/package/assets/uefn/limits.json'),jolt_samples=len(probe),rows=report,
        method='No IK, contact cleanup, loop closure or LAFAN retarget. Authored shoulder measured relative to actual clavicle PHAT connector; robot projection measured relative to its rigid torso. 240 Hz quaternion interpolation. Required limits contain this clip only with no extra safety margin.',
        display='Reflect complete posed geometry on world Y, same handedness convention as corrected replayer; labels and stored motion data unchanged.')
    (folder/'report.json').write_text(json.dumps(doc,indent=2))
    # Display the actual source PHAT bodies, not the reduced rig, by default.
    bodies=[];sourceposes=[]
    for body in rig['bodies']:
        i=motion.names.index(body['name']);shapes=[]
        for s in body['shapes']:
            size=[s['radius_cm']*.01,s['cylinder_length_cm']*.005] if s['kind']=='capsule' else ([s['radius_cm']*.01] if s['kind']=='sphere' else (np.array(s['half_extent_cm'])*.01).tolist())
            q=s['local']['rotation_xyzw'];shapes.append(dict(type=s['kind'],size=size,pos=(np.array(s['local']['position_cm'])*.01).tolist(),quat=[q[3],*q[:3]]))
        bodies.append(dict(name=body['name'],shapes=shapes))
        sourceposes.append(np.concatenate((positions[:,i],R.from_matrix(rotations[:,i]).as_quat()),-1))
    sourceposes=np.stack(sourceposes,1)
    pp,qq=ae.fk(model,frames);robotposes=np.concatenate((pp,qq),-1)
    # Center both using the same authored pelvis position, preserving relative placement.
    origin=positions[:,motion.names.index('pelvis'),:2].copy()
    sourceposes[:,:,:2]-=origin[:,None,:];robotposes[:,:,:2]-=origin[:,None,:]
    robotbodies=json.loads((ROOT/'Saved/MimicKitCrawl/upperarm-pose-audit/data.json').read_text())['bodies']
    viewer=dict(report=doc,variants=[dict(label='Updated FBX · authored skeleton',bodies=bodies,poses=sourceposes.round(7).tolist()),
        dict(label='Robot projection · no cleanup',bodies=robotbodies,poses=robotposes.round(7).tolist())])
    (folder/'data.json').write_text(json.dumps(viewer,separators=(',',':')))

if __name__=='__main__':main()
