#include "ProphecyKneePopSmoothing.h"
// The reference hinge must be read before changing the endpoint. In particular,
// a nearly straight reference cannot infer its pole from an already moved ankle.
#if WITH_EDITOR
static TAutoConsoleVariable<int32> CVarTickPinningPreserveHinge(
    TEXT("Prophecy.WalkPinning.PreserveHinge"),2,
    TEXT("Editor diagnosis only: 0 reproduces the old per-tick pin hinge/recurrence; 1 preserves raw hinge; 2 also shares the presentation bend reference."));
#endif
static bool PreserveTickPinningHinge()
{
#if WITH_EDITOR
    return CVarTickPinningPreserveHinge.GetValueOnGameThread()!=0;
#else
    return true;
#endif
}
static void MoveTickPinningEndpoint(const FPelvisLegGeometry& G,int32 O,
    const FVector3f& Shift,const float* Source,float* Changed,bool ClampOuter,bool Preserve,const float* StableReference=nullptr)
{
    WriteStateVec3(Changed,O,ReadStateVec3(Source,O)+Shift);
    ResolvePelvisLeg(ReadStateVec3(Source,0),MatrixFromRot6(Source+3),ReadStateVec3(Source,0),MatrixFromRot6(Source+3),
        G,Changed,O,Preserve?(StableReference?StableReference:Source):nullptr,false,nullptr,0.f,ClampOuter);
}
static void ShiftTickPinningLeg(const AProphecyNNLocomotionManager::FImpl* Impl,
    const AProphecyAgent* A,int32 PoseId,int32 Side,float PelvisWeight,float LegWeight,
    const FVector3f& Shift,const float* Source,float* Changed,bool ClampOuter,bool Preserve)
{
    const int32 O=9+16*Side;
    WriteStateVec3(Changed,O,ReadStateVec3(Source,O)+Shift);
    const bool Reconstruct=ProphecyLegChainDebug::IsEnabled(A) &&
        (ProphecyLowerTempering::Find(A) || ProphecyNNPresentation::HasRecoveryCalfLengths(PoseId) || LegWeight!=PelvisWeight);
    if(!Reconstruct)return;
    const auto L=Impl->BlendLimb(Side,LegWeight);const FVector3f Ankle=ReadStateVec3(Changed,O);
    const auto Axes=Impl->BuildFootAxes(L,Ankle,MatrixFromRot6(Changed+O+3),Changed[O+15]);
    const FPelvisLegGeometry G{Impl->LocalOffsets[L.Start],Impl->LocalOffsets[L.Mid],L.LocalPoleAxes[0],
        Impl->LocalOffsets[L.End].Size()+ProphecyKickFootLeeway::ReturningLengthDeltaCm(A,Side)/100.f,
        Ankle.Z+Impl->GroundHeight-ExactFootMinimum(Axes,Impl->FootHalfDims,Impl->ToeHalfDims)+1.e-5f};
    float Stable[StateDim];const float* Reference=nullptr;
    bool UsePresentation=Preserve;
#if WITH_EDITOR
    UsePresentation=UsePresentation && CVarTickPinningPreserveHinge.GetValueOnGameThread()>=2;
#endif
    float Zone=0;FVector LocalPole;
    if(UsePresentation && ProphecyNNPresentation::ReadKneePopReference(PoseId,Side,Zone,LocalPole))
    {
        const FMat3f R=MatrixFromRot6(Source+O+9);
        const FVector3f Hip=ReadStateVec3(Source,0)+TransformRow(G.HipOffset,MatrixFromRot6(Source+3));
        FTransform Thigh(MatrixToQuat(MirrorYBasis(R)),LocalTrainingToUnreal(Hip));
        FTransform Calf(FQuat::Identity,LocalTrainingToUnreal(Hip+TransformRow(G.KneeOffset,R)));
        FTransform Foot(FQuat::Identity,LocalTrainingToUnreal(ReadStateVec3(Source,O)));
        // Use the existing soft-IK reference, only for its bend plane. Its temporary
        // inward ankle movement is not imposed on the requested pin endpoint.
        if(ProphecyKneePopSmoothing::Apply(Thigh,Calf,Foot,nullptr,Zone,Thigh.TransformVectorNoScale(LocalPole)))
        {
            FMemory::Memcpy(Stable,Source,sizeof(Stable));
            WriteStateVec3(Stable,O,LocalUnrealToTraining(Foot.GetLocation()));
            WriteRot6(MirrorYBasis(QuatToMatrix(Thigh.GetRotation())),Stable+O+9);
            Reference=Stable;
        }
    }
    MoveTickPinningEndpoint(G,O,Shift,Source,Changed,ClampOuter,Preserve,Reference);
}

// Re-evaluate only the cached Walk pin contribution at presentation cadence.
// Inference and blend clocks are unchanged; coherent endpoint corrections are committed below.
void AProphecyNNLocomotionManager::UpdateWalkTickPinning(float DeltaSeconds)
{
    if(!GetWorld() || GetWorld()->IsPaused() || IsSimBridgeActive())return;
    for(int32 Index=0;Index<AgentActors.Num();++Index)
    {
        const AProphecyAgent* A=AgentActors[Index];auto* T=ProphecyWalkPinning::FindTickPinning(A);
        if(!T || !T->HasBase)continue;
        const auto* S=ProphecyWalkPinning::FindSmoothing(A);
        auto& Agent=Impl->Agents[Index];
        if(!S || Agent.Slash.bActive || Agent.DefensePose || !A->bNNInferenceEnabled)
        {ProphecyWalkPinning::ResetTickPinning(A);continue;}
        auto& Offsets=ProphecyWalkPinning::TickOffsets(A);
        const FVector2f Value(S->Current[0],S->Current[1]);
        // Integrate this render interval only. Reweighting a whole 30 Hz endpoint
        // after half of it was already displayed would produce a catch-up jump.
        bool Moved=false;
        const float Fraction=FMath::Clamp(DeltaSeconds*NNUpdateHz*GetAgentTimeDilation(A->GetAgentHandle()),0.f,1.f);
        for(int32 I=0;I<2;++I)
        {
            const FVector Delta=LowerPointToWorld(T->Current.Shift(I,Value[I])*Fraction,Impl->SeedRootRot,FVector3f::ZeroVector,Agent.PublishedYaw);
            Offsets.WorldOffset[I]+=Delta;Moved|=!Delta.IsNearlyZero(1.e-9);
        }
        if(!T->Dirty && T->Last==Value && !Moved)continue;
        T->Last=Value;T->Dirty=false;
        FTransform Result[2][8];
        FLocomotionClamps C;
        C.bClampFoot=A->bOverrideLocomotionFootClamp?A->bLocomotionFootClamp:bClampFoot;
        C.FootClampLengthMultiplier=A->bOverrideLocomotionFootClamp?1.f:FootClampLengthMultiplier;
        C.FootLeeway=A->bOverrideLocomotionFootClamp?A->LocomotionFootClampLeewayCm/100.f:0.f;
        C.bClampCalf=A->bOverrideLocomotionCalfClamp?A->bLocomotionCalfClamp:bClampCalf;
        C.CalfClampLengthMultiplier=A->bOverrideLocomotionCalfClamp?1.f:CalfClampLengthMultiplier;
        C.CalfLeeway=A->bOverrideLocomotionCalfClamp?A->LocomotionCalfClampLeewayCm/100.f:0.f;
        for(int32 End=0;End<2;++End)
        {
            const auto* Base=End?T->BaseCurrent:T->BasePrevious;
            for(int32 J=0;J<8;++J)Result[End][J]=Base[J];
            const float Yaw=End?Agent.PublishedYaw:Agent.PreviousPublishedYaw;
            FVector3f Shift[2];
            for(int32 I=0;I<2;++I) Shift[I]=TransformRow(TransformRow(UnrealToTraining(Offsets.WorldOffset[I]),YawMatrix(Yaw)),Transpose(Impl->SeedRootRot));
            if(Shift[0].IsNearlyZero(1.e-9f) && Shift[1].IsNearlyZero(1.e-9f))continue;
            const float* Lower=StateSlice(End?Impl->PublishedStateBuffer:Impl->PreviousPublishedStateBuffer,Index);
            const float* Upper=UpperStateSlice(End?Impl->UpperPublishedStateBuffer:Impl->UpperPreviousPublishedStateBuffer,Index);
            const float W=End?Agent.PublishedWalkWeight:Agent.PreviousPublishedWalkWeight;
            const FVector2f Weights=End?Agent.PublishedLegWalkWeights:Agent.PreviousPublishedLegWalkWeights;
            float Changed[StateDim];FMemory::Memcpy(Changed,Lower,sizeof(Changed));
            for(int32 I=0;I<2;++I)
            {
                if(Shift[I].IsNearlyZero(1.e-9f))continue;
                ShiftTickPinningLeg(Impl,A,T->PoseId,I,W,Weights[I],Shift[I],Lower,Changed,
                    C.bClampCalf,PreserveTickPinningHinge());
            }
            FTransform Before[FullBodyBoneCount],After[FullBodyBoneCount];
            DecodeLocomotionPose(Impl,Lower,Upper,W,MakeArrayView(Before),nullptr,C,&Weights);
            DecodeLocomotionPose(Impl,Changed,Upper,W,MakeArrayView(After),nullptr,C,&Weights);
            for(int32 J=0;J<8;++J)
            {
                if(Shift[J/4].IsNearlyZero(1.e-9f))continue;
                const int32 B=T->Bones[J];
                Result[End][J].AddToTranslation(After[B].GetLocation()-Before[B].GetLocation());
                Result[End][J].SetRotation((After[B].GetRotation()*Before[B].GetRotation().Inverse()*Base[J].GetRotation()).GetNormalized());
            }
        }
        FProphecyNNPoseStore::UpdateTickPinningLegs(T->PoseId,MakeArrayView(T->Bones),MakeArrayView(Result[0]),MakeArrayView(Result[1]));
        FVector2f Effective;
        for(int32 I=0;I<2;++I) Effective[I]=T->Current.OtherPin[I]+T->Current.WalkWeight[I]*T->Current.Effective(I,Value[I]);
        Agent.PinProbability=Effective;
        T->Effective=Effective;T->SampleTime=GetWorld()->GetTimeSeconds();
    }
}


// Carry only the newly applied pin correction into the next real NN input.
// Do this before physical feedback so an actual simulation sample still wins.
void AProphecyNNLocomotionManager::CommitWalkTickPinning()
{
    const auto* Clock=ProphecyAgentTime::Context(this);
    for(int32 Index=0;Index<AgentActors.Num();++Index)
    {
        if(Clock && !Clock->Step->Due[Index])continue;
        const AProphecyAgent* A=AgentActors[Index];auto* T=ProphecyWalkPinning::FindTickPinning(A);
        if(!T || !T->HasBase)continue;
        const auto& Agent=Impl->Agents[Index];
        if(!A->bNNInferenceEnabled || Agent.Slash.bActive || Agent.DefensePose)continue;
        auto& Offsets=ProphecyWalkPinning::TickOffsets(A);
        for(int32 I=0;I<2;++I)
        {
            if(Offsets.WorldOffset[I].IsNearlyZero(1.e-9))continue;
            const FVector3f World=UnrealToTraining(Offsets.WorldOffset[I]);
            const int32 O=9+16*I;
            auto Shift=[&](float* State,float Yaw,bool Recurrent)
            {
                const FVector3f D=TransformRow(TransformRow(World,YawMatrix(Yaw)),Transpose(Impl->SeedRootRot));
                // Feed the new pin displacement into the policy. The connected
                // knee remains a presentation solve, just as at policy cadence.
                if(Recurrent && UsePresentationRecovery())
                { WriteStateVec3(State,O,ReadStateVec3(State,O)+D);return; }
                if(PreserveTickPinningHinge())
                {
                    // Current and published states use different root frames. Solve
                    // each from its untouched reference in that frame, before physics
                    // feedback, carrying both the ankle and its connected thigh.
                    float Source[StateDim];FMemory::Memcpy(Source,State,sizeof(Source));
                    ShiftTickPinningLeg(Impl,A,T->PoseId,I,Agent.PublishedWalkWeight,
                        Agent.PublishedLegWalkWeights[I],D,Source,State,
                        A->bOverrideLocomotionCalfClamp?A->bLocomotionCalfClamp:bClampCalf,true);
                }
                else WriteStateVec3(State,O,ReadStateVec3(State,O)+D);
            };
            Shift(StateSlice(Impl->CurStateBuffer,Index),Agent.CurRootYaw,true);
            Shift(StateSlice(Impl->PublishedStateBuffer,Index),Agent.PublishedYaw,false);
            Offsets.WorldOffset[I]=FVector::ZeroVector;
        }
    }
}

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
static void CheckTickPinningHingeReference(FAutomationTestBase& Test)
{
    const FPelvisLegGeometry G{FVector3f::ZeroVector,FVector3f(0,0,-.39f),FVector3f(1,0,0),.425f,-10.f};
    float Source[41]{};
    WriteStateVec3(Source,0,FVector3f(0,0,1));WriteRot6(FMat3f(),Source+3);WriteRot6(FMat3f(),Source+12);
    WriteRot6(AxisAngleMatrix(FVector3f(0,1,0),.0073f),Source+18);
    const FVector3f Hip=ReadStateVec3(Source,0),Upper=TransformRow(G.KneeOffset,MatrixFromRot6(Source+18));
    WriteStateVec3(Source,9,Hip+FVector3f(0,0,Upper.Z-FMath::Sqrt(G.CalfLength*G.CalfLength-Upper.X*Upper.X)));
    const FVector3f OldAxis=SafeNormal(ReadStateVec3(Source,9)-Hip);
    const FVector3f OldPole=ProjectToPlane(Upper,OldAxis);
    float Original[41];FMemory::Memcpy(Original,Source,sizeof(Source));
    for(int32 I=0;I<21;++I)
    {
        const FVector3f Shift(.025f,.001f*I,.025f);
        float Fixed[41];FMemory::Memcpy(Fixed,Source,sizeof(Fixed));
        MoveTickPinningEndpoint(G,9,Shift,Source,Fixed,true,true);
        const FVector3f Axis=SafeNormal(ReadStateVec3(Fixed,9)-Hip);
        const FVector3f Expected=ProjectToPlane(OldPole-(OldAxis+Axis)*
            (FVector3f::DotProduct(OldPole,Axis)/(1.f+FVector3f::DotProduct(OldAxis,Axis))),Axis);
        const FVector3f U=TransformRow(G.KneeOffset,MatrixFromRot6(Fixed+18));
        Test.TestTrue(TEXT("Near-straight tick correction preserves transported source pole"),
            FVector3f::DotProduct(ProjectToPlane(U,Axis),Expected)>.99999f);
        Test.TestTrue(TEXT("Corrected calf stays connected at authored length"),
            FMath::Abs((ReadStateVec3(Fixed,9)-Hip-U).Size()-G.CalfLength)<2.e-6f);
        Test.TestTrue(TEXT("Reachable corrected ankle retained"),
            ReadStateVec3(Fixed,9).Equals(ReadStateVec3(Source,9)+Shift,2.e-6f));
        Test.TestTrue(TEXT("Foot rotation is not altered"),MatrixToQuat(MatrixFromRot6(Fixed+12)).Equals(FQuat::Identity,1.e-7));
    }
    Test.TestTrue(TEXT("Source state remains immutable for recurrence and presentation"),FMemory::Memcmp(Source,Original,sizeof(Source))==0);
    float LeastAgreement=1.f;
    for(float X:{-.025f,.025f})
    {
        float Broken[41];FMemory::Memcpy(Broken,Source,sizeof(Broken));
        MoveTickPinningEndpoint(G,9,FVector3f(X,.01f,.025f),Source,Broken,true,false);
        const FVector3f Axis=SafeNormal(ReadStateVec3(Broken,9)-Hip);
        const FVector3f Expected=ProjectToPlane(OldPole-(OldAxis+Axis)*
            (FVector3f::DotProduct(OldPole,Axis)/(1.f+FVector3f::DotProduct(OldAxis,Axis))),Axis);
        LeastAgreement=FMath::Min(LeastAgreement,FVector3f::DotProduct(
            ProjectToPlane(TransformRow(G.KneeOffset,MatrixFromRot6(Broken+18)),Axis),Expected));
    }
    Test.TestTrue(TEXT("Fixture detects old moved-ankle source-pole regression"),LeastAgreement<.95f);
}
#endif
