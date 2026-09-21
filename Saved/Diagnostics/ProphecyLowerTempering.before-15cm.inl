// Included after policy blend math. Previous is the previous PUBLISHED state in
// its own root frame, not CurStateBuffer rebased to keep positions world-stationary.
void TemperLowerPose(const ProphecyLowerTempering::FSettings& S, const float* Previous, float* Predicted)
{
    auto Position = [&](int32 Offset, float Follow)
    {
        if (Follow == 1.f) return;
        if (Follow == 0.f) FMemory::Memcpy(Predicted+Offset, Previous+Offset, 3*sizeof(float));
        else BlendStateVector(Predicted, Previous, Offset, 1.f-Follow);
    };
    auto Rotation = [&](int32 Offset, float Follow)
    {
        if (Follow == 1.f) return;
        if (Follow == 0.f) FMemory::Memcpy(Predicted+Offset, Previous+Offset, 6*sizeof(float));
        else BlendStateRotation(Predicted, Previous, Offset, 1.f-Follow);
    };
    Position(0, S.PelvisTranslation); Rotation(3, S.PelvisRotation);
    for (int32 Offset : {9,25})
    {
        Position(Offset, S.FeetTranslation);
        Rotation(Offset+3, S.FeetRotation);
        // Thigh orientation is solved from untouched source hinge frames below.
        // Independently blending it here corrupts the source bend direction.
        if (S.FeetRotation != 1.f)
            Predicted[Offset+15] = S.FeetRotation == 0.f ? Previous[Offset+15]
                : FMath::Lerp(Previous[Offset+15], Predicted[Offset+15], S.FeetRotation);
    }
}

void ResolveTemperedLeg(const ProphecyLowerTempering::FSettings& S,const float* Previous,
    const FPelvisLegGeometry& G,float* Target,int32 Offset,
    FVector3f FootForwardLocal=FVector3f(1,0,0),FVector3f FootUpLocal=FVector3f(0,0,1),
    float MinimumReach=0.f,bool bClampOuterReach=true)
{
    const FVector3f Pelvis=ReadStateVec3(Target,0);
    const FMat3f PelvisRotation=MatrixFromRot6(Target+3);
    auto Solve=[&](const float* Source,float* Output,FVector3f* Pole=nullptr)
    {
        ResolvePelvisLeg(ReadStateVec3(Source,0),MatrixFromRot6(Source+3),Pelvis,PelvisRotation,
            G,Output,Offset,Source,false,Pole,MinimumReach,bClampOuterReach);
    };
    // The previous published leg is coherent; raw NN endpoint/thigh pairs
    // can be wildly inconsistent on recovery. Transport this hinge through
    // accepted endpoint changes, without coupling foot pitch to knee orbit.
    Solve(Previous,Target);
    if (S.FeetRotation==0.f) return;
    const FVector3f Hip=Pelvis+TransformRow(G.HipOffset,PelvisRotation);
    const FVector3f Axis=SafeNormal(ReadStateVec3(Target,Offset)-Hip);
    const FMat3f Thigh=MatrixFromRot6(Target+Offset+9);
    const FVector3f Upper=TransformRow(G.KneeOffset,Thigh);
    const float Along=FVector3f::DotProduct(Upper,Axis);
    const FVector3f Radial=Upper-Axis*Along;
    const float Radius=Radial.Size();
    if (Radius<1.e-6f) return;
    const FVector3f Pole=Radial/Radius;
    // The sole's lateral axis is stable while the toes pitch vertically.
    const FVector3f FootSide=TransformRow(SafeNormal(FVector3f::CrossProduct(FootUpLocal,FootForwardLocal)),MatrixFromRot6(Target+Offset+3));
    const FVector3f Flat(FootSide.X,FootSide.Y,0);
    // Start from an upright human leg (ankle down, knee toward foot heading),
    // then minimally swing this complete frame to the accepted ankle direction.
    // Cross(Axis,Side) chooses a sign but flips when the leg passes sideways;
    // this transported reference instead keeps a forward knee through that pose.
    const FVector3f Down(0,0,-1);
    const FVector3f Forward=SafeNormal(FVector3f(Flat.Y,-Flat.X,0),FVector3f(1,0,0));
    const float Denominator=1.f-Axis.Z;
    // Only the exact upside-down reference is singular. Fade toward the previous
    // transported frame near it; foot pitch never supplies the reference Down.
    const float Reliability=FMath::Clamp(Denominator*4.f,0.f,1.f);
    const float Strength=S.FeetRotation*Flat.SizeSquared()*Reliability*Reliability*(3.f-2.f*Reliability);
    if (Strength<1.e-8f) return;
    const FVector3f DesiredPole=ProjectToPlane(Forward-(Down+Axis)
        *(FVector3f::DotProduct(Forward,Axis)/FMath::Max(Denominator,1.e-6f)),Axis);
    const float Angle=FMath::Atan2(FVector3f::DotProduct(Axis,FVector3f::CrossProduct(Pole,DesiredPole)),
        FMath::Clamp(FVector3f::DotProduct(Pole,DesiredPole),-1.f,1.f));
    WriteRot6(Multiply(Thigh,AxisAngleMatrix(Axis,Angle*Strength)),Target+Offset+9);
}

#if WITH_DEV_AUTOMATION_TESTS
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
    // A knee already on the backward branch must not be a fixed point of the
    // correction. Both branches are in the same sagittal plane.
    float Backward[41];FMemory::Memcpy(Backward,Source,sizeof(Backward));
    WriteRot6(Multiply(SourceThigh,AxisAngleMatrix(FVector3f(0,0,1),PI)),Backward+18);
    FMemory::Memcpy(Target,Backward,sizeof(Target));
    ResolveTemperedLeg(FSettings{1,1,1,1},Backward,G,Target,9);
    const FVector3f CorrectedUpper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
    TestTrue(TEXT("Backward branch resolves to forward knee"),CorrectedUpper.X>0.f && FMath::Abs(CorrectedUpper.Y)<2.e-5f);
    TestTrue(TEXT("Branch correction preserves ankle"),ReadStateVec3(Target,9).Equals(ReadStateVec3(Backward,9),1.e-6f));
    const FVector3f ObliqueAxis(0,FMath::Sqrt(.6f),-FMath::Sqrt(.4f));
    FMemory::Memcpy(Backward,Source,sizeof(Backward));
    WriteStateVec3(Backward,9,FoldHip+ObliqueAxis*.35f);
    ResolvePelvisLeg(ReadStateVec3(Source,0),Identity,ReadStateVec3(Source,0),Identity,G,Backward,9,Source);
    WriteRot6(Multiply(MatrixFromRot6(Backward+18),AxisAngleMatrix(ObliqueAxis,PI)),Backward+18);
    FMemory::Memcpy(Target,Backward,sizeof(Target));
    ResolveTemperedLeg(FSettings{1,1,1,1},Backward,G,Target,9);
    const FVector3f ObliqueUpper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
    TestTrue(TEXT("Unambiguous oblique leg cannot retain backward bend"),
        FVector3f::DotProduct(SafeNormal(ObliqueUpper-ObliqueAxis*FVector3f::DotProduct(ObliqueUpper,ObliqueAxis)),FVector3f(1,0,0))>.999f);
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
