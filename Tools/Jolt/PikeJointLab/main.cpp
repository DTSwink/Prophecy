#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/Constraints/SliderConstraint.h>
#include "CoupledPike.h"
#include "HardSix.h"
#include <Jolt/Physics/Collision/ContactListener.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
using namespace JPH;
bool SpinStress=false;
struct Layers final : BroadPhaseLayerInterface, ObjectVsBroadPhaseLayerFilter, ObjectLayerPairFilter {
 uint GetNumBroadPhaseLayers() const override { return 2; }
 BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer l) const override { return BroadPhaseLayer(l); }
 bool ShouldCollide(ObjectLayer a,BroadPhaseLayer b) const override { return a || b.GetValue(); }
 bool ShouldCollide(ObjectLayer a,ObjectLayer b) const override { return a || b; }
};
struct ContactCount : ContactListener { int Count=0; void OnContactAdded(const Body&,const Body&,const ContactManifold&,ContactSettings&) override {++Count;} };
void Run(int mode,bool obstacle,float mass,float lever) {
 Layers layers; TempAllocatorImpl temp(8*1024*1024); JobSystemSingleThreaded jobs(cMaxPhysicsJobs);
 PhysicsSystem physics; physics.Init(128,0,256,256,layers,layers,layers);
 physics.SetGravity(Vec3::sZero()); ContactCount contacts; physics.SetContactListener(&contacts);
 auto &bi=physics.GetBodyInterface();
 Ref<GroupFilterTable> filter=new GroupFilterTable(2); filter->DisableCollision(0,1);
 auto add=[&](Vec3 size,RVec3 p,float m,int group) {
  BodyCreationSettings s(new BoxShape(size,0.005f),p,Quat::sIdentity(),m>0?EMotionType::Dynamic:EMotionType::Static,m>0?1:0);
  if(m>0) {s.mOverrideMassProperties=EOverrideMassProperties::CalculateInertia;s.mMassPropertiesOverride.mMass=m;s.mAllowSleeping=false;}
  if(group>=0) s.mCollisionGroup=CollisionGroup(filter,0,group);
  return bi.CreateAndAddBody(s,EActivation::Activate);
 };
 // A long thin blade through an off-centre wound. Connected pair alone ignores contact.
 auto sword=add(Vec3(.025f,.012f,.7f),RVec3(0,0,2),1,0);
 auto arm=add(Vec3(.07f,.07f,.2f),RVec3(.09f,0,2+lever),mass,1);
 if(obstacle) add(Vec3(.1f,2,2),RVec3(.55f,0,2),0,-1);
 SixDOFConstraintSettings six; six.mSpace=EConstraintSpace::LocalToBodyCOM;
 six.mPosition1=RVec3(0,0,lever);six.mPosition2=RVec3(-.09f,0,0);
 for(int axis=0;axis<6;axis++) six.MakeFixedAxis(SixDOFConstraintSettings::EAxis(axis));
 six.SetLimitedAxis(SixDOFConstraintSettings::TranslationZ,-1.26f,1.26f);
 SliderConstraintSettings slider; slider.mSpace=EConstraintSpace::LocalToBodyCOM;
 slider.mAutoDetectPoint=false;slider.mPoint1=six.mPosition1;slider.mPoint2=six.mPosition2;
 slider.mSliderAxis1=slider.mSliderAxis2=Vec3::sAxisZ();slider.mNormalAxis1=slider.mNormalAxis2=Vec3::sAxisX();
 slider.mLimitsMin=-1.26f;slider.mLimitsMax=1.26f;
 if(mode==2) for(int axis=0;axis<6;axis++) if(axis!=2) six.MakeFreeAxis(SixDOFConstraintSettings::EAxis(axis));
 Ref<TwoBodyConstraint> joint=bi.CreateConstraint(mode==1?static_cast<TwoBodyConstraintSettings*>(&slider):&six,sword,arm);
 if(mode==2)joint=new CoupledPike(*static_cast<SixDOFConstraint*>(joint.GetPtr()),six);
 if(mode==3)joint=new HardSix(*static_cast<SixDOFConstraint*>(joint.GetPtr()),six);
 physics.AddConstraint(joint);
 bi.SetLinearVelocity(sword,Vec3(3,1,0));bi.SetLinearVelocity(arm,Vec3(-1,0,0));
 if(SpinStress){bi.SetAngularVelocity(sword,Vec3(0,15,0));bi.SetAngularVelocity(arm,Vec3(-3,0,0));}
 double peak=0,rms=0,angle=0,max_x=-100;auto start=std::chrono::steady_clock::now();
 for(int i=0;i<120;i++) {
  if(obstacle)bi.AddForce(arm,Vec3(mass*10,0,0));
  physics.Update(1.f/60,1,&temp,&jobs);
  auto s=bi.GetCenterOfMassTransform(sword),a=bi.GetCenterOfMassTransform(arm);
  Vec3 delta(a*six.mPosition2-s*six.mPosition1),axis=s.Multiply3x3(Vec3::sAxisZ());
  float lateral=(delta-axis*delta.Dot(axis)).Length();peak=std::max(peak,double(lateral));rms+=lateral*lateral;
  angle=std::max(angle,double(2*ACos(std::min(1.f,abs(bi.GetRotation(sword).Dot(bi.GetRotation(arm)))))));
  max_x=std::max(max_x,double(bi.GetCenterOfMassPosition(sword).GetX()));
 }
 auto us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/120;
 printf("%s,obstacle=%d,mass=%.1f,lever=%.2f,peak_cm=%.6f,rms_cm=%.6f,angle_deg=%.4f,max_x=%.4f,contacts=%d,us=%.2f\n",mode==3?"six_full":mode==2?"coupled":mode==1?"slider":"six",obstacle,mass,lever,peak*100,sqrt(rms/120)*100,angle*180/JPH_PI,max_x,contacts.Count,us);
 physics.RemoveConstraint(joint);
 BodyIDVector ids;physics.GetBodies(ids);bi.RemoveBodies(ids.data(),int(ids.size()));bi.DestroyBodies(ids.data(),int(ids.size()));
}
int main(int argc,char**){SpinStress=argc>1;RegisterDefaultAllocator();Factory::sInstance=new Factory;RegisterTypes();
 AssertFailed=[](const char *e,const char *m,const char *f,uint l){fprintf(stderr,"%s:%u %s %s\n",f,l,e,m?m:"");exit(2);return false;};
 for(float mass:{2.f,10.f,50.f})for(float lever:{.1f,.6f})for(bool obstacle:{false,true})for(int mode:{0,1,2,3})Run(mode,obstacle,mass,lever);
 UnregisterTypes();delete Factory::sInstance;
}






