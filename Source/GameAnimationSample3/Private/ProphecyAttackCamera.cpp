#include "ProphecyAttackCamera.h"
#include "ProphecyAttackControlLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNDefenseLibrary.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"

namespace ProphecyAttackCameraFade
{
struct FReturn
{
	FVector StartOffset=FVector::ZeroVector;
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
	if (Durations.IsEmpty())
	{
		FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();
	}
	else if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
	{
		for (auto It=Durations.CreateIterator();It;++It)
			if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
		RefreshCleanup();
	});
}
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
	if (NewMesh) AddTickPrerequisiteComponent(NewMesh);
}

void UProphecyAttackCameraComponent::Follow(AActor* InManager, AProphecyAgent* InAgent)
{
	if (!ProphecyAttackCameraFade::IsPossessedPlayer(InAgent)) return;
	if (bFollowing)
	{
		SetMesh(InAgent->GetPoseReferenceMesh());
		if (ProphecyAttackCameraFade::Returns.Remove(this))
		{
			// A new attack interrupts the return without dropping the residual offset.
			InitialPelvisFromRoot=Mesh->GetSocketLocation(TEXT("pelvis"))-InAgent->GetActorLocation()-AppliedOffset;
		}
		return;
	}
	Manager = InManager; Agent = InAgent; Spring = InAgent->GetAgentSpringArm();
	SetMesh(InAgent->GetPoseReferenceMesh());
	InitialPelvisFromRoot = Mesh->GetSocketLocation(TEXT("pelvis")) - InAgent->GetActorLocation();
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
	const FVector Delta=Spring->GetComponentLocation()-PreviousSpringOrigin;
	if (Delta.ContainsNaN() || Delta.IsNearlyZero()) return;
	Spring->TargetOffset-=Delta;
	AppliedOffset-=Delta;
	Returns.FindOrAdd(this).Begin(AppliedOffset,Seconds);
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
	SetComponentTickEnabled(false);
	ReleasePrerequisites();
}

void UProphecyAttackCameraComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	AProphecyAgent* Pawn = Agent.Get();
	const auto* OwnerManager = Cast<AProphecyNNLocomotionManager>(Manager.Get());
	FName Attack; bool bHalf = false, bArmed = false, bHit = false; int32 Frame = 0;
	const bool bFullAttack = Pawn && OwnerManager && OwnerManager->GetAgentNNAttackState(
		Pawn->GetAgentHandle(), Attack, bHalf, bArmed, bHit, Frame) && !bHalf;
	if (!bFollowing || !OwnerManager || !ProphecyAttackCameraFade::IsPossessedPlayer(Pawn) || !Spring.IsValid() || !Mesh.IsValid())
	{
		Stop();
		return;
	}
	const auto Activity=Pawn && OwnerManager ? OwnerManager->GetAgentActivityState(Pawn->GetAgentHandle()) : EProphecyAgentState::Locomotion;
	if (!bFullAttack && Activity!=EProphecyAgentState::Parrying && Activity!=EProphecyAgentState::Dodging)
	{
		using namespace ProphecyAttackCameraFade;
		FReturn* Fade=Returns.Find(this);
		if (!Fade)
		{
			const float Seconds=Duration(Pawn);
			if (Seconds<=0.f || AppliedOffset.IsNearlyZero()) { Stop();return; }
			Fade=&Returns.Add(this);Fade->Begin(AppliedOffset,Seconds);
		}
		// Count completed game ticks, never DeltaTime or NN/policy steps.
		Fade->Advance(GFrameCounter,TickType==LEVELTICK_All && GetWorld() && !GetWorld()->IsPaused());
		if (Fade->ElapsedTicks>=Fade->TotalTicks) { Stop();return; }
		const FVector Offset=Fade->Value();
		Spring->TargetOffset+=Offset-AppliedOffset;AppliedOffset=Offset;
		return;
	}
	if (ProphecyAttackCameraFade::Returns.Remove(this))
	{
		// Also cover an attack begun by Blueprint after the manager's update.
		InitialPelvisFromRoot=Mesh->GetSocketLocation(TEXT("pelvis"))-Pawn->GetActorLocation()-AppliedOffset;
	}
	// Jolt publishes before physics completes; the mesh prerequisite also waits
	// for skeletal evaluation. Read the actual displayed body in either backend.
	FVector Offset = Mesh->GetSocketLocation(TEXT("pelvis")) - Pawn->GetActorLocation() - InitialPelvisFromRoot;
	Offset.Z = 0; // Follow attack travel without adding pelvis bob to the camera.
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
	const FVector BeforeResume=Spring->TargetOffset;
	Follow->Follow(Manager,Pawn);
	TestFalse(TEXT("New attack cancels compensated return"),Returns.Contains(Follow));
	TestTrue(TEXT("New attack preserves compensated camera offset"),Spring->TargetOffset.Equals(BeforeResume,1.e-7));
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
#endif
