"""Add review-only nearest-shoulder poses to the updated source viewer."""
import json, os, pickle, subprocess
import numpy as np
from scipy.spatial.transform import Rotation as R
from upperarm_pose_audit import ROOT, nearest, poses, MJCFCharModel
from current_phat import verify_current_phat
from fit_motion_limits import sampled_coordinates
from test_model import coords, violation


def main():
    folder = ROOT / 'Saved/MimicKitCrawl/updated-source-2e849ce9c900'
    data = json.loads((folder/'data.json').read_text())
    meta = verify_current_phat(ROOT/'Saved/MimicKitCrawl/package/assets/uefn')
    rig = json.loads((ROOT/'Saved/MimicKitUEFN/source-rig.json').read_text())
    model = MJCFCharModel('cpu')
    model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    frames = pickle.loads((folder/'projected_robot.pkl').read_bytes())['frames']
    limited_frames = frames.copy()
    source = np.array(data['variants'][0]['poses'])
    limited_source = source.copy()
    names = [b['name'] for b in data['variants'][0]['bodies']]
    probe = []; corrections = []

    def solve(q, joint):
        if not violation(coords(q[None]), joint)[0]:
            return q, 0.
        # Tiny interior tolerance survives the float32 Jolt/runtime conversion.
        inset = dict(joint, limits_rad=(np.array(joint['limits_rad'])-1e-5).tolist())
        return nearest(q, inset, thorough=True)

    for side in ('right', 'left'):
        joint = next(j for j in meta['joints'] if j['body']==side+'_upper_arm')
        constraint = next(j for j in rig['joints'] if j['name']==joint['source_joint'])
        ci = names.index(rig['bodies'][constraint['child']]['name'])
        pi = names.index(rig['bodies'][constraint['parent']]['name'])
        pf = R.from_quat(constraint['parent_frame']['rotation_xyzw'])
        cf = R.from_quat(constraint['child_frame']['rotation_xyzw'])
        descendants = {constraint['child']}
        while True:
            expanded = descendants | {j['child'] for j in rig['joints'] if j['parent'] in descendants}
            if expanded == descendants: break
            descendants = expanded
        indices = [names.index(rig['bodies'][i]['name']) for i in descendants]
        original = ((R.from_quat(source[:,pi,3:])*pf).inv()*R.from_quat(source[:,ci,3:])*cf).as_quat()[:,[3,0,1,2]]
        angles = []
        for f,q in enumerate(original):
            nq,angle = solve(q,joint); angles.append(float(np.rad2deg(angle)))
            old = R.from_quat(source[f,ci,3:])
            new = R.from_quat(source[f,pi,3:])*pf*R.from_quat(nq[[1,2,3,0]])*cf.inv()
            delta = new*old.inv()
            pivot = source[f,ci,:3] + old.apply(np.array(constraint['child_frame']['position_cm'])*.01)
            limited_source[f,indices,:3] = pivot + delta.apply(source[f,indices,:3]-pivot)
            limited_source[f,indices,3:] = (delta*R.from_quat(source[f,indices,3:])).as_quat()
        actual = ((R.from_quat(limited_source[:,pi,3:])*pf).inv()*R.from_quat(limited_source[:,ci,3:])*cf).as_quat()[:,[3,0,1,2]]
        for q in actual: probe.append([len(probe),*joint['modes'],*joint['limits_rad'],*q])
        corrections.append(dict(stage='authored',side=side,correction_deg=angles))

        qs = sampled_coordinates(model,joint,frames,1)[1]
        reference = R.from_quat(np.array(joint['reference_wxyz'])[[1,2,3,0]])
        start = 6+model.get_joint(model.get_body_names().index(joint['body'])).dof_idx
        angles = []
        for f,q in enumerate(qs):
            nq,angle = solve(q,joint); angles.append(float(np.rad2deg(angle)))
            limited_frames[f,start:start+3] = (reference.inv()*R.from_quat(nq[[1,2,3,0]])).as_rotvec()
        actual = sampled_coordinates(model,joint,limited_frames,1)[1]
        for q in actual: probe.append([len(probe),*joint['modes'],*joint['limits_rad'],*q])
        corrections.append(dict(stage='robot_projection',side=side,correction_deg=angles))

    robot = poses(model,limited_frames)
    original_robot = poses(model,frames)
    robot[:,:,:3] += np.array(data['variants'][1]['poses'])[:,:1,:3]-original_robot[:,:1,:3]
    np.savetxt(folder/'overlay-jolt-input.csv',probe,delimiter=',',header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='',fmt='%.12g')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(folder/'overlay-jolt-input.csv'),str(folder/'overlay-jolt-output.csv')],env=env,check=True,capture_output=True)
    check=np.genfromtxt(folder/'overlay-jolt-output.csv',names=True,delimiter=',')
    assert np.all(check['mask']==0), check[check['mask']!=0]
    data['variants'][0]['limited_poses']=limited_source.tolist()
    data['variants'][1]['limited_poses']=robot.tolist()
    data['limit_overlay']=dict(jolt_samples=len(probe),corrections=corrections,
        method='Nearest shoulder rotations within current PHAT swing/twist bounds; both shoulders corrected independently. All other local articulation held fixed. Hands follow the arms; no hand planting or physics simulation.')
    (folder/'data.json').write_text(json.dumps(data,separators=(',',':')))
    (folder/'overlay-verification.json').write_text(json.dumps(data['limit_overlay'],indent=2))
    print(f'Validated {len(probe)} shoulder poses in Jolt; source and robot overlay saved.')


if __name__=='__main__': main()
