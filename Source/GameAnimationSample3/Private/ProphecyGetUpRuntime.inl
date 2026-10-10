// Included in the manager translation unit after its pose sampler and decoder.
#include "Animation/AnimSequence.h"
#include "ProphecyPhysicalProfileLibrary.h"
namespace
{
FTransform GetUpCarrier(const AProphecyAgent* A,const FVector3f& Root,float Yaw)
{
    const auto* Capsule=A->GetAgentCapsule();const auto* Mesh=A->GetAgentMesh();
    const FTransform Relative=A->bManualNNPoseApplication?Mesh->GetRelativeTransform():A->GetAuthoredMeshRelativeTransform();
    return Relative*FTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),
        TrainingToUnreal(Root)+FVector(0,0,Capsule->GetScaledCapsuleHalfHeight()));
}
// Fit yaw without flattening the fallen pelvis or assuming a skeleton forward axis.
double GetUpYaw(const FQuat& Clip,const FQuat& Physical)
{
    double Dot=0,Cross=0;
    for(const FVector Axis:{FVector::ForwardVector,FVector::RightVector,FVector::UpVector})
    { const FVector C=Clip.RotateVector(Axis),P=Physical.RotateVector(Axis);Dot+=C.X*P.X+C.Y*P.Y;Cross+=C.X*P.Y-C.Y*P.X; }
    return FMath::Atan2(Cross,Dot);
}
void CommitGetUpPose(AProphecyNNLocomotionManager::FImpl& Impl,int32 I,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current)
{
    auto& A=Impl.Agents[I];
    float* PL=StateSlice(Impl.PreviousPublishedStateBuffer,I),*L=StateSlice(Impl.PublishedStateBuffer,I);
    float* PU=UpperStateSlice(Impl.UpperPreviousPublishedStateBuffer,I),*U=UpperStateSlice(Impl.UpperPublishedStateBuffer,I);
    EncodeComponentPoseToNNStates(Impl,A,Previous,PL,PU);EncodeComponentPoseToNNStates(Impl,A,Current,L,U);
    auto Copy=[&](bool Prev)
    {
        float* Lower=StateSlice(Prev?Impl.PrevStateBuffer:Impl.CurStateBuffer,I);
        float* Upper=UpperStateSlice(Prev?Impl.UpperPreviousStateBuffer:Impl.UpperCurrentStateBuffer,I);
        FMemory::Memcpy(Lower,Prev?PL:L,StateDim*sizeof(float));FMemory::Memcpy(Upper,Prev?PU:U,UpperStateDim*sizeof(float));
        const FVector3f From=Prev?A.PreviousPublishedRoot:A.PublishedRoot,To=Prev?A.PrevRootPos:A.CurRootPos;
        const float FromYaw=Prev?A.PreviousPublishedYaw:A.PublishedYaw,ToYaw=Prev?A.PrevRootYaw:A.CurRootYaw;
        const FVector3f Delta=TransformRow(To-From,YawMatrix(FromYaw));const float DY=WrapAngle(ToYaw-FromYaw);
        RebaseStateRoot(Lower,Impl,Delta,DY);RebaseUpperHeadingState(Upper,Delta,DY);
        if(!Prev)BuildUpperBaseFromLower(Lower,Impl,UpperStateSlice(Impl.UpperCurrentBaseBuffer,I));
        LowerTransformToHeading(Lower,0,3,Impl,TransformStateSlice(Prev?Impl.PreviousPelvisHeadingBuffer:Impl.CurrentPelvisHeadingBuffer,I));
    };
    Copy(true);Copy(false);
}
void TemperGetUpUpper(const AProphecyNNLocomotionManager::FImpl& Impl,const ProphecyGetUp::FActive& S,
    TArrayView<FTransform> Candidate)
{
    if(S.Core>=1 && S.Hands.Normal())return;
    FTransform Local[25];
    for(int32 B=0;B<25;++B)
    {
        const int32 P=Impl.Parents[B];Local[B]=P<0?Candidate[B]:Candidate[B].GetRelativeTransform(Candidate[P]);
        if(S.Core<1 && Impl.UpperCoreBoneNames.Contains(Impl.BodyNames[B]))
        {
            const FQuat Previous=S.Current[B].GetRelativeTransform(S.Current[P]).GetRotation();
            Local[B].SetRotation(FQuat::Slerp(Previous,Local[B].GetRotation(),S.Core).GetNormalized());
        }
    }
    for(int32 B=0;B<25;++B)
    { const int32 P=Impl.Parents[B];Candidate[B]=P<0?Local[B]:Local[B]*Candidate[P]; }
    const int32 Spine=Impl.BodyNames.IndexOfByKey(TEXT("spine_05"));
    if(Spine==INDEX_NONE)return;
    for(int32 Side=0;Side<2;++Side)
    {
        const auto& Follow=S.Hands.Hand[Side];if(Follow.Normal())continue;
        const auto& Arm=Impl.UpperArms[Side];
        const FTransform Target=ProphecyHandRecovery::TemperTarget(Follow,S.Current[Spine],Candidate[Spine],S.Current[Arm.End],Candidate[Arm.End]);
        auto Carry=[&](int32 B){return S.Current[B].GetRelativeTransform(S.Current[Spine])*Candidate[Spine];};
        ProphecyHandChain::Resolve(Carry(Arm.Start),Carry(Arm.Mid),Carry(Arm.End),
            Candidate[Arm.Start],Candidate[Arm.Mid],Candidate[Arm.End],Target,
            LocalTrainingToUnreal(Impl.UpperLocalOffsets[Arm.Mid]),LocalTrainingToUnreal(Arm.LocalPoleAxes[0]),
            Follow.Rotation,Impl.UpperLocalOffsets[Arm.End].Size()*100.);
        SetForearmRollFromUpperArm(Impl.UpperLocalOffsets[Arm.End],Side,Candidate[Arm.Start],Candidate[Arm.Mid],Candidate[Arm.End]);
    }
}
bool ApplyGetUpPresentation(AProphecyNNLocomotionManager::FImpl& Impl,int32 I,AProphecyAgent* Actor,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,
    const FTransform& PreviousCarrier,const FTransform& Carrier)
{
    auto* S=ProphecyGetUp::Find(Actor);if(!S)return false;
    if(S->LastSample!=S->Elapsed)
    {
        TemperGetUpUpper(Impl,*S,Current);
        FTransform Clip[25],CandidateLocal[25],ClipLocal[25];
        if(!SampleAnimationComponentPose(Impl,Actor->GetPoseReferenceMesh()->GetSkeletalMeshAsset(),
            S->Animation.Get(),S->Playback,false,MakeArrayView(Clip),false))
        { ProphecyGetUp::Cancel(Actor);return false; }
        const float Entry=S->Profile.Entry<=0?1.f:ProphecyGetUp::Curve(float(S->Elapsed/S->Profile.Entry),S->Profile.EntryCurve);
        for(int32 B=0;B<25;++B)
        {
            const int32 Parent=Impl.Parents[B];
            // Snapshot and clip share the fixed world anchor. Blend parent locals,
            // preserving connected chains rather than linearly pulling world-space joints apart.
            const FTransform C=Parent<0?Clip[B]:Clip[B].GetRelativeTransform(Clip[Parent]);
            const FTransform P=Parent<0?S->Snapshot[B]:S->Snapshot[B].GetRelativeTransform(S->Snapshot[Parent]);
            ClipLocal[B].Blend(P,C,Entry);
            CandidateLocal[B]=Parent<0?Current[B]:Current[B].GetRelativeTransform(Current[Parent]);
        }
        if(S->Published)
        { for(int32 B=0;B<25;++B)S->Previous[B]=S->Current[B];S->PreviousCarrier=S->CurrentCarrier; }
        for(int32 B=0;B<25;++B)
        {
            const int32 Parent=Impl.Parents[B];float W=S->CoreAlpha;
            if(B==0)W=S->PelvisAlpha;
            for(int32 Side=0;Side<2;++Side)
            {
                const auto& L=Impl.Limbs[Side];const auto& Arm=Impl.UpperArms[Side];
                if(B==L.Start || B==L.Mid || B==L.End || B==L.Toe)W=S->FeetAlpha;
                if(B==Arm.Start || B==Arm.Mid || B==Arm.End)W=S->HandAlpha[Side];
            }
            FTransform Source=ClipLocal[B];
            if(Parent<0)Source=(Source*S->Anchor).GetRelativeTransform(Carrier);
            FTransform Blended;Blended.Blend(Source,CandidateLocal[B],W);Blended.NormalizeRotation();
            S->Current[B]=Parent<0?Blended:Blended*S->Current[Parent];
        }
        S->CurrentCarrier=Carrier;S->LastSample=S->Elapsed;S->Published=true;
    }
    for(int32 B=0;B<25;++B)
    {
        Previous[B]=(S->Previous[B]*S->PreviousCarrier).GetRelativeTransform(PreviousCarrier);
        Current[B]=(S->Current[B]*S->CurrentCarrier).GetRelativeTransform(Carrier);
        const int32 P=Impl.Parents[B];Local[B]=P<0?Current[B]:Current[B].GetRelativeTransform(Current[P]);
    }
    CommitGetUpPose(Impl,I,Previous,Current);return true;
}
}

bool AProphecyNNLocomotionManager::StartAgentGetUp(FProphecyAgentHandle Handle,float Rate)
{
    auto* Actor=ResolveAgent(Handle);
    if(!Impl || !Impl->bInitialized || !Actor || !Actor->bNNInferenceEnabled || IsSimBridgeActive() ||
        !FMath::IsFinite(Rate) || Rate<=0 || ProphecyGetUp::IsActive(Actor))return false;
    const auto* Mesh=Actor->GetPoseReferenceMesh();auto* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;
    if(!Asset || !Actor->GetAgentMesh() || !Actor->GetAgentCapsule())return false;
    auto Profile=ProphecyGetUp::Configured(Actor);
    UAnimSequence* Clips[2]={Profile.Front.Get(),Profile.Back.Get()};
    if(!Clips[0])Clips[0]=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/_mygame/animations/AS_GetUp_Front1.AS_GetUp_Front1"));
    if(!Clips[1])Clips[1]=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/_mygame/animations/AS_GetUp_Back1.AS_GetUp_Back1"));
    FTransform Initial[2][25],Physical[25],Last[25];
    for(int32 Side=0;Side<2;++Side)if(!Clips[Side] || Clips[Side]->GetPlayLength()<=0 ||
        !SampleAnimationComponentPose(*Impl,Asset,Clips[Side],0,false,MakeArrayView(Initial[Side]),false))
    { UE_LOG(LogProphecyNNLocomotion,Warning,TEXT("Get Up: front/back clips must match the agent skeleton."));return false; }
    if(!Actor->SampleActualComponentPose(Impl->PublishedBoneNames,MakeArrayView(Physical)))return false;
    const FTransform PhysicalReference=Actor->GetAgentMesh()->GetComponentTransform();
    for(auto& P:Physical)P=P*PhysicalReference;
    // Pelvis orientation relative to gravity distinguishes face-up from face-down,
    // regardless of world yaw or the animation's imported skeletal axes.
    double Yaws[2],Errors[2];
    for(int32 Side=0;Side<2;++Side)
    {
        Yaws[Side]=GetUpYaw(Initial[Side][0].GetRotation(),Physical[0].GetRotation());
        const FQuat Q=FQuat(FVector::UpVector,Yaws[Side])*Initial[Side][0].GetRotation();
        Errors[Side]=Q.AngularDistance(Physical[0].GetRotation());
    }
    const int32 Side=Errors[0]<=Errors[1]?0:1;
    if(!SampleAnimationComponentPose(*Impl,Asset,Clips[Side],Clips[Side]->GetPlayLength(),false,MakeArrayView(Last),false))return false;
    FHitResult Ground;FCollisionQueryParams Query(SCENE_QUERY_STAT(ProphecyGetUpGround),false,Actor);
    FCollisionObjectQueryParams GroundObjects(ECC_WorldStatic);
    // The project's floor is an object channel of its own. Resolve its configured
    // name so channel reordering does not silently break recovery.
    for(int32 Channel=0;Channel<ECC_MAX;++Channel)
        if(UCollisionProfile::Get()->ReturnChannelNameFromContainerIndex(Channel)==TEXT("floor"))
            GroundObjects.AddObjectTypesToQuery(ECollisionChannel(Channel));
    const FVector Pelvis=Physical[0].GetLocation();
    if(!GetWorld()->LineTraceSingleByObjectType(Ground,Pelvis+FVector(0,0,100),Pelvis-FVector(0,0,300),
        GroundObjects,Query) || Ground.ImpactNormal.Z<.5f)
    { UE_LOG(LogProphecyNNLocomotion,Warning,TEXT("Get Up: no supporting floor below the pelvis."));return false; }
    ProphecyGetUp::FActive State;State.Profile=Profile;State.Rate=Rate;
    State.ClipDuration=double(Clips[Side]->GetPlayLength())/Rate;State.Animation.Reset(Clips[Side]);
    const FQuat Yaw(FVector::UpVector,Yaws[Side]);
    FVector Anchor=Pelvis-Yaw.RotateVector(Initial[Side][0].GetLocation());
    // Match the clip's final ankle/toe floor to the normal skeleton's sole height.
    double ClipFloor=DBL_MAX,NormalFloor=DBL_MAX;
    const auto& Ref=Asset->GetRefSkeleton();TArray<FTransform> Reference;
    Reference.SetNum(Ref.GetNum());
    for(int32 B=0;B<Ref.GetNum();++B){const int32 P=Ref.GetParentIndex(B);Reference[B]=P<0?Ref.GetRefBonePose()[B]:Ref.GetRefBonePose()[B]*Reference[P];}
    for(const auto& L:Impl->Limbs)for(int32 B:{L.End,L.Toe})
    {
        ClipFloor=FMath::Min(ClipFloor,Last[B].GetLocation().Z);
        NormalFloor=FMath::Min(NormalFloor,Reference[Ref.FindBoneIndex(Impl->BodyNames[B])].GetLocation().Z);
    }
    Anchor.Z=Ground.ImpactPoint.Z-ClipFloor+NormalFloor+Profile.GroundOffset;
    State.Anchor=FTransform(Yaw,Anchor);
    for(int32 B=0;B<25;++B)State.Snapshot[B]=Physical[B].GetRelativeTransform(State.Anchor);
    // Resolve all fall/animation data before interrupting anything.
    StopAgentNNDefense(Handle);StopAgentNNAttack(Handle);
    if(!IsValid(Actor) || ResolveAgent(Handle)!=Actor)return false;
    auto& A=Impl->Agents[Handle.Index];
    if(A.Slash.bActive || A.DefensePose)return false; // A callback started a replacement.
    ProphecyBlendClock::Stop(Actor,ProphecyBlendClock::EKind::AnimationLayer);
    A.AnimationLayer.Reset();Actor->ActiveNNAnimationLayerAsset=nullptr;
    ProphecyArmedPose::Cancel(Actor);ProphecyFKReturn::Cancel(Actor);ProphecyAttackRecovery::Cancel(Actor);
    ProphecyLowerTempering::Remove(Actor);ProphecyHandRecovery::CancelMotion(Actor);ProphecyCoreTempering::CancelMotion(Actor);
    ProphecyUpperBodyInertia::Cancel(Actor);ProphecySlashReturn::Cancel(Actor);ProphecyLegRecovery::Cancel(Actor);
    ProphecyWalkPinning::ResetSmoothing(Actor);ProphecyRootBalance::ResetMotion(Actor);
    ProphecyPelvisInertia::ResetMotion(Actor);ProphecyHandInertia::ResetMotion(Actor);
    FVector CarrierLocation=State.Anchor.TransformPosition(FVector(Last[0].GetLocation().X,Last[0].GetLocation().Y,0));
    // Use the actual floor as the mover's low point; the authored mesh offset
    // determines the component frame, independently of the imported clip origin.
    const FTransform Relative=Actor->bManualNNPoseApplication?Actor->GetAgentMesh()->GetRelativeTransform():Actor->GetAuthoredMeshRelativeTransform();
    const FQuat ActorYaw=(Yaw*Relative.GetRotation().Inverse()).GetNormalized();
    const FVector RootWorld(CarrierLocation.X,CarrierLocation.Y,Ground.ImpactPoint.Z);
    const FVector3f Root=UnrealToTraining(RootWorld);const float RootYaw=-FMath::DegreesToRadians(float(ActorYaw.Rotator().Yaw));
    A.CurRootPos=A.PrevRootPos=A.PublishedRoot=A.PreviousPublishedRoot=Root;
    A.CurRootYaw=A.PrevRootYaw=A.PublishedYaw=A.PreviousPublishedYaw=RootYaw;
    A.MoverState={};A.MoverState.position={Root.X,Root.Z};A.MoverState.yaw_radians=A.MoverState.previous_yaw_radians=RootYaw;
    A.MoverIntent.speed_amplitude=0;A.MoverIntent.orientation_yaw_radians=RootYaw;
    A.bHasPhysicalSample=false;A.PinProbability=FVector2f::ZeroVector;
    if(auto* W=ProphecyNNRootWindow::Find(Actor)){const auto Factors=W->Factors;*W={};W->Factors=Factors;}
    State.PreviousCarrier=State.CurrentCarrier=GetUpCarrier(Actor,Root,RootYaw);
    for(int32 B=0;B<25;++B)State.Previous[B]=State.Current[B]=Physical[B].GetRelativeTransform(State.CurrentCarrier);
    ProphecyGetUp::Install(Actor,MoveTemp(State));
    // Publish snapshot targets before applying any restored drive strength.
    PublishAgentPose(Handle.Index,A.PublishedPoseTimeSeconds);
    FProphecyNNPoseStore::SetInterpolationMode(PoseStoreAgentBase+Handle.Index,Actor->GetNNInterpolationMode());
    if(UProphecyPhysicalProfileLibrary::BlendAllBodyMagnetizationToSnapshot(Actor,Profile.Magnetization,Profile.Snapshot)==0)
        Actor->BlendBodyMagnetizationBelow(TEXT("pelvis"),true,1,1,Profile.Magnetization);
    UE_LOG(LogProphecyNNLocomotion,Display,TEXT("Get Up: %s clip=%s rate=%.3f lower=%.3f upper=%.3f"),
        *Actor->GetName(),*Clips[Side]->GetName(),Rate,Profile.LowerStart,Profile.UpperStart);
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGetUpPoseMathTest,"Prophecy.GetUp.PoseMath",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyGetUpPoseMathTest::RunTest(const FString&)
{
    const FQuat Clip=FRotator(83,17,-62).Quaternion();
    for(double Degrees:{-170.,-30.,0.,95.,179.})
    {
        const FQuat Physical=FQuat(FVector::UpVector,FMath::DegreesToRadians(Degrees))*Clip;
        const FQuat Fit=FQuat(FVector::UpVector,GetUpYaw(Clip,Physical))*Clip;
        TestTrue(TEXT("Yaw alignment retains fallen orientation at every heading"),Fit.AngularDistance(Physical)<1.e-6);
    }
    AProphecyNNLocomotionManager::FImpl Impl;
    Impl.BodyNames.Init(NAME_None,25);Impl.Parents.Init(0,25);Impl.Parents[0]=-1;
    Impl.UpperLocalOffsets.Init(FVector3f::ZeroVector,25);
    Impl.BodyNames[1]=TEXT("spine_05");Impl.UpperCoreBoneNames.Add(TEXT("spine_05"));
    ProphecyGetUp::FActive S;FTransform Candidate[25];
    for(int32 B=0;B<25;++B)S.Current[B]=Candidate[B]=FTransform(FVector(0,0,100));
    S.Current[0]=Candidate[0]=FTransform::Identity;
    for(int32 Side=0;Side<2;++Side)
    {
        auto& Arm=Impl.UpperArms[Side];Arm.Start=2+Side*3;Arm.Mid=Arm.Start+1;Arm.End=Arm.Start+2;
        Impl.Parents[Arm.Start]=1;Impl.Parents[Arm.Mid]=Arm.Start;Impl.Parents[Arm.End]=Arm.Mid;
        Impl.UpperLocalOffsets[Arm.Mid]=FVector3f(.3f,0,0);Impl.UpperLocalOffsets[Arm.End]=FVector3f(.2f,0,0);
        Arm.LocalPoleAxes[0]=FVector3f(0,0,1);
        for(int32 J=0;J<3;++J)S.Current[Arm.Start+J]=Candidate[Arm.Start+J]=FTransform(FVector(J==0?0:J==1?30:50,Side?20:-20,100));
    }
    const FTransform Turn(FRotator(20,40,10),FVector(12,20,0));
    for(int32 B=1;B<8;++B)Candidate[B]=Candidate[B]*Turn;
    S.Core=0;
    TemperGetUpUpper(Impl,S,MakeArrayView(Candidate));
    TestTrue(TEXT("Core zero holds parent-local rotation"),Candidate[1].GetRelativeTransform(Candidate[0]).GetRotation().Equals(FQuat::Identity,1.e-6));
    const auto RelativeArm=Candidate[4].GetRelativeTransform(Candidate[1]);
    TestTrue(TEXT("Core carries the arm attachment"),RelativeArm.GetLocation().Equals(FVector(50,-20,0),1.e-4));
    S.Core=1;S.Hands.Hand[0]={0,0,0};
    Candidate[4].AddToTranslation(FVector(-5,3,0));
    const FTransform Expected=S.Current[4].GetRelativeTransform(S.Current[1])*Candidate[1];
    TemperGetUpUpper(Impl,S,MakeArrayView(Candidate));
    TestTrue(TEXT("Zero hand follow holds in the moved spine frame"),Candidate[4].GetLocation().Equals(Expected.GetLocation(),1.e-3));
    TestTrue(TEXT("Zero hand follow preserves carried wrist rotation"),Candidate[4].GetRotation().Equals(Expected.GetRotation(),1.e-6));
    return !HasAnyErrors();
}
#endif
