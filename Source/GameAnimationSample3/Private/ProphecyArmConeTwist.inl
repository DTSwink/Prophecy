// Included inside ProphecyArmCone. Separate allocations preserve Live Coding state layouts.
struct FTwistConfig { double Limit=90,Strength=100,Damping=20; };
struct FTwistArm
{
    FQuat Reference=FQuat::Identity;
    FVector LocalAxis=FVector::ForwardVector,LocalRadial=FVector::UpVector;
    double AcceptedAngle=0,Offset=0,Velocity=0;
    bool Ready=false;
};
struct FTwistState { FTwistArm Arm[2]; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTwistConfig> TwistConfigs,TwistBaselines;
// Separate configuration keeps retained Live Coding allocations unchanged.
static TMap<TWeakObjectPtr<const AProphecyAgent>,double> WristRollStrengths,WristRollBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTwistState> TwistStates;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTwistArm> WristIdleReferences;
// Separate allocation from the rejected 3D/body-avoidance solver for Live Coding.
struct FWristRecoilMotion
{
    FQuat Start=FQuat::Identity;
    double Yaw=0,Elevation=0,YawVelocity=0,ElevationVelocity=0,ReleaseYaw=0,RollVelocity=0;
    bool Releasing=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FWristRecoilMotion> WristRecoilMotions;
#if WITH_EDITOR
static TAutoConsoleVariable<int32> TwistAudit(TEXT("Prophecy.ArmCone.TwistAudit"),0,TEXT("Opt-in right wrist angle/branch diagnostic."));
#endif

static bool SeedTwist(FTwistArm& S,const FTransform& Lower,const FTransform& Hand)
{
    const FVector Axis=(Hand.GetLocation()-Lower.GetLocation()).GetSafeNormal();
    if(Axis.IsNearlyZero()) return false;
    S.Reference=Hand.GetRotation();
    // Published component poses are already root local. Keep the target upright
    // with that root instead of inheriting pelvis/spine lean.
    S.LocalAxis=FVector::UpVector;
    const FVector Basis=FMath::Abs(S.LocalAxis.Y)<.9?FVector::RightVector:FVector::UpVector;
    const FVector Forward=(Basis-S.LocalAxis*FVector::DotProduct(Basis,S.LocalAxis)).GetSafeNormal();
    S.LocalRadial=S.Reference.UnrotateVector(Forward); // hand-local forward, overridden by blade axis when equipped
    S.Ready=true;return true;
}
bool NeedsWristIdleReference(const AProphecyAgent* A)
{
    return !TwistConfigs.IsEmpty() && TwistConfigs.Contains(A) && Recoveries.Contains(A)
        && !AttackHolds.Contains(A) && !WristIdleReferences.Contains(A);
}
void SetWristIdleReference(const AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<FTransform> Idle)
{
    if(!NeedsWristIdleReference(A))return;
    const int32 Lower=Names.IndexOfByKey(FName(TEXT("lowerarm_r"))),Hand=Names.IndexOfByKey(FName(TEXT("hand_r")));
    if(!Idle.IsValidIndex(Lower)||!Idle.IsValidIndex(Hand))return;
    FTwistArm Reference;
    if(SeedTwist(Reference,Idle[Lower],Idle[Hand]))
    {
        if(const auto* Sword=A->GetHeldSword())
        {
            TInlineComponentArray<UStaticMeshComponent*> Meshes;Sword->GetComponents(Meshes);
            for(const auto* Mesh:Meshes)if(Mesh && Mesh->GetStaticMesh() && (Mesh->GetFName()==TEXT("sword") || Meshes.Num()==1))
            {
                const FBox B=Mesh->GetStaticMesh()->GetBoundingBox();const FVector Size=B.GetSize();
                const int32 I=Size.X>Size.Y?(Size.X>Size.Z?0:2):(Size.Y>Size.Z?1:2);
                FVector P=B.GetCenter(),Q=P;P[I]=B.Min[I];Q[I]=B.Max[I];
                P=A->SwordGripTransform.TransformPosition(P);Q=A->SwordGripTransform.TransformPosition(Q);
                if(P.SizeSquared()>Q.SizeSquared())Swap(P,Q);
                const FVector Direction=(Q-P).GetSafeNormal();
                if(!Direction.IsNearlyZero() && FVector::CrossProduct(Reference.Reference.RotateVector(Direction),Reference.LocalAxis).SizeSquared()>1.e-8)
                    Reference.LocalRadial=Direction;
                break;
            }
        }
        WristIdleReferences.Add(A,Reference);
#if WITH_EDITOR
        if(TwistAudit.GetValueOnGameThread() && A->IsPlayerControlled())
            UE_LOG(LogTemp,Display,TEXT("WristIdleReference q=%.9f,%.9f,%.9f,%.9f axis=%.9f,%.9f,%.9f"),
                Reference.Reference.X,Reference.Reference.Y,Reference.Reference.Z,Reference.Reference.W,
                Reference.LocalAxis.X,Reference.LocalAxis.Y,Reference.LocalAxis.Z);
#endif
    }
}
// Signed rotation about root-up, and elevation in its perpendicular
// plane. The yaw sign comes from the blade direction, never quaternion winding.
static FVector2D WristAngles(const FTwistArm& S,const FQuat& Q,double NearYaw=0)
{
    const FVector Up=S.LocalAxis,Aim=Q.RotateVector(S.LocalRadial);
    const FVector Idle=S.Reference.RotateVector(S.LocalRadial);
    const FVector Forward=(Idle-Up*FVector::DotProduct(Idle,Up)).GetSafeNormal();
    const FVector Flat=Aim-Up*FVector::DotProduct(Aim,Up);
    const double Yaw=Flat.SizeSquared()>1.e-10?
        FMath::Atan2(FVector::DotProduct(Up,FVector::CrossProduct(Forward,Flat)),FVector::DotProduct(Forward,Flat)):NearYaw;
    return FVector2D(NearYaw+FMath::UnwindRadians(Yaw-NearYaw),FMath::Asin(FMath::Clamp(FVector::DotProduct(Aim,Up),-1.,1.)));
}
static FVector WristDirection(const FTwistArm& S,double Yaw,double Elevation)
{
    const FVector Idle=S.Reference.RotateVector(S.LocalRadial),Up=S.LocalAxis;
    const FVector Forward=(Idle-Up*FVector::DotProduct(Idle,Up)).GetSafeNormal();
    return FQuat(Up,Yaw).RotateVector(Forward)*FMath::Cos(Elevation)+Up*FMath::Sin(Elevation);
}
static FWristRecoilMotion SeedWristMotion(const FTwistArm& S,const FQuat& Q,bool Recoil=true)
{
    FWristRecoilMotion M;M.Start=Q;
    const FVector2D Angles=WristAngles(S,Q);M.Yaw=Angles.X;M.Elevation=Angles.Y;
    // Right wrist: a backward blade returns around the outside of the arm,
    // not along the shorter inward arc through the torso. Same orientation, different winding.
    if(Recoil && M.Yaw<-UE_HALF_PI)M.Yaw+=UE_TWO_PI;
    return M;
}
static void AdvanceWristAngle(double& Angle,double Goal,double& Velocity,const FTwistConfig& C,double Dt)
{
    const double Error=Goal-Angle,Damping=FMath::Max(C.Damping,2*FMath::Sqrt(C.Strength));
    Velocity=(Velocity+C.Strength*Error*Dt)/(1+Damping*Dt+C.Strength*Dt*Dt);
    // Do not overshoot or reverse an already completed return.
    const double Step=FMath::Clamp(Velocity*Dt,FMath::Min(0.,Error),FMath::Max(0.,Error));
    Angle+=Step;if(FMath::Abs(Step-Error)<1.e-10)Velocity=0;
}
static FQuat AdvanceRootWrist(FWristRecoilMotion& M,const FTwistArm& S,const FQuat& Raw,const FTwistConfig& C,double Weight,double Dt,double RollStrength=-1)
{
    if(Weight<=0 || Dt<=0)return Raw;
    const double IdleElevation=WristAngles(S,S.Reference).Y;
    const FVector Idle=S.Reference.RotateVector(S.LocalRadial),RawAim=Raw.RotateVector(S.LocalRadial);
    if(C.Strength>0)
    {
        // Follow the live NN pose, restricted to the idle cone. Never latch the
        // outgoing pose or freeze at the first angle that enters the cone.
        const double Error=FMath::Acos(FMath::Clamp(FVector::DotProduct(RawAim,Idle),-1.,1.));
        const double Limit=FMath::DegreesToRadians(C.Limit);
        const FQuat Swing=FQuat::FindBetweenNormals(Idle,RawAim);
        const FVector GoalAim=Error>Limit?FQuat::Slerp(FQuat::Identity,Swing,Limit/Error).RotateVector(Idle):RawAim;
        const FQuat Goal=(FQuat::FindBetweenNormals(RawAim,GoalAim)*Raw).GetNormalized();
        const FVector2D Angles=WristAngles(S,Goal);
        AdvanceWristAngle(M.Yaw,Angles.X,M.YawVelocity,C,Dt);
        AdvanceWristAngle(M.Elevation,Angles.Y,M.ElevationVelocity,C,Dt);
    }
    else
    {
        const FVector2D Proposed=WristAngles(S,Raw,M.Yaw);
        M.Yaw+=(Proposed.X-M.Yaw)/(FMath::Abs(Proposed.X)>FMath::Abs(M.Yaw)?1+C.Damping*Dt:1);
        M.Elevation+=(Proposed.Y-M.Elevation)/(FMath::Abs(Proposed.Y-IdleElevation)>FMath::Abs(M.Elevation-IdleElevation)?1+C.Damping*Dt:1);
    }
    double Yaw=M.Yaw,Elevation=M.Elevation;
    if(Weight<1)
    {
        if(!M.Releasing){M.ReleaseYaw=M.Yaw;M.Releasing=true;}
        const FVector2D Proposed=WristAngles(S,Raw,M.ReleaseYaw);M.ReleaseYaw=Proposed.X;
        Yaw=FMath::Lerp(Proposed.X,M.Yaw,Weight);Elevation=FMath::Lerp(Proposed.Y,M.Elevation,Weight);
    }
    // Carry axial roll toward the live NN too, rather than holding it until
    // release. Align the pointing directions first so roll cannot steer the blade.
    const FVector HeldAim=WristDirection(S,M.Yaw,M.Elevation),Aim=WristDirection(S,Yaw,Elevation);
    const FQuat Previous=(FQuat::FindBetweenNormals(M.Start.RotateVector(S.LocalRadial),HeldAim)*M.Start).GetNormalized();
    const FQuat Target=(FQuat::FindBetweenNormals(RawAim,HeldAim)*Raw).GetNormalized();
    FTwistConfig RollConfig=C;RollConfig.Strength=RollStrength<0?C.Strength:RollStrength;
    if(RollConfig.Strength>0)
    {
        FQuat Delta=(Target*Previous.Inverse()).GetNormalized();if(Delta.W<0)Delta=Delta*-1.;
        const double RollError=2*FMath::Atan2(FVector::DotProduct(FVector(Delta.X,Delta.Y,Delta.Z),HeldAim),Delta.W);
        double RollStep=0;AdvanceWristAngle(RollStep,RollError,M.RollVelocity,RollConfig,Dt);
        M.Start=(FQuat(HeldAim,RollStep)*Previous).GetNormalized();
    }
    else { M.Start=Target;M.RollVelocity=0; }
    const FQuat Held=(FQuat::FindBetweenNormals(HeldAim,Aim)*M.Start).GetNormalized();
    const FQuat Free=(FQuat::FindBetweenNormals(RawAim,Aim)*Raw).GetNormalized();
    return FQuat::Slerp(Free,Held,Weight).GetNormalized();
}
static void ApplyTwist(AProphecyAgent* A,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,
    const int32* Indices,double Weight,double Dt)
{
    if(TwistConfigs.IsEmpty() || Dt<=0)return;
    const auto* C=TwistConfigs.Find(A);if(!C)return;
    auto& S=TwistStates.FindOrAdd(A).Arm[1];const int32 H=Indices[5];
    if(!S.Ready){const auto* Idle=WristIdleReferences.Find(A);if(!Idle)return;S=*Idle;}
    const FQuat Raw=Current[H].GetRotation();
    auto* M=WristRecoilMotions.Find(A);
    if(!M)M=&WristRecoilMotions.Add(A,SeedWristMotion(S,Previous[H].GetRotation(),C->Strength>0));
    const double* Roll=WristRollStrengths.Find(A);
    const FQuat Accepted=AdvanceRootWrist(*M,S,Raw,*C,Weight,Dt,Roll?*Roll:-1);
    Current[H].SetRotation(Accepted);
#if WITH_EDITOR
    if(TwistAudit.GetValueOnGameThread() && A->IsPlayerControlled())
    {
        const FVector2D Angles=WristAngles(S,Accepted);
        UE_LOG(LogTemp,Display,TEXT("WristSplit time=%.9f weight=%.6f yaw=%.6f elevation=%.6f idleElevation=%.6f"),
            A->GetWorld()->GetTimeSeconds(),Weight,FMath::RadiansToDegrees(Angles.X),FMath::RadiansToDegrees(Angles.Y),FMath::RadiansToDegrees(WristAngles(S,S.Reference).Y));
    }
#endif
}

static void DrawTwist(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<FTransform> Pose,const FQuat& Root,float Length,float Duration,bool Active)
{
    const auto* C=TwistConfigs.Find(A);const auto* S=WristIdleReferences.Find(A);
    if(!C || !S)return;
    const int32 Hand=Names.IndexOfByKey(FName(TEXT("hand_r")));
    if(!Pose.IsValidIndex(Hand))return;
    const FQuat Idle=Root*S->Reference;
    const FVector Center=Pose[Hand].GetLocation(),Ref=Idle.RotateVector(S->LocalRadial);
    const double Error=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Ref,Pose[Hand].GetRotation().RotateVector(S->LocalRadial)),-1.,1.)));
    const FColor Color=!Active?FColor::Silver:Error>C->Limit?FColor::Red:FColor::Green;
    const double Limit=FMath::DegreesToRadians(C->Limit);
    DrawDebugCone(A->GetWorld(),Center,Ref,Length*.35,Limit,Limit,16,FColor::Yellow,false,Duration,0,.6f);
    DrawDebugLine(A->GetWorld(),Center,Center+Ref*Length*.35,FColor::Cyan,false,Duration,0,1.f);
    DrawDebugLine(A->GetWorld(),Center,Center+Pose[Hand].GetRotation().RotateVector(S->LocalRadial)*Length*.35,Color,false,Duration,0,2.f);
    DrawDebugString(A->GetWorld(),Center,FString::Printf(TEXT("R idle direction %.1f / %.1f"),Error,C->Limit),nullptr,Color,Duration,false,.8f);
}
