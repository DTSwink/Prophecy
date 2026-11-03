"""Bounded, single-threaded wrist-damper probe; never changes production physics."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
import json, inspect, subprocess, hashlib
from pathlib import Path
import test_crawl_jolt_audit as base
import numpy as np

DEST=base.ROOT/'Saved/MimicKitSlowLoco/wrist-damping-20261103'
DEST.mkdir(exist_ok=True)

def build():
    src=(base.OUT/'fixture.cpp').read_text()
    src=src.replace('std::vector<Ref<SixDOFConstraint>> joints;',
                    'std::vector<Ref<SixDOFConstraint>> joints, dampers;')
    needle='physics.AddConstraint(joint);joints.push_back(joint);'
    assert src.count(needle)==1
    src=src.replace(needle,needle+'''
            // Separate passive viscous coupling, no pose spring or world drag.
            // Zero target velocity, k=0: torque opposes hand/forearm relative omega.
            const float c=std::getenv("WRIST_DAMPING")?std::atof(std::getenv("WRIST_DAMPING")):0.f;
            if(c>0 && (j.child==5 || j.child==8)) {
                SixDOFConstraintSettings ds;
                ds.mSpace=EConstraintSpace::LocalToBodyCOM;
                ds.mPosition1=settings.mPosition1;ds.mPosition2=settings.mPosition2;
                ds.mAxisX1=settings.mAxisX1;ds.mAxisY1=settings.mAxisY1;
                ds.mAxisX2=settings.mAxisX2;ds.mAxisY2=settings.mAxisY2;
                ds.mNumVelocityStepsOverride=100;ds.mNumPositionStepsOverride=20;
                for(int a=0;a<6;++a)ds.MakeFreeAxis(static_cast<SixDOFConstraintSettings::EAxis>(a));
                for(int a=3;a<6;++a)ds.mMotorSettings[a]=MotorSettings(ESpringMode::StiffnessAndDamping,0,c);
                Ref<SixDOFConstraint> damper=static_cast<SixDOFConstraint*>(ds.Create(*bodies[j.parent],*bodies[j.child]));
                for(int a=3;a<6;++a)damper->SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(a),EMotorState::PositionAndVelocity);
                damper->SetTargetAngularVelocityCS(Vec3::sZero());
                physics.AddConstraint(damper);dampers.push_back(damper);
            }
''')
    src=src.replace('for(auto& j:joints)physics.RemoveConstraint(j);',
                    'for(auto& d:dampers)physics.RemoveConstraint(d);for(auto& j:joints)physics.RemoveConstraint(j);')
    check=src[src.index('static int MotorSelfTest()'):src.index('static int RigContactSelfTest()')]
    check=check.replace('MotorSelfTest()', 'DamperSelfTest()')
    check=check.replace('joint->SetTargetAngularVelocityCS(PolicyVelocityCS(childFrame,Vec3(1,0,0)));',
        'joint->SetTargetAngularVelocityCS(Vec3::sZero());bi.SetAngularVelocity(bodies[1]->GetID(),childRotation*Vec3(1,0,0));')
    check=check.replace('(20.f/240)/(1+20.f/240)', '1.f/(1+20.f/240)')
    check=check.replace('motor_test_error_rad_s','damper_test_error_rad_s')
    src=src.replace('int main(int argc,char** argv)',check+'\nint main(int argc,char** argv)')
    src=src.replace('if(std::string(argv[1])=="--motor-test"){',
        'if(std::string(argv[1])=="--damper-test"){const int result=DamperSelfTest();UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;}\n    if(std::string(argv[1])=="--motor-test"){')
    (DEST/'fixture.cpp').write_text(src)
    (DEST/'jolt-rig-generated.h').write_bytes((base.OUT/'jolt-rig-generated.h').read_bytes())
    build=(base.OUT/'build.ps1').read_text().replace(str(base.OUT),str(DEST))
    (DEST/'build.ps1').write_text(build)
    subprocess.run(['pwsh','-NoProfile','-File',str(DEST/'build.ps1')],check=True,timeout=90)
    env=dict(os.environ);env['PATH']=str(base.ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env.get('PATH','')
    check=subprocess.run([str(DEST/'fixture.exe'),'--damper-test'],env=env,capture_output=True,text=True,check=True,timeout=10)
    (DEST/'damper-selftest.json').write_text(check.stdout)
    (DEST/'build.json').write_text(json.dumps({'fixture_sha256':hashlib.sha256(src.encode()).hexdigest(),
       'law':'tau = -c * (hand angular velocity - forearm angular velocity), isotropic, implicit Jolt constraint',
       'units':'N m s / rad','unchanged_motor_caps_nm':50,'no_training_changes':True},indent=2))

# Preserve the original fixture runner; redirect only this diagnostic's executable/log.
scope=dict(vars(base));scope['DEST']=DEST
code=inspect.getsource(base.Jolt).replace("OUT/'fixture.exe'","DEST/'fixture.exe'").replace("OUT/'stderr.log'","DEST/'stderr.log'")
exec(code,scope)
Jolt=scope['Jolt']

def stats(s):
    result=base.metrics(s)
    # Wrist/forearm relative rotation and hand translation, separately.
    rel=s[:,[5,8],10:13]-s[:,[4,7],10:13]
    result['wrist_relative_omega_rms_rad_s']=float(np.sqrt(np.mean(np.sum(rel**2,-1))))
    result['wrist_relative_omega_change_rms_rad_s']=float(np.sqrt(np.mean(np.sum(np.diff(rel,axis=0)**2,-1))))
    for label,children,parents in [('elbow',[4,7],[3,6]),('shoulder',[3,6],[1,1])]:
        w=s[:,children,10:13]-s[:,parents,10:13]
        result[label+'_omega_change_rms_rad_s']=float(np.sqrt(np.mean(np.sum(np.diff(w,axis=0)**2,-1))))
    result['min_pelvis_height_m']=float(s[:,0,2].min())
    return result

def run(pol,row,c):
    os.environ['WRIST_DAMPING']=str(c)
    original=base.states(row);phase=np.array(base.meta['replay_rows'][row]['frame_phase'])
    state=original[150].copy();sim=Jolt(state,True);history=[state.copy()];actions=[]
    try:
        for tick in range(80):
            action,_=pol(state,phase[150+tick,:2]);o=sim.request('step '+' '.join(map(str,action)))
            state=np.array(o['bodies']);assert np.isfinite(state).all()
            history.append(state);actions.append(action)
    finally:sim.close()
    states=np.array(history)
    np.savez_compressed(DEST/f'row{row}-c{c}.npz',states=states,actions=actions)
    result=dict(row=row,damping=c,**stats(states))
    print(json.dumps(result),flush=True)
    return result

def main():
    build();pol=base.Policy();results=[]
    if '--validate-extra' in __import__('sys').argv:
        results=json.loads((DEST/'results.json').read_text())
        results.append(run(pol,0,100))
        (DEST/'results.json').write_text(json.dumps(results,indent=2))
        return
    for c in (0,1,5,20):
        results.append(run(pol,0,c))
        (DEST/'results.json').write_text(json.dumps(results,indent=2))
    # Validate the strongest probe on three other identical recorded starts.
    for row in (2,5,7):
        for c in (0,20):
            results.append(run(pol,row,c))
            (DEST/'results.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
