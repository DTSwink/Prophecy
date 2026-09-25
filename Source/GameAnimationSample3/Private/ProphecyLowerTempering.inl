// Included after policy blend math. Previous is the previous PUBLISHED state in
// its own root frame, not CurStateBuffer rebased to keep positions world-stationary.
#if WITH_EDITOR
static TAutoConsoleVariable<int32> CVarRecoveryCleanSource(
    TEXT("Prophecy.Recovery.CleanSource"),1,
    TEXT("Editor comparison: preserve the policy hinge before pinning during calf/regional recovery."));
static TAutoConsoleVariable<int32> CVarRecoveryPolePresentation(
    TEXT("Prophecy.Recovery.PolePresentation"),1,
    TEXT("Editor comparison: 1 keeps procedural recovery legs in presentation; 0 feeds reconstruction back into the policy (legacy)."));
static TAutoConsoleVariable<int32> CVarRecoveryPoleWindow(
    TEXT("Prophecy.Recovery.PoleWindow"),1,
    TEXT("Editor comparison: independent tick-based recovery pole window; 0 retains tempering-only smoothing."));
static TAutoConsoleVariable<int32> CVarTemperingSupportSource(
    TEXT("Prophecy.Tempering.SupportSource"),1,
    TEXT("Editor recovery comparison: 1 follows NN hinge near the floor; 0 uses the previous-pose hinge throughout."));
static TAutoConsoleVariable<int32> CVarTemperingKneePlane(
    TEXT("Prophecy.Tempering.KneePlane"),3,
    TEXT("Editor recovery comparison: 3 transports normalized source bend direction (trial); 1 restores the original lateral stance plane; 0 forces zero lateral offset."));
static TAutoConsoleVariable<int32> CVarTemperingCalfContinuity(
    TEXT("Prophecy.Tempering.CalfContinuity"),1,
    TEXT("Editor comparison: 1 carries published calf twist during feet tempering; 0 re-decodes it immediately."));
static TAutoConsoleVariable<int32> CVarTemperingPoleSmoothing(
    TEXT("Prophecy.Tempering.PoleSmoothing"),1,
    TEXT("Editor comparison: 1 limits recovery knee steering in the foot frame; 0 preserves the unsmoothed target."));
static TAutoConsoleVariable<int32> CVarTemperingPoleTrace(
    TEXT("Prophecy.Tempering.PoleTrace"),0,
    TEXT("Capture this many possessed-agent recovery legs, including the exact unsmoothed and smoothed targets."));
#endif
static bool UsePresentationRecovery()
{
#if WITH_EDITOR
    return CVarRecoveryPolePresentation.GetValueOnGameThread()!=0;
#else
    return true;
#endif
}

// A procedural recovery is a target-pose constraint, not a new NN action.
// Keep the coherent pre-solve ankle/thigh in recurrence. Preserve any later
// pelvis-inertia adjustment instead of overwriting it with an older pose.
// Plain, uninitialized storage: no construction/copy/math outside recovery.
struct FRecoveryPolicyLegs
{
    float Source[2][9],Solved[2][9];
    static void Capture(const float* Pose,float (&Out)[2][9])
    {
        for(int32 I=0;I<2;++I)
        {
            FMemory::Memcpy(Out[I],Pose+9+16*I,3*sizeof(float));
            FMemory::Memcpy(Out[I]+3,Pose+18+16*I,6*sizeof(float));
        }
    }
    void Restore(float* Policy) const
    {
        for(int32 I=0;I<2;++I)
        {
            float* P=Policy+9+16*I;float* R=Policy+18+16*I;
            if(!FMemory::Memcmp(P,Solved[I],3*sizeof(float))) FMemory::Memcpy(P,Source[I],3*sizeof(float));
            else WriteStateVec3(Policy,9+16*I,ReadStateVec3(Policy,9+16*I)+ReadStateVec3(Source[I],0)-ReadStateVec3(Solved[I],0));
            if(!FMemory::Memcmp(R,Solved[I]+3,6*sizeof(float))) FMemory::Memcpy(R,Source[I]+3,6*sizeof(float));
            else WriteRot6(Multiply(Multiply(MatrixFromRot6(Source[I]+3),Transpose(MatrixFromRot6(Solved[I]+3))),MatrixFromRot6(R)),R);
        }
    }
};
static bool NeedsTemperedLegReconstruction(const ProphecyLowerTempering::FSettings& Pelvis,const ProphecyLowerTempering::FSettings& Foot)
{
    return !Foot.FeetAreIdentity() || Pelvis.PelvisTranslation!=1.f || Pelvis.PelvisTranslationZ!=1.f || Pelvis.PelvisRotation!=1.f;
}
void TemperLowerPose(const ProphecyLowerTempering::FSettings& S, const float* Previous, float* Predicted,
    const ProphecyLowerTempering::FSettings* Right=nullptr)
{
    auto Position = [&](int32 Offset, float XY, float Z)
    {
        // Lower pose coordinates are Z-up (unlike the mover's Y-up coordinates).
        for (int32 Axis=0;Axis<3;++Axis)
        {
            const float Follow=Axis==2 ? Z : XY;
            if (Follow==1.f) continue;
            Predicted[Offset+Axis]=Follow==0.f ? Previous[Offset+Axis]
                : FMath::Lerp(Previous[Offset+Axis],Predicted[Offset+Axis],Follow);
        }
    };
    auto Rotation = [&](int32 Offset, float Follow)
    {
        if (Follow == 1.f) return;
        if (Follow == 0.f) FMemory::Memcpy(Predicted+Offset, Previous+Offset, 6*sizeof(float));
        else BlendStateRotation(Predicted, Previous, Offset, 1.f-Follow);
    };
    Position(0, S.PelvisTranslation, S.PelvisTranslationZ); Rotation(3, S.PelvisRotation);
    for (int32 Offset : {9,25})
    {
        const auto& Foot=Offset==25 && Right ? *Right : S;
        Position(Offset, Foot.FeetTranslation, Foot.FeetTranslationZ);
        Rotation(Offset+3, Foot.FeetRotation);
        // Thigh orientation is solved from untouched source hinge frames below.
        // Independently blending it here corrupts the source bend direction.
        if (Foot.FeetRotation != 1.f)
            Predicted[Offset+15] = Foot.FeetRotation == 0.f ? Previous[Offset+15]
                : FMath::Lerp(Previous[Offset+15], Predicted[Offset+15], Foot.FeetRotation);
    }
}

FQuat TemperCalfRotation(const FQuat& Previous,const FQuat& Decoded,const FVector& LocalAxis,float Follow)
{
    if (Follow>=1.f) return Decoded;
    const FVector Axis=LocalAxis.GetSafeNormal();
    // The ankle fixes the calf's aim, but does not fix its twist. Transport the
    // actual published calf to that aim before following the new decoder's roll.
    // Slerp now acts about one common axis, so it cannot detach the ankle.
    const FQuat Carried=(FQuat::FindBetweenNormals(Previous.RotateVector(Axis),Decoded.RotateVector(Axis))*Previous).GetNormalized();
    return Follow<=0.f ? Carried : FQuat::Slerp(Carried,Decoded,Follow).GetNormalized();
}

void ResolveTemperedLeg(const ProphecyLowerTempering::FSettings& S,const float* Previous,
    const FPelvisLegGeometry& G,float* Target,int32 Offset,
    FVector3f FootForwardLocal=FVector3f(1,0,0),FVector3f FootUpLocal=FVector3f(0,0,1),
    float MinimumReach=0.f,bool bClampOuterReach=true,
    const float* ExperimentNNSource=nullptr)
{
    constexpr int32 ExperimentMode=7; // Exact first September20 comparison, selected by user.
    const FVector3f Pelvis=ReadStateVec3(Target,0);
    const FMat3f PelvisRotation=MatrixFromRot6(Target+3);
    const FVector3f Hip=Pelvis+TransformRow(G.HipOffset,PelvisRotation);
    const FMat3f FootRotation=MatrixFromRot6(Target+Offset+3);
    const FVector3f Toe=TransformRow(SafeNormal(FootForwardLocal),FootRotation);
    const FVector3f FootSide=TransformRow(SafeNormal(FVector3f::CrossProduct(FootUpLocal,FootForwardLocal)),FootRotation);
    const FVector3f FlatToe(Toe.X,Toe.Y,0);
    const FVector3f Forward=SafeNormal(FlatToe,SafeNormal(FVector3f(FootSide.Y,-FootSide.X,0),FVector3f(1,0,0)));
    const FVector3f Side(-Forward.Y,Forward.X,0);
    if (MinimumReach>0.f)
    {
        const FVector3f Delta=ReadStateVec3(Target,Offset)-Hip;
        const FVector3f Sagittal=Delta-Side*FVector3f::DotProduct(Delta,Side);
        if (Sagittal.SizeSquared()<MinimumReach*MinimumReach)
        {
            const FVector3f PriorDelta=ReadStateVec3(Previous,Offset)-ReadStateVec3(Previous,0)
                -TransformRow(G.HipOffset,MatrixFromRot6(Previous+3));
            const FVector3f Fallback=SafeNormal(PriorDelta-Side*FVector3f::DotProduct(PriorDelta,Side),FVector3f(0,0,-1));
            WriteStateVec3(Target,Offset,Hip+Side*FVector3f::DotProduct(Delta,Side)
                +SafeNormal(Sagittal,Fallback)*MinimumReach);
        }
    }
    auto Solve=[&](const float* Source,float* Output,FVector3f* Pole=nullptr)
    {
        ResolvePelvisLeg(ReadStateVec3(Source,0),MatrixFromRot6(Source+3),Pelvis,PelvisRotation,
            G,Output,Offset,Source,false,Pole,MinimumReach,bClampOuterReach);
    };
    // The previous published leg is coherent; raw NN endpoint/thigh pairs
    // can be wildly inconsistent on recovery. Transport this hinge through
    // accepted endpoint changes, without coupling foot pitch to knee orbit.
    float Support=0.f;
    if (ExperimentMode)
    {
        float T=FMath::Clamp((ReadStateVec3(Target,Offset).Z-G.MinimumAnkleZ-.02f)/.10f,0.f,1.f);
        Support=1.f-T*T*(3.f-2.f*T);
    }
    if (ExperimentMode>=2 && Support>0.f && ExperimentNNSource && S.FeetRotation>0.f)
    {
        float SourceFollow=Support*(ExperimentMode==4 ? S.FeetRotation
            : ExperimentMode==5 ? S.FeetRotation*S.FeetRotation : 1.f);
        if (ExperimentMode>=6)
        {
            const float Difference=MatrixToQuat(MatrixFromRot6(Previous+Offset+9)).AngularDistance(
                MatrixToQuat(MatrixFromRot6(ExperimentNNSource+Offset+9)));
            SourceFollow*=S.FeetRotation==0.f ? 0.f : FMath::Min(1.f,FMath::DegreesToRadians(10.f*(ExperimentMode-5))/FMath::Max(Difference,1.e-6f));
        }
        float Source[41]; FMemory::Memcpy(Source,Previous,sizeof(Source));
        for (int32 O : {0,Offset})
            WriteStateVec3(Source,O,FMath::Lerp(ReadStateVec3(Previous,O),ReadStateVec3(ExperimentNNSource,O),SourceFollow));
        for (int32 O : {3,Offset+9}) BlendStateRotation(Source,ExperimentNNSource,O,SourceFollow);
        Solve(Source,Target);
    }
    else
        Solve(Previous,Target);
    if (S.FeetRotation==0.f) return;
    const FVector3f Axis=SafeNormal(ReadStateVec3(Target,Offset)-Hip);
    const FMat3f Thigh=MatrixFromRot6(Target+Offset+9);
    const FVector3f Upper=TransformRow(G.KneeOffset,Thigh);
    const float Along=FVector3f::DotProduct(Upper,Axis);
    const FVector3f Radial=Upper-Axis*Along;
    const float Radius=Radial.Size();
    if (Radius<1.e-6f) return;
    const FVector3f Pole=Radial/Radius;
    const float SideAlong=FVector3f::DotProduct(Axis,Side);
    const FVector3f N0=Side-Axis*SideAlong;
    const float NLength=N0.Size();
    if (NLength<1.e-6f) return;
    const FVector3f N=N0/NLength;
    const FVector3f HingePole=SafeNormal(FVector3f::CrossProduct(Axis,N));
    const float HipFrontQ=-Along*SideAlong/(Radius*NLength);
    // Use one oriented hinge throughout the motion. Crossing hip height must
    // never choose the opposite branch. Undefined/infeasible planes retain the
    // transported frame rather than normalizing a singular direction.
    auto Smooth=[](float X) { X=FMath::Clamp(X,0.f,1.f);return X*X*(3.f-2.f*X); };
    // Raised feet retain the accepted hip-front knee placement. Near the floor,
    // instead align the bend direction with the foot: forcing the knee itself
    // into the hip-front plane makes its pole over-turn as the ankle moves sideways.
    // Interpolate directions on the connected knee circle, not knee positions.
    // Support already eases from 0 at 12cm clearance to 1 at 2cm clearance.
    const float HipFrontAngle=FMath::Asin(FMath::Clamp(HipFrontQ,-1.f,1.f));
    const float Q=Support<=0.f ? HipFrontQ : FMath::Sin(HipFrontAngle*(1.f-Support));
    const float PlaneConfidence=FMath::Lerp(Smooth((1.f-FMath::Abs(HipFrontQ))*4.f),1.f,Support);
    const float Strength=Smooth(FlatToe.SizeSquared()*4.f)*Smooth(NLength*NLength*4.f)
        *PlaneConfidence
        * ((ExperimentMode==1 || ExperimentMode==2) ? 1.f-Support : 1.f);
    if (Strength<1.e-8f) return;
    const float ClampedQ=FMath::Clamp(Q,-1.f,1.f);
    const FVector3f DesiredPole=N*ClampedQ+HingePole*FMath::Sqrt(FMath::Max(0.f,1.f-ClampedQ*ClampedQ));
    const float Angle=FMath::Atan2(FVector3f::DotProduct(Axis,FVector3f::CrossProduct(Pole,DesiredPole)),
        FMath::Clamp(FVector3f::DotProduct(Pole,DesiredPole),-1.f,1.f));
    WriteRot6(Multiply(Thigh,AxisAngleMatrix(Axis,Angle*Strength)),Target+Offset+9);
}


// Post-process the existing geometric solution, not its target construction.
// Carry the previous complete hinge with the foot, then minimally transport it
// to the accepted hip/ankle axis. Only the remaining turn ABOUT that axis is
// limited. This preserves both endpoints, segment lengths and foot rotation.
// The previous published pose is the history: no new timer or persistent state.
static bool SmoothTemperedKneePole(const float* Previous,const FPelvisLegGeometry& G,
    float* Target,int32 Offset,float MaxTurnRadians=FMath::DegreesToRadians(12.f))
{
    const FVector3f Hip=ReadStateVec3(Target,0)+TransformRow(G.HipOffset,MatrixFromRot6(Target+3));
    const FVector3f Axis=SafeNormal(ReadStateVec3(Target,Offset)-Hip);
    const FMat3f Thigh=MatrixFromRot6(Target+Offset+9);
    const FVector3f Upper=TransformRow(G.KneeOffset,Thigh);
    const FVector3f Radial=Upper-Axis*FVector3f::DotProduct(Upper,Axis);
    if (Radial.SizeSquared()<1.e-10f) return false;
    const FVector3f DesiredPole=SafeNormal(Radial);
    const FVector3f OldHip=ReadStateVec3(Previous,0)+TransformRow(G.HipOffset,MatrixFromRot6(Previous+3));
    const FMat3f OldThigh=MatrixFromRot6(Previous+Offset+9);
    const FVector3f OldUpper=TransformRow(G.KneeOffset,OldThigh);
    const FVector3f OldAxis=SafeNormal(ReadStateVec3(Previous,Offset)-OldHip,SafeNormal(OldUpper));
    const FVector3f OldRadial=OldUpper-OldAxis*FVector3f::DotProduct(OldUpper,OldAxis);
    const FVector3f OldPole=OldRadial.SizeSquared()>1.e-10f ? SafeNormal(OldRadial)
        : ProjectToPlane(TransformRow(G.Pole,OldThigh),OldAxis);
    const FMat3f FootChange=Multiply(Transpose(MatrixFromRot6(Previous+Offset+3)),MatrixFromRot6(Target+Offset+3));
    const FVector3f CarriedAxis=SafeNormal(TransformRow(OldAxis,FootChange));
    const FVector3f CarriedPole=SafeNormal(TransformRow(OldPole,FootChange));
    const float Cos=FMath::Clamp(FVector3f::DotProduct(CarriedAxis,Axis),-1.f,1.f);
    const FVector3f Transport=Cos<-1.f+1.e-6f ? -CarriedPole
        : CarriedPole-(CarriedAxis+Axis)*(FVector3f::DotProduct(CarriedPole,Axis)/FMath::Max(1.e-6f,1.f+Cos));
    const FVector3f From=ProjectToPlane(Transport,Axis);
    const float Angle=FMath::Atan2(FVector3f::DotProduct(Axis,FVector3f::CrossProduct(From,DesiredPole)),
        FMath::Clamp(FVector3f::DotProduct(From,DesiredPole),-1.f,1.f));
    if (FMath::Abs(Angle)<=MaxTurnRadians+1.e-7f) return false; // Exact old result for already smooth guidance.
    const float Accepted=FMath::Clamp(Angle,-MaxTurnRadians,MaxTurnRadians);
    WriteRot6(Multiply(Thigh,AxisAngleMatrix(Axis,Accepted-Angle)),Target+Offset+9);
    return true;
}

static bool ApplyTemperedKneePoleRecovery(const AProphecyAgent* Actor,const float* Previous,
    const FPelvisLegGeometry& G,float* Target,int32 Offset,float MaxTurnRadians=FMath::DegreesToRadians(12.f))
{
    bool Limited=false;
#if WITH_EDITOR
    const bool Trace=CVarTemperingPoleTrace.GetValueOnGameThread()>0 && Actor && Actor->IsPlayerControlled();
    float Before[41];if(Trace) FMemory::Memcpy(Before,Target,sizeof(Before));
    if(CVarTemperingPoleSmoothing.GetValueOnGameThread()!=0)
#endif
        Limited=SmoothTemperedKneePole(Previous,G,Target,Offset,MaxTurnRadians);
#if WITH_EDITOR
    if(Trace)
    {
        CVarTemperingPoleTrace->Set(CVarTemperingPoleTrace.GetValueOnGameThread()-1,ECVF_SetByConsole);
        float Candidate[41];FMemory::Memcpy(Candidate,Before,sizeof(Candidate));
        SmoothTemperedKneePole(Previous,G,Candidate,Offset,MaxTurnRadians);
        auto Row=MakeShared<FJsonObject>();
        auto Add=[&](const TCHAR* Key,const float* V,int32 Count){TArray<TSharedPtr<FJsonValue>> A;for(int32 I=0;I<Count;++I) A.Add(MakeShared<FJsonValueNumber>(V[I]));Row->SetArrayField(Key,A);};
        auto Vec=[&](const TCHAR* Key,const FVector3f& V){const float A[]={V.X,V.Y,V.Z};Add(Key,A,3);};
        Add(TEXT("previous"),Previous,41);Add(TEXT("before"),Before,41);Add(TEXT("after"),Candidate,41);
        Vec(TEXT("hip"),G.HipOffset);Vec(TEXT("knee"),G.KneeOffset);Vec(TEXT("pole"),G.Pole);
        Row->SetNumberField(TEXT("offset"),Offset);Row->SetNumberField(TEXT("calf"),G.CalfLength);
        Row->SetNumberField(TEXT("time"),Actor->GetWorld()->GetTimeSeconds());
        Row->SetNumberField(TEXT("max_turn"),MaxTurnRadians);
        FString Line;FJsonSerializer::Serialize(Row,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line));
        FFileHelper::SaveStringToFile(Line+TEXT("\n"),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/RecoveryPoleSmoothing.jsonl")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
    }
#endif
    return Limited;
}

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRecoveryPolicyIsolationTest,
    "Prophecy.NN.LowerTempering.PolicyIsolation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRecoveryPolicyIsolationTest::RunTest(const FString&)
{
    float Source[41]{},Published[41],Policy[41];
    for(int32 I=0;I<41;++I) Source[I]=float(I)*.01f;
    for(int32 O:{3,12,18,28,34}) WriteRot6(AxisAngleMatrix(FVector3f(0,0,1),.17f),Source+O);
    FMemory::Memcpy(Published,Source,sizeof(Source));
    FRecoveryPolicyLegs Saved;FRecoveryPolicyLegs::Capture(Source,Saved.Source);
    for(int32 I=0;I<2;++I)
    {
        WriteStateVec3(Published,9+16*I,ReadStateVec3(Source,9+16*I)+FVector3f(.02f,-.03f,.01f));
        WriteRot6(Multiply(MatrixFromRot6(Source+18+16*I),AxisAngleMatrix(FVector3f(1,0,0),I?.6f:-.7f)),Published+18+16*I);
    }
    FRecoveryPolicyLegs::Capture(Published,Saved.Solved);
    FMemory::Memcpy(Policy,Published,sizeof(Policy));Saved.Restore(Policy);
    TestEqual(TEXT("Pure recovery leaves the coherent policy input bitwise unchanged"),FMemory::Memcmp(Policy,Source,sizeof(Source)),0);
    const FMat3f LaterTurn=AxisAngleMatrix(FVector3f(0,1,0),.23f);
    const FVector3f LaterShift(.04f,.05f,-.02f);
    FMemory::Memcpy(Policy,Published,sizeof(Policy));
    for(int32 I=0;I<2;++I)
    {
        WriteStateVec3(Policy,9+16*I,ReadStateVec3(Policy,9+16*I)+LaterShift);
        WriteRot6(Multiply(MatrixFromRot6(Policy+18+16*I),LaterTurn),Policy+18+16*I);
    }
    Saved.Restore(Policy);
    for(int32 I=0;I<2;++I)
    {
        TestTrue(TEXT("Later pelvis-inertia ankle correction survives"),ReadStateVec3(Policy,9+16*I).Equals(ReadStateVec3(Source,9+16*I)+LaterShift,1.e-6f));
        TestTrue(TEXT("Later noncommuting thigh adjustment survives"),MatrixToQuat(MatrixFromRot6(Policy+18+16*I)).Equals(MatrixToQuat(Multiply(MatrixFromRot6(Source+18+16*I),LaterTurn)),1.e-6));
        TestEqual(TEXT("Foot rotation and toe remain untouched"),FMemory::Memcmp(Policy+12+16*I,Source+12+16*I,6*sizeof(float)),0);
        TestEqual(TEXT("Published reconstruction remains intact"),FMemory::Memcmp(Published+18+16*I,Saved.Solved[I]+3,6*sizeof(float)),0);
    }
    TestEqual(TEXT("Pelvis is never filtered by policy isolation"),FMemory::Memcmp(Policy,Source,9*sizeof(float)),0);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingFootFramePoleTest,
    "Prophecy.NN.LowerTempering.FootFramePoleSmoothing", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingFootFramePoleTest::RunTest(const FString&)
{
    const FPelvisLegGeometry G{FVector3f(0,.1f,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
    float Previous[41]{};
    WriteStateVec3(Previous,0,FVector3f(0,0,.8f));
    WriteStateVec3(Previous,9,FVector3f(.1f,.1f,.08f));
    for(int32 O:{3,12,18,28,34}) WriteRot6(FMat3f(),Previous+O);
    ResolvePelvisLeg(ReadStateVec3(Previous,0),FMat3f(),ReadStateVec3(Previous,0),FMat3f(),G,Previous,9);
    const FVector3f Hip=ReadStateVec3(Previous,0)+G.HipOffset;
    const FVector3f Axis=SafeNormal(ReadStateVec3(Previous,9)-Hip);
    const FMat3f InitialThigh=MatrixFromRot6(Previous+18);
    for(float Angle:{-179.f,-80.f,-12.f,-5.f,0.f,5.f,12.f,80.f,179.f})
    {
        float Target[41],Before[41];FMemory::Memcpy(Target,Previous,sizeof(Target));
        WriteRot6(Multiply(InitialThigh,AxisAngleMatrix(Axis,FMath::DegreesToRadians(Angle))),Target+18);
        FMemory::Memcpy(Before,Target,sizeof(Before));
        SmoothTemperedKneePole(Previous,G,Target,9);
        const FQuat Expected=MatrixToQuat(Multiply(InitialThigh,AxisAngleMatrix(Axis,FMath::DegreesToRadians(FMath::Clamp(Angle,-12.f,12.f)))));
        TestTrue(TEXT("Only excess foot-relative steering is limited"),Expected.Equals(MatrixToQuat(MatrixFromRot6(Target+18)),2.e-5));
        TestEqual(TEXT("Pelvis and foot position/rotation preserved bitwise"),FMemory::Memcmp(Before,Target,18*sizeof(float)),0);
        TestEqual(TEXT("Toe and other leg preserved bitwise"),FMemory::Memcmp(Before+24,Target+24,17*sizeof(float)),0);
        const FVector3f K=Hip+TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        TestTrue(TEXT("Connected calf unchanged"),FMath::Abs((K-ReadStateVec3(Target,9)).Size()-G.CalfLength)<2.e-6f);
        if(FMath::Abs(Angle)<12.f) TestEqual(TEXT("Smooth guidance is exactly unchanged"),FMemory::Memcmp(Before,Target,sizeof(Target)),0);
    }
    // Large common foot/hinge rotations must carry immediately, not acquire a
    // world-space lag. Sweep yaw, pitch and roll, including nearly reversed axes.
    for(int32 I=0;I<=360;++I)
    {
        const FMat3f Change=AxisAngleMatrix(SafeNormal(FVector3f(1,2,3)),FMath::DegreesToRadians(float(I)));
        float Target[41],Before[41];FMemory::Memcpy(Target,Previous,sizeof(Target));
        WriteStateVec3(Target,9,Hip+TransformRow(ReadStateVec3(Previous,9)-Hip,Change));
        WriteRot6(Change,Target+12);WriteRot6(Multiply(InitialThigh,Change),Target+18);
        FMemory::Memcpy(Before,Target,sizeof(Before));
        SmoothTemperedKneePole(Previous,G,Target,9);
        TestEqual(TEXT("Rigid foot-frame motion is unchanged, including full turns"),FMemory::Memcmp(Before,Target,sizeof(Target)),0);
    }
    // Repeated corrections reach the exact original target, so no residual is
    // discarded when the existing recovery window retires.
    float Target[41];FMemory::Memcpy(Target,Previous,sizeof(Target));
    const FMat3f Goal=Multiply(InitialThigh,AxisAngleMatrix(Axis,FMath::DegreesToRadians(73.f)));
    for(int32 I=0;I<7;++I)
    {
        float Prior[41];FMemory::Memcpy(Prior,Target,sizeof(Prior));WriteRot6(Goal,Target+18);
        SmoothTemperedKneePole(Prior,G,Target,9);
    }
    TestTrue(TEXT("Stationary target is reached in finite steps"),MatrixToQuat(Goal).Equals(MatrixToQuat(MatrixFromRot6(Target+18)),2.e-6));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingHeightDirectionTest,
    "Prophecy.NN.LowerTempering.HeightDirection", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingHeightDirectionTest::RunTest(const FString&)
{
    const FMat3f Identity;
    FPelvisLegGeometry G{FVector3f(0,.1f,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
    float Previous[41]{};
    WriteStateVec3(Previous,0,FVector3f(0,0,.8f));
    for(int32 O:{3,12,18,28,34}) WriteRot6(Identity,Previous+O);
    const FVector3f Endpoint(.15f,.3f,.15f);
    WriteStateVec3(Previous,9,Endpoint);
    WriteRot6(AxisAngleMatrix(FVector3f(0,1,0),-.4f),Previous+18);
    ResolvePelvisLeg(ReadStateVec3(Previous,0),Identity,ReadStateVec3(Previous,0),Identity,G,Previous,9);
    const FVector3f Hip=ReadStateVec3(Previous,0)+G.HipOffset;
    const FVector3f Axis=SafeNormal(Endpoint-Hip);
    FVector3f LastKnee;float WorstStep=0;
    // Fixed hip/ankle/foot and source: vary only clearance to exercise the entire
    // direction transition without an NN rollout or an endpoint change hiding it.
    for(int32 I=0;I<=140;++I)
    {
        const float Clearance=float(I)*.001f;
        G.MinimumAnkleZ=Endpoint.Z-Clearance;
        float Target[41];FMemory::Memcpy(Target,Previous,sizeof(Target));
        ResolveTemperedLeg({1,1,1,1},Previous,G,Target,9);
        const FVector3f Upper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        const FVector3f Knee=Hip+Upper;
        const FVector3f Pole=SafeNormal(Upper-Axis*FVector3f::DotProduct(Upper,Axis));
        if(I<=20) TestTrue(TEXT("Near floor bend follows foot heading"),FMath::Abs(Pole.Y)<2.e-5f && Pole.X>0.f);
        if(I>=120) TestTrue(TEXT("Raised foot retains hip-front knee plane"),FMath::Abs(Upper.Y)<2.e-5f && Upper.X>0.f);
        TestTrue(TEXT("Calf stays connected"),FMath::Abs((Endpoint-Knee).Size()-G.CalfLength)<2.e-6f);
        TestEqual(TEXT("Pelvis unchanged"),FMemory::Memcmp(Target,Previous,9*sizeof(float)),0);
        TestTrue(TEXT("Ankle unchanged"),ReadStateVec3(Target,9).Equals(Endpoint,2.e-6f));
        TestEqual(TEXT("Foot rotation unchanged"),FMemory::Memcmp(Target+12,Previous+12,6*sizeof(float)),0);
        TestEqual(TEXT("Other leg unchanged"),FMemory::Memcmp(Target+25,Previous+25,16*sizeof(float)),0);
        if(I) WorstStep=FMath::Max(WorstStep,(Knee-LastKnee).Size());
        LastKnee=Knee;
    }
    TestTrue(TEXT("Height transition has no knee discontinuity"),WorstStep<.004f);
    AddInfo(FString::Printf(TEXT("Fixed-endpoint height sweep: maximum knee step %.6fcm per 1mm clearance"),WorstStep*100.f));
    return true;
}

#if WITH_EDITOR
static void CheckCapturedKneePlaneReturn(FAutomationTestBase& Test)
{
    // Recorded131->161 recovery: changing the plane becomes feasible at157.
    // These are frozen inputs; this check cannot pass merely by changing rollout.
    const float Previous[41]={-0.0139852036f,-0.0183354877f,0.899950325f,0.0323824659f,0.0786658525f,0.996374965f,0.206406504f,0.974881887f,-0.0836772025f,-0.280153304f,0.0356324837f,0.130454123f,0.119750373f,-0.190972894f,0.97426343f,0.0430869944f,0.981400192f,0.187075838f,0.414380491f,-0.0808831155f,0.906502485f,0.0178953838f,0.996574581f,0.0807395056f,-0.947685719f,0.0194326192f,0.3100003f,0.175645411f,0.196144298f,0.444234312f,-0.874175787f,-0.526791334f,-0.704180777f,-0.476046592f,0.00918883178f,0.0100692902f,-0.999907076f,-0.272030801f,-0.962211251f,-0.0121894972f,-0.935755968f};
    const float NN[41]={-0.0220915144f,-0.0264487825f,0.911052396f,0.0404931365f,0.0534222382f,0.997750655f,0.123610567f,0.990630977f,-0.0580576953f,-0.135414764f,0.0741419327f,0.104437325f,0.123978138f,-0.242851869f,0.962108305f,0.0657512112f,0.96946836f,0.236236907f,0.273927742f,-0.0428891702f,0.96079348f,0.0189047619f,0.999052255f,0.0392071597f,-0.931232305f,-0.060180936f,0.169378325f,0.167875064f,0.162172781f,0.33575902f,-0.927882465f,-0.462054395f,-0.805031685f,-0.372061451f,-0.0821176504f,-0.194671304f,-0.977425074f,-0.248620739f,-0.945729217f,0.209246209f,-0.97195895f};
    const float Recorded[41]={-0.0217763893f,-0.0261333864f,0.910620809f,0.0400942601f,0.0545123033f,0.997707903f,0.127249524f,0.990101874f,-0.0592104234f,-0.229537964f,0.0894430131f,0.135315448f,0.123925224f,-0.242099568f,0.962304711f,0.0654194877f,0.96966368f,0.235526264f,0.285925239f,-0.00139057636f,0.95825094f,-0.689636886f,0.694004238f,0.206782579f,-0.931472182f,-0.0563509911f,0.176143169f,0.168014765f,0.163591236f,0.341203153f,-0.925644815f,-0.465362221f,-0.800643146f,-0.377370626f,-0.0988058001f,-0.222776696f,-0.969849408f,-0.262603313f,-0.934232473f,0.241348833f,-0.970217347f};
    const ProphecyLowerTempering::FSettings S{0.985422254f,0.985422254f,0.96112597f,0.956266701f,0.985422254f,0.96112597f};
    const FPelvisLegGeometry G{FVector3f(-0.0256932992f,0.000108699314f,-0.0775007159f),FVector3f(-0.390062451f,-5.7220459e-05f,-9.39704478e-06f),FVector3f(1.07968381e-05f,-0.930421889f,-0.366490304f),0.430068872f,0.135315446f};
    float Candidate[41];FMemory::Memcpy(Candidate,Recorded,sizeof(Candidate));
    auto Solve=[&](float* Out){ResolveTemperedLeg(S,Previous,G,Out,9,FVector3f(-0.0615985096f,-0.13826412f,0.00680604391f),FVector3f(1,0,0),.15f,true,NN);};
    Solve(Candidate);
    const FQuat Prior=MatrixToQuat(MatrixFromRot6(Previous+18));
    const FQuat New=MatrixToQuat(MatrixFromRot6(Candidate+18));
    Test.TestEqual(TEXT("Recorded solve leaves pelvis unchanged"),FMemory::Memcmp(Recorded,Candidate,9*sizeof(float)),0);
    Test.TestTrue(TEXT("Recorded solve keeps the exact ankle endpoint"),ReadStateVec3(Recorded,9).Equals(ReadStateVec3(Candidate,9),2.e-6f));
    Test.TestEqual(TEXT("Recorded solve preserves foot rotation and toe"),FMemory::Memcmp(Recorded+12,Candidate+12,6*sizeof(float)),0);
    Test.TestEqual(TEXT("Recorded toe unchanged"),Recorded[24],Candidate[24]);
    const FVector3f Hip=ReadStateVec3(Candidate,0)+TransformRow(G.HipOffset,MatrixFromRot6(Candidate+3));
    const FVector3f Knee=Hip+TransformRow(G.KneeOffset,MatrixFromRot6(Candidate+18));
    Test.TestTrue(TEXT("Recorded calf remains connected"),FMath::Abs((ReadStateVec3(Candidate,9)-Knee).Size()-G.CalfLength)<2.e-6f);
    // The rejected normalized-coordinate trial's golden rotation is obsolete.
    // This frozen endpoint is at floor level: the accepted rule requires a pole
    // in the foot-forward vertical plane, with the forward-facing branch.
    const FVector Axis=FVector(ReadStateVec3(Candidate,9)-Hip).GetSafeNormal();
    const FVector Upper=FVector(Knee-Hip);
    const FVector Bend=(Upper-Axis*FVector::DotProduct(Upper,Axis)).GetSafeNormal();
    FVector Forward=FVector(TransformRow(FVector3f(-.0615985096f,-.13826412f,.00680604391f),MatrixFromRot6(Candidate+12)));
    Forward.Z=0;Forward.Normalize();
    const FVector Side(-Forward.Y,Forward.X,0);
    Test.TestTrue(TEXT("Frozen floor-level bend follows the foot-forward plane"),FMath::Abs(FVector::DotProduct(Bend,Side))<2.e-5);
    Test.TestTrue(TEXT("Frozen floor-level bend retains the forward branch"),FVector::DotProduct(Bend,Forward)>0);
    // Sweep the endpoint through the previous feasibility boundary using fixed
    // reference poses. This also covers an almost straight connected leg.
    FQuat Last;double MaxStep=0;
    for(int32 I=0;I<=1000;++I)
    {
        float P[41];FMemory::Memcpy(P,Recorded,sizeof(P));
        WriteStateVec3(P,9,ReadStateVec3(Recorded,9)+FVector3f((float(I)/1000.f-.5f)*.16f,0,0));
        Solve(P);
        const FQuat Q=MatrixToQuat(MatrixFromRot6(P+18));
        if(I) MaxStep=FMath::Max(MaxStep,double(FMath::RadiansToDegrees(Last.AngularDistance(Q))));
        Last=Q;
        Test.TestTrue(TEXT("Endpoint sweep remains finite"),!Q.ContainsNaN());
    }
    Test.TestTrue(TEXT("No discrete knee turn across endpoint feasibility sweep"),MaxStep<1.);
    Test.AddInfo(FString::Printf(TEXT("Frozen recorded157 height-guided thigh step %.6f degrees; sweep max %.6f degrees"),FMath::RadiansToDegrees(Prior.AngularDistance(New)),MaxStep));
}
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingSupportSourceTest,
    "Prophecy.NN.LowerTempering.SupportSourceContracts", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingSupportSourceTest::RunTest(const FString&)
{
    using ProphecyLowerTempering::FSettings;
    const FMat3f Identity;
    const FPelvisLegGeometry G{FVector3f(0,.1f,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
    float Previous[41]{},NN[41]{},Target[41]{},Legacy[41]{};
    WriteStateVec3(Previous,0,FVector3f(0,0,.8f));
    for (int32 O : {3,12,18,28,34}) WriteRot6(Identity,Previous+O);
    WriteStateVec3(Previous,9,FVector3f(.12f,.1f,.05f));
    WriteRot6(AxisAngleMatrix(FVector3f(0,1,0),-.4f),Previous+18);
    ResolvePelvisLeg(ReadStateVec3(Previous,0),Identity,ReadStateVec3(Previous,0),Identity,G,Previous,9);
    FMemory::Memcpy(NN,Previous,sizeof(NN));
    WriteStateVec3(NN,0,FVector3f(.04f,.015f,.82f));
    WriteStateVec3(NN,9,FVector3f(.15f,.11f,.05f));
    WriteRot6(Multiply(MatrixFromRot6(Previous+18),AxisAngleMatrix(FVector3f(0,0,1),.3f)),NN+18);
    auto Resolve=[&](const FSettings& S,float* Out,const float* Source)
    { ResolveTemperedLeg(S,Previous,G,Out,9,FVector3f(1,0,0),FVector3f(0,0,1),0,true,Source); };
    FMemory::Memcpy(Target,Previous,sizeof(Target));FMemory::Memcpy(Legacy,Target,sizeof(Target));
    Resolve(FSettings{0,0,0,0},Legacy,nullptr);Resolve(FSettings{0,0,0,0},Target,NN);
    TestEqual(TEXT("Frozen controls retain the accepted source bit for bit"),FMemory::Memcmp(Target,Legacy,sizeof(Target)),0);
    FMemory::Memcpy(Target,NN,sizeof(Target));WriteStateVec3(Target,9,FVector3f(.23f,.1f,.24f));
    FMemory::Memcpy(Legacy,Target,sizeof(Target));
    const FSettings Mixed{.4f,.6f,.5f,.7f,.5f,.5f};
    Resolve(Mixed,Legacy,nullptr);Resolve(Mixed,Target,NN);
    TestEqual(TEXT("Raised-foot solve is bit identical to the accepted solver"),FMemory::Memcmp(Target,Legacy,sizeof(Target)),0);
    for (int32 J=0;J<=12;++J) for (float Follow : {.1f,.5f,.9f,1.f})
    {
        FMemory::Memcpy(Target,NN,sizeof(Target));
        const FVector3f Endpoint(.13f,.1f,.05f+.0125f*J);
        WriteStateVec3(Target,9,Endpoint);
        float Before[41];FMemory::Memcpy(Before,Target,sizeof(Before));
        Resolve(FSettings{.5f,Follow,.5f,.5f,.5f,.5f},Target,NN);
        const FVector3f Hip=ReadStateVec3(Target,0)+G.HipOffset;
        const FMat3f Thigh=MatrixFromRot6(Target+18);
        const FVector3f Knee=Hip+TransformRow(G.KneeOffset,Thigh);
        TestTrue(TEXT("Reachable pinned ankle retained"),ReadStateVec3(Target,9).Equals(Endpoint,2.e-6f));
        TestTrue(TEXT("Both segment lengths retained"),FMath::IsNearlyEqual((Knee-Hip).Size(),.45f,2.e-6f)
            && FMath::IsNearlyEqual((Endpoint-Knee).Size(),G.CalfLength,2.e-6f));
        TestEqual(TEXT("Leg solve does not change pelvis"),FMemory::Memcmp(Target,Before,9*sizeof(float)),0);
        TestEqual(TEXT("Foot rotation remains unchanged"),FMemory::Memcmp(Target+12,Before+12,6*sizeof(float)),0);
        TestEqual(TEXT("Toe remains unchanged"),Target[24],Before[24]);
        TestEqual(TEXT("Other leg remains unchanged"),FMemory::Memcmp(Target+25,Before+25,16*sizeof(float)),0);
        const FMat3f Calf=CalfRotationFromHinge(G.KneeOffset,FVector3f(0,0,-.43f),G.Pole,G.Pole,Thigh,Endpoint-Knee);
        TestTrue(TEXT("Decoded calf reaches the stored ankle"),(Knee+TransformRow(FVector3f(0,0,-.43f),Calf)).Equals(Endpoint,3.e-6f));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRegionalPoseBlendTest,
    "Prophecy.NN.PolicyBlend.RegionalPose", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRegionalPoseBlendTest::RunTest(const FString&)
{
    float Run[41]{},Walk[41]{},Target[41];
    for (int32 I=0;I<41;++I) { Run[I]=float(I);Walk[I]=float(I+100); }
    FMemory::Memcpy(Target,Run,sizeof(Target));
    BlendLowerPolicyRegion(Target,Walk,0,0);BlendLowerPolicyRegion(Target,Walk,9,0);BlendLowerPolicyRegion(Target,Walk,25,1);
    TestEqual(TEXT("Run pelvis and entire left leg remain bit exact"),FMemory::Memcmp(Target,Run,25*sizeof(float)),0);
    TestEqual(TEXT("Entire right leg including thigh and toe takes walk"),FMemory::Memcmp(Target+25,Walk+25,16*sizeof(float)),0);
    const FMat3f Identity;
    for (int32 O : {3,12,18,28,34}) { WriteRot6(Identity,Target+O);WriteRot6(Identity,Walk+O); }
    BlendLowerPolicyRegion(Target,Walk,9,.5f);
    TestEqual(TEXT("Left endpoint interpolates independently"),Target[9],59.f);
    TestEqual(TEXT("Left toe uses left weight"),Target[24],74.f);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingAxesTest,
    "Prophecy.NN.LowerTempering.TranslationAxes", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingAxesTest::RunTest(const FString&)
{
    float Previous[41]{},Target[41]{};
    for (int32 O : {0,9,25})
    { WriteStateVec3(Previous,O,FVector3f(1,2,3));WriteStateVec3(Target,O,FVector3f(5,6,7)); }
    // Feet XY frozen, Z half; pelvis XY follows fully, Z frozen. Rotation untouched.
    TemperLowerPose(ProphecyLowerTempering::FSettings{0,1,1,1,.5f,0},Previous,Target);
    TestTrue(TEXT("Pelvis XY and Z independent"),ReadStateVec3(Target,0).Equals(FVector3f(5,6,3)));
    for (int32 O : {9,25}) TestTrue(TEXT("Feet XY and Z independent"),ReadStateVec3(Target,O).Equals(FVector3f(1,2,5)));
    for (int32 O:{0,9,25}) WriteStateVec3(Target,O,FVector3f(5,6,7));
    Previous[24]=.1f;Target[24]=.9f;Previous[40]=.2f;Target[40]=.8f;
    const ProphecyLowerTempering::FSettings Left{0,0,1,1,.5f,1},Right{1,1,1,1,0,1};
    TemperLowerPose(Left,Previous,Target,&Right);
    TestTrue(TEXT("Left uses its own XY/Z values"),ReadStateVec3(Target,9).Equals(FVector3f(1,2,5)));
    TestTrue(TEXT("Right uses its own XY/Z values"),ReadStateVec3(Target,25).Equals(FVector3f(5,6,3)));
    TestEqual(TEXT("Left toe follows left rotation tempering"),Target[24],.1f);
    TestEqual(TEXT("Right toe follows right rotation tempering"),Target[40],.8f);
    const ProphecyLowerTempering::FSettings Normal;
    TestTrue(TEXT("Modified foot requires chain reconstruction"),NeedsTemperedLegReconstruction(Normal,Left));
    TestFalse(TEXT("Other normal foot and normal pelvis bypass reconstruction"),NeedsTemperedLegReconstruction(Normal,Normal));
    TestTrue(TEXT("Modified pelvis still requires both chains"),NeedsTemperedLegReconstruction({1,1,0,1},Normal));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyLowerTemperingTest,
    "Prophecy.NN.LowerTempering.RootLocalPinAndChain", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyLowerTemperingTest::RunTest(const FString&)
{
    using ProphecyLowerTempering::FSettings;
    float Previous[41]{}, Predicted[41]{}, Original[41]{};
    const FMat3f Identity;
    WriteStateVec3(Previous, 0, FVector3f(0,0,.9f));
    for (int32 O : {3,12,18,28,34}) WriteRot6(Identity, Previous+O);
    for (int32 I=0; I<2; ++I)
    {
        const int32 O=9+16*I;
        const float Side=I ? -.1f : .1f;
        WriteStateVec3(Previous,O,FVector3f(.12f,Side,.08f));
        WriteRot6(AxisAngleMatrix(FVector3f(0,1,0),-.4f),Previous+O+9);
        const FPelvisLegGeometry G{FVector3f(0,Side,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
        ResolvePelvisLeg(ReadStateVec3(Previous,0),Identity,ReadStateVec3(Previous,0),Identity,G,Previous,O);
    }
    FMemory::Memcpy(Original, Previous, sizeof(Previous));
    for (int32 O : {0,9,25}) WriteStateVec3(Original,O,ReadStateVec3(Original,O)+FVector3f(.1f,.02f,.05f));
    for (int32 O : {3,12,18,28,34}) WriteRot6(AxisAngleMatrix(FVector3f(0,0,1),.4f),Original+O);
    Original[24]=.3f; Original[40]=-.2f;
    FMemory::Memcpy(Predicted,Original,sizeof(Original));
    TemperLowerPose(FSettings{},Previous,Predicted);
    TestEqual(TEXT("All-one math leaves every bit unchanged"),FMemory::Memcmp(Predicted,Original,sizeof(Original)),0);
    TemperLowerPose(FSettings{0,0,0,0},Previous,Predicted);
    for (int32 O : {0,9,25})
        TestTrue(TEXT("Zero retains root-local pelvis and feet"),ReadStateVec3(Predicted,O)==ReadStateVec3(Previous,O));
    for (int32 I=0;I<2;++I)
    {
        const FPelvisLegGeometry G{FVector3f(0,I?-.1f:.1f,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
        ResolveTemperedLeg(FSettings{0,0,0,0},Previous,G,Predicted,9+16*I);
        TestTrue(TEXT("Zero solve retains source thigh frame"),MatrixToQuat(MatrixFromRot6(Predicted+18+16*I)).Equals(
            MatrixToQuat(MatrixFromRot6(Previous+18+16*I)),1.e-5));
    }
    const FTransform RootA(FRotator(0,20,0),FVector(100,200,0));
    const FTransform RootB(FRotator(0,100,0),FVector(400,-80,0));
    const FVector Foot=LocalTrainingToUnreal(ReadStateVec3(Predicted,9));
    TestFalse(TEXT("Frozen local foot follows translated/rotated root in world space"),RootA.TransformPosition(Foot).Equals(RootB.TransformPosition(Foot),1.e-5));
    FMemory::Memcpy(Predicted,Original,sizeof(Original));
    TemperLowerPose(FSettings{.5f,1.f,0.f,.5f},Previous,Predicted);
    TestTrue(TEXT("Independent feet translation interpolates"),ReadStateVec3(Predicted,9).Equals(FMath::Lerp(ReadStateVec3(Previous,9),ReadStateVec3(Original,9),.5f),1.e-7f));
    TestTrue(TEXT("Independent pelvis translation freezes"),ReadStateVec3(Predicted,0)==ReadStateVec3(Previous,0));
    TestEqual(TEXT("Feet rotation one remains exact"),FMemory::Memcmp(Predicted+12,Original+12,6*sizeof(float)),0);
    const auto ExpectedRotation=FQuat::Slerp(MatrixToQuat(MatrixFromRot6(Previous+3)),MatrixToQuat(MatrixFromRot6(Original+3)),.5);
    TestTrue(TEXT("Independent pelvis rotation interpolates"),MatrixToQuat(MatrixFromRot6(Predicted+3)).Equals(ExpectedRotation,1.e-6));

    // The actual order: temper -> pin in the current root frame -> resolve.
    // A small carrier shift is reachable, so the solve must retain the global pin.
    float Reference[41];
    FMemory::Memcpy(Predicted,Original,sizeof(Original));
    TemperLowerPose(FSettings{0,0,0,0},Previous,Predicted);
    FMemory::Memcpy(Reference,Original,sizeof(Reference));
    const FVector3f RootDelta(.025f,0,0);
    const FVector3f Pinned=ReadStateVec3(Previous,9)-RootDelta;
    WriteStateVec3(Predicted,9,Pinned);
    const FPelvisLegGeometry G{FVector3f(0,.1f,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
    const FVector3f Pelvis=ReadStateVec3(Predicted,0);
    ResolveTemperedLeg(FSettings{0,0,0,0},Previous,G,Predicted,9);
    TestTrue(TEXT("World pin overrides zero tempering within reach"),(ReadStateVec3(Predicted,9)+RootDelta).Equals(ReadStateVec3(Previous,9),1.e-6f));
    const FVector3f Hip=Pelvis+G.HipOffset;
    const FVector3f Knee=Hip+TransformRow(G.KneeOffset,MatrixFromRot6(Predicted+18));
    TestTrue(TEXT("Pinned chain retains thigh length"),FMath::IsNearlyEqual((Knee-Hip).Size(),.45f,1.e-6f));
    TestTrue(TEXT("Pinned chain retains calf length"),FMath::IsNearlyEqual((ReadStateVec3(Predicted,9)-Knee).Size(),.43f,1.e-6f));
    // Repeated mixed controls, reach and floor corrections: no detached ankles.
    float Worst=0;
    for (int32 I=0; I<120; ++I)
    {
        FMemory::Memcpy(Predicted,Original,sizeof(Original));
        WriteStateVec3(Predicted,0,FVector3f(.4f*FMath::Sin(I*.1f),0,.5f+.5f*FMath::Abs(FMath::Cos(I*.07f))));
        FMemory::Memcpy(Reference,Predicted,sizeof(Reference));
        TemperLowerPose(FSettings{.3f,.7f,.5f,.2f},Previous,Predicted);
        const auto P=ReadStateVec3(Predicted,0);const auto R=MatrixFromRot6(Predicted+3);
        WriteStateVec3(Predicted,9,ReadStateVec3(Predicted,9)+FVector3f(.1f,0,-.1f));
        ResolveTemperedLeg(FSettings{.3f,.7f,.5f,.2f},Previous,G,Predicted,9);
        const auto K=P+TransformRow(G.HipOffset,R)+TransformRow(G.KneeOffset,MatrixFromRot6(Predicted+18));
        Worst=FMath::Max(Worst,FMath::Abs((ReadStateVec3(Predicted,9)-K).Size()-.43f));
        TestTrue(TEXT("Solved foot respects feasible floor"),Predicted[11]>=.05f-1.e-6f);
    }
    TestTrue(TEXT("Mixed controls keep ankle connected"),Worst<2.e-6f);

    // Regression: an inconsistent raw NN thigh must not make the tempered knee
    // orbit the ankle. The foot pitches 40 degrees, while a deliberately corrupted
    // raw thigh points another 140 degrees around the chain. Only the coherent
    // previous hinge and anatomical foot frame may steer the reconstruction.
    float Source[41],NN[41],Target[41];
    FMemory::Memcpy(Source,Previous,sizeof(Source));
    const FVector3f FoldHip=ReadStateVec3(Source,0)+G.HipOffset;
    WriteStateVec3(Source,9,FoldHip+FVector3f(0,0,-.12f));
    ResolvePelvisLeg(ReadStateVec3(Source,0),Identity,ReadStateVec3(Source,0),Identity,G,Source,9,Previous);
    const FMat3f SourceThigh=MatrixFromRot6(Source+18);
    const FVector3f SourceUpper=TransformRow(G.KneeOffset,SourceThigh);
    FMemory::Memcpy(NN,Source,sizeof(NN));
    WriteRot6(Multiply(SourceThigh,AxisAngleMatrix(FVector3f(0,0,1),FMath::DegreesToRadians(140.f))),NN+18);
    for (float Follow : {0.f,.2f,.5f,.8f,1.f})
    {
        FMemory::Memcpy(Target,NN,sizeof(Target));
        WriteRot6(AxisAngleMatrix(FVector3f(0,1,0),FMath::DegreesToRadians(40.f)),Target+12);
        ResolveTemperedLeg(FSettings{1,Follow,1,1},Source,G,Target,9);
        const FVector3f Upper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        const FVector3f Expected=SourceUpper;
        TestTrue(TEXT("Raw thigh corruption cannot steer the foot-anchored knee sideways"),Upper.Equals(Expected,2.e-5f));
        TestTrue(TEXT("Deep folded blended thigh preserves calf length"),FMath::IsNearlyEqual((ReadStateVec3(Target,9)-FoldHip-Upper).Size(),G.CalfLength,2.e-5f));
    }
    // Cross foot-forward while deeply bent: projecting a forward ray changes
    // sign here. A transported foot frame must remain in the sagittal plane.
    FMemory::Memcpy(Target,Source,sizeof(Target));
    FVector3f LastUpper;float WorstStep=0;
    for (int32 I=0;I<=120;++I)
    {
        float Prev[41];FMemory::Memcpy(Prev,Target,sizeof(Prev));
        const float Angle=FMath::Lerp(-.7f,.7f,I/120.f);
        WriteStateVec3(Target,9,FoldHip+FVector3f(.4f*FMath::Cos(Angle),0,.4f*FMath::Sin(Angle)));
        WriteRot6(Identity,Target+12);
        ResolveTemperedLeg(FSettings{.5f,1,.5f,.5f},Prev,G,Target,9);
        const FVector3f Upper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        TestTrue(TEXT("Folded sweep stays in foot sagittal plane"),FMath::Abs(Upper.Y)<2.e-5f);
        if (I) WorstStep=FMath::Max(WorstStep,FMath::Acos(FMath::Clamp(FVector3f::DotProduct(SafeNormal(Upper),SafeNormal(LastUpper)),-1.f,1.f)));
        LastUpper=Upper;
    }
    TestTrue(TEXT("Folded sweep has no pole sign snap"),WorstStep<.02f);
    // The accepted source-plane solver preserves a coherent branch instead of
    // forcibly flipping an unchanged pose. Both roots satisfy the sagittal plane.
    float Backward[41];FMemory::Memcpy(Backward,Source,sizeof(Backward));
    WriteRot6(Multiply(SourceThigh,AxisAngleMatrix(FVector3f(0,0,1),PI)),Backward+18);
    FMemory::Memcpy(Target,Backward,sizeof(Target));
    ResolveTemperedLeg(FSettings{1,1,1,1},Backward,G,Target,9);
    const FVector3f CorrectedUpper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
    TestTrue(TEXT("Unchanged sagittal source does not receive an artificial branch flip"),
        CorrectedUpper.Equals(TransformRow(G.KneeOffset,MatrixFromRot6(Backward+18)),2.e-5f));
    TestTrue(TEXT("Branch correction preserves ankle"),ReadStateVec3(Target,9).Equals(ReadStateVec3(Backward,9),1.e-6f));
    const FVector3f ObliqueAxis(0,FMath::Sqrt(.6f),-FMath::Sqrt(.4f));
    FMemory::Memcpy(Backward,Source,sizeof(Backward));
    WriteStateVec3(Backward,9,FoldHip+ObliqueAxis*.35f);
    ResolvePelvisLeg(ReadStateVec3(Source,0),Identity,ReadStateVec3(Source,0),Identity,G,Backward,9,Source);
    WriteRot6(Multiply(MatrixFromRot6(Backward+18),AxisAngleMatrix(ObliqueAxis,PI)),Backward+18);
    FMemory::Memcpy(Target,Backward,sizeof(Target));
    ResolveTemperedLeg(FSettings{1,1,1,1},Backward,G,Target,9);
    const FVector3f ObliqueUpper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
    TestTrue(TEXT("Unchanged oblique source preserves its coherent branch"),
        ObliqueUpper.Equals(TransformRow(G.KneeOffset,MatrixFromRot6(Backward+18)),2.e-5f));
    // A cross-product sign reversal at lateral extension must have vanishing
    // influence, rather than normalize a nearly zero vector into a 180deg snap.
    for (float Epsilon : {-.0001f,.0001f})
    {
        float Lateral[41];FMemory::Memcpy(Lateral,Source,sizeof(Lateral));
        WriteStateVec3(Lateral,9,FoldHip+FVector3f(Epsilon,.4f,0));
        ResolvePelvisLeg(ReadStateVec3(Source,0),Identity,ReadStateVec3(Source,0),Identity,G,Lateral,9,Source);
        const FMat3f Before=MatrixFromRot6(Lateral+18);
        FMemory::Memcpy(Target,Lateral,sizeof(Target));
        ResolveTemperedLeg(FSettings{1,1,1,1},Lateral,G,Target,9);
        TestTrue(TEXT("Ambiguous lateral orientation preserves transported thigh"),MatrixToQuat(MatrixFromRot6(Target+18)).Equals(MatrixToQuat(Before),1.e-5));
    }
    FMemory::Memcpy(Target,Source,sizeof(Target));
    FVector3f LastSideUpper;float WorstSideStep=0;
    for (int32 I=0;I<=120;++I)
    {
        float Prev[41];FMemory::Memcpy(Prev,Target,sizeof(Prev));
        const float A=FMath::Lerp(1.f,2.f,I/120.f);
        WriteStateVec3(Target,9,FoldHip+FVector3f(0,.35f*FMath::Sin(A),-.35f*FMath::Cos(A)));
        ResolveTemperedLeg(FSettings{.5f,1,.5f,.5f},Prev,G,Target,9);
        const FVector3f U=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        TestTrue(TEXT("Sideways crossing keeps the forward knee branch"),U.X>0.f);
        if (I) WorstSideStep=FMath::Max(WorstSideStep,FMath::Acos(FMath::Clamp(
            FVector3f::DotProduct(SafeNormal(U),SafeNormal(LastSideUpper)),-1.f,1.f)));
        LastSideUpper=U;
    }
    TestTrue(TEXT("Sideways crossing has no branch snap"),WorstSideStep<.02f);
    const float InnerReach=1.2f*FMath::Abs(G.KneeOffset.Size()-G.CalfLength);
    TestTrue(TEXT("Inner reach is 1.2 times segment length difference"),FMath::IsNearlyEqual(InnerReach,.024f,1.e-7f));
    for (const FVector3f Delta : {FVector3f::ZeroVector,FVector3f(.01f,0,-.01f),FVector3f(.3f,0,-.1f),FVector3f(1.4f,0,-.1f)})
    {
        FMemory::Memcpy(Target,Source,sizeof(Target));
        WriteStateVec3(Target,9,FoldHip+Delta);
        const FMat3f FootBefore=MatrixFromRot6(Target+12);
        ResolveTemperedLeg(FSettings{.5f,.5f,.5f,.5f},Source,G,Target,9,
            FVector3f(1,0,0),FVector3f(0,0,1),InnerReach,false);
        const FVector3f Accepted=ReadStateVec3(Target,9);
        TestTrue(TEXT("Inner-only bound excludes hip neighborhood"),(Accepted-FoldHip).Size()>=InnerReach-1.e-6f);
        if (Delta.Size()>=InnerReach)
            TestTrue(TEXT("Inner-only bound preserves outside endpoints, including beyond full extension"),Accepted.Equals(FoldHip+Delta,1.e-6f));
        TestTrue(TEXT("Inner bound leaves foot rotation unchanged"),MatrixToQuat(MatrixFromRot6(Target+12)).Equals(MatrixToQuat(FootBefore),1.e-6));
        const FVector3f K=FoldHip+TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        TestTrue(TEXT("Inner bound preserves thigh length"),FMath::IsNearlyEqual((K-FoldHip).Size(),G.KneeOffset.Size(),1.e-6f));
        if (Delta.Size()<G.KneeOffset.Size()+G.CalfLength)
            TestTrue(TEXT("Inner bound resolves connected calf when within outer reach"),FMath::IsNearlyEqual((Accepted-K).Size(),G.CalfLength,2.e-6f));
    }
    return true;
}
#endif
