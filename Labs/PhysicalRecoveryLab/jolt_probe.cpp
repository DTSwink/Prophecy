// Numerical calibration against the exact Jolt DLL used by this project.
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/ConstraintPart/SwingTwistConstraintPart.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <algorithm>
#include <string>

using namespace JPH;
class Layers final : public BroadPhaseLayerInterface
{
public:
    uint GetNumBroadPhaseLayers() const override { return 2; }
    BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer layer) const override { return BroadPhaseLayer(layer); }
};
class BroadFilter final : public ObjectVsBroadPhaseLayerFilter
{
public: bool ShouldCollide(ObjectLayer a, BroadPhaseLayer b) const override { return a == 1 || b.GetValue() == 1; }
};
class PairFilter final : public ObjectLayerPairFilter
{
public: bool ShouldCollide(ObjectLayer a, ObjectLayer b) const override { return a == 1 || b == 1; }
};

void Run(std::ofstream& out, const char* test, float dt, float friction, bool box, bool slide)
{
    Layers layers; BroadFilter broad; PairFilter pair;
    PhysicsSystem physics;
    physics.Init(32, 0, 128, 128, layers, broad, pair);
    physics.SetGravity(Vec3(0,0,-9.81f));
    TempAllocatorImpl allocator(8*1024*1024);
    JobSystemSingleThreaded jobs(1024);
    BodyInterface& bodies = physics.GetBodyInterface();
    RefConst<Shape> floor = new BoxShape(Vec3(10,10,.1f), 0.0f);
    BodyCreationSettings ground(floor, RVec3(0,0,-.1), Quat::sIdentity(), EMotionType::Static, 0);
    ground.mFriction = friction;
    ground.mRestitution = 0;
    bodies.CreateAndAddBody(ground, EActivation::DontActivate);
    RefConst<Shape> shape = box ? static_cast<const Shape*>(new BoxShape(Vec3(.1f,.1f,.1f),0.0f))
                               : static_cast<const Shape*>(new SphereShape(.1f));
    BodyCreationSettings moving(shape, RVec3(0,0,slide ? .1 : 1), Quat::sIdentity(), EMotionType::Dynamic, 1);
    moving.mFriction=friction; moving.mRestitution=0;
    moving.mLinearDamping=0; moving.mAngularDamping=0; moving.mAllowSleeping=false;
    moving.mOverrideMassProperties = EOverrideMassProperties::CalculateInertia;
    moving.mMassPropertiesOverride.mMass = 1;
    BodyID id = bodies.CreateAndAddBody(moving, EActivation::Activate);
    if (slide) bodies.SetLinearVelocity(id, Vec3(2,0,0));
    const int count = int(2.0f/dt+.5f);
    for (int tick=0; tick<=count; ++tick)
    {
        const auto p=bodies.GetPosition(id); const auto q=bodies.GetRotation(id);
        const auto v=bodies.GetLinearVelocity(id); const auto w=bodies.GetAngularVelocity(id);
        out << test << ',' << dt << ',' << friction << ',' << tick << ',' << tick*dt
            << ',' << p.GetX() << ',' << p.GetY() << ',' << p.GetZ()
            << ',' << q.GetX() << ',' << q.GetY() << ',' << q.GetZ() << ',' << q.GetW()
            << ',' << v.GetX() << ',' << v.GetY() << ',' << v.GetZ()
            << ',' << w.GetX() << ',' << w.GetY() << ',' << w.GetZ() << '\n';
        if (tick<count && physics.Update(dt,1,&allocator,&jobs)!=EPhysicsUpdateError::None)
            throw std::runtime_error("Jolt update failed");
    }
}
int ProbeLimits(const char* source,const char* destination)
{
    std::ifstream input(source); std::ofstream out(destination);
    out << std::setprecision(12) << "index,mask,twist,swing_y,swing_z,clamped_qx,clamped_qy,clamped_qz,clamped_qw\n";
    std::string line; std::getline(input,line);
    while (std::getline(input,line))
    {
        for(char& c:line) if(c==',') c=' ';
        std::istringstream row(line);
        int index,m0,m1,m2; float a,b,c,w,x,y,z;
        if(!(row>>index>>m0>>m1>>m2>>a>>b>>c>>w>>x>>y>>z)) return 5;
        auto limit=[](int mode,float angle){return mode==2?0.0f:mode==0?JPH_PI:angle;};
        a=limit(m0,a);b=limit(m1,b);c=limit(m2,c);
        SwingTwistConstraintPart part; part.SetSwingType(ESwingType::Cone);part.SetLimits(-a,a,-b,b,-c,c);
        Quat q=Quat(x,y,z,w).Normalized(), swing,twist;
        q.GetSwingTwist(swing,twist);
        if(swing.GetW()<0) swing=-swing;
        if(twist.GetW()<0) twist=-twist;
        const float theta=2.0f*ATan2(twist.GetX(),twist.GetW());
        const float sy=swing.GetY(),sz=swing.GetZ();
        uint mask=0;part.ClampSwingTwist(swing,twist,mask);q=swing*twist;
        out<<index<<','<<mask<<','<<theta<<','<<sy<<','<<sz<<','<<q.GetX()<<','<<q.GetY()<<','<<q.GetZ()<<','<<q.GetW()<<'\n';
    }
    return 0;
}
void JointResponse(std::ofstream& out,int test)
{
    Layers layers; BroadFilter broad; PairFilter pair; PhysicsSystem physics;
    physics.Init(16,0,32,32,layers,broad,pair);physics.SetGravity(Vec3::sZero());
    TempAllocatorImpl allocator(8*1024*1024);JobSystemSingleThreaded jobs(1024);
    auto& bodies=physics.GetBodyInterface();
    RefConst<Shape> shape=new SphereShape(.05f);
    BodyCreationSettings fixed(shape,RVec3::sZero(),Quat::sIdentity(),EMotionType::Static,0);
    Body* parent=bodies.CreateBody(fixed);bodies.AddBody(parent->GetID(),EActivation::DontActivate);
    BodyCreationSettings moving(shape,RVec3(0,0,1),Quat::sIdentity(),EMotionType::Dynamic,1);
    moving.mLinearDamping=0;moving.mAngularDamping=0;moving.mAllowSleeping=false;
    moving.mOverrideMassProperties=EOverrideMassProperties::MassAndInertiaProvided;
    moving.mMassPropertiesOverride.mMass=1;
    moving.mMassPropertiesOverride.mInertia=Mat44::sScale(Vec3(.1f,.2f,.3f));
    Body* child=bodies.CreateBody(moving);bodies.AddBody(child->GetID(),EActivation::Activate);
    SwingTwistConstraintSettings settings;
    settings.mPosition1=settings.mPosition2=RVec3(0,0,1);
    settings.mTwistMinAngle=-DegreesToRadians(30.0f);settings.mTwistMaxAngle=DegreesToRadians(30.0f);
    settings.mNormalHalfConeAngle=DegreesToRadians(45.0f);settings.mPlaneHalfConeAngle=DegreesToRadians(25.0f);
    Ref<Constraint> joint=settings.Create(*parent,*child);physics.AddConstraint(joint);
    const Vec3 target=test==0?Vec3(.15f,.2f,-.1f):test==1?Vec3(1.2f,0,0):Vec3(0,1.2f,0);
    const Quat desired=Quat::sRotation(target.Normalized(),target.Length());
    for(int tick=0;tick<=480;++tick)
    {
        const Quat q=bodies.GetRotation(child->GetID());
        const Vec3 velocity=q.Conjugated()*bodies.GetAngularVelocity(child->GetID());
        out<<test<<','<<tick<<','<<q.GetW()<<','<<q.GetX()<<','<<q.GetY()<<','<<q.GetZ()
            <<','<<velocity.GetX()<<','<<velocity.GetY()<<','<<velocity.GetZ()<<'\n';
        Quat error=q.Conjugated()*desired;if(error.GetW()<0)error=-error;
        const Vec3 vector=error.GetXYZ();const float length=vector.Length();
        const Vec3 rotation=length>1.0e-7f?vector*(2.0f*ATan2(length,error.GetW())/length):2.0f*vector;
        Vec3 torque=20.0f*rotation-3.0f*velocity;
        torque*=std::min(1.0f,20.0f/std::max(1.0e-8f,torque.Length()));
        bodies.AddTorque(child->GetID(),q*torque);
        if(tick<480 && physics.Update(1.0f/240,1,&allocator,&jobs)!=EPhysicsUpdateError::None)
            throw std::runtime_error("Joint update failed");
    }
    physics.RemoveConstraint(joint);
}
void FreeSpin(std::ofstream& out, bool gyroscopic)
{
    Layers layers; BroadFilter broad; PairFilter pair; PhysicsSystem physics;
    physics.Init(8,0,16,16,layers,broad,pair);physics.SetGravity(Vec3::sZero());
    TempAllocatorImpl allocator(8*1024*1024);JobSystemSingleThreaded jobs(1024);
    auto& bodies=physics.GetBodyInterface();
    BodyCreationSettings settings(new SphereShape(.05f),RVec3::sZero(),Quat::sIdentity(),EMotionType::Dynamic,1);
    settings.mLinearDamping=0;settings.mAngularDamping=0;settings.mAllowSleeping=false;
    settings.mApplyGyroscopicForce=gyroscopic;
    settings.mOverrideMassProperties=EOverrideMassProperties::MassAndInertiaProvided;
    settings.mMassPropertiesOverride.mMass=1;
    settings.mMassPropertiesOverride.mInertia=Mat44::sScale(Vec3(.002f,.004f,.005f));
    BodyID id=bodies.CreateAndAddBody(settings,EActivation::Activate);
    bodies.SetAngularVelocity(id,Vec3(5,10,15));
    for(int tick=0;tick<=240;++tick)
    {
        const auto q=bodies.GetRotation(id);const auto w=bodies.GetAngularVelocity(id);
        out<<int(gyroscopic)<<','<<tick<<','<<q.GetW()<<','<<q.GetX()<<','<<q.GetY()<<','<<q.GetZ()
           <<','<<w.GetX()<<','<<w.GetY()<<','<<w.GetZ()<<'\n';
        if(tick<240 && physics.Update(1.0f/240,1,&allocator,&jobs)!=EPhysicsUpdateError::None)
            throw std::runtime_error("Free spin update failed");
    }
}
// Isolated motor integration comparison. No assets or gameplay settings change.
int MotorResponses(const char* source,const char* destination)
{
    std::ifstream input(source);std::ofstream out(destination);std::string line;
    out<<std::setprecision(12)<<"case,mode,tick,qw,qx,qy,qz,wx,wy,wz\n";
    std::getline(input,line);
    while(std::getline(input,line))
    {
        for(char& c:line)if(c==',')c=' ';
        std::istringstream row(line);int id,relative;float ix,iy,iz,kp,kd,cap,rx,ry,rz;
        if(!(row>>id>>relative>>ix>>iy>>iz>>kp>>kd>>cap>>rx>>ry>>rz))return 5;
        for(int mode=0;mode<2;++mode)
        {
            Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
            physics.Init(8,0,16,16,layers,broad,pair);physics.SetGravity(Vec3::sZero());
            TempAllocatorImpl allocator(8*1024*1024);JobSystemSingleThreaded jobs(1024);
            auto& bodies=physics.GetBodyInterface();RefConst<Shape> shape=new SphereShape(.05f);
            BodyCreationSettings fixed(shape,RVec3::sZero(),Quat::sIdentity(),EMotionType::Static,0);
            Body* parent=bodies.CreateBody(fixed);bodies.AddBody(parent->GetID(),EActivation::DontActivate);
            BodyCreationSettings moving(shape,RVec3(0,0,1),Quat::sIdentity(),EMotionType::Dynamic,1);
            moving.mLinearDamping=0;moving.mAngularDamping=0;moving.mAllowSleeping=false;
            moving.mMaxAngularVelocity=1000; // Separate the motor from the production speed cap.
            moving.mOverrideMassProperties=EOverrideMassProperties::MassAndInertiaProvided;
            moving.mMassPropertiesOverride.mMass=1;moving.mMassPropertiesOverride.mInertia=Mat44::sScale(Vec3(ix,iy,iz));
            Body* child=bodies.CreateBody(moving);bodies.AddBody(child->GetID(),EActivation::Activate);
            SixDOFConstraintSettings settings;settings.mPosition1=settings.mPosition2=RVec3(0,0,1);
            for(int axis=0;axis<3;++axis)
            {
                settings.MakeFixedAxis(static_cast<SixDOFConstraintSettings::EAxis>(axis));
                settings.MakeFreeAxis(static_cast<SixDOFConstraintSettings::EAxis>(axis+3));
                settings.mMotorSettings[axis+3]=MotorSettings(ESpringMode::StiffnessAndDamping,mode==0?kp:0,kd);
                settings.mMotorSettings[axis+3].SetTorqueLimit(cap);
            }
            Ref<SixDOFConstraint> joint=static_cast<SixDOFConstraint*>(settings.Create(*parent,*child));physics.AddConstraint(joint);
            for(int axis=3;axis<6;++axis)joint->SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(axis),mode==0?EMotorState::Position:EMotorState::PositionAndVelocity);
            const Vec3 rv(rx,ry,rz);const Quat delta=Quat::sRotation(rv.Normalized(),rv.Length());
            for(int tick=0;tick<=240;++tick)
            {
                const Quat q=bodies.GetRotation(child->GetID());const Vec3 w=q.Conjugated()*bodies.GetAngularVelocity(child->GetID());
                out<<id<<','<<mode<<','<<tick<<','<<q.GetW()<<','<<q.GetX()<<','<<q.GetY()<<','<<q.GetZ()<<','<<w.GetX()<<','<<w.GetY()<<','<<w.GetZ()<<'\n';
                const Quat target=relative?q*delta:delta;
                joint->SetTargetOrientationCS(target);
                if(mode==1)
                {
                    Quat diff=q.Conjugated()*target;if(diff.GetW()<0)diff=-diff;
                    const Vec3 v=diff.GetXYZ();const float len=v.Length();
                    const Vec3 error=len>1e-7f?v*(2*ATan2(len,diff.GetW())/len):2*v;
                    joint->SetTargetAngularVelocityCS(error*(kp/kd));
                }
                if(tick<240 && physics.Update(1.f/240,1,&allocator,&jobs)!=EPhysicsUpdateError::None)throw std::runtime_error("Motor update failed");
            }
            physics.RemoveConstraint(joint);
        }
    }
    return 0;
}
int main(int argc, char** argv)
{
    if(argc==4 && std::string(argv[1])=="--limits") return ProbeLimits(argv[2],argv[3]);
    const bool motor=argc==4 && std::string(argv[1])=="--motors";
    if (!motor && argc!=2 && !(argc==3 && (std::string(argv[1])=="--joints" || std::string(argv[1])=="--free-spin"))) return 2;
    RegisterDefaultAllocator();
    AssertFailed = [](const char* expr, const char* msg, const char* file, uint line) {
        std::cerr << file << ':' << line << " Jolt assertion: " << expr << ' ' << (msg ? msg : "") << std::endl;
        std::exit(4); return false;
    };
    if (!VerifyJoltVersionID()) return 3;
    Factory::sInstance=new Factory(); RegisterTypes();
    if(motor)
    {
        const int result=MotorResponses(argv[2],argv[3]);UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;
    }
    if(argc==3)
    {
        std::ofstream out(argv[2]);out<<std::setprecision(12)<<"test,tick,qw,qx,qy,qz,wx,wy,wz\n";
        if(std::string(argv[1])=="--free-spin")
        { FreeSpin(out,false);FreeSpin(out,true); }
        else for(int test=0;test<3;++test)JointResponse(out,test);
        UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return 0;
    }
    std::ofstream out(argv[1]); out << std::setprecision(12);
    out << "test,dt,friction,tick,time,x,y,z,qx,qy,qz,qw,vx,vy,vz,wx,wy,wz\n";
    for (float dt : {1.0f/60,1.0f/120,1.0f/240})
        for (float friction : {0.0f,.4f,.7f,1.0f})
        {
            Run(out,"sphere_drop",dt,friction,false,false);
            Run(out,"box_drop",dt,friction,true,false);
            Run(out,"box_slide",dt,friction,true,true);
        }
    UnregisterTypes(); delete Factory::sInstance; Factory::sInstance=nullptr;
    std::cout << "Jolt shape calibration recorded\n";
}
