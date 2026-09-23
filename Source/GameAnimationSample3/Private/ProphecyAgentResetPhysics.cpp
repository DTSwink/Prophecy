#include "ProphecyAgentResetPhysics.h"
#include "ProphecyAgent.h"
#include "ProphecyPhysicalProfileLibrary.h"
#include "ProphecyPhysicalContext.h"
#include "ProphecyJointDampingPolicy.h"
#include "ProphecyAngularLimitBlend.h"
#include "ProphecyAngularLimits.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyLowerTemperingLibrary.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyCoreTempering.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecySlashReturn.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "ProphecyRootBalance.h"
#include "ProphecyKickFootLeeway.h"
#include "ProphecyClampProfiles.h"
#include "ProphecyJoltCharacterComponent.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "ProphecyResetHitAudit.inl"

namespace ProphecyAgentResetPhysics
{
struct FState
{
    FName Profile;
    TMap<FName,FProphecyBodyMagnetizationSettings> Bodies;
    bool Enabled=true;
    float Linear=1,Angular=1;
    ProphecyLowerTempering::FSettings Tempering;
    TWeakObjectPtr<UPhysicalMaterial> Material;
    bool HadMaterial=false;
    TWeakObjectPtr<UPhysicsAsset> Asset;
    TArray<FConstraintProfileProperties> Limits;
};
// Separate storage avoids resizing already-live manager/checkpoint allocations.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static TMap<TWeakObjectPtr<const AProphecyAgent>,ProphecyLowerTempering::FSettings> RightTemperingStates;
// Keep equipment separate: do not resize physics snapshots retained by Live Coding.
struct FEquipmentState
{
    bool HadSword=false;
    bool Simulated=false;
    TWeakObjectPtr<AActor> Sword;
    TSoftClassPtr<AActor> SwordClass;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FEquipmentState> EquipmentStates;
bool Has(const AProphecyAgent* Agent) { return States.Contains(Agent); }
void Remove(const AProphecyAgent* Agent)
{
    if (auto* S=States.Find(Agent)) ProphecyPhysicalContext::DeleteSnapshot(Agent,S->Profile);
    States.Remove(Agent);RightTemperingStates.Remove(Agent);
    EquipmentStates.Remove(Agent);
    ProphecyHandRecovery::ForgetReset(Agent);
    ProphecyCoreTempering::ForgetReset(Agent);
    ProphecyUpperBodyInertia::ForgetReset(Agent);
    ProphecySlashReturn::ForgetReset(Agent);
}
bool Capture(AProphecyAgent* Agent,FString& Error)
{
    Error.Reset();
    if (!IsValid(Agent)) return false;
    if (States.Contains(Agent)) return true;
    FState S;
    S.Profile=FName(*FString::Printf(TEXT("AgentReset_%s"),*FGuid::NewGuid().ToString()));
    if (!UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot(Agent,S.Profile))
    { Error=TEXT("Could not capture initial physical profiles.");return false; }
    S.Bodies=Agent->BodyMagnetizationSettings;
    S.Enabled=Agent->bWorldMagnetizationEnabled;
    S.Linear=Agent->WorldMagnetizationLinearStrengthScale;S.Angular=Agent->WorldMagnetizationAngularStrengthScale;
    if (const auto* T=ProphecyLowerTempering::Find(Agent))
    { S.Tempering=*T;RightTemperingStates.Add(Agent,ProphecyLowerTempering::RightFootSettings(Agent,*T)); }
    if (auto* Mesh=Agent->GetPoseReferenceMesh())
    {
        S.Material=Mesh->BodyInstance.GetPhysMaterialOverride();S.HadMaterial=S.Material.IsValid();
        S.Asset=Mesh->GetPhysicsAsset();
        for (const auto* Joint:Mesh->Constraints)
        {
            if (!Joint) { ProphecyPhysicalContext::DeleteSnapshot(Agent,S.Profile);Error=TEXT("Missing initial PHAT joint.");return false; }
            S.Limits.Add(Joint->ProfileInstance);
        }
    }
    FEquipmentState Equipment;
    Equipment.Sword=Agent->GetHeldSword();
    Equipment.HadSword=Equipment.Sword.IsValid();
    Equipment.Simulated=Agent->IsSwordSimulated();
    if (Equipment.HadSword) Equipment.SwordClass=Equipment.Sword->GetClass();
    EquipmentStates.Add(Agent,MoveTemp(Equipment));
    ProphecyHandRecovery::CaptureReset(Agent);
    ProphecyCoreTempering::CaptureReset(Agent);
    ProphecyUpperBodyInertia::CaptureReset(Agent);
    ProphecySlashReturn::CaptureReset(Agent);
    States.Add(Agent,MoveTemp(S));return true;
}
bool RestoreEquipment(AProphecyAgent* Agent,FString& Error)
{
    Error.Reset();
    const auto* Saved=EquipmentStates.Find(Agent);
    if (!Saved)
    { Error=TEXT("Equipment baseline missing: start a new Play session and initialize reset after equipping.");return false; }
    const FEquipmentState Baseline=*Saved;
    // Despawn through the controller to release its grip/body and pending binds.
    // A dropped copy no longer belongs to the controller; retire that copy too.
    Agent->HideSword();
    if (Baseline.Sword.IsValid()) Baseline.Sword->Destroy();
    if (!Baseline.HadSword) return true;
    const auto ConfiguredClass=Agent->SwordBlueprint;
    Agent->SwordBlueprint=Baseline.SwordClass;
    const bool Equipped=Agent->EquipSword(Baseline.Simulated);
    Agent->SwordBlueprint=ConfiguredClass;
    if (auto* Current=EquipmentStates.Find(Agent)) Current->Sword=Agent->GetHeldSword();
    if (!Equipped) Error=TEXT("Could not restore the captured held sword.");
    return Equipped;
}
void CancelBlends(AProphecyAgent* Agent)
{
    ProphecyKickFootLeeway::Cancel(Agent);
    ProphecyClampProfiles::Cancel(Agent);
    using namespace ProphecyPhysicalContext;
    for (EKind Kind:{EKind::Magnetization,EKind::Feedback,EKind::Damping}) Discard(Agent,Kind);
    Agent->CancelBodyMagnetizationBlend();Agent->CancelPhysicalFeedbackToleranceBlend();
    ProphecyAngularLimitBlend::Cancel(Agent);
    ProphecyAttackRecovery::Cancel(Agent);
    ProphecyHandRecovery::CancelMotion(Agent);
    ProphecyCoreTempering::CancelMotion(Agent);
    ProphecyUpperBodyInertia::Cancel(Agent);
    ProphecySlashReturn::Cancel(Agent);
    ProphecyRootBalance::CancelKickException(Agent);
    ProphecyLowerTempering::ClearAttackSelection(Agent);
    ProphecyLowerTempering::Remove(Agent);
    ProphecyBlendClock::Remove(Agent);
}
bool Restore(AProphecyAgent* Agent,FString& Error)
{
    Error.Reset();const auto* Found=States.Find(Agent);
    if (!Found) { Error=TEXT("Physics reset baseline is missing; start a new Play session and initialize after delayed BeginPlay setup.");return false; }
    const FState S=*Found;
    CancelBlends(Agent);
    ProphecyJointDamping::Remove(Agent); // Discard cached death damping before the replacement rig is admitted.
    Agent->BodyMagnetizationSettings=S.Bodies;
    Agent->bWorldMagnetizationEnabled=S.Enabled;
    Agent->WorldMagnetizationLinearStrengthScale=S.Linear;Agent->WorldMagnetizationAngularStrengthScale=S.Angular;
    if (!ProphecyPhysicalContext::RestoreResetSnapshot(Agent,S.Profile))
    { Error=TEXT("Initial physical profile snapshot is unavailable.");return false; }
    // Profile restore materializes defaults for every PHAT bone. Retain the
    // original sparse map: Jolt/HalfSim deliberately drive missing entries with
    // native defaults, whereas the legacy Sim membership query requires an entry.
    // Converting absence into bSimulateBody=false disables those Jolt drives.
    for (auto It=Agent->BodyMagnetizationSettings.CreateIterator();It;++It)
        if (!S.Bodies.Contains(It.Key())) It.RemoveCurrent();
    const auto& T=S.Tempering;
    UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(Agent,true,T.FeetTranslation,T.FeetTranslationZ,T.FeetRotation,T.PelvisTranslation,T.PelvisTranslationZ,T.PelvisRotation);
    if (const auto* Right=RightTemperingStates.Find(Agent)) ProphecyLowerTempering::RestoreRightFootSettings(Agent,*Right);
    ProphecyHandRecovery::RestoreReset(Agent);
    ProphecyCoreTempering::RestoreReset(Agent);
    ProphecyUpperBodyInertia::RestoreReset(Agent);
    ProphecySlashReturn::RestoreReset(Agent);
    if (S.HadMaterial && !S.Material.IsValid()) { Error=TEXT("Initial physical material no longer exists.");return false; }
    if (auto* Mesh=Agent->GetPoseReferenceMesh()) Mesh->SetPhysMaterialOverride(S.Material.Get());
    return RestoreLimits(Agent,Error);
}
bool RestoreLimits(AProphecyAgent* Agent,FString& Error)
{
    const auto* S=States.Find(Agent);if (!S) return false;
    if (S->Limits.IsEmpty()) return true;
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Mesh || Mesh->GetPhysicsAsset()!=S->Asset.Get() || Mesh->Constraints.Num()!=S->Limits.Num())
    { Error=TEXT("The reset PHAT joint layout changed.");return false; }
    TArray<FConstraintProfileProperties> Profiles;
    for (int32 I=0;I<S->Limits.Num();++I)
    {
        if (!Mesh->Constraints[I]) { Error=TEXT("Missing reset PHAT joint.");return false; }
        Profiles.Add(Mesh->Constraints[I]->ProfileInstance);
        ProphecyAngularLimits::Copy(Profiles.Last(),S->Limits[I]);
    }
    if (Agent->IsJoltPhysicalAnimationEnabled())
        return Agent->GetJoltCharacterComponent()->ApplyAngularLimitProfiles(Profiles,Error);
    for (int32 I=0;I<Profiles.Num();++I) ProphecyAngularLimits::Apply(*Mesh->Constraints[I],Profiles[I]);
    return true;
}
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyResetPhysicsTest,"Prophecy.NN.AgentReset.PhysicalBaseline",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyResetPhysicsTest::RunTest(const FString&)
{
    using namespace ProphecyAgentResetPhysics;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if (!TestNotNull(TEXT("World"),World)) return false;
    if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    AProphecyAgent* Agent=nullptr;
    ON_SCOPE_EXIT
    {
        Remove(Agent);ProphecyPhysicalContext::Remove(Agent);ProphecyJointDamping::Remove(Agent);
        ProphecyLowerTempering::Remove(Agent);ProphecyBlendClock::Remove(Agent);
        World->DestroyWorld(false);if (GEngine) GEngine->DestroyWorldContext(World);
    };
    Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Agent"),Agent)) return false;
    Agent->bAutoEnsureStandaloneNNManager=false;
    auto* Asset=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Skeleton"),Asset)) return false;
    Agent->GetAgentMesh()->SetSkeletalMeshAsset(Asset);
    Agent->BodyMagnetizationSettings.Remove(TEXT("foot_l"));
    Agent->BodyMagnetizationSettings.Remove(TEXT("upperarm_l"));
    Agent->BodyMagnetizationSettings.FindOrAdd(TEXT("hand_r")).bSimulateBody=false;
    Agent->SetBodyMagnetization(TEXT("head"),true,.25f,.5f);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),12,24);
    TestTrue(TEXT("Stage baseline damping"),ProphecyJointDamping::ApplyValue(Agent,TEXT("head"),37));
    UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(Agent,true,.3f,.7f,.4f,.5f,.8f,.6f);
    ProphecyLowerTempering::RestoreRightFootSettings(Agent,{.9f,.8f,1,1,.2f,1});
    FString Error;
    if (!TestTrue(TEXT("Capture baseline"),Capture(Agent,Error))) { AddError(Error);return false; }
    for (int32 Repeat=0;Repeat<2;++Repeat)
    {
        Agent->bWorldMagnetizationEnabled=false;
        Agent->WorldMagnetizationLinearStrengthScale=9;
        Agent->SetBodyMagnetization(TEXT("head"),false,8,9);
        Agent->SetPhysicalFeedbackTolerance(TEXT("head"),99,88);
        ProphecyJointDamping::ApplyValue(Agent,TEXT("head"),400);
        Agent->BlendBodyMagnetization(TEXT("head"),7,6,1);
        Agent->BlendPhysicalFeedbackTolerance(TEXT("head"),50,60,1);
        UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,0,1,0);
        TestTrue(TEXT("Restore physics"),Restore(Agent,Error));
        if (!Error.IsEmpty()) AddError(Error);
        for (int32 Tick=0;Tick<90;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120.f);
            ProphecyPhysicalContext::Update(Agent);
            ProphecyLowerTempering::Find(Agent);
        }
        FProphecyBodyMagnetizationSettings M;Agent->GetBodyMagnetizationSettings(TEXT("head"),M);
        TestTrue(TEXT("Magnetization gate restored"),M.bMagnetizationEnabled && Agent->bWorldMagnetizationEnabled);
        TestEqual(TEXT("Global strength restored"),Agent->WorldMagnetizationLinearStrengthScale,1.f);
        TestEqual(TEXT("Linear magnetization survives old blend endpoint"),M.LinearStrengthScale,.25f);
        TestEqual(TEXT("Angular magnetization restored"),M.AngularStrengthScale,.5f);
        FProphecyPhysicalFeedbackToleranceSettings F;Agent->GetPhysicalFeedbackTolerance(TEXT("head"),F);
        TestEqual(TEXT("Linear tolerance survives old blend endpoint"),F.LinearToleranceCm,12.f);
        TestEqual(TEXT("Angular tolerance restored"),F.AngularToleranceDegrees,24.f);
        float D=0;ProphecyJointDamping::Get(Agent,TEXT("head"),D);
        TestEqual(TEXT("Damping restored while rig is detached"),D,37.f);
        const auto* T=ProphecyLowerTempering::Find(Agent);
        TestTrue(TEXT("Tempering return cancelled, XY/Z restored"),T && T->FeetTranslation==.3f && T->PelvisRotation==.6f
            && T->FeetTranslationZ==.7f && T->PelvisTranslationZ==.8f);
        if (T)
        {
            const auto& R=ProphecyLowerTempering::RightFootSettings(Agent,*T);
            TestTrue(TEXT("Reset restores asymmetric right foot and cancels its blend"),R.FeetTranslation==.9f && R.FeetTranslationZ==.2f && R.FeetRotation==.8f);
        }
        TestFalse(TEXT("Missing baseline entry remains absent"),Agent->GetBodyMagnetizationSettings(TEXT("foot_l"),M));
        TestTrue(TEXT("Missing entry retains native Jolt drive defaults"),M.bSimulateBody && M.bMagnetizationEnabled);
        TestFalse(TEXT("Upper arm absent at capture remains absent"),Agent->GetBodyMagnetizationSettings(TEXT("upperarm_l"),M));
        TestTrue(TEXT("Upper arm keeps default magnetization"),M.bSimulateBody && M.bMagnetizationEnabled && M.LinearStrengthScale==1 && M.AngularStrengthScale==1);
        TestTrue(TEXT("Explicitly excluded body remains configured"),Agent->GetBodyMagnetizationSettings(TEXT("hand_r"),M));
        TestFalse(TEXT("Explicit exclusion is still disabled"),M.bSimulateBody);
    }
    return true;
}
#endif
