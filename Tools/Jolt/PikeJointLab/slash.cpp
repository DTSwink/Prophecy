#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include "../../../Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltSlashJoint.h"
#include <chrono>
#include <cstdio>
#include <vector>
using namespace JPH;
struct Layers final : BroadPhaseLayerInterface,ObjectVsBroadPhaseLayerFilter,ObjectLayerPairFilter {
 uint GetNumBroadPhaseLayers() const override{return 2;}
 BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer l) const override{return BroadPhaseLayer(l);}
 bool ShouldCollide(ObjectLayer a,BroadPhaseLayer b) const override{return a||b.GetValue();}
 bool ShouldCollide(ObjectLayer a,ObjectLayer b) const override{return a||b;}
};
bool Run(bool coupled,int count,bool moving) {
 Layers layers;TempAllocatorImpl temp(16*1024*1024);JobSystemSingleThreaded jobs(cMaxPhysicsJobs);
 PhysicsSystem physics;physics.Init(2048,0,4096,4096,layers,layers,layers);physics.SetGravity(Vec3::sZero());
 auto& bi=physics.GetBodyInterface();Ref<GroupFilterTable> filter=new GroupFilterTable(2);filter->DisableCollision(0,1);
 struct Pair{BodyID sword,victim;Ref<TwoBodyConstraint> joint;};std::vector<Pair> pairs;
 for(int i=0;i<count;i++) {
  auto make=[&](Vec3 size,RVec3 p,float mass,int subgroup) {
   BodyCreationSettings s(new BoxShape(size,.005f),p,Quat::sIdentity(),mass>0?EMotionType::Dynamic:EMotionType::Static,mass>0?1:0);
   if(mass>0){s.mOverrideMassProperties=EOverrideMassProperties::CalculateInertia;s.mMassPropertiesOverride.mMass=mass;s.mAllowSleeping=false;}
   s.mCollisionGroup=CollisionGroup(filter,i,subgroup);return bi.CreateAndAddBody(s,EActivation::Activate);
  };
  BodyID sword=make(Vec3(.012f,.028f,.5f),RVec3(i*3.,0,2),1,0);
  BodyID victim=make(Vec3(.06f,.06f,.2f),RVec3(i*3.,.028f,2.4),moving?10.f:0.f,1);
  SixDOFConstraintSettings original;original.mSpace=EConstraintSpace::LocalToBodyCOM;
  original.mPosition1=RVec3(0,0,-.4);original.mPosition2=RVec3::sZero();
  original.MakeFixedAxis(SixDOFConstraintSettings::TranslationX);
  original.SetLimitedAxis(SixDOFConstraintSettings::TranslationY,-1000.f,.028f);
  original.SetLimitedAxis(SixDOFConstraintSettings::TranslationZ,0.f,1000.f);
  original.MakeFreeAxis(SixDOFConstraintSettings::RotationX);
  original.MakeFixedAxis(SixDOFConstraintSettings::RotationY);original.MakeFixedAxis(SixDOFConstraintSettings::RotationZ);
  auto native=original;
  if(coupled){native.MakeFreeAxis(SixDOFConstraintSettings::TranslationX);native.MakeFreeAxis(SixDOFConstraintSettings::RotationY);native.MakeFreeAxis(SixDOFConstraintSettings::RotationZ);}
  Ref<TwoBodyConstraint> joint=bi.CreateConstraint(&native,sword,victim);
  if(coupled)joint=new ProphecyJolt::FSlashJoint(*static_cast<SixDOFConstraint*>(joint.GetPtr()),original);
  physics.AddConstraint(joint);pairs.push_back({sword,victim,joint});
  bi.SetLinearVelocity(sword,Vec3(2,-10,0));bi.SetAngularVelocity(sword,Vec3(3,1,1));
 }
 double peak=0,angle=0,width=0,freeRotation=0,micros=0;
 for(int step=0;step<120;step++) {
  for(auto& p:pairs)bi.AddForce(p.sword,Vec3(5,-10,0));
  auto start=std::chrono::steady_clock::now();physics.Update(1.f/60,1,&temp,&jobs);
  micros+=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
  for(auto& p:pairs) {
   auto a=bi.GetCenterOfMassTransform(p.sword),b=bi.GetCenterOfMassTransform(p.victim);
   Vec3 delta(b.GetTranslation()-a*RVec3(0,0,-.4));Vec3 normal=a.Multiply3x3(Vec3::sAxisX());
   peak=std::max(peak,double(abs(delta.Dot(normal))));
   angle=std::max(angle,double(normal.Cross(b.Multiply3x3(Vec3::sAxisX())).Length()));
   width=std::max(width,double(delta.Dot(a.Multiply3x3(Vec3::sAxisY()))-.028f));
   freeRotation=std::max(freeRotation,double(abs(bi.GetRotation(p.sword).GetX())));
  }
 }
 printf("%s,%d,%s,%.6f,%.6f,%.6f,%.4f,%.3f\n",coupled?"coupled":"stock",count,moving?"dynamic":"static",peak*100,angle,width*100,freeRotation,micros/120);
 bool ok=!coupled||(peak<.002&&angle<.005&&freeRotation>.05);
 for(auto& p:pairs){physics.RemoveConstraint(p.joint);bi.RemoveBody(p.sword);bi.RemoveBody(p.victim);bi.DestroyBody(p.sword);bi.DestroyBody(p.victim);}
 return ok;
}
int main(){RegisterDefaultAllocator();Factory::sInstance=new Factory;RegisterTypes();bool ok=true;
 puts("mode,cuts,victim,plane_error_cm,swing_error_sine,width_excess_cm,free_twist_quat_x,world_step_us");
 for(int count:{1,100})for(bool moving:{false,true})for(bool coupled:{false,true})ok=Run(coupled,count,moving)&&ok;
 UnregisterTypes();delete Factory::sInstance;return ok?0:1;}
