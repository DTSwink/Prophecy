// Exact course publication, including the30Hz carrier/pose history needed when
// the caller disables Foot IK and ordinary locomotion resumes.
namespace
{
bool PublishFootIKPose(AProphecyNNLocomotionManager::FImpl& Impl,int32 Index,AProphecyAgent* Actor,int32 PoseId,double SourceTime)
{
    FVector Position,Velocity;float YawDegrees=0;
    if(!ProphecyFootIK::Root(Actor,Position,YawDegrees,&Velocity))return false;
    auto& A=Impl.Agents[Index];const FVector3f Root=UnrealToTraining(Position),Speed=UnrealToTraining(Velocity);const float Yaw=-FMath::DegreesToRadians(YawDegrees);
    const FTransform Carrier=GetUpCarrier(Actor,Root,Yaw);
    auto Previous=TransformSlice(Impl.PreviousComponentTransformBuffer,Index),Current=TransformSlice(Impl.ComponentTransformBuffer,Index),Local=TransformSlice(Impl.LocalTransformBuffer,Index);
    if(!ProphecyFootIK::Apply(Actor,Impl.PublishedBoneNames,Impl.Parents,Previous,Current,Local,Carrier))return false;
    A.PreviousPublishedRoot=A.PublishedRoot=A.CurRootPos=Root;
    FVector OldRoot=Position;float OldYaw=YawDegrees;ProphecyFootIK::History(Actor,OldRoot,OldYaw);A.PrevRootPos=UnrealToTraining(OldRoot);
    A.PreviousPublishedYaw=A.PublishedYaw=A.CurRootYaw=Yaw;A.PrevRootYaw=-FMath::DegreesToRadians(OldYaw);
    A.MoverState.position={Root.X,Root.Z};A.MoverState.velocity={Speed.X,Speed.Z};A.MoverState.yaw_radians=A.MoverState.previous_yaw_radians=Yaw;A.MoverIntent.orientation_yaw_radians=Yaw;
    A.bHasAppliedVisualRoot=true;A.bPhysicalWorldBlockedPending=false;A.PublishedPoseTimeSeconds=SourceTime;
    CommitGetUpPose(Impl,Index,Previous,Current);
    FProphecyNNPoseStore::SetAgentLocalPose(PoseId,Impl.PublishedBoneNames,Local,Previous,Current,Carrier,Carrier,SourceTime,true,false,0,FVector2D::ZeroVector,FProphecyNNFixedArms(),false,false);
    ProphecyNNPresentation::Publish(PoseId,SourceTime,1.f);return true;
}
}

namespace
{
// Stage both samples completely before publishing either one. Rendering is one
// policy interval behind inference, so each actual carrier is transported into
// its existing recurrent frame. The controller clock and roots stay unchanged.
bool SeedFootIKTerrainExitHistory(AProphecyNNLocomotionManager::FImpl& Impl,int32 Index,
    const ProphecyFootIKLive::FSourceSample& Previous,const ProphecyFootIKLive::FSourceSample& Current,
    const FTransform& PreviousCarrier,const FTransform& CurrentCarrier,const FTransform& PublishedCarrier,
    double PreviousTime,double CurrentTime,double Interval,FString& Error)
{
    Error.Reset();
    if(!Impl.Agents.IsValidIndex(Index)||!FMath::IsFinite(PreviousTime)||!FMath::IsFinite(CurrentTime)||
        !FMath::IsFinite(Interval)||Interval<=0||FMath::Abs(CurrentTime-PreviousTime-Interval)>1.e-5||
        PreviousCarrier.ContainsNaN()||CurrentCarrier.ContainsNaN()||PublishedCarrier.ContainsNaN())
    {Error=TEXT("Terrain exit requires consecutive actual30Hz pose samples");return false;}
    const auto& A=Impl.Agents[Index];
    for(const auto* Sample:{&Previous,&Current})
    {
        if(Sample->BodiesWorld.Num()!=25||Sample->RootWorld.ContainsNaN()||Sample->HeadingWorld.ContainsNaN()||
            FVector(Sample->HeadingWorld.X,Sample->HeadingWorld.Y,0).IsNearlyZero())
        {Error=TEXT("Terrain exit requires complete finite body/root/heading history");return false;}
        for(const auto& Body:Sample->BodiesWorld)
            if(Body.ContainsNaN()||!Body.GetRotation().IsNormalized())
            {Error=TEXT("Terrain exit contains an invalid body transform");return false;}
    }
    if(A.PrevRootPos.ContainsNaN()||A.CurRootPos.ContainsNaN()||A.PublishedRoot.ContainsNaN()||
        !FMath::IsFinite(A.PrevRootYaw)||!FMath::IsFinite(A.CurRootYaw)||!FMath::IsFinite(A.PublishedYaw))
    {Error=TEXT("Terrain exit has no finite recurrent root frame");return false;}
    if(Impl.PrevStateBuffer.Num()<(Index+1)*StateDim||Impl.CurStateBuffer.Num()<(Index+1)*StateDim||
        Impl.UpperPreviousStateBuffer.Num()<(Index+1)*UpperStateDim||Impl.UpperCurrentStateBuffer.Num()<(Index+1)*UpperStateDim||
        Impl.UpperCurrentBaseBuffer.Num()<(Index+1)*UpperStateDim||Impl.PreviousPelvisHeadingBuffer.Num()<(Index+1)*9||
        Impl.CurrentPelvisHeadingBuffer.Num()<(Index+1)*9||Impl.PublishedStateBuffer.Num()<(Index+1)*StateDim||
        Impl.UpperPublishedStateBuffer.Num()<(Index+1)*UpperStateDim)
    {Error=TEXT("Terrain exit recurrent buffers are incomplete");return false;}
    float Lower[2][StateDim],Upper[2][UpperStateDim],Heading[2][9],Base[UpperStateDim];
    float PublishedLower[StateDim],PublishedUpper[UpperStateDim];
    const auto EncodeInFrame=[&](const ProphecyFootIKLive::FSourceSample& Sample,const FTransform& ActualCarrier,
        const FVector3f& TargetRoot,float TargetYaw,float* OutLower,float* OutUpper)
    {
        const FTransform FromFrame(FRotator(0,Sample.HeadingWorld.Rotation().Yaw,0),Sample.RootWorld);
        const FVector TargetRootWorld=TrainingToUnreal(TargetRoot);
        const FTransform ToFrame(FRotator(0,-FMath::RadiansToDegrees(TargetYaw),0),TargetRootWorld);
        // Retain the real authored mesh-to-capsule transform. RebaseStateRoot
        // works in the NN contract's axes; using its translation formula here
        // would assume that a custom mesh-relative yaw was zero.
        const FTransform TargetCarrier=ActualCarrier*FromFrame.Inverse()*ToFrame;
        const FVector NavigationLift(0,0,Sample.RootWorld.Z-TargetRootWorld.Z);
        FTransform Local[25];
        for(int32 B=0;B<25;++B)
        {
            FTransform Flat=Sample.BodiesWorld[B];Flat.AddToTranslation(-NavigationLift);
            Local[B]=Flat.GetRelativeTransform(TargetCarrier);
        }
        EncodeComponentPoseToNNStates(Impl,A,Local,OutLower,OutUpper);
    };
    for(int32 SampleIndex=0;SampleIndex<2;++SampleIndex)
    {
        const auto& Sample=SampleIndex?Current:Previous;
        const auto& Carrier=SampleIndex?CurrentCarrier:PreviousCarrier;
        const FVector3f ToRoot=SampleIndex?A.CurRootPos:A.PrevRootPos;
        const float ToYaw=SampleIndex?A.CurRootYaw:A.PrevRootYaw;
        EncodeInFrame(Sample,Carrier,ToRoot,ToYaw,Lower[SampleIndex],Upper[SampleIndex]);
        LowerTransformToHeading(Lower[SampleIndex],0,3,Impl,Heading[SampleIndex]);
        for(float Value:Lower[SampleIndex])if(!FMath::IsFinite(Value)){Error=TEXT("Nonfinite terrain exit lower encoding");return false;}
        for(float Value:Upper[SampleIndex])if(!FMath::IsFinite(Value)){Error=TEXT("Nonfinite terrain exit upper encoding");return false;}
    }
    BuildUpperBaseFromLower(Lower[1],Impl,Base);
    for(float Value:Base)if(!FMath::IsFinite(Value)){Error=TEXT("Nonfinite terrain exit pelvis encoding");return false;}
    // The next ordinary policy step shifts these into its previous endpoint.
    // Replace that pending endpoint too, without changing the already-published
    // PoseStore or any controller/presentation carrier.
    // The future publication carrier can already be farther up the ramp than
    // this displayed sample. Encode against that exact cached world carrier;
    // reusing the displayed navigation lift moves the next predecessor in Z.
    FTransform PublishedLocal[25];
    for(int32 B=0;B<25;++B)PublishedLocal[B]=Current.BodiesWorld[B].GetRelativeTransform(PublishedCarrier);
    EncodeComponentPoseToNNStates(Impl,A,PublishedLocal,PublishedLower,PublishedUpper);
    for(float Value:PublishedLower)if(!FMath::IsFinite(Value)){Error=TEXT("Nonfinite terrain exit publication encoding");return false;}
    for(float Value:PublishedUpper)if(!FMath::IsFinite(Value)){Error=TEXT("Nonfinite terrain exit upper publication encoding");return false;}
    FMemory::Memcpy(StateSlice(Impl.PrevStateBuffer,Index),Lower[0],sizeof(Lower[0]));
    FMemory::Memcpy(StateSlice(Impl.CurStateBuffer,Index),Lower[1],sizeof(Lower[1]));
    FMemory::Memcpy(UpperStateSlice(Impl.UpperPreviousStateBuffer,Index),Upper[0],sizeof(Upper[0]));
    FMemory::Memcpy(UpperStateSlice(Impl.UpperCurrentStateBuffer,Index),Upper[1],sizeof(Upper[1]));
    FMemory::Memcpy(UpperStateSlice(Impl.UpperCurrentBaseBuffer,Index),Base,sizeof(Base));
    FMemory::Memcpy(TransformStateSlice(Impl.PreviousPelvisHeadingBuffer,Index),Heading[0],sizeof(Heading[0]));
    FMemory::Memcpy(TransformStateSlice(Impl.CurrentPelvisHeadingBuffer,Index),Heading[1],sizeof(Heading[1]));
    FMemory::Memcpy(StateSlice(Impl.PublishedStateBuffer,Index),PublishedLower,sizeof(PublishedLower));
    FMemory::Memcpy(UpperStateSlice(Impl.UpperPublishedStateBuffer,Index),PublishedUpper,sizeof(PublishedUpper));
    Impl.Agents[Index].bHasPhysicalSample=false;
    return true;
}
}

bool AProphecyNNLocomotionManager::ReseedFootIKTerrainExit(AProphecyAgent* Actor,
    const ProphecyFootIKLive::FSourceSample& Previous,const ProphecyFootIKLive::FSourceSample& Current,
    double PreviousTimeSeconds,double CurrentTimeSeconds,FString& Error)
{
    Error.Reset();
    if(!IsInGameThread()||!Impl||!Impl->bInitialized||!IsValid(Actor)||ResolveAgent(Actor->GetAgentHandle())!=Actor)
    {Error=TEXT("Terrain exit requires an initialized registered game agent");return false;}
    const int32 Index=Actor->GetAgentHandle().Index;const auto& A=Impl->Agents[Index];
    if(ProphecyFootIKSurface::Active(Actor)||A.bUseWalkPolicy||A.RecoveryWeights.NeedsWalk())
    {Error=TEXT("Terrain exit requires the ordinary unblended Run policy");return false;}
    for(const auto* Sample:{&Previous,&Current})
        if(Sample->RootWorld.ContainsNaN()||Sample->HeadingWorld.ContainsNaN()||
            FVector(Sample->HeadingWorld.X,Sample->HeadingWorld.Y,0).IsNearlyZero())
        {Error=TEXT("Terrain exit requires finite actual root headings");return false;}
    if(!Current.RootWorld.Equals(Actor->GetRootLowPoint(),.01))
    {Error=TEXT("Terrain exit current sample does not match the actual root");return false;}
    const float PreviousYaw=-FMath::DegreesToRadians(Previous.HeadingWorld.Rotation().Yaw);
    const float CurrentYaw=-FMath::DegreesToRadians(Current.HeadingWorld.Rotation().Yaw);
    const FVector PreviousVirtual=TrainingToUnreal(A.PreviousPublishedRoot),PublishedVirtual=TrainingToUnreal(A.PublishedRoot);
    FVector PreviousPublished=PreviousVirtual,Published=PublishedVirtual;
    ProphecyFootIKNavigation::PublicationCarriers(Actor,A.PublishedPoseTimeSeconds,
        PreviousVirtual,PublishedVirtual,PreviousPublished,Published);
    return SeedFootIKTerrainExitHistory(*Impl,Index,Previous,Current,
        GetUpCarrier(Actor,UnrealToTraining(Previous.RootWorld),PreviousYaw),
        GetUpCarrier(Actor,UnrealToTraining(Current.RootWorld),CurrentYaw),
        GetUpCarrier(Actor,UnrealToTraining(Published),A.PublishedYaw),
        PreviousTimeSeconds,CurrentTimeSeconds,1./NNUpdateHz,Error);
}

bool AProphecyNNLocomotionManager::RestoreFootIKSurfacePolicy(AProphecyAgent* Actor,FString& Error)
{
    Error.Reset();if(!Impl||!Impl->bInitialized||!IsValid(Actor)||ResolveAgent(Actor->GetAgentHandle())!=Actor)return false;
    if(!ProphecyFootIKSurface::Active(Actor))return true;
    ProphecyFootIKSurface::FPolicyHandoff H;if(!ProphecyFootIKSurface::ReadPolicyHandoff(Actor,H,Error))return false;
    const int32 I=Actor->GetAgentHandle().Index;auto& A=Impl->Agents[I];
    if(H.Previous.BodiesWorld.Num()!=25||H.Current.BodiesWorld.Num()!=25){Error=TEXT("Incomplete surface policy handoff");return false;}
    A.PrevRootPos=UnrealToTraining(H.Previous.RootWorld);A.CurRootPos=UnrealToTraining(H.Current.RootWorld);
    A.PrevRootYaw=-FMath::DegreesToRadians(H.Previous.HeadingWorld.Rotation().Yaw);A.CurRootYaw=-FMath::DegreesToRadians(H.Current.HeadingWorld.Rotation().Yaw);
    const FTransform OldCarrier=GetUpCarrier(Actor,A.PrevRootPos,A.PrevRootYaw),Carrier=GetUpCarrier(Actor,A.CurRootPos,A.CurRootYaw);
    FTransform Previous[25],Current[25];for(int32 B=0;B<25;++B){Previous[B]=H.Previous.BodiesWorld[B].GetRelativeTransform(OldCarrier);Current[B]=H.Current.BodiesWorld[B].GetRelativeTransform(Carrier);}
    float* Prev=StateSlice(Impl->PrevStateBuffer,I),*Now=StateSlice(Impl->CurStateBuffer,I);
    float* PrevUpper=UpperStateSlice(Impl->UpperPreviousStateBuffer,I),*NowUpper=UpperStateSlice(Impl->UpperCurrentStateBuffer,I);
    EncodeComponentPoseToNNStates(*Impl,A,Previous,Prev,PrevUpper);EncodeComponentPoseToNNStates(*Impl,A,Current,Now,NowUpper);
    BuildUpperBaseFromLower(Now,*Impl,UpperStateSlice(Impl->UpperCurrentBaseBuffer,I));
    LowerTransformToHeading(Prev,0,3,*Impl,TransformStateSlice(Impl->PreviousPelvisHeadingBuffer,I));
    LowerTransformToHeading(Now,0,3,*Impl,TransformStateSlice(Impl->CurrentPelvisHeadingBuffer,I));
    const FVector3f Velocity=UnrealToTraining(H.VelocityWorld);
    A.MoverState.position={A.CurRootPos.X,A.CurRootPos.Z};A.MoverState.velocity={Velocity.X,Velocity.Z};
    A.MoverState.yaw_radians=A.CurRootYaw;A.MoverState.previous_yaw_radians=A.PrevRootYaw;A.bHasPhysicalSample=false;
    // The visible physical-target pair stays intact until ordinary publication;
    // it is deliberately separate from the clean policy recurrence above.
    return true;
}

void AProphecyNNLocomotionManager::ReleaseFootIKNavigation(AProphecyAgent* Actor)
{
    const double Lift=ProphecyFootIKNavigation::Remove(Actor);
    if(!Lift||!Impl||!Impl->bInitialized||!IsValid(Actor)||ResolveAgent(Actor->GetAgentHandle())!=Actor)return;
    auto& A=Impl->Agents[Actor->GetAgentHandle().Index];const FVector3f Shift(0,float(Lift*.01),0);
    A.PrevRootPos+=Shift;A.CurRootPos+=Shift;A.PreviousPublishedRoot+=Shift;A.PublishedRoot+=Shift;
    A.FedInputRoot+=Shift;A.WindowPreviousRoot+=Shift;for(auto& Root:A.FedFutureRootPositions)Root+=Shift;
    // These are a new world origin for the same root-local NN samples, not a
    // collision correction. RebaseStateRoot here would undo the ramp climb.
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyFootIKTerrainExitTests.inl"
#endif
