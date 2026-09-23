// Included by the standard-constraint runtime: no new UObject or retained character layout.
// Only ordinary skeletal endpoints of a constraint are admitted; agent rigs keep their owner.
namespace ProphecyJolt::ConstrainedSkeleton
{
struct FState
{
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<USkeletalMesh> Asset;
    TWeakObjectPtr<UPhysicsAsset> PhysicsAsset;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Native;
    FProphecyJoltRigHandle Rig;
    TArray<FProphecyJoltBodyHandle> Bodies;
    FProphecyJoltRigSnapshot Capture;
    TArray<FTransform> BaseLocal, BodyWorld, AnchorLocal;
    ProphecyJolt::Pose::FPreparedLayout Layout;
    FProphecyJoltComposedPose Pose;
    uint64 Revision = 0;
    TSubclassOf<UAnimInstance> AnimClass;
    EAnimationMode::Type AnimMode;
    FSingleAnimationPlayData AnimationData;
    ECollisionEnabled::Type Collision;
    TEnumAsByte<EKinematicBonesUpdateToPhysics::Type> KinematicUpdate;
    TEnumAsByte<EPhysicsTransformUpdateMode::Type> TransformUpdate;
    bool Tick, EnableAnimation, Pause, NoSkeleton, ForceRef, UpdateRate, Defer, PostProcess;
    bool Committed = false;
    FString Error;
};
TMap<TWeakObjectPtr<USkeletalMeshComponent>, TSharedPtr<FState>> Rigs;

bool Valid(const FState& S)
{
    auto* M = S.Mesh.Get();
    return M && M->IsRegistered() && IsValid(M->GetOwner()) && !M->GetOwner()->IsActorBeingDestroyed()
        && M->GetSkeletalMeshAsset() == S.Asset.Get() && M->GetPhysicsAsset() == S.PhysicsAsset.Get()
        && S.Native.IsValid() && S.Native->OwnsRig(S.Rig);
}

void Retire(const TSharedPtr<FState>& S)
{
    if (S->Native.IsValid() && S->Native->OwnsRig(S->Rig)) S->Native->DestroyRig(S->Rig);
    auto* M = S->Mesh.Get();
    if (!S->Committed || !IsValid(M) || !M->IsRegistered() || M->GetWorld()->bIsTearingDown
        || !IsValid(M->GetOwner()) || M->GetOwner()->IsActorBeingDestroyed()) return;
    S->Committed = false;
    M->HandleExistingParallelEvaluationTask(true,true);
    M->SetAllBodiesSimulatePhysics(false);
    M->SetCollisionEnabled(S->Collision);
    M->SetAnimInstanceClass(S->AnimClass);
    M->AnimationData = S->AnimationData;
    M->SetAnimationMode(S->AnimMode);
    M->KinematicBonesUpdateType = S->KinematicUpdate;
    M->PhysicsTransformUpdateMode = S->TransformUpdate;
    M->bEnableAnimation = S->EnableAnimation; M->bPauseAnims = S->Pause;
    M->bNoSkeletonUpdate = S->NoSkeleton; M->bForceRefpose = S->ForceRef;
    M->bEnableUpdateRateOptimizations = S->UpdateRate; M->bDeferKinematicBoneUpdate = S->Defer;
    M->SetDisablePostProcessBlueprint(S->PostProcess); M->SetComponentTickEnabled(S->Tick);
    // Release leaves simulation off, matching the standard Jolt body adapter. Never resurrect
    // Chaos while the other endpoint remains native. A fresh PIE uses unchanged authored values.
}

bool Publish(FState& S, FString& Error)
{
    if (!Valid(S)) { Error=TEXT("Constrained skeletal binding changed or was destroyed."); return false; }
    auto* M=S.Mesh.Get();
    auto* Anim=Cast<UProphecyJoltPoseAnimInstance>(M->GetAnimInstance());
    if (!Anim) { Error=TEXT("Constrained skeletal pose ownership was replaced."); return false; }
    S.BodyWorld.Reset(S.Bodies.Num());
    for (const auto& H:S.Bodies)
    {
        FProphecyJoltBodyState B; const auto Read=S.Native->ReadBody(H,B);
        if (!Read.IsSuccess()) { Error=Read.Message; return false; }
        S.BodyWorld.Emplace(B.Rotation,B.PositionCm);
    }
    if (!S.Layout.Compose(S.BaseLocal,S.BodyWorld,M->GetComponentTransform(),S.Pose,Error)
        || !Anim->PublishCompletedLocalPose(S.Pose.LocalTransforms,++S.Revision,Error)) return false;
    M->HandleExistingParallelEvaluationTask(true,true);
    if (!Valid(S)) return false;
    M->TickAnimation(0,false);
    if (!Valid(S)) return false;
    M->RefreshBoneTransforms(nullptr);
    if (!Valid(S)) return false;
    M->UpdateKinematicBonesToAnim(M->GetComponentSpaceTransforms(),ETeleportType::TeleportPhysics,
        true,EAllowKinematicDeferral::DisallowDeferral);
    return true;
}

bool Admit(USkeletalMeshComponent& M, FString& Error)
{
    if (Rigs.Contains(&M)) return Valid(*Rigs[&M]);
    if (!M.GetSkeletalMeshAsset() || !M.GetPhysicsAsset() || !M.IsRegistered())
    { Error=TEXT("Skeletal constraint endpoint needs a registered mesh and PHAT."); return false; }
    auto* Native=M.GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Native) return false;
    M.HandleExistingParallelEvaluationTask(true,true);
    auto S=MakeShared<FState>();
    S->Mesh=&M; S->Native=Native; S->Asset=M.GetSkeletalMeshAsset(); S->PhysicsAsset=M.GetPhysicsAsset();
    FProphecyJoltPreparedRig Prepared;
    if (!ProphecyJolt::Rig::CaptureLiveRig(M,S->Capture,Error) || !Prepared.Build(S->Capture,Error)) return false;
    const auto& Ref=M.GetSkeletalMeshAsset()->GetRefSkeleton();
    TArray<int32> Parents; TArray<FProphecyJoltPoseBodyMapping> Mappings;
    const auto& CS=M.GetComponentSpaceTransforms();
    S->BaseLocal=Ref.GetRefBonePose();
    for (int32 I=0;I<Ref.GetNum();++I)
    {
        const int32 P=Ref.GetParentIndex(I); Parents.Add(P);
        if (CS.IsValidIndex(I)) S->BaseLocal[I]=P==INDEX_NONE?CS[I]:CS[I].GetRelativeTransform(CS[P]);
    }
    for (const auto& B:S->Capture.Bodies)
    {
        FProphecyJoltPoseBodyMapping Map; Map.BoneIndex=B.BoneIndex;
        Map.VisualScale=M.GetSocketTransform(B.BodyName,RTS_World).GetScale3D();
        Mappings.Add(Map); S->BodyWorld.Add(B.BodyOriginToWorld);
        S->AnchorLocal.Add(B.BodyOriginToWorld.GetRelativeTransform(M.GetComponentTransform()));
    }
    if (!S->Layout.Build(Ref.GetNum(),Parents,Mappings,Error)
        || !S->Layout.Compose(S->BaseLocal,S->BodyWorld,M.GetComponentTransform(),S->Pose,Error)) return false;
    TArray<FString> Coverage;
    auto Made=Native->CreateRig(S->Capture,Prepared,S->Rig,S->Bodies,Coverage);
    if (!Made.IsSuccess()) { Error=Made.Message; return false; }
    const auto Events=Native->SetRigHitEvents(S->Rig,&M,M.BodyInstance.bNotifyRigidBodyCollision);
    if (!Events.IsSuccess()) { Native->DestroyRig(S->Rig); Error=Events.Message; return false; }
    S->AnimClass=M.GetAnimClass(); S->AnimMode=M.GetAnimationMode(); S->AnimationData=M.AnimationData;
    S->Collision=M.GetCollisionEnabled(); S->KinematicUpdate=M.KinematicBonesUpdateType;
    S->TransformUpdate=M.PhysicsTransformUpdateMode; S->Tick=M.IsComponentTickEnabled();
    S->EnableAnimation=M.bEnableAnimation; S->Pause=M.bPauseAnims; S->NoSkeleton=M.bNoSkeletonUpdate;
    S->ForceRef=M.bForceRefpose; S->UpdateRate=M.bEnableUpdateRateOptimizations;
    S->Defer=M.bDeferKinematicBoneUpdate; S->PostProcess=M.GetDisablePostProcessBlueprint();
    Rigs.Add(&M,S); S->Committed=true;
    M.SetAllBodiesSimulatePhysics(false); M.SetSimulatePhysics(false);
    M.SetAllBodiesPhysicsBlendWeight(0); M.SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    M.PhysicsTransformUpdateMode=EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
    M.KinematicBonesUpdateType=EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
    M.bDeferKinematicBoneUpdate=false; M.bEnableUpdateRateOptimizations=false;
    M.bPauseAnims=false; M.bNoSkeletonUpdate=false; M.bForceRefpose=false;
    M.SetEnableAnimation(true); M.SetDisablePostProcessBlueprint(true); M.SetComponentTickEnabled(false);
    M.SetAnimInstanceClass(UProphecyJoltPoseAnimInstance::StaticClass());
    if (!Publish(*S,Error)) { Rigs.Remove(&M); Retire(S); return false; }
    UE_LOG(LogTemp,Display,TEXT("Jolt skeletal constraint endpoint %s: %d bodies, %d PHAT joints"),
        *M.GetPathName(),S->Bodies.Num(),S->Capture.Joints.Num());
    return true;
}

bool BodyFor(USkeletalMeshComponent& M,FName Bone,FProphecyJoltBodyHandle& Body,FString& Error)
{
    if (!Admit(M,Error)) return false;
    const auto S=Rigs.FindChecked(&M);
    if (Bone.IsNone() && !S->Bodies.IsEmpty()) { Body=S->Bodies[0]; return true; }
    for (int32 I=0;I<S->Capture.Bodies.Num();++I)
        if (S->Capture.Bodies[I].BodyName==Bone) { Body=S->Bodies[I]; return true; }
    Error=FString::Printf(TEXT("Bone %s has no PHAT body on %s."),*Bone.ToString(),*M.GetPathName());
    return false;
}

void Prepare(UWorld* World)
{
    TArray<TSharedPtr<FState>> Entries; Rigs.GenerateValueArray(Entries);
    for (const auto& S:Entries)
    {
        if (S->Mesh.IsValid() && S->Mesh->GetWorld()!=World) continue;
        if (!Valid(*S)) { Rigs.Remove(S->Mesh); Retire(S); continue; }
        for (int32 I=0;I<S->Bodies.Num();++I) if (!S->Capture.Bodies[I].bSimulating)
        {
            auto Target=S->AnchorLocal[I]*S->Mesh->GetComponentTransform(); Target.RemoveScaling();
            const auto Result=S->Native->MoveKinematicBody(S->Bodies[I],Target,World->GetDeltaSeconds());
            if (!Result.IsSuccess() && S->Error!=Result.Message)
            { S->Error=Result.Message; UE_LOG(LogTemp,Error,TEXT("Jolt skeletal anchor: %s"),*S->Error); }
        }
    }
}
void Finish(UWorld* World)
{
    TArray<TSharedPtr<FState>> Entries; Rigs.GenerateValueArray(Entries);
    for (const auto& S:Entries) if (S->Mesh.IsValid() && S->Mesh->GetWorld()==World)
    {
        FString Error;
        if (!Publish(*S,Error) && S->Error!=Error)
        { S->Error=Error; UE_LOG(LogTemp,Error,TEXT("Jolt constrained skeleton: %s"),*Error); }
    }
}
void Disable(UWorld* World)
{
    TArray<TSharedPtr<FState>> Entries;
    for (auto It=Rigs.CreateIterator();It;++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld()==World) { Entries.Add(It.Value()); It.RemoveCurrent(); }
    for (const auto& S:Entries) Retire(S);
}
#if !UE_BUILD_SHIPPING
void Audit(const TArray<FString>& Args,UWorld* World)
{
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (const auto& Pair:Rigs)
    {
        const auto S=Pair.Value;
        if (!Valid(*S) || S->Mesh->GetWorld()!=World) continue;
        if (Args.Num()==2) S->Native->SetRigSolverIterations(S->Rig,FCString::Atoi(*Args[0]),FCString::Atoi(*Args[1]));
        auto Row=MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("mesh"),S->Mesh->GetPathName());
        Row->SetNumberField(TEXT("body_count"),S->Bodies.Num());
        Row->SetNumberField(TEXT("joint_count"),S->Capture.Joints.Num());
        TArray<FTransform> Transforms;
        TArray<TSharedPtr<FJsonValue>> Bones;
        for (int32 I=0;I<S->Bodies.Num();++I)
        {
            FProphecyJoltBodyState State; S->Native->ReadBody(S->Bodies[I],State);
            Transforms.Emplace(State.Rotation,State.PositionCm);
            const auto& Source=S->Capture.Bodies[I];
            auto B=MakeShared<FJsonObject>(); B->SetStringField(TEXT("name"),Source.BodyName.ToString());
            B->SetBoolField(TEXT("dynamic"),State.bDynamic); B->SetNumberField(TEXT("mass"),Source.MassKg);
            B->SetNumberField(TEXT("pose_error_cm"),FVector::Distance(State.PositionCm,S->Mesh->GetSocketLocation(Source.BodyName)));
            B->SetNumberField(TEXT("from_start_cm"),FVector::Distance(State.PositionCm,Source.BodyOriginToWorld.GetLocation()));
            B->SetNumberField(TEXT("speed"),State.CenterOfMassVelocityCmPerSecond.Size());
            Bones.Add(MakeShared<FJsonValueObject>(B));
        }
        Row->SetArrayField(TEXT("bones"),Bones);
        double MaxGap=0,InitialGap=0;
        for (const auto& J:S->Capture.Joints)
        {
            MaxGap=FMath::Max(MaxGap,FVector::Distance((J.Frame1*Transforms[J.Body1Index]).GetLocation(),(J.Frame2*Transforms[J.Body2Index]).GetLocation()));
            InitialGap=FMath::Max(InitialGap,FVector::Distance((J.Frame1*S->Capture.Bodies[J.Body1Index].BodyOriginToWorld).GetLocation(),(J.Frame2*S->Capture.Bodies[J.Body2Index].BodyOriginToWorld).GetLocation()));
        }
        Row->SetNumberField(TEXT("max_phat_anchor_gap_cm"),MaxGap); Row->SetNumberField(TEXT("initial_phat_anchor_gap_cm"),InitialGap);
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    auto Root=MakeShared<FJsonObject>(); Root->SetArrayField(TEXT("rigs"),Rows);
    FString Json; FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ConstrainedSkeleton.json")));
}
FAutoConsoleCommandWithWorldAndArgs AuditCommand(TEXT("Prophecy.Jolt.SkeletonAudit"),
    TEXT("Read admitted skeletal endpoints; optional velocity/position iteration overrides for this Play session."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&Audit));
#endif
}
