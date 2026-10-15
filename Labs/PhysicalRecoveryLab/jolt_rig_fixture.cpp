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
#include <cmath>
using namespace JPH;
struct BodySpec {const char* name;int kind;Vec3 size,shapePosition;Quat shapeRotation;Vec3 com;Quat inertiaRotation;Vec3 inertia;float mass,linearDamping,angularDamping,maxAngular,maxLinear;};
struct JointSpec {int parent,child;Vec3 parentPosition;Quat parentRotation;Vec3 childPosition;Quat childRotation;int modes[3];Vec3 limits;int actions[3];Vec3 gains;};
#include "jolt-rig-generated.h"
class Layers final:public BroadPhaseLayerInterface {public:uint GetNumBroadPhaseLayers()const override{return 2;}BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer l)const override{return BroadPhaseLayer(l);}};
class BroadFilter final:public ObjectVsBroadPhaseLayerFilter {public:bool ShouldCollide(ObjectLayer a,BroadPhaseLayer b)const override{return a==1||b.GetValue()==1;}};
class PairFilter final:public ObjectLayerPairFilter {public:bool ShouldCollide(ObjectLayer a,ObjectLayer b)const override{return a==1||b==1;}};

struct Fixture : ContactImpulseListener
{
    Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
    TempAllocatorImpl allocator{32*1024*1024};JobSystemSingleThreaded jobs{1024};
    std::vector<Body*> bodies;std::vector<Ref<SixDOFConstraint>> joints;
    BodyID floorID;std::vector<double> groundImpulse;double externalVerticalImpulse=0;float groundNormalTilt=0;
    Fixture(const char* source)
    {
        physics.Init(64,0,1024,1024,layers,broad,pair);physics.SetGravity(Vec3(0,0,-9.81f));
        auto& bi=physics.GetBodyInterface();
        BodyCreationSettings floor(new BoxShape(Vec3(100,100,.1f),0),RVec3(0,0,-.1),Quat::sIdentity(),EMotionType::Static,0);
        floor.mFriction=.7f;floor.mRestitution=0;floorID=bi.CreateAndAddBody(floor,EActivation::DontActivate);
        Ref<GroupFilterTable> filter=new GroupFilterTable(uint(std::size(kBodies)));
        for(const auto& p:kDisabledPairs)filter->DisableCollision(p[0],p[1]);
        std::ifstream input(source);
        for(const auto& b:kBodies)
        {
            double x,y,z;float qx,qy,qz,qw,vx,vy,vz,wx,wy,wz;
            if(!(input>>x>>y>>z>>qx>>qy>>qz>>qw>>vx>>vy>>vz>>wx>>wy>>wz))throw std::runtime_error("Invalid initial body states");
            RefConst<Shape> inner;Quat rotation=b.shapeRotation;
            if(b.kind==0){inner=new CapsuleShape(b.size.GetY(),b.size.GetX());rotation=rotation*Quat::sRotation(Vec3::sAxisX(),.5f*JPH_PI);}
            else if(b.kind==1)inner=new BoxShape(b.size,0);
            else inner=new SphereShape(b.size.GetX());
            StaticCompoundShapeSettings compound;compound.AddShape(b.shapePosition,rotation,inner);
            const auto result=compound.Create();if(result.HasError())throw std::runtime_error(result.GetError().c_str());
            RefConst<Shape> shape=new OffsetCenterOfMassShape(result.Get(),b.com-result.Get()->GetCenterOfMass());
            BodyCreationSettings settings(shape,RVec3(x,y,z),Quat(qx,qy,qz,qw).Normalized(),EMotionType::Dynamic,1);
            settings.mFriction=.7f;settings.mRestitution=0;settings.mLinearDamping=b.linearDamping;settings.mAngularDamping=b.angularDamping;
            settings.mAllowSleeping=false;settings.mMaxAngularVelocity=b.maxAngular;settings.mMaxLinearVelocity=b.maxLinear;
            settings.mLinearVelocity=Vec3(vx,vy,vz);settings.mAngularVelocity=Vec3(wx,wy,wz);
            settings.mCollisionGroup=CollisionGroup(filter,0,uint(bodies.size()));
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
                if(j.modes[axis]==2)settings.MakeFixedAxis(angular);else settings.SetLimitedAxis(angular,-j.limits[axis],j.limits[axis]);
                settings.mMotorSettings[axis+3]=MotorSettings(ESpringMode::StiffnessAndDamping,0,j.gains.GetY());
                settings.mMotorSettings[axis+3].SetTorqueLimit(j.gains.GetZ()/std::sqrt(3.f));
            }
            Ref<SixDOFConstraint> joint=static_cast<SixDOFConstraint*>(settings.Create(*bodies[j.parent],*bodies[j.child]));
            for(int axis=0;axis<3;++axis)joint->SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(axis+3),EMotorState::PositionAndVelocity);
            physics.AddConstraint(joint);joints.push_back(joint);
        }
        groundImpulse.resize(bodies.size(),0.0);physics.SetContactImpulseListener(this);
    }
    ~Fixture(){physics.SetContactImpulseListener(nullptr);for(auto& j:joints)physics.RemoveConstraint(j);}
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
        std::fill(groundImpulse.begin(),groundImpulse.end(),0.0);
        externalVerticalImpulse=0;groundNormalTilt=0;
        for(int substep=0;substep<8;++substep)
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
                const auto& j=kJoints[i];auto& joint=*joints[i];const Quat q=joint.GetRotationInConstraintSpace();
                Quat swing,twist;q.GetSwingTwist(swing,twist);if(swing.GetW()<0)swing=-swing;if(twist.GetW()<0)twist=-twist;
                float target[3]={2*ATan2(twist.GetX(),twist.GetW()),swing.GetY(),swing.GetZ()};
                const float increment=.25f*(j.gains.GetZ()/std::sqrt(3.f))/j.gains.GetX();
                float radius=0;
                for(int axis=0;axis<3;++axis)
                {
                    if(j.actions[axis]<0)target[axis]=0;
                    else target[axis]+=actions[j.actions[axis]]*(axis==0?increment:std::sin(.5f*increment));
                    if(axis>0&&j.actions[axis]>=0){const float norm=target[axis]/std::sin(.5f*j.limits[axis]);radius+=norm*norm;}
                }
                target[0]=Clamp(target[0],-j.limits[0],j.limits[0]);const float scale=std::max(1.f,std::sqrt(radius));target[1]/=scale;target[2]/=scale;
                const Quat desired=Quat(0,target[1],target[2],std::sqrt(std::max(0.f,1-target[1]*target[1]-target[2]*target[2]))) * Quat::sRotation(Vec3::sAxisX(),target[0]);
                Quat diff=q.Conjugated()*desired;if(diff.GetW()<0)diff=-diff;
                const Vec3 v=diff.GetXYZ();const float length=v.Length();
                const Vec3 error=length>1e-7f?v*(2*ATan2(length,diff.GetW())/length):2*v;
                joint.SetTargetAngularVelocityCS(error*(j.gains.GetX()/j.gains.GetY()));
            }
            if(physics.Update(1.f/240,1,&allocator,&jobs)!=EPhysicsUpdateError::None)throw std::runtime_error("Native physics failed");
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
            <<",\"ground_normal_tilt_sin\":"<<groundNormalTilt<<"}"<<std::endl;
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
int main(int argc,char** argv)
{
    if(argc!=2)return 2;RegisterDefaultAllocator();
    AssertFailed=[](const char* e,const char* m,const char* f,uint l){std::cerr<<f<<':'<<l<<' '<<e<<' '<<(m?m:"")<<std::endl;std::exit(4);return false;};
    if(!VerifyJoltVersionID())return 3;Factory::sInstance=new Factory();RegisterTypes();std::cout<<std::setprecision(12);
    int result=0;
    try
    {
        Fixture fixture(argv[1]);fixture.Print();std::string line;
        while(std::getline(std::cin,line))
        {
            std::istringstream input(line);std::string command;input>>command;if(command=="quit")break;
            if(command=="inspect"){fixture.Inspect();continue;}
            if(command!="step")throw std::runtime_error("Expected step or quit");std::vector<float> actions(kActionCount);
            for(float& a:actions){if(!(input>>a)||!std::isfinite(a))throw std::runtime_error("Invalid action");a=Clamp(a,-4.f,4.f);}
            fixture.Step(actions);fixture.Print();
        }
    }
    catch(const std::exception& error){std::cerr<<error.what()<<std::endl;result=5;}
    UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;
}
