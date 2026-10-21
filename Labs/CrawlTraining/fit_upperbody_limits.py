"""Fit current authored crawl/idle and their robot projections with 5% room."""
import argparse, json, os, pickle, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitCrawl/upperbody-limits-20261017'
sys.path.insert(0,str(ROOT/'Labs/RoboticCrawlAE'))
import prepare as ae
from current_phat import verify_current_phat, sha
from repair_references import wanted_poses
from fit_motion_limits import sampled_coordinates, fit, inflate
from test_model import coords, violation
from upperarm_pose_audit import quaternion


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify-saved',action='store_true');args=parser.parse_args()
    meta=verify_current_phat(ROOT/'Saved/MimicKitCrawl/package/assets/uefn')
    rig=json.loads((ROOT/'Saved/MimicKitCrawl/current-phat-analysis/live-rig.json').read_text())
    assert rig==json.loads((ROOT/'Saved/MimicKitUEFN/source-rig.json').read_text())
    model=ae.rt.MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    clips=[];fingerprints={}
    for item in json.loads((OUT/'imports.json').read_text()):
        assert sha(Path(item['path']))==item['sha256']
        fingerprints[item['path']]=item['sha256']
        path=OUT/(item['name']+'.bvh');motion=ae.read_motion(path)
        rot=ae.rt.WORLD@ae.rt.source_rotations(motion)@np.diag([1.,-1.,1.])
        wanted=wanted_poses(path,model,meta,rig);dof,actual=ae.rt.project(model,wanted)
        frames=np.concatenate((wanted[:,0,:3,3],R.from_matrix(actual[:,0]).as_rotvec(),dof),-1).astype(np.float32)
        clips.append((item['name'],motion,rot,frames))
        fingerprints[str(path)]=sha(path)
    idlepath=ROOT/'Saved/MimicKitCrawl/package/motions/crawl_idle.pkl'
    idle=pickle.loads(idlepath.read_bytes())['frames'];fingerprints[str(idlepath)]=sha(idlepath)
    rows=[];probe=[];dense_total=0
    for src in rig['joints']:
        child=rig['bodies'][src['child']]['name']
        if child.startswith(('thigh','calf','foot')):continue
        parent=rig['bodies'][src['parent']]['name']
        joint=dict(body=child,source_body=child,source_joint=src['name'],kind='ball',modes=src['angular_modes_twist_swing2_swing1'],limits_rad=np.deg2rad(src['angular_limits_deg_twist_swing2_swing1']).tolist())
        retained=next((j for j in meta['joints'] if j['source_joint']==src['name']),None)
        def samples(subdivisions):
            result=[]
            for label,motion,rot,frames in clips:
                pr=rot[:,motion.names.index(parent)]@R.from_quat(src['parent_frame']['rotation_xyzw']).as_matrix()
                cr=rot[:,motion.names.index(child)]@R.from_quat(src['child_frame']['rotation_xyzw']).as_matrix()
                local=R.from_matrix(pr.transpose(0,2,1)@cr)
                q=Slerp(np.arange(motion.count),local)(np.linspace(0,motion.count-1,(motion.count-1)*subdivisions+1)).as_quat()[:,[3,0,1,2]]
                result.append((label+'_authored',coords(q)))
                if retained:result.append((label+'_robot',sampled_coordinates(model,retained,frames,subdivisions)[0]))
            if retained:result.append(('idle_contact_reference',sampled_coordinates(model,retained,idle,subdivisions)[0]))
            # Existing diagnostic convention removes only sub-0.001-degree
            # export residue on genuinely locked axes, never authored motion.
            for axis,mode in enumerate(joint['modes']):
                if mode==2 and max(np.max(abs(a[:,axis])) for _,a in result)<1e-5:
                    for _,a in result:a[:,axis]=0.
            return result
        values=samples(16);v=np.concatenate([a for _,a in values])
        if not violation(inflate(v,1.05),joint).any():
            row=dict(source_joint=src['name'],source_body=child,body=child,
                old_modes=joint['modes'],new_modes=joint['modes'],
                old_degrees=src['angular_limits_deg_twist_swing2_swing1'],new_degrees=src['angular_limits_deg_twist_swing2_swing1'],
                changed=False,outside_before=0,outside_after=0,outside_with_margin=0,samples=len(v))
        else:
            assert not args.verify_saved, ('Saved profile lacks 5% room',child)
            row=fit(joint,v,1.05)
        fitted=dict(joint,modes=row['new_modes'],limits_rad=np.deg2rad(row['new_degrees']).tolist())
        dense=samples(128)
        for label,a in dense:
            assert not violation(inflate(a,1.05),fitted).any(),(child,label)
        row['dense_verified_samples']=sum(len(a) for _,a in dense);dense_total+=row['dense_verified_samples']
        row['stages']=[dict(name=label,samples=len(a),outside_before=int(violation(a,joint).sum())) for label,a in values]
        for _,a in values:
            for vals in (a,inflate(a,1.05)):
                for value in vals:
                    probe.append([len(probe),*fitted['modes'],*fitted['limits_rad'],*quaternion(value)])
        rows.append(row)
        if row['changed']:print(child,row['old_degrees'],'->',row['new_degrees'],'modes',row['old_modes'],'->',row['new_modes'],flush=True)
    prefix='saved' if args.verify_saved else 'plan'
    np.savetxt(OUT/(prefix+'-jolt-input.csv'),probe,delimiter=',',header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='',fmt='%.12g')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(OUT/(prefix+'-jolt-input.csv')),str(OUT/(prefix+'-jolt-output.csv'))],env=env,check=True,capture_output=True)
    check=np.genfromtxt(OUT/(prefix+'-jolt-output.csv'),names=True,delimiter=',');assert not np.any(check['mask']),check[check['mask']!=0][:5]
    doc=dict(margin_factor=1.05,source_files=rig['source_files'],limits_sha256=sha(ROOT/'Labs/MimicKitUEFN/limits.json'),motion_sha256=fingerprints,
        joints=rows,jolt_samples=len(probe),dense_samples=dense_total,excluded=['thigh_l','thigh_r','calf_l','calf_r','foot_l','foot_r'],
        method='Current authored crawl/idle plus pure robot projections and existing contact-corrected idle. No obsolete cleaned crawl. 1.05x twist and swing-angle magnitude; coupled ellipse; never shrink; round changed bounds outward to 0.01 degree. Fit16, verify128 subdivisions.')
    (OUT/('limit-verification.json' if args.verify_saved else 'limit-plan.json')).write_text(json.dumps(doc,indent=2))
    print('Verified',dense_total,'dense samples and',len(probe),'Jolt reference/margin cases.')


if __name__=='__main__':main()
