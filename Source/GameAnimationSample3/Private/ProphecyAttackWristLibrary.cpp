#include "ProphecyAttackWristLibrary.h"
#include "ProphecyAttackWrist.h"
#include "ProphecyForearmStretch.h"
#include "ProphecyAgent.h"
#include "ProphecyClampEase.h"
#include "Engine/World.h"

namespace ProphecyAttackWrist
{
struct FSettings { float Limits[5]={-1,-1,-1,-1,-1}; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> ModeSettings;
static TMap<TWeakObjectPtr<const AProphecyAgent>,uint8> Freedom;
static TMap<TWeakObjectPtr<const AProphecyAgent>,uint16> AttackMasks;
static FDelegateHandle ModeCleanup;
static bool Valid(AProphecyAgent* Agent)
{ return IsInGameThread() && IsValid(Agent) && !Agent->IsActorBeingDestroyed() && Agent->GetWorld() && !Agent->GetWorld()->bIsTearingDown; }
static void RefreshCleanup()
{
    const bool Any=!ModeSettings.IsEmpty() || !Freedom.IsEmpty() || !AttackMasks.IsEmpty();
    if (!ModeCleanup.IsValid() && Any)
        ModeCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=ModeSettings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=Freedom.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=AttackMasks.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            RefreshCleanup();
        });
    if (!Any && ModeCleanup.IsValid())
    { FWorldDelegates::OnWorldCleanup.Remove(ModeCleanup);ModeCleanup.Reset(); }
}
bool FreePosition(const AProphecyAgent* Agent) { return ProphecyForearmStretch::OwnsPosition(Agent) || (!Freedom.IsEmpty() && (Freedom.FindRef(Agent)&1)!=0); }
bool FreeRotation(const AProphecyAgent* Agent) { return !Freedom.IsEmpty() && (Freedom.FindRef(Agent)&6)!=0; }
float Degrees(const AProphecyAgent* Agent,EProphecyClampProfileMode Mode,FName Attack)
{
    if(FreeRotation(Agent))return -1;
    if (ModeSettings.IsEmpty()) return -1;
    const auto* Settings=ModeSettings.Find(Agent);
    const int32 Index=static_cast<int32>(Mode);
    const float Limit=Settings && Index>0 && Index<5 ? Settings->Limits[Index] : -1;
    if (Limit>=0 && Mode==EProphecyClampProfileMode::Attack && !Attack.IsNone() && !AttackMasks.IsEmpty())
        if (const auto* Mask=AttackMasks.Find(Agent))
        {
            static const FName Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
                TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
            for (int32 I=0;I<UE_ARRAY_COUNT(Names);++I) if (Attack==Names[I]) return (*Mask&(1u<<I))?Limit:-1.f;
        }
    return Limit;
}
bool Enabled(const AProphecyAgent* Agent,FName Attack)
{ const float Limit=Degrees(Agent,EProphecyClampProfileMode::Attack,Attack);return Limit>=0 && Limit<180; }

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
    if (!Valid(Agent) || Index<0 || Index>=5) return false;
    if (Enabled && (!FMath::IsFinite(MaxBendDegrees) || MaxBendDegrees<0 || MaxBendDegrees>180)) return false;
    if (Enabled || ModeSettings.Contains(Agent))
    {
        auto& Settings=ModeSettings.FindOrAdd(Agent);
        for (int32 I=1;I<5;++I) if (Index==0 || Index==I)
            Settings.Limits[I]=Enabled ? MaxBendDegrees : -1.f;
        if (Settings.Limits[1]<0 && Settings.Limits[2]<0 && Settings.Limits[3]<0 && Settings.Limits[4]<0)
            ModeSettings.Remove(Agent);
    }
    RefreshCleanup();
    return true;
}

bool UProphecyAttackWristLibrary::SetNNWristFreedom(AProphecyAgent* Agent,bool FreePosition,bool FreeRotation)
{
    using namespace ProphecyAttackWrist;
    if(!Valid(Agent))return false;
    const uint8 Flags=(Freedom.FindRef(Agent)&4)|(FreePosition?1:0)|(FreeRotation?2:0);
    if(Flags)Freedom.Add(Agent,Flags);else Freedom.Remove(Agent);
    if(FreeRotation)ProphecyClampEase::Resolve(Agent,ProphecyClampEase::EChannel::Wrist,-1);
    RefreshCleanup();return true;
}

bool UProphecyAttackWristLibrary::SetLeftHandConstraintAttacks(AProphecyAgent* Agent,
    bool SlashL,bool SlashR,bool SlashLD,bool SlashRD,bool SlashLU,bool SlashRU,bool Pike,
    bool JabL,bool JabR,bool HookL,bool HookR,bool OverL,bool OverR,bool Headbutt,bool KickL,bool KickR)
{
    using namespace ProphecyAttackWrist;
    if(!Valid(Agent))return false;
    const bool Values[]={SlashL,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike,JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR};
    uint16 Mask=0;for(int32 I=0;I<UE_ARRAY_COUNT(Values);++I)if(Values[I])Mask|=uint16(1u<<I);
    if(Mask==0xffff)AttackMasks.Remove(Agent);else AttackMasks.Add(Agent,Mask);
    RefreshCleanup();return true;
}

bool UProphecyAttackWristLibrary::SetLeftHandConstraintGlobalEnabled(AProphecyAgent* Agent,bool Enabled)
{
    using namespace ProphecyAttackWrist;
    if(!Valid(Agent))return false;
    const uint8 Flags=(Freedom.FindRef(Agent)&3)|(Enabled?0:4);
    if(Flags)Freedom.Add(Agent,Flags);else Freedom.Remove(Agent);
    if(!Enabled)ProphecyClampEase::Resolve(Agent,ProphecyClampEase::EChannel::Wrist,-1);
    RefreshCleanup();return true;
}
