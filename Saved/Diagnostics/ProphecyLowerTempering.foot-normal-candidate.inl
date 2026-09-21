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
    const float* Baseline,const FPelvisLegGeometry& G,float* Target,int32 Offset,
    FVector3f FootForwardLocal=FVector3f(1,0,0),FVector3f FootUpLocal=FVector3f(0,0,1))
{
    const FVector3f Pelvis=ReadStateVec3(Target,0);
    const FMat3f PelvisRotation=MatrixFromRot6(Target+3);
    auto Solve=[&](const float* Source,float* Output,FVector3f* Pole=nullptr)
    {
        ResolvePelvisLeg(ReadStateVec3(Source,0),MatrixFromRot6(Source+3),Pelvis,PelvisRotation,
            G,Output,Offset,Source,true,Pole);
    };
    FVector3f PreviousPole;
    Solve(Previous,Target,&PreviousPole);
    if (S.FeetRotation==0.f) return;
    const FVector3f Hip=Pelvis+TransformRow(G.HipOffset,PelvisRotation);
    const FVector3f Axis=SafeNormal(ReadStateVec3(Target,Offset)-Hip);

    // The raw NN thigh/ankle pair need not be a feasible triangle (especially
    // just after a kick). Its geometric bend is therefore NOT a hinge reference.
    // Anchor the signed hinge NORMAL to the foot's anatomical frame instead.
    // Transporting a canonical down-axis by shortest swing can rotate that
    // normal sideways near a high kick; projecting foot-forward can flip when
    // it meets the chain axis. The normal has neither of those singularities.
    const FMat3f Foot=MatrixFromRot6(Target+Offset+3);
    const FVector3f Down=SafeNormal(TransformRow(-FootUpLocal,Foot));
    const FVector3f Forward=ProjectToPlane(TransformRow(FootForwardLocal,Foot),Down);
    const FVector3f FootNormal=SafeNormal(FVector3f::CrossProduct(Down,Forward));
    const FVector3f NewPole=SafeNormal(FVector3f::CrossProduct(FootNormal,Axis),PreviousPole);
    const float Angle=FMath::Atan2(FVector3f::DotProduct(Axis,FVector3f::CrossProduct(PreviousPole,NewPole)),
        FMath::Clamp(FVector3f::DotProduct(PreviousPole,NewPole),-1.f,1.f));
    const FMat3f OldAligned=Multiply(MatrixFromRot6(Target+Offset+9),AxisAngleMatrix(Axis,Angle*S.FeetRotation));
    const FVector3f Pole=RotateAroundAxis(PreviousPole,Axis,Angle*S.FeetRotation);
    const FVector3f Upper=SafeNormal(TransformRow(G.KneeOffset,OldAligned));
    const FVector3f Normal=SafeNormal(FVector3f::CrossProduct(Axis,Pole));
    const FVector3f LocalUpper=SafeNormal(G.KneeOffset);
    const FVector3f LocalNormal=SafeNormal(FVector3f::CrossProduct(LocalUpper,G.Pole));
    FMat3f LocalBasis,NewBasis;
    LocalBasis.Rows[0]=LocalUpper;LocalBasis.Rows[1]=SafeNormal(FVector3f::CrossProduct(LocalNormal,LocalUpper));LocalBasis.Rows[2]=LocalNormal;
    NewBasis.Rows[0]=Upper;NewBasis.Rows[1]=SafeNormal(FVector3f::CrossProduct(Normal,Upper));NewBasis.Rows[2]=Normal;
    const FMat3f NewAligned=Multiply(Transpose(LocalBasis),NewBasis);
    WriteRot6(QuatToMatrix(FQuat::Slerp(MatrixToQuat(OldAligned),MatrixToQuat(NewAligned),S.FeetRotation).GetNormalized()),Target+Offset+9);
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
        ResolveTemperedLeg(FSettings{0,0,0,0},Previous,Original,G,Predicted,9+16*I);
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
    ResolveTemperedLeg(FSettings{0,0,0,0},Previous,Reference,G,Predicted,9);
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
        ResolveTemperedLeg(FSettings{.3f,.7f,.5f,.2f},Previous,Reference,G,Predicted,9);
        const auto K=P+TransformRow(G.HipOffset,R)+TransformRow(G.KneeOffset,MatrixFromRot6(Predicted+18));
        Worst=FMath::Max(Worst,FMath::Abs((ReadStateVec3(Predicted,9)-K).Size()-.43f));
        TestTrue(TEXT("Solved foot respects feasible floor"),Predicted[11]>=.05f-1.e-6f);
    }
    TestTrue(TEXT("Mixed controls keep ankle connected"),Worst<2.e-6f);

    // Regression: an inconsistent raw NN thigh must not make the tempered knee
    // orbit the ankle. The foot turns 40 degrees, while a deliberately corrupted
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
        WriteRot6(AxisAngleMatrix(FVector3f(0,0,1),FMath::DegreesToRadians(40.f)),Target+12);
        ResolveTemperedLeg(FSettings{1,Follow,1,1},Source,NN,G,Target,9);
        const FVector3f Upper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        const FVector3f Expected=RotateAroundAxis(SourceUpper,FVector3f(0,0,1),FMath::DegreesToRadians(40.f));
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
        ResolveTemperedLeg(FSettings{.5f,1,.5f,.5f},Prev,NN,G,Target,9);
        const FVector3f Upper=TransformRow(G.KneeOffset,MatrixFromRot6(Target+18));
        TestTrue(TEXT("Folded sweep stays in foot sagittal plane"),FMath::Abs(Upper.Y)<2.e-5f);
        if (I) WorstStep=FMath::Max(WorstStep,FMath::Acos(FMath::Clamp(FVector3f::DotProduct(SafeNormal(Upper),SafeNormal(LastUpper)),-1.f,1.f)));
        LastUpper=Upper;
    }
    TestTrue(TEXT("Folded sweep has no pole sign snap"),WorstStep<.02f);
    return true;
}
#endif
