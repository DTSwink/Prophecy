// Isolated project-DLL fixture. No Unreal process, assets or gameplay are edited.
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>
#include <array>
#include <cmath>
using namespace JPH;
struct ShapeSpec {int kind;Vec3 size,position;Quat rotation;};
struct DragSpec {float coefficient;Vec3 first;Mat44 second;};
struct BodySpec {const char* name;int start,end;Vec3 com;Quat inertiaRotation;Vec3 inertia;float mass,linearDamping,angularDamping,maxAngular,maxLinear;};
struct JointSpec {int parent,child;Vec3 parentPosition;Quat parentRotation;Vec3 childPosition;Quat childRotation;int modes[3];Vec3 limits;int actions[3];Vec3 gains;};
#include "jolt-rig-generated.h"
// Experimental spherical angular limit, solved by Jolt's own constraint solver.
// Matches the native-training total-angle bound, rather than a PHAT swing ellipse.
class RecoverySphericalLimit final : public TwoBodyConstraint {
    Quat frame1,frame2;float radius;Vec3 axis=Vec3::sAxisX();AngleConstraintPart part;
public:
    RecoverySphericalLimit(Body& a,Body& b,const SixDOFConstraintSettings& settings,const JointSpec& j):
        TwoBodyConstraint(a,b,settings),frame1(j.parentRotation),frame2(j.childRotation),radius(j.limits.ReduceMax()){}
    EConstraintSubType GetSubType()const override{return EConstraintSubType::Cone;}
    void NotifyShapeChanged(const BodyID&,Vec3Arg)override{}
    Mat44 GetConstraintToBody1Matrix()const override{return Mat44::sRotation(frame1);}
    Mat44 GetConstraintToBody2Matrix()const override{return Mat44::sRotation(frame2);}
    Ref<ConstraintSettings> GetConstraintSettings()const override{return new SixDOFConstraintSettings;}
    void SetupVelocityConstraint(float dt)override{
        Quat world=mBody1->GetRotation()*frame1;
        Quat q=(world.Conjugated()*mBody2->GetRotation()*frame2).EnsureWPositive();
        float angle;Vec3 local;q.GetAxisAngle(local,angle);
        float error=angle-radius;
        if(error<=0){part.Deactivate();return;}
        axis=world*local;
        constexpr float hz=32.f;
        part.CalculateConstraintPropertiesWithSettingsForLimit(dt,*mBody1,*mBody2,axis,0,error,SpringSettings(ESpringMode::FrequencyAndDamping,hz,1));
    }
    void ResetWarmStart()override{part.Deactivate();}
    void WarmStartVelocityConstraint(float ratio)override{if(part.IsActive())part.WarmStart(*mBody1,*mBody2,ratio);}
    bool SolveVelocityConstraint(float)override{return part.IsActive()&&part.SolveVelocityConstraint(*mBody1,*mBody2,axis,-1.e10f,0);}
    bool SolvePositionConstraint(float,float)override{return false;}
};

class Layers final:public BroadPhaseLayerInterface {public:uint GetNumBroadPhaseLayers()const override{return 2;}BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer l)const override{return BroadPhaseLayer(l);}};
class BroadFilter final:public ObjectVsBroadPhaseLayerFilter {public:bool ShouldCollide(ObjectLayer a,BroadPhaseLayer b)const override{return a==1||b.GetValue()==1;}};
class PairFilter final:public ObjectLayerPairFilter {public:bool ShouldCollide(ObjectLayer a,ObjectLayer b)const override{return !std::getenv("TRANSFER_NO_CONTACT") && (a==1||b==1) && !(std::getenv("TRANSFER_NO_SELF") && a==1 && b==1);}};

static Vec3 PolicyVelocityCS(QuatArg childFrame,Vec3Arg local){return childFrame.Conjugated()*local;}
// Isolated experiment only. A tagged body opts out of response to separated
// manifolds; re-evaluate persisted contacts so real contact becomes solid again.
struct RigContactFilter : ContactListener
{
    uint64 added=0,persisted=0,suppressed=0,solid=0;
    bool enabled=true;
    std::vector<std::string> observations;
    static constexpr uint64 Tag=0x5249473135ULL;
    void Apply(const Body& a,const Body& b,const ContactManifold& m,ContactSettings& s)
    {
        if(a.GetObjectLayer()==0 || b.GetObjectLayer()==0){
            std::ostringstream o;o<<std::setprecision(12)<<"{\"depth\":"<<m.mPenetrationDepth<<",\"friction\":"<<s.mCombinedFriction<<",\"restitution\":"<<s.mCombinedRestitution<<",\"points\":[";
            for(uint i=0;i<m.mRelativeContactPointsOn1.size();++i){if(i)o<<',';auto p=m.GetWorldSpaceContactPointOn2(i);o<<'['<<p.GetX()<<','<<p.GetY()<<','<<p.GetZ()<<']';}o<<"]}";observations.push_back(o.str());
        }
        if(std::getenv("TRANSFER_FRICTIONLESS_SELF") && a.GetObjectLayer()==1 && b.GetObjectLayer()==1)s.mCombinedFriction=0;
        if(!enabled || (a.GetUserData()!=Tag && b.GetUserData()!=Tag))return;
        if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}
        else ++solid; // Leave the settings initialized by Jolt untouched.
    }
    void OnContactAdded(const Body& a,const Body& b,const ContactManifold& m,ContactSettings& s) override
    {++added;Apply(a,b,m,s);}
    void OnContactPersisted(const Body& a,const Body& b,const ContactManifold& m,ContactSettings& s) override
    {++persisted;Apply(a,b,m,s);}
};


struct Fixture : ContactImpulseListener
{
    RigContactFilter rigContactFilter;Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
    TempAllocatorImpl allocator{32*1024*1024};JobSystemSingleThreaded jobs{1024};
    std::vector<Ref<TwoBodyConstraint>> extra;std::vector<Body*> bodies;std::vector<Ref<SixDOFConstraint>> joints;
    float maxMotorFraction=0;BodyID floorID;std::vector<double> groundImpulse;double externalVerticalImpulse=0;float groundNormalTilt=0;
    Fixture(const char* source)
    {
        physics.Init(64,0,1024,1024,layers,broad,pair);physics.SetGravity(std::getenv("TRANSFER_NO_GRAVITY")?Vec3::sZero():Vec3(0,0,-9.81f));
        auto& bi=physics.GetBodyInterface();if(std::getenv("TRANSFER_NO_SPECULATIVE")){auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}
        if(std::getenv("TRANSFER_HIGH_ITERATIONS")) {auto ps=physics.GetPhysicsSettings();ps.mNumVelocitySteps=100;ps.mNumPositionSteps=20;physics.SetPhysicsSettings(ps);}
        BodyCreationSettings floor(new BoxShape(Vec3(100,100,.1f),0),RVec3(0,0,-.1),Quat::sIdentity(),EMotionType::Static,0);
        floor.mFriction=std::getenv("TRANSFER_TRAINING_CONTACT")?1.f:.7f;floor.mRestitution=0;if(std::getenv("TRANSFER_FRICTION"))floor.mFriction=std::atof(std::getenv("TRANSFER_FRICTION"));floorID=bi.CreateAndAddBody(floor,EActivation::DontActivate);
        Ref<GroupFilterTable> filter=new GroupFilterTable(uint(std::size(kBodies)));
        for(const auto& p:kDisabledPairs)filter->DisableCollision(p[0],p[1]);
        std::ifstream input(source);
        for(const auto& b:kBodies)
        {
            double x,y,z;float qx,qy,qz,qw,vx,vy,vz,wx,wy,wz;
            if(!(input>>x>>y>>z>>qx>>qy>>qz>>qw>>vx>>vy>>vz>>wx>>wy>>wz))throw std::runtime_error("Invalid initial body states");
            StaticCompoundShapeSettings compound;
            for(int si=b.start;si<b.end;++si){
                const auto& s=kShapes[si];RefConst<Shape> inner;Quat rotation=s.rotation;
                if(s.kind==0){inner=new CapsuleShape(s.size.GetY(),s.size.GetX());rotation=rotation*Quat::sRotation(Vec3::sAxisX(),.5f*JPH_PI);}
                else if(s.kind==1)inner=new BoxShape(s.size,0);else inner=new SphereShape(s.size.GetX());
                compound.AddShape(s.position,rotation,inner);
            }
            const auto result=compound.Create();if(result.HasError())throw std::runtime_error(result.GetError().c_str());
            RefConst<Shape> shape=new OffsetCenterOfMassShape(result.Get(),b.com-result.Get()->GetCenterOfMass());
            BodyCreationSettings settings(shape,RVec3(x,y,z),Quat(qx,qy,qz,qw).Normalized(),EMotionType::Dynamic,1);
            settings.mFriction=std::getenv("TRANSFER_TRAINING_CONTACT")?1.f:.7f;
            settings.mRestitution=std::getenv("TRANSFER_TRAINING_CONTACT")?0.f:.3f;settings.mLinearDamping=b.linearDamping;settings.mAngularDamping=b.angularDamping;
            if(std::getenv("TRANSFER_FRICTION"))settings.mFriction=std::atof(std::getenv("TRANSFER_FRICTION"));if(std::getenv("TRANSFER_RESTITUTION"))settings.mRestitution=std::atof(std::getenv("TRANSFER_RESTITUTION"));settings.mAllowSleeping=false;settings.mMaxAngularVelocity=b.maxAngular;settings.mMaxLinearVelocity=b.maxLinear;
            settings.mLinearVelocity=Vec3(vx,vy,vz);settings.mAngularVelocity=Vec3(wx,wy,wz);
            settings.mNumVelocityStepsOverride=std::getenv("TRANSFER_RIG_VELOCITY_STEPS")?std::atoi(std::getenv("TRANSFER_RIG_VELOCITY_STEPS")):0; settings.mNumPositionStepsOverride=std::getenv("TRANSFER_RIG_POSITION_STEPS")?std::atoi(std::getenv("TRANSFER_RIG_POSITION_STEPS")):0;settings.mCollisionGroup=CollisionGroup(filter,0,uint(bodies.size()));settings.mUserData=RigContactFilter::Tag;
            settings.mOverrideMassProperties=EOverrideMassProperties::MassAndInertiaProvided;
            settings.mMassPropertiesOverride.mMass=b.mass;
            const Mat44 basis=Mat44::sRotation(b.inertiaRotation);
            settings.mMassPropertiesOverride.mInertia=basis*Mat44::sScale(b.inertia)*basis.Transposed();
            Body* body=bi.CreateBody(settings);bi.AddBody(body->GetID(),EActivation::Activate);bodies.push_back(body);
        }
        for(const auto& j:kJoints)
        {
            SixDOFConstraintSettings settings;settings.mSpace=EConstraintSpace::LocalToBodyCOM;settings.mSwingType=ESwingType::Cone;
            settings.mPosition1=RVec3(j.parentPosition-kBodies[j.parent].com);settings.mPosition2=RVec3(j.childPosition-kBodies[j.child].com);
            settings.mAxisX1=j.parentRotation*Vec3::sAxisX();settings.mAxisY1=j.parentRotation*Vec3::sAxisY();
            settings.mAxisX2=j.childRotation*Vec3::sAxisX();settings.mAxisY2=j.childRotation*Vec3::sAxisY();
            for(int axis=0;axis<3;++axis)
            {
                settings.MakeFixedAxis(static_cast<SixDOFConstraintSettings::EAxis>(axis));
                const auto angular=static_cast<SixDOFConstraintSettings::EAxis>(axis+3);
                if(j.modes[axis]==2)settings.MakeFixedAxis(angular);else if(std::getenv("TRANSFER_NO_LIMITS")||(std::getenv("TRANSFER_NATIVE_BALL_LIMITS")&&j.actions[0]>=0&&j.actions[1]>=0&&j.actions[2]>=0))settings.MakeFreeAxis(angular);else settings.SetLimitedAxis(angular,-j.limits[axis],j.limits[axis]);
                settings.mMotorSettings[axis+3]=MotorSettings(ESpringMode::StiffnessAndDamping,0,j.gains.GetY());
                settings.mMotorSettings[axis+3].SetTorqueLimit(kTorqueCaps[&j-kJoints][axis]);
            }
            settings.mNumVelocityStepsOverride=std::getenv("TRANSFER_RIG_VELOCITY_STEPS")?std::atoi(std::getenv("TRANSFER_RIG_VELOCITY_STEPS")):0; settings.mNumPositionStepsOverride=std::getenv("TRANSFER_RIG_POSITION_STEPS")?std::atoi(std::getenv("TRANSFER_RIG_POSITION_STEPS")):0;Ref<SixDOFConstraint> joint=static_cast<SixDOFConstraint*>(settings.Create(*bodies[j.parent],*bodies[j.child]));
            for(int axis=0;axis<3;++axis)joint->SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(axis+3),std::getenv("TRANSFER_NO_MOTORS")?EMotorState::Off:EMotorState::PositionAndVelocity);
            physics.AddConstraint(joint);joints.push_back(joint);
if(std::getenv("TRANSFER_NATIVE_BALL_LIMITS")&&j.actions[0]>=0&&j.actions[1]>=0&&j.actions[2]>=0){Ref<TwoBodyConstraint> limit=new RecoverySphericalLimit(*bodies[j.parent],*bodies[j.child],settings,j);physics.AddConstraint(limit);extra.push_back(limit);}
        }
        groundImpulse.resize(bodies.size(),0.0);physics.SetContactImpulseListener(this);if(!std::getenv("TRANSFER_RIG_ALLOW_SPECULATIVE"))physics.SetContactListener(&rigContactFilter);
    }
    ~Fixture(){for(auto& c:extra)physics.RemoveConstraint(c);physics.SetContactListener(nullptr);physics.SetContactImpulseListener(nullptr);for(auto& j:joints)physics.RemoveConstraint(j);}
    bool WantsContactImpulse(const Body& a,const Body& b) const override
    {return a.GetID()==floorID||b.GetID()==floorID;}
    void OnContactImpulse(const Body& a,const Body& b,const SubShapeID&,const SubShapeID&,
        RVec3Arg,RVec3Arg,Vec3Arg normal,float impulse) override
    {
        // Read-only observation of the actual solved impulse. The fixture uses
        // a single-threaded job system; no contact or body state is modified.
        const BodyID id=a.GetID()==floorID?b.GetID():a.GetID();
        const double vertical=impulse*(a.GetID()==floorID?normal.GetZ():-normal.GetZ());
        groundNormalTilt=std::max(groundNormalTilt,std::sqrt(normal.GetX()*normal.GetX()+normal.GetY()*normal.GetY()));
        for(size_t i=0;i<bodies.size();++i)if(bodies[i]->GetID()==id){groundImpulse[i]+=vertical;break;}
    }
    void Step(const std::vector<float>& actions)
    {
        rigContactFilter.observations.clear();std::fill(groundImpulse.begin(),groundImpulse.end(),0.0);
        externalVerticalImpulse=0;groundNormalTilt=0;maxMotorFraction=0;
        for(int substep=0;substep<(std::getenv("TRANSFER_SUBSTEPS")?std::atoi(std::getenv("TRANSFER_SUBSTEPS")):8);++substep)
        {
            // Gravity followed by native body drag, before internal motors and
            // contacts. Used only to validate the measured contact impulses.
            for(const Body* body:bodies)
            {
                const auto* motion=body->GetMotionProperties();const float v=body->GetLinearVelocity().GetZ();
                const float after=(v-9.81f/240)*std::max(0.f,1.f-motion->GetLinearDamping()/240);
                externalVerticalImpulse+=(after-v)/motion->GetInverseMass();
            }
            for(size_t i=0;i<joints.size();++i)
            {
                const auto& j=kJoints[i];auto& joint=*joints[i];
                Vec3 local=Vec3::sZero();for(int a=0;a<3;++a)if(j.actions[a]>=0)local.SetComponent(a,actions[j.actions[a]]);
                // Rotation motors use body-2 constraint space (unlike linear
                // motors). Child constraint axes equal the training body axes.
                joint.SetTargetAngularVelocityCS(PolicyVelocityCS(j.childRotation,local));
            }
            auto& bi=physics.GetBodyInterface();if(std::getenv("TRANSFER_NO_SPECULATIVE")){auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}
        if(std::getenv("TRANSFER_HIGH_ITERATIONS")) {auto ps=physics.GetPhysicsSettings();ps.mNumVelocitySteps=100;ps.mNumPositionSteps=20;physics.SetPhysicsSettings(ps);}
            for(size_t i=0;i<bodies.size();++i){
                const auto& b=*bodies[i];const auto& d=kDrag[i];const auto rot=Mat44::sRotation(b.GetRotation());
                const auto vel=b.GetLinearVelocity(),ang=b.GetAngularVelocity();const Vec3 first=rot.Multiply3x3(d.first);
                if(!std::getenv("TRANSFER_NO_DRAG"))bi.AddForceAndTorque(b.GetID(),-d.coefficient*vel-ang.Cross(first),-first.Cross(vel)-(rot*d.second*rot.Transposed()).Multiply3x3(ang));
            }
            if(physics.Update(1.f/240,1,&allocator,&jobs)!=EPhysicsUpdateError::None)throw std::runtime_error("Native physics failed");
            for(size_t ji=0;ji<joints.size();++ji){const Vec3 impulse=joints[ji]->GetTotalLambdaMotorRotation();
                for(int axis=0;axis<3;++axis)maxMotorFraction=std::max(maxMotorFraction,std::abs(impulse[axis])*240.f/kTorqueCaps[ji][axis]);}
        }
    }
    void Print()
    {
        std::cout<<"{\"rig_sha256\":\""<<kRigHash<<"\",\"controller_sha256\":\""<<kControllerHash<<"\",\"bodies\":[";
        for(size_t i=0;i<bodies.size();++i)
        {
            if(i)std::cout<<',';const auto& b=*bodies[i];const auto p=b.GetPosition();const auto q=b.GetRotation();const auto v=b.GetLinearVelocity(),w=b.GetAngularVelocity();
            std::cout<<'['<<p.GetX()<<','<<p.GetY()<<','<<p.GetZ()<<','<<q.GetX()<<','<<q.GetY()<<','<<q.GetZ()<<','<<q.GetW()<<','<<v.GetX()<<','<<v.GetY()<<','<<v.GetZ()<<','<<w.GetX()<<','<<w.GetY()<<','<<w.GetZ()<<']';
        }
        std::cout<<"],\"ground_vertical_impulse_ns\":[";
        for(size_t i=0;i<groundImpulse.size();++i){if(i)std::cout<<',';std::cout<<groundImpulse[i];}
        std::cout<<"],\"external_vertical_impulse_ns\":"<<externalVerticalImpulse
            <<",\"max_motor_fraction\":"<<maxMotorFraction<<",\"ground_normal_tilt_sin\":"<<groundNormalTilt<<",\"contacts\":[";
        for(size_t i=0;i<rigContactFilter.observations.size();++i){if(i)std::cout<<',';std::cout<<rigContactFilter.observations[i];}std::cout<<"]}"<<std::endl;
    }
    void Inspect()
    {
        std::cout<<"{\"body_properties\":[";
        for(size_t i=0;i<bodies.size();++i)
        {
            if(i)std::cout<<',';const auto& b=*bodies[i];const auto& mp=*b.GetMotionProperties();
            const Vec3 com=b.GetShape()->GetCenterOfMass();const auto inertia=mp.GetLocalSpaceInverseInertia();const auto box=b.GetWorldSpaceBounds();
            std::cout<<'['<<1/mp.GetInverseMass()<<','<<com.GetX()<<','<<com.GetY()<<','<<com.GetZ();
            for(int row=0;row<3;++row)for(int col=0;col<3;++col)std::cout<<','<<inertia(row,col);
            for(int axis=0;axis<3;++axis)std::cout<<','<<box.mMin[axis];
            for(int axis=0;axis<3;++axis)std::cout<<','<<box.mMax[axis];std::cout<<']';
        }
        std::cout<<"]}"<<std::endl;
    }
};
// Independent physical check: rotated child and rotated child constraint frame.
// Two unit inertias, no gravity/contact/limits/armature, velocity gain10.
static int MotorSelfTest()
{
    RigContactFilter rigContactFilter;Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
    physics.Init(16,0,32,32,layers,broad,pair);physics.SetGravity(Vec3::sZero());
    TempAllocatorImpl alloc(8*1024*1024);JobSystemSingleThreaded jobs(128);
    auto& bi=physics.GetBodyInterface();if(std::getenv("TRANSFER_NO_SPECULATIVE")){auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}
        if(std::getenv("TRANSFER_HIGH_ITERATIONS")) {auto ps=physics.GetPhysicsSettings();ps.mNumVelocitySteps=100;ps.mNumPositionSteps=20;physics.SetPhysicsSettings(ps);}Body* bodies[2];
    const Quat childRotation=Quat::sRotation(Vec3::sAxisZ(),.5f*JPH_PI);
    const Quat childFrame=Quat::sRotation(Vec3::sAxisZ(),JPH_PI/6);
    for(int i=0;i<2;++i){
        BodyCreationSettings s(new SphereShape(.1f),RVec3(0,0,10+10*i),i?childRotation:Quat::sIdentity(),EMotionType::Dynamic,1);
        s.mLinearDamping=0;s.mAngularDamping=0;s.mAllowSleeping=false;
        s.mOverrideMassProperties=EOverrideMassProperties::MassAndInertiaProvided;
        s.mMassPropertiesOverride.mMass=1;s.mMassPropertiesOverride.mInertia=Mat44::sIdentity();
        bodies[i]=bi.CreateBody(s);bi.AddBody(bodies[i]->GetID(),EActivation::Activate);
    }
    SixDOFConstraintSettings s;s.mSpace=EConstraintSpace::LocalToBodyCOM;
    s.mAxisX2=childFrame*Vec3::sAxisX();s.mAxisY2=childFrame*Vec3::sAxisY();
    for(int i=0;i<6;++i)s.MakeFreeAxis(static_cast<SixDOFConstraintSettings::EAxis>(i));
    for(int i=3;i<6;++i){s.mMotorSettings[i]=MotorSettings(ESpringMode::StiffnessAndDamping,0,10);s.mMotorSettings[i].SetTorqueLimit(100);}
    Ref<SixDOFConstraint> joint=static_cast<SixDOFConstraint*>(s.Create(*bodies[0],*bodies[1]));
    for(int i=3;i<6;++i)joint->SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(i),std::getenv("TRANSFER_NO_MOTORS")?EMotorState::Off:EMotorState::PositionAndVelocity);
    joint->SetTargetAngularVelocityCS(PolicyVelocityCS(childFrame,Vec3(1,0,0)));
    physics.AddConstraint(joint);physics.Update(1.f/240,1,&alloc,&jobs);
    const Vec3 measured=bodies[1]->GetAngularVelocity()-bodies[0]->GetAngularVelocity();
    const Vec3 expected=childRotation*Vec3((20.f/240)/(1+20.f/240),0,0);
    const float error=(measured-expected).Length();physics.RemoveConstraint(joint);
    std::cout<<"{\"motor_test_error_rad_s\":"<<error<<",\"measured\":["<<measured.GetX()<<','<<measured.GetY()<<','<<measured.GetZ()<<"]}"<<std::endl;
    return error<1e-5?0:6;
}

static int RigContactSelfTest()
{
    using Row=std::array<double,4>;
    std::vector<Row> samples[4];uint64 taggedSuppressed=0,taggedSolid=0,taggedPersisted=0;
    for(int mode=0;mode<4;++mode){
        Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
        physics.Init(16,0,64,64,layers,broad,pair);physics.SetGravity(Vec3(0,0,-9.81f));
        TempAllocatorImpl alloc(8*1024*1024);JobSystemSingleThreaded jobs(128);
        RigContactFilter filter;if(mode==1||mode==3)physics.SetContactListener(&filter);
        if(mode==2){auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}
        auto& bi=physics.GetBodyInterface();
        BodyCreationSettings floor(new BoxShape(Vec3(10,10,.1f),0),RVec3(0,0,-.1),Quat::sIdentity(),EMotionType::Static,0);
        floor.mRestitution=0;bi.CreateAndAddBody(floor,EActivation::DontActivate);
        Body* body[2];
        for(int i=0;i<2;++i){
            BodyCreationSettings s(new SphereShape(.1f),RVec3(i*2-1,0,.112),Quat::sIdentity(),EMotionType::Dynamic,1);
            s.mUserData=i==0?RigContactFilter::Tag:0;s.mLinearVelocity=Vec3(0,0,-1);
            s.mRestitution=.3f;s.mLinearDamping=0;s.mAngularDamping=0;s.mAllowSleeping=false;
            body[i]=bi.CreateBody(s);bi.AddBody(body[i]->GetID(),EActivation::Activate);
        }
        for(int tick=0;tick<120;++tick){
            if(mode==3&&tick==12)filter.enabled=false;
            physics.Update(1.f/240,1,&alloc,&jobs);
            samples[mode].push_back({body[0]->GetPosition().GetZ(),body[0]->GetLinearVelocity().GetZ(),body[1]->GetPosition().GetZ(),body[1]->GetLinearVelocity().GetZ()});
        }
        if(mode==1){taggedSuppressed=filter.suppressed;taggedSolid=filter.solid;taggedPersisted=filter.persisted;}
        physics.SetContactListener(nullptr);
    }
    double untouched=0,reference=0,effect=0,minHeight=1;
    for(size_t i=0;i<samples[0].size();++i){
        for(int c=0;c<2;++c){
            untouched=std::max(untouched,std::abs(samples[1][i][c+2]-samples[0][i][c+2]));
            reference=std::max(reference,std::abs(samples[1][i][c]-samples[2][i][c]));
            effect=std::max(effect,std::abs(samples[1][i][c]-samples[0][i][c]));
        }
        minHeight=std::min(minHeight,std::min(samples[1][i][0],samples[3][i][0]));
    }
    const bool pass=untouched==0&&reference<1e-6&&effect>1e-3&&taggedSuppressed>0&&taggedSolid>0&&taggedPersisted>0&&minHeight>.09;
    std::cout<<"{\"passed\":"<<(pass?"true":"false")<<",\"unmarked_max_error\":"<<untouched
        <<",\"tagged_vs_global_zero_max_error\":"<<reference<<",\"tagged_vs_default_max_difference\":"<<effect
        <<",\"suppressed_contacts\":"<<taggedSuppressed<<",\"solid_contacts\":"<<taggedSolid
        <<",\"persisted_callbacks\":"<<taggedPersisted<<",\"minimum_center_height_m\":"<<minHeight<<"}"<<std::endl;
    return pass?0:7;
}

int main(int argc,char** argv)
{
    if(argc!=2)return 2;RegisterDefaultAllocator();
    AssertFailed=[](const char* e,const char* m,const char* f,uint l){std::cerr<<f<<':'<<l<<' '<<e<<' '<<(m?m:"")<<std::endl;std::exit(4);return false;};
    if(!VerifyJoltVersionID())return 3;Factory::sInstance=new Factory();RegisterTypes();std::cout<<std::setprecision(12);
    if(std::string(argv[1])=="--motor-test"){
        const int result=MotorSelfTest();UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;}
    if(std::string(argv[1])=="--contact-test"){
        const int result=RigContactSelfTest();UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;}
    int result=0;
    try
    {
        Fixture fixture(argv[1]);fixture.Print();std::string line;
        while(std::getline(std::cin,line))
        {
            std::istringstream input(line);std::string command;input>>command;if(command=="quit")break;
            if(command=="inspect"){fixture.Inspect();continue;}
            if(command!="step")throw std::runtime_error("Expected step or quit");std::vector<float> actions(kActionCount);
            for(float& a:actions){if(!(input>>a)||!std::isfinite(a))throw std::runtime_error("Invalid action");/* Caller applies exact saved per-axis action bounds. */}
            fixture.Step(actions);fixture.Print();
        }
    }
    catch(const std::exception& error){std::cerr<<error.what()<<std::endl;result=5;}
    UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;
}


