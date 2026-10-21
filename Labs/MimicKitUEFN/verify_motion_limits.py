"""Verify saved PHAT-derived limits against the unchanged accepted references."""
import hashlib
import json
import os
import pickle
import subprocess
import argparse
from pathlib import Path
import numpy as np
from fit_motion_limits import ROOT, HERE, sampled_coordinates, inflate, violation, MJCFCharModel


def quaternions(v):
    t=v[:,0]/2;y=v[:,1];z=v[:,2]
    s=np.sqrt(np.maximum(0,1-y*y-z*z));c=np.cos(t);a=np.sin(t)
    return np.column_stack((s*c,s*a,y*c+z*a,z*c-y*a))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backup-name',default='before-omni-limits')
    parser.add_argument('--idle',action='store_true',help='Verify the added idle against unchanged current limits')
    parser.add_argument('--equipment',action='store_true')
    args=parser.parse_args();assert args.backup_name in ('before-omni-limits','before-wrist-limits','before-equipment-limits')
    out=ROOT/'Saved/MimicKitUEFN';backup=out/args.backup_name
    if args.idle:
        source=out/'idle/retarget/M_Neutral_Stand_Idle_Loop.pkl'
        frames=pickle.loads(source.read_bytes())['frames']
        meta=json.loads((HERE/'limits.json').read_text())
        model=MJCFCharModel('cpu');model.load(str(HERE/'humanoid_uefn.xml'))
        rows=[]
        for joint in meta['joints']:
            values,_=sampled_coordinates(model,joint,frames,128)
            rows.append(dict(body=joint['body'],samples=len(values),outside=int(violation(values,joint).sum()),
                outside_margin=int(violation(inflate(values,1.05),joint).sum())))
        report=dict(passed=not any(r['outside'] or r['outside_margin'] for r in rows),
            motion_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            limits_sha256=hashlib.sha256((HERE/'limits.json').read_bytes()).hexdigest(),
            subdivisions=128,margin_factor=1.05,rows=rows)
        (out/'idle/limits-verification.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report));assert report['passed'],'Idle exceeds current PHAT limits'
        return
    plan=json.loads((out/('equipment/limit-plan.json' if args.equipment else 'omni-limit-plan.json')).read_text())
    before=json.loads((backup/'limits.json').read_text());after=json.loads((HERE/'limits.json').read_text())
    for key in ('geometry','groups','body_frames','source_body_frames','source_parents','parents','mass_kg','collision_exclusions'):
        assert before[key]==after[key],key
    oldxml=(backup/'humanoid_uefn.xml').read_bytes()
    # Equipment references can require hinge expansion. Only their range
    # attributes may change in either generated model.
    import xml.etree.ElementTree as ET
    for filename in ('humanoid_uefn.xml','humanoid_uefn_physics.xml'):
        a=ET.fromstring((backup/filename).read_bytes());b=ET.fromstring((HERE/filename).read_bytes())
        for j,p in zip(after['joints'],plan['joints']):
            if j['kind']=='hinge' and p['changed']:
                x=a.find(f".//joint[@name='{j['name']}']");y=b.find(f".//joint[@name='{j['name']}']")
                np.testing.assert_allclose([float(v) for v in y.attrib['range'].split()],j['range_rad'],atol=1e-8)
                x.set('range',y.attrib['range'])
        assert ET.tostring(a)==ET.tostring(b),filename
    assert (backup/'physics.json').read_bytes()!=(HERE/'physics.json').read_bytes() # New source fingerprint.
    oldphysics=json.loads((backup/'physics.json').read_text());newphysics=json.loads((HERE/'physics.json').read_text())
    assert oldphysics['bodies']==newphysics['bodies'] and oldphysics['cancel_gyroscopic']==newphysics['cancel_gyroscopic']
    assert (backup/'historical-rig.json').read_bytes()==(ROOT/'Saved/Robotics/rig.json').read_bytes()
    for name,info in after['source_files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==info['sha256']
    model=MJCFCharModel('cpu');model.load(str(HERE/'humanoid_uefn.xml'))
    clips=[]
    for name,digest in plan['motion_sha256'].items():
        content=(Path(name) if args.equipment else out/'omni'/name).read_bytes();assert hashlib.sha256(content).hexdigest()==digest,name
        clips.append(pickle.loads(content)['frames'])
    rows=[];count=0
    for j,p in zip(after['joints'],plan['joints']):
        assert j['modes']==p['new_modes']
        np.testing.assert_allclose(np.rad2deg(j['limits_rad']),p['new_degrees'],atol=1e-4,rtol=0)
        dense=np.concatenate([sampled_coordinates(model,j,f,128)[0] for f in clips])
        assert not violation(inflate(dense,1.05),j).any(),j['body']
        count+=len(dense)
        v=np.concatenate([sampled_coordinates(model,j,f,1)[0] for f in clips])
        for q in quaternions(np.concatenate((v,inflate(v,1.05)))):
            rows.append([len(rows),*j['modes'],*j['limits_rad'],*q])
    prefix=out/'equipment' if args.equipment else out
    src=prefix/'omni-limits-jolt-input.csv';dst=prefix/'omni-limits-jolt-output.csv'
    np.savetxt(src,rows,delimiter=',',fmt=['%d']*4+['%.12g']*7,header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(src),str(dst)],env=env,check=True,capture_output=True)
    result=np.genfromtxt(dst,delimiter=',',names=True)
    assert np.all(result['mask']==0),'Exact project Jolt rejected a reference or its margin'
    report=dict(passed=True,clips=len(clips),changed_constraints=sum(r['changed'] for r in plan['joints']),
                dense_joint_samples=count,jolt_reference_and_margin_samples=len(rows),outside_limits=0,angular_margin=1.05,
                geometry_mass_inertia_damping_unchanged=True,motion_files_bit_identical=True,historical_export_preserved=True,
                source_files=after['source_files'])
    (out/('equipment/limit-verification.json' if args.equipment else 'omni-limit-verification.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
