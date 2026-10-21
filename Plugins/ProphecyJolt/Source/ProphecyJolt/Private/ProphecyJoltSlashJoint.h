#pragma once
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/StateRecorder.h>

namespace ProphecyJolt {
// A slash has one locked translation (blade thickness) and two locked swings.
// Solve those three coupled rows together at the wound. Twist, blade travel,
// their limits and friction remain with the normal SixDOF joint.
class FSlashJoint final : public JPH::TwoBodyConstraint {
public:
 FSlashJoint(JPH::SixDOFConstraint& native,const JPH::SixDOFConstraintSettings& settings)
 : TwoBodyConstraint(*native.GetBody1(),*native.GetBody2(),settings),Native(&native),
   LocalA(native.GetConstraintToBody1Matrix()),LocalB(native.GetConstraintToBody2Matrix()) { Build(); }
 bool HasSolvableMassMatrix() const {return Valid;}
 JPH::SixDOFConstraint& GetNative() const {return *Native;}
 JPH::Vec3 GetLinearImpulse() const {return Native->GetTotalWorldSpaceLinearImpulse()+VelocityAxes[0]*Lambda[0];}
 JPH::Vec3 GetAngularImpulse() const {return Native->GetTotalWorldSpaceAngularImpulse()+VelocityAxes[1]*Lambda[1]+VelocityAxes[2]*Lambda[2];}
 JPH::EConstraintSubType GetSubType() const override {return JPH::EConstraintSubType::User4;}
 void NotifyShapeChanged(const JPH::BodyID& id,JPH::Vec3Arg d) override {
  Native->NotifyShapeChanged(id,d);LocalA=Native->GetConstraintToBody1Matrix();LocalB=Native->GetConstraintToBody2Matrix();
 }
 void ResetWarmStart() override {Native->ResetWarmStart();for(float& v:Lambda)v=0;}
 void SetupVelocityConstraint(float dt) override {
  Native->SetupVelocityConstraint(dt);Build();
  for(int i=0;i<3;i++)VelocityAxes[i]=i==0?Lin[i]:AngA[i];
 }
 void WarmStartVelocityConstraint(float ratio) override {
  Native->WarmStartVelocityConstraint(ratio);for(float& v:Lambda)v=Valid?v*ratio:0;Apply(Lambda,false);
 }
 bool SolveVelocityConstraint(float dt) override {
  bool changed=Native->SolveVelocityConstraint(dt);float rhs[3],step[3];
  auto va=mBody1->GetLinearVelocity(),vb=mBody2->GetLinearVelocity();
  auto wa=mBody1->GetAngularVelocity(),wb=mBody2->GetAngularVelocity();
  for(int i=0;i<3;i++)rhs[i]=-(Lin[i].Dot(vb-va)+AngB[i].Dot(wb)-AngA[i].Dot(wa));
  if(!Solve(rhs,step))return changed;
  for(int i=0;i<3;i++)Lambda[i]+=step[i];Apply(step,false);return true;
 }
 bool SolvePositionConstraint(float dt,float beta) override {
  // Full correction for the hard blade-edge stop as well as the locked plane.
  // This runs inside the existing iterations; contacts still solve afterward.
  bool changed=Native->SolvePositionConstraint(dt,1.f);Build();
  auto pa=mBody1->GetCenterOfMassTransform()*LocalA.GetTranslation();
  auto pb=mBody2->GetCenterOfMassTransform()*LocalB.GetTranslation();
  auto qa=mBody1->GetRotation()*LocalA.GetQuaternion(),qb=mBody2->GetRotation()*LocalB.GetQuaternion();
  auto a=qa*JPH::Vec3::sAxisX(),b=qb*JPH::Vec3::sAxisX();
  auto cross=a.Cross(b);float sine=cross.Length();
  auto error=sine>1.e-6f?cross*(atan2f(sine,a.Dot(b))/sine):cross;
  float rhs[3]={-JPH::Vec3(pb-pa).Dot(Lin[0]),-error.Dot(AngA[1]),-error.Dot(AngA[2])},step[3];
  if(!Solve(rhs,step))return changed;Apply(step,true);return true;
 }
 JPH::Mat44 GetConstraintToBody1Matrix() const override {return LocalA;}
 JPH::Mat44 GetConstraintToBody2Matrix() const override {return LocalB;}
 JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings() const override {return Native->GetConstraintSettings();}
 void SaveState(JPH::StateRecorder& s) const override {TwoBodyConstraint::SaveState(s);Native->SaveState(s);for(float v:Lambda)s.Write(v);}
 void RestoreState(JPH::StateRecorder& s) override {TwoBodyConstraint::RestoreState(s);Native->RestoreState(s);for(float& v:Lambda)s.Read(v);}
private:
 static double Dot(JPH::Vec3 a,JPH::Vec3 b) {return double(a.GetX())*b.GetX()+double(a.GetY())*b.GetY()+double(a.GetZ())*b.GetZ();}
 JPH::Vec3 InvI(const JPH::Body& b,JPH::Vec3 v) const {return b.IsDynamic()?b.GetMotionPropertiesUnchecked()->MultiplyWorldSpaceInverseInertiaByVector(b.GetRotation(),v):JPH::Vec3::sZero();}
 float InvM(const JPH::Body& b) const {return b.IsDynamic()?b.GetMotionPropertiesUnchecked()->GetInverseMass():0;}
 void Build() {
  auto pb=mBody2->GetCenterOfMassTransform()*LocalB.GetTranslation();
  JPH::Vec3 ra(pb-mBody1->GetCenterOfMassPosition()),rb(pb-mBody2->GetCenterOfMassPosition());
  auto q=mBody1->GetRotation()*LocalA.GetQuaternion();
  Lin[0]=q*JPH::Vec3::sAxisX();Lin[1]=Lin[2]=JPH::Vec3::sZero();
  AngA[0]=ra.Cross(Lin[0]);AngB[0]=rb.Cross(Lin[0]);
  AngA[1]=AngB[1]=q*JPH::Vec3::sAxisY();AngA[2]=AngB[2]=q*JPH::Vec3::sAxisZ();
  for(int i=0;i<3;i++){IA[i]=InvI(*mBody1,AngA[i]);IB[i]=InvI(*mBody2,AngB[i]);}
  Valid=true;float invMass=InvM(*mBody1)+InvM(*mBody2);
  for(int i=0;i<3;i++)for(int j=0;j<=i;j++) {
   double v=double(invMass)*Dot(Lin[i],Lin[j])+Dot(AngA[i],IA[j])+Dot(AngB[i],IB[j]);
   for(int k=0;k<j;k++)v-=L[i][k]*L[j][k];
   if(i==j){if(!(v>1.e-12)){Valid=false;return;}L[i][j]=sqrt(v);}else L[i][j]=v/L[j][j];
  }
 }
 bool Solve(const float rhs[3],float x[3]) const {
  if(!Valid)return false;double y[3]={};
  for(int i=0;i<3;i++){double v=rhs[i];for(int k=0;k<i;k++)v-=L[i][k]*y[k];y[i]=v/L[i][i];}
  for(int i=2;i>=0;i--){double v=y[i];for(int k=i+1;k<3;k++)v-=L[k][i]*x[k];x[i]=float(v/L[i][i]);}return true;
 }
 void Apply(const float step[3],bool position) {
  auto linear=JPH::Vec3::sZero(),a=linear,b=linear;
  for(int i=0;i<3;i++){linear+=step[i]*Lin[i];a+=step[i]*IA[i];b+=step[i]*IB[i];}
  if(mBody1->IsDynamic()){if(position){mBody1->SubPositionStep(InvM(*mBody1)*linear);mBody1->SubRotationStep(a);}else{auto mp=mBody1->GetMotionPropertiesUnchecked();mp->SubLinearVelocityStep(InvM(*mBody1)*linear);mp->SubAngularVelocityStep(a);}}
  if(mBody2->IsDynamic()){if(position){mBody2->AddPositionStep(InvM(*mBody2)*linear);mBody2->AddRotationStep(b);}else{auto mp=mBody2->GetMotionPropertiesUnchecked();mp->AddLinearVelocityStep(InvM(*mBody2)*linear);mp->AddAngularVelocityStep(b);}}
 }
 JPH::Ref<JPH::SixDOFConstraint> Native;JPH::Mat44 LocalA,LocalB;
 JPH::Vec3 Lin[3],AngA[3],AngB[3],IA[3],IB[3],VelocityAxes[3];
 double L[3][3]={};float Lambda[3]={};bool Valid=false;
};
}
