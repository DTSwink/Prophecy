// Included in the policy math namespace. State positions are metres, local Z-up.
// Port of dodge_leg_feedback.py v4: endpoint reach projection and complete hinge-frame transport.
struct FPelvisLegGeometry
{
    FVector3f HipOffset, KneeOffset, Pole;
    float CalfLength = 0, MinimumAnkleZ = 0;
};
struct FPelvisInertiaStepContext
{
    const AProphecyAgent* Actor = nullptr;
    FTransform Carrier = FTransform::Identity;
    double Time = 0, Step = 1./30.;
};

float ExactFootMinimum(const FFootAxes& A, const FVector3f& FootHalf, const FVector3f& ToeHalf)
{
    const float Foot = A.FootCenter.Z - FMath::Abs(A.FootForward.Z)*FootHalf.X
        - FMath::Abs(A.FootSide.Z)*FootHalf.Y - FMath::Abs(A.FootUp.Z)*FootHalf.Z;
    const float Toe = A.ToeCenter.Z - FMath::Abs(A.ToeForward.Z)*ToeHalf.X
        - FMath::Abs(A.ToeSide.Z)*ToeHalf.Y - FMath::Abs(A.ToeUp.Z)*ToeHalf.Z;
    return FMath::Min(Foot,Toe);
}

void ResolvePelvisLeg(const FVector3f& OldPelvis, const FMat3f& OldPelvisRotation,
    const FVector3f& NewPelvis, const FMat3f& NewPelvisRotation,
    const FPelvisLegGeometry& G, float* State, int32 Offset, const float* ReferenceState = nullptr,
    bool bCarryFootRotation = false, FVector3f* OutPole = nullptr,
    float MinimumReach = 0.f, bool bClampOuterReach = true)
{
    const float* Reference = ReferenceState ? ReferenceState : State;
    const FMat3f OldThigh = MatrixFromRot6(Reference+Offset+9);
    const FVector3f OldHip = OldPelvis+TransformRow(G.HipOffset,OldPelvisRotation);
    const FVector3f OldUpper = TransformRow(G.KneeOffset,OldThigh);
    const FVector3f OldAnkle = ReadStateVec3(Reference,Offset);
    const FVector3f OldAxis = SafeNormal(OldAnkle-OldHip,SafeNormal(OldUpper));
    const FVector3f RawBend = OldUpper-OldAxis*FVector3f::DotProduct(OldUpper,OldAxis);
    const FVector3f OldPole = RawBend.SizeSquared()>1.e-10f ? SafeNormal(RawBend)
        : ProjectToPlane(TransformRow(G.Pole,OldThigh),OldAxis);
    const FVector3f Hip = NewPelvis+TransformRow(G.HipOffset,NewPelvisRotation);
    const float L1=G.KneeOffset.Size(), L2=G.CalfLength;
    const float Max=L1+L2-2.e-5f;
    const float Min=FMath::Clamp(MinimumReach,FMath::Abs(L1-L2)+2.e-5f,Max);
    const FVector3f Delta=ReadStateVec3(State,Offset)-Hip;
    const float RequestedDistance=Delta.Size();
    FVector3f Ankle=Hip+SafeNormal(Delta,OldAxis)*(bClampOuterReach
        ? FMath::Clamp(RequestedDistance,Min,Max) : FMath::Max(RequestedDistance,Min));
    // Floor-plane reach projection, never lift then radially pull underground.
    // Unbounded world coasting can put the entire reach sphere below the floor;
    // in that infeasible case keep the leg connected at its highest reachable point.
    if (Ankle.Z<G.MinimumAnkleZ)
    {
        const float Dz=G.MinimumAnkleZ-Hip.Z;
        if (bClampOuterReach && Dz>Max) Ankle=Hip+FVector3f(0,0,Max);
        else
        {
            FVector3f Flat(Ankle.X-Hip.X,Ankle.Y-Hip.Y,0);
            const float Radius=Flat.Size();
            const FVector3f Axis=SafeNormal(Flat,SafeNormal(FVector3f(OldAxis.X,OldAxis.Y,0)));
            const float Low=FMath::Sqrt(FMath::Max(0.f,Min*Min-Dz*Dz));
            const float High=FMath::Sqrt(FMath::Max(0.f,Max*Max-Dz*Dz));
            Ankle=Hip+Axis*(bClampOuterReach ? FMath::Clamp(Radius,Low,High) : FMath::Max(Radius,Low));
            Ankle.Z=G.MinimumAnkleZ;
        }
    }
    const FVector3f Axis=SafeNormal(Ankle-Hip,OldAxis);
    // dodge_leg_feedback.foot_local_hinge_pole: carry the SOURCE frame through
    // the foot rotation before minimal swing. Pelvis-only inertia retains its
    // original identity-carry path; tempering supplies an untouched source pose.
    FVector3f CarriedAxis=OldAxis,CarriedPole=OldPole;
    if (bCarryFootRotation)
    {
        const FMat3f Change=Multiply(Transpose(MatrixFromRot6(Reference+Offset+3)),MatrixFromRot6(State+Offset+3));
        CarriedAxis=SafeNormal(TransformRow(OldAxis,Change));
        CarriedPole=ProjectToPlane(TransformRow(OldPole,Change),CarriedAxis);
    }
    const float Cos=FMath::Clamp(FVector3f::DotProduct(CarriedAxis,Axis),-1.f,1.f);
    const FVector3f Transport=Cos < -1.f+1.e-6f ? -CarriedPole
        : CarriedPole-(CarriedAxis+Axis)*(FVector3f::DotProduct(CarriedPole,Axis)/FMath::Max(1.e-6f,1.f+Cos));
    const FVector3f Pole=ProjectToPlane(Transport,Axis);
    if (OutPole) *OutPole=Pole;
    // An unclamped endpoint can exceed a fixed-length chain. Aim a straight leg
    // at it while preserving the endpoint for the existing unclamped decoder.
    const float Distance=FMath::Min((Ankle-Hip).Size(),Max);
    const float Along=(L1*L1-L2*L2+Distance*Distance)/(2.f*Distance);
    const FVector3f NewUpper=Axis*Along+Pole*FMath::Sqrt(FMath::Max(0.f,L1*L1-Along*Along));
    const FVector3f OldNormal=SafeNormal(FVector3f::CrossProduct(OldAxis,OldPole));
    const FVector3f NewNormal=SafeNormal(FVector3f::CrossProduct(Axis,Pole));
    FMat3f OldBasis,NewBasis;
    OldBasis.Rows[0]=SafeNormal(OldUpper);
    OldBasis.Rows[1]=SafeNormal(FVector3f::CrossProduct(OldNormal,OldBasis.Rows[0]));
    OldBasis.Rows[2]=OldNormal;
    NewBasis.Rows[0]=SafeNormal(NewUpper);
    NewBasis.Rows[1]=SafeNormal(FVector3f::CrossProduct(NewNormal,NewBasis.Rows[0]));
    NewBasis.Rows[2]=NewNormal;
    WriteStateVec3(State,Offset,Ankle);
    WriteRot6(Multiply(Multiply(OldThigh,Transpose(OldBasis)),NewBasis),State+Offset+9);
}

bool CorrectLowerPelvis(const AProphecyAgent* Actor, double Time, double Dt,
    const FTransform& PreviousCarrier, const FTransform& Carrier,
    const float* Previous, float* Lower, const FPelvisLegGeometry (&Legs)[2])
{
    const FVector3f OldPosition=ReadStateVec3(Lower,0);
    const FMat3f OldRotation=MatrixFromRot6(Lower+3);
    FTransform Prev(MatrixToQuat(MirrorYBasis(MatrixFromRot6(Previous+3))),LocalTrainingToUnreal(ReadStateVec3(Previous,0)));
    FTransform Next(MatrixToQuat(MirrorYBasis(OldRotation)),LocalTrainingToUnreal(OldPosition));
    if (!ProphecyPelvisInertia::ApplyTarget(Actor,Time,Dt,PreviousCarrier,Carrier,Prev,Next)) return false;
    const FVector3f NewPosition=LocalUnrealToTraining(Next.GetTranslation());
    const FMat3f NewRotation=MirrorYBasis(QuatToMatrix(Next.GetRotation()));
    if (ProphecyLegChainDebug::IsEnabled(Actor))
        for (int32 I=0; I<2; ++I)
            ResolvePelvisLeg(OldPosition,OldRotation,NewPosition,NewRotation,Legs[I],Lower,9+16*I);
    WriteStateVec3(Lower,0,NewPosition);
    WriteRot6(NewRotation,Lower+3);
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPelvisLegChainTest,
    "Prophecy.NN.PelvisInertia.LegChain", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyPelvisLegChainTest::RunTest(const FString&)
{
    const FVector3f OldPelvis(0,0,.9f);
    const FMat3f Identity;
    const FPelvisLegGeometry G{FVector3f(0,.1f,0),FVector3f(0,0,-.45f),FVector3f(1,0,0),.43f,.05f};
    float WorstUpper=0,WorstLower=0,WorstRotation=0;
    for (int32 I=0; I<1001; ++I)
    {
        float S[41]{};
        const FMat3f Thigh=AxisAngleMatrix(FVector3f(0,1,0),-.4f);
        WriteRot6(Thigh,S+18); WriteRot6(Identity,S+12);
        WriteStateVec3(S,9,FVector3f(.12f,.1f,.08f));
        const float T=I*.013f;
        const FVector3f Pelvis(.6f*FMath::Sin(T),.4f*FMath::Cos(T*.7f),.5f+.6f*FMath::Abs(FMath::Sin(T*.4f)));
        const FMat3f Rotation=AxisAngleMatrix(SafeNormal(FVector3f(1,2,3)),T);
        ResolvePelvisLeg(OldPelvis,Identity,Pelvis,Rotation,G,S,9);
        const FMat3f R=MatrixFromRot6(S+18);
        const FVector3f Hip=Pelvis+TransformRow(G.HipOffset,Rotation);
        const FVector3f Knee=Hip+TransformRow(G.KneeOffset,R);
        const FVector3f Ankle=ReadStateVec3(S,9);
        WorstUpper=FMath::Max(WorstUpper,FMath::Abs((Knee-Hip).Size()-.45f));
        WorstLower=FMath::Max(WorstLower,FMath::Abs((Ankle-Knee).Size()-.43f));
        const FMat3f Calf=CalfRotationFromHinge(G.KneeOffset,FVector3f(0,0,-.43f),G.Pole,G.Pole,R,Ankle-Knee);
        WorstRotation=FMath::Max(WorstRotation,(Knee+TransformRow(FVector3f(0,0,-.43f),Calf)-Ankle).Size());
        if (Ankle.Z<G.MinimumAnkleZ-1.e-6f) AddError(TEXT("Feasible foot fell below floor"));
        if (!FMath::IsFinite(Ankle.X+Ankle.Y+Ankle.Z)) AddError(TEXT("Nonfinite solved leg"));
        TestTrue(TEXT("Foot rotation retained"),MatrixToQuat(MatrixFromRot6(S+12)).Equals(FQuat::Identity,1.e-7));
    }
    TestTrue(TEXT("Thigh length preserved"),WorstUpper<2.e-6f);
    TestTrue(TEXT("Calf length preserved"),WorstLower<2.e-6f);
    TestTrue(TEXT("Rendered calf FK reaches stored ankle"),WorstRotation<2.e-6f);
    AddInfo(FString::Printf(TEXT("1001 poses: max thigh/calf/FK errors = %.9g / %.9g / %.9g m"),WorstUpper,WorstLower,WorstRotation));
    // Coincident and reversed endpoint directions must resolve, not reject a pose.
    for (int32 I=0; I<2; ++I)
    {
        float S[41]{}; WriteRot6(Identity,S+18); WriteRot6(Identity,S+12);
        const FVector3f End(0,.1f,.1f); WriteStateVec3(S,9,End);
        const FVector3f P=I ? FVector3f(0,0,-.7f) : FVector3f(0,0,.1f);
        ResolvePelvisLeg(OldPelvis,Identity,P,Identity,G,S,9);
        const FVector3f Knee=P+G.HipOffset+TransformRow(G.KneeOffset,MatrixFromRot6(S+18));
        TestTrue(TEXT("Singular target preserves calf length"),FMath::Abs((ReadStateVec3(S,9)-Knee).Size()-.43f)<2.e-6f);
    }
    return true;
}
#endif
