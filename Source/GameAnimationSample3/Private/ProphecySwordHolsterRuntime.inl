// Included by the sword controller; new state leaves retained controller layouts unchanged.
namespace ProphecySwordHolster
{
struct FProfile {
 float Shrink=10,Unshrink=.25f,Stabilization=0,ReturnDuration=.25f;
 float ShrinkDuration=.25f,AttachedSpeed=100,AttachedRotation=180,TipTolerance=2;
 bool LeewayPhase=true,HigherSolverAccuracy=false;
};
struct FReference { TWeakObjectPtr<USceneComponent> Holster;FTransform Seated;float Length=0;FVector BaseLocal=FVector::ZeroVector; };
enum class EPhase : uint8 { Prepare,Reach,Slide,Holstered,Grow,AlignTip };
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
struct FRequest { bool Sheathe;float Reach,Rotation,Sliding;ProphecySwordHolsterPose::FEntryPose Before;uint64 SampleTick=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRequest> Pending;
static TMap<TWeakObjectPtr<const UProphecySwordComponent>,FVector> AssetScales;
// A new sidecar; existing retained holster state layouts are unchanged.
struct FKinematicMount { TWeakObjectPtr<UPrimitiveComponent> Holster;TWeakObjectPtr<USceneComponent> Parent;FName Socket;FTransform PelvisLocal;bool Simulated=false; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FKinematicMount> KinematicMounts;
// Entry/exit only. Separate new storage keeps the already-live FState layout intact.
struct FNeckLimit
{
    FName Joint,Bone1,Bone2;
    EAngularConstraintMotion Swing1,Swing2,Twist;
    float Angle1,Angle2,AngleTwist;
};
using FNeckLimits=TArray<FNeckLimit,TInlineAllocator<3>>;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FNeckLimits> NeckLimits;
static bool ApplyNeckLimits(AProphecyAgent* A,bool Free,FString& Error)
{
    auto* Saved=NeckLimits.Find(A);
    if(Free?Saved!=nullptr:Saved==nullptr)return true;
    auto* Mesh=A?A->GetPoseReferenceMesh():nullptr;
    if(!Mesh){if(!Free)NeckLimits.Remove(A);return !Free;}
    TArray<FConstraintProfileProperties> JointProfiles;FNeckLimits Captured;
    JointProfiles.Reserve(Mesh->Constraints.Num());
    for(const auto* Joint:Mesh->Constraints)
    {
        if(!Joint){Error=TEXT("Missing physical joint while changing D/S neck limits");return false;}
        auto& P=JointProfiles.Add_GetRef(Joint->ProfileInstance);
        if(Free)
        {
            const auto IsNeck=[](FName Bone){return Bone==TEXT("neck_01")||Bone==TEXT("neck_02")||Bone==TEXT("head");};
            if(!IsNeck(Joint->ConstraintBone1)&&!IsNeck(Joint->ConstraintBone2))continue;
            Captured.Add({Joint->JointName,Joint->ConstraintBone1,Joint->ConstraintBone2,
                P.ConeLimit.Swing1Motion.GetValue(),P.ConeLimit.Swing2Motion.GetValue(),P.TwistLimit.TwistMotion.GetValue(),
                P.ConeLimit.Swing1LimitDegrees,P.ConeLimit.Swing2LimitDegrees,P.TwistLimit.TwistLimitDegrees});
            P.ConeLimit.Swing1Motion=ACM_Free;P.ConeLimit.Swing2Motion=ACM_Free;P.TwistLimit.TwistMotion=ACM_Free;
        }
        else for(const auto& Before:*Saved)
            if(Joint->JointName==Before.Joint&&Joint->ConstraintBone1==Before.Bone1&&Joint->ConstraintBone2==Before.Bone2)
            {
                P.ConeLimit.Swing1Motion=Before.Swing1;P.ConeLimit.Swing2Motion=Before.Swing2;P.TwistLimit.TwistMotion=Before.Twist;
                P.ConeLimit.Swing1LimitDegrees=Before.Angle1;P.ConeLimit.Swing2LimitDegrees=Before.Angle2;P.TwistLimit.TwistLimitDegrees=Before.AngleTwist;
                break;
            }
    }
    if(Free&&Captured.IsEmpty())return true;
    auto* Character=A->GetJoltCharacterComponent();
    if(A->IsJoltPhysicalAnimationEnabled()&&Character&&!Character->IsSteppingStopped())
    {
        if(!Character->ApplyAngularLimitProfiles(JointProfiles,Error))return false;
    }
    else for(int I=0;I<JointProfiles.Num();++I)
        if(!ProphecyAngularLimits::Equal(Mesh->Constraints[I]->ProfileInstance,JointProfiles[I]))ProphecyAngularLimits::Apply(*Mesh->Constraints[I],JointProfiles[I]);
    if(Free)NeckLimits.Add(A,MoveTemp(Captured));else NeckLimits.Remove(A);
    return true;
}
static void RestoreNeckLimits(AProphecyAgent* A)
{
    FString Error;if(!ApplyNeckLimits(A,false,Error))UE_LOG(LogTemp,Warning,TEXT("Sword holster neck limits restore: %s"),*Error);
}
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
        Clean(States);Clean(Pending);Clean(References);Clean(Profiles);Clean(AssetScales);Clean(KinematicMounts);Clean(NeckLimits);
        if(States.IsEmpty() && References.IsEmpty() && Profiles.IsEmpty() && AssetScales.IsEmpty())
        {FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
    });
}
bool InHolster(const AProphecyAgent* A){const auto* S=States.Find(A);return S && S->Attached;}
void BeforeModeChange(AProphecyAgent* A,bool Kinematic)
{
    // Restore before either backend captures a temporary stabilized mount.
    ProphecySwordHolsterPose::RestoreHolsterMount(A);
    // Restore before backend teardown captures its source constraint profiles.
    RestoreNeckLimits(A);
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
static const FState* StateForSource(const UPrimitiveComponent* Source)
{
    if(States.IsEmpty()||!Source||!Source->GetOwner())return nullptr;
    const auto* A=Cast<AProphecyAgent>(Source->GetOwner()->GetOwner());
    const auto* C=A?A->FindComponentByClass<UProphecySwordComponent>():nullptr;
    return C&&C->GetSword()==Source->GetOwner()?States.Find(A):nullptr;
}
bool IsPhysicsDriven(const UPrimitiveComponent* Source,const FProphecyJoltBodyHandle& Body)
{
    const auto* S=StateForSource(Source);
    if(!S||S->Kinematic||(S->Phase!=EPhase::Slide&&S->Phase!=EPhase::AlignTip))return false;
    const auto& Held=S->JointSettings.BodyB;
    return Held.WorldLifetime==Body.WorldLifetime&&Held.Slot==Body.Slot&&Held.Generation==Body.Generation;
}
bool FollowsAttachment(const UPrimitiveComponent* Source)
{
    const auto* S=StateForSource(Source);
    return S&&!S->Kinematic&&S->Phase!=EPhase::Slide&&S->Phase!=EPhase::AlignTip
        &&(S->Attached||(!S->Sheathe&&S->Phase==EPhase::Grow));
}
bool PhysicsTarget(const UPrimitiveComponent* Source,const FProphecyJoltBodyHandle& Body,FTransform& World)
{
    return IsPhysicsDriven(Source,Body)&&ProphecySwordHolsterPose::PhysicsSwordTarget(Cast<AProphecyAgent>(Source->GetOwner()->GetOwner()),World);
}
static void DestroyJoint(FState& S)
{
 if(S.World.IsValid()){
  if(S.Sheathe&&!S.Attached&&S.World->OwnsBody(S.JointSettings.BodyB))SwordDriveFollower(S.World.Get(),S.JointSettings.BodyB,S.JointSettings.BodyA,FTransform::Identity,false);
  if(S.World->OwnsJoint(S.Joint))S.World->DestroyJoint(S.Joint);
 }
 S.Joint={};
}
static bool SetHeadClavicleSuppressed(AProphecyAgent* A,bool Suppressed,FString& Error)
{
    auto* Owner=A?A->FindComponentByClass<UProphecySwordComponent>():nullptr;
    auto* World=A&&A->GetWorld()?A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;
    FProphecyJoltWorldDiagnostics D;
    if(!Owner||!World||!World->GetDiagnostics(D).IsSuccess()||!D.bInitialized)return !Suppressed;
    TArray<FProphecyJoltBodyPair,TInlineAllocator<2>> Pairs;
    if(Suppressed)
    {
        auto* Character=A->GetJoltCharacterComponent();FProphecyJoltBodyHandle Head,Clavicle;
        if(!Character||!Character->GetBodyHandle(TEXT("head"),Head)){Error=TEXT("Missing D/S physical head");return false;}
        for(FName Bone:{FName(TEXT("clavicle_l")),FName(TEXT("clavicle_r"))})
        {
            if(!Character->GetBodyHandle(Bone,Clavicle)){Error=TEXT("Missing D/S physical clavicle");return false;}
            Pairs.Add({Head,Clavicle});
        }
    }
    // Independent ownership preserves PHAT and user collision settings on release.
    // Only admission/cleanup touch these two pairs; no per-tick collision work.
    const auto Result=World->UpdateScopedContactRules(Owner,Pairs,{});
    if(!Result.IsSuccess())Error=Result.Message;
    return Result.IsSuccess();
}
static void RestoreActionPhysics(AProphecyAgent* A)
{
    ProphecySpecialSolver::HolsterChanged(A,false);
    RestoreNeckLimits(A);
    FString Error;
    if(!SetHeadClavicleSuppressed(A,false,Error))
        UE_LOG(LogTemp,Warning,TEXT("Sword holster head collision restore: %s"),*Error);
    if(!ProphecyLimbCollision::SetHolsterArmSuppressed(A,false,Error))
        UE_LOG(LogTemp,Warning,TEXT("Sword holster collision restore: %s"),*Error);
}
void Remove(const AProphecyAgent* A)
{RestoreActionPhysics(const_cast<AProphecyAgent*>(A));if(auto* S=States.Find(A))DestroyJoint(*S);States.Remove(A);Pending.Remove(A);References.Remove(A);Profiles.Remove(A);KinematicMounts.Remove(A);ProphecySwordHolsterPose::Remove(A,true);}
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
        double GripCm=-1,GripDeg=-1,RenderCm=-1,RenderDeg=-1;
        if(S&&S->World.IsValid()){
            FProphecyJoltJointSettings Joint;FProphecyJoltBodyState HB,SB;
            if(S->World->ReadJoint(S->Joint,Joint).IsSuccess()&&S->World->ReadBody(Joint.BodyA,HB).IsSuccess()&&S->World->ReadBody(Joint.BodyB,SB).IsSuccess()){
                const FTransform HA=Joint.FrameA*FTransform(HB.Rotation,HB.PositionCm),SA=Joint.FrameB*FTransform(SB.Rotation,SB.PositionCm);
                GripCm=FVector::Distance(HA.GetLocation(),SA.GetLocation());GripDeg=FMath::RadiansToDegrees(HA.GetRotation().AngularDistance(SA.GetRotation()));
            }
            if(const auto* C=A->FindComponentByClass<UProphecySwordComponent>())if(const auto* ItemActor=C->GetSword()){
                const auto* Adapter=ItemActor->FindComponentByClass<UProphecyJoltBodyComponent>();FTransform Origin;
                if(Adapter&&Adapter->GetBodyState(SB)&&Adapter->GetBodyOriginToComponent(Origin)&&ItemActor->GetRootComponent()){
                    const FTransform Native=Origin.Inverse()*FTransform(SB.Rotation,SB.PositionCm),Visible=ItemActor->GetRootComponent()->GetComponentTransform();
                    RenderCm=FVector::Distance(Native.GetLocation(),Visible.GetLocation());RenderDeg=FMath::RadiansToDegrees(Native.GetRotation().AngularDistance(Visible.GetRotation()));
                }
            }
        }
        Text+=FString::Printf(TEXT("%s reference=1 length=%.4f phase=%d attached=%d scale=%.6f insertion=%.6f progress=%.6f joint=%d distance=%.3f angle=%.3f target=%s goal=%s joint_slot=%d joint_generation=%llu world_joints=%u pose_tick=%d reach_ticks=%d slide_ticks=%d pose_error=%.6f finished=%d kinematic=%d queued=%d start_slot=%d returning=%d slide_progress=%.9f head_step=%.9f grip_cm=%.9f grip_deg=%.9f render_cm=%.9f render_deg=%.9f\n"),
            *A->GetName(),Item.Value.Length,S?int32(S->Phase):-1,S?S->Attached:0,S?S->Scale:1,S?S->Insertion:0,S?S->ReachProgress:0,
            S && S->World.IsValid() && S->World->OwnsJoint(S->Joint),FVector::Distance(Hand.GetLocation(),Goal.GetLocation()),
            FMath::RadiansToDegrees(Hand.GetRotation().AngularDistance(Goal.GetRotation())),S?*S->TargetHand.GetLocation().ToString():TEXT("none"),*Goal.GetLocation().ToString(),
            S?S->Joint.Slot:INDEX_NONE,S?S->Joint.Generation:0,Diagnostics.GenericJointCount,PS.Tick,PS.ReachTicks,PS.SlideTicks,PS.HandError,PS.Finished,S?S->Kinematic:0,Pending.Contains(A),ProphecySwordHolsterSchedule::Slot(A),PS.Returning,PS.SlideProgress,PS.HeadStep,GripCm,GripDeg,RenderCm,RenderDeg);
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
    // The class viewport owns the mount. Old placed-instance overrides and a
    // previous runtime world rotation must never become the new neutral pose.
    if(A->GetWorld()&&A->GetWorld()->IsGameWorld()&&!ProphecySwordHolster::States.Contains(A))
        if(auto* Class=Cast<UBlueprintGeneratedClass>(A->GetClass());Class&&Class->SimpleConstructionScript)
            for(auto* N:Class->SimpleConstructionScript->GetAllNodes())if(N->GetVariableName()==Holster->GetFName())
                if(auto* Template=Cast<USceneComponent>(N->GetActualComponentTemplate(Class))){
                    Holster->SetUsingAbsoluteRotation(Template->IsUsingAbsoluteRotation());
                    Holster->SetRelativeTransform(Template->GetRelativeTransform());break;
                }
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
bool UProphecySwordHolsterLibrary::SetSwordHolsterProfile(AProphecyAgent* A,float Shrink,float Duration,float Stabilization,float ReturnDuration,float ShrinkDuration,float AttachedSpeed,float AttachedRotation,bool LeewayPhase,float TipTolerance,bool HigherSolverAccuracy,FVector2D DrawNNBlendRange,FVector2D SheatheNNBlendRange)
{
    if(!IsInGameThread() || !IsValid(A) || !FMath::IsFinite(Shrink) || Shrink<0 || Shrink>=100 || !FMath::IsFinite(Duration) || Duration<0)return false;
    if(!FMath::IsFinite(Stabilization)||Stabilization<0||Stabilization>100||!FMath::IsFinite(ReturnDuration)||ReturnDuration<0)return false;
    for(float V:{ShrinkDuration,AttachedSpeed,AttachedRotation})if(!FMath::IsFinite(V)||V<=0)return false;
    if(!FMath::IsFinite(TipTolerance)||TipTolerance<0||TipTolerance>100)return false;
    for(const FVector2D Range:{DrawNNBlendRange,SheatheNNBlendRange})if(!FMath::IsFinite(Range.X)||!FMath::IsFinite(Range.Y)||Range.X<.5||Range.Y>1||Range.Y<Range.X)return false;
    ProphecySwordHolsterPose::ConfigureReturnBlend(A,DrawNNBlendRange,SheatheNNBlendRange);
    ProphecySwordHolster::Profiles.Add(A,{Shrink,Duration,Stabilization*.01f,ReturnDuration,ShrinkDuration,AttachedSpeed,AttachedRotation,TipTolerance,LeewayPhase,HigherSolverAccuracy});ProphecySwordHolster::EnsureCleanup();return true;
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
    ProphecySwordHolster::Pending.Remove(Agent());
    ProphecySwordHolster::RestoreActionPhysics(Agent());
    if(auto* S=ProphecySwordHolster::States.Find(Agent()))
    {
        ProphecySwordHolster::DestroyJoint(*S);
        FProphecyJoltBodyHandle Body;
        if(S->World.IsValid() && JoltBody && JoltBody->GetBodyHandle(Body))S->World->UpdateBodySuppressedPairs(Body,{});
    }
    ProphecySwordHolster::States.Remove(Agent());
    ProphecySwordHolsterPose::Remove(Agent());
}
bool UProphecySwordComponent::StartHolster(bool Sheathe,float Reach,float Rotation,float Sliding,const ProphecySwordHolsterPose::FEntryPose* Previous)
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();const auto* Reference=References.Find(A);auto* Existing=States.Find(A);
    if(!A || !Reference || !Reference->Holster.IsValid() || !IsValid(Sword) || !IsValid(Blade)
        || bDropPending || PendingJoltBindId.IsValid() || bBinding)return false;
    const bool LabProfile=ProphecySwordHolsterPose::ActionSpeeds(A,Sheathe,Reach,Rotation,Sliding);
    if(const auto* Request=Pending.Find(A))return Request->Sheathe==Sheathe;
    if(Existing && Existing->Phase!=EPhase::Holstered)return Existing->Sheathe==Sheathe; // Idempotent; never add another joint.
    if(Sheathe && Existing)return true;
    if(!Sheathe && !Existing)return false;
    // Waiting changes no pose, collision, grip, scale or ownership. Admission
    // below is repeated against the current NN/holster when the slot is due.
    ProphecySwordHolsterSchedule::Reserve(A);
    bool Accepted=false;ON_SCOPE_EXIT {if(!Accepted)ProphecySwordHolsterSchedule::Remove(A);};
    if(!ProphecySwordHolsterSchedule::Ready(A)){
        FRequest Request{Sheathe,Reach,Rotation,Sliding};
        if(!ProphecySwordHolsterPose::CaptureEntryPose(A,Request.Before))return false;
        Request.SampleTick=ProphecySwordHolsterSchedule::Tick(A);
        Pending.Add(A,MoveTemp(Request));EnsureCleanup();SetComponentTickEnabled(true);Accepted=true;return true;
    }
    FState S=Existing?*Existing:FState{};S.Reference=*Reference;
    if(LabProfile){
        // Palm-in roll about the blade axis at the mouth, exactly as the lab.
        auto& Seat=S.Reference.Seated;const FVector Mouth=Seat.TransformPosition(S.Reference.BaseLocal);
        const FQuat Q=(Seat.GetRotation()*FQuat(FVector::UpVector,PI)).GetNormalized();
        Seat.SetRotation(Q);Seat.SetLocation(Mouth-Q.RotateVector(Seat.GetScale3D()*S.Reference.BaseLocal));
    }
    if(const auto* P=Profiles.Find(A))
    {const float HeldShrink=S.Profile.Shrink;S.Profile=*P;if(!Sheathe&&Existing)S.Profile.Shrink=HeldShrink;}
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
    if(!S.Kinematic&&!ApplyNeckLimits(A,true,CollisionError))
    {RestoreActionPhysics(A);if(Sheathe&&!S.RestoreSimulation)SetSimulated(false);UE_LOG(LogTemp,Warning,TEXT("Sword holster neck limits admission: %s"),*CollisionError);return false;}
    if(!S.Kinematic&&!SetHeadClavicleSuppressed(A,true,CollisionError))
    {RestoreActionPhysics(A);if(Sheathe&&!S.RestoreSimulation)SetSimulated(false);UE_LOG(LogTemp,Warning,TEXT("Sword holster head collision admission: %s"),*CollisionError);return false;}
    const FTransform Full=S.Reference.Seated*S.Reference.Holster->GetComponentTransform();
    ProphecySwordHolsterPose::FGeometry Geometry;Geometry.Valid=true;Geometry.Holster=S.Reference.Holster;Geometry.Seated=S.Reference.Seated;
    Geometry.GripStabilization=S.Profile.Stabilization;Geometry.HolsterReturnDuration=S.Profile.ReturnDuration;
    Geometry.ShrinkDuration=S.Profile.ShrinkDuration;Geometry.AttachedSpeed=S.Profile.AttachedSpeed;Geometry.AttachedRotation=S.Profile.AttachedRotation;Geometry.LeewayPhase=S.Profile.LeewayPhase;Geometry.TipTolerance=S.Profile.TipTolerance;
    Geometry.Grip=A->SwordGripTransform;Geometry.AssetScale=AssetScales.FindRef(this);Geometry.BaseLocal=S.Reference.BaseLocal;
    Geometry.TipLocal=FVector(0,0,Blade->GetStaticMesh()->GetBoundingBox().Max.Z);Geometry.Retained=1-S.Profile.Shrink*.01;
    if(!ProphecySwordHolsterPose::Begin(A,Sheathe,Reach,Rotation,Sliding,S.Reference.Length*(1-S.Profile.Shrink*.01f),GoalHand(A,S,0),GoalHand(A,S,1),Full.TransformPosition(S.Reference.BaseLocal),Geometry,Previous))
    {RestoreActionPhysics(A);if(Sheathe&&!S.Kinematic&&!S.RestoreSimulation)SetSimulated(false);UE_LOG(LogTemp,Warning,TEXT("Sword holster: no compatible live NN pose for admission."));return false;}
    ProphecySpecialSolver::HolsterChanged(A,S.Profile.HigherSolverAccuracy);
    S.Phase=EPhase::Prepare;States.Add(A,MoveTemp(S));EnsureCleanup();SetComponentTickEnabled(true);Accepted=true;return true;
}
bool UProphecySwordComponent::TickHolster()
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();
    if(auto* Request=Pending.Find(A)){
        const uint64 Tick=ProphecySwordHolsterSchedule::Tick(A);
        if(ProphecySwordHolsterSchedule::Ready(A)&&Tick==Request->SampleTick+1){
            const FRequest R=MoveTemp(*Request);Pending.Remove(A);
            if(!StartHolster(R.Sheathe,R.Reach,R.Rotation,R.Sliding,&R.Before)){
                ProphecySwordHolsterSchedule::Remove(A);
                if(const auto* Held=States.Find(A))if(Held->Phase==EPhase::Holstered)SetComponentTickEnabled(false);
                UE_LOG(LogTemp,Warning,TEXT("Queued sword holster start no longer admissible: %s"),*GetNameSafe(A));
            }
        }else if(Tick!=Request->SampleTick){
            // Only waiting actions retain a pose. After skipped ticks, wait for
            // a consecutive pair instead of inventing the missing velocity.
            if(ProphecySwordHolsterPose::CaptureEntryPose(A,Request->Before))Request->SampleTick=Tick;
            else{Pending.Remove(A);ProphecySwordHolsterSchedule::Remove(A);}
        }
    }
    auto* S=States.Find(A);if(!S)return false;
    ON_SCOPE_EXIT {if(IsValid(JoltBody)&&FollowsAttachment(Blade))JoltBody->SynchronizeSourceTransform();};
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
    auto PresentSword=[&](const FTransform& Goal)
    {
        FTransform Presented=Goal;
        if(!S->Kinematic){
            FProphecyJoltBodyState Completed;FTransform Origin;
            if(!JoltBody->GetBodyState(Completed)||!JoltBody->GetBodyOriginToComponent(Origin))return false;
            Presented=Origin.Inverse()*FTransform(Completed.Rotation,Completed.PositionCm);
            Presented.SetScale3D(Blade->GetComponentScale());
        }
        Blade->SetWorldTransform(Presented,false,nullptr,ETeleportType::TeleportPhysics);return true;
    };
    auto Joint=[&](bool Capture=false)
    {
        if(S->Kinematic)return true;
        auto Drive=[&]()
        {
            if(!S->Sheathe||S->Attached)return true;
            FTransform BodyOrigin;if(!JoltBody->GetBodyOriginToComponent(BodyOrigin))return false;
            FTransform Component=GripLocal()*Mesh->GetSocketTransform(A->SwordHandSocket);Component.RemoveScaling();
            FTransform Offset=(BodyOrigin*Component).GetRelativeTransform(Mesh->GetSocketTransform(Mesh->GetSocketBoneName(A->SwordHandSocket)));
            Offset.RemoveScaling();Offset.NormalizeRotation();
            return SwordDriveFollower(this,SwordBody,Hand,Offset,true);
        };
        if(World->OwnsJoint(S->Joint)&&!Capture)
        {
            if(FMath::IsNearlyEqual(S->Scale,S->JointScale,1.e-7f))return true;
            S->JointSettings.FrameB.ScaleTranslation(FVector(1,1,S->Scale/S->JointScale));S->JointScale=S->Scale;
            return World->UpdateJoint(S->Joint,S->JointSettings).IsSuccess()&&Drive();
        }
        FProphecyJoltBodyState HB,SB;
        if(!World->ReadBody(Hand,HB).IsSuccess() || !World->ReadBody(SwordBody,SB).IsSuccess())return false;
        const FTransform HandWorld=Mesh->GetSocketTransform(A->SwordHandSocket);
        // S transfers authority at the current grip without moving either body.
        // D retains its authored grip, avoiding a baked-in acquisition error.
        // Update the existing joint at transfer; never add a second hand grip.
        S->JointSettings.Type=EProphecyJoltJointType::Fixed;S->JointSettings.BodyA=Hand;S->JointSettings.BodyB=SwordBody;
        S->JointSettings.FrameA=HandWorld.GetRelativeTransform(FTransform(HB.Rotation,HB.PositionCm));
        S->JointSettings.FrameB=HandWorld.GetRelativeTransform(FTransform(SB.Rotation,SB.PositionCm));
        if(!Capture){
            FTransform BodyOrigin;if(!JoltBody->GetBodyOriginToComponent(BodyOrigin))return false;
            FTransform Component=GripLocal()*HandWorld;Component.RemoveScaling();
            S->JointSettings.FrameB=HandWorld.GetRelativeTransform(BodyOrigin*Component);
        }
        S->JointSettings.FrameA.RemoveScaling();S->JointSettings.FrameB.RemoveScaling();
        S->JointScale=S->Scale;
        return (World->OwnsJoint(S->Joint)?World->UpdateJoint(S->Joint,S->JointSettings):World->CreateJoint(S->JointSettings,{},S->Joint)).IsSuccess()&&Drive();
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
    ProphecySwordHolsterPose::UpdateHolsterMount(A);
    const FTransform Full=S->Reference.Seated*S->Reference.Holster->GetComponentTransform();
    ProphecySwordHolsterPose::SetTargets(A,GoalHand(A,*S,0),GoalHand(A,*S,1),Full.TransformPosition(S->Reference.BaseLocal));
    if(S->Phase==EPhase::Reach)
    {
        FTransform Goal;double TargetScale;
        if(!ProphecySwordHolsterPose::SwordTarget(A,Goal,TargetScale))return Fail(TEXT("Missing sword target"));
        S->TargetHand=Goal;S->ReachProgress=PoseStatus.Progress;
        if(S->Sheathe)
        {
            if(!SetScale(TargetScale) || !Joint())return Fail(Error.IsEmpty()?TEXT("Could not resize the held grip."):Error);
        }
        FTransform Actual=Mesh->GetSocketTransform(A->SwordHandSocket);
        const bool Arrived=S->Sheathe?ProphecySwordHolsterPose::TrySheathe(A,Blade->GetComponentTransform()):
            PoseStatus.ReachDone && PoseStatus.HandError<=2 && FVector::Distance(Actual.GetLocation(),Goal.GetLocation())<=2
            && FMath::RadiansToDegrees(Actual.GetRotation().AngularDistance(Goal.GetRotation()))<=5;
        if(!Arrived)return true;
        if(S->Sheathe)
        {
            if(!S->Kinematic&&!SwordDriveFollower(this,SwordBody,Hand,FTransform::Identity,false))return Fail(TEXT("Could not release held sword drive."));
            if(!S->Kinematic && !JoltBody->SetSimulationEnabled(false,Error))return Fail(Error);
            if(!Blade->AttachToComponent(S->Reference.Holster.Get(),FAttachmentTransformRules::KeepWorldTransform))
                return Fail(TEXT("Could not attach the sword to its holster."));
            S->Attached=true;S->Insertion=0;
            if(!Joint(true))return Fail(TEXT("Could not capture the attached hand grip."));
        }
        else {if(!Joint())return Fail(TEXT("Could not grip the seated sword."));S->Insertion=1;}
        if(S->Sheathe){ProphecySwordHolsterPose::Status(A,PoseStatus);S->Phase=PoseStatus.Aligning?EPhase::AlignTip:EPhase::Slide;return true;}
        S->Phase=EPhase::Slide;ProphecySwordHolsterPose::SetSliding(A,true);
    }
    if(S->Phase==EPhase::AlignTip){
        double TargetScale;if(!ProphecySwordHolsterPose::SwordTarget(A,S->TargetHand,TargetScale))return Fail(TEXT("Missing tip alignment target"));
        if(!SetScale(TargetScale)||!Joint())return Fail(TEXT("Could not update alignment grip"));
        FTransform BladeTarget;if(!ProphecySwordHolsterPose::PhysicsSwordTarget(A,BladeTarget))return Fail(TEXT("Missing captured sword path"));
        if(!PresentSword(BladeTarget))return Fail(TEXT("Missing completed sword body"));
        if(PoseStatus.Aligning)return true;
        S->Phase=EPhase::Slide;
    }
    if(S->Phase==EPhase::Slide)
    {
        S->Insertion=PoseStatus.Insertion;
        double TargetScale;
        if(!ProphecySwordHolsterPose::SwordTarget(A,S->TargetHand,TargetScale))return Fail(TEXT("Missing sliding target"));
        if(!SetScale(TargetScale)||!Joint())return Fail(TEXT("Could not update sliding grip"));
        FTransform BladeTarget;if(!ProphecySwordHolsterPose::PhysicsSwordTarget(A,BladeTarget))return Fail(TEXT("Missing sliding sword path"));
        if(!PresentSword(BladeTarget))return Fail(TEXT("Missing completed sword body"));
        // Ownership changes on the authored endpoint. Waiting for the previous
        // physics publication holds the joint into the first FK-return tick.
        if(S->Sheathe && S->Insertion>=1)
        {DestroyJoint(*S);S->Phase=EPhase::Grow;S->GrowTicks=0;
            Blade->SetWorldTransform(BladeTarget,false,nullptr,ETeleportType::TeleportPhysics);return true;}
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
        if(S->Sheathe){if(PoseStatus.Finished){RestoreActionPhysics(A);S->Phase=EPhase::Holstered;ProphecySwordHolsterPose::Remove(A);SetComponentTickEnabled(false);}return true;}
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
 ProphecySwordHolsterPose::Configure(A,P->Profile);
 const auto& V=P->Profile;
 ProphecySwordHolster::Profiles.Add(A,{float(V.Shrink),float(V.Unshrink),float(V.Stabilization),float(V.HolsterReturnDuration),float(V.ShrinkDuration),float(V.AttachedSpeed),float(V.AttachedRotation),float(V.TipTolerance),V.LeewayPhase});ProphecySwordHolster::EnsureCleanup();return true;
}
