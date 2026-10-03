from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyModeTransitions.cpp');s=p.read_text();Path('Saved/Diagnostics/GoldenRulesFix/before/'+p.name).write_text(s)
s=s.replace('#include "ProphecyModeTransitions.h"','#include "ProphecyModeTransitions.h"\n#include "ProphecyBlendClock.h"')
a='\tFStorage& ModeTransitionStorage() { static FStorage* S = new FStorage; return *S; }'
s=s.replace(a,a+'''
	// Only the manual physics proxy's nonphysical helpers survive the transition.
	// Full captured poses and their blend clock retire at the deadline.
	auto& ManualHelpers()
	{
		static auto* Helpers = new TMap<TWeakObjectPtr<const AProphecyAgent>, FSnapshot>;
		return *Helpers;
	}''')
s=s.replace('if (!Blend || Agent->GetWorld()->GetTimeSeconds() <= Blend->Start) return;', 'if (Blend && Blend->Start <= 0) return;')
s=s.replace('S.Start = Agent->GetWorld()->GetTimeSeconds();','S.Start = 0;\n\tManualHelpers().Remove(Agent);\n\tProphecyBlendClock::Start(Agent, ProphecyBlendClock::EKind::ModeTransition, BlendSeconds);')
a=s.index('void ProphecyModeTransitions::PreUpdate(');b=s.index('\nvoid ProphecyModeTransitions::Evaluate',a)
s=s[:a]+'''void ProphecyModeTransitions::PreUpdate(const void* Proxy, const AProphecyAgent* A)
{
	FSnapshot Snapshot;
	if (A)
	{
		FPose* S = ModeTransitionStorage().Blends.Find(A);
		USkeletalMeshComponent* M = A->GetPoseReferenceMesh();
		if (S && M && S->Mesh == M)
		{
			S->Start += ProphecyBlendClock::Consume(A, ProphecyBlendClock::EKind::ModeTransition);
			const double T = FMath::Clamp((S->Start + 1.e-8) / BlendSeconds, 0., 1.);
			const bool ManualSim = A->bManualNNPoseApplication && A->GetSimulationMode() == EProphecyAgentSimulationMode::Physical;
			if (T >= 1)
			{
				if (ManualSim)
				{
					Snapshot.bLocal = true;
					Snapshot.Alpha = 0;
					TSet<FName> Physical;
					for (const FBody& B : S->Bodies) Physical.Add(B.Name);
					for (int32 I = 0; I < S->Names.Num(); ++I)
						if (!Physical.Contains(S->Names[I]) && !IsFinger(S->Names[I]))
						{ Snapshot.Names.Add(S->Names[I]); Snapshot.FromLocal.Add(S->Local[I]); }
					ManualHelpers().Add(A, Snapshot);
				}
				ModeTransitionStorage().Blends.Remove(A);
				ProphecyBlendClock::Stop(A, ProphecyBlendClock::EKind::ModeTransition);
			}
			else
			{
				Snapshot.Alpha = float(T*T*(3-2*T));
				Snapshot.bManualSim = ManualSim;
				Snapshot.bLocal = A->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic && S->Start > 0;
				Snapshot.Names = S->Names;
				Snapshot.FromLocal = S->Local;
				for (const FBody& B : S->Bodies) Snapshot.PhysicalBones.Add(B.Name);
				if (!Snapshot.bLocal)
					for (const FTransform& W : S->World) Snapshot.FromCS.Add(W.GetRelativeTransform(M->GetComponentTransform()));
			}
		}
		else if (S)
		{
			ModeTransitionStorage().Blends.Remove(A);
			ManualHelpers().Remove(A);
			ProphecyBlendClock::Stop(A, ProphecyBlendClock::EKind::ModeTransition);
		}
		else if (A->bManualNNPoseApplication && A->GetSimulationMode() == EProphecyAgentSimulationMode::Physical)
		{
			if (const auto* Helpers = ManualHelpers().Find(A)) Snapshot = *Helpers;
		}
	}
	FScopeLock Lock(&ModeTransitionStorage().Lock);
	if (Snapshot.Names.IsEmpty()) ModeTransitionStorage().Snapshots.Remove(Proxy);
	else ModeTransitionStorage().Snapshots.Add(Proxy, MoveTemp(Snapshot));
}
''' +s[b:]
s=s.replace('Desired.SetNum(Output.Pose.GetNumBones());','if (!S->bLocal) Desired.SetNum(Output.Pose.GetNumBones());').replace('Original.SetNum(Output.Pose.GetNumBones());','if (!S->bLocal) Original.SetNum(Output.Pose.GetNumBones());')
s=s.replace('ModeTransitionStorage().Blends.Remove(A);\n\tModeTransitionStorage().Captures.Remove(A);','ModeTransitionStorage().Blends.Remove(A);\n\tManualHelpers().Remove(A);\n\tProphecyBlendClock::Stop(A, ProphecyBlendClock::EKind::ModeTransition);\n\tModeTransitionStorage().Captures.Remove(A);')
p.write_text(s)
