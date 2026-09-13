#include "ProphecyPhysicalBlendSubsystem.h"

#include "ProphecyNNLocomotionManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

namespace
{
	bool ValidRequest(FVector2f Target, float Duration)
	{
		return FMath::IsFinite(Target.X) && FMath::IsFinite(Target.Y) && FMath::IsFinite(Duration);
	}

	// Hierarchy/PHAT discovery is request-time only, never part of the active update loop.
	TArray<FName> Descendants(AProphecyAgent& Agent, FName Parent, bool bIncludeParent, bool bFeedback)
	{
		TArray<FName> Result;
		const auto* Mesh = Agent.GetPoseReferenceMesh();
		const auto* Asset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
		if (!Asset) return Result;
		const auto& Ref = Asset->GetRefSkeleton();
		const int32 ParentIndex = Ref.FindBoneIndex(Parent);
		if (ParentIndex == INDEX_NONE) return Result;
		const auto* Physics = Mesh->GetPhysicsAsset();
		for (int32 Index = 0; Index < Ref.GetNum(); ++Index)
		{
			if (Index == ParentIndex && !bIncludeParent) continue;
			int32 Cursor = Index;
			while (Cursor != INDEX_NONE && Cursor != ParentIndex) Cursor = Ref.GetParentIndex(Cursor);
			if (Cursor == INDEX_NONE) continue;
			const FName Bone = Ref.GetBoneName(Index);
			FProphecyPhysicalFeedbackToleranceSettings Feedback;
			if (bFeedback ? Agent.GetPhysicalFeedbackTolerance(Bone, Feedback)
				: Physics && Physics->FindBodyIndex(Bone) != INDEX_NONE)
			{
				Result.Add(Bone);
			}
		}
		return Result;
	}
}

bool UProphecyPhysicalBlendSubsystem::DoesSupportWorldType(EWorldType::Type Type) const
{
	return Type == EWorldType::Game || Type == EWorldType::PIE || Type == EWorldType::GamePreview;
}

void UProphecyPhysicalBlendSubsystem::RefreshCallback()
{
	if (ActiveAgents.IsEmpty())
	{
		FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);
		TickHandle.Reset();
	}
	else if (!TickHandle.IsValid())
	{
		TickHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this, &ThisClass::Advance);
	}
}

void UProphecyPhysicalBlendSubsystem::Clear()
{
	ActiveAgents.Reset();
	RefreshCallback();
}

void UProphecyPhysicalBlendSubsystem::OnWorldEndPlay(UWorld& InWorld)
{
	bEnding = true;
	Clear();
	Super::OnWorldEndPlay(InWorld);
}

void UProphecyPhysicalBlendSubsystem::Deinitialize()
{
	bEnding = true;
	Clear();
	Super::Deinitialize();
}

bool UProphecyPhysicalBlendSubsystem::Start(AProphecyAgent& Agent, FName Bone,
	EProphecyPhysicalBlend Kind, FVector2f Target, float Duration)
{
	if (bEnding || Agent.GetWorld() != GetWorld() || Agent.IsActorBeingDestroyed() || Bone.IsNone()
		|| !ValidRequest(Target, Duration)) return false;
	Target.X = FMath::Max(0.0f, Target.X);
	Target.Y = FMath::Max(0.0f, Target.Y);
	FVector2f Start;
	if (Kind == EProphecyPhysicalBlend::Feedback)
	{
		FProphecyPhysicalFeedbackToleranceSettings Settings;
		if (!Agent.GetPhysicalFeedbackTolerance(Bone, Settings)) return false;
		Start = FVector2f(Settings.LinearToleranceCm, Settings.AngularToleranceDegrees);
	}
	else
	{
		const auto* Mesh = Agent.GetPoseReferenceMesh();
		const auto* Asset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
		if (!Asset || Asset->FindBodyIndex(Bone) == INDEX_NONE) return false;
		FProphecyBodyMagnetizationSettings Settings;
		Agent.GetBodyMagnetizationSettings(Bone, Settings);
		Start = Settings.bMagnetizationEnabled
			? FVector2f(Settings.LinearStrengthScale, Settings.AngularStrengthScale) : FVector2f::ZeroVector;
	}
	if (!ValidRequest(Start, Duration)) return false;
	Start.X = FMath::Max(0.0f, Start.X);
	Start.Y = FMath::Max(0.0f, Start.Y);
	const FVector2f Initial = Duration <= 0.0f ? Target : Start;
	// These setters also cancel the previous blend. Allocate map entries before ticking.
	if (Kind == EProphecyPhysicalBlend::Feedback)
	{
		if (!Agent.SetPhysicalFeedbackTolerance(Bone, Initial.X, Initial.Y)) return false;
	}
	else
		Agent.SetBodyMagnetization(Bone, true, Initial.X, Initial.Y);
	if (Duration <= 0.0f || Start == Target) return true;
	auto* Entry = ActiveAgents.FindByPredicate([&](const auto& E) { return E.Agent == &Agent; });
	if (!Entry)
	{
		Entry = &ActiveAgents.AddDefaulted_GetRef();
		Entry->Agent = &Agent;
	}
	Entry->Blends.Add({Bone, Kind, Start, Target, 0.0, double(Duration)});
	RefreshCallback();
	return true;
}

void UProphecyPhysicalBlendSubsystem::Cancel(AProphecyAgent& Agent, FName Bone, EProphecyPhysicalBlend Kind)
{
	for (int32 Index = 0; Index < ActiveAgents.Num(); ++Index)
	{
		auto& Entry = ActiveAgents[Index];
		if (Entry.Agent != &Agent) continue;
		Entry.Blends.RemoveAllSwap([&](const auto& B) { return B.Kind == Kind && (Bone.IsNone() || B.Bone == Bone); }, EAllowShrinking::No);
		if (Entry.Blends.IsEmpty()) ActiveAgents.RemoveAtSwap(Index, 1, EAllowShrinking::No);
		RefreshCallback();
		break;
	}
}

void UProphecyPhysicalBlendSubsystem::RemoveAgent(AProphecyAgent& Agent)
{
	ActiveAgents.RemoveAllSwap([&](const auto& E) { return E.Agent == &Agent; }, EAllowShrinking::No);
	RefreshCallback();
}

void UProphecyPhysicalBlendSubsystem::Advance(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
	if (World != GetWorld() || World->IsPaused() || TickType == LEVELTICK_ViewportsOnly
		|| !FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f) return;
	TRACE_CPUPROFILER_EVENT_SCOPE(ProphecyPhysicalBlends);
	for (int32 Index = ActiveAgents.Num() - 1; Index >= 0; --Index)
	{
		auto& Entry = ActiveAgents[Index];
		auto* Agent = Entry.Agent.Get();
		if (!Agent || Agent->IsActorBeingDestroyed())
		{
			ActiveAgents.RemoveAtSwap(Index, 1, EAllowShrinking::No);
			continue;
		}
		const double Delta = double(DeltaSeconds) * Agent->CustomTimeDilation;
		if (!FMath::IsFinite(Delta) || Delta <= 0.0) continue;
		AProphecyNNLocomotionManager* Manager = nullptr;
		if (Entry.Blends.ContainsByPredicate([](const auto& B) { return B.Kind == EProphecyPhysicalBlend::Feedback; }))
		{
			const auto Handle = Agent->GetAgentHandle();
			Manager = Entry.Manager.Get();
			if (Handle != Entry.ManagerHandle || !Manager || Manager->ResolveAgent(Handle) != Agent)
			{
				Manager = nullptr;
				if (Handle.IsValid())
				{
					for (TActorIterator<AProphecyNNLocomotionManager> It(World); It; ++It)
						if (It->ResolveAgent(Handle) == Agent) { Manager = *It; break; }
				}
				Entry.Manager = Manager;
				Entry.ManagerHandle = Handle;
			}
		}
		for (int32 BlendIndex = Entry.Blends.Num() - 1; BlendIndex >= 0; --BlendIndex)
		{
			auto& Blend = Entry.Blends[BlendIndex];
			Blend.Elapsed = FMath::Min(Blend.Duration, Blend.Elapsed + Delta);
			const double T = Blend.Elapsed / Blend.Duration;
			const float Alpha = float(T * T * (3.0 - 2.0 * T));
			const FVector2f Value = Blend.Elapsed >= Blend.Duration ? Blend.Target : FMath::Lerp(Blend.Start, Blend.Target, Alpha);
			if (Blend.Kind == EProphecyPhysicalBlend::Magnetization)
			{
				if (auto* Settings = Agent->BodyMagnetizationSettings.Find(Blend.Bone))
				{
					Settings->LinearStrengthScale = Value.X;
					Settings->AngularStrengthScale = Value.Y;
					Agent->ApplyHalfSimulationBodyStrength(Blend.Bone);
				}
			}
			else
			{
				if (auto* Settings = Agent->PhysicalFeedbackTolerances.Find(Blend.Bone))
				{
					Settings->LinearToleranceCm = Value.X;
					Settings->AngularToleranceDegrees = Value.Y;
				}
				if (Manager) Manager->SetAgentPhysicalFeedbackTolerance(Entry.ManagerHandle, Blend.Bone, Value.X, Value.Y);
			}
			if (Blend.Elapsed >= Blend.Duration) Entry.Blends.RemoveAtSwap(BlendIndex, 1, EAllowShrinking::No);
		}
		if (Entry.Blends.IsEmpty()) ActiveAgents.RemoveAtSwap(Index, 1, EAllowShrinking::No);
	}
	RefreshCallback();
}

bool AProphecyAgent::BlendBodyMagnetization(FName BoneName, float Linear, float Angular, float Duration)
{
	auto* Blends = GetWorld() ? GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>() : nullptr;
	return Blends && Blends->Start(*this, BoneName, EProphecyPhysicalBlend::Magnetization, FVector2f(Linear, Angular), Duration);
}

bool AProphecyAgent::BlendPhysicalFeedbackTolerance(FName BoneName, float Linear, float Angular, float Duration)
{
	auto* Blends = GetWorld() ? GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>() : nullptr;
	return Blends && Blends->Start(*this, BoneName, EProphecyPhysicalBlend::Feedback, FVector2f(Linear, Angular), Duration);
}

int32 AProphecyAgent::BlendBodyMagnetizationBelow(FName Parent, bool bIncludeParent, float Linear, float Angular, float Duration)
{
	if (!ValidRequest(FVector2f(Linear, Angular), Duration)) return 0;
	int32 Count = 0;
	for (FName Bone : Descendants(*this, Parent, bIncludeParent, false))
		Count += BlendBodyMagnetization(Bone, Linear, Angular, Duration) ? 1 : 0;
	return Count;
}

int32 AProphecyAgent::BlendPhysicalFeedbackToleranceBelow(FName Parent, bool bIncludeParent, float Linear, float Angular, float Duration)
{
	if (!ValidRequest(FVector2f(Linear, Angular), Duration)) return 0;
	int32 Count = 0;
	for (FName Bone : Descendants(*this, Parent, bIncludeParent, true))
		Count += BlendPhysicalFeedbackTolerance(Bone, Linear, Angular, Duration) ? 1 : 0;
	return Count;
}

void AProphecyAgent::CancelBodyMagnetizationBlend(FName Bone)
{
	if (auto* Blends = GetWorld() ? GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>() : nullptr)
		Blends->Cancel(*this, Bone, EProphecyPhysicalBlend::Magnetization);
}

void AProphecyAgent::CancelPhysicalFeedbackToleranceBlend(FName Bone)
{
	if (auto* Blends = GetWorld() ? GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>() : nullptr)
		Blends->Cancel(*this, Bone, EProphecyPhysicalBlend::Feedback);
}
