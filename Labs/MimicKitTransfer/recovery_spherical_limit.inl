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
        float hz=std::getenv("CAND_LIMIT_HZ")?std::atof(std::getenv("CAND_LIMIT_HZ")):8.f;
        part.CalculateConstraintPropertiesWithSettingsForLimit(dt,*mBody1,*mBody2,axis,0,error,SpringSettings(ESpringMode::FrequencyAndDamping,hz,1));
    }
    void ResetWarmStart()override{part.Deactivate();}
    void WarmStartVelocityConstraint(float ratio)override{if(part.IsActive())part.WarmStart(*mBody1,*mBody2,ratio);}
    bool SolveVelocityConstraint(float)override{return part.IsActive()&&part.SolveVelocityConstraint(*mBody1,*mBody2,axis,-1.e10f,0);}
    bool SolvePositionConstraint(float,float)override{return false;}
};
