#include "ProphecySwordComponent.h"
#include "ProphecySwordPhysicsLibrary.h"
#include "ProphecyGhostAttackLibrary.h"
#if WITH_EDITOR
#include "StaticMeshCompiler.h"
#endif
#include "ProphecySwordAttackCollision.h"
#include "ProphecyJoltPHATSweepLibrary.h"
#include "ProphecyDefenseCollision.h"
#include "ProphecyDefenseArmedGate.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "UObject/UnrealType.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "PBDRigidsSolver.h"
#include "Chaos/PBDRigidsEvolution.h"
#include "Chaos/Collision/CollisionConstraintFlags.h"
#include "ProphecySwordCollisionCooldown.inl"

namespace ProphecySwordNoReaction
{
static TSet<TWeakObjectPtr<const AProphecyAgent>> EnabledAgents;
struct FAutomatic { bool Slash=false,Armed=false; float Strength=1.f; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FAutomatic> Automatic;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for(auto It=EnabledAgents.CreateIterator();It;++It)
            if(!It->IsValid() || It->Get()->GetWorld()==World)It.RemoveCurrent();
        for(auto It=Automatic.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();
        if(EnabledAgents.IsEmpty() && Automatic.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
    });
}
static bool Apply(UProphecyJoltBodyComponent* Body,float Strength)
{
    FProphecyJoltBodyHandle H;
    if(!Body || !Body->GetBodyHandle(H))return true; // Preference is applied on admission.
    auto* World=Body->GetWorldOwner();if(!World)return false;
    const auto Result=World->SetBodyContactReactionScale(H,1.f-Strength);
    if(!Result.IsSuccess())UE_LOG(LogTemp,Warning,TEXT("Sword contact response: %s"),*Result.Message);
    return Result.IsSuccess();
}
static float Desired(const AProphecyAgent* Agent)
{
    if(EnabledAgents.Contains(Agent))return 1.f;
    const auto* State=Automatic.Find(Agent);
    return State && State->Slash && State->Armed && State->Strength>0.f
        && !ProphecyDefenseCollision::BlocksSlashSwordNoReaction(Agent) ? State->Strength : 0.f;
}
static bool Refresh(AProphecyAgent* Agent)
{
    auto* Sword=Agent?Agent->GetHeldSword():nullptr;
    return !Sword || Apply(Sword->FindComponentByClass<UProphecyJoltBodyComponent>(),Desired(Agent));
}
static void Family(AProphecyAgent* Agent,FName Name,bool Armed)
{
    if(auto* State=Automatic.Find(Agent))
    {
        State->Slash=Name.ToString().StartsWith(TEXT("slash"),ESearchCase::IgnoreCase);
        State->Armed|=Armed;Refresh(Agent);
    }
}
static void Armed(AProphecyAgent* Agent)
{
    if(auto* State=Automatic.Find(Agent)){State->Armed=true;Refresh(Agent);}
}
static void End(AProphecyAgent* Agent)
{
    if(auto* State=Automatic.Find(Agent)){State->Slash=false;State->Armed=false;Refresh(Agent);}
}
void DefenseChanged()
{
    for(const auto& Entry:Automatic)if(Entry.Value.Slash && Entry.Value.Armed)
        if(auto* Agent=const_cast<AProphecyAgent*>(Entry.Key.Get()))Refresh(Agent);
}
void VictimChanged(AProphecyAgent* Agent)
{
    if(Automatic.Contains(Agent))Refresh(Agent);
}
}

namespace ProphecySwordAttackCollision
{
namespace
{
void SetAttackArmWindow(AProphecyAgent* Agent,bool Active)
{
    if (!Agent) return;
    // Phase events only; reflected dispatch avoids a new live cross-DLL import.
    struct FParams { AActor* Agent; bool Active; } Params{Agent,Active};
    auto* Library=FindObjectChecked<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltBodyDriveLibrary"))->GetDefaultObject();
    Library->ProcessEvent(Library->FindFunctionChecked(TEXT("NotifyArmsAntiJiggleAttackWindow")),&Params);
}
void SelectSlashSweep(AProphecyAgent* Agent,FName Family)
{
    static const FName Slashes[]={TEXT("slashL"),TEXT("slashLU"),TEXT("slashLD"),TEXT("slashR"),TEXT("slashRU"),TEXT("slashRD")};
    bool Slash=false;
    for (FName Name:Slashes) Slash|=Family==Name;
    AActor* Sword=Slash && Agent ? Agent->GetHeldSword() : nullptr;
    UProphecyJoltPHATSweepLibrary::SetAttackParts(Agent,Sword ? TArray<FName>{TEXT("sword")} : TArray<FName>{},
        Sword ? Cast<UPrimitiveComponent>(Sword->GetRootComponent()) : nullptr);
}
struct FGate
{
	// Keep the previous one-byte family field/layout for existing Live Coding state.
	enum : uint8 { Weapon=1, RightPunch=2, PunchArmed=4, ArmedSeen=8 };
	uint8 Family=0;
	bool bAllowed=false,bSuppressed=false,bGapMelee=false;
	bool IsWeapon() const { return (Family&Weapon)!=0; }
	bool SuppressesPunch() const { return (Family&(RightPunch|PunchArmed))==(RightPunch|PunchArmed); }
	TWeakObjectPtr<UStaticMeshComponent> Blade;
	FCollisionResponseContainer Original;
};
uint8 CollisionFamily(FName Family)
{
	if (Family==TEXT("jabR") || Family==TEXT("hookR") || Family==TEXT("overR")) return FGate::RightPunch;
	return Family==TEXT("pike") || Family.ToString().StartsWith(TEXT("slash"),ESearchCase::IgnoreCase) ? FGate::Weapon : 0;
}
TMap<TWeakObjectPtr<const AProphecyAgent>,FGate> Gates;
TSet<TWeakObjectPtr<const AProphecyAgent>> HitOwners;
// Event-only preference; no component layout changes or per-tick collision polling.
TSet<TWeakObjectPtr<const AProphecyAgent>> CollisionDisabled;
TSet<TWeakObjectPtr<const AProphecyAgent>> OwnCollisionDisabled;
FDelegateHandle OwnCollisionCleanup;
void EnsureOwnCollisionCleanup()
{
    if (OwnCollisionCleanup.IsValid()) return;
    OwnCollisionCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=OwnCollisionDisabled.CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
        if (OwnCollisionDisabled.IsEmpty())
        { FWorldDelegates::OnWorldCleanup.Remove(OwnCollisionCleanup);OwnCollisionCleanup.Reset(); }
    });
}
void SetBodySuppressed(AProphecyAgent* Agent, bool bSuppressed)
{
    if (!Agent) return;
    if (auto* Character = Agent->GetJoltCharacterComponent(); Character && Character->IsJoltPhysical())
    {
        FString Error;
        if (!Character->SetAttackSelfCollisionSuppressed(bSuppressed, Error))
            UE_LOG(LogTemp, Warning, TEXT("Attack body self-collision: %s"), *Error);
    }
}
void RefreshOwner(AProphecyAgent* Agent)
{
    if (Agent) if (auto* Controller=Agent->FindComponentByClass<UProphecySwordComponent>())
        Controller->RefreshOwnerCollision();
}
void Responses(UStaticMeshComponent& Blade,const FCollisionResponseContainer& Value)
{
	Blade.SetCollisionResponseToChannels(Value);
	// Update Jolt immediately too, including a sword welded into the hand. Keep
	// its body, grip, mass and velocities intact; the UE receiver stays QueryOnly.
	if (auto* Body=Blade.GetOwner()->FindComponentByClass<UProphecyJoltBodyComponent>())
	{
		FProphecyJoltBodyHandle Handle;
		if (Body->GetBodyHandle(Handle)) if (auto* World=Body->GetWorldOwner())
		{
			FProphecyJoltCollisionUpdate Update;Update.Handle=Handle;
			Update.ObjectChannel=Blade.GetCollisionObjectType();Update.Responses=Value;
			const auto Result=World->UpdateBodyCollision(MakeArrayView(&Update,1));
			if (!Result.IsSuccess()) UE_LOG(LogTemp,Warning,TEXT("Sword attack collision update: %s"),*Result.Message);
		}
	}
}
void Restore(FGate& Gate)
{
	if (Gate.bSuppressed) if (auto* Blade=Gate.Blade.Get()) Responses(*Blade,Gate.Original);
	Gate.bSuppressed=false;Gate.Blade.Reset();
}
}
bool SuppressesOwner(const AProphecyAgent* Agent)
{
    return Agent && Agent->IsSwordAttackActive() && !HitOwners.Contains(Agent);
}
// Keep the automatic body-body attack mask separate from this sword-only preference.
bool SuppressesSwordOwner(const AProphecyAgent* Agent)
{
    const auto* Gate=Gates.Find(Agent);
    // Weapon wind-up gates only the owner's pairs; melee retains its until-Hit rule.
    return OwnCollisionDisabled.Contains(Agent)
        || (Gate && Gate->IsWeapon() && !Gate->bGapMelee ? !Gate->bAllowed : SuppressesOwner(Agent));
}
bool IsAllowed(const AProphecyAgent* Agent)
{
	const auto* Gate=Gates.Find(Agent);
	return !CollisionDisabled.Contains(Agent) && (!Gate || (!Gate->SuppressesPunch() && (Gate->bAllowed
        || (!Gate->bGapMelee && (Gate->IsWeapon() || ProphecySwordCooldown::Active.Contains(Agent))))));
}
void Refresh(AProphecyAgent* Agent)
{
	auto* Gate=Gates.Find(Agent);
	if (!Gate && CollisionDisabled.Contains(Agent))
	{
		Gate=&Gates.Add(Agent);Gate->bAllowed=true;
	}
	if (!Gate) return;
	if (IsAllowed(Agent)) { Restore(*Gate);return; }
	auto* Sword=Agent->GetHeldSword();
	auto* Blade=Sword?Cast<UStaticMeshComponent>(Sword->GetRootComponent()):nullptr;
	if (!Blade) return;
	if (Gate->Blade.Get()!=Blade)
	{
		Restore(*Gate);Gate->Blade=Blade;Gate->Original=Blade->GetCollisionResponseToChannels();
	}
	Gate->bSuppressed=true;
	Responses(*Blade,FCollisionResponseContainer(ECR_Ignore));
}
void Begin(AProphecyAgent* Agent,FName Family,int64 EntryTicks)
{
	if (!Agent) return;
	End(Agent);
	ProphecySwordCooldown::Family(Agent,Family,false);
	ProphecySwordNoReaction::Family(Agent,Family,false);
	auto& Gate=Gates.FindOrAdd(Agent);
	Gate.bAllowed=false;
	Gate.bGapMelee=(EntryTicks>=0 ? EntryTicks : UProphecyGhostAttackLibrary::GetTicksSinceLastAttack(Agent))
		>ProphecySwordCooldown::MeleeGapThreshold(Agent);
	Gate.Family=CollisionFamily(Family);
	SetBodySuppressed(Agent, true);
	RefreshOwner(Agent);
}
void Armed(AProphecyAgent* Agent)
{
	ProphecySwordNoReaction::Armed(Agent);
	auto* Gate=Gates.Find(Agent);
	if (!Gate) return;
	Gate->Family|=FGate::ArmedSeen;
	SetAttackArmWindow(Agent,Gate->IsWeapon());
	if ((Gate->Family&FGate::RightPunch)!=0)
	{
		if (!Gate->SuppressesPunch()) { Gate->Family|=FGate::PunchArmed;Refresh(Agent); }
		return;
	}
	if (!Gate->IsWeapon()) return;
	ProphecySwordCooldown::Armed(Agent);
	if (Gate->bGapMelee) return; // Actual slash still qualifies for its eventual end cooldown.
	if (Gate->bAllowed) return;
	Gate->bAllowed=true;RefreshOwner(Agent);
}
void RetargetFamily(AProphecyAgent* Agent,FName Family,bool bArmed,bool bHit)
{
	auto* Gate=Gates.Find(Agent);
	if (!Gate) return;
    SelectSlashSweep(Agent,Family);
	ProphecySwordCooldown::Family(Agent,Family,bArmed);
	ProphecySwordNoReaction::Family(Agent,Family,bArmed);
	const uint8 Kind=CollisionFamily(Family);
	const uint8 ArmedPhase=bArmed || (Gate->Family&FGate::ArmedSeen) ? FGate::ArmedSeen : 0;
	// NN Hit precedes physical contact. Keep sword-arm suppression through follow-through.
	SetAttackArmWindow(Agent,(Kind&FGate::Weapon)!=0 && ArmedPhase!=0);
	const uint8 PreviousKind=Gate->Family&(FGate::Weapon|FGate::RightPunch);
	const uint8 Phase=ArmedPhase | (Kind==FGate::RightPunch && (bArmed || (PreviousKind==Kind && Gate->SuppressesPunch()))
		? FGate::PunchArmed : 0);
	if (PreviousKind==Kind)
	{
		if (Gate->Family!=(Kind|Phase)) { Gate->Family=Kind|Phase;Refresh(Agent); }
		return; // Preserve the already-latched collision phase.
	}
	Gate->Family=Kind|Phase;
	const bool bWeapon=Gate->IsWeapon();
	Gate->bAllowed=bWeapon && !Gate->bGapMelee ? bArmed : bHit;
	RefreshOwner(Agent); // Retain original responses, body and grip; no End/Begin cycle.
}
void Hit(AProphecyAgent* Agent)
{
    if (!Agent || !Gates.Contains(Agent)) return;
    const bool First=!HitOwners.Contains(Agent);
    HitOwners.Add(Agent);
    // Restore owner pairs for every attack family without ending any attack systems.
    if (First) { SetBodySuppressed(Agent, false); RefreshOwner(Agent); }
	auto* Gate=Gates.Find(Agent);
	if (!Gate || (Gate->IsWeapon() && !Gate->bGapMelee) || Gate->bAllowed) return;
	Gate->bAllowed=true;Refresh(Agent);
}
void End(AProphecyAgent* Agent)
{
	SetAttackArmWindow(Agent,false);
	ProphecySwordNoReaction::End(Agent);
	ProphecySwordCooldown::End(Agent);
	SetBodySuppressed(Agent, false);
	FGate Gate;if (Gates.RemoveAndCopyValue(Agent,Gate)) Restore(Gate);
    HitOwners.Remove(Agent);
	Refresh(Agent); // A manual disable survives attack end.
}
void ReleaseSword(AProphecyAgent* Agent)
{
	ProphecySwordCooldown::Cancel(Agent);
	if (auto* Gate=Gates.Find(Agent)) Restore(*Gate);
}
void CancelCooldown(AProphecyAgent* Agent) { ProphecySwordCooldown::Cancel(Agent);Refresh(Agent); }
}

struct FProphecyJoltSwordBinding
{
	TWeakObjectPtr<UProphecyJoltWorldSubsystem> World;
	TWeakObjectPtr<UProphecyJoltCharacterComponent> Character;
	FProphecyJoltJointHandle Joint;
	FProphecyJoltBodyHandle Hand;
};

void FProphecyJoltSwordBindingDeleter::operator()(FProphecyJoltSwordBinding* Binding) const { delete Binding; }

namespace
{
bool SwordDriveFollower(UObject* Context, const FProphecyJoltBodyHandle& Body,
    const FProphecyJoltBodyHandle& Hand, const FTransform& Offset, bool Enabled)
{
    // New plugin API via its reflected bridge: no dependency on a stale live import library.
    struct FArgs
    {
        UObject* WorldContext; FGuid Lifetime; int32 BodySlot; int64 BodyGeneration;
        int32 ParentSlot; int64 ParentGeneration; FTransform BodyToParent; bool Enabled; bool ReturnValue;
    } Args{Context,Body.WorldLifetime,Body.Slot,int64(Body.Generation),Hand.Slot,int64(Hand.Generation),Offset,Enabled,false};
    auto* Library=FindObjectChecked<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltBodyDriveLibrary"))->GetDefaultObject();
    Library->ProcessEvent(Library->FindFunctionChecked(TEXT("SetDriveFollower")),&Args);
    return Args.ReturnValue;
}
}

namespace
{
	struct FOwnerCollisionPairs
	{
		Chaos::FPhysicsSolver* Solver = nullptr;
		Chaos::FUniqueIdx Blade;
		TArray<Chaos::FUniqueIdx> Bodies;
	};
	// Stable across Live Coding; entries are released on drop, destruction and EndPlay.
	TMap<const UProphecySwordComponent*, FOwnerCollisionPairs>& OwnerCollisionPairs()
	{
		static auto* Pairs = new TMap<const UProphecySwordComponent*, FOwnerCollisionPairs>;
		return *Pairs;
	}
	void QueueOwnerCollisions(const FOwnerCollisionPairs& Pairs, bool bIgnore)
	{
		Pairs.Solver->EnqueueCommandImmediate([Pairs, bIgnore]()
		{
			auto* BladeProxy = Pairs.Solver->GetParticleProxy_PT(Pairs.Blade);
			if (!BladeProxy) return;
			auto& Manager = Pairs.Solver->GetEvolution()->GetBroadPhase().GetIgnoreCollisionManager();
			for (const auto Id : Pairs.Bodies)
			{
				if (auto* BodyProxy = Pairs.Solver->GetParticleProxy_PT(Id))
				{
					if (bIgnore) Manager.AddIgnoreCollisions(BladeProxy->GetHandle_LowLevel(), BodyProxy->GetHandle_LowLevel());
					else Manager.RemoveIgnoreCollisions(BladeProxy->GetHandle_LowLevel(), BodyProxy->GetHandle_LowLevel());
				}
			}
		});
	}
	void ClearOwnerCollisions(const UProphecySwordComponent* Controller)
	{
		FOwnerCollisionPairs Pairs;
		if (OwnerCollisionPairs().RemoveAndCopyValue(Controller, Pairs)) QueueOwnerCollisions(Pairs, false);
	}
	void IgnoreOwnerCollisions(const UProphecySwordComponent* Controller, UStaticMeshComponent* Blade, AProphecyAgent* Owner,
		bool bAllOwner = true, bool bIncludeHand = false)
	{
		FOwnerCollisionPairs Pairs;
		const auto Handle = Blade->BodyInstance.ActorHandle;
		if (!Handle) return;
		Pairs.Solver = Handle->GetSolver<Chaos::FPhysicsSolver>();
		if (!Pairs.Solver) return;
		Pairs.Blade = Handle->GetGameThreadAPI().UniqueIdx();
		// The fixed grip owns this pair independently, including after an attack ends.
		const auto* OwnerMesh = Owner->GetPoseReferenceMesh();
		const FBodyInstance* GrippingHand = OwnerMesh ? OwnerMesh->GetBodyInstance(OwnerMesh->GetSocketBoneName(Owner->SwordHandSocket)) : nullptr;
		const FBodyInstance* GrippingForearm = OwnerMesh
			? OwnerMesh->GetBodyInstance(OwnerMesh->GetParentBone(OwnerMesh->GetSocketBoneName(Owner->SwordHandSocket))) : nullptr;
		TArray<UPrimitiveComponent*> Components;
		Owner->GetComponents(Components);
		for (UPrimitiveComponent* Component : Components)
		{
			auto Add = [&Pairs, GrippingHand, GrippingForearm, bAllOwner, bIncludeHand](FBodyInstance* Body)
			{
				if (Body && (Body == GrippingHand ? bIncludeHand : (Body == GrippingForearm || bAllOwner))
					&& Body->ActorHandle && Body->ActorHandle->GetSolver<Chaos::FPhysicsSolver>() == Pairs.Solver)
					Pairs.Bodies.AddUnique(Body->ActorHandle->GetGameThreadAPI().UniqueIdx());
			};
			if (auto* Mesh = Cast<USkeletalMeshComponent>(Component)) for (auto* Body : Mesh->Bodies) Add(Body);
			else Add(Component->GetBodyInstance());
		}
		OwnerCollisionPairs().Add(Controller, Pairs);
		QueueOwnerCollisions(Pairs, true);
	}
}

UProphecySwordComponent::UProphecySwordComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

UProphecySwordComponent::~UProphecySwordComponent() = default;

AProphecyAgent* UProphecySwordComponent::Agent() const { return Cast<AProphecyAgent>(GetOwner()); }

FTransform UProphecySwordComponent::GripWorld() const
{
	return Agent()->SwordGripTransform * Agent()->GetPoseReferenceMesh()->GetSocketTransform(Agent()->SwordHandSocket);
}

bool UProphecySwordComponent::Equip(bool bSimulated)
{
	if (Sword) return SetSimulated(bSimulated);
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* M = A ? A->GetPoseReferenceMesh() : nullptr;
	UClass* Class = A ? A->SwordBlueprint.LoadSynchronous() : nullptr;
	if (!M || !M->DoesSocketExist(A->SwordHandSocket) || !Class) return false;
	if (!FMath::IsFinite(A->SwordMassKg) || A->SwordMassKg <= 0 || A->SwordGripTransform.ContainsNaN()) return false;
	// A_Sword's existing cutting/NS code expects its decal manager in the world.
	// Reuse it or create the dependency once; do not remove the cutting graph.
	const bool bKnownSword = Class->GetPathName() == TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C");
	if (bKnownSword)
	{
		if (const FObjectPropertyBase* P = FindFProperty<FObjectPropertyBase>(Class, TEXT("decal manager"));
			P && P->PropertyClass && P->PropertyClass->IsChildOf(AActor::StaticClass()))
		{
			bool bFound = false;
			for (TActorIterator<AActor> It(GetWorld(), P->PropertyClass); It; ++It) { bFound = true; break; }
			if (!bFound)
			{
				FActorSpawnParameters ManagerParameters;
				ManagerParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				if (!GetWorld()->SpawnActor<AActor>(P->PropertyClass, FTransform::Identity, ManagerParameters)) return false;
			}
		}
	}
	FActorSpawnParameters P;
	P.Owner = A;
	P.Instigator = A;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	P.bDeferConstruction = true;
	Sword = GetWorld()->SpawnActor<AActor>(Class, GripWorld(), P);
	if (!Sword) return false;
	if (bKnownSword)
	{
		// Per-instance gameplay initialization BEFORE Blueprint BeginPlay. Its
		// authored debug defaults otherwise change global FPS and pause on tick 0.
		if (FBoolProperty* Flag = FindFProperty<FBoolProperty>(Class, TEXT("debug mode"))) Flag->SetPropertyValue_InContainer(Sword, false);
		if (FIntProperty* Freeze = FindFProperty<FIntProperty>(Class, TEXT("freeze tick"))) Freeze->SetPropertyValue_InContainer(Sword, -1);
		if (FIntProperty* Unfreeze = FindFProperty<FIntProperty>(Class, TEXT("unfreeze tick"))) Unfreeze->SetPropertyValue_InContainer(Sword, 0);
		if (FBoolProperty* Gravity = FindFProperty<FBoolProperty>(Class, TEXT("enable gravity"))) Gravity->SetPropertyValue_InContainer(Sword, true);
	}
	Sword->FinishSpawning(GripWorld());
	TArray<UStaticMeshComponent*> Meshes;
	Sword->GetComponents(Meshes);
	for (UStaticMeshComponent* C : Meshes) if (C->GetFName() == TEXT("sword")) Blade = C;
	if (!Blade && Meshes.Num() == 1) Blade = Meshes[0];
	if (!Blade || !Blade->GetStaticMesh()) { Disappear(); return false; }
	if (Blade->GetStaticMesh()->GetPathName() == TEXT("/Game/_mygame/sword/geometry/Sword_GL01.Sword_GL01"))
	{
		if (UStaticMesh* Exact = A->SwordTrainingMesh.LoadSynchronous()) Blade->SetStaticMesh(Exact);
	}
#if WITH_EDITOR
	// LoadSynchronous does not finish editor asynchronous mesh compilation. UE
	// suppresses ShouldCreatePhysicsState while IsCompiling, so a cold first PIE
	// can otherwise fail Bind/IsSimulatingPhysics and delete the just-spawned item.
	// Finish only the selected sword mesh, once at equip; never wait from Tick.
	if (UStaticMesh* Mesh = Blade->GetStaticMesh(); Mesh && Mesh->IsCompiling())
	{
		UE_LOG(LogTemp, Display, TEXT("Sword equip: finishing pending mesh compilation for %s"), *Mesh->GetPathName());
		UStaticMesh* PendingMeshes[] = {Mesh};
		FStaticMeshCompilingManager::Get().FinishCompilation(PendingMeshes);
	}
#endif
	// Make the existing Blueprint mesh the runtime root so a dropped simulated
	// sword's actor transform follows its body, not an abandoned scene root.
	USceneComponent* OldRoot = Sword->GetRootComponent();
	// This controller owns the native Jolt weld or explicit Chaos grip. UE auto-welding
	// the attached receiver into the hand adds foreign shapes to its PHAT body on a
	// backend switch and prevents later Jolt rig capture.
	Blade->BodyInstance.bAutoWeld = false;
	Blade->SetSimulatePhysics(false);
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	Sword->SetRootComponent(Blade);
	if (OldRoot && OldRoot != Blade) OldRoot->AttachToComponent(Blade, FAttachmentTransformRules::KeepWorldTransform);
	Blade->SetCollisionProfileName(TEXT("PhysicsActor"));
	Blade->SetEnableGravity(true);
	BaseMassKg = A->SwordMassKg;
	if (!ApplyMass(BaseMassKg * A->GetSwordInertiaScale())) { Disappear(); return false; }
	Blade->BodyInstance.bUseCCD = true;
	Blade->BodyInstance.PositionSolverIterationCount = 16;
	Blade->BodyInstance.VelocitySolverIterationCount = 8;
	Grip = NewObject<UPhysicsConstraintComponent>(A);
	Grip->ComponentTags.Add(TEXT("Prophecy.ManagedConstraint")); // Its controller owns the Jolt grip separately.
	A->AddInstanceComponent(Grip);
	Grip->RegisterComponent();
	Grip->SetDisableCollision(true);
	Grip->SetLinearXLimit(LCM_Locked, 0);
	Grip->SetLinearYLimit(LCM_Locked, 0);
	Grip->SetLinearZLimit(LCM_Locked, 0);
	Grip->SetAngularSwing1Limit(ACM_Locked, 0);
	Grip->SetAngularSwing2Limit(ACM_Locked, 0);
	Grip->SetAngularTwistLimit(ACM_Locked, 0);
	bPhysicsHold = bSimulated;
	if (!Bind(true)) { Disappear(); return false; }
	SetComponentTickEnabled(true);
	return true;
}

UProphecyJoltBodyComponent* UProphecySwordComponent::EnsureJoltBody()
{
	if (!IsValid(Sword) || !IsValid(Blade)) return nullptr;
	if (!JoltBody)
	{
		JoltBody = NewObject<UProphecyJoltBodyComponent>(Sword);
		Sword->AddInstanceComponent(JoltBody);
		JoltBody->RegisterComponent();
	}
	return IsValid(JoltBody) && JoltBody->IsRegistered() && JoltBody->GetOwner() == Sword ? JoltBody.Get() : nullptr;
}

void UProphecySwordComponent::CancelJoltAdmission()
{
	PendingJoltBindId.Invalidate();
	bDropPending = false;
	if (JoltBody)
	{
		JoltBody->OnDeferredEnableCompleted.Remove(JoltEnableDelegate);
		if (JoltBody->IsEnablePending()) JoltBody->DisableBody();
	}
	JoltEnableDelegate.Reset();
}

bool UProphecySwordComponent::ReleaseJoltGrip()
{
    if(!ProphecySwordNoReaction::Apply(JoltBody,false))return false;
	if (JoltBinding && JoltBinding->World.IsValid() && JoltBinding->World->OwnsJoint(JoltBinding->Joint))
	{
		const auto Result = JoltBinding->World->DestroyJoint(JoltBinding->Joint);
		if (!Result.IsSuccess())
		{
			UE_LOG(LogTemp, Error, TEXT("Jolt sword grip cleanup failed: %s"), *Result.Message);
			return false;
		}
	}
	if (JoltBinding && JoltBody && !JoltBody->IsAttachedCollider())
	{
		FProphecyJoltBodyHandle Body;
		if (JoltBody->GetBodyHandle(Body))
		{
			if (!SwordDriveFollower(this,Body,JoltBinding->Hand,FTransform::Identity,false)) return false;
			if (auto* World=JoltBinding->World.Get())
				if (!World->UpdateBodySuppressedPairs(Body,{}).IsSuccess()) return false;
		}
	}
	JoltBinding.Reset();
	return true;
}

bool UProphecySwordComponent::ReleaseJoltBody()
{
	CancelJoltAdmission();
	if (!ReleaseJoltGrip()) return false;
	if (JoltBody)
	{
		JoltBody->DisableBody();
		if (JoltBody->IsJoltBody() || JoltBody->IsReceiverRestorePending()) return false;
	}
	return true;
}

bool UProphecySwordComponent::FinishJoltGrip(UProphecyJoltCharacterComponent& Character, USkeletalMeshComponent& Mesh)
{
	AProphecyAgent* A = Agent();
	if (!A || !IsValid(Sword) || !IsValid(Blade) || !JoltBody
		|| Character.IsSteppingStopped()
		|| !A->IsJoltPhysicalAnimationEnabled() || A->GetJoltCharacterComponent() != &Character
		|| A->GetPoseReferenceMesh() != &Mesh || !Mesh.GetPhysicsAsset()) return false;
	UProphecyJoltWorldSubsystem* World = JoltBody->GetWorldOwner();
	if (!World || World != GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()) return false;
	const FName Bone = Mesh.GetSocketBoneName(A->SwordHandSocket);
	FProphecyJoltBodyHandle Hand, SwordBody;
	FProphecyJoltBodyState HandState;
	FTransform BodyOriginToComponent;
	if (!Character.GetBodyHandle(Bone, Hand) || !JoltBody->GetBodyHandle(SwordBody)
		|| Hand.WorldLifetime != SwordBody.WorldLifetime || !World->ReadBody(Hand, HandState).IsSuccess()
		|| !JoltBody->GetBodyOriginToComponent(BodyOriginToComponent)) return false;
	if (!bPhysicsHold)
	{
		if (!ReleaseJoltGrip()) return false;
		FString Error;
		if (!JoltBody->FollowWelded(Hand, Mesh, A->SwordHandSocket, A->SwordGripTransform, Error))
		{ UE_LOG(LogTemp, Error, TEXT("Attached sword collider failed: %s"), *Error); return false; }
		if (!SetAttachedInertiaScale(A->GetSwordAttachedInertiaScale())) return false;
		JoltBinding.Reset(new FProphecyJoltSwordBinding);
		JoltBinding->World = World;
		JoltBinding->Character = &Character;
		JoltBinding->Hand = Hand;
		RefreshOwnerCollision();
		Blade->AttachToComponent(&Mesh, FAttachmentTransformRules::KeepWorldTransform, A->SwordHandSocket);
		Blade->SetRelativeTransform(A->SwordGripTransform);
		Blade->UpdateComponentToWorld();
		return ProphecySwordNoReaction::Apply(JoltBody,ProphecySwordNoReaction::Desired(A));
	}
	FTransform Anchor = Mesh.GetSocketTransform(A->SwordHandSocket);
	Anchor.SetScale3D(FVector::OneVector);
	FTransform DesiredComponent = GripWorld();
	DesiredComponent.SetScale3D(FVector::OneVector);
	const FTransform DesiredBodyOrigin = BodyOriginToComponent * DesiredComponent;
	FProphecyJoltJointSettings Settings;
	Settings.Type = EProphecyJoltJointType::Fixed;
	Settings.BodyA = Hand;
	Settings.BodyB = SwordBody;
	Settings.FrameA = Anchor.GetRelativeTransform(FTransform(HandState.Rotation, HandState.PositionCm));
	Settings.FrameB = Anchor.GetRelativeTransform(DesiredBodyOrigin);
	Settings.FrameA.SetScale3D(FVector::OneVector);
	Settings.FrameB.SetScale3D(FVector::OneVector);
	Settings.FrameA.NormalizeRotation();
	Settings.FrameB.NormalizeRotation();
	TArray<FProphecyJoltBodyPair> Exclusions;
	const FName Forearm = Mesh.GetParentBone(Bone);
	for (const USkeletalBodySetup* Setup : Mesh.GetPhysicsAsset()->SkeletalBodySetups)
	{
		FProphecyJoltBodyHandle OwnerBody;
		if (!Setup || !Character.GetBodyHandle(Setup->BoneName, OwnerBody)
			|| OwnerBody.WorldLifetime != SwordBody.WorldLifetime) return false;
		if (ProphecySwordAttackCollision::SuppressesSwordOwner(A) || Setup->BoneName == Bone || Setup->BoneName == Forearm)
			Exclusions.Add({ SwordBody, OwnerBody });
	}
	if (!ReleaseJoltGrip()) return false;
	FProphecyJoltJointHandle Joint;
	const auto Result = World->CreateJoint(Settings, Exclusions, Joint);
	if (!Result.IsSuccess())
	{
		UE_LOG(LogTemp, Error, TEXT("Jolt sword fixed grip failed: %s"), *Result.Message);
		return false;
	}
	JoltBinding.Reset(new FProphecyJoltSwordBinding);
	JoltBinding->World = World;
	JoltBinding->Character = &Character;
	JoltBinding->Joint = Joint;
	JoltBinding->Hand = Hand;
	// Offset is derived from the authored grip/socket and captured body origin,
	// never from the currently deflected sword or the actual hand physics target.
	FTransform HandBoneWorld=Mesh.GetSocketTransform(Bone); HandBoneWorld.RemoveScaling();
	FTransform BodyToHand=DesiredBodyOrigin.GetRelativeTransform(HandBoneWorld);
	BodyToHand.RemoveScaling(); BodyToHand.NormalizeRotation();
	if (!SwordDriveFollower(this,SwordBody,Hand,BodyToHand,true))
	{
		ReleaseJoltGrip();
		UE_LOG(LogTemp,Error,TEXT("Could not bind independent sword magnetisation to the hand target."));
		return false;
	}
	ProphecySwordAttackCollision::Refresh(A);
	return ProphecySwordNoReaction::Apply(JoltBody,ProphecySwordNoReaction::Desired(A));
}

bool UProphecySwordComponent::BindJolt(bool bSnapToGrip)
{
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* Mesh = A ? A->GetPoseReferenceMesh() : nullptr;
	UProphecyJoltCharacterComponent* Character = A ? A->GetJoltCharacterComponent() : nullptr;
	FProphecyJoltBodyHandle ExpectedHand;
	if (!Mesh || !Character || Character->IsSteppingStopped()
		|| !Character->GetBodyHandle(Mesh->GetSocketBoneName(A->SwordHandSocket), ExpectedHand)) return false;
	if (PendingJoltBindId.IsValid()) return true;
	if (!EnsureJoltBody()) return false;
	if (JoltBody->IsAttachedCollider() && bPhysicsHold && !ReleaseJoltBody()) return false;
	if (JoltBody->IsJoltBody()) return FinishJoltGrip(*Character, *Mesh);
	const TWeakObjectPtr<AActor> ExpectedSword = Sword;
	const TWeakObjectPtr<UStaticMeshComponent> ExpectedBlade = Blade;
	const TWeakObjectPtr<USkeletalMeshComponent> ExpectedMesh = Mesh;
	const TWeakObjectPtr<UProphecyJoltCharacterComponent> ExpectedCharacter = Character;
	const TWeakObjectPtr<UProphecyJoltBodyComponent> ExpectedBody = JoltBody;
	const auto Intact = [&]()
	{
		return IsValid(this) && ExpectedSword.IsValid() && !ExpectedSword->IsActorBeingDestroyed()
			&& ExpectedBlade.IsValid() && Sword == ExpectedSword.Get() && Blade == ExpectedBlade.Get()
			&& JoltBody == ExpectedBody.Get() && Agent() == A && A->IsJoltPhysicalAnimationEnabled()
			&& A->GetPoseReferenceMesh() == ExpectedMesh.Get() && A->GetJoltCharacterComponent() == ExpectedCharacter.Get();
	};
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	if (!Intact()) return false;
	if (bSnapToGrip) Blade->SetWorldTransform(GripWorld(), false, nullptr, ETeleportType::TeleportPhysics);
	if (!Intact()) return false;
	Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	if (!Intact()) return false;
	Blade->SetSimulatePhysics(true); // Required live source; coordinator admission owns the handoff.
	if (!Intact() || !Blade->IsSimulatingPhysics()) return false;
	// User-approved Jolt policy: omit Chaos MACD and retain the existing CCD setting.
	Blade->BodyInstance.SetUseMACD(false);
	if (bSnapToGrip)
	{
		// Internal capture setup belongs to this controller. Do not dispatch through
		// the generic receiver, which would auto-admit a second owner before ours.
		Blade->UPrimitiveComponent::SetPhysicsLinearVelocity(CarriedLinear);
		Blade->UPrimitiveComponent::SetPhysicsAngularVelocityInRadians(CarriedAngular);
	}
	const FGuid RequestId = FGuid::NewGuid();
	PendingJoltBindId = RequestId;
	JoltEnableDelegate = JoltBody->OnDeferredEnableCompleted.AddWeakLambda(this,
		[this, RequestId, ExpectedSword, ExpectedBlade, ExpectedMesh, ExpectedCharacter, ExpectedBody,
		 ExpectedHand](bool bSucceeded, const FString& Error)
		{
			if (PendingJoltBindId != RequestId || Sword != ExpectedSword.Get() || Blade != ExpectedBlade.Get()
				|| JoltBody != ExpectedBody.Get()) return;
			PendingJoltBindId.Invalidate();
			JoltEnableDelegate.Reset();
			FProphecyJoltBodyHandle CurrentHand;
			const bool bSameHand = ExpectedMesh.IsValid() && ExpectedCharacter.IsValid() && Agent()
				&& ExpectedCharacter->GetBodyHandle(ExpectedMesh->GetSocketBoneName(Agent()->SwordHandSocket), CurrentHand)
				&& CurrentHand.WorldLifetime == ExpectedHand.WorldLifetime && CurrentHand.Slot == ExpectedHand.Slot
				&& CurrentHand.Generation == ExpectedHand.Generation;
			if (bSucceeded && bSameHand && FinishJoltGrip(*ExpectedCharacter, *ExpectedMesh)) return;
			UE_LOG(LogTemp, Error, TEXT("Deferred Jolt sword binding failed: %s"),
				Error.IsEmpty() ? TEXT("The captured hand binding changed or the fixed joint could not be created.") : *Error);
			// Keep the existing receiver, materials and blood even when native activation fails.
			if (ReleaseJoltBody())
			{
				bPhysicsHold = false;
				if (Bind(false)) return;
			}
			bRefreshPending = true;
		});
	FString Error;
	if (!JoltBody->EnableBody(*Blade, Error))
	{
		CancelJoltAdmission();
		UE_LOG(LogTemp, Error, TEXT("Jolt sword body activation failed: %s"), *Error);
		return false;
	}
	if (!Intact()) return false;
	if (JoltBody->IsEnablePending()) return true;
	CancelJoltAdmission(); // Remove only our completion listener; active ownership remains.
	if (FinishJoltGrip(*Character, *Mesh)) return true;
	ReleaseJoltBody();
	return false;
}

bool UProphecySwordComponent::Bind(bool bSnapToGrip)
{
	if (bBinding || bDropPending || (JoltBody && JoltBody->IsReceiverRestorePending())) return false;
	TGuardValue<bool> BindingGuard(bBinding, true);
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* M = A ? A->GetPoseReferenceMesh() : nullptr;
	if (!M || !Sword || !Blade || !Grip || !M->DoesSocketExist(A->SwordHandSocket)) return false;
	if (A->GetJoltCharacterComponent() && A->GetJoltCharacterComponent()->IsKinematicRestorePending()) return false;
	ClearOwnerCollisions(this);
	Grip->BreakConstraint();
	if (BoundMesh != M)
	{
		if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
		BoundMesh = M;
		AddTickPrerequisiteComponent(M);
	}
	if (A->IsJoltPhysicalAnimationEnabled()) return BindJolt(bSnapToGrip);
	if (bPhysicsHold)
	{
		if (!ReleaseJoltBody()) return false;
		const FName Bone = M->GetSocketBoneName(A->SwordHandSocket);
		FBodyInstance* Hand = M->GetBodyInstance(Bone);
		if (!Hand || !Hand->IsValidBodyInstance()) return false;
		Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
		if (bSnapToGrip) Blade->SetWorldTransform(GripWorld(), false, nullptr, ETeleportType::TeleportPhysics);
		Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Blade->SetSimulatePhysics(true);
		if (!Blade->IsSimulatingPhysics()) return false;
		IgnoreOwnerCollisions(this, Blade, A, ProphecySwordAttackCollision::SuppressesSwordOwner(A));
		FTransform Anchor = M->GetSocketTransform(A->SwordHandSocket);
		Anchor.SetScale3D(FVector::OneVector);
		Grip->SetWorldTransform(Anchor);
		Grip->SetConstrainedComponents(M, Bone, Blade, NAME_None);
		// Fixed authored frames, not frames inferred from a deflected current sword.
		Grip->SetConstraintReferenceFrame(EConstraintFrame::Frame1,
			Anchor.GetRelativeTransform(Hand->GetUnrealWorldTransform()));
		FTransform BladeFrame = Anchor.GetRelativeTransform(GripWorld());
		// Chaos reference positions are in scaled body-local coordinates.
		BladeFrame.SetLocation(BladeFrame.GetLocation() * GripWorld().GetScale3D());
		BladeFrame.SetScale3D(FVector::OneVector);
		Grip->SetConstraintReferenceFrame(EConstraintFrame::Frame2, BladeFrame);
		Blade->WakeAllRigidBodies();
	}
	else
	{
		if (!ReleaseJoltBody()) return false;
		Blade->SetSimulatePhysics(false);
		// Chaos owns a moving, non-simulated collider while the socket owns presentation.
		Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Blade->AttachToComponent(M, FAttachmentTransformRules::KeepWorldTransform, A->SwordHandSocket);
		Blade->SetRelativeTransform(A->SwordGripTransform);
		// An unchanged relative transform can early-out after a mode switch has
		// temporarily propagated a different socket pose to attached children.
		Blade->UpdateComponentToWorld();
		IgnoreOwnerCollisions(this, Blade, A, ProphecySwordAttackCollision::SuppressesSwordOwner(A), true);
	}
	bHasPrevious = false;
	ProphecySwordAttackCollision::Refresh(A);
	return true;
}

bool UProphecySwordComponent::ApplyMass(float MassKg)
{
	if (!Blade || !FMath::IsFinite(MassKg) || MassKg <= 0 || !FMath::IsFinite(1.0f / MassKg)) return false;
	if (JoltBody && (JoltBody->IsEnablePending() || JoltBody->IsReceiverRestorePending())) return false;
	if (JoltBody && JoltBody->IsJoltBody() && !JoltBody->IsAttachedCollider())
	{
		FProphecyJoltBodyHandle Handle;
		if (!JoltBody->GetWorldOwner() || !JoltBody->GetBodyHandle(Handle)) return false;
		const auto Result = JoltBody->GetWorldOwner()->SetBodyMassKg(Handle, MassKg);
		if (!Result.IsSuccess()) { UE_LOG(LogTemp, Error, TEXT("Sword mass update failed: %s"), *Result.Message); return false; }
	}
	// Keep the existing UE receiver's mass override in sync for backend changes/re-admission.
	// Neither operation replaces the body, changes its COM, or rewrites its velocity.
	Blade->SetMassOverrideInKg(NAME_None, MassKg, true);
	return true;
}

bool UProphecySwordComponent::SetInertiaScale(float Scale)
{
	return !Sword || (!bDropPending && ApplyMass(BaseMassKg * Scale));
}

bool UProphecySwordComponent::SetAttachedInertiaScale(float Scale)
{
	// Store preferences before equip, during deferred admission, and on other backends.
	// Only an existing welded Jolt collider needs a native update here.
	if (!JoltBody || !JoltBody->IsAttachedCollider()) return true;
	FProphecyJoltBodyHandle Handle;
	if (!JoltBody->GetWorldOwner() || !JoltBody->GetBodyHandle(Handle)) return false;
	const auto Result = JoltBody->GetWorldOwner()->SetWeldedBodyInertiaScale(Handle, Scale);
	if (!Result.IsSuccess()) UE_LOG(LogTemp, Error, TEXT("Attached sword inertia update failed: %s"), *Result.Message);
	return Result.IsSuccess();
}

void UProphecySwordComponent::RefreshOwnerCollision()
{
	AProphecyAgent* A = Agent();
	if (!A || !Sword || !Blade || bDropPending) return;
	ProphecySwordAttackCollision::Refresh(A);
	// Deferred admission reads the current attack state when it creates the grip.
	if (PendingJoltBindId.IsValid()) return;
	if (JoltBinding)
	{
		FProphecyJoltBodyHandle SwordBody;
		auto* Character = JoltBinding->Character.Get();
		auto* World = JoltBinding->World.Get();
		if (!World || !Character || !BoundMesh || !BoundMesh->GetPhysicsAsset()
			|| !JoltBody || !JoltBody->GetBodyHandle(SwordBody)) return;
		TArray<FProphecyJoltBodyPair> Pairs;
		Pairs.Add({ SwordBody, JoltBinding->Hand });
		// The gripping forearm stays excluded for the entire held lifetime, including
		// Hit/end and a broken diagnostic grip. Drop releases these owned pairs.
		FProphecyJoltBodyHandle Forearm;
		if (Character->GetBodyHandle(BoundMesh->GetParentBone(BoundMesh->GetSocketBoneName(A->SwordHandSocket)), Forearm))
			Pairs.Add({ SwordBody, Forearm });
		if (ProphecySwordAttackCollision::SuppressesSwordOwner(A))
		{
			for (const USkeletalBodySetup* Setup : BoundMesh->GetPhysicsAsset()->SkeletalBodySetups)
			{
				FProphecyJoltBodyHandle Body;
				if (Setup && Character->GetBodyHandle(Setup->BoneName, Body)) Pairs.Add({ SwordBody, Body });
			}
		}
		const auto Result = JoltBody->IsAttachedCollider() || !JoltBinding->Joint.IsSet()
			? World->UpdateBodySuppressedPairs(SwordBody, Pairs)
			: World->UpdateJointSuppressedPairs(JoltBinding->Joint, Pairs);
		if (!Result.IsSuccess()) UE_LOG(LogTemp, Error, TEXT("Sword owner collision update failed: %s"), *Result.Message);
	}
	else
	{
		ClearOwnerCollisions(this);
		IgnoreOwnerCollisions(this, Blade, A, ProphecySwordAttackCollision::SuppressesSwordOwner(A), !bPhysicsHold);
	}
}

bool UProphecySwordComponent::SetSimulated(bool bSimulated)
{
	if (!Sword || !Blade || bBinding || bDropPending || PendingJoltBindId.IsValid()
		|| (JoltBody && JoltBody->IsReceiverRestorePending())) return false;
	if (bPhysicsHold == bSimulated) return true;
	const bool OldMode = bPhysicsHold;
	bPhysicsHold = bSimulated;
	if (!Bind(bSimulated)) { bPhysicsHold = OldMode; if (!Bind(false)) bRefreshPending = true; return false; }
	if (bSimulated)
	{
		if (JoltBody && JoltBody->IsJoltBody())
		{
			FString Error;
			if (!JoltBody->SetBodyVelocity(CarriedLinear, CarriedAngular, true, Error))
			{
				UE_LOG(LogTemp, Error, TEXT("Jolt sword velocity handoff failed: %s"), *Error);
				bPhysicsHold = OldMode;
				if (!Bind(false)) bRefreshPending = true;
				return false;
			}
		}
		else if (!PendingJoltBindId.IsValid())
		{
			Blade->UPrimitiveComponent::SetPhysicsLinearVelocity(CarriedLinear);
			Blade->UPrimitiveComponent::SetPhysicsAngularVelocityInRadians(CarriedAngular);
		}
	}
	return true;
}

void UProphecySwordComponent::RefreshHandConstraint()
{
	if (!Sword || bDropPending) return;
	AProphecyAgent* A = Agent();
	if (bBinding || (JoltBody && JoltBody->IsReceiverRestorePending())
		|| (A && A->GetJoltCharacterComponent() && A->GetJoltCharacterComponent()->IsKinematicRestorePending()))
	{ bRefreshPending = true; return; }
	bRefreshPending = false;
	if (!Bind(false))
	{
		UE_LOG(LogTemp, Error, TEXT("Sword backend refresh failed; retaining the item in attached mode."));
		bPhysicsHold = false;
		if (!Bind(false)) bRefreshPending = true;
	}
}

AActor* UProphecySwordComponent::FinishDrop()
{
	ProphecySwordAttackCollision::ReleaseSword(Agent());
	ClearOwnerCollisions(this);
	if (Grip) { Grip->BreakConstraint(); Grip->DestroyComponent(); Grip = nullptr; }
	AActor* Result = Sword;
	Result->SetOwner(nullptr);
	if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
	BoundMesh = nullptr;
	// The component belongs to the sword actor and remains registered after these held references clear.
	JoltBody = nullptr;
	Sword = nullptr;
	Blade = nullptr;
	bPhysicsHold = false;
	bDropPending = false;
	bRefreshPending = false;
	PendingJoltBindId.Invalidate();
	JoltEnableDelegate.Reset();
	bHasPrevious = false;
	return Result;
}

AActor* UProphecySwordComponent::Drop()
{
	if (!IsValid(Sword) || !IsValid(Blade) || bBinding
		|| (JoltBody && JoltBody->IsReceiverRestorePending())) return nullptr;
	if (bDropPending) return Sword;
	AProphecyAgent* A = Agent();
	if (A && A->GetJoltCharacterComponent() && A->GetJoltCharacterComponent()->IsKinematicRestorePending()) return nullptr;
	TGuardValue<bool> BindingGuard(bBinding, true);
	// Restore the hand shape and re-admit the sword as an independent dynamic on drop.
	if (JoltBody && JoltBody->IsAttachedCollider() && !ReleaseJoltBody()) return nullptr;
	// Held assistance ends on release, without changing the carried linear/angular velocities.
	if (!ApplyMass(BaseMassKg)) return nullptr;
	if (JoltBody && JoltBody->IsJoltBody())
	{
		FProphecyJoltBodyState Current;
		if (JoltBody->IsSteppingStopped() || !JoltBody->GetBodyState(Current) || !ReleaseJoltGrip()) return nullptr;
		CancelJoltAdmission();
		return FinishDrop(); // Native V/W, gravity and registration are unchanged.
	}
	const FVector Linear = bPhysicsHold ? Blade->GetPhysicsLinearVelocity() : CarriedLinear;
	const FVector Angular = bPhysicsHold ? Blade->GetPhysicsAngularVelocityInRadians() : CarriedAngular;
	CancelJoltAdmission();
	if (!ReleaseJoltGrip()) return nullptr;
	ClearOwnerCollisions(this);
	if (Grip) Grip->BreakConstraint();
	const TWeakObjectPtr<AActor> ExpectedSword = Sword;
	const TWeakObjectPtr<UStaticMeshComponent> ExpectedBlade = Blade;
	const auto Intact = [&]()
	{
		return IsValid(this) && ExpectedSword.IsValid() && !ExpectedSword->IsActorBeingDestroyed()
			&& ExpectedBlade.IsValid() && Sword == ExpectedSword.Get() && Blade == ExpectedBlade.Get();
	};
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	if (!Intact()) return nullptr;
	Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	if (!Intact()) return nullptr;
	Blade->SetEnableGravity(true);
	Blade->SetSimulatePhysics(true);
	if (!Intact()) return nullptr;
	// Stage the live source for the managed handoff below. Calling the derived
	// Blueprint receiver here auto-admits/freezes it before EnsureJoltBody runs.
	Blade->UPrimitiveComponent::SetPhysicsLinearVelocity(Linear);
	Blade->UPrimitiveComponent::SetPhysicsAngularVelocityInRadians(Angular);
	Blade->WakeAllRigidBodies();
	if (!Intact()) return nullptr;
	if (!A || !A->IsJoltPhysicalAnimationEnabled()) return FinishDrop();
	const auto RestoreAttached = [&]()
	{
		if (!Intact()) return;
		CancelJoltAdmission();
		bPhysicsHold = false;
		TGuardValue<bool> AllowBind(bBinding, false);
		if (!Bind(false)) bRefreshPending = true;
	};
	if (!EnsureJoltBody()) { RestoreAttached(); return nullptr; }
	// An attached sword can be dropped directly without ever going through BindJolt.
	Blade->BodyInstance.SetUseMACD(false);
	const TWeakObjectPtr<UProphecyJoltBodyComponent> ExpectedBody = JoltBody;
	const FGuid RequestId = FGuid::NewGuid();
	PendingJoltBindId = RequestId;
	bDropPending = true;
	JoltEnableDelegate = JoltBody->OnDeferredEnableCompleted.AddWeakLambda(this,
		[this, ExpectedSword, ExpectedBlade, ExpectedBody, RequestId](bool bSucceeded, const FString& Error)
		{
			if (PendingJoltBindId != RequestId || !bDropPending || Sword != ExpectedSword.Get()
				|| Blade != ExpectedBlade.Get() || JoltBody != ExpectedBody.Get()) return;
			PendingJoltBindId.Invalidate();
			JoltEnableDelegate.Reset();
			bDropPending = false;
			if (bSucceeded && ExpectedBody.IsValid() && ExpectedBody->IsJoltBody()) { FinishDrop(); return; }
			UE_LOG(LogTemp, Error, TEXT("Deferred Jolt sword drop failed; the existing sword stays held: %s"), *Error);
			bPhysicsHold = false;
			if (!Bind(false)) bRefreshPending = true;
		});
	FString Error;
	if (!JoltBody->EnableBody(*Blade, Error))
	{
		UE_LOG(LogTemp, Error, TEXT("Jolt sword drop failed; restored held attachment: %s"), *Error);
		RestoreAttached();
		return nullptr;
	}
	if (!Intact()) return nullptr;
	if (JoltBody->IsEnablePending()) return Sword; // Accepted request; held references survive until success.
	CancelJoltAdmission();
	return FinishDrop();
}

void UProphecySwordComponent::Disappear()
{
	ProphecySwordAttackCollision::ReleaseSword(Agent());
	CancelJoltAdmission();
	ReleaseJoltBody(); // Generic grip is always removed before its native body.
	ClearOwnerCollisions(this);
	if (Grip) { Grip->BreakConstraint(); Grip->DestroyComponent(); Grip = nullptr; }
	if (Sword) Sword->Destroy();
	Sword = nullptr;
	Blade = nullptr;
	JoltBody = nullptr;
	if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
	BoundMesh = nullptr;
	bPhysicsHold = false;
	bRefreshPending = false;
	bHasPrevious = false;
}

void UProphecySwordComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	ProphecySwordNoReaction::EnabledAgents.Remove(Agent());
	ProphecySwordNoReaction::Automatic.Remove(Agent());
	ProphecySwordCooldown::Remove(Agent());
	ProphecySwordAttackCollision::CollisionDisabled.Remove(Agent());
	ProphecySwordAttackCollision::OwnCollisionDisabled.Remove(Agent());
	ProphecySwordAttackCollision::End(Agent());
	Disappear();
	Super::EndPlay(Reason);
}

void UProphecySwordComponent::TickComponent(float Dt, ELevelTick Type, FActorComponentTickFunction* Function)
{
	Super::TickComponent(Dt, Type, Function);
	if (!IsValid(Sword) || !IsValid(Blade)) { Disappear(); return; }
	AProphecyAgent* A = Agent();
	if (!A) return;
	if (!bDropPending && (bRefreshPending || BoundMesh != A->GetPoseReferenceMesh()
		|| (!PendingJoltBindId.IsValid()
			&& A->IsJoltPhysicalAnimationEnabled() != bool(JoltBinding)))) RefreshHandConstraint();
	if (!IsValid(Sword) || !IsValid(Blade)) return;
	const FTransform Current = Blade->GetComponentTransform();
	if (bHasPrevious && Dt > SMALL_NUMBER)
	{
		CarriedLinear = (Current.GetLocation() - PreviousWorld.GetLocation()) / Dt;
		FQuat Delta = Current.GetRotation() * PreviousWorld.GetRotation().Inverse();
		if (Delta.W < 0) Delta = Delta * -1.;
		FVector Axis; double Angle;
		Delta.ToAxisAndAngle(Axis, Angle);
		CarriedAngular = Axis * Angle / Dt;
	}
	PreviousWorld = Current;
	bHasPrevious = true;
}

bool UProphecySwordComponent::GetHeldBodyState(FTransform& WorldTransform, FVector& LinearVelocity,
	FVector& AngularVelocity, bool& bSimulating) const
{
	WorldTransform = FTransform::Identity;
	LinearVelocity = AngularVelocity = FVector::ZeroVector;
	bSimulating = false;
	if (!IsValid(Sword) || !IsValid(Blade) || Sword->IsActorBeingDestroyed()) return false;
	if (JoltBody && JoltBody->IsJoltBody())
	{
		FProphecyJoltBodyState State;
		if (!JoltBody->GetBodyState(State)) return false;
		WorldTransform = FTransform(State.Rotation, State.PositionCm);
		LinearVelocity = State.CenterOfMassVelocityCmPerSecond;
		AngularVelocity = State.AngularVelocityRadiansPerSecond;
		bSimulating = State.bDynamic;
		return true;
	}
	if (Blade->IsSimulatingPhysics())
	{
		const FBodyInstance* Body = Blade->GetBodyInstance();
		if (!Body || !Body->IsValidBodyInstance()) return false;
		WorldTransform = Body->GetUnrealWorldTransform();
		LinearVelocity = Body->GetUnrealWorldVelocity();
		AngularVelocity = Body->GetUnrealWorldAngularVelocityInRadians();
		bSimulating = true;
		return true;
	}
	WorldTransform = Blade->GetComponentTransform();
	if (bHasPrevious)
	{
		// Reuse existing carried-motion samples; convert component-origin velocity to COM.
		AngularVelocity = CarriedAngular;
		LinearVelocity = CarriedLinear + FVector::CrossProduct(CarriedAngular,
			Blade->GetCenterOfMass() - WorldTransform.GetLocation());
	}
	return true;
}

namespace
{
	UProphecySwordComponent* SwordController(AProphecyAgent* A, bool bCreate)
	{
		auto* C = A->FindComponentByClass<UProphecySwordComponent>();
		if (!C && bCreate)
		{
			C = NewObject<UProphecySwordComponent>(A);
			A->AddInstanceComponent(C);
			C->RegisterComponent();
		}
		return C;
	}
}

bool AProphecyAgent::EquipSword(bool bSimulated) { return SwordController(this, true)->Equip(bSimulated); }
bool UProphecySwordPhysicsLibrary::SetSwordNoReaction(AProphecyAgent* Agent,bool Enabled)
{
	if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown)return false;
	using namespace ProphecySwordNoReaction;
	// Event-only preference; do not create a component or add a tick before equip.
	const bool WasEnabled=EnabledAgents.Contains(Agent);
	if(Enabled){EnabledAgents.Add(Agent);EnsureCleanup();}else EnabledAgents.Remove(Agent);
	if(!Refresh(Agent)){if(WasEnabled)EnabledAgents.Add(Agent);else EnabledAgents.Remove(Agent);return false;}
	return true;
}
bool UProphecySwordPhysicsLibrary::SetSlashSwordNoReaction(AProphecyAgent* Agent,bool Enabled,float Strength)
{
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown)return false;
    if(!FMath::IsFinite(Strength))return false;
    Strength=FMath::Clamp(Strength,0.f,1.f);
    using namespace ProphecySwordNoReaction;
    const auto* Previous=Automatic.Find(Agent);
    const bool WasEnabled=Previous!=nullptr;
    const FAutomatic Saved=Previous?*Previous:FAutomatic{};
    if(Enabled)
    {
        if(!Previous)
        {
            FName Name;bool Half,IsArmed,Hit;int32 Frame;
            FAutomatic State;
            if(Agent->GetNNAttackState(Name,Half,IsArmed,Hit,Frame))
            {
                State.Slash=Name.ToString().StartsWith(TEXT("slash"),ESearchCase::IgnoreCase);
                State.Armed=IsArmed || ProphecySwordCooldown::Qualified.Contains(Agent);
            }
            Automatic.Add(Agent,State);
        }
        Automatic.FindChecked(Agent).Strength=Strength;
        EnsureCleanup();
    }
    else Automatic.Remove(Agent);
    if(Refresh(Agent))return true;
    if(WasEnabled)Automatic.Add(Agent,Saved);else Automatic.Remove(Agent);
    return false;
}
void UProphecySwordPhysicsLibrary::SetOwnSwordCollisionEnabled(AProphecyAgent* Agent, bool Enabled)
{
	if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return;
	using namespace ProphecySwordAttackCollision;
	if (Enabled == !OwnCollisionDisabled.Contains(Agent)) return;
	if (Enabled) OwnCollisionDisabled.Remove(Agent);
	else { OwnCollisionDisabled.Add(Agent);EnsureOwnCollisionCleanup(); }
	// Do not create/tick a sword component just to retain a preference before equip.
	RefreshOwner(Agent);
}
void UProphecySwordPhysicsLibrary::SetSwordCollisionEnabled(AProphecyAgent* Agent, bool Enabled)
{
	if (!IsValid(Agent)) return;
	using namespace ProphecySwordAttackCollision;
	if (Enabled == !CollisionDisabled.Contains(Agent)) return;
	if (Enabled) CollisionDisabled.Remove(Agent);
	else
	{
		// Ensure cleanup even if configured before the first equip.
		SwordController(Agent, true);
		CollisionDisabled.Add(Agent);
	}
	Refresh(Agent);
	if (Enabled && !Agent->IsSwordAttackActive()) Gates.Remove(Agent);
}
bool AProphecyAgent::SetSwordAttachedInertiaScale(float Scale)
{
	if (!FMath::IsFinite(Scale) || Scale < 0.0f) return false;
	if (Scale == SwordAttachedInertiaScale) return true;
	if (auto* C = SwordController(this, false); C && !C->SetAttachedInertiaScale(Scale)) return false;
	SwordAttachedInertiaScale = Scale;
	return true;
}

bool UProphecySwordComponent::BreakGripConstraint()
{
	if (!IsInGameThread() || !bPhysicsHold || bBinding || bDropPending || PendingJoltBindId.IsValid()
		|| !JoltBinding || !JoltBody || !JoltBody->IsJoltBody() || JoltBody->IsAttachedCollider()
		|| JoltBody->IsSteppingStopped()) return false;
	auto* World=JoltBinding->World.Get();
	if (!World) return false;
	if (JoltBinding->Joint.IsSet())
	{
		if (!World->DestroyJoint(JoltBinding->Joint).IsSuccess()) return false;
		JoltBinding->Joint={};
	}
	// Preserve the binding and independent drive; an invalid joint is intentional.
	// Migrate the usual hand/attack exclusions to the body, without modifying channels.
	RefreshOwnerCollision();
	return true;
}

bool UProphecySwordPhysicsLibrary::BreakSwordGripConstraint(AProphecyAgent* Agent)
{
	if (!IsValid(Agent)) return false;
	auto* Controller=Agent->FindComponentByClass<UProphecySwordComponent>();
	return Controller && Controller->BreakGripConstraint();
}

bool AProphecyAgent::SetSwordInertiaScale(float Scale)
{
	if (!FMath::IsFinite(Scale) || Scale <= 0 || !FMath::IsFinite(1.0f / Scale)) return false;
	if (Scale == SwordInertiaScale) return true;
	if (auto* C = SwordController(this, false); C && !C->SetInertiaScale(Scale)) return false;
	SwordInertiaScale = Scale;
	return true;
}
#include "ProphecyPhysicalContext.h"
#include "ProphecySpecialSolver.h"
#include "ProphecyAttackControlLibrary.h"
#include "ProphecyJoltPHATSweepLibrary.h"
void AProphecyAgent::NotifySwordAttackState(bool bAttacking,int64 EntryTicks)
{
    ProphecySpecialSolver::AttackChanged(this,bAttacking);
    if (bAttacking)
    {
        FName Attack;bool Half,Armed,Hit;int32 Frame;
        if (GetNNAttackState(Attack,Half,Armed,Hit,Frame))
        {
            ProphecySwordAttackCollision::SelectSlashSweep(this,Attack);
        }
        else UProphecyJoltPHATSweepLibrary::SetAttackParts(this,{},nullptr);
    }
	// Event-only reflected dispatch avoids a new cross-DLL import during Live Coding.
	// The plugin owns configuration versus effective activation; BeginPlay/Tick setters
	// cannot accidentally leave sweeps running after this attack ends.
	struct FSweepAttackState { AActor* Agent; bool Attacking; } SweepState{this, bAttacking};
	auto* SweepLibrary = FindObjectChecked<UClass>(nullptr,
		TEXT("/Script/ProphecyJolt.ProphecyJoltPHATSweepLibrary"))->GetDefaultObject();
	SweepLibrary->ProcessEvent(SweepLibrary->FindFunctionChecked(TEXT("NotifyAttackState")), &SweepState);
	if (!bAttacking) ProphecySwordAttackCollision::End(this);
	if (bSwordAttackActive == bAttacking) return;
	bSwordAttackActive = bAttacking;
	if (bAttacking)
	{
		FName Family;bool Half,Armed,Hit;int32 Frame;
		if (GetNNAttackState(Family,Half,Armed,Hit,Frame)) ProphecySwordAttackCollision::Begin(this,Family,EntryTicks);
	}
	ProphecyPhysicalContext::AttackChanged(this);
	if (auto* C = SwordController(this, false)) C->RefreshOwnerCollision();
}
bool AProphecyAgent::SetSwordSimulated(bool bSimulated)
{
	UProphecySwordComponent* C = SwordController(this, false);
	return C && C->SetSimulated(bSimulated);
}
AActor* AProphecyAgent::DropSword()
{
	UProphecySwordComponent* C = SwordController(this, false);
	return C ? C->Drop() : nullptr;
}
void AProphecyAgent::HideSword()
{
	if (UProphecySwordComponent* C = SwordController(this, false)) C->Disappear();
}
AActor* AProphecyAgent::GetHeldSword() const
{
	const UProphecySwordComponent* C = FindComponentByClass<UProphecySwordComponent>();
	return C ? C->GetSword() : nullptr;
}
bool AProphecyAgent::IsSwordSimulated() const
{
	const UProphecySwordComponent* C = FindComponentByClass<UProphecySwordComponent>();
	return C && C->IsSimulated();
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySlashSwordNoReactionTest,"Prophecy.Sword.SlashNoReactionGate",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySlashSwordNoReactionTest::RunTest(const FString&)
{
    using namespace ProphecySwordNoReaction;
    auto* World=UWorld::CreateWorld(EWorldType::Game,false);if(!World)return false;
    auto* A=World->SpawnActor<AProphecyAgent>();auto* D=World->SpawnActor<AProphecyAgent>();
    auto* Other=World->SpawnActor<AProphecyAgent>();
    if(!A || !D || !Other){World->DestroyWorld(false);return false;}
    ProphecyDefenseArmedGate::SetVictim(A,D);
    TestFalse(TEXT("Default disabled"),Desired(A)!=0.f);
    TestTrue(TEXT("Can configure before equipping"),UProphecySwordPhysicsLibrary::SetSlashSwordNoReaction(A,true));
    for(const TCHAR* Name:{TEXT("slashL"),TEXT("slashLU"),TEXT("slashLD"),TEXT("slashR"),TEXT("slashRU"),TEXT("slashRD")})
    {
        End(A);Family(A,FName(Name),false);
        TestFalse(TEXT("Wind-up remains normal"),Desired(A)!=0.f);
        Armed(A);TestTrue(TEXT("First Armed enables slash"),Desired(A)!=0.f);
        Family(A,FName(Name),false);TestTrue(TEXT("Armed remains latched"),Desired(A)!=0.f);
        UProphecySwordPhysicsLibrary::SetSlashSwordNoReaction(A,true);
        TestTrue(TEXT("Repeated enable preserves phase"),Desired(A)!=0.f);
        for(bool Dodge:{false,true})
        {
            ProphecyDefenseCollision::Start(D,A,FName(Name),Dodge);
            TestFalse(TEXT("Active parry/dodge overrides automatic mode"),Desired(A)!=0.f);
            UProphecySwordPhysicsLibrary::SetSwordNoReaction(A,true);
            TestTrue(TEXT("Explicit manual override preserved"),Desired(A)!=0.f);
            UProphecySwordPhysicsLibrary::SetSwordNoReaction(A,false);
            TestFalse(TEXT("Clearing manual restores automatic defense gate"),Desired(A)!=0.f);
            ProphecyDefenseCollision::Stop(D);
            TestTrue(TEXT("Defense exit restores an ongoing armed slash"),Desired(A)!=0.f);
        }
        End(A);TestFalse(TEXT("Attack end clears immediately"),Desired(A)!=0.f);
    }
    for(const TCHAR* Name:{TEXT("pike"),TEXT("jabR"),TEXT("hookR"),TEXT("overR")})
    {End(A);Family(A,FName(Name),false);Armed(A);TestFalse(TEXT("Non-slash excluded"),Desired(A)!=0.f);}
    Family(A,TEXT("slashL"),true);
    ProphecyDefenseCollision::Start(Other,A,TEXT("slashL"),false);
    TestTrue(TEXT("Unrelated defender does not replace assigned victim"),Desired(A)!=0.f);
    ProphecyDefenseArmedGate::SetVictim(A,nullptr);
    TestFalse(TEXT("No assigned victim uses active defenses against attacker"),Desired(A)!=0.f);
    ProphecyDefenseCollision::Stop(Other);
    TestTrue(TEXT("Unassigned defense exit restores slash"),Desired(A)!=0.f);
    UProphecySwordPhysicsLibrary::SetSlashSwordNoReaction(A,true,.35f);
    TestEqual(TEXT("Fractional strength during slash"),Desired(A),.35f);
    ProphecyDefenseCollision::Start(D,A,TEXT("slashL"),true);
    TestEqual(TEXT("Defense fully suspends fractional strength"),Desired(A),0.f);
    ProphecyDefenseCollision::Stop(D);
    TestEqual(TEXT("Defense exit restores fractional setting"),Desired(A),.35f);
    End(A);Family(A,TEXT("slashR"),false);Armed(A);
    TestEqual(TEXT("Strength survives attack boundaries"),Desired(A),.35f);
    UProphecySwordPhysicsLibrary::SetSwordNoReaction(A,true);
    TestEqual(TEXT("Manual override remains full strength"),Desired(A),1.f);
    UProphecySwordPhysicsLibrary::SetSwordNoReaction(A,false);
    TestEqual(TEXT("Manual release restores fractional mode"),Desired(A),.35f);
    UProphecySwordPhysicsLibrary::SetSlashSwordNoReaction(A,true,0.f);
    TestEqual(TEXT("Zero strength gives normal response"),Desired(A),0.f);
    UProphecySwordPhysicsLibrary::SetSlashSwordNoReaction(A,false);
    TestFalse(TEXT("Disable removes automatic effect immediately"),Desired(A)!=0.f);
    TestFalse(TEXT("Disable releases preference"),Automatic.Contains(A));
    ProphecyDefenseArmedGate::RemoveAgent(A);
    World->DestroyWorld(false);World->MarkAsGarbage();return !HasAnyErrors();
}
#endif
