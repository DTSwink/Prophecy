#include "ProphecyAttackCamera.h"
#include "ProphecyAttackControlLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNDefenseLibrary.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ProphecyJoltCharacterComponent.h"

namespace ProphecyAttackCameraFade
{
struct FReturn
{
	FVector StartOffset=FVector::ZeroVector;
	FVector PendingSpringOrigin=FVector::ZeroVector;
	bool bPendingSnap=false;
	uint64 TotalTicks=0,ElapsedTicks=0,LastFrame=MAX_uint64;
	void Begin(const FVector& Offset,float Seconds)
	{
		StartOffset=Offset;ElapsedTicks=0;LastFrame=MAX_uint64;
		TotalTicks=Seconds>0.f ? uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Seconds)*60.,9.e15)-1.e-5))) : 0;
	}
	FVector Value() const
	{
		if (!TotalTicks || ElapsedTicks>=TotalTicks) return FVector::ZeroVector;
		const double Alpha=double(ElapsedTicks)/double(TotalTicks);
		return StartOffset*(1.-Alpha*Alpha*(3.-2.*Alpha));
	}
	void Advance(uint64 Frame,bool UnpausedGameTick)
	{
		if (!UnpausedGameTick || LastFrame==Frame) return;
		LastFrame=Frame;if (ElapsedTicks<TotalTicks) ++ElapsedTicks;
	}
};
// Sidecar storage avoids changing live component layouts. Only the possessed
// camera creates a return; default duration requires no per-agent entry.
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Durations;
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> ComAlphas;
static TMap<TWeakObjectPtr<const UProphecyAttackCameraComponent>,FReturn> Returns;
static FDelegateHandle Cleanup;
static bool IsPossessedPlayer(const AProphecyAgent* Pawn)
{
	const auto* Controller=Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	return Controller && Controller->GetPawn()==Pawn;
}
static float Duration(const AProphecyAgent* Pawn)
{
	const float* Override=Durations.IsEmpty() ? nullptr : Durations.Find(Pawn);
	return Override ? *Override : 1.f;
}
static void RefreshCleanup()
{
	if (Durations.IsEmpty() && ComAlphas.IsEmpty())
	{
		FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();
	}
	else if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
	{
		for (auto It=Durations.CreateIterator();It;++It)
			if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
		for (auto It=ComAlphas.CreateIterator();It;++It)
			if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
		RefreshCleanup();
	});
}
}

bool UProphecyAttackControlLibrary::SetAttackCameraCOMFollow(AProphecyAgent* Agent,float Alpha)
{
	using namespace ProphecyAttackCameraFade;
	if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !FMath::IsFinite(Alpha)) return false;
	Alpha=FMath::Clamp(Alpha,0.f,1.f);
	if (Alpha==0.f) ComAlphas.Remove(Agent);else ComAlphas.Add(Agent,Alpha);
	RefreshCleanup();return true;
}

bool UProphecyAttackControlLibrary::SetAttackCameraOffsetFadeDuration(AProphecyAgent* Agent,float DurationSeconds)
{
	using namespace ProphecyAttackCameraFade;
	if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
		|| !FMath::IsFinite(DurationSeconds) || DurationSeconds<0.f) return false;
	if (DurationSeconds==1.f) Durations.Remove(Agent);else Durations.Add(Agent,DurationSeconds);
	RefreshCleanup();
	if (auto* Follow=Agent->FindComponentByClass<UProphecyAttackCameraComponent>())
		if (FReturn* Fade=Returns.Find(Follow))
		{
			if (DurationSeconds==0.f) Follow->Stop();
			else Fade->Begin(Fade->Value(),DurationSeconds);
		}
	return true;
}

UProphecyAttackCameraComponent::UProphecyAttackCameraComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
	PrimaryComponentTick.EndTickGroup = TG_PostPhysics;
}

void UProphecyAttackCameraComponent::SetMesh(USkeletalMeshComponent* NewMesh)
{
	if (Mesh.Get() == NewMesh) return;
	if (Mesh.IsValid()) RemoveTickPrerequisiteComponent(Mesh.Get());
	Mesh = NewMesh;
	BoneMasses.Reset();bTrackingCom=false;
	if (NewMesh) AddTickPrerequisiteComponent(NewMesh);
}

FVector UProphecyAttackCameraComponent::ReadCenterOfMass(bool bRebuild)
{
	if (bRebuild)
	{
		BoneMasses.Reset();
		if (const UPhysicsAsset* Asset=Mesh->GetPhysicsAsset())
			for (const USkeletalBodySetup* Setup:Asset->SkeletalBodySetups)
			{
				if (!Setup) continue;
				const int32 Index=Mesh->GetBoneIndex(Setup->BoneName);
				const FBodyInstance* Body=Mesh->GetBodyInstance(Setup->BoneName);
				if (Index==INDEX_NONE || !Body || !Body->IsValidBodyInstance()) continue;
				double Mass=0.;
				if (Agent->IsJoltPhysicalAnimationEnabled())
					Mass=Agent->GetJoltCharacterComponent()->GetCapturedBodyMassKg(Setup->BoneName);
				if (Mass<=0.) Mass=Body->GetBodyMass();
				const FVector LocalCenter=Body->GetMassSpaceLocal().GetLocation();
				if (Mass>0. && FMath::IsFinite(Mass) && !LocalCenter.ContainsNaN())
					BoneMasses.Add({Index,Mass,LocalCenter});
			}
	}
	// Sample the displayed skeleton after physics, using cached body masses and
	// local mass centers. Works for physical and kinematic presentation alike.
	FVector Weighted=FVector::ZeroVector;double Total=0.;
	for (const auto& Body:BoneMasses)
	{
		Weighted+=Mesh->GetBoneTransform(Body.Index).TransformPosition(Body.LocalCenter)*Body.Mass;
		Total+=Body.Mass;
	}
	return Total>0. ? Weighted/Total : Mesh->GetSocketLocation(TEXT("pelvis"));
}

void UProphecyAttackCameraComponent::Follow(AActor* InManager, AProphecyAgent* InAgent)
{
	if (!ProphecyAttackCameraFade::IsPossessedPlayer(InAgent)) return;
	if (bFollowing)
	{
		SetMesh(InAgent->GetPoseReferenceMesh());
		return;
	}
	Manager = InManager; Agent = InAgent; Spring = InAgent->GetAgentSpringArm();
	SetMesh(InAgent->GetPoseReferenceMesh());
	AddTickPrerequisiteActor(InManager);
	AddTickPrerequisiteActor(InAgent);
	Spring->AddTickPrerequisiteComponent(this);
	bFollowing = true;
	SetComponentTickEnabled(true);
}

void UProphecyAttackCameraComponent::Restore()
{
	if (Spring.IsValid()) Spring->TargetOffset -= AppliedOffset;
	AppliedOffset = FVector::ZeroVector;
}

void UProphecyAttackCameraComponent::CompensateRootSnap(const FVector& PreviousSpringOrigin)
{
	using namespace ProphecyAttackCameraFade;
	if (!bFollowing || !IsPossessedPlayer(Agent.Get()) || !Spring.IsValid()) return;
	const float Seconds=Duration(Agent.Get());
	if (Seconds<=0.f) { Stop();return; }
	// TargetOffset is world-space. Measure the real spring origin before/after
	// BOTH attack carrier moves, so blocked catch-up and the balancing/pelvis
	// destination contribute their applied displacement exactly once.
	const FReturn* Pending=Returns.Find(this);
	const FVector Delta=Spring->GetComponentLocation()-
		(Pending && Pending->bPendingSnap ? Pending->PendingSpringOrigin : PreviousSpringOrigin);
	if (Delta.ContainsNaN() || (Delta.IsNearlyZero() && !bTrackingCom)) return;
	bTrackingCom=false;
	Spring->TargetOffset-=Delta;
	AppliedOffset-=Delta;
	auto& Fade=Returns.FindOrAdd(this);
	Fade.Begin(AppliedOffset,Seconds);
	// Root balancing, physics and Blueprint can still move the capsule later
	// this frame. Finish compensation in PostPhysics before the spring ticks.
	Fade.PendingSpringOrigin=Spring->GetComponentLocation();
	Fade.bPendingSnap=true;
	// Keep the pivot exact on the snap frame; start fading on the next game tick.
	Fade.LastFrame=GFrameCounter;
}

void UProphecyAttackCameraComponent::ReleasePrerequisites()
{
	if (Spring.IsValid()) Spring->RemoveTickPrerequisiteComponent(this);
	if (Manager.IsValid()) RemoveTickPrerequisiteActor(Manager.Get());
	if (Agent.IsValid()) RemoveTickPrerequisiteActor(Agent.Get());
	SetMesh(nullptr);
}

void UProphecyAttackCameraComponent::Stop()
{
	ProphecyAttackCameraFade::Returns.Remove(this);
	Restore();
	bFollowing = false;
	bTrackingPelvis = false;
	bTrackingCom = false;
	SetComponentTickEnabled(false);
	ReleasePrerequisites();
}

void UProphecyAttackCameraComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	AProphecyAgent* Pawn = Agent.Get();
	const auto* OwnerManager = Cast<AProphecyNNLocomotionManager>(Manager.Get());
	if (!bFollowing || !OwnerManager || !ProphecyAttackCameraFade::IsPossessedPlayer(Pawn) || !Spring.IsValid() || !Mesh.IsValid())
	{
		Stop();
		return;
	}
	if (auto* Fade=ProphecyAttackCameraFade::Returns.Find(this); Fade && Fade->bPendingSnap)
	{
		const FVector LateDelta=Spring->GetComponentLocation()-Fade->PendingSpringOrigin;
		if (!LateDelta.ContainsNaN())
		{
			Spring->TargetOffset-=LateDelta;
			AppliedOffset-=LateDelta;
			Fade->StartOffset-=LateDelta;
		}
		Fade->bPendingSnap=false;
		Fade->LastFrame=GFrameCounter;
	}
	const auto Activity=Pawn && OwnerManager ? OwnerManager->GetAgentActivityState(Pawn->GetAgentHandle()) : EProphecyAgentState::Locomotion;
	using namespace ProphecyAttackCameraFade;
	const float* ComAlpha=ComAlphas.IsEmpty() ? nullptr : ComAlphas.Find(Pawn);
	FName Attack;bool bHalf=false,bArmed=false,bHit=false;int32 Frame=0;
	const bool bComAttack=ComAlpha && *ComAlpha>0.f &&
		OwnerManager->GetAgentNNAttackState(Pawn->GetAgentHandle(),Attack,bHalf,bArmed,bHit,Frame) && !bHalf;
	if (bComAttack)
	{
		const FVector CenterFromRoot=ReadCenterOfMass(!bTrackingCom)-Pawn->GetActorLocation();
		if (!bTrackingCom)
		{
			InitialComFromRoot=CenterFromRoot;bTrackingCom=true;
			// A defense may have left a follow offset rather than an active fade.
			if (!Returns.Contains(this) && !AppliedOffset.IsNearlyZero()) Returns.Add(this).Begin(AppliedOffset,Duration(Pawn));
		}
		bTrackingPelvis=false;
		FVector Offset=(CenterFromRoot-InitialComFromRoot)*(*ComAlpha);Offset.Z=0.;
		if (FReturn* Fade=Returns.Find(this))
		{
			Fade->Advance(GFrameCounter,TickType==LEVELTICK_All && GetWorld() && !GetWorld()->IsPaused());
			Offset+=Fade->Value();
			if (Fade->ElapsedTicks>=Fade->TotalTicks) Returns.Remove(this);
		}
		Spring->TargetOffset+=Offset-AppliedOffset;AppliedOffset=Offset;
		return;
	}
	if (bTrackingCom)
	{
		bTrackingCom=false;
		// Also handles disabling COM follow during an attack and exits without a root snap.
		Returns.FindOrAdd(this).Begin(AppliedOffset,Duration(Pawn));
	}
	if (Activity!=EProphecyAgentState::Parrying && Activity!=EProphecyAgentState::Dodging)
	{
		bTrackingPelvis=false;
		using namespace ProphecyAttackCameraFade;
		FReturn* Fade=Returns.Find(this);
		if (!Fade)
		{
			const float Seconds=Duration(Pawn);
			if (Seconds<=0.f || AppliedOffset.IsNearlyZero())
			{
				// Attacks stay on the capsule. Keep the component ready for the
				// eventual root snap, without reading any animated bone location.
				if (Activity!=EProphecyAgentState::Attacking) Stop();
				return;
			}
			Fade=&Returns.Add(this);Fade->Begin(AppliedOffset,Seconds);
		}
		// Count completed game ticks, never DeltaTime or NN/policy steps.
		Fade->Advance(GFrameCounter,TickType==LEVELTICK_All && GetWorld() && !GetWorld()->IsPaused());
		if (Fade->ElapsedTicks>=Fade->TotalTicks)
		{
			Returns.Remove(this);Restore();
			// An attack may end from Blueprint before the next manager update.
			// Keep snap compensation ready if it outlasted the previous fade.
			if (Activity!=EProphecyAgentState::Attacking) Stop();
			return;
		}
		const FVector Offset=Fade->Value();
		Spring->TargetOffset+=Offset-AppliedOffset;AppliedOffset=Offset;
		return;
	}
	if (!bTrackingPelvis)
	{
		// Preserve the existing defense camera. Attacks never enter this branch.
		InitialPelvisFromRoot=Mesh->GetSocketLocation(TEXT("pelvis"))-Pawn->GetActorLocation()-AppliedOffset;
		ProphecyAttackCameraFade::Returns.Remove(this);
		bTrackingPelvis=true;
	}
	// Jolt publishes before physics completes; the mesh prerequisite also waits
	// for skeletal evaluation. Read the actual displayed body in either backend.
	FVector Offset = Mesh->GetSocketLocation(TEXT("pelvis")) - Pawn->GetActorLocation() - InitialPelvisFromRoot;
	Offset.Z = 0; // Follow defense travel without adding pelvis bob to the camera.
	Spring->TargetOffset += Offset - AppliedOffset;
	AppliedOffset = Offset;
}

void UProphecyAttackCameraComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	Stop();
	Super::EndPlay(Reason);
}

void UProphecyAttackCameraComponent::OnUnregister()
{
	Stop();
	Super::OnUnregister();
}

namespace ProphecyAttackCamera
{
	void RefreshPlayerRig(AProphecyAgent* Agent)
	{
		if (!IsValid(Agent) || !Agent->GetWorld() || !Agent->GetWorld()->IsGameWorld()) return;
		auto* Spring=Agent->GetAgentSpringArm();auto* Camera=Agent->GetAgentCamera();
		if (!Spring || !Camera) return;
		if (Cast<APlayerController>(Agent->GetController()))
		{
			if (Spring->GetAttachParent()!=Agent->GetAgentCapsule())
				Spring->AttachToComponent(Agent->GetAgentCapsule(),FAttachmentTransformRules::KeepRelativeTransform);
			if (!Spring->IsRegistered()) Spring->RegisterComponent();
			if (!Camera->IsRegistered()) Camera->RegisterComponent();
			Spring->SetComponentTickEnabled(true);Camera->Activate();
		}
		else
		{
			if (auto* Follow=Agent->FindComponentByClass<UProphecyAttackCameraComponent>()) Follow->Stop();
			Camera->Deactivate();Camera->SetComponentTickEnabled(false);
			Spring->SetComponentTickEnabled(false);
			if (Camera->IsRegistered()) Camera->UnregisterComponent();
			if (Spring->IsRegistered()) Spring->UnregisterComponent();
			Spring->DetachFromComponent(FDetachmentTransformRules::KeepRelativeTransform);
		}
	}

	static TMap<const AActor*, TWeakObjectPtr<UProphecyAttackCameraComponent>> Followers;

	void CompensateRootSnap(AProphecyAgent* Player,const FVector& PreviousSpringOrigin)
	{
		if (!ProphecyAttackCameraFade::IsPossessedPlayer(Player)) return;
		if (auto* Follow=Player->FindComponentByClass<UProphecyAttackCameraComponent>())
			Follow->CompensateRootSnap(PreviousSpringOrigin);
	}

	void Stop(const AActor* Manager)
	{
		if (auto* Entry = Followers.Find(Manager))
			if (auto* Follow = Entry->Get()) Follow->Stop();
	}

	void End(const AActor* Manager)
	{
		TWeakObjectPtr<UProphecyAttackCameraComponent> Entry;
		if (Followers.RemoveAndCopyValue(Manager, Entry))
			if (auto* Follow = Entry.Get()) Follow->DestroyComponent();
	}

	void Update(AActor* Manager, AProphecyAgent* Player, bool bFullAttack)
	{
		if (!bFullAttack || !ProphecyAttackCameraFade::IsPossessedPlayer(Player) ||
			!Player->GetAgentSpringArm() || !Player->GetPoseReferenceMesh())
		{
			// Blueprint may start the next attack later in PrePhysics. The follower
			// resolves the final state in PostPhysics, avoiding an intermediate reset.
			return;
		}
		auto& Entry = Followers.FindOrAdd(Manager);
		if (Entry.IsValid() && Entry->GetOwner() != Player)
		{
			Entry->DestroyComponent();
			Entry.Reset();
		}
		if (!Entry.IsValid())
		{
			auto* Follow = NewObject<UProphecyAttackCameraComponent>(Player, NAME_None, RF_Transient);
			Player->AddInstanceComponent(Follow);
			Follow->RegisterComponent();
			Entry = Follow;
		}
		Entry->Follow(Manager, Player);
	}
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackCameraFadeTest,"Prophecy.Camera.AttackOffsetFade",
	EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackCameraFadeTest::RunTest(const FString&)
{
	using namespace ProphecyAttackCameraFade;
	FReturn Fade;
	Fade.Begin(FVector(120,-60,0),1.f);
	for (uint64 Frame=1;Frame<=60;++Frame)
	{
		Fade.Advance(Frame,false);
		TestEqual(TEXT("Paused/non-game ticks do not advance"),Fade.ElapsedTicks,Frame-1);
		Fade.Advance(Frame,true);Fade.Advance(Frame,true);
		TestEqual(TEXT("Duplicate reads do not advance twice"),Fade.ElapsedTicks,Frame);
		if (Frame==30) TestTrue(TEXT("Halfway after 30 game ticks"),Fade.Value().Equals(FVector(60,-30,0),1.e-8));
	}
	TestTrue(TEXT("Exactly zero after 60 game ticks"),Fade.Value().IsZero());
	Fade.Begin(FVector(100,0,0),.1f);
	TestEqual(TEXT("Fractional authored seconds use tick count"),Fade.TotalTicks,uint64(6));
	Fade.Begin(FVector(100,0,0),0.f);
	TestTrue(TEXT("Zero duration is immediate"),Fade.Value().IsZero());
	Fade.Begin(FVector(100,0,0),1.e-8f);
	TestEqual(TEXT("Positive duration gets at least one tick"),Fade.TotalTicks,uint64(1));
	Fade.Begin(FVector(100,0,0),1.f);
	for (uint64 Frame=1;Frame<=30;++Frame) Fade.Advance(Frame,true);
	Fade.Begin(Fade.Value(),2.f);
	TestTrue(TEXT("Retiming starts from current offset"),Fade.Value().Equals(FVector(50,0,0),1.e-8));
	TestEqual(TEXT("Retiming changes remaining tick duration"),Fade.TotalTicks,uint64(120));
	Fade.Begin(FVector(100,0,0),10.f);
	for (uint64 Frame=1;Frame<=60;++Frame) Fade.Advance(Frame,true);
	TestTrue(TEXT("Ten-second fade still has 97.2 percent after 60 ticks"),Fade.Value().Equals(FVector(97.2,0,0),1.e-8));
	for (uint64 Frame=61;Frame<=600;++Frame) Fade.Advance(Frame,true);
	TestTrue(TEXT("Ten-second fade completes on tick 600"),Fade.Value().IsZero());

	// Exercise real follower retirement and possession checks without starting PIE or inference.
	UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
	AProphecyAgent* Pawn=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
	APlayerController* PC=World ? World->SpawnActor<APlayerController>() : nullptr;
	AProphecyNNLocomotionManager* Manager=World ? World->SpawnActor<AProphecyNNLocomotionManager>() : nullptr;
	if (!Pawn || !PC || !Manager) { if (World) World->DestroyWorld(false);return false; }
	auto* Follow=NewObject<UProphecyAttackCameraComponent>(Pawn);
	Pawn->AddInstanceComponent(Follow);Follow->RegisterComponent();
	Follow->Follow(Manager,Pawn);
	TestFalse(TEXT("Unpossessed agent cannot start camera tick"),Follow->IsComponentTickEnabled());
	PC->Possess(Pawn);
	Follow->Follow(Manager,Pawn);
	Pawn->GetAgentSpringArm()->TargetOffset=FVector(0,40,0);
	Returns.Add(Follow).Begin(FVector(100,0,0),1.f);
	Follow->TickComponent(1.f/30.f,LEVELTICK_All,nullptr);
	TestTrue(TEXT("Possessed player's return runs"),Pawn->GetAgentSpringArm()->TargetOffset.X>99.);
	TestTrue(TEXT("Fade keeps component active"),Follow->IsComponentTickEnabled());
	USpringArmComponent* Spring=Pawn->GetAgentSpringArm();
	Spring->SetRelativeLocation(FVector(30,20,29));
	const FVector BeforeOrigin=Spring->GetComponentLocation();
	const FVector BeforePivot=BeforeOrigin+Spring->TargetOffset;
	const FVector BeforeOffset=Spring->TargetOffset;
	// Two moves mirror attack carrier catch-up followed by root-balancing placement.
	Pawn->SetActorLocation(Pawn->GetActorLocation()+FVector(70,-20,0));
	Pawn->SetActorLocationAndRotation(Pawn->GetActorLocation()+FVector(-25,55,0),FRotator(0,65,0));
	const FVector ActualDelta=Spring->GetComponentLocation()-BeforeOrigin;
	ProphecyAttackCamera::CompensateRootSnap(Pawn,BeforeOrigin);
	TestTrue(TEXT("Attack root snap leaves camera pivot continuous"),
		(Spring->GetComponentLocation()+Spring->TargetOffset).Equals(BeforePivot,1.e-7));
	TestTrue(TEXT("Inverse actual displacement is applied once"),Spring->TargetOffset.Equals(BeforeOffset-ActualDelta,1.e-7));
	TestTrue(TEXT("Combined offset seeds the same fade"),Returns.FindChecked(Follow).Value().Equals(Spring->TargetOffset-FVector(0,40,0),1.e-7));
	// Production Blueprint/physics root corrections can follow the synchronous
	// handoff. They must join this fade before the camera renders the frame.
	Pawn->AddActorWorldOffset(FVector(4,8,0));
	Follow->TickComponent(1.f/60.f,LEVELTICK_All,nullptr);
	TestTrue(TEXT("PostPhysics includes late root movement and keeps the snap pivot exact"),
		(Spring->GetComponentLocation()+Spring->TargetOffset).Equals(BeforePivot,1.e-7));
	const FVector BeforeResume=Spring->TargetOffset;
	Follow->Follow(Manager,Pawn);
	TestTrue(TEXT("New attack keeps fading the snap compensation"),Returns.Contains(Follow));
	TestTrue(TEXT("New attack preserves compensated camera offset"),Spring->TargetOffset.Equals(BeforeResume,1.e-7));
	Pawn->GetPoseReferenceMesh()->AddWorldOffset(FVector(200,-100,40));
	Follow->TickComponent(1.f/60.f,LEVELTICK_All,nullptr);
	TestTrue(TEXT("Animated mesh movement does not change the capsule camera offset"),Spring->TargetOffset.Equals(BeforeResume,1.e-7));
	for (int32 Tick=1;Tick<=60;++Tick)
	{
		// Model distinct engine frames without changing the global frame counter.
		Returns.FindChecked(Follow).LastFrame=MAX_uint64;
		Follow->Follow(Manager,Pawn);
		Follow->TickComponent(1.f/60.f,LEVELTICK_All,nullptr);
	}
	TestFalse(TEXT("Repeated attack updates do not interrupt the 60-tick fade"),Returns.Contains(Follow));
	TestTrue(TEXT("Completed fade keeps the independent offset"),Spring->TargetOffset.Equals(FVector(0,40,0),1.e-8));
	Follow->Follow(Manager,Pawn);
	const FVector NextOrigin=Spring->GetComponentLocation();
	Pawn->AddActorWorldOffset(FVector(-90,40,10));
	ProphecyAttackCamera::CompensateRootSnap(Pawn,NextOrigin);
	PC->UnPossess();
	Follow->TickComponent(1.f/120.f,LEVELTICK_All,nullptr);
	TestFalse(TEXT("Unpossession disables camera tick"),Follow->IsComponentTickEnabled());
	TestFalse(TEXT("Unpossession removes active return"),Returns.Contains(Follow));
	TestTrue(TEXT("Unpossession preserves independent Blueprint offset"),Pawn->GetAgentSpringArm()->TargetOffset.Equals(FVector(0,40,0),1.e-8));
	PC->Possess(Pawn);Follow->Follow(Manager,Pawn);
	Returns.Add(Follow).Begin(FVector(100,0,0),1.f);
	Follow->TickComponent(1.f/60.f,LEVELTICK_All,nullptr);
	UProphecyAttackControlLibrary::SetAttackCameraOffsetFadeDuration(Pawn,0.f);
	TestFalse(TEXT("Setting zero retires an ongoing fade immediately"),Follow->IsComponentTickEnabled());
	TestFalse(TEXT("Zero removes active return"),Returns.Contains(Follow));
	TestTrue(TEXT("Zero restores original offset"),Pawn->GetAgentSpringArm()->TargetOffset.Equals(FVector(0,40,0),1.e-8));
	UProphecyAttackControlLibrary::SetAttackCameraOffsetFadeDuration(Pawn,1.f);
	TestFalse(TEXT("Default setting needs no entry"),Durations.Contains(Pawn));
	World->DestroyWorld(false);
	return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackCameraComTest,"Prophecy.Camera.COMAndPlayerRig",
 EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackCameraComTest::RunTest(const FString&)
{
 using namespace ProphecyAttackCameraFade;
 UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
 AProphecyAgent* Pawn=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
 APlayerController* PC=World ? World->SpawnActor<APlayerController>() : nullptr;
 AProphecyNNLocomotionManager* Manager=World ? World->SpawnActor<AProphecyNNLocomotionManager>() : nullptr;
 if (!Pawn || !PC || !Manager) { if (World) World->DestroyWorld(false);return false; }
 auto* Spring=Pawn->GetAgentSpringArm();auto* Camera=Pawn->GetAgentCamera();
 const FTransform Relative=Spring->GetRelativeTransform();
 ProphecyAttackCamera::RefreshPlayerRig(Pawn);
 TestFalse(TEXT("NPC spring is unregistered"),Spring->IsRegistered());
 TestFalse(TEXT("NPC camera is unregistered"),Camera->IsRegistered());
 TestFalse(TEXT("NPC spring does not tick"),Spring->IsComponentTickEnabled());
 TestNull(TEXT("NPC camera subtree does not follow root transforms"),Spring->GetAttachParent());
 PC->Possess(Pawn);
 TestTrue(TEXT("Possession registers spring"),Spring->IsRegistered());
 TestTrue(TEXT("Possession registers camera"),Camera->IsRegistered());
 TestTrue(TEXT("Possession restores attachment/settings"),Spring->GetAttachParent()==Pawn->GetAgentCapsule() && Spring->GetRelativeTransform().Equals(Relative));
 TestTrue(TEXT("Default COM setting needs no entry"),!ComAlphas.Contains(Pawn));
 TestTrue(TEXT("Configure partial COM follow"),UProphecyAttackControlLibrary::SetAttackCameraCOMFollow(Pawn,.5f));
 TestEqual(TEXT("Partial alpha retained"),ComAlphas.FindChecked(Pawn),.5f);
 UProphecyAttackControlLibrary::SetAttackCameraCOMFollow(Pawn,2.f);
 TestEqual(TEXT("Alpha clamped to one"),ComAlphas.FindChecked(Pawn),1.f);
 UProphecyAttackControlLibrary::SetAttackCameraCOMFollow(Pawn,0.f);
 TestFalse(TEXT("Zero removes the setting"),ComAlphas.Contains(Pawn));
 auto* Follow=NewObject<UProphecyAttackCameraComponent>(Pawn);
 Pawn->AddInstanceComponent(Follow);Follow->RegisterComponent();Follow->Follow(Manager,Pawn);
 auto* Mesh=Pawn->GetPoseReferenceMesh();
 const int32 Pelvis=Mesh->GetBoneIndex(TEXT("pelvis")),Hand=Mesh->GetBoneIndex(TEXT("hand_r"));
 if (TestTrue(TEXT("Reference body bones exist"),Pelvis!=INDEX_NONE && Hand!=INDEX_NONE))
 {
  Follow->BoneMasses={{Pelvis,1.,FVector(2,3,4)},{Hand,3.,FVector(-3,2,1)}};
  const FVector Expected=(Mesh->GetBoneTransform(Pelvis).TransformPosition(FVector(2,3,4))+
   Mesh->GetBoneTransform(Hand).TransformPosition(FVector(-3,2,1))*3.)/4.;
  TestTrue(TEXT("COM uses body masses and local mass centers"),Follow->ReadCenterOfMass(false).Equals(Expected,1.e-7));
 }
 // A horizontal COM offset and the inverse capsule displacement must share one fade.
 Follow->bTrackingCom=true;Follow->AppliedOffset=FVector(17,-23,0);Spring->TargetOffset+=Follow->AppliedOffset;
 const FVector OldOrigin=Spring->GetComponentLocation(),OldPivot=OldOrigin+Spring->TargetOffset;
 Pawn->AddActorWorldOffset(FVector(30,20,0));Follow->CompensateRootSnap(OldOrigin);
 Pawn->AddActorWorldOffset(FVector(4,-7,0));Follow->TickComponent(1.f/60.f,LEVELTICK_All,nullptr);
 TestFalse(TEXT("Handoff ends COM tracking"),Follow->bTrackingCom);
 TestTrue(TEXT("COM handoff plus late root update preserves pivot"),(Spring->GetComponentLocation()+Spring->TargetOffset).Equals(OldPivot,1.e-7));
 PC->UnPossess();
 TestFalse(TEXT("Unpossession unregisters spring"),Spring->IsRegistered());
 TestFalse(TEXT("Unpossession stops follow immediately"),Follow->IsComponentTickEnabled());
 TestTrue(TEXT("Unpossession removes camera offset"),Spring->TargetOffset.IsNearlyZero());
 PC->Possess(Pawn);
 TestTrue(TEXT("Repossess restores camera"),Camera->IsRegistered() && Spring->IsComponentTickEnabled());
 World->DestroyWorld(false);return !HasAnyErrors();
}
#endif
