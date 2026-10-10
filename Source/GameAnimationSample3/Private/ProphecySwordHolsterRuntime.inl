// Included by the sword controller; new state leaves retained controller layouts unchanged.
namespace ProphecySwordHolster
{
struct FProfile { float Shrink=10,Unshrink=.25f; };
struct FReference { TWeakObjectPtr<USceneComponent> Holster;FTransform Seated;float Length=0;FVector BaseLocal=FVector::ZeroVector; };
enum class EPhase : uint8 { Prepare,Reach,Slide,Holstered,Grow };
struct FState
{
    FReference Reference;FProfile Profile;
    EPhase Phase=EPhase::Prepare;
    bool Sheathe=true,Attached=false,RestoreSimulation=true,Kinematic=false;
    float ReachSpeed=100,RotationSpeed=180,SlideSpeed=60,Scale=1,ReachProgress=0,Insertion=0,GrowTicks=0,JointScale=1;
    FTransform TargetHand;
    FProphecyJoltJointHandle Joint;
    FProphecyJoltJointSettings JointSettings;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> World;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FProfile> Profiles;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReference> References;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static TMap<TWeakObjectPtr<const UProphecySwordComponent>,FVector> AssetScales;
// A new sidecar; existing retained holster state layouts are unchanged.
struct FKinematicMount { TWeakObjectPtr<UPrimitiveComponent> Holster;TWeakObjectPtr<USceneComponent> Parent;FName Socket;FTransform PelvisLocal;bool Simulated=false; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FKinematicMount> KinematicMounts;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
        Clean(States);Clean(References);Clean(Profiles);Clean(AssetScales);Clean(KinematicMounts);
        if(States.IsEmpty() && References.IsEmpty() && Profiles.IsEmpty() && AssetScales.IsEmpty())
        {FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
    });
}
bool InHolster(const AProphecyAgent* A){const auto* S=States.Find(A);return S && S->Attached;}
void BeforeModeChange(AProphecyAgent* A,bool Kinematic)
{
    if(!Kinematic || KinematicMounts.Contains(A))return;
    const auto* R=References.Find(A);auto* H=R?Cast<UPrimitiveComponent>(R->Holster.Get()):nullptr;
    auto* M=A?A->GetPoseReferenceMesh():nullptr;if(!H||!M||!M->DoesSocketExist(TEXT("pelvis")))return;
    FKinematicMount Mount;Mount.Holster=H;Mount.Parent=H->GetAttachParent();Mount.Socket=H->GetAttachSocketName();
    Mount.PelvisLocal=H->GetComponentTransform().GetRelativeTransform(M->GetSocketTransform(TEXT("pelvis")));
    Mount.Simulated=UProphecyJoltStandardPhysicsLibrary::IsSimulatingPhysics(H,NAME_None);
    if(Mount.Simulated)UProphecyJoltStandardPhysicsLibrary::SetSimulatePhysics(H,false);
    H->AttachToComponent(M,FAttachmentTransformRules::KeepWorldTransform,TEXT("pelvis"));
    KinematicMounts.Add(A,Mount);
}
void AfterModeChange(AProphecyAgent* A)
{
    auto* Mount=KinematicMounts.Find(A);if(!Mount)return;auto* H=Mount->Holster.Get();
    if(!H){KinematicMounts.Remove(A);return;}
    if(A->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic){
        if(auto* M=A->GetPoseReferenceMesh()){H->AttachToComponent(M,FAttachmentTransformRules::KeepWorldTransform,TEXT("pelvis"));H->SetRelativeTransform(Mount->PelvisLocal);}
    }else{
        if(auto* P=Mount->Parent.Get())H->AttachToComponent(P,FAttachmentTransformRules::KeepWorldTransform,Mount->Socket);
        else H->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
        if(Mount->Simulated)UProphecyJoltStandardPhysicsLibrary::SetSimulatePhysics(H,true);
        KinematicMounts.Remove(A);
    }
}
bool HandTarget(const AProphecyAgent* A,FTransform& World)
{
    const auto* S=States.IsEmpty()?nullptr:States.Find(A);
    if(!S || (S->Phase!=EPhase::Reach && S->Phase!=EPhase::Slide))return false;
    World=S->TargetHand;return true;
}
static void DestroyJoint(FState& S)
{if(S.World.IsValid() && S.World->OwnsJoint(S.Joint))S.World->DestroyJoint(S.Joint);S.Joint={};}
static void RestoreArmCollision(AProphecyAgent* A)
{
    FString Error;
    if(!ProphecyLimbCollision::SetHolsterArmSuppressed(A,false,Error))
        UE_LOG(LogTemp,Warning,TEXT("Sword holster collision restore: %s"),*Error);
}
void Remove(const AProphecyAgent* A)
{RestoreArmCollision(const_cast<AProphecyAgent*>(A));if(auto* S=States.Find(A))DestroyJoint(*S);States.Remove(A);References.Remove(A);Profiles.Remove(A);KinematicMounts.Remove(A);ProphecySwordHolsterPose::Remove(A,true);}
static FTransform ScaledGrip(const AProphecyAgent* A,const FVector& BaseScale,float Scale)
{
    FTransform Grip=A->SwordGripTransform;
    const FVector AxisScale(1,1,Scale);
    // The grip translation is in hand space; shorten it in blade space so the
    // hand's contact point stays fixed while only the blade axis changes length.
    Grip.SetTranslation(Grip.GetRotation().RotateVector(Grip.GetRotation().UnrotateVector(Grip.GetTranslation())*AxisScale));
    Grip.SetScale3D(BaseScale*AxisScale);
    return Grip;
}
static FTransform HandForBlade(const AProphecyAgent* A,const FTransform& Blade,float Scale)
{
    const FQuat Q=(Blade.GetRotation()*A->SwordGripTransform.GetRotation().Inverse()).GetNormalized();
    return FTransform(Q,Blade.GetLocation()-Q.RotateVector(ScaledGrip(A,FVector::OneVector,Scale).GetLocation()));
}
static FTransform BladeForHand(const AProphecyAgent* A,const FTransform& Hand,const FVector& BaseScale,float Scale)
{
    return ScaledGrip(A,BaseScale,Scale)*Hand;
}
static FTransform SeatedHand(const AProphecyAgent* A,const FState& S)
{
 const FTransform Full=S.Reference.Seated*S.Reference.Holster->GetComponentTransform();const float Scale=1-S.Profile.Shrink*.01f;
 FTransform Short=Full;Short.SetTranslation(Full.TransformPosition(S.Reference.BaseLocal)-Full.GetRotation().RotateVector(Full.GetScale3D()*FVector(1,1,Scale)*S.Reference.BaseLocal));
 return HandForBlade(A,Short,Scale);
}
static FTransform GoalHand(const AProphecyAgent* A,const FState& S,float Insertion)
{
    FTransform Result=SeatedHand(A,S);
    const FTransform Full=S.Reference.Seated*S.Reference.Holster->GetComponentTransform();
    Result.AddToTranslation(-Full.GetRotation().GetAxisZ()*S.Reference.Length*(1-S.Profile.Shrink*.01f)*(1-Insertion));
    return Result;
}
static void Report()
{
    FString Text;
    for(const auto& Item:References)if(const auto* A=Item.Key.Get())if(A->GetWorld()->IsGameWorld())
    {
        const auto* S=States.Find(A);
        const FTransform Hand=A->GetPoseReferenceMesh()->GetSocketTransform(A->SwordHandSocket);
        const FTransform Goal=S?GoalHand(A,*S,S->Phase==EPhase::Reach?(S->Sheathe?0:1):S->Insertion):Hand;
        ProphecySwordHolsterPose::FStatus PS;ProphecySwordHolsterPose::Status(A,PS);
        FProphecyJoltWorldDiagnostics Diagnostics;
        if(auto* W=A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>())W->GetDiagnostics(Diagnostics);
        Text+=FString::Printf(TEXT("%s reference=1 length=%.4f phase=%d attached=%d scale=%.6f insertion=%.6f progress=%.6f joint=%d distance=%.3f angle=%.3f target=%s goal=%s joint_slot=%d joint_generation=%llu world_joints=%u pose_tick=%d reach_ticks=%d slide_ticks=%d pose_error=%.6f finished=%d kinematic=%d\n"),
            *A->GetName(),Item.Value.Length,S?int32(S->Phase):-1,S?S->Attached:0,S?S->Scale:1,S?S->Insertion:0,S?S->ReachProgress:0,
            S && S->World.IsValid() && S->World->OwnsJoint(S->Joint),FVector::Distance(Hand.GetLocation(),Goal.GetLocation()),
            FMath::RadiansToDegrees(Hand.GetRotation().AngularDistance(Goal.GetRotation())),S?*S->TargetHand.GetLocation().ToString():TEXT("none"),*Goal.GetLocation().ToString(),
            S?S->Joint.Slot:INDEX_NONE,S?S->Joint.Generation:0,Diagnostics.GenericJointCount,PS.Tick,PS.ReachTicks,PS.SlideTicks,PS.HandError,PS.Finished,S?S->Kinematic:0);
    }
    FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordDraw20261010/state.txt")));
}
static FAutoConsoleCommand ReportCommand(TEXT("Prophecy.Sword.HolsterReport"),TEXT("On-demand holster state, no sampling work when unused."),FConsoleCommandDelegate::CreateStatic(&Report));
}

bool UProphecySwordHolsterLibrary::CaptureSwordHolsterReference(AProphecyAgent* A)
{
    if(!IsInGameThread() || !IsValid(A))return false;
    UChildActorComponent* Ref=nullptr;TInlineComponentArray<UChildActorComponent*> Children(A);
    for(auto* C:Children)if(C->GetName().StartsWith(TEXT("SwordRef"))){Ref=C;break;}
    auto* Sword=Ref?Ref->GetChildActor():nullptr;auto* Holster=Ref?Ref->GetAttachParent():nullptr;
    if(!Sword || !Holster)return false;
    USceneComponent* Base=nullptr;UStaticMeshComponent* Blade=nullptr;TInlineComponentArray<USceneComponent*> Parts(Sword);
    for(auto* C:Parts)
    {
        if(C->GetFName()==TEXT("sword"))Blade=Cast<UStaticMeshComponent>(C);
        if(C->GetFName()==TEXT("base blade") || C->GetFName()==TEXT("blade base"))Base=C;
    }
    if(!Blade || !Blade->GetStaticMesh())return false;
    FVector BaseLocal=FVector::ZeroVector;
    if(Base)BaseLocal=Blade->GetComponentTransform().InverseTransformPosition(Base->GetComponentLocation());
    else
    {
        // Child BeginPlay can delete the marker before its owner's BeginPlay. The
        // construction template retains the user's marker under the sword mesh.
        bool Found=false;
        auto* Class=Cast<UBlueprintGeneratedClass>(Sword->GetClass());
        if(Class && Class->SimpleConstructionScript)for(auto* N:Class->SimpleConstructionScript->GetAllNodes())
            if(N->GetVariableName()==TEXT("base blade") || N->GetVariableName()==TEXT("blade base"))
                if(auto* Template=Cast<USceneComponent>(N->GetActualComponentTemplate(Class)))
                {BaseLocal=Template->GetRelativeLocation();Found=true;break;}
        if(!Found)return false;
    }
    const double Tip=Blade->GetStaticMesh()->GetBoundingBox().Max.Z;
    const float Length=float((Tip-BaseLocal.Z)*Blade->GetComponentScale().Z);
    if(!FMath::IsFinite(Length) || Length<=0)return false;
    ProphecySwordHolster::References.Add(A,{Holster,Blade->GetComponentTransform().GetRelativeTransform(Holster->GetComponentTransform()),Length,BaseLocal});
    ProphecySwordHolster::EnsureCleanup();return true;
}
bool UProphecySwordHolsterLibrary::SetSwordHolsterProfile(AProphecyAgent* A,float Shrink,float Duration)
{
    if(!IsInGameThread() || !IsValid(A) || !FMath::IsFinite(Shrink) || Shrink<0 || Shrink>=100 || !FMath::IsFinite(Duration) || Duration<0)return false;
    ProphecySwordHolster::Profiles.Add(A,{Shrink,Duration});ProphecySwordHolster::EnsureCleanup();return true;
}
bool UProphecySwordHolsterLibrary::DrawSword(AProphecyAgent* A,bool Sheathe,float Reach,float Rotation,float Sliding)
{
    if(!IsInGameThread() || !IsValid(A) || !A->GetWorld() || !A->GetWorld()->IsGameWorld())return false;
    for(float V:{Reach,Rotation,Sliding})if(!FMath::IsFinite(V) || V<=0)return false;
    auto* C=A->FindComponentByClass<UProphecySwordComponent>();return C && C->StartHolster(Sheathe,Reach,Rotation,Sliding);
}

FTransform UProphecySwordComponent::GripLocal() const
{
    const auto* Base=ProphecySwordHolster::AssetScales.Find(this);
    const auto* S=ProphecySwordHolster::States.Find(Agent());const float Scale=S?S->Scale:1;
    return ProphecySwordHolster::ScaledGrip(Agent(),Base?*Base:FVector::OneVector,Scale);
}
void UProphecySwordComponent::ClearHolster()
{
    ProphecySwordHolster::RestoreArmCollision(Agent());
    if(auto* S=ProphecySwordHolster::States.Find(Agent()))
    {
        ProphecySwordHolster::DestroyJoint(*S);
        FProphecyJoltBodyHandle Body;
        if(S->World.IsValid() && JoltBody && JoltBody->GetBodyHandle(Body))S->World->UpdateBodySuppressedPairs(Body,{});
    }
    ProphecySwordHolster::States.Remove(Agent());
    ProphecySwordHolsterPose::Remove(Agent());
}
bool UProphecySwordComponent::StartHolster(bool Sheathe,float Reach,float Rotation,float Sliding)
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();const auto* Reference=References.Find(A);auto* Existing=States.Find(A);
    if(!A || !Reference || !Reference->Holster.IsValid() || !IsValid(Sword) || !IsValid(Blade)
        || bDropPending || PendingJoltBindId.IsValid() || bBinding)return false;
    if(Existing && Existing->Phase!=EPhase::Holstered)return Existing->Sheathe==Sheathe; // Idempotent; never add another joint.
    if(Sheathe && Existing)return true;
    if(!Sheathe && !Existing)return false;
    FState S=Existing?*Existing:FState{};S.Reference=*Reference;
    if(const auto* P=Profiles.Find(A))
    {if(Sheathe)S.Profile=*P;else S.Profile.Unshrink=P->Unshrink;}
    S.Kinematic=!A->IsJoltPhysicalAnimationEnabled();S.Sheathe=Sheathe;S.ReachSpeed=Reach;S.RotationSpeed=Rotation;S.SlideSpeed=Sliding;
    S.ReachProgress=0;S.TargetHand=A->GetPoseReferenceMesh()->GetSocketTransform(A->SwordHandSocket);S.TargetHand.RemoveScaling();
    if(Sheathe)
    {
        S.RestoreSimulation=bPhysicsHold;
        if(!S.Kinematic && !bPhysicsHold && !SetSimulated(true))return false;
    }
    FString CollisionError;
    if(!S.Kinematic && !ProphecyLimbCollision::SetHolsterArmSuppressed(A,true,CollisionError))
    {if(Sheathe&&!S.RestoreSimulation)SetSimulated(false);UE_LOG(LogTemp,Warning,TEXT("Sword holster collision admission: %s"),*CollisionError);return false;}
    const FTransform Full=S.Reference.Seated*S.Reference.Holster->GetComponentTransform();
    if(!ProphecySwordHolsterPose::Begin(A,Sheathe,Reach,Rotation,Sliding,S.Reference.Length*(1-S.Profile.Shrink*.01f),GoalHand(A,S,0),GoalHand(A,S,1),Full.TransformPosition(S.Reference.BaseLocal)))
    {RestoreArmCollision(A);if(Sheathe&&!S.Kinematic&&!S.RestoreSimulation)SetSimulated(false);UE_LOG(LogTemp,Warning,TEXT("Sword holster: no compatible live NN pose for admission."));return false;}
    S.Phase=EPhase::Prepare;States.Add(A,MoveTemp(S));EnsureCleanup();SetComponentTickEnabled(true);return true;
}
bool UProphecySwordComponent::TickHolster()
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();auto* S=States.Find(A);if(!S)return false;
    if(!S->Reference.Holster.IsValid() || (!S->Kinematic && (!JoltBody || JoltBody->IsSteppingStopped())))
    {ClearHolster();return false;}
    if(S->Phase==EPhase::Holstered)return true;
    if(!S->Kinematic && (PendingJoltBindId.IsValid() || JoltBody->IsEnablePending()))return true;
    FString Error;
    auto Fail=[&](const FString& Why)
    {
        UE_LOG(LogTemp,Error,TEXT("Sword holster: %s"),*Why);
        if(JoltBody && !JoltBody->IsSteppingStopped())
        {
            FString RestoreError;
            if(JoltBody->ScaleBladeAxis(1/S->Scale,RestoreError))S->Scale=1;
            JoltBody->SetSimulationEnabled(true,RestoreError);
        }
        ClearHolster();bRefreshPending=true;return true;
    };
    auto* World=JoltBody?JoltBody->GetWorldOwner():nullptr;FProphecyJoltBodyHandle SwordBody,Hand;
    auto* Character=A->GetJoltCharacterComponent();auto* Mesh=A->GetPoseReferenceMesh();
    if(!S->Kinematic && (!World || !JoltBody->GetBodyHandle(SwordBody) || !Character || !Character->GetBodyHandle(TEXT("hand_r"),Hand)))return Fail(TEXT("Missing native sword or hand."));
    S->World=World;
    auto SetScale=[&](float Value)
    {
        if(FMath::IsNearlyEqual(Value,S->Scale,1.e-7f))return true;
        if(S->Kinematic)Blade->SetWorldScale3D(AssetScales.FindRef(this)*FVector(1,1,Value));
        else if(!JoltBody->ScaleBladeAxis(Value/S->Scale,Error))return false;
        S->Scale=Value;if(S->Kinematic&&!S->Attached)Blade->SetRelativeTransform(GripLocal());return true;
    };
    auto Joint=[&]()
    {
        if(S->Kinematic)return true;
        if(World->OwnsJoint(S->Joint))
        {
            if(FMath::IsNearlyEqual(S->Scale,S->JointScale,1.e-7f))return true;
            S->JointSettings.FrameB.ScaleTranslation(FVector(1,1,S->Scale/S->JointScale));S->JointScale=S->Scale;
            return World->UpdateJoint(S->Joint,S->JointSettings).IsSuccess();
        }
        FProphecyJoltBodyState HB,SB;
        if(!World->ReadBody(Hand,HB).IsSuccess() || !World->ReadBody(SwordBody,SB).IsSuccess())return false;
        const FTransform HandWorld=Mesh->GetSocketTransform(A->SwordHandSocket);
        // Capture the current grip without snapping either body. Subsequent shrinking
        // scales this anchor in the existing joint instead of adding another constraint.
        S->JointSettings.Type=EProphecyJoltJointType::Fixed;S->JointSettings.BodyA=Hand;S->JointSettings.BodyB=SwordBody;
        S->JointSettings.FrameA=HandWorld.GetRelativeTransform(FTransform(HB.Rotation,HB.PositionCm));
        S->JointSettings.FrameB=HandWorld.GetRelativeTransform(FTransform(SB.Rotation,SB.PositionCm));
        S->JointSettings.FrameA.RemoveScaling();S->JointSettings.FrameB.RemoveScaling();
        S->JointScale=S->Scale;
        return World->CreateJoint(S->JointSettings,{},S->Joint).IsSuccess();
    };
    if(S->Phase==EPhase::Prepare)
    {
      if(!S->Kinematic)
      {
        if(JoltBody->IsAttachedCollider())return Fail(TEXT("Sword still welded during holster admission."));
        if(!ReleaseJoltGrip())return Fail(TEXT("Could not release the normal sword grip."));
        TArray<FProphecyJoltBodyPair> Pairs;
        for(const USkeletalBodySetup* B:Mesh->GetPhysicsAsset()->SkeletalBodySetups)if(B)
        {FProphecyJoltBodyHandle H;if(Character->GetBodyHandle(B->BoneName,H))Pairs.Add({SwordBody,H});}
        if(auto* Scene=UProphecyJoltSceneCollisionComponent::FindForWorld(GetWorld()))
        {FProphecyJoltBodyHandle H;if(auto* P=Cast<UPrimitiveComponent>(S->Reference.Holster.Get()))if(Scene->GetBodyHandle(*P,INDEX_NONE,H))Pairs.Add({SwordBody,H});}
        if(!World->UpdateBodySuppressedPairs(SwordBody,Pairs).IsSuccess())return Fail(TEXT("Could not set holster contact exclusions."));
        if(S->Sheathe && !Joint())return Fail(TEXT("Could not create the temporary hand grip."));
      }
        S->Phase=EPhase::Reach;
    }
    ProphecySwordHolsterPose::FStatus PoseStatus;if(!ProphecySwordHolsterPose::Status(A,PoseStatus))return Fail(TEXT("Holster pose controller was lost."));
    const FTransform Full=S->Reference.Seated*S->Reference.Holster->GetComponentTransform();
    ProphecySwordHolsterPose::SetTargets(A,GoalHand(A,*S,0),GoalHand(A,*S,1),Full.TransformPosition(S->Reference.BaseLocal));
    if(S->Phase==EPhase::Reach)
    {
        const FTransform Goal=GoalHand(A,*S,S->Sheathe?0:1);
        S->TargetHand=Goal;S->ReachProgress=PoseStatus.Progress;
        if(S->Sheathe)
        {
            if(!SetScale(1-S->Profile.Shrink*.01f*S->ReachProgress) || !Joint())return Fail(Error.IsEmpty()?TEXT("Could not resize the held grip."):Error);
        }
        FTransform Actual=Mesh->GetSocketTransform(A->SwordHandSocket);
        const bool Arrived=PoseStatus.ReachDone && PoseStatus.HandError<=2 && FVector::Distance(Actual.GetLocation(),Goal.GetLocation())<=2
            && FMath::RadiansToDegrees(Actual.GetRotation().AngularDistance(Goal.GetRotation()))<=5;
        if(!Arrived)return true;
        if(S->Sheathe)
        {
            if(!S->Kinematic && !JoltBody->SetSimulationEnabled(false,Error))return Fail(Error);
            if(!Blade->AttachToComponent(S->Reference.Holster.Get(),FAttachmentTransformRules::KeepWorldTransform))
                return Fail(TEXT("Could not attach the sword to its holster."));
            S->Attached=true;S->Insertion=0;
        }
        else {if(!Joint())return Fail(TEXT("Could not grip the seated sword."));S->Insertion=1;}
        S->Phase=EPhase::Slide;ProphecySwordHolsterPose::SetSliding(A,true);
    }
    if(S->Phase==EPhase::Slide)
    {
        S->Insertion=S->Sheathe?PoseStatus.SlideProgress:1-PoseStatus.SlideProgress;
        S->TargetHand=GoalHand(A,*S,S->Insertion);
        const FVector Base=AssetScales.FindRef(this);
        Blade->SetWorldTransform(BladeForHand(A,S->TargetHand,Base,S->Scale),false,nullptr,ETeleportType::TeleportPhysics);
        // Ownership changes on the authored endpoint. Waiting for the previous
        // physics publication holds the joint into the first FK-return tick.
        if(S->Sheathe && S->Insertion>=1)
        {DestroyJoint(*S);S->Phase=EPhase::Grow;S->GrowTicks=0;return true;}
        if(!S->Sheathe && S->Insertion<=0)
        {
            DestroyJoint(*S);S->Attached=false;S->Phase=EPhase::Grow;S->GrowTicks=0;
            if(S->Profile.Unshrink<=0 && !SetScale(1))return Fail(Error);
            Blade->AttachToComponent(Mesh,FAttachmentTransformRules::KeepWorldTransform,A->SwordHandSocket);
            Blade->SetRelativeTransform(GripLocal());
        }
        return true;
    }
    if(S->Phase==EPhase::Grow)
    {
        if(S->Sheathe){if(PoseStatus.Finished){RestoreArmCollision(A);S->Phase=EPhase::Holstered;ProphecySwordHolsterPose::Remove(A);SetComponentTickEnabled(false);}return true;}
        const float T=ProphecySwordHolsterPose::UnshrinkAlpha(S->GrowTicks,S->Profile.Unshrink);
        if(!SetScale(FMath::Lerp(1-S->Profile.Shrink*.01f,1.f,T)))return Fail(Error);
        Blade->SetRelativeTransform(GripLocal());
        if(T>=1 && PoseStatus.Finished)
        {
            const bool Restore=S->RestoreSimulation;
            if(!S->Kinematic && !JoltBody->SetSimulationEnabled(true,Error))return Fail(Error);
            ClearHolster();bPhysicsHold=Restore;
            if(!Bind(false))bRefreshPending=true;
        }
        return true;
    }
    return true;
}

bool UProphecySwordHolsterLibrary::SetSwordHolsterLabProfile(AProphecyAgent* A,const FString& File)
{
 if(!IsInGameThread()||!IsValid(A))return false;
 // Profiles are shared across crowds; file parsing happens only on explicit configuration.
 struct FCachedProfile { FDateTime Stamp;ProphecySwordHolsterPose::FProfile Profile; };
 static TMap<FString,FCachedProfile> FileCache;
 const FString Path=FPaths::IsRelative(File)?FPaths::ProjectDir()/File:File;
 const FDateTime Stamp=IFileManager::Get().GetTimeStamp(*Path);const auto* P=FileCache.Find(Path);
 if(!P||P->Stamp!=Stamp){ProphecySwordHolsterPose::FProfile Loaded;FString Error;
  if(!ProphecySwordHolsterPose::LoadProfile(Path,Loaded,Error)){UE_LOG(LogTemp,Warning,TEXT("%s"),*Error);return false;}
  P=&FileCache.Add(Path,{Stamp,Loaded});}
 ProphecySwordHolsterPose::Configure(A,P->Profile);return true;
}
