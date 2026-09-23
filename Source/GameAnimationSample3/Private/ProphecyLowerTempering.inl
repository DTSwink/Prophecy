// Included after policy blend math. Previous is the previous PUBLISHED state in
// its own root frame, not CurStateBuffer rebased to keep positions world-stationary.
#if WITH_EDITOR
static TAutoConsoleVariable<int32> CVarTemperingSupportSource(
    TEXT("Prophecy.Tempering.SupportSource"),1,
    TEXT("Editor recovery comparison: 1 follows NN hinge near the floor; 0 uses the previous-pose hinge throughout."));
static TAutoConsoleVariable<int32> CVarTemperingKneePlane(
    TEXT("Prophecy.Tempering.KneePlane"),1,
    TEXT("Editor geometry comparison: 0 forces a zero-offset knee plane; 1 preserves the source stance plane."));
static TAutoConsoleVariable<int32> CVarTemperingCalfContinuity(
    TEXT("Prophecy.Tempering.CalfContinuity"),1,
    TEXT("Editor comparison: 1 carries published calf twist during feet tempering; 0 re-decodes it immediately."));
#endif
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
    const float* NNSource=nullptr)
{
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
    float AlignedSource[41];
    // Preserve the accepted previous-pose hinge for raised/frozen feet. Near
    // the floor, retaining that frame indefinitely fights the walking policy:
    // the knee may stay forward while the thigh twists/stalls and disturbs the
    // next pelvis prediction. Admit the NN source in the presented foot frame, then
    // resolve the SAME final endpoints and forward-knee constraint below.
    float SourceFollow=0.f;
    if (NNSource && S.FeetRotation>0.f)
    {
        const float T=FMath::Clamp((ReadStateVec3(Target,Offset).Z-G.MinimumAnkleZ-.02f)/.10f,0.f,1.f);
        const float Support=1.f-T*T*(3.f-2.f*T);
        if (Support>0.f)
        {
            // Compare stance hinges in the same foot-heading frame. The untempered
            // policy foot may already be turning while the presented foot is held.
            const FMat3f R=MatrixFromRot6(NNSource+Offset+3);
            const FVector3f SourceToe=TransformRow(SafeNormal(FootForwardLocal),R);
            const FVector3f SourceFlat(SourceToe.X,SourceToe.Y,0);
            auto Confidence=[](float V){V=FMath::Clamp(V,0.f,1.f);return V*V*(3.f-2.f*V);};
            // Fade the source weight, not its yaw: a partial +/-180 degree
            // turn would otherwise jump at the heading wrap.
            const float HeadingTrust=Confidence(SourceFlat.SizeSquared()*4.f)*Confidence(FlatToe.SizeSquared()*4.f);
            const FVector3f SourceForward=SafeNormal(SourceFlat,Forward);
            const float Angle=FMath::Atan2(FVector3f::CrossProduct(SourceForward,Forward).Z,FVector3f::DotProduct(SourceForward,Forward));
            const FMat3f Turn=AxisAngleMatrix(FVector3f(0,0,1),Angle);
            FMemory::Memcpy(AlignedSource,NNSource,sizeof(AlignedSource));
            const FVector3f SourceHip=ReadStateVec3(NNSource,0)+TransformRow(G.HipOffset,MatrixFromRot6(NNSource+3));
            WriteStateVec3(AlignedSource,Offset,SourceHip+TransformRow(ReadStateVec3(NNSource,Offset)-SourceHip,Turn));
            for(int32 O:{Offset+3,Offset+9})WriteRot6(Multiply(MatrixFromRot6(NNSource+O),Turn),AlignedSource+O);
            NNSource=AlignedSource;
            const float Difference=MatrixToQuat(MatrixFromRot6(Previous+Offset+9)).AngularDistance(
                MatrixToQuat(MatrixFromRot6(NNSource+Offset+9)));
            // A source-frame handover bound per fixed 30Hz policy step, not a
            // clamp on the solved joint or a new wall-time blend clock.
            // The foot and its incoming hinge must follow the same authored
            // amount. Near-floor support is confidence, not permission to
            // bypass tempering: doing so feeds a fast-turning thigh beside a
            // held foot back into the next policy step and perturbs its height.
            SourceFollow=S.FeetRotation*HeadingTrust*Support
                *FMath::Min(1.f,FMath::DegreesToRadians(20.f)/FMath::Max(Difference,1.e-6f));
        }
    }
    if (SourceFollow>0.f)
    {
        // Interpolating hip/ankle positions and thigh rotation independently
        // can collapse/reverse the source hinge before solving. Transport
        // each intact source to the SAME final ankle, then mix on its circle.
        float Other[41];FMemory::Memcpy(Other,Target,sizeof(Other));
        FVector3f PriorPole,NextPole;
        Solve(Previous,Target,&PriorPole);Solve(NNSource,Other,&NextPole);
        const FVector3f Axis=SafeNormal(ReadStateVec3(Target,Offset)-Hip);
        const float Cos=FMath::Clamp(FVector3f::DotProduct(PriorPole,NextPole),-1.f,1.f);
        const FVector3f SourceHip=ReadStateVec3(NNSource,0)+TransformRow(G.HipOffset,MatrixFromRot6(NNSource+3));
        const FVector3f SourceAxis=SafeNormal(ReadStateVec3(NNSource,Offset)-SourceHip);
        const FVector3f SourceUpper=TransformRow(G.KneeOffset,MatrixFromRot6(NNSource+Offset+9));
        const float Radius=(SourceUpper-SourceAxis*FVector3f::DotProduct(SourceUpper,SourceAxis)).Size();
        auto Trust=[](float V){V=FMath::Clamp(V,0.f,1.f);return V*V*(3.f-2.f*V);};
        SourceFollow*=Trust(Radius/(G.KneeOffset.Size()*.02f))*Trust((1.f+Cos)/.02f)
            *Trust((1.f+FVector3f::DotProduct(SourceAxis,Axis))/.05f);
        const float Angle=FMath::Atan2(FVector3f::DotProduct(Axis,FVector3f::CrossProduct(PriorPole,NextPole)),Cos);
        const FMat3f Prior=MatrixFromRot6(Target+Offset+9),Next=MatrixFromRot6(Other+Offset+9);
        const FMat3f A=Multiply(Prior,AxisAngleMatrix(Axis,Angle*SourceFollow));
        const FMat3f B=Multiply(Next,AxisAngleMatrix(Axis,-Angle*(1.f-SourceFollow)));
        WriteRot6(QuatToMatrix(FQuat::Slerp(MatrixToQuat(A),MatrixToQuat(B),SourceFollow).GetNormalized()),Target+Offset+9);
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
    auto Smooth=[](float X) { X=FMath::Clamp(X,0.f,1.f);return X*X*(3.f-2.f*X); };
    const float TransportedOffset=FVector3f::DotProduct(Upper,Side);
    // Preserve the coherent source stance in its own foot-forward frame. A
    // connected wide stance need not put the knee in the plane through the hip.
    // Raised feet keep the previous source; grounded feet admit the same NN
    // source already used above, at the authored feet-rotation following rate.
    auto SourceSideOffset=[&](const float* Source)
    {
        const FMat3f R=MatrixFromRot6(Source+Offset+3);
        const FVector3f SourceToe=TransformRow(SafeNormal(FootForwardLocal),R);
        const FVector3f SourceSide=TransformRow(SafeNormal(FVector3f::CrossProduct(FootUpLocal,FootForwardLocal)),R);
        const FVector3f SourceForward=SafeNormal(FVector3f(SourceToe.X,SourceToe.Y,0),
            SafeNormal(FVector3f(SourceSide.Y,-SourceSide.X,0),FVector3f(1,0,0)));
        const float OffsetValue=FVector3f::DotProduct(TransformRow(G.KneeOffset,MatrixFromRot6(Source+Offset+9)),
            FVector3f(-SourceForward.Y,SourceForward.X,0));
        // Horizontal heading is unobservable when the source toe is vertical.
        // Fall back to the already connected hinge continuously, before mixing
        // sources; target-heading confidence alone cannot protect this case.
        const float Confidence=Smooth((SourceToe.X*SourceToe.X+SourceToe.Y*SourceToe.Y)*4.f);
        return FMath::Lerp(TransportedOffset,OffsetValue,Confidence);
    };
    float StanceOffset=SourceSideOffset(Previous);
    if (SourceFollow>0.f)
        // SourceFollow already includes FeetRotation; applying it twice would
        // over-hold the stance and restore the old planted-thigh hitch.
        StanceOffset=FMath::Lerp(StanceOffset,SourceSideOffset(NNSource),SourceFollow);
    bool bSourcePlane=true;
#if WITH_EDITOR
    bSourcePlane=CVarTemperingKneePlane.GetValueOnGameThread()!=0;
#endif
    if (!bSourcePlane) StanceOffset=0.f;
    const float Q=(StanceOffset-Along*SideAlong)/(Radius*NLength);
    // Both circle roots satisfy the lateral plane. Follow the transported
    // coherent branch; forcing the positive root can rotate an unchanged pose.
    // Fade at an ambiguous branch so changing its sign cannot create a jump.
    const float BranchDot=FVector3f::DotProduct(Pole,HingePole);
    const float Branch=bSourcePlane && BranchDot<0.f ? -1.f : 1.f;
    // The stance plane is guidance, not an instantaneous second pose override.
    // Follow it at the same authored rotation amount as the connected hinge;
    // otherwise a nearly held foot can still receive a full knee-plane turn.
    float Strength=S.FeetRotation*Smooth(FlatToe.SizeSquared()*4.f)*Smooth(NLength*NLength*4.f)
        *Smooth((1.f-FMath::Abs(Q))*4.f);
    if (bSourcePlane) Strength*=Smooth(FMath::Abs(BranchDot)*4.f);
    if (Strength<1.e-8f) return;
    const float ClampedQ=FMath::Clamp(Q,-1.f,1.f);
    const FVector3f DesiredPole=N*ClampedQ+HingePole*(Branch*FMath::Sqrt(FMath::Max(0.f,1.f-ClampedQ*ClampedQ)));
    const float Angle=FMath::Atan2(FVector3f::DotProduct(Axis,FVector3f::CrossProduct(Pole,DesiredPole)),
        FMath::Clamp(FVector3f::DotProduct(Pole,DesiredPole),-1.f,1.f));
    WriteRot6(Multiply(Thigh,AxisAngleMatrix(Axis,Angle*Strength)),Target+Offset+9);
}

#if WITH_DEV_AUTOMATION_TESTS
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
