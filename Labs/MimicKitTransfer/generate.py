"""Build a 15-body diagnostic fixture from the checkpoint's frozen assets."""
from pathlib import Path
import json, xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitTransfer'
ASSET=OUT/'source/assets/uefn'
meta=json.loads((ASSET/'limits.json').read_text());physics=json.loads((ASSET/'physics.json').read_text())
rig=json.loads((ROOT/'Saved/MimicKitUEFN/source-rig.json').read_text())
native_bodies={b['name']:b for b in rig['bodies']}
nodes=list(ET.parse(ASSET/'humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
names=[b.attrib['name'] for b in nodes]
def vals(s):return np.fromstring(s,sep=' ')
def num(x):return f'{float(x):.12e}f'
def v(x):return 'Vec3('+','.join(map(num,x))+')'
def q(x):return 'Quat('+','.join(map(num,x))+')'
def xmlq(node):return np.roll(vals(node.attrib.get('quat','1 0 0 0')),-1)
lines=['// Generated from the frozen checkpoint source. SI units, training body frames.',
       'static const char* kRigHash="'+meta['source_sha256']+'";',
       'static const char* kControllerHash="velocity-soft-motors-diagnostic";',
       'static const int kActionCount=34;','static const ShapeSpec kShapes[]={']
shape_ranges=[];count=0
for node in nodes:
    start=count
    for g in node.findall('geom'):
        size=np.zeros(3);a=vals(g.attrib['size']);size[:len(a)]=a
        lines.append('{'+str({'capsule':0,'box':1,'sphere':2}[g.attrib['type']])+','+v(size)+','+v(vals(g.attrib.get('pos','0 0 0')))+','+q(xmlq(g))+'},');count+=1
    shape_ranges.append((start,count))
lines+=['};','static const BodySpec kBodies[]={']
for node,(start,end) in zip(nodes,shape_ranges):
    b=node.find('inertial');name=node.attrib['name'];p=physics['bodies'][name]
    # Native damping is replaced by the same aggregate physical drag as training.
    members=[native_bodies[n] for n in meta['groups'][name]['colliders_from']]
    caps=[min(m['max_angular_velocity_rad_s'] for m in members),min(m['max_linear_velocity_cm_s']/100 for m in members)]
    lines.append('{"'+name+'",'+f'{start},{end},'+v(vals(b.attrib['pos']))+','+q(xmlq(b))+','+v(vals(b.attrib['diaginertia']))+','+num(b.attrib['mass'])+',0,0,'+','.join(map(num,caps))+'},')
lines+=['};','static const JointSpec kJoints[]={'];action=0
for node in nodes[1:]:
    name=node.attrib['name'];j=next(x for x in meta['joints'] if x['body']==name)
    parent=j['parent'];frame=meta['body_frames'][parent];frameq=R.from_quat(frame['quaternion'])
    source=j['source_parent_frame'];parentpos=frameq.inv().apply(np.array(source['position'])-frame['position']);parentrot=(frameq.inv()*R.from_quat(source['quaternion'])).as_quat()
    # Child constraint axes in this retargeted model are its body axes.
    # Hinge XML axes were reduced in exactly this PHAT frame convention.
    modes=j['modes'];ids=[-1]*3
    if j['kind']=='ball':ids=list(range(action,action+3));action+=3
    else:ids[2]=action;action+=1
    motor=node.find('joint');gain=float(motor.attrib['damping']);limit=max(abs(vals(motor.attrib['actuatorfrcrange'])))
    lines.append('{'+f'{names.index(parent)},{names.index(name)},'+v(parentpos)+','+q(parentrot)+','+v([0,0,0])+','+q([0,0,0,1])+',{' +','.join(map(str,modes))+'},'+v(j['limits_rad'])+',{' +','.join(map(str,ids))+'},'+v([0,gain,limit])+'},')
assert action==34
lines+=['};','static const int kDisabledPairs[][2]={']
for a,b in meta['collision_exclusions']:lines.append('{'+f'{names.index(a)},{names.index(b)}'+'},')
lines+=['};','static const DragSpec kDrag[]={']
for name in names:
    p=physics['bodies'][name]
    # Mat44 columns; symmetric drag tensor.
    mat=np.array(p['drag_second'])
    lines.append('{'+num(p['drag_mass'])+','+v(p['drag_first'])+',Mat44('+','.join('Vec4('+','.join(map(num,[*mat[:,i],0]))+')' for i in range(3))+',Vec4(0,0,0,1))},')
lines+=['};'];(OUT/'jolt-rig-generated.h').write_text('\n'.join(lines))
cpp=(ROOT/'Labs/PhysicalRecoveryLab/jolt_rig_fixture.cpp').read_text()
cpp=cpp.replace('struct BodySpec {const char* name;int kind;Vec3 size,shapePosition;Quat shapeRotation;',
'''struct ShapeSpec {int kind;Vec3 size,position;Quat rotation;};
struct DragSpec {float coefficient;Vec3 first;Mat44 second;};
struct BodySpec {const char* name;int start,end;''')
begin=cpp.index('            RefConst<Shape> inner;');end=cpp.index('            const auto result=',begin)
cpp=cpp[:begin]+'''            StaticCompoundShapeSettings compound;
            for(int si=b.start;si<b.end;++si){
                const auto& s=kShapes[si];RefConst<Shape> inner;Quat rotation=s.rotation;
                if(s.kind==0){inner=new CapsuleShape(s.size.GetY(),s.size.GetX());rotation=rotation*Quat::sRotation(Vec3::sAxisX(),.5f*JPH_PI);}
                else if(s.kind==1)inner=new BoxShape(s.size,0);else inner=new SphereShape(s.size.GetX());
                compound.AddShape(s.position,rotation,inner);
            }
''' +cpp[end:]
cpp=cpp.replace('j.gains.GetZ()/std::sqrt(3.f)','j.gains.GetZ()')
cpp=cpp.replace('settings.mFriction=.7f;settings.mRestitution=0;',
'''settings.mFriction=std::getenv("TRANSFER_TRAINING_CONTACT")?1.f:.7f;
            settings.mRestitution=std::getenv("TRANSFER_TRAINING_CONTACT")?0.f:.3f;''')
cpp=cpp.replace('floor.mFriction=.7f;', 'floor.mFriction=std::getenv("TRANSFER_TRAINING_CONTACT")?1.f:.7f;')
cpp=cpp.replace('BodyID floorID;', 'float maxMotorFraction=0;BodyID floorID;')
cpp=cpp.replace('externalVerticalImpulse=0;groundNormalTilt=0;', 'externalVerticalImpulse=0;groundNormalTilt=0;maxMotorFraction=0;')
cpp=cpp.replace('throw std::runtime_error("Native physics failed");', '''throw std::runtime_error("Native physics failed");
            for(size_t ji=0;ji<joints.size();++ji){const Vec3 impulse=joints[ji]->GetTotalLambdaMotorRotation();
                for(int axis=0;axis<3;++axis)maxMotorFraction=std::max(maxMotorFraction,std::abs(impulse[axis])*240.f/kJoints[ji].gains.GetZ());}''')
cpp=cpp.replace('<<",\\\"ground_normal_tilt_sin\\\":"<<groundNormalTilt', '<<",\\\"max_motor_fraction\\\":"<<maxMotorFraction<<",\\\"ground_normal_tilt_sin\\\":"<<groundNormalTilt')
begin=cpp.index('                const auto& j=kJoints[i];auto& joint=');end=cpp.index('            if(physics.Update',begin)
cpp=cpp[:begin]+'''                const auto& j=kJoints[i];auto& joint=*joints[i];
                Vec3 local=Vec3::sZero();for(int a=0;a<3;++a)if(j.actions[a]>=0)local.SetComponent(a,actions[j.actions[a]]);
                // Rotation motors use body-2 constraint space (unlike linear
                // motors). Child constraint axes equal the training body axes.
                joint.SetTargetAngularVelocityCS(PolicyVelocityCS(j.childRotation,local));
            }
            auto& bi=physics.GetBodyInterface();
            for(size_t i=0;i<bodies.size();++i){
                const auto& b=*bodies[i];const auto& d=kDrag[i];const auto rot=Mat44::sRotation(b.GetRotation());
                const auto vel=b.GetLinearVelocity(),ang=b.GetAngularVelocity();const Vec3 first=rot.Multiply3x3(d.first);
                bi.AddForceAndTorque(b.GetID(),-d.coefficient*vel-ang.Cross(first),-first.Cross(vel)-(rot*d.second*rot.Transposed()).Multiply3x3(ang));
            }
''' +cpp[end:]
# CharEnv clips velocity commands to its action bounds after actor inference.
cpp=cpp.replace('a=Clamp(a,-4.f,4.f);','a=Clamp(a,-2.f*JPH_PI,2.f*JPH_PI);')
cpp=cpp.replace('struct Fixture : ContactImpulseListener',
'''static Vec3 PolicyVelocityCS(QuatArg childFrame,Vec3Arg local){return childFrame.Conjugated()*local;}
struct Fixture : ContactImpulseListener''')
cpp=cpp.replace('int main(int argc,char** argv)',(ROOT/'Labs/MimicKitTransfer/motor_test.inl').read_text()+'\nint main(int argc,char** argv)')
cpp=cpp.replace('    int result=0;', '''    if(std::string(argv[1])=="--motor-test"){
        const int result=MotorSelfTest();UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;}
    int result=0;''')
(OUT/'fixture.cpp').write_text(cpp)
print('Generated isolated15-body/34-action fixture',flush=True)
