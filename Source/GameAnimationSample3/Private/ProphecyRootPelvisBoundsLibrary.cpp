#include "ProphecyRootPelvisBoundsLibrary.h"
#include "ProphecyRootPelvisBounds.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "Components/PrimitiveComponent.h"

// Kept in its own translation unit so bounds implementation edits do not rebuild the NN implementation.
namespace ProphecyRootPelvisBounds
{
// Separate opt-in storage preserves existing UObject/native layouts for Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>, float> Radii;
static TMap<TWeakObjectPtr<const AProphecyAgent>, TWeakObjectPtr<UPrimitiveComponent>> MagicCubes;
void Remove(const AProphecyAgent* Agent) { Radii.Remove(Agent); MagicCubes.Remove(Agent); }

void Apply(AProphecyNNLocomotionManager& Manager)
{
    if (Radii.IsEmpty()) return;
    static const FName PelvisBone(TEXT("pelvis"));
    struct FCorrection { FProphecyAgentHandle Handle; FVector Root; };
    TArray<FCorrection, TInlineAllocator<32>> Corrections;
    for (auto It = Radii.CreateIterator(); It; ++It)
    {
        const auto* Actor = It.Key().Get();
        if (!IsValid(Actor) || Actor->IsActorBeingDestroyed()) { MagicCubes.Remove(It.Key()); It.RemoveCurrent(); continue; }
        const auto Handle = Actor->GetAgentHandle();
        if (!Actor->bNNInferenceEnabled || Manager.ResolveAgent(Handle) != Actor) continue;
        FTransform Pelvis;
        FVector LinearVelocity, AngularVelocity;
        bool bSimulated = false;
        if (!Actor->GetPhysicalBodyState(PelvisBone, Pelvis, LinearVelocity, AngularVelocity, bSimulated) || !bSimulated) continue;
        FVector ClampedRoot;
        if (ClampLocation(Actor->GetRootLowPoint(), Pelvis.GetLocation(), It.Value(), ClampedRoot))
            Corrections.Add({Handle, ClampedRoot});
    }
    // Moving the actor can dispatch overlap callbacks that retune/disable bounds.
    // Finish iterating configuration before executing those moves.
    for (const auto& Correction : Corrections)
    {
        auto* Actor = Manager.ResolveAgent(Correction.Handle);
        if (!IsValid(Actor) || !Radii.Contains(Actor)) continue;
        const auto* Registered = MagicCubes.Find(Actor);
        const TWeakObjectPtr<UPrimitiveComponent> Cube = Registered ? *Registered : nullptr;
        // Capture BEFORE actor movement: attached components may already inherit that move.
        const FVector CubeDestination = Cube.IsValid()
            ? Cube->GetComponentLocation() + Correction.Root - Actor->GetRootLowPoint()
            : FVector::ZeroVector;
        if (Manager.SetAgentLocomotionRootWindowLocation(Correction.Handle, Correction.Root, true)
            && Cube.IsValid() && !Cube->IsBeingDestroyed())
        {
            // The Jolt adapter's TransformUpdated hook synchronizes its native body pose.
            // TeleportPhysics also preserves velocities on the Chaos fallback.
            Cube->SetWorldLocation(CubeDestination, false, nullptr, ETeleportType::TeleportPhysics);
        }
    }
}
}

bool UProphecyRootPelvisBoundsLibrary::SetRootPelvisBounds(AProphecyAgent* Agent, bool bEnabled, float RadiusCm, UPrimitiveComponent* MagicCube)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    if (!bEnabled) { ProphecyRootPelvisBounds::Remove(Agent); return true; }
    if (!FMath::IsFinite(RadiusCm) || RadiusCm < 0.f) return false;
    if (MagicCube && (!IsValid(MagicCube) || MagicCube->IsBeingDestroyed() || MagicCube->GetWorld() != Agent->GetWorld())) return false;
    ProphecyRootPelvisBounds::Radii.Add(Agent, RadiusCm);
    if (MagicCube) ProphecyRootPelvisBounds::MagicCubes.Add(Agent, MagicCube);
    else ProphecyRootPelvisBounds::MagicCubes.Remove(Agent);
    return true;
}

void UProphecyRootPelvisBoundsLibrary::GetRootPelvisBounds(AProphecyAgent* Agent, bool& bEnabled, float& RadiusCm)
{
    const float* Radius = IsInGameThread() && IsValid(Agent) ? ProphecyRootPelvisBounds::Radii.Find(Agent) : nullptr;
    bEnabled = Radius != nullptr;
    RadiusCm = Radius ? *Radius : 20.f;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootPelvisBoundsTest, "Prophecy.Root.PelvisBounds.PlanarCircle",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRootPelvisBoundsTest::RunTest(const FString& Parameters)
{
    using ProphecyRootPelvisBounds::ClampLocation;
    FVector Result;
    const FVector Pelvis(100., 200., 90.);
    TestFalse(TEXT("Inside circle unchanged"), ClampLocation(FVector(103,204,-.5),Pelvis,20.,Result));
    TestTrue(TEXT("Inside preserves root exactly"), Result == FVector(103,204,-.5));
    TestFalse(TEXT("Boundary unchanged"), ClampLocation(FVector(112,216,-.5),Pelvis,20.,Result));
    TestTrue(TEXT("Diagonal outside corrected"), ClampLocation(FVector(130,240,-.5),Pelvis,20.,Result));
    TestTrue(TEXT("Circle, not an axis-aligned box; Z preserved"), Result.Equals(FVector(112,216,-.5),1.e-8));
    TestTrue(TEXT("Zero radius supported"), ClampLocation(FVector(130,240,-.5),Pelvis,0.,Result));
    TestTrue(TEXT("Zero radius directly below pelvis"), Result == FVector(100,200,-.5));
    TestFalse(TEXT("Negative radius rejected"), ClampLocation(FVector(130,240,0),Pelvis,-1.,Result));
    return true;
}
#endif
