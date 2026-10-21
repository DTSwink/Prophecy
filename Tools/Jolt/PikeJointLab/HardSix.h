#pragma once
class HardSix final : public JPH::TwoBodyConstraint {
 JPH::Ref<JPH::SixDOFConstraint> N;
public:
 HardSix(JPH::SixDOFConstraint& n,const JPH::SixDOFConstraintSettings& s):TwoBodyConstraint(*n.GetBody1(),*n.GetBody2(),s),N(&n){}
 JPH::EConstraintSubType GetSubType()const override{return JPH::EConstraintSubType::User4;}
 void NotifyShapeChanged(const JPH::BodyID& id,JPH::Vec3Arg d)override{N->NotifyShapeChanged(id,d);}
 void ResetWarmStart()override{N->ResetWarmStart();}
 void SetupVelocityConstraint(float dt)override{N->SetupVelocityConstraint(dt);}
 void WarmStartVelocityConstraint(float r)override{N->WarmStartVelocityConstraint(r);}
 bool SolveVelocityConstraint(float dt)override{return N->SolveVelocityConstraint(dt);}
 bool SolvePositionConstraint(float dt,float)override{return N->SolvePositionConstraint(dt,1.f);}
 JPH::Mat44 GetConstraintToBody1Matrix()const override{return N->GetConstraintToBody1Matrix();}
 JPH::Mat44 GetConstraintToBody2Matrix()const override{return N->GetConstraintToBody2Matrix();}
 JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings()const override{return N->GetConstraintSettings();}
 void SaveState(JPH::StateRecorder& s)const override{TwoBodyConstraint::SaveState(s);N->SaveState(s);}
 void RestoreState(JPH::StateRecorder& s)override{TwoBodyConstraint::RestoreState(s);N->RestoreState(s);}
};
