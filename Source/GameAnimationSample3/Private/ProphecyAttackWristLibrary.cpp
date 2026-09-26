#include "ProphecyAttackWristLibrary.h"
#include "ProphecyAttackWrist.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyAttackWrist
{
struct FSettings { float Limits[5]={-1,-1,-1,-1,-1}; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> ModeSettings;
static FDelegateHandle ModeCleanup;
float Degrees(const AProphecyAgent* Agent,EProphecyClampProfileMode Mode)
{
    if (ModeSettings.IsEmpty()) return -1;
    const auto* Settings=ModeSettings.Find(Agent);
    const int32 Index=static_cast<int32>(Mode);
    return Settings && Index>0 && Index<5 ? Settings->Limits[Index] : -1;
}
bool Enabled(const AProphecyAgent* Agent)
{ return Degrees(Agent,EProphecyClampProfileMode::Attack)>=0; }

bool ConstrainPose(FTransform& Hand,const FVector& Elbow,float MaxBendDegrees)
{
    // UE's mirrored basis still has anatomical +X for the left palm.
    const FQuat Q=Hand.GetRotation();
    FVector3f Rows[3]={FVector3f(Q.GetAxisX()),FVector3f(Q.GetAxisY()),FVector3f(Q.GetAxisZ())};
    if (!Constrain(Rows,FVector3f::ZeroVector,FVector3f((Hand.GetTranslation()-Elbow)*.01),MaxBendDegrees)) return false;
    FMatrix Matrix=FMatrix::Identity;
    for (int32 I=0;I<3;++I) for (int32 J=0;J<3;++J) Matrix.M[I][J]=Rows[I][J];
    Hand.SetRotation(FQuat(Matrix).GetNormalized());
    return true;
}
}

bool UProphecyAttackWristLibrary::SetLeftHandConstraint(AProphecyAgent* Agent,bool Enabled,
    EProphecyClampProfileMode Mode,float MaxBendDegrees)
{
    using namespace ProphecyAttackWrist;
    const int32 Index=static_cast<int32>(Mode);
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() ||
        !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown || Index<0 || Index>=5) return false;
    if (Enabled && Mode!=EProphecyClampProfileMode::Attack &&
        (!FMath::IsFinite(MaxBendDegrees) || MaxBendDegrees<0 || MaxBendDegrees>=180)) return false;
    if (Enabled || ModeSettings.Contains(Agent))
    {
        auto& Settings=ModeSettings.FindOrAdd(Agent);
        for (int32 I=1;I<5;++I) if (Index==0 || Index==I)
            Settings.Limits[I]=Enabled ? (I==static_cast<int32>(EProphecyClampProfileMode::Attack)?55.f:MaxBendDegrees) : -1.f;
        if (Settings.Limits[1]<0 && Settings.Limits[2]<0 && Settings.Limits[3]<0 && Settings.Limits[4]<0)
            ModeSettings.Remove(Agent);
    }
    if (!ModeCleanup.IsValid() && !ModeSettings.IsEmpty())
        ModeCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=ModeSettings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            if (ModeSettings.IsEmpty()) { FWorldDelegates::OnWorldCleanup.Remove(ModeCleanup);ModeCleanup.Reset(); }
        });
    if (ModeSettings.IsEmpty() && ModeCleanup.IsValid())
    { FWorldDelegates::OnWorldCleanup.Remove(ModeCleanup);ModeCleanup.Reset(); }
    return true;
}
