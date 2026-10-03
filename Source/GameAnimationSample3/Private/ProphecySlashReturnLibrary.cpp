#include "ProphecySlashReturnLibrary.h"
#include "ProphecySlashReturn.h"
#include "ProphecySlashReturnMath.h"
#include "ProphecyHandChainMath.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#endif

namespace ProphecySlashReturn
{
#if WITH_EDITOR
static TAutoConsoleVariable<int32> AuditReturn(TEXT("Prophecy.SlashReturn.Audit"),0,TEXT("Log active attack-arm return stages for diagnosis."),ECVF_Default);
static TAutoConsoleVariable<int32> UnarmedShortestRotation(TEXT("Prophecy.SlashReturn.UnarmedShortestRotation"),1,TEXT("Comparison only: 0 restores the old sword-style winding on empty hands."),ECVF_Default);
static TAutoConsoleVariable<int32> RefinedReturn(TEXT("Prophecy.SlashReturn.Refined"),1,TEXT("Editor comparison: 0 restores pre-reach/direct-route return."),ECVF_Default);
static TAutoConsoleVariable<int32> BodyRouteGeometry(TEXT("Prophecy.SlashReturn.BodyRoute"),1,TEXT("Diagnosis only: 0 restores the carrier-space obstacle seam."),ECVF_Default);
#endif
static bool Refined()
{
#if WITH_EDITOR
    return RefinedReturn.GetValueOnGameThread()!=0;
#else
    return true;
#endif
}
static bool BodyRoute()
{
#if WITH_EDITOR
    return BodyRouteGeometry.GetValueOnGameThread()!=0;
#else
    return true;
#endif
}
static FVector RoutePath(const FVector& From,const FVector& To,double Width,double T,const FTransform* ReferenceToTorso=nullptr)
{
    if(!Refined()) return FrontPath(From,To,Width+5.,T);
#if WITH_EDITOR
    if(!BodyRoute() && ReferenceToTorso && T>0)
    {
        const FVector A=ReferenceToTorso->TransformPosition(From),B=ReferenceToTorso->TransformPosition(To);
        const double Angle=FMath::Abs(FMath::Atan2(From.Y,From.X)-FMath::Atan2(To.Y,To.X));
        auto Smooth=[](double X) {X=FMath::Clamp(X,0.,1.);return X*X*X*(10.+X*(-15.+6.*X));};
        const double Weight=Smooth((FMath::Sqrt(ReturnSegmentClearance(A,B,FMath::Max(1.,Width)))-1.02)/.12)*Smooth((PI-Angle)/.2);
        return Weight>=1 ? FMath::Lerp(From,To,T) : FMath::Lerp(FrontPath(From,To,Width+5.,T),FMath::Lerp(From,To,T),Weight);
    }
#endif
    return ClearFrontPath(From,To,Width,T,ReferenceToTorso);
}
using K=ProphecyBlendClock::EKind;
struct FConfig { float Hold=.3f,Blend=.5f,Speed=100; };
struct FReturn { FConfig Config; double Elapsed=0;bool Initialized=false; FTransform Wrist; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
// Separate from retained FConfig/FReturn allocations for Live Coding.
struct FArmOptions { float LeftHold=-1,LeftBlend=-1,LeftAlpha=1,RightAlpha=1; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FArmOptions> ArmOptions,ArmOptionBaselines;
static FArmOptions Options(const AProphecyAgent* A)
{ const auto* C=ArmOptions.IsEmpty()?nullptr:ArmOptions.Find(A);return C?*C:FArmOptions{}; }
static double Influence(const AProphecyAgent* A,int32 Arm)
{ const auto C=Options(A);return Arm==0?C.LeftAlpha:C.RightAlpha; }
static FConfig ConfigForArm(const AProphecyAgent* A,FConfig C,int32 Arm)
{
    if(Arm==0) { const auto O=Options(A);if(O.LeftHold>=0)C.Hold=O.LeftHold;if(O.LeftBlend>=0)C.Blend=O.LeftBlend; }
    return C;
}
static bool Alive(const AProphecyAgent* A,const FReturn& R,int32 Arm)
{
    // Match the blend clock's tick rounding, including float-authored durations.
    return Influence(A,Arm)>0 && R.Elapsed*60.+1.e-5<(double(R.Config.Hold)+R.Config.Blend)*60.;
}
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturn> Returns;
// Event-only selection; retain the old FReturn layout across Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>,int32> ReturnArms;
struct FBothArmsConfig { bool Enabled=false;TSet<FName> Attacks; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBothArmsConfig> BothArmsConfigs,BothArmsBaselines;
// Event-only gate; keep retained Live Coding config layouts unchanged.
static TMap<TWeakObjectPtr<const AProphecyAgent>,TSet<FName>> BlockedAttacks,BlockedAttackBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturn> ExtraReturns;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FName> ReturnAttacks;
static TMap<TWeakObjectPtr<const AProphecyAgent>,TSet<FName>> PelvisChoices,PelvisBaselines;
static TSet<TWeakObjectPtr<const AProphecyAgent>> PelvisReturns;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTransform> PelvisOffsets;
struct FRotationConfig { float Spine=0, Pelvis=1; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRotationConfig> RotationConfigs,RotationBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> RotationReturns;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FQuat> PelvisAxes;
bool UsesPelvisReference(const AProphecyAgent* A) { return PelvisReturns.Contains(A); }
bool UsesControlledReference(const AProphecyAgent* A)
{
    // Restore the original spine/clavicle-mounted neutral arm and torso
    // carrier. A rotation-node call must not replace that anatomical frame.
    // Only explicit pelvis-position returns use the configurable reference.
    return UsesPelvisReference(A);
}
void FitNeutralArm(const FTransform& Shoulder,
    FTransform& NeutralShoulder,FTransform& NeutralElbow,FTransform& NeutralWrist)
{
    if(!Refined()) return;
    // The reference determines orientation, not a second, detached shoulder.
    // Keep authored neutral geometry. Copying transient NN segment lengths here
    // feeds compressed forearms back into the next prediction and can collapse
    // the chain before the publication clamp restores its minimum length.
    const FVector Delta=Shoulder.GetLocation()-NeutralShoulder.GetLocation();
    NeutralShoulder.AddToTranslation(Delta);NeutralElbow.AddToTranslation(Delta);NeutralWrist.AddToTranslation(Delta);
}
void PelvisReferenceFrames(const AProphecyAgent* A,const FTransform& IdleTorso,const FTransform& IdlePelvis,
    const FTransform& Pelvis,const FTransform& PreviousPelvis,const FQuat& RootRotation,const FQuat& PreviousRootRotation,
    FTransform& Reference,FTransform& PreviousReference,const FTransform* TorsoOrigin,const FTransform* PreviousTorsoOrigin)
{
    const float* Setting=RotationReturns.Find(A);const float Alpha=Setting ? *Setting : 1.f;
    FQuat Rotation=RootRotation,PreviousRotation=PreviousRootRotation;
    if(Alpha<1)
    {
        // Calibrate the pelvis bone's arbitrary axes to anatomical torso axes
        // once. All weights then describe the same two rotation endpoints.
        auto* Axes=PelvisAxes.Find(A);
        if(!Axes) Axes=&PelvisAxes.Add(A,(IdlePelvis.GetRotation().Inverse()*IdleTorso.GetRotation()).GetNormalized());
        Rotation=(Pelvis.GetRotation()*(*Axes)).GetNormalized();
        PreviousRotation=(PreviousPelvis.GetRotation()*(*Axes)).GetNormalized();
        if(Alpha>0)
        {
            Rotation=FQuat::Slerp(Rotation,RootRotation,Alpha).GetNormalized();
            PreviousRotation=FQuat::Slerp(PreviousRotation,PreviousRootRotation,Alpha).GetNormalized();
        }
    }
    if(TorsoOrigin && PreviousTorsoOrigin)
    {
        Reference=FTransform(Rotation,TorsoOrigin->GetLocation());
        PreviousReference=FTransform(PreviousRotation,PreviousTorsoOrigin->GetLocation());return;
    }
    auto* Offset=PelvisOffsets.Find(A);
    if(!Offset) Offset=&PelvisOffsets.Add(A,FTransform(FQuat::Identity,
        Rotation.UnrotateVector(IdleTorso.GetLocation()-IdlePelvis.GetLocation())));
    Reference=FTransform(Rotation,Pelvis.GetLocation()+Rotation.RotateVector(Offset->GetLocation()));
    PreviousReference=FTransform(PreviousRotation,PreviousPelvis.GetLocation()+PreviousRotation.RotateVector(Offset->GetLocation()));
}
static void LatchReference(const AProphecyAgent* A,FName Attack)
{
    PelvisReturns.Remove(A);PelvisOffsets.Remove(A);RotationReturns.Remove(A);PelvisAxes.Remove(A);
    if(const auto* Choices=PelvisChoices.Find(A);Choices && Choices->Contains(Attack)) PelvisReturns.Add(A);
    if(const auto* C=RotationConfigs.Find(A)) RotationReturns.Add(A,UsesPelvisReference(A)?C->Pelvis:C->Spine);
}
// Separate versioned sidecar: do not resize the retained FReturn allocation
// while Live Coding. Basis is calibrated to the actual held blade's long axis.
struct FWeaponRoute
{
    FQuat Basis=FQuat::Identity;
    FRotator Rotation=FRotator::ZeroRotator,Goal=FRotator::ZeroRotator;
    double Side=1;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FWeaponRoute> WeaponRoutes;
struct FBladeGeometry { FVector Base=FVector::ZeroVector,Tip=FVector::ZeroVector;double Padding=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBladeGeometry> Blades;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FWeaponRoute> ExtraWeaponRoutes;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBladeGeometry> ExtraBlades;
// Separate storage keeps retained return/route layouts valid during Live Coding.
// Offsets live in anatomical torso space, independently of the return carrier.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FVector> BladeOffsets,ExtraBladeOffsets;
static FWeaponRoute MakeWeaponRoute(const AProphecyAgent* A,int32 ArmIndex,const FTransform& Hand,const FTransform& Neutral,double Width,
    TMap<TWeakObjectPtr<const AProphecyAgent>,FBladeGeometry>& ArmBlades,const FTransform* ReferenceToTorso=nullptr)
{
    FWeaponRoute V;FVector Axis=Neutral.GetRotation().UnrotateVector(FVector::ForwardVector);
    FVector Up=Neutral.GetRotation().UnrotateVector(FVector::UpVector);
    // A held sword belongs to the right hand. Its grip/bounds must never be
    // interpreted as left-hand geometry when returning a left hook/overhead.
    if(const auto* Sword=ArmIndex==1 ? A->GetHeldSword() : nullptr)
    {
        TArray<UStaticMeshComponent*> Meshes;Sword->GetComponents(Meshes);
        for(auto* Mesh:Meshes) if(Mesh && Mesh->GetStaticMesh() && (Mesh->GetFName()==TEXT("sword") || Meshes.Num()==1))
        {
            const FBox B=Mesh->GetStaticMesh()->GetBoundingBox();const FVector Size=B.GetSize();
            const int32 I=Size.X>Size.Y ? (Size.X>Size.Z?0:2) : (Size.Y>Size.Z?1:2);
            FVector P=B.GetCenter(),Q=P;P[I]=B.Min[I];Q[I]=B.Max[I];
            P=A->SwordGripTransform.TransformPosition(P);Q=A->SwordGripTransform.TransformPosition(Q);
            if(P.SizeSquared()>Q.SizeSquared()) Swap(P,Q);
            double Radius=0;
            for(int32 J=0;J<3;++J) if(J!=I) Radius+=FMath::Square(Size[J]*A->SwordGripTransform.GetScale3D()[J]*.5);
            ArmBlades.Add(A,FBladeGeometry{P,Q,FMath::Sqrt(Radius)+1.});
            Axis=(Q-P).GetSafeNormal();Up=A->SwordGripTransform.TransformVectorNoScale(FVector::YAxisVector);break;
        }
    }
    V.Basis=FRotationMatrix::MakeFromXZ(Axis,Up).ToQuat();
    V.Rotation=(Hand.GetRotation()*V.Basis).Rotator();
    V.Side=Hand.GetLocation().Y<=0 ? 1. : -1.;
    const FRotator Idle=(Neutral.GetRotation()*V.Basis).Rotator();
    V.Goal=FRotator(0,DirectedHeading(V.Rotation.Yaw,0,V.Side),Idle.Roll);
    if(const auto* Blade=ArmBlades.Find(A))
    {
        // A clear short rotation at the outgoing wrist must not become a full
        // revolution to avoid a later positional overlap. Translation has its
        // own clearance solve. Otherwise retain the existing moving-hand route.
        const double Short=V.Rotation.Yaw+FMath::UnwindDegrees(-V.Rotation.Yaw);
        double BestCost=1.e30,BestYaw=V.Goal.Yaw;
        for(double Goal:{Short,Short+360.,Short-360.})
        {
            if(FMath::Abs(Goal-V.Rotation.Yaw)>360.+1.e-6) continue;
            double Cost=0;bool ClearShort=Goal==Short;
            for(int32 I=1;I<=48;++I)
            {
                const double T=I/48.;FRotator End=V.Goal;End.Yaw=Goal;
                FTransform P((BlendWeaponRotation(V.Rotation,End,T).Quaternion()*V.Basis.Inverse()).GetNormalized(),
                    Hand.GetLocation());
                if(ClearShort && BladeClearance(ReferenceToTorso ? P*(*ReferenceToTorso) : P,
                    Blade->Base,Blade->Tip,Width,Blade->Padding)<1.04) ClearShort=false;
                P.SetLocation(RoutePath(Hand.GetLocation(),Neutral.GetLocation(),Width,T,ReferenceToTorso));
                Cost+=FMath::Max(0.,1.04-BladeClearance(ReferenceToTorso ? P*(*ReferenceToTorso) : P,Blade->Base,Blade->Tip,Width,Blade->Padding));
            }
            if(ClearShort) { BestYaw=Short;break; }
            Cost+=FMath::Abs(Goal-V.Rotation.Yaw)*1.e-5;
            if(Cost<BestCost) {BestCost=Cost;BestYaw=Goal;}
        }
        V.Goal.Yaw=BestYaw;
    }
    // Retain the selected direction after Rotation advances toward Goal.
    V.Side=FMath::Sign(V.Goal.Yaw-V.Rotation.Yaw);
#if WITH_EDITOR
    if(AuditReturn.GetValueOnGameThread() && A->IsPlayerControlled())
        UE_LOG(LogTemp,Display,TEXT("ReturnSwordRoute time=%.9f arm=%d start=%.6f goal=%.6f idle=%.6f side=%.0f"),
            A->GetWorld()->GetTimeSeconds(),ArmIndex,V.Rotation.Yaw,V.Goal.Yaw,Idle.Yaw,V.Side);
#endif
    return V;
}
bool RightWristReturnDirection(const AProphecyAgent* A,double& Direction)
{
    if(!(ActiveArmMask(A)&2))return false;
    const auto* Route=ActiveArm(A)==1?WeaponRoutes.Find(A):ExtraWeaponRoutes.Find(A);
    if(!Route)return false;
    Direction=Route->Side;return true;
}
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map) { for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Baselines);Clean(Returns);Clean(ReturnArms);Clean(WeaponRoutes);Clean(Blades);
        Clean(BladeOffsets);Clean(ExtraBladeOffsets);
        Clean(ArmOptions);Clean(ArmOptionBaselines);
        Clean(BlockedAttacks);Clean(BlockedAttackBaselines);
        Clean(BothArmsConfigs);Clean(BothArmsBaselines);Clean(ExtraReturns);Clean(ReturnAttacks);Clean(ExtraWeaponRoutes);Clean(ExtraBlades);
        Clean(PelvisChoices);Clean(PelvisBaselines);Clean(PelvisOffsets);
        Clean(RotationConfigs);Clean(RotationBaselines);Clean(RotationReturns);Clean(PelvisAxes);
        for(auto It=PelvisReturns.CreateIterator();It;++It)
            if(!It->IsValid() || (*It)->GetWorld()==W) It.RemoveCurrent();
    });
}
bool IsSlash(FName N)
{ return N==TEXT("slashL") || N==TEXT("slashR") || N==TEXT("slashLD") || N==TEXT("slashRD") || N==TEXT("slashLU") || N==TEXT("slashRU"); }
int32 ArmForAttack(FName N)
{
    if(IsSlash(N) || N==TEXT("pike") || N==TEXT("jabR") || N==TEXT("hookR") || N==TEXT("overR")) return 1;
    if(N==TEXT("jabL") || N==TEXT("hookL") || N==TEXT("overL")) return 0;
    return INDEX_NONE;
}
bool Active(const AProphecyAgent* A) { return !Returns.IsEmpty() && Returns.Contains(A); }
int32 ActiveArm(const AProphecyAgent* A)
{
    if(!Active(A)) return INDEX_NONE;
    const int32* Arm=ReturnArms.Find(A);
    return Arm ? *Arm : 1; // A slash already returning when this patch loads.
}
uint8 ActiveArmMask(const AProphecyAgent* A)
{
    const int32 Arm=ActiveArm(A);if(Arm==INDEX_NONE) return 0;
    uint8 Mask=Alive(A,Returns.FindChecked(A),Arm)?uint8(1<<Arm):0;
    if(const auto* Extra=ExtraReturns.Find(A);Extra && Alive(A,*Extra,1-Arm))Mask|=uint8(1<<(1-Arm));
    return Mask;
}
static void StartRemainingClock(const AProphecyAgent* A)
{
    auto* R=Returns.Find(A);if(!R)return;
    // Preserve any unread ticks when adding a longer-lived extra arm mid-return.
    R->Elapsed+=ProphecyBlendClock::Consume(A,K::SlashReturn);
    const int32 Arm=ActiveArm(A);
    double End=Alive(A,*R,Arm)?double(R->Config.Hold)+R->Config.Blend:0;
    if(auto* Extra=ExtraReturns.Find(A))
    {
        Extra->Elapsed=R->Elapsed;
        if(Alive(A,*Extra,1-Arm))End=FMath::Max(End,double(Extra->Config.Hold)+Extra->Config.Blend);
    }
    if(End<=R->Elapsed)Cancel(A);else ProphecyBlendClock::Start(A,K::SlashReturn,End-R->Elapsed);
}
static void CancelExtra(const AProphecyAgent* A)
{ ExtraReturns.Remove(A);ExtraWeaponRoutes.Remove(A);ExtraBlades.Remove(A);ExtraBladeOffsets.Remove(A); }
void Cancel(const AProphecyAgent* A)
{ CancelExtra(A);BladeOffsets.Remove(A);PelvisReturns.Remove(A);PelvisOffsets.Remove(A);RotationReturns.Remove(A);PelvisAxes.Remove(A);ReturnAttacks.Remove(A);ReturnArms.Remove(A);Blades.Remove(A);WeaponRoutes.Remove(A);if(Returns.Remove(A)) ProphecyBlendClock::Stop(A,K::SlashReturn); }
static void CancelExtension(const AProphecyAgent* A)
{
    const auto* Attack=ReturnAttacks.Find(A);
    if(Attack && ArmForAttack(*Attack)==INDEX_NONE) Cancel(A);
    else { CancelExtra(A);if(!ActiveArmMask(A))Cancel(A); }
}
static void SyncExtra(const AProphecyAgent* A)
{
    const auto* Choice=BothArmsConfigs.Find(A);const auto* Attack=ReturnAttacks.Find(A);
    if(!Choice || !Choice->Enabled || !Attack || !Choice->Attacks.Contains(*Attack)) { CancelExtension(A);return; }
    // Called at entry / in Special Ended. Never reset a return already in progress.
    if(!ExtraReturns.Contains(A)) if(const auto* C=Configs.Find(A)) if(const auto* R=Returns.Find(A))
    {
        FReturn Extra{ConfigForArm(A,*C,1-ActiveArm(A))};Extra.Elapsed=R->Elapsed;
        if(Alive(A,Extra,1-ActiveArm(A))) { ExtraReturns.Add(A,Extra);StartRemainingClock(A); }
    }
}
void Begin(const AProphecyAgent* A,FName Attack)
{
    Cancel(A);int32 Arm=ArmForAttack(Attack);
    if(!BlockedAttacks.IsEmpty())if(const auto* Blocked=BlockedAttacks.Find(A);Blocked && Blocked->Contains(Attack))return;
    if(Arm==INDEX_NONE)
    {
        const auto* Choice=BothArmsConfigs.Find(A);
        if(!Choice || !Choice->Enabled || !Choice->Attacks.Contains(Attack)) return;
        Arm=1; // Explicitly selected kick/headbutt: both arms, no default return.
    }
    if(const auto* C=Configs.Find(A))
    { Returns.Add(A,FReturn{ConfigForArm(A,*C,Arm)});ReturnArms.Add(A,Arm);ReturnAttacks.Add(A,Attack);LatchReference(A,Attack);SyncExtra(A);StartRemainingClock(A); }
}
void Remove(const AProphecyAgent* A) { Cancel(A);Configs.Remove(A);Baselines.Remove(A);ArmOptions.Remove(A);ArmOptionBaselines.Remove(A);BothArmsConfigs.Remove(A);BothArmsBaselines.Remove(A);PelvisChoices.Remove(A);PelvisBaselines.Remove(A);RotationConfigs.Remove(A);RotationBaselines.Remove(A);BlockedAttacks.Remove(A);BlockedAttackBaselines.Remove(A); }
void CaptureReset(const AProphecyAgent* A)
{ EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A);
  if(const auto* C=ArmOptions.Find(A))ArmOptionBaselines.Add(A,*C);else ArmOptionBaselines.Remove(A);
  if(const auto* C=BlockedAttacks.Find(A)) BlockedAttackBaselines.Add(A,*C);else BlockedAttackBaselines.Remove(A);
  if(const auto* C=BothArmsConfigs.Find(A)) BothArmsBaselines.Add(A,*C);else BothArmsBaselines.Remove(A);
  if(const auto* C=PelvisChoices.Find(A)) PelvisBaselines.Add(A,*C);else PelvisBaselines.Remove(A);
  if(const auto* C=RotationConfigs.Find(A)) RotationBaselines.Add(A,*C);else RotationBaselines.Remove(A); }
void RestoreReset(const AProphecyAgent* A)
{ Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C);
  ArmOptions.Remove(A);if(const auto* C=ArmOptionBaselines.Find(A))ArmOptions.Add(A,*C);
  BlockedAttacks.Remove(A);if(const auto* C=BlockedAttackBaselines.Find(A)) BlockedAttacks.Add(A,*C);
  BothArmsConfigs.Remove(A);if(const auto* C=BothArmsBaselines.Find(A)) BothArmsConfigs.Add(A,*C);
  PelvisChoices.Remove(A);if(const auto* C=PelvisBaselines.Find(A)) PelvisChoices.Add(A,*C);
  RotationConfigs.Remove(A);if(const auto* C=RotationBaselines.Find(A)) RotationConfigs.Add(A,*C); }
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A);ArmOptionBaselines.Remove(A);BothArmsBaselines.Remove(A);PelvisBaselines.Remove(A);RotationBaselines.Remove(A);BlockedAttackBaselines.Remove(A); }
double AdvanceFrame(const AProphecyAgent* A)
{
    auto* R=Returns.Find(A);if(!R) return 0;
    const double Dt=ProphecyBlendClock::Consume(A,K::SlashReturn);R->Elapsed+=Dt;
    if(auto* Extra=ExtraReturns.Find(A))
    {
        Extra->Elapsed=R->Elapsed;
        if(!Alive(A,*Extra,1-ActiveArm(A)))CancelExtra(A);
    }
    if(!ActiveArmMask(A)) { Cancel(A);return 0; }
    return Dt;
}
static void BlendArmInfluence(const FTransform* NN,double Weight,FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist)
{
    if(Weight>=1)return;
    if(Weight<=0) { Shoulder=NN[0];Elbow=NN[1];Wrist=NN[2];return; }
    // Blend in the joint hierarchy, then reconstruct FK attachments. Blending
    // three independent world positions would shorten the forearm mid-blend.
    const FTransform NNElbow=NN[1].GetRelativeTransform(NN[0]),NNWrist=NN[2].GetRelativeTransform(NN[1]);
    const FQuat ElbowLocal=Shoulder.GetRotation().Inverse()*Elbow.GetRotation();
    const FQuat WristLocal=Elbow.GetRotation().Inverse()*Wrist.GetRotation();
    Shoulder=FTransform(FQuat::Slerp(NN[0].GetRotation(),Shoulder.GetRotation(),Weight).GetNormalized(),NN[0].GetLocation(),NN[0].GetScale3D());
    Elbow=FTransform(FQuat::Slerp(NNElbow.GetRotation(),ElbowLocal,Weight).GetNormalized(),NNElbow.GetLocation(),NNElbow.GetScale3D())*Shoulder;
    Wrist=FTransform(FQuat::Slerp(NNWrist.GetRotation(),WristLocal,Weight).GetNormalized(),NNWrist.GetLocation(),NNWrist.GetScale3D())*Elbow;
}
void ApplyPose(const AProphecyAgent* A,int32 ArmIndex,double Dt,const FTransform& Torso,const FTransform& PreviousTorso,
    double HalfWidth,const FTransform& PreviousShoulder,const FTransform& PreviousElbow,
    const FTransform& PreviousWrist,const FTransform& NeutralShoulder,
    const FTransform& NeutralElbow,const FTransform& NeutralWrist,const FTransform& InitialNeutralWrist,
    FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,const FVector& LocalPole,
    const FTransform* Reference,const FTransform* PreviousReference)
{
    const int32 Primary=ActiveArm(A);if(Primary==INDEX_NONE || (ArmIndex!=0 && ArmIndex!=1)) return;
    const bool Extra=ArmIndex!=Primary;
    auto* R=Extra ? ExtraReturns.Find(A) : Returns.Find(A);if(!R || !Alive(A,*R,ArmIndex)) return;
    const double ArmAlpha=Influence(A,ArmIndex);
    const FTransform Natural[3]={Shoulder,Elbow,Wrist};
    auto& ArmRoutes=Extra ? ExtraWeaponRoutes : WeaponRoutes;
    auto& ArmBlades=Extra ? ExtraBlades : Blades;
    const FTransform& Frame=Reference ? *Reference : Torso;
    const FTransform& PreviousFrame=PreviousReference ? *PreviousReference : PreviousTorso;
    const FTransform ReferenceToTorso=Reference ? Frame.GetRelativeTransform(Torso) : FTransform::Identity;
    const FTransform* RouteTransform=Reference ? &ReferenceToTorso : nullptr;
    const double T=R->Elapsed+1.e-8<R->Config.Hold ? 0. : R->Config.Blend>0
        ? FMath::Clamp((R->Elapsed-R->Config.Hold)/R->Config.Blend,0.,1.) : 1.;
    if(!R->Initialized)
    {
        R->Initialized=true;R->Wrist=PreviousWrist.GetRelativeTransform(PreviousFrame);
        // Capture once from the outgoing pose and its fitted neutral arm.
        // Config.Speed is a per-return copy, not the saved setting.
        // Later torso/target motion must not recalculate or compound this scale.
        R->Config.Speed*=float(FVector::Distance(PreviousWrist.GetLocation(),InitialNeutralWrist.GetLocation())/100.);
    }
    const FTransform Neutral=NeutralWrist.GetRelativeTransform(Frame);
    auto* Weapon=ArmRoutes.Find(A);
    if(!Weapon)
    {
        Weapon=&ArmRoutes.Add(A,MakeWeaponRoute(A,ArmIndex,R->Wrist,Neutral,HalfWidth,ArmBlades,RouteTransform));
    }
    const double RouteWidth=HalfWidth+5.;
    const double Step=RouteTransform && BodyRoute() ? Advance(RouteTransform->TransformPosition(R->Wrist.GetLocation()),
        RouteTransform->TransformPosition(Neutral.GetLocation()),RouteWidth,R->Config.Speed*Dt,Dt) :
        Advance(R->Wrist.GetLocation(),Neutral.GetLocation(),RouteWidth,R->Config.Speed*Dt,Dt);
    const double RotationStep=1.-FMath::Exp(-R->Config.Speed*Dt/25.);
    R->Wrist.SetLocation(RoutePath(R->Wrist.GetLocation(),Neutral.GetLocation(),HalfWidth,Step,RouteTransform));
    const double Alpha=T*T*(3-2*T);
    const FTransform NN=Wrist.GetRelativeTransform(Frame);
    bool bWeaponWinding=ArmBlades.Contains(A);
#if WITH_EDITOR
    bWeaponWinding|=UnarmedShortestRotation.GetValueOnGameThread()==0;
#endif
    FQuat Rotation;
    if(bWeaponWinding)
    {
        // A real blade retains its tested outward winding and clearance path.
        const double YawStep=FMath::Min(Step,120./FMath::Max(1.e-6,FMath::Abs(Weapon->Goal.Yaw-Weapon->Rotation.Yaw)));
        Weapon->Rotation=BlendWeaponRotation(Weapon->Rotation,Weapon->Goal,YawStep);
        R->Wrist.SetRotation((Weapon->Rotation.Quaternion()*Weapon->Basis.Inverse()).GetNormalized());
        FRotator NNRotation=(NN.GetRotation()*Weapon->Basis).Rotator();
        NNRotation.Yaw=Weapon->Goal.Yaw+FMath::UnwindDegrees(NNRotation.Yaw-Weapon->Goal.Yaw);
        Rotation=(BlendWeaponRotation(Weapon->Rotation,NNRotation,Alpha).Quaternion()*Weapon->Basis.Inverse()).GetNormalized();
    }
    else
    {
        // Empty hands need no blade-unwinding direction. Applying that Euler
        // route here made left hooks rotate almost a full turn out of attacks.
        Rotation=AdvanceUnarmedRotation(R->Wrist,Neutral.GetRotation(),NN.GetRotation(),Step,Alpha);
    }
    FTransform LocalTarget(Rotation,RoutePath(R->Wrist.GetLocation(),NN.GetLocation(),HalfWidth,Alpha,RouteTransform));
#if WITH_EDITOR
    const FVector BeforeClear=LocalTarget.GetLocation();
#endif
    // Reference is a motion carrier only. Clearance must follow the actual body.
    auto ClearSmoothly=[&](FTransform& TorsoTarget)
    {
        const auto* Blade=ArmBlades.Find(A);if(!Blade)return;
        const FVector Desired=ClearBladePosition(TorsoTarget,Blade->Base,Blade->Tip,HalfWidth,Blade->Padding)-TorsoTarget.GetLocation();
        auto& Offsets=Extra ? ExtraBladeOffsets : BladeOffsets;
        FVector& Offset=Offsets.FindOrAdd(A,FVector::ZeroVector);
        // Smooth engagement AND release; a transient blade intersection must
        // not teleport the IK goal outside reach. Respect the return speed too.
        const double StepTime=FMath::Max(0.,Dt);
        Offset+=((Desired-Offset)*(1.-FMath::Exp(-StepTime/.1))).GetClampedToMaxSize(R->Config.Speed*StepTime);
        TorsoTarget.AddToTranslation(Offset);
    };
    FTransform Target;
    if(Reference)
    {
        FTransform TorsoTarget=(LocalTarget*Frame).GetRelativeTransform(Torso);
        ClearSmoothly(TorsoTarget);
        Target=TorsoTarget*Torso;
    }
    else
    {
        ClearSmoothly(LocalTarget);
        Target=LocalTarget*Torso;
    }
    auto Carry=[&](const FTransform& V) { return V.GetRelativeTransform(PreviousFrame)*Frame; };
    const FVector LocalUpper=Shoulder.GetRotation().UnrotateVector(Elbow.GetLocation()-Shoulder.GetLocation());
    // The moving shoulder can temporarily outrun a pelvis-local hand. Soften
    // the target before the two-bone solve instead of hitting its hard straight
    // singularity. Derive the zone from the neutral bend and the SAME forearm
    // length the two solves below will use; fade with procedural ownership.
    const double UpperLength=LocalUpper.Length();
    const double LowerLength=FVector::Distance(Elbow.GetLocation(),Wrist.GetLocation());
    const double CosBend=FMath::Clamp(FVector::DotProduct(
        (NeutralElbow.GetLocation()-NeutralShoulder.GetLocation()).GetSafeNormal(),
        (NeutralWrist.GetLocation()-NeutralElbow.GetLocation()).GetSafeNormal()),-1.,1.);
    const double Reach=UpperLength+LowerLength;
    const double NeutralReach=FMath::Sqrt(FMath::Max(0.,UpperLength*UpperLength+LowerLength*LowerLength+2*UpperLength*LowerLength*CosBend));
    const FVector TargetDelta=Target.GetLocation()-Shoulder.GetLocation();
    const double Distance=TargetDelta.Length();
    // Start exactly at the neutral reach: an already neutral arm is unchanged.
    // Preserve half its geometric bend reserve at the asymptote, then remove
    // that reserve continuously as NN ownership reaches one.
    const double Reserve=FMath::Max(0.,Reach-NeutralReach)*(1.-Alpha);
    const double SoftDistance=Refined() ? SoftReturnReach(Distance,Reach-.5*Reserve,.5*Reserve) : Distance;
    if(SoftDistance<Distance && Distance>1.e-8)
        Target.SetLocation(Shoulder.GetLocation()+TargetDelta*(SoftDistance/Distance));
    FTransform GuideShoulder=Shoulder,GuideElbow=Elbow,GuideWrist=Wrist;
    // Fade the hinge guidance to NN together with ownership. Prior hinge comes
    // from accepted/rebased state, so torso motion and root snaps cannot orbit it.
    ProphecyHandChain::Resolve(NeutralShoulder,NeutralElbow,NeutralWrist,
        GuideShoulder,GuideElbow,GuideWrist,Target,LocalUpper,LocalPole,Alpha,LowerLength);
    ProphecyHandChain::Resolve(Carry(PreviousShoulder),Carry(PreviousElbow),Carry(PreviousWrist),
        GuideShoulder,GuideElbow,GuideWrist,Target,LocalUpper,LocalPole,
        FMath::Lerp(RotationStep,1.,Alpha),LowerLength);
    const FVector S=Torso.InverseTransformPosition(GuideShoulder.GetLocation());
    const FVector E=Torso.InverseTransformPosition(GuideElbow.GetLocation());
    const FVector H=Torso.InverseTransformPosition(GuideWrist.GetLocation());
    const double Turn=ClearElbowAngle(S,E,H,HalfWidth,Dt);
    if(Turn!=0)
    {
        const FQuat Q((GuideWrist.GetLocation()-GuideShoulder.GetLocation()).GetSafeNormal(),Turn);
        GuideElbow.SetLocation(GuideShoulder.GetLocation()+Q.RotateVector(GuideElbow.GetLocation()-GuideShoulder.GetLocation()));
        GuideShoulder.SetRotation((Q*GuideShoulder.GetRotation()).GetNormalized());
        GuideElbow.SetRotation((Q*GuideElbow.GetRotation()).GetNormalized());
    }
    Shoulder=GuideShoulder;Elbow=GuideElbow;Wrist=GuideWrist;
    // Fade the complete solved correction, including blade/elbow clearance,
    // so no procedural residual is released abruptly when the timer retires.
    const double ReturnWeight=ArmAlpha*(1.-Alpha);
    if(ReturnWeight<1)BlendArmInfluence(Natural,ReturnWeight,Shoulder,Elbow,Wrist);
#if WITH_EDITOR
    if(const auto* Audit=IConsoleManager::Get().FindConsoleVariable(TEXT("Prophecy.SlashReturn.Audit"));Audit && Audit->GetInt())
    {
        if(A->IsPlayerControlled() && ArmIndex==1)
            UE_LOG(LogTemp,Display,TEXT("ReturnSwordStep time=%.9f route=%.6f goal=%.6f nn=%.6f target=%.6f final=%.6f weight=%.6f"),
                A->GetWorld()->GetTimeSeconds(),Weapon->Rotation.Yaw,Weapon->Goal.Yaw,(NN.GetRotation()*Weapon->Basis).Rotator().Yaw,
                (Rotation*Weapon->Basis).Rotator().Yaw,(Wrist.GetRelativeTransform(Frame).GetRotation()*Weapon->Basis).Rotator().Yaw,ReturnWeight);
        auto V=[](const FVector& P){return FString::Printf(TEXT("%.6f,%.6f,%.6f"),P.X,P.Y,P.Z);};
        auto Transform=[&](const FTransform& P) { const FTransform L=P.GetRelativeTransform(Torso);const FQuat Q=L.GetRotation();
            return V(L.GetLocation())+FString::Printf(TEXT(",%.9f,%.9f,%.9f,%.9f"),Q.X,Q.Y,Q.Z,Q.W); };
        UE_LOG(LogTemp,Display,TEXT("SlashElbowAudit,%s,%.6f,%.6f,%.6f,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s"),
            *A->GetName(),R->Elapsed,Alpha,Turn,*V(LocalUpper),*V(LocalPole),
            *Transform(Carry(PreviousShoulder)),*Transform(Carry(PreviousElbow)),*Transform(Carry(PreviousWrist)),
            *Transform(NeutralShoulder),*Transform(NeutralElbow),*Transform(NeutralWrist),*V(E),*V(H));
        UE_LOG(LogTemp,Display,TEXT("SlashReturnAudit,%s,%.6f,%.6f,%.6f,%.6f,%.6f,%s,%s,%s,%s,%s,%s,%s,%.6f,%.6f,%.6f"),
            *A->GetName(),R->Elapsed,Dt,Step,Alpha,HalfWidth,
            *V(R->Wrist.GetLocation()),*V(Neutral.GetLocation()),*V(NN.GetLocation()),*V(BeforeClear),
            *V(LocalTarget.GetLocation()),*V(Torso.InverseTransformPosition(Wrist.GetLocation())),
            *V(S),LocalUpper.Length(),(GuideWrist.GetLocation()-GuideElbow.GetLocation()).Length(),R->Config.Speed);
    }
#endif
}
}
bool UProphecySlashReturnLibrary::SetAttackArmReturnEnabled(AProphecyAgent* A,
    bool SlashL,bool SlashR,bool SlashLD,bool SlashRD,bool SlashLU,bool SlashRU,bool Pike,
    bool JabL,bool JabR,bool HookL,bool HookR,bool OverL,bool OverR,bool Headbutt,bool KickL,bool KickR)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown)return false;
    EnsureCleanup();TSet<FName> Blocked;
    const TCHAR* Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    const bool Choices[]={SlashL,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike,JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR};
    for(int32 I=0;I<UE_ARRAY_COUNT(Names);++I)if(!Choices[I])Blocked.Add(Names[I]);
    if(const auto* Current=ReturnAttacks.Find(A);Current && Blocked.Contains(*Current))Cancel(A);
    if(Blocked.IsEmpty())BlockedAttacks.Remove(A);else BlockedAttacks.Add(A,MoveTemp(Blocked));
    if(ProphecyAttackRecovery::IsEndEvent(A) && !Active(A))Begin(A,ProphecyAttackRecovery::EndEventAttack(A));
    return true;
}
bool UProphecySlashReturnLibrary::SetSlashRightArmReturnToNeutral(AProphecyAgent* A,bool Enabled,float Hold,float Blend,float Speed,
    float LeftHold,float LeftBlend,float LeftAlpha,float RightAlpha)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown ||
        !FMath::IsFinite(Hold) || !FMath::IsFinite(Blend) || !FMath::IsFinite(Speed) || Hold<0 || Blend<0 || Speed<0 ||
        !FMath::IsFinite(LeftHold) || !FMath::IsFinite(LeftBlend) || (LeftHold<0 && LeftHold!=-1) || (LeftBlend<0 && LeftBlend!=-1) ||
        !FMath::IsFinite(LeftAlpha) || !FMath::IsFinite(RightAlpha)) return false;
    LeftAlpha=FMath::Clamp(LeftAlpha,0.f,1.f);RightAlpha=FMath::Clamp(RightAlpha,0.f,1.f);
    EnsureCleanup();
    const auto Previous=Options(A);
    const FArmOptions New{LeftHold,LeftBlend,LeftAlpha,RightAlpha};
    const bool Effective=Enabled && ((RightAlpha>0 && double(Hold)+Blend>0) ||
        (LeftAlpha>0 && double(LeftHold<0?Hold:LeftHold)+(LeftBlend<0?Blend:LeftBlend)>0));
    if(Effective && (LeftHold!=-1 || LeftBlend!=-1 || LeftAlpha!=1 || RightAlpha!=1))ArmOptions.Add(A,New);else ArmOptions.Remove(A);
    if(Effective) if(const auto* Existing=Configs.Find(A))
        if(Existing->Hold==Hold && Existing->Blend==Blend && Existing->Speed==Speed && Previous.LeftHold==LeftHold && Previous.LeftBlend==LeftBlend)
        {
            if(Previous.LeftAlpha!=LeftAlpha || Previous.RightAlpha!=RightAlpha)
            { if(Active(A)) { SyncExtra(A);StartRemainingClock(A); } }
            return true;
        }
    Cancel(A);
    if(Effective) Configs.Add(A,FConfig{Hold,Blend,Speed});else Configs.Remove(A);
    if(ProphecyAttackRecovery::IsEndEvent(A)) Begin(A,ProphecyAttackRecovery::EndEventAttack(A));
    return true;
}

bool UProphecySlashReturnLibrary::SetAttackArmReturnRotationBlend(AProphecyAgent* A,float SpineLocalRotationBlend,float PelvisLocalRotationBlend)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown ||
        !FMath::IsFinite(SpineLocalRotationBlend) || !FMath::IsFinite(PelvisLocalRotationBlend)) return false;
    EnsureCleanup();RotationConfigs.Add(A,FRotationConfig{FMath::Clamp(SpineLocalRotationBlend,0.f,1.f),FMath::Clamp(PelvisLocalRotationBlend,0.f,1.f)});
    if(const auto* R=Returns.Find(A);R && !R->Initialized)
        if(const auto* Attack=ReturnAttacks.Find(A)) LatchReference(A,*Attack);
    return true;
}
bool UProphecySlashReturnLibrary::SetAttackArmReturnPelvisLocal(AProphecyAgent* A,
    bool SlashL,bool SlashR,bool SlashLD,bool SlashRD,bool SlashLU,bool SlashRU,bool Pike,
    bool JabL,bool JabR,bool HookL,bool HookR,bool OverL,bool OverR,bool Headbutt,bool KickL,bool KickR)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown) return false;
    EnsureCleanup();
    TSet<FName> Selected;
    const TCHAR* Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    const bool Choices[]={SlashL,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike,JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR};
    for(int32 I=0;I<UE_ARRAY_COUNT(Names);++I) if(Choices[I]) Selected.Add(Names[I]);
    if(Selected.IsEmpty()) PelvisChoices.Remove(A);else PelvisChoices.Add(A,MoveTemp(Selected));
    // Special Ended runs after Begin but before pose initialization. Once moving,
    // latch through the whole return to avoid reinterpreting stored transforms.
    if(const auto* R=Returns.Find(A);R && !R->Initialized)
        if(const auto* Attack=ReturnAttacks.Find(A)) LatchReference(A,*Attack);
    return true;
}
bool UProphecySlashReturnLibrary::SetAttackBothArmsReturnToNeutral(AProphecyAgent* A,
    bool SlashL,bool SlashR,bool SlashLD,bool SlashRD,bool SlashLU,bool SlashRU,bool Pike,
    bool JabL,bool JabR,bool HookL,bool HookR,bool OverL,bool OverR,bool Headbutt,bool KickL,bool KickR)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown) return false;
    EnsureCleanup();
    auto& C=BothArmsConfigs.FindOrAdd(A);C.Attacks.Reset();
    const TCHAR* Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    const bool Choices[]={SlashL,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike,JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR};
    for(int32 I=0;I<UE_ARRAY_COUNT(Names);++I) if(Choices[I]) C.Attacks.Add(Names[I]);
    const auto* Current=ReturnAttacks.Find(A);
    if(Current && !C.Attacks.Contains(*Current)) CancelExtension(A);
    if(!C.Enabled && C.Attacks.IsEmpty()) BothArmsConfigs.Remove(A);
    if(ProphecyAttackRecovery::IsEndEvent(A))
    { if(Active(A)) SyncExtra(A);else Begin(A,ProphecyAttackRecovery::EndEventAttack(A)); }
    return true;
}
bool UProphecySlashReturnLibrary::SetBothArmsReturnToNeutralEnabled(AProphecyAgent* A,bool Enabled)
{
    using namespace ProphecySlashReturn;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown) return false;
    EnsureCleanup();
    auto& C=BothArmsConfigs.FindOrAdd(A);C.Enabled=Enabled;
    if(!C.Enabled && C.Attacks.IsEmpty()) BothArmsConfigs.Remove(A);
    if(!Enabled) CancelExtension(A);
    else if(ProphecyAttackRecovery::IsEndEvent(A))
    { if(Active(A)) SyncExtra(A);else Begin(A,ProphecyAttackRecovery::EndEventAttack(A)); }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecySlashReturnArmSettingsTests.inl"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnAttackGateTest,"Prophecy.NN.SlashReturn.PerAttackGate",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyReturnAttackGateTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A || !B)return false;
    L::SetSlashRightArmReturnToNeutral(A,true,.3,.5,100);
    L::SetSlashRightArmReturnToNeutral(B,true,.3,.5,100);
    L::SetBothArmsReturnToNeutralEnabled(A,true);
    L::SetAttackBothArmsReturnToNeutral(A,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true);
    const TCHAR* Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    for(int32 I=0;I<UE_ARRAY_COUNT(Names);++I)
    {
        L::SetAttackArmReturnEnabled(A);Begin(A,Names[I]);
        TestEqual(TEXT("Checked permits configured both-arm return"),int32(ActiveArmMask(A)),3);
        L::SetAttackArmReturnEnabled(A,I!=0,I!=1,I!=2,I!=3,I!=4,I!=5,I!=6,I!=7,I!=8,I!=9,I!=10,I!=11,I!=12,I!=13,I!=14,I!=15);
        TestFalse(TEXT("Unchecking cancels both active arms"),Active(A) || ExtraReturns.Contains(A));
        Begin(A,Names[I]);TestFalse(TEXT("Unchecked attack cannot start return"),Active(A));
        Begin(A,Names[(I+1)%UE_ARRAY_COUNT(Names)]);TestTrue(TEXT("Other checked attacks remain enabled"),Active(A));
    }
    L::SetAttackArmReturnEnabled(A,false);CaptureReset(A);L::SetAttackArmReturnEnabled(A);RestoreReset(A);
    Begin(A,TEXT("slashL"));TestFalse(TEXT("Reset restores blocked attack"),Active(A));
    Begin(B,TEXT("slashL"));TestTrue(TEXT("Other agent unaffected"),Active(B));
    L::SetAttackArmReturnEnabled(A);TestFalse(TEXT("All checked removes gate storage"),BlockedAttacks.Contains(A));
    L::SetSlashRightArmReturnToNeutral(A,false);Begin(A,TEXT("slashL"));
    TestFalse(TEXT("Gate does not enable master return"),Active(A));
    Remove(A);Remove(B);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnReachAndPathTest,"Prophecy.NN.SlashReturn.ReachableIdleAndPath",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyReturnReachAndPathTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;
    const FTransform S(FVector(17,-14,5));
    FTransform NS(FVector(100,50,20)),NE(FVector(100,50,-10)),NH(FVector(110,50,-30));
    const FVector OldUpper=(NE.GetLocation()-NS.GetLocation()).GetSafeNormal();
    const FVector OldLower=(NH.GetLocation()-NE.GetLocation()).GetSafeNormal();
    const double OriginalCos=FVector::DotProduct(OldUpper,OldLower);
    FitNeutralArm(S,NS,NE,NH);
    TestTrue(TEXT("Idle is attached to actual shoulder"),NS.GetLocation().Equals(S.GetLocation(),1.e-9));
    TestTrue(TEXT("Authored upper length retained"),FMath::IsNearlyEqual(FVector::Distance(NS.GetLocation(),NE.GetLocation()),30.,1.e-9));
    TestTrue(TEXT("Authored forearm length retained"),FMath::IsNearlyEqual(FVector::Distance(NE.GetLocation(),NH.GetLocation()),FMath::Sqrt(500.),1.e-9));
    TestTrue(TEXT("Neutral bend preserved under changed origin"),FMath::IsNearlyEqual(OriginalCos,FVector::DotProduct(
        (NE.GetLocation()-NS.GetLocation()).GetSafeNormal(),(NH.GetLocation()-NE.GetLocation()).GetSafeNormal()),1.e-9));
    for(int32 I=0;I<=100;++I)
    {
        const double T=I/100.;const FVector From(80,25,-10),To(10,25,-40);
        TestTrue(TEXT("Clear front segment is exactly straight"),ClearFrontPath(From,To,17,T).Equals(FMath::Lerp(From,To,T),1.e-9));
        const FVector Mirror(1,-1,1);
        TestTrue(TEXT("Both arms share mirrored route"),ClearFrontPath(From*Mirror,To*Mirror,17,T).Equals(ClearFrontPath(From,To,17,T)*Mirror,1.e-9));
        const FVector Across=ClearFrontPath(FVector(-3,-25,-15),FVector(-3,25,-15),17,T);
        if(FMath::Abs(Across.Y)<17) TestTrue(TEXT("Blocked route still wraps in front"),Across.X>=15.3);
        const double D=45.+I*.1,Soft=SoftReturnReach(D,49.,1.);
        TestTrue(TEXT("Reach monotonic and below asymptote"),Soft<49. && Soft<=D+1.e-10);
        if(I) TestTrue(TEXT("Reach cannot reverse as target moves out"),Soft>=SoftReturnReach(D-.1,49.,1.));
        TestEqual(TEXT("Zero softness preserves original target"),SoftReturnReach(D,50.,0.),D);
    }
    constexpr double Eps=1.e-4;
    TestEqual(TEXT("Neutral boundary unchanged"),SoftReturnReach(48.,49.,1.),48.);
    TestTrue(TEXT("Matching first derivative at reach onset"),FMath::Abs((SoftReturnReach(48.+Eps,49.,1.)-48.)/Eps-1)<1.e-7);
    TestTrue(TEXT("Matching second derivative at reach onset"),FMath::Abs((SoftReturnReach(48.+Eps,49.,1.)-96.+SoftReturnReach(48.-Eps,49.,1.))/(Eps*Eps))<.001);
    for(double Z:{-51.,5.1})
    {
        const double Lo=ReturnSegmentClearance(FVector(2,2,Z-Eps),FVector(3,3,Z-Eps),17);
        const double Hi=ReturnSegmentClearance(FVector(2,2,Z+Eps),FVector(3,3,Z+Eps),17);
        TestTrue(TEXT("No clearance jump at torso height boundaries"),FMath::Abs(Hi-Lo)<1.e-7);
    }
    const FVector BackFrom(40,0,40);
    const FVector BackLo=ClearFrontPath(BackFrom,FVector(-40,Eps,40),17,.5);
    const FVector BackHi=ClearFrontPath(BackFrom,FVector(-40,-Eps,40),17,.5);
    // Both sides of a rear destination retain opposite valid front windings;
    // the direct-path weight must vanish continuously approaching that seam.
    TestTrue(TEXT("No direct chord across opposite directions"),BackLo.Size()>30 && BackHi.Size()>30);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnRotationBlendTest,"Prophecy.NN.SlashReturn.RotationBlendAndBodySeam",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyReturnRotationBlendTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    // A carrier's rear seam may lie entirely in front of the real torso.
    const FTransform ToTorso(FRotator(0,180,0),FVector::ZeroVector);
    const FVector From(-22.,.04,-43.83),To(-22.97,-3.17,-43.30);
    for(double T:{.01,.5,.896,1.})
    {
        const FVector Expected=FMath::Lerp(From,To,T);
        TestTrue(TEXT("Clear torso-front crossing ignores carrier seam"),ClearFrontPath(From,To,17,T,&ToTorso).Equals(Expected,1.e-8));
        const FTransform Shifted(FRotator(12,71,-5),FVector(7,-11,3));
        const FVector A=Shifted.InverseTransformPosition(FVector(30,-30,-15));
        const FVector B=Shifted.InverseTransformPosition(FVector(30,30,-15));
        TestTrue(TEXT("Route is independent of chosen reference coordinates"),
            Shifted.TransformPosition(ClearFrontPath(A,B,17,T,&Shifted)).Equals(
                ClearFrontPath(FVector(30,-30,-15),FVector(30,30,-15),17,T),1.e-8));
    }
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A || !B) return false;
    L::SetSlashRightArmReturnToNeutral(A,true,1,1,0);L::SetSlashRightArmReturnToNeutral(B,true,1,1,0);
    const FTransform IdleTorso(FQuat::Identity,FVector(0,0,40)),Still=FTransform::Identity;
    const FTransform Pelvis(FRotator(15,60,-10),FVector(10,20,5));
    const FQuat Root=FRotator(0,-20,0).Quaternion();
    const FTransform Torso(FRotator(20,100,0),FVector(15,22,45));
    FTransform Ref,Prev;
    for(float Alpha:{0.f,.25f,.5f,.75f,1.f})
    {
        L::SetAttackArmReturnRotationBlend(A,Alpha,1-Alpha);
        Begin(A,TEXT("pike")); // unchecked => torso-position mode
        TestFalse(TEXT("Rotation node never overrides original spine return, at any weight"),UsesControlledReference(A));
        L::SetAttackArmReturnPelvisLocal(A,false,false,false,false,false,false,true);
        Begin(A,TEXT("pike"));
        TestTrue(TEXT("Explicit pelvis-position return retains rotation control"),UsesControlledReference(A));
        PelvisReferenceFrames(A,IdleTorso,Still,Pelvis,Still,Root,FQuat::Identity,Ref,Prev);
        TestTrue(TEXT("Pelvis entry is independent"),Ref.GetRotation().Equals(FQuat::Slerp(Pelvis.GetRotation(),Root,1-Alpha),1.e-8));
        L::SetAttackArmReturnPelvisLocal(A);
    }
    Begin(B,TEXT("pike"));TestFalse(TEXT("Other agent retains original spine frame"),UsesControlledReference(B));
    L::SetAttackArmReturnRotationBlend(A,.25f,.75f);CaptureReset(A);Begin(A,TEXT("pike"));
    Returns.FindChecked(A).Initialized=true;
    L::SetAttackArmReturnRotationBlend(A,1,0);
    TestEqual(TEXT("Moving return does not change frame"),RotationReturns.FindChecked(A),.25f);
    RestoreReset(A);TestFalse(TEXT("Reset cancels live reference"),UsesControlledReference(A));
    Begin(A,TEXT("pike"));TestEqual(TEXT("Reset restores rotation controls"),RotationReturns.FindChecked(A),.25f);
    Cancel(A);TestFalse(TEXT("Cancellation clears calibration"),PelvisAxes.Contains(A)||RotationReturns.Contains(A));
    Remove(A);Remove(B);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnReferenceTest,"Prophecy.NN.SlashReturn.PelvisReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyReturnReferenceTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A || !B) return false;
    L::SetSlashRightArmReturnToNeutral(A,true,1,1,0);
    L::SetSlashRightArmReturnToNeutral(B,true,1,1,0);
    Begin(A,TEXT("pike"));TestFalse(TEXT("Default is original torso"),UsesPelvisReference(A));
    L::SetAttackArmReturnPelvisLocal(A,false,false,false,false,false,false,true);
    TestTrue(TEXT("Choice before first pose applies to current return"),UsesPelvisReference(A));
    CaptureReset(A);
    Begin(B,TEXT("pike"));TestFalse(TEXT("Choice is per agent"),UsesPelvisReference(B));
    L::SetAttackBothArmsReturnToNeutral(A,false,false,false,false,false,false,true);
    L::SetBothArmsReturnToNeutralEnabled(A,true);Begin(A,TEXT("pike"));
    TestEqual(TEXT("Both arms active"),int32(ActiveArmMask(A)),3);
    const FTransform Still=FTransform::Identity;
    const FTransform Turned(FRotator(0,45,0),FVector::ZeroVector);
    FTransform Ref,PrevRef;
    PelvisReferenceFrames(A,Still,Still,Still,Still,FQuat::Identity,FQuat::Identity,Ref,PrevRef);
    for(int32 Arm=0;Arm<2;++Arm)
    {
        const double Side=Arm==0?-1.:1.;
        const FTransform PS(FQuat::Identity,FVector(0,Side*17,0));
        const FTransform PE(FQuat::Identity,FVector(25,Side*25,-5));
        const FTransform PH(FQuat::Identity,FVector(45,Side*20,-15));
        FTransform S=PS,E=PE,H=PH;
        ApplyPose(A,Arm,1./60,Turned,Still,17,PS,PE,PH,PS,PE,PH,PH,S,E,H,FVector::UpVector,&Ref,&PrevRef);
        TestTrue(TEXT("Stationary pelvis: world wrist does not orbit rotating torso"),H.GetLocation().Equals(PH.GetLocation(),1.e-6));
        TestTrue(TEXT("Stationary pelvis: world wrist rotation retained"),H.GetRotation().Equals(PH.GetRotation(),1.e-6));
        TestFalse(TEXT("Solved arm finite"),S.ContainsNaN()||E.ContainsNaN()||H.ContainsNaN());
        if(Arm==1)
        {
            S=PS;E=PE;H=PH;
            ApplyPose(B,Arm,1./60,Turned,Still,17,PS,PE,PH,PS,PE,PH,PH,S,E,H,FVector::UpVector);
            TestTrue(TEXT("Original torso reference still carries wrist on an arc"),FVector::Distance(H.GetLocation(),PH.GetLocation())>10.);
        }
    }
    L::SetAttackArmReturnPelvisLocal(A);
    TestTrue(TEXT("Changing selection cannot jump an initialized return"),UsesPelvisReference(A));
    Begin(A,TEXT("pike"));TestFalse(TEXT("Next return uses changed selection"),UsesPelvisReference(A));
    RestoreReset(A);TestFalse(TEXT("Reset cancels reference state"),UsesPelvisReference(A));Begin(A,TEXT("pike"));
    TestTrue(TEXT("Reset restores configuration"),UsesPelvisReference(A));
    PelvisReferenceFrames(A,Still,Still,Turned,Still,FQuat::Identity,FQuat::Identity,Ref,PrevRef);
    TestTrue(TEXT("Pelvis yaw cannot rotate the return frame"),Ref.Equals(Still,1.e-8));
    const FTransform Moved(FRotator(25,70,-30),FVector(10,20,30));
    PelvisReferenceFrames(A,Still,Still,Moved,Still,Turned.GetRotation(),FQuat::Identity,Ref,PrevRef);
    TestTrue(TEXT("Reference follows pelvis position and root rotation independently"),
        Ref.Equals(FTransform(Turned.GetRotation(),Moved.GetLocation()),1.e-8));
    TestTrue(TEXT("Previous reference uses previous root"),PrevRef.Equals(Still,1.e-8));
    PelvisReferenceFrames(A,Turned,Still,Still,Still,FQuat::Identity,FQuat::Identity,Ref,PrevRef);
    TestTrue(TEXT("Neutral calibration cannot drift during return"),Ref.Equals(Still,1.e-8));
    const TCHAR* Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    for(int32 I=0;I<UE_ARRAY_COUNT(Names);++I)
    {
        L::SetAttackArmReturnPelvisLocal(A,I==0,I==1,I==2,I==3,I==4,I==5,I==6,I==7,I==8,I==9,I==10,I==11,I==12,I==13,I==14,I==15);
        TestEqual(TEXT("Node replaces all choices"),PelvisChoices.FindChecked(A).Num(),1);
        TestTrue(TEXT("Each checkbox maps correctly"),PelvisChoices.FindChecked(A).Contains(Names[I]));
    }
    Cancel(A);TestFalse(TEXT("Cancel clears all active reference state"),PelvisOffsets.Contains(A)||UsesPelvisReference(A));
    Remove(A);Remove(B);W->DestroyWorld(false);return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBothArmsReturnTest,"Prophecy.NN.SlashReturn.BothArms",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBothArmsReturnTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A || !B) return false;
    L::SetSlashRightArmReturnToNeutral(A,true,.1f,.1f,100);
    L::SetSlashRightArmReturnToNeutral(B,true,.1f,.1f,100);
    TestTrue(TEXT("Default checkbox node clears all selections"),L::SetAttackBothArmsReturnToNeutral(A));
    TestTrue(TEXT("Select slashRU"),L::SetAttackBothArmsReturnToNeutral(A,false,false,false,false,false,true));
    Begin(A,TEXT("slashRU"));TestEqual(TEXT("Master is off by default"),int32(ActiveArmMask(A)),2);
    L::SetBothArmsReturnToNeutralEnabled(A,true);
    Begin(A,TEXT("slashL"));TestEqual(TEXT("Unselected slash keeps right only"),int32(ActiveArmMask(A)),2);
    CaptureReset(A);
    for(float FPS:{30.f,60.f,120.f})
    {
        Begin(A,TEXT("slashRU"));Begin(B,TEXT("slashRU"));
        TestEqual(TEXT("Selected attack returns both"),int32(ActiveArmMask(A)),3);
        TestEqual(TEXT("Other agent unchanged"),int32(ActiveArmMask(B)),2);
        for(int32 Tick=1;Tick<=12;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            const double Dt=AdvanceFrame(A),OtherDt=AdvanceFrame(B);
            if(Tick==12) {TestEqual(TEXT("Both retire on tick12"),int32(ActiveArmMask(A)),0);break;}
            TestTrue(TEXT("One shared 60Hz clock for two arms"),FMath::IsNearlyEqual(Returns.FindChecked(A).Elapsed,Tick/60.,1.e-9));
            TestEqual(TEXT("Extra arm shares elapsed time"),ExtraReturns.FindChecked(A).Elapsed,Returns.FindChecked(A).Elapsed);
            for(int32 Arm=0;Arm<2;++Arm)
            {
                const double Side=Arm==0?-1:1;
                // Deliberately different left/right bone rotation bases.
                const FQuat Basis=FRotator(Arm==0?170:15,Arm==0?-80:30,Arm==0?45:-25).Quaternion();
                const FTransform PS(Basis,FVector(0,Side*17,0)),PE(Basis,FVector(15,Side*25,-15)),PH(Basis,FVector(10,Side*22,-35));
                FTransform Idle=PH;Idle.AddToTranslation(FVector(Arm==0?20:80,0,0));
                Idle.SetRotation((FRotator(0,35,0).Quaternion()*Basis).GetNormalized());
                FTransform S=PS,E=PE,H=PH;
                ApplyPose(A,Arm,Dt,FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,Idle,Idle,S,E,H,FVector::UpVector);
                TestFalse(TEXT("Each mirrored chain stays finite"),S.ContainsNaN()||E.ContainsNaN()||H.ContainsNaN());
                if(Arm==1)
                {
                    FTransform BS=PS,BE=PE,BH=PH;
                    ApplyPose(B,Arm,OtherDt,FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,Idle,Idle,BS,BE,BH,FVector::UpVector);
                    TestTrue(TEXT("Additional arm cannot alter original return"),BS.Equals(S,1.e-9)&&BE.Equals(E,1.e-9)&&BH.Equals(H,1.e-9));
                }
            }
            TestEqual(TEXT("Own left initial distance"),ExtraReturns.FindChecked(A).Config.Speed,20.f);
            TestEqual(TEXT("Own right initial distance"),Returns.FindChecked(A).Config.Speed,80.f);
        }
        TestFalse(TEXT("Finished extra routing removed"),ExtraReturns.Contains(A)||ExtraWeaponRoutes.Contains(A)||ExtraBlades.Contains(A));
    }
    Begin(A,TEXT("slashRU"));L::SetBothArmsReturnToNeutralEnabled(A,false);
    TestEqual(TEXT("Master off leaves original return alive"),int32(ActiveArmMask(A)),2);
    L::SetBothArmsReturnToNeutralEnabled(A,true);Begin(A,TEXT("slashRU"));
    TestEqual(TEXT("Master preserves attack choices"),int32(ActiveArmMask(A)),3);
    L::SetAttackBothArmsReturnToNeutral(A);
    TestEqual(TEXT("Per-attack off stops only extra arm"),int32(ActiveArmMask(A)),2);
    RestoreReset(A);TestFalse(TEXT("Reset cancels all motion"),Active(A));Begin(A,TEXT("slashRU"));
    TestEqual(TEXT("Reset restores selection and master"),int32(ActiveArmMask(A)),3);
    L::SetAttackBothArmsReturnToNeutral(A,false,false,false,false,false,false,false,false,false,true);Begin(A,TEXT("hookL"));
    TestEqual(TEXT("Left-primary attack supports right as extra"),ActiveArm(A),0);
    TestEqual(TEXT("Both left-primary arms active"),int32(ActiveArmMask(A)),3);
    Begin(A,TEXT("slashRU"));TestEqual(TEXT("Checkbox node replaces rather than accumulates choices"),int32(ActiveArmMask(A)),2);
    const TCHAR* AllNames[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    for(int32 I=0;I<UE_ARRAY_COUNT(AllNames);++I)
    {
        L::SetAttackBothArmsReturnToNeutral(A,I==0,I==1,I==2,I==3,I==4,I==5,I==6,I==7,I==8,I==9,I==10,I==11,I==12,I==13,I==14,I==15);
        TestEqual(TEXT("One checkbox selects exactly one attack"),BothArmsConfigs.FindChecked(A).Attacks.Num(),1);
        TestTrue(TEXT("Every checkbox maps to its own name"),BothArmsConfigs.FindChecked(A).Attacks.Contains(AllNames[I]));
        Begin(A,AllNames[I]);TestEqual(TEXT("Every selected attack can return both arms"),int32(ActiveArmMask(A)),3);
        L::SetBothArmsReturnToNeutralEnabled(A,false);
        TestEqual(TEXT("Master off restores original behavior"),int32(ActiveArmMask(A)),ArmForAttack(AllNames[I])==INDEX_NONE?0:(1<<ArmForAttack(AllNames[I])));
        L::SetBothArmsReturnToNeutralEnabled(A,true);
    }
    Cancel(A);TestEqual(TEXT("New special cancels both arms"),int32(ActiveArmMask(A)),0);
    L::SetSlashRightArmReturnToNeutral(A,false,.1f,.1f,100);Begin(A,TEXT("slashRU"));
    TestFalse(TEXT("Existing return disable remains master for whole controller"),Active(A));
    L::SetSlashRightArmReturnToNeutral(A,true,0,0,100);Begin(A,TEXT("slashRU"));
    TestFalse(TEXT("Zero durations start no additional work"),Active(A));
    Remove(A);Remove(B);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyUnarmedReturnRotationTest,"Prophecy.NN.SlashReturn.UnarmedRotation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
// Exercise the production quaternion path independently of checkpoint inference.
bool FProphecyUnarmedReturnRotationTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;
    for(double Angle:{15.,135.,179.,181.,225.,315.}) for(double Side:{-1.,1.})
    {
        const FQuat Neutral=FRotator(31,-62,18).Quaternion();
        const FQuat Start=FQuat(FVector(.2,.7,.5).GetSafeNormal(),FMath::DegreesToRadians(Angle*Side))*Neutral;
        FTransform Returning(Start,FVector(12,-20,8));
        const double Initial=Start.AngularDistance(Neutral);double Sum=0;
        FQuat Prior=Start;
        for(int32 I=0;I<100;++I)
        {
            const FQuat Current=AdvanceUnarmedRotation(Returning,Neutral,Neutral,.1,0);
            const double Step=Prior.AngularDistance(Current);Sum+=Step;
            TestTrue(TEXT("Empty wrist approaches idle monotonically"),Current.AngularDistance(Neutral)<=Prior.AngularDistance(Neutral)+1.e-7);
            TestTrue(TEXT("No forced 360-degree winding"),Sum<=Initial+1.e-6);
            TestTrue(TEXT("Angular progress bounded by chosen route progress"),Step<=.1*Prior.AngularDistance(Neutral)+1.e-6);
            TestTrue(TEXT("Rotation helper never changes wraparound position"),Returning.GetLocation()==FVector(12,-20,8));
            Prior=Current;
        }
        const FQuat NN=FRotator(-24,179,61).Quaternion();
        TestTrue(TEXT("Full transfer reaches exact NN orientation"),AdvanceUnarmedRotation(Returning,Neutral,NN,.2,1).Equals(NN,1.e-6));
        FTransform Positive(Start),Negative(Start*-1.);
        TestTrue(TEXT("Quaternion sign cannot select another winding"),
            AdvanceUnarmedRotation(Positive,Neutral,NN,.2,.4).Equals(AdvanceUnarmedRotation(Negative,Neutral*-1.,NN*-1.,.2,.4),1.e-6));
    }
    // Keep the user's long outward sword turn available; it is deliberately
    // different from a bare hand's shortest return.
    TestEqual(TEXT("Sword directed winding unchanged"),DirectedHeading(135,0,1),360.);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySlashReturnTest,"Prophecy.NN.SlashReturn.RouteAndLifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySlashReturnTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    for(const TCHAR* Name:{TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU")})
    {
        TestTrue(TEXT("All six slash names"),IsSlash(FName(Name)));
        TestEqual(TEXT("All slash directions return the sword arm"),ArmForAttack(FName(Name)),1);
    }
    for(const TCHAR* Name:{TEXT("pike"),TEXT("kickL"),TEXT("hookR"),TEXT("jabL"),TEXT("overR")})
        TestFalse(TEXT("Non-slash classification stays strict"),IsSlash(FName(Name)));
    for(const TCHAR* Name:{TEXT("jabL"),TEXT("hookL"),TEXT("overL")})
        TestEqual(TEXT("Left jab/hook/over selects left arm"),ArmForAttack(FName(Name)),0);
    for(const TCHAR* Name:{TEXT("jabR"),TEXT("hookR"),TEXT("overR"),TEXT("pike")})
        TestEqual(TEXT("Right jab/hook/over and pike select right arm"),ArmForAttack(FName(Name)),1);
    for(const TCHAR* Name:{TEXT("kickL"),TEXT("kickR"),TEXT("headbutt"),TEXT("dodge"),TEXT("parry"),TEXT("")})
        TestEqual(TEXT("Other attacks and defense have no return arm"),ArmForAttack(FName(Name)),INDEX_NONE);
    const FVector From(-3,-25,0),To(-3,25,-30);
    for(int32 I=0;I<=100;++I)
    {
        const FVector V=FrontPath(From,To,17,I/100.);
        if(FMath::Abs(V.Y)<17) TestTrue(TEXT("Cross-body route is in front, not through torso or behind it"),V.X>=15.3);
        const FVector Mirrored=FrontPath(From*FVector(1,-1,1),To*FVector(1,-1,1),17,I/100.);
        TestTrue(TEXT("Left-hand route mirrors around the front of the same torso"),Mirrored.Equals(V*FVector(1,-1,1),1.e-9));
    }
    FVector P=From;
    for(int32 I=0;I<600;++I)
    {
        const FVector Next=FrontPath(P,To,17,Advance(P,To,17,100./60,1./60));
        TestTrue(TEXT("Route respects speed bound"),(Next-P).Length()<=100./60+1.e-6);P=Next;
    }
    TestTrue(TEXT("Route reaches destination"),P.Equals(To,1.e-5));
    TestTrue(TEXT("Zero speed holds"),FrontPath(From,To,17,Advance(From,To,17,0,1./60))==From);
    TestEqual(TEXT("Left-side sketch takes clockwise long turn"),DirectedHeading(135,0,1),360.);
    TestEqual(TEXT("Right-side mirrored sketch takes opposite long turn"),DirectedHeading(-135,0,-1),-360.);
    double LongClear=1.e6,ShortClear=1.e6;
    for(int32 I=0;I<=100;++I)
    {
        const FVector Grip(-20,-25,-20);
        const double T=I/100.;
        const FVector Safe=FRotator(0,FMath::Lerp(135.,360.,T),0).Vector();
        const FVector Unsafe=FRotator(0,FMath::Lerp(135.,0.,T),0).Vector();
        LongClear=FMath::Min(LongClear,TorsoSegmentClearance(Grip,Grip+Safe*110.,17));
        ShortClear=FMath::Min(ShortClear,TorsoSegmentClearance(Grip,Grip+Unsafe*110.,17));
    }
    TestTrue(TEXT("Full blade clears on long winding while shortest rotation crosses torso"),LongClear>1 && ShortClear<1);
    {
    const FVector S(0,17,0),H(26.88,-.14,-22.35);FVector E(8.72,5.17,-20.28);
    const double Upper=(E-S).Length(),Lower=(H-E).Length();
    for(int32 I=0;I<30;++I)
    {
        const double Turn=ClearElbowAngle(S,E,H,17,1./60);
        TestTrue(TEXT("Bounded continuous elbow escape"),FMath::Abs(Turn)<=8./60+1.e-9);
        E=S+FQuat((H-S).GetSafeNormal(),Turn).RotateVector(E-S);
        TestTrue(TEXT("Avoidance keeps both lengths and fixed wrist"),FMath::IsNearlyEqual((E-S).Length(),Upper,1.e-7) && FMath::IsNearlyEqual((H-E).Length(),Lower,1.e-7));
    }
    TestTrue(TEXT("Half-slash inward elbow clears both arm segments"),
        TorsoSegmentClearance(S,E,17)>=1.02-1.e-6 && TorsoSegmentClearance(E,H,17)>=1.02-1.e-6);
    }
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A) return false;
    for(float FPS:{30.f,60.f,120.f})
    {
        TestTrue(TEXT("Configure"),L::SetSlashRightArmReturnToNeutral(A,true,.5,1,100));CaptureReset(A);
        Begin(A,TEXT("kickL"));TestFalse(TEXT("Kick never starts"),Active(A));
        Begin(A,TEXT("slashL"));TestTrue(TEXT("Slash starts"),Active(A));
        FTransform S(FVector(0,17,0)),E(FVector(15,25,-15)),H(FVector(10,22,-35));
        const FTransform PS=S,PE=E,PH=H;
        for(int32 Tick=1;Tick<=90;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            ApplyPose(A,ActiveArm(A),AdvanceFrame(A),FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,PH,PH,S,E,H,FVector::UpVector);
            if(Tick==30) TestTrue(TEXT("Hold consumes precisely 30 ticks"),Active(A) && FMath::IsNearlyEqual(Returns.FindChecked(A).Elapsed,.5,1.e-6));
            TestFalse(TEXT("Finite valid pose"),S.ContainsNaN() || E.ContainsNaN() || H.ContainsNaN());
        }
        TestFalse(TEXT("90 ticks retire regardless of FPS"),Active(A));
        Begin(A,TEXT("slashRU"));Cancel(A);TestFalse(TEXT("New special cancels"),Active(A));
        L::SetSlashRightArmReturnToNeutral(A,false,0,0,0);RestoreReset(A);Begin(A,TEXT("slashLD"));
        TestTrue(TEXT("Reset restores saved config"),Active(A));
        RestoreReset(A);TestFalse(TEXT("Reset cancels active return"),Active(A));
        L::SetSlashRightArmReturnToNeutral(A,true,0,0,100);Begin(A,TEXT("slashR"));
        TestFalse(TEXT("Zero times retain no active work"),Active(A));
        L::SetSlashRightArmReturnToNeutral(A,true,.25f,0,100);Begin(A,TEXT("slashR"));
        for(int32 Tick=1;Tick<=15;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            ApplyPose(A,ActiveArm(A),AdvanceFrame(A),FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,PH,PH,S,E,H,FVector::UpVector);
            TestTrue(TEXT("Hold-only arm return retains ownership until tick15 then retires"),Active(A)==(Tick<15));
        }
    }
    {
        const FTransform PS(FVector(0,17,0)),PE(FVector(15,25,-15)),PH(FVector(10,22,-35));
        auto ApplyAt=[&](double Distance)
        {
            FTransform S=PS,E=PE,H=PH,Idle=PH;Idle.AddToTranslation(FVector(Distance,0,0));
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);
            ApplyPose(A,ActiveArm(A),AdvanceFrame(A),FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,Idle,Idle,S,E,H,FVector::UpVector);
        };
        L::SetSlashRightArmReturnToNeutral(A,true,.5,1,300);
        Begin(A,TEXT("slashR"));ApplyAt(20);
        TestEqual(TEXT("20cm initial distance scales reference speed300 to60"),Returns.FindChecked(A).Config.Speed,60.f);
        ApplyAt(80);
        TestEqual(TEXT("Later target distance does not change captured speed"),Returns.FindChecked(A).Config.Speed,60.f);
        TestEqual(TEXT("Configured speed is never scaled in place"),Configs.FindChecked(A).Speed,300.f);
        Begin(A,TEXT("slashL"));ApplyAt(80);
        TestEqual(TEXT("Next return captures its own80cm distance"),Returns.FindChecked(A).Config.Speed,240.f);
        Begin(A,TEXT("slashRU"));ApplyAt(0);ApplyAt(80);
        TestEqual(TEXT("Initially idle retains zero positional speed even if goal later moves"),Returns.FindChecked(A).Config.Speed,0.f);
    }
    for(float FPS:{30.f,60.f,120.f}) for(const TCHAR* Name:{TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("pike")})
    {
        const int32 Arm=ArmForAttack(FName(Name));const double Side=Arm==0?-1.:1.;
        L::SetSlashRightArmReturnToNeutral(A,true,.1f,.1f,100);
        Begin(A,FName(Name));TestEqual(TEXT("Eligible return latches the proper hand"),ActiveArm(A),Arm);
        const FTransform PS(FVector(0,Side*17,0)),PE(FVector(15,Side*25,-15)),PH(FVector(10,Side*22,-35));
        FTransform Idle=PH;Idle.AddToTranslation(FVector(20,0,0));
        for(int32 Tick=1;Tick<=12;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            FTransform S=PS,E=PE,H=PH;
            ApplyPose(A,ActiveArm(A),AdvanceFrame(A),FTransform::Identity,FTransform::Identity,17,PS,PE,PH,PS,PE,Idle,Idle,S,E,H,FVector::UpVector);
            TestFalse(TEXT("Both-handed returns have finite connected targets"),S.ContainsNaN()||E.ContainsNaN()||H.ContainsNaN());
            if(Tick<12)TestEqual(TEXT("Arm selection survives the hold and blend"),ActiveArm(A),Arm);
        }
        TestFalse(TEXT("Eligible return retires after 12 ticks at every FPS"),Active(A));
        TestFalse(TEXT("No arm-selection sidecar remains after retirement"),ReturnArms.Contains(A));
        Begin(A,FName(Name));Cancel(A);TestEqual(TEXT("New special cancels either arm"),ActiveArm(A),INDEX_NONE);
        L::SetSlashRightArmReturnToNeutral(A,false,.1f,.1f,100);Begin(A,FName(Name));
        TestFalse(TEXT("Disabled eligible return performs no work"),Active(A));
    }
    AddInfo(TEXT("AttackArmReturn: six sword-arm slashes, pike, six sided jab/hook/over returns, front-route mirror and 12-tick retirement at 30/60/120 FPS verified."));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
