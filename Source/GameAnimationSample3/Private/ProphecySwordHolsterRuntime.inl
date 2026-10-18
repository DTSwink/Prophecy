// Included by the sword controller; new state leaves retained controller layouts unchanged.
namespace ProphecySwordHolster
{
struct FProfile {
 float Shrink=10,Unshrink=.25f,Stabilization=0,ReturnDuration=.25f;
 float ShrinkDuration=.25f,AttachedSpeed=100,AttachedRotation=180,TipTolerance=2;
 bool LeewayPhase=true,HigherSolverAccuracy=false;
 float SheatheKinematicFraction=.8f;
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
struct FKinematicArm
{
 TWeakObjectPtr<UProphecyJoltWorldSubsystem> World;
 TWeakObjectPtr<UPrimitiveComponent> Blade;
 TWeakObjectPtr<UProphecyJoltBodyComponent> SwordBody;
 FProphecyJoltBodyHandle Bones[3],Pelvis,Clavicle,Sword;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FKinematicArm> KinematicArms;
static bool EndAttachedArm(const AProphecyAgent* A,FString& Error);
struct FRequest { bool Sheathe;float Reach,Rotation,Sliding;ProphecySwordHolsterPose::FEntryPose Before;uint64 SampleTick=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRequest> Pending;
static TMap<TWeakObjectPtr<const UProphecySwordComponent>,FVector> AssetScales;
// Entry/exit only. Neck/head and right wrist share the complete D/S lifetime.
// Preserve this retained storage layout; a fourth joint spills beyond the inline capacity.
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
        if(!Joint){Error=TEXT("Missing physical joint while changing D/S angular limits");return false;}
        auto& P=JointProfiles.Add_GetRef(Joint->ProfileInstance);
        if(Free)
        {
            const auto IsNeck=[](FName Bone){return Bone==TEXT("neck_01")||Bone==TEXT("neck_02")||Bone==TEXT("head");};
            const bool IsRightWrist=
                (Joint->ConstraintBone1==TEXT("hand_r")&&Joint->ConstraintBone2==TEXT("lowerarm_r"))||
                (Joint->ConstraintBone2==TEXT("hand_r")&&Joint->ConstraintBone1==TEXT("lowerarm_r"));
            if(!IsRightWrist&&!IsNeck(Joint->ConstraintBone1)&&!IsNeck(Joint->ConstraintBone2))continue;
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
    FString Error;if(!ApplyNeckLimits(A,false,Error))UE_LOG(LogTemp,Warning,TEXT("Sword holster angular limits restore: %s"),*Error);
}
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
        Clean(States);Clean(Pending);Clean(References);Clean(Profiles);Clean(AssetScales);Clean(NeckLimits);Clean(KinematicArms);
        if(States.IsEmpty() && References.IsEmpty() && Profiles.IsEmpty() && AssetScales.IsEmpty())
        {FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
    });
}
bool InHolster(const AProphecyAgent* A){const auto* S=States.Find(A);return S && S->Attached;}
bool BeforeModeChange(AProphecyAgent* A,bool Kinematic)
{
    // Release old physics handles without removing the live pose or its clocks.
    if(auto* C=A->FindComponentByClass<UProphecySwordComponent>();C&&!C->PrepareForModeChange())return false;
    FString Error;if(!EndAttachedArm(A,Error))UE_LOG(LogTemp,Warning,TEXT("Sword arm mode restore: %s"),*Error);
    // Restore before backend teardown captures its source constraint profiles.
    RestoreNeckLimits(A);
    const auto* P=Profiles.Find(A);
    ProphecyHolsterMount::BeforeAgentModeChange(A,Kinematic,P?P->ReturnDuration:.25f);
    return true;
}
void AfterModeChange(AProphecyAgent* A)
{
    ProphecyHolsterMount::AfterAgentModeChange(A);
}
static const FState* StateForSource(const UPrimitiveComponent* Source)
{
    if(States.IsEmpty()||!Source||!Source->GetOwner())return nullptr;
    const auto* A=Cast<AProphecyAgent>(Source->GetOwner()->GetOwner());
    const auto* C=A?A->FindComponentByClass<UProphecySwordComponent>():nullptr;
    return C&&C->GetSword()==Source->GetOwner()?States.Find(A):nullptr;
}
bool HasKinematicArm(const AProphecyAgent* A){return !KinematicArms.IsEmpty()&&KinematicArms.Contains(A);}
bool FollowsAttachment(const UPrimitiveComponent* Source)
{
    const auto* S=StateForSource(Source);
    return S&&!S->Kinematic&&(S->Attached||(!S->Sheathe&&S->Phase==EPhase::Grow));
}
static void DestroyJoint(FState& S)
{
 if(S.World.IsValid()){
  if(S.Sheathe&&!S.Attached&&S.World->OwnsBody(S.JointSettings.BodyB))SwordDriveFollower(S.World.Get(),S.JointSettings.BodyB,S.JointSettings.BodyA,FTransform::Identity,false);
  if(S.World->OwnsJoint(S.Joint))S.World->DestroyJoint(S.Joint);
 }
 S.Joint={};
}
static bool BeginAttachedArm(AProphecyAgent* A,FState& S,UPrimitiveComponent* Blade,UProphecyJoltBodyComponent* Sword,FString& Error)
{
 if(S.Kinematic||KinematicArms.Contains(A))return true;
 auto* C=A->GetJoltCharacterComponent();FKinematicArm Arm;Arm.World=S.World;Arm.Blade=Blade;Arm.SwordBody=Sword;
 const FName Names[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
 if(!C||!S.World.IsValid()||!Sword->GetBodyHandle(Arm.Sword))return false;
 for(int K=0;K<3;++K)if(!C->GetBodyHandle(Names[K],Arm.Bones[K]))return false;
 if(!C->GetBodyHandle(TEXT("pelvis"),Arm.Pelvis)||!C->GetBodyHandle(TEXT("clavicle_r"),Arm.Clavicle))return false;
 DestroyJoint(S);
 const auto Result=S.World->SetRigKinematicLimb(Arm.Bones,true);
 if(!Result.IsSuccess()){Error=Result.Message;return false;}
 KinematicArms.Add(A,MoveTemp(Arm));return true;
}
static bool EndAttachedArm(const AProphecyAgent* A,FString& Error)
{
 const auto* Arm=KinematicArms.Find(A);if(!Arm)return true;
 if(!A||!A->GetWorld()||A->GetWorld()->bIsTearingDown){KinematicArms.Remove(A);return true;}
 if(Arm->World.IsValid()&&Arm->World->OwnsBody(Arm->Bones[0])){
  const auto Result=Arm->World->SetRigKinematicLimb(Arm->Bones,false);
  if(!Result.IsSuccess()){Error=Result.Message;return false;}
 }
 KinematicArms.Remove(A);return true;
}
bool CompleteAttachedArms(UWorld* World,float DeltaSeconds,FString& Error)
{
 if(KinematicArms.IsEmpty())return true;
 CSV_SCOPED_TIMING_STAT(ProphecySword, AttachedArm);
 // Component transform callbacks may cancel an action. Do not keep map
 // iterators or references alive across those calls.
 TArray<TWeakObjectPtr<const AProphecyAgent>,TInlineAllocator<128>> Agents;
 for(const auto& Item:KinematicArms)if(Item.Key.IsValid()&&Item.Key->GetWorld()==World)Agents.Add(Item.Key);
 CSV_CUSTOM_STAT(ProphecySword, AttachedAgents, Agents.Num(), ECsvCustomStatOp::Set);
 for(const auto& Key:Agents){const auto* A=Key.Get();const auto* Found=KinematicArms.Find(Key);if(!A||!Found)continue;const auto Arm=*Found;
  const auto* S=States.Find(A);auto* W=Arm.World.Get();auto* Blade=Arm.Blade.Get();
  if(!S||!W){Error=TEXT("Lost attached arm ownership");return false;}
  // Equipment can be destroyed before the sword controller's cleanup tick.
  // Release the limb now; ordinary equipment cleanup must not fault the world.
  if(!Blade||!Arm.SwordBody.IsValid()||!S->Reference.Holster.IsValid()||!W->OwnsBody(Arm.Sword)){
   if(!EndAttachedArm(A,Error))return false;
   continue;
  }
  FProphecyJoltBodyState Pelvis,Clavicle;
  if(!W->ReadBody(Arm.Pelvis,Pelvis).IsSuccess()||!W->ReadBody(Arm.Clavicle,Clavicle).IsSuccess())return false;
  FTransform Pose[3],Holster,Sword;
  if(!ProphecySwordHolsterPose::CompleteAttachedArm(A,FTransform(Pelvis.Rotation,Pelvis.PositionCm),FTransform(Clavicle.Rotation,Clavicle.PositionCm),Pose,Holster,Sword))return false;
  const auto Posed=W->PoseRigKinematicLimb(Arm.Bones,Pose,DeltaSeconds);
  if(!Posed.IsSuccess()){Error=Posed.Message;return false;}
  {
   // The holster move carries the sword before its own local move. Publish
   // the sword once with both changes, preserving overlap handling.
   FScopedMovementUpdate SwordMove(Blade,EScopedUpdate::DeferredUpdates);
   auto* H=S->Reference.Holster.Get();if(H->IsUsingAbsoluteRotation())H->SetWorldRotation(Holster.GetRotation());
   if(!HasKinematicArm(A)||!Arm.Blade.IsValid())continue;
   Blade->SetRelativeTransform(Sword.GetRelativeTransform(Holster));
  }
  if(!HasKinematicArm(A)||!Arm.World.IsValid())continue;
  FTransform Origin;if(!Arm.SwordBody.IsValid()||!Arm.SwordBody->GetBodyOriginToComponent(Origin))return false;
  Sword.RemoveScaling();const auto Placed=W->SetBodyPose(Arm.Sword,Origin*Sword);
  if(!Placed.IsSuccess()){Error=Placed.Message;return false;}
 }
 return true;
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
{FString Error;EndAttachedArm(A,Error);RestoreActionPhysics(const_cast<AProphecyAgent*>(A));if(auto* S=States.Find(A))DestroyJoint(*S);States.Remove(A);Pending.Remove(A);References.Remove(A);Profiles.Remove(A);ProphecyHolsterMount::Remove(A);ProphecySwordHolsterPose::Remove(A,true);}
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
        double GripCm=-1,GripDeg=-1,RenderCm=-1,RenderDeg=-1,QueryCm=-1,QueryDeg=-1;
        if(HasKinematicArm(A)){FTransform Target;double Scale;
            if(ProphecySwordHolsterPose::SwordTarget(A,Target,Scale)){
                GripCm=FVector::Distance(Hand.GetLocation(),Target.GetLocation());GripDeg=FMath::RadiansToDegrees(Hand.GetRotation().AngularDistance(Target.GetRotation()));
            }
        }
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
                    if(auto* Primitive=Cast<UPrimitiveComponent>(ItemActor->GetRootComponent()))if(auto* Body=Primitive->GetBodyInstance()){
                        const FTransform Query=Body->GetUnrealWorldTransform();QueryCm=FVector::Distance(Query.GetLocation(),SB.PositionCm);
                        QueryDeg=FMath::RadiansToDegrees(Query.GetRotation().AngularDistance(SB.Rotation));
                    }
                }
            }
        }
        Text+=FString::Printf(TEXT("%s reference=1 length=%.4f phase=%d attached=%d scale=%.6f insertion=%.6f progress=%.6f joint=%d distance=%.3f angle=%.3f target=%s goal=%s joint_slot=%d joint_generation=%llu world_joints=%u pose_tick=%d reach_ticks=%d slide_ticks=%d pose_error=%.6f finished=%d kinematic=%d queued=%d start_slot=%d returning=%d slide_progress=%.9f head_step=%.9f grip_cm=%.9f grip_deg=%.9f render_cm=%.9f render_deg=%.9f kinematic_arm=%d query_cm=%.9f query_deg=%.9f\n"),
            *A->GetName(),Item.Value.Length,S?int32(S->Phase):-1,S?S->Attached:0,S?S->Scale:1,S?S->Insertion:0,S?S->ReachProgress:0,
            S && S->World.IsValid() && S->World->OwnsJoint(S->Joint),FVector::Distance(Hand.GetLocation(),Goal.GetLocation()),
            FMath::RadiansToDegrees(Hand.GetRotation().AngularDistance(Goal.GetRotation())),S?*S->TargetHand.GetLocation().ToString():TEXT("none"),*Goal.GetLocation().ToString(),
            S?S->Joint.Slot:INDEX_NONE,S?S->Joint.Generation:0,Diagnostics.GenericJointCount,PS.Tick,PS.ReachTicks,PS.SlideTicks,PS.HandError,PS.Finished,S?S->Kinematic:0,Pending.Contains(A),ProphecySwordHolsterSchedule::Slot(A),PS.Returning,PS.SlideProgress,PS.HeadStep,GripCm,GripDeg,RenderCm,RenderDeg,HasKinematicArm(A),QueryCm,QueryDeg);
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
    // Capture the authored relationship before restoring the class mount.
    // SwordRef's simulated mesh does not follow a parent transform change;
    // measuring afterward mixes the old blade pose with the new holster pose.
    const FTransform Seated=Blade->GetComponentTransform().GetRelativeTransform(Holster->GetComponentTransform());
    // The class viewport owns the mount, rather than old placed-instance overrides.
    if(A->GetWorld()&&A->GetWorld()->IsGameWorld()&&!ProphecySwordHolster::States.Contains(A))
        if(auto* Class=Cast<UBlueprintGeneratedClass>(A->GetClass());Class&&Class->SimpleConstructionScript)
            for(auto* N:Class->SimpleConstructionScript->GetAllNodes())if(N->GetVariableName()==Holster->GetFName())
                if(auto* Template=Cast<USceneComponent>(N->GetActualComponentTemplate(Class))){
                    const FTransform Rest=Template->GetRelativeTransform();
                    Holster->SetUsingAbsoluteRotation(Template->IsUsingAbsoluteRotation());
                    if(auto* Mesh=A->GetPoseReferenceMesh();Mesh&&Mesh->DoesSocketExist(TEXT("pelvis"))){
                        if(Holster->GetAttachParent()==Mesh&&Holster->GetAttachSocketName()==TEXT("pelvis"))Holster->SetRelativeTransform(Rest);
                        else Holster->SetWorldTransform(Rest*Mesh->GetSocketTransform(TEXT("pelvis")),false,nullptr,ETeleportType::TeleportPhysics);
                        if(auto* Primitive=Cast<UPrimitiveComponent>(Holster)){
                            TInlineComponentArray<UPhysicsConstraintComponent*> Joints(A);
                            for(auto* Joint:Joints){UPrimitiveComponent* C1=nullptr;UPrimitiveComponent* C2=nullptr;FName B1,B2;
                                Joint->GetConstrainedComponents(C1,B1,C2,B2);
                                if((C1==Primitive&&C2==Mesh&&B2==TEXT("pelvis"))||(C2==Primitive&&C1==Mesh&&B1==TEXT("pelvis")))Joint->UpdateConstraintFrames();
                            }
                            const auto* T=Cast<UPrimitiveComponent>(Template);
                            ProphecyHolsterMount::Capture(A,Primitive,Rest,T&&T->BodyInstance.bSimulatePhysics);
                        }
                    }break;
                }
    ProphecySwordHolster::References.Add(A,{Holster,Seated,Length,BaseLocal});
    ProphecySwordHolster::EnsureCleanup();return true;
}
bool UProphecySwordHolsterLibrary::SetSwordHolsterProfile(AProphecyAgent* A,float Shrink,float Duration,float Stabilization,float ReturnDuration,float ShrinkDuration,float AttachedSpeed,float AttachedRotation,bool LeewayPhase,float TipTolerance,bool HigherSolverAccuracy,FVector2D DrawNNBlendRange,FVector2D SheatheNNBlendRange,float SheatheKinematicFraction,float DrawSlidingSpeed,float SheatheSlidingSpeed)
{
    if(!IsInGameThread() || !IsValid(A) || !FMath::IsFinite(Shrink) || Shrink<0 || Shrink>=100 || !FMath::IsFinite(Duration) || Duration<0)return false;
    if(!FMath::IsFinite(Stabilization)||Stabilization<0||Stabilization>100||!FMath::IsFinite(ReturnDuration)||ReturnDuration<0)return false;
    for(float V:{ShrinkDuration,AttachedSpeed,AttachedRotation})if(!FMath::IsFinite(V)||V<=0)return false;
    if(!FMath::IsFinite(TipTolerance)||TipTolerance<0||TipTolerance>100)return false;
    if(!FMath::IsFinite(SheatheKinematicFraction)||SheatheKinematicFraction<0||SheatheKinematicFraction>1)return false;
    for(float V:{DrawSlidingSpeed,SheatheSlidingSpeed})if(!FMath::IsFinite(V)||V<0)return false;
    for(const FVector2D Range:{DrawNNBlendRange,SheatheNNBlendRange})if(!FMath::IsFinite(Range.X)||!FMath::IsFinite(Range.Y)||Range.X<.5||Range.Y>1||Range.Y<Range.X)return false;
    ProphecySwordHolsterPose::ConfigureNodeOverrides(A,DrawNNBlendRange,SheatheNNBlendRange,DrawSlidingSpeed,SheatheSlidingSpeed);
    ProphecySwordHolster::Profiles.Add(A,{Shrink,Duration,Stabilization*.01f,ReturnDuration,ShrinkDuration,AttachedSpeed,AttachedRotation,TipTolerance,LeewayPhase,HigherSolverAccuracy,SheatheKinematicFraction});ProphecySwordHolster::EnsureCleanup();return true;
}
bool UProphecySwordHolsterLibrary::DrawSword(AProphecyAgent* A,bool Sheathe)
{
    if(!IsInGameThread() || !IsValid(A) || !A->GetWorld() || !A->GetWorld()->IsGameWorld())return false;
    // StartHolster resolves the selected action's profile speeds. Retain the
    // original defaults for callers that have not configured a lab profile.
    auto* C=A->FindComponentByClass<UProphecySwordComponent>();return C && C->StartHolster(Sheathe,100,180,60);
}
bool UProphecySwordHolsterLibrary::SetHolsterSimulatePhysics(AProphecyAgent* A,bool Simulate)
{
    const auto* P=ProphecySwordHolster::Profiles.Find(A);
    return ProphecyHolsterMount::SetSimulated(A,Simulate,P?P->ReturnDuration:.25f);
}

FTransform UProphecySwordComponent::GripLocal() const
{
    const auto* Base=ProphecySwordHolster::AssetScales.Find(this);
    const auto* S=ProphecySwordHolster::States.Find(Agent());const float Scale=S?S->Scale:1;
    return ProphecySwordHolster::ScaledGrip(Agent(),Base?*Base:FVector::OneVector,Scale);
}
bool UProphecySwordComponent::BindHolster(bool Kinematic)
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();auto* S=States.Find(A);
    if(!S||!IsValid(Blade)||!S->Reference.Holster.IsValid())return false;
    auto* Mesh=A->GetPoseReferenceMesh();if(!Mesh)return false;
    FString Error;
    if(Kinematic)
    {
        if(!ReleaseJoltBody())return false;
        S->Kinematic=true;S->World.Reset();
        Blade->SetSimulatePhysics(false);
    }
    else
    {
        auto* Character=A->GetJoltCharacterComponent();
        auto* World=JoltBody?JoltBody->GetWorldOwner():nullptr;FProphecyJoltBodyHandle SwordBody;
        if(!Character||!World||!JoltBody->GetBodyHandle(SwordBody)||JoltBody->IsAttachedCollider())return false;
        if(!ReleaseJoltGrip())return false;
        S->Kinematic=false;S->World=World;
        const bool HeldReach=S->Sheathe&&!S->Attached;
        if(!JoltBody->SetSimulationEnabled(HeldReach,Error))return false;
        if(S->Phase!=EPhase::Holstered)
        {
            if(!ProphecyLimbCollision::SetHolsterArmSuppressed(A,true,Error)
                ||!ApplyNeckLimits(A,true,Error)||!SetHeadClavicleSuppressed(A,true,Error))return false;
            ProphecySpecialSolver::HolsterChanged(A,S->Profile.HigherSolverAccuracy);
            TArray<FProphecyJoltBodyPair> Pairs;
            for(const USkeletalBodySetup* B:Mesh->GetPhysicsAsset()->SkeletalBodySetups)if(B)
            {FProphecyJoltBodyHandle H;if(Character->GetBodyHandle(B->BoneName,H))Pairs.Add({SwordBody,H});}
            if(auto* Scene=UProphecyJoltSceneCollisionComponent::FindForWorld(GetWorld()))
            {FProphecyJoltBodyHandle H;if(auto* P=Cast<UPrimitiveComponent>(S->Reference.Holster.Get()))if(Scene->GetBodyHandle(*P,INDEX_NONE,H))Pairs.Add({SwordBody,H});}
            if(!World->UpdateBodySuppressedPairs(SwordBody,Pairs).IsSuccess())return false;
            if(HeldReach&&!UpdateHolsterGrip())return false;
            if((S->Phase==EPhase::Slide||S->Phase==EPhase::AlignTip)&&!BeginAttachedArm(A,*S,Blade,JoltBody,Error))return false;
        }
    }
    // Rebinding must retain the current transform, scale and action progress.
    if(S->Attached)return Blade->AttachToComponent(S->Reference.Holster.Get(),FAttachmentTransformRules::KeepWorldTransform);
    if(Kinematic||(!S->Sheathe&&S->Phase==EPhase::Grow))
        return Blade->AttachToComponent(Mesh,FAttachmentTransformRules::KeepWorldTransform,A->SwordHandSocket);
    return true;
}
bool UProphecySwordComponent::UpdateHolsterGrip()
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();auto* S=States.Find(A);if(!S)return false;
    auto* Mesh=A->GetPoseReferenceMesh();auto* World=S->World.Get();
    FProphecyJoltBodyHandle SwordBody,Hand;
    if(!S->Kinematic&&(!World||!JoltBody||!A->GetJoltCharacterComponent()||!JoltBody->GetBodyHandle(SwordBody)
        ||!A->GetJoltCharacterComponent()->GetBodyHandle(TEXT("hand_r"),Hand)))return false;
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
    if(World->OwnsJoint(S->Joint))
    {
        if(FMath::IsNearlyEqual(S->Scale,S->JointScale,1.e-7f))return true;
        S->JointSettings.FrameB.ScaleTranslation(FVector(1,1,S->Scale/S->JointScale));S->JointScale=S->Scale;
        return World->UpdateJoint(S->Joint,S->JointSettings).IsSuccess()&&Drive();
    }
    FProphecyJoltBodyState HB;
    if(!World->ReadBody(Hand,HB).IsSuccess())return false;
    const FTransform HandWorld=Mesh->GetSocketTransform(A->SwordHandSocket);
    // The held sword follows the hand during S reach only. Attachment
    // removes this grip and gives the holster ownership of the sword path.
    S->JointSettings.Type=EProphecyJoltJointType::Fixed;S->JointSettings.BodyA=Hand;S->JointSettings.BodyB=SwordBody;
    S->JointSettings.FrameA=HandWorld.GetRelativeTransform(FTransform(HB.Rotation,HB.PositionCm));
    {
        FTransform BodyOrigin;if(!JoltBody->GetBodyOriginToComponent(BodyOrigin))return false;
        FTransform Component=GripLocal()*HandWorld;Component.RemoveScaling();
        S->JointSettings.FrameB=HandWorld.GetRelativeTransform(BodyOrigin*Component);
    }
    S->JointSettings.FrameA.RemoveScaling();S->JointSettings.FrameB.RemoveScaling();
    S->JointScale=S->Scale;
    return (World->OwnsJoint(S->Joint)?World->UpdateJoint(S->Joint,S->JointSettings):World->CreateJoint(S->JointSettings,{},S->Joint)).IsSuccess()&&Drive();
}
bool UProphecySwordComponent::PrepareForModeChange()
{
    using namespace ProphecySwordHolster;
    auto* A=Agent();auto* S=States.Find(A);if(!S)return true;
    FString Error;
    if(!EndAttachedArm(A,Error)){UE_LOG(LogTemp,Error,TEXT("Sword mode change arm release: %s"),*Error);return false;}
    ProphecySwordHolsterPose::Republish(A);
    DestroyJoint(*S);
    RestoreActionPhysics(A);
    S->World.Reset();
    bRefreshPending=true;SetComponentTickEnabled(true);
    return true;
}
void UProphecySwordComponent::ClearHolster()
{
    FString ArmError;if(!ProphecySwordHolster::EndAttachedArm(Agent(),ArmError))UE_LOG(LogTemp,Warning,TEXT("Sword arm restore: %s"),*ArmError);
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
    const bool Kinematic=A->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic;
    if(!Kinematic&&!A->IsJoltPhysicalAnimationEnabled())
    {UE_LOG(LogTemp,Warning,TEXT("Sword holster: simulated D/S requires active Jolt physics; check Jolt startup errors."));return false;}
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
    S.Kinematic=Kinematic;S.Sheathe=Sheathe;S.ReachSpeed=Reach;S.RotationSpeed=Rotation;S.SlideSpeed=Sliding;
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
    {RestoreActionPhysics(A);if(Sheathe&&!S.RestoreSimulation)SetSimulated(false);UE_LOG(LogTemp,Warning,TEXT("Sword holster angular limits admission: %s"),*CollisionError);return false;}
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
    if(S->Phase==EPhase::Holstered){if(!Pending.Contains(A)&&!bRefreshPending&&!PendingJoltBindId.IsValid())SetComponentTickEnabled(false);return true;}
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
        if(S->Kinematic)Blade->SetWorldTransform(Goal,false,nullptr,ETeleportType::TeleportPhysics);
        else Blade->SetRelativeTransform(Goal.GetRelativeTransform(S->Reference.Holster->GetComponentTransform()));
        return true;
    };
    if(S->Phase==EPhase::Prepare)
    {
        if(!BindHolster(S->Kinematic))return Fail(TEXT("Could not bind sword action physics."));
        S->Phase=EPhase::Reach;
    }
    ProphecySwordHolsterPose::FStatus PoseStatus;if(!ProphecySwordHolsterPose::Status(A,PoseStatus))return Fail(TEXT("Holster pose controller was lost."));
    // Take only mount ownership here. Grip compensation still begins at attachment.
    if(S->Phase==EPhase::Reach && S->Sheathe && PoseStatus.Progress>=S->Profile.SheatheKinematicFraction)
        if(!ProphecyHolsterMount::BeginGrip(A,S->Profile.ReturnDuration))return Fail(TEXT("Could not take kinematic ownership of the holster."));
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
            if(!SetScale(TargetScale) || !UpdateHolsterGrip())return Fail(Error.IsEmpty()?TEXT("Could not resize the held grip."):Error);
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
            if(!BeginAttachedArm(A,*S,Blade,JoltBody,Error))return Fail(Error);
        }
        else {if(!BeginAttachedArm(A,*S,Blade,JoltBody,Error))return Fail(Error);S->Insertion=1;}
        if(S->Sheathe){ProphecySwordHolsterPose::Status(A,PoseStatus);S->Phase=PoseStatus.Aligning?EPhase::AlignTip:EPhase::Slide;return true;}
        if(!ProphecySwordHolsterPose::SetSliding(A,true))return Fail(TEXT("Could not take kinematic ownership of the holster."));
        S->Phase=EPhase::Slide;
    }
    if(S->Phase==EPhase::AlignTip){
        double TargetScale;if(!ProphecySwordHolsterPose::SwordTarget(A,S->TargetHand,TargetScale))return Fail(TEXT("Missing tip alignment target"));
        if(!SetScale(TargetScale))return Fail(Error);
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
        if(!SetScale(TargetScale))return Fail(Error);
        FTransform BladeTarget;if(!ProphecySwordHolsterPose::PhysicsSwordTarget(A,BladeTarget))return Fail(TEXT("Missing sliding sword path"));
        if(!PresentSword(BladeTarget))return Fail(TEXT("Missing completed sword body"));
        // Ownership changes on the authored endpoint. Waiting for the previous
        // physics publication holds the joint into the first FK-return tick.
        if(S->Sheathe && S->Insertion>=1)
        {if(!EndAttachedArm(A,Error))return Fail(Error);DestroyJoint(*S);ProphecyHolsterMount::EndGrip(A);S->Phase=EPhase::Grow;S->GrowTicks=0;
            Blade->SetWorldTransform(BladeTarget,false,nullptr,ETeleportType::TeleportPhysics);return true;}
        if(!S->Sheathe && S->Insertion<=0)
        {
            if(!EndAttachedArm(A,Error))return Fail(Error);DestroyJoint(*S);ProphecyHolsterMount::EndGrip(A);S->Attached=false;S->Phase=EPhase::Grow;S->GrowTicks=0;
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
