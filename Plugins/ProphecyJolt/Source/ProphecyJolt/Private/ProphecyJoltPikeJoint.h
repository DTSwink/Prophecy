#pragma once
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/StateRecorder.h>

// Block solve: the two transverse rows and three angular rows share
// one effective mass matrix. The stock joint retains axial limits and motors.
namespace ProphecyJolt {
class FPikeJoint final : public JPH::TwoBodyConstraint {
public:
 FPikeJoint(JPH::SixDOFConstraint &native,const JPH::SixDOFConstraintSettings &settings)
 : TwoBodyConstraint(*native.GetBody1(),*native.GetBody2(),settings),Native(&native),
   LocalA(native.GetConstraintToBody1Matrix()),LocalB(native.GetConstraintToBody2Matrix()) { Build(); }
 bool HasSolvableMassMatrix() const { return Valid; }
 JPH::SixDOFConstraint& GetNative() const { return *Native; }
 JPH::Vec3 GetLinearImpulse() const { return Native->GetTotalWorldSpaceLinearImpulse()+VelocityLin[0]*Lambda[0]+VelocityLin[1]*Lambda[1]; }
 JPH::Vec3 GetAngularImpulse() const { return Native->GetTotalWorldSpaceAngularImpulse()+JPH::Vec3(Lambda[2],Lambda[3],Lambda[4]); }
 JPH::EConstraintSubType GetSubType() const override {return JPH::EConstraintSubType::User3;}
 void NotifyShapeChanged(const JPH::BodyID &id,JPH::Vec3Arg d) override {
  Native->NotifyShapeChanged(id,d);LocalA=Native->GetConstraintToBody1Matrix();LocalB=Native->GetConstraintToBody2Matrix();
 }
 void ResetWarmStart() override {Native->ResetWarmStart();for(float &v:Lambda)v=0;}
 void SetupVelocityConstraint(float dt) override {Native->SetupVelocityConstraint(dt);Build();VelocityLin[0]=Lin[0];VelocityLin[1]=Lin[1];}
 void WarmStartVelocityConstraint(float ratio) override {
  Native->WarmStartVelocityConstraint(ratio);for(float &v:Lambda)v=Valid?v*ratio:0;Apply(Lambda,false);
 }
 bool SolveVelocityConstraint(float dt) override {
  bool changed=Native->SolveVelocityConstraint(dt);float rhs[5],step[5];
  auto va=mBody1->GetLinearVelocity(),vb=mBody2->GetLinearVelocity();
  auto wa=mBody1->GetAngularVelocity(),wb=mBody2->GetAngularVelocity();
  for(int i=0;i<5;i++)rhs[i]=-(Lin[i].Dot(vb-va)+AngB[i].Dot(wb)-AngA[i].Dot(wa));
  if(!Solve(rhs,step))return changed;
  for(int i=0;i<5;i++)Lambda[i]+=step[i];Apply(step,false);return true;
 }
 bool SolvePositionConstraint(float dt,float beta) override {
  // The axial bound is a hard blade stop, like the locked connector rows.
  // Correct it fully inside the existing iterations, before contact solving.
  bool changed=Native->SolvePositionConstraint(dt,1.f);Build();
  // Hard connector: remove the coupled error in this solver iteration. Contacts
  // still solve in the same island, after joints; there is no post-step teleport.
  beta=1.f;
  auto pa=mBody1->GetCenterOfMassTransform()*LocalA.GetTranslation();
  auto pb=mBody2->GetCenterOfMassTransform()*LocalB.GetTranslation();
  auto qa=mBody1->GetRotation()*LocalA.GetQuaternion(),qb=mBody2->GetRotation()*LocalB.GetQuaternion();
  auto q=qb*qa.Conjugated();auto err=q.GetXYZ()*(q.GetW()<0?-2.f:2.f);
  float rhs[5]={-beta*JPH::Vec3(pb-pa).Dot(Lin[0]),-beta*JPH::Vec3(pb-pa).Dot(Lin[1]),-beta*err.GetX(),-beta*err.GetY(),-beta*err.GetZ()},step[5];
  if(!Solve(rhs,step))return changed;Apply(step,true);return true;
 }
 JPH::Mat44 GetConstraintToBody1Matrix() const override{return LocalA;}
 JPH::Mat44 GetConstraintToBody2Matrix() const override{return LocalB;}
 JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings() const override{return Native->GetConstraintSettings();}
 void SaveState(JPH::StateRecorder &s) const override {TwoBodyConstraint::SaveState(s);Native->SaveState(s);for(float v:Lambda)s.Write(v);}
 void RestoreState(JPH::StateRecorder &s) override {TwoBodyConstraint::RestoreState(s);Native->RestoreState(s);for(float &v:Lambda)s.Read(v);}
private:
 static double Dot(JPH::Vec3 a,JPH::Vec3 b) { return double(a.GetX())*b.GetX()+double(a.GetY())*b.GetY()+double(a.GetZ())*b.GetZ(); }
 static JPH::Vec3 Axis(int i){return i==0?JPH::Vec3::sAxisX():i==1?JPH::Vec3::sAxisY():JPH::Vec3::sAxisZ();}
 JPH::Vec3 InvI(const JPH::Body &b,JPH::Vec3 v) const {return b.IsDynamic()?b.GetMotionPropertiesUnchecked()->MultiplyWorldSpaceInverseInertiaByVector(b.GetRotation(),v):JPH::Vec3::sZero();}
 float InvM(const JPH::Body &b) const {return b.IsDynamic()?b.GetMotionPropertiesUnchecked()->GetInverseMass():0;}
 void Build(){
  auto pb=mBody2->GetCenterOfMassTransform()*LocalB.GetTranslation();
  JPH::Vec3 ra(pb-mBody1->GetCenterOfMassPosition()),rb(pb-mBody2->GetCenterOfMassPosition());
  auto q=mBody1->GetRotation()*LocalA.GetQuaternion();
  for(int i=0;i<5;i++){
   Lin[i]=i<2?q*Axis(i):JPH::Vec3::sZero();
   AngA[i]=i<2?ra.Cross(Lin[i]):Axis(i-2);
   AngB[i]=i<2?rb.Cross(Lin[i]):Axis(i-2);
   IA[i]=InvI(*mBody1,AngA[i]);IB[i]=InvI(*mBody2,AngB[i]);
  }
  Valid=true;
  const float invMass=InvM(*mBody1)+InvM(*mBody2);
  for(int i=0;i<5;i++)for(int j=0;j<=i;j++){
   double v=double(invMass)*Dot(Lin[i],Lin[j])+Dot(AngA[i],IA[j])+Dot(AngB[i],IB[j]);
   for(int k=0;k<j;k++)v-=L[i][k]*L[j][k];
   if(i==j){if(!(v>1.e-12)){Valid=false;return;}L[i][j]=sqrt(v);}else L[i][j]=v/L[j][j];
  }
 }
 bool Solve(const float rhs[5],float x[5])const{
  if(!Valid)return false;
  double y[5]={};
  for(int i=0;i<5;i++){double v=rhs[i];for(int k=0;k<i;k++)v-=L[i][k]*y[k];y[i]=v/L[i][i];}
  for(int i=4;i>=0;i--){double v=y[i];for(int k=i+1;k<5;k++)v-=L[k][i]*x[k];x[i]=float(v/L[i][i]);}return true;
 }
 void Apply(const float step[5],bool position){
  auto linear=JPH::Vec3::sZero(),a=linear,b=linear;
  for(int i=0;i<5;i++){linear+=step[i]*Lin[i];a+=step[i]*IA[i];b+=step[i]*IB[i];}
  if(mBody1->IsDynamic()){if(position){mBody1->SubPositionStep(InvM(*mBody1)*linear);mBody1->SubRotationStep(a);}else {auto mp=mBody1->GetMotionPropertiesUnchecked();mp->SubLinearVelocityStep(InvM(*mBody1)*linear);mp->SubAngularVelocityStep(a);}}
  if(mBody2->IsDynamic()){if(position){mBody2->AddPositionStep(InvM(*mBody2)*linear);mBody2->AddRotationStep(b);}else {auto mp=mBody2->GetMotionPropertiesUnchecked();mp->AddLinearVelocityStep(InvM(*mBody2)*linear);mp->AddAngularVelocityStep(b);}}
 }
 JPH::Ref<JPH::SixDOFConstraint> Native;JPH::Mat44 LocalA,LocalB;
 JPH::Vec3 Lin[5],AngA[5],AngB[5],IA[5],IB[5];JPH::Vec3 VelocityLin[2]={JPH::Vec3::sZero(),JPH::Vec3::sZero()};
 double L[5][5]={};float Lambda[5]={};bool Valid=false;
};


}

