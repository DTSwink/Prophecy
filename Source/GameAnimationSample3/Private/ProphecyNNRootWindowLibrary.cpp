#include "ProphecyNNRootWindowLibrary.h"
#include "ProphecyNNRootWindowSmoothing.h"
#include "ProphecyAgent.h"

namespace ProphecyNNRootWindow
{
static TMap<TWeakObjectPtr<const AProphecyAgent>, FState> States;
FState* Find(const AProphecyAgent* Agent) { return States.IsEmpty() ? nullptr : States.Find(Agent); }
void Remove(const AProphecyAgent* Agent) { States.Remove(Agent); }
}

bool UProphecyNNRootWindowLibrary::SetLocomotionRootWindowSmoothing(AProphecyAgent* Agent,
    float Distance, float Direction, float Orientation)
{
    using namespace ProphecyNNRootWindow;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    for (float Factor : {Distance, Direction, Orientation})
        if (!FMath::IsFinite(Factor) || Factor < 0.f || Factor > 1.f) return false;
    for (auto It = States.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    if (Distance == 1.f && Direction == 1.f && Orientation == 1.f) { Remove(Agent); return true; }
    if (auto* Existing = Find(Agent)) { Existing->Factors = FVector(Distance, Direction, Orientation); return true; }
    auto& State = States.Add(Agent);
    State.Factors = FVector(Distance, Direction, Orientation);
    // Before the first published window the only established transform is root0.
    // Start collapsed, so zero factors cannot admit the first nonzero movement request.
    for (auto& Sample : State.Samples) Sample.bInitialized = true;
    TArray<FTransform> Roots;
    TArray<float> Times;
    if (Agent->GetLocomotionRootWindow(Roots, Times) && Roots.Num() == Count + 2)
        for (int32 I = 0; I < Count; ++I)
        {
            const FTransform Local = Roots[I+2].GetRelativeTransform(Roots[1]);
            double Yaw = FMath::DegreesToRadians(Local.Rotator().Yaw);
            State.Samples[I].Filter(Local.GetLocation(), Yaw, FVector::OneVector);
        }
    return true;
}

void UProphecyNNRootWindowLibrary::GetLocomotionRootWindowSmoothing(AProphecyAgent* Agent,
    float& Distance, float& Direction, float& Orientation)
{
    const auto* State = ProphecyNNRootWindow::Find(Agent);
    const FVector F = State ? State->Factors : FVector::OneVector;
    Distance = F.X; Direction = F.Y; Orientation = F.Z;
}
