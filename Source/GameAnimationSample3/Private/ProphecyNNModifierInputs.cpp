#include "ProphecyPhysicalContext.h"
#include "ProphecyNNModifierDebug.h"
#include "ProphecyAgent.h"
#include "ProphecyNNRootWindowSmoothing.h"
#include "ProphecyRootMagic.h"
#include "ProphecyRootFacing.h"
#include "ProphecyRootSpeedLimits.h"
#include "ProphecyRootPelvisBoundsLibrary.h"
#include "ProphecyAttackFootLocomotion.h"
#include "ProphecyJointDampingPolicy.h"
#include "Engine/World.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "HAL/IConsoleManager.h"

void ProphecyNNModifierDebug::Roots(FReport& R)
{
    const auto* A=R.Agent;
    if(R.LowerLoco || ProphecyAttackFootLocomotion::FindActive(A))
    {
        if(const auto* W=ProphecyNNRootWindow::Find(A))
            R.Add(TEXT("RootWindow"),TEXT("INPUT"),TEXT("Root window response"),FString::Printf(TEXT("distance/direction/orientation %s | braking %.3g"),*W->Factors.ToCompactString(),ProphecyNNRootWindow::GetDistanceDeceleration(A)));
        if(const auto* V=ProphecyRootMagic::Find(A))
            R.Add(TEXT("RootMagic"),TEXT("INPUT"),TEXT("Root magic velocity"),FString::Printf(TEXT("UE cm/s %.3f,%.3f,%.3f | yaw %.3f deg/s"),100.*V->Linear.X,100.*V->Linear.Z,100.*V->Linear.Y,-FMath::RadiansToDegrees(V->Yaw)));
        if(const auto* L=ProphecyRootSpeedLimits::Find(A))
            R.Add(TEXT("RootSpeed"),TEXT("CONSTRAINT"),TEXT("Root speed limits"),FString::Printf(TEXT("linear %.3g cm/s angular %.3g deg/s | last window clamped %d"),L->Linear*100.,FMath::RadiansToDegrees(L->Angular),L->bClamped));
        if(ProphecyRootFacing::IsImpulseOwned(A))R.Add(TEXT("RootImpulse"),TEXT("INPUT"),TEXT("Impulse-owned facing"),TEXT("unwrapped stopping heading"));
        bool Bounds=false;float Radius=0;UProphecyRootPelvisBoundsLibrary::GetRootPelvisBounds(const_cast<AProphecyAgent*>(A),Bounds,Radius);
        if(Bounds && A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)
            R.Add(TEXT("RootBounds"),TEXT("CONSTRAINT"),TEXT("Root / physical pelvis bound"),FString::Printf(TEXT("radius %.3g cm; requires simulated pelvis"),Radius));
    }
    if(A->CustomTimeDilation!=1 || (A->GetWorld() && A->GetWorld()->IsPaused()))
        R.Add(TEXT("ActorClock"),TEXT("CLOCK"),TEXT("Actor time / world pause"),FString::Printf(TEXT("actor dilation %.3g | paused %d | blend durations remain 60 game ticks"),A->CustomTimeDilation,A->GetWorld()->IsPaused()));
    if(A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)
    {
        if(A->IsJoltPhysicalAnimationEnabled())
            R.Add(TEXT("MagnetizationMode"),TEXT("PHYSICS"),TEXT("Magnetization coordinate mode"),
                FString::Printf(TEXT("%.3g (0 physical-parent local / 1 world); pelvis always world"),ProphecyPhysicalContext::MagnetizationMode(A)));
        const auto* Mesh=A->GetPoseReferenceMesh();const auto* Asset=Mesh?Mesh->GetPhysicsAsset():nullptr;
        if(Asset)for(const USkeletalBodySetup* Body:Asset->SkeletalBodySetups)
        {
            if(!Body)continue;
            FProphecyBodyMagnetizationSettings M;A->GetBodyMagnetizationSettings(Body->BoneName,M);
            if(!M.bSimulateBody)continue;
            const bool Enabled=A->bWorldMagnetizationEnabled&&M.bMagnetizationEnabled;
            float Damping=0;const bool HasDamping=ProphecyJointDamping::Get(A,Body->BoneName,Damping);
            const FString Name=Body->BoneName.ToString();
            R.Add(*(TEXT("Drive/")+Name),TEXT("PHYSICS"),*(TEXT("Drive ")+Name),FString::Printf(TEXT("magnet L %.3g A %.3g | gravity cancel %d | extra joint damping %s"),
                Enabled?M.LinearStrengthScale*A->WorldMagnetizationLinearStrengthScale:0.f,
                Enabled?M.AngularStrengthScale*A->WorldMagnetizationAngularStrengthScale:0.f,M.bCancelGravity,
                HasDamping?*FString::SanitizeFloat(Damping):TEXT("n/a")));
        }
    }
#if WITH_EDITOR
    // Non-default diagnostic switches can silently invalidate a motion comparison.
    struct FSwitch {const TCHAR* Name;int32 Normal;};
    const FSwitch Switches[]={
        {TEXT("Prophecy.SlashTestHalfUpperSource"),-1},{TEXT("Prophecy.SlashTestHalfRelativeTarget"),0},
        {TEXT("Prophecy.KneeSmoothing.SpecialOrder"),1},{TEXT("Prophecy.Debug.SharedCalfRecovery"),1},
        {TEXT("Prophecy.Recovery.LocomotionLengthTarget"),1},{TEXT("Prophecy.Recovery.LengthInterpolation"),1},{TEXT("Prophecy.Recovery.UpperLengthBlend"),1},
        {TEXT("Prophecy.Recovery.CleanSource"),1},{TEXT("Prophecy.Recovery.PolePresentation"),1},
        {TEXT("Prophecy.Recovery.PoleWindow"),1},{TEXT("Prophecy.Tempering.SupportSource"),1},
        {TEXT("Prophecy.Tempering.KneePlane"),3},{TEXT("Prophecy.Tempering.CalfContinuity"),1},
        {TEXT("Prophecy.Tempering.PoleSmoothing"),1}};
    for(const auto& S:Switches)if(const auto* V=IConsoleManager::Get().FindConsoleVariable(S.Name);V && V->GetInt()!=S.Normal)
        R.Add(S.Name,TEXT("DEBUG OVERRIDE"),S.Name,FString::Printf(TEXT("%d (normal %d)"),V->GetInt(),S.Normal));
#endif
}
