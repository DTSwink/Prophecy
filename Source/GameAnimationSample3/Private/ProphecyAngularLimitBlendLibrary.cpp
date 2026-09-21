#include "ProphecyAngularLimitBlendLibrary.h"
#include "ProphecyAngularLimitBlend.h"
#include "ProphecyAngularLimits.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "Engine/World.h"

namespace ProphecyAngularLimitBlend
{
struct FBlend
{
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<UPhysicsAsset> Asset;
    TArray<FConstraintProfileProperties> Start,Target;
    uint64 Ticks=0,TotalTicks=0;
};
static TMap<TWeakObjectPtr<AProphecyAgent>,FBlend> Active;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
void Cancel(const AProphecyAgent* Agent)
{
    if (!Active.IsEmpty() && Active.Remove(const_cast<AProphecyAgent*>(Agent))) Refresh();
}
static float Angle(EAngularConstraintMotion Motion,float Limit)
{ return Motion==ACM_Free ? 180.f : Motion==ACM_Locked ? 0.f : Limit; }
static void Axis(EAngularConstraintMotion From,float FromAngle,EAngularConstraintMotion To,float ToAngle,
    float Alpha,TEnumAsByte<EAngularConstraintMotion>& Motion,float& Limit)
{
    if (Alpha<=0) { Motion=From;Limit=FromAngle;return; }
    if (Alpha>=1) { Motion=To;Limit=ToAngle;return; }
    if (From==To && (From!=ACM_Limited || FromAngle==ToAngle))
    { Motion=To;Limit=ToAngle;return; }
    Motion=ACM_Limited;
    Limit=FMath::Lerp(Angle(From,FromAngle),Angle(To,ToAngle),Alpha);
}
static FConstraintProfileProperties Sample(const FConstraintProfileProperties& Start,
    const FConstraintProfileProperties& Target,const FConstraintProfileProperties& Current,float Alpha)
{
    FConstraintProfileProperties P=Current;
    Axis(Start.ConeLimit.Swing1Motion,Start.ConeLimit.Swing1LimitDegrees,
        Target.ConeLimit.Swing1Motion,Target.ConeLimit.Swing1LimitDegrees,Alpha,P.ConeLimit.Swing1Motion,P.ConeLimit.Swing1LimitDegrees);
    Axis(Start.ConeLimit.Swing2Motion,Start.ConeLimit.Swing2LimitDegrees,
        Target.ConeLimit.Swing2Motion,Target.ConeLimit.Swing2LimitDegrees,Alpha,P.ConeLimit.Swing2Motion,P.ConeLimit.Swing2LimitDegrees);
    Axis(Start.TwistLimit.TwistMotion,Start.TwistLimit.TwistLimitDegrees,
        Target.TwistLimit.TwistMotion,Target.TwistLimit.TwistLimitDegrees,Alpha,P.TwistLimit.TwistMotion,P.TwistLimit.TwistLimitDegrees);
    return P;
}
static void JoltRange(TEnumAsByte<EAngularConstraintMotion>& Motion,float& Limit)
{
    if (Motion!=ACM_Limited) return;
    // Respect the existing lossless converter's Jolt thresholds. Do not lock a
    // closing axis early; the exact authored mode is installed at the endpoint.
    if (Limit>179.5f) { Motion=ACM_Free;Limit=180.f; }
    else if (Limit<.5f) Limit=.5f;
}
static bool Apply(AProphecyAgent& Agent,TConstArrayView<FConstraintProfileProperties> Profiles,FString& Error)
{
    if (Agent.IsJoltPhysicalAnimationEnabled())
        return Agent.GetJoltCharacterComponent()->ApplyAngularLimitProfiles(Profiles,Error);
    auto* Mesh=Agent.GetPoseReferenceMesh();
    if (!Mesh || Mesh->Constraints.Num()!=Profiles.Num()) return false;
    for (int32 I=0;I<Profiles.Num();++I) ProphecyAngularLimits::Apply(*Mesh->Constraints[I],Profiles[I]);
    Mesh->WakeAllRigidBodies();return true;
}
static void Tick(UWorld* World,ELevelTick TickType,float DeltaSeconds)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || DeltaSeconds<=0) return;
    for (auto It=Active.CreateIterator();It;++It)
    {
        auto* Agent=It.Key().Get();auto& B=It.Value();
        if (!Agent || Agent->IsActorBeingDestroyed()) { It.RemoveCurrent();continue; }
        if (Agent->GetWorld()!=World) continue;
        auto* Mesh=Agent->GetPoseReferenceMesh();
        TArray<FConstraintProfileProperties> Profiles;FString Error;
        if (Mesh!=B.Mesh.Get() || !Mesh || Mesh->GetPhysicsAsset()!=B.Asset.Get()
            || !ProphecyAngularLimits::Prepare(*Mesh,false,Profiles,Error) || Profiles.Num()!=B.Start.Num())
        { It.RemoveCurrent();continue; }
        const float T=float(FMath::Min(++B.Ticks,B.TotalTicks))/float(B.TotalTicks);
        const float Alpha=T*T*(3.f-2.f*T);
        for (int32 I=0;I<Profiles.Num();++I)
        {
            Profiles[I]=Sample(B.Start[I],B.Target[I],Mesh->Constraints[I]->ProfileInstance,Alpha);
            if (Agent->IsJoltPhysicalAnimationEnabled() && B.Ticks<B.TotalTicks)
            {
                auto& P=Profiles[I];
                JoltRange(P.ConeLimit.Swing1Motion,P.ConeLimit.Swing1LimitDegrees);
                JoltRange(P.ConeLimit.Swing2Motion,P.ConeLimit.Swing2LimitDegrees);
                JoltRange(P.TwistLimit.TwistMotion,P.TwistLimit.TwistLimitDegrees);
            }
        }
        if (!Apply(*Agent,Profiles,Error))
        {
            UE_LOG(LogTemp,Warning,TEXT("Angular limit restore stopped for %s: %s"),*Agent->GetName(),*Error);
            It.RemoveCurrent();continue;
        }
        if (B.Ticks>=B.TotalTicks) It.RemoveCurrent();
    }
    if (Active.IsEmpty()) Refresh();
}
static void Refresh()
{
    if (Active.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();
        return;
    }
    if (!TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    if (!CleanupHandle.IsValid()) CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=Active.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        Refresh();
    });
}
}
bool UProphecyAngularLimitBlendLibrary::BlendToAuthoredAngularLimits(AProphecyAgent* Agent,float Duration,FString& OutError)
{
    using namespace ProphecyAngularLimitBlend;
    OutError.Reset();
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || !FMath::IsFinite(Duration) || Duration<0)
    { OutError=TEXT("A live agent and finite nonnegative duration are required.");return false; }
    auto* Mesh=Agent->GetPoseReferenceMesh();FBlend B;
    if (!Mesh || !ProphecyAngularLimits::Prepare(*Mesh,true,B.Target,OutError)) return false;
    bool Changed=false;
    for (int32 I=0;I<B.Target.Num();++I)
    {
        B.Start.Add(Mesh->Constraints[I]->ProfileInstance);
        Changed|=!ProphecyAngularLimits::Equal(B.Start.Last(),B.Target[I]);
    }
    if (Duration==0 || !Changed)
    {
        if (Duration==0 && !Apply(*Agent,B.Target,OutError)) return false;
        Cancel(Agent);return true;
    }
    B.Mesh=Mesh;B.Asset=Mesh->GetPhysicsAsset();
    B.TotalTicks=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Duration)*60.,9.e15)-1.e-5)));
    Active.Add(Agent,MoveTemp(B));Refresh();return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAngularLimitBlendMathTest,"Prophecy.Joints.AngularLimitBlend",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyAngularLimitBlendMathTest::RunTest(const FString&)
{
    using namespace ProphecyAngularLimitBlend;
    TEnumAsByte<EAngularConstraintMotion> Motion;float Limit;
    Axis(ACM_Free,45,ACM_Limited,40,0,Motion,Limit);
    TestTrue(TEXT("No restriction at start"),Motion==ACM_Free);
    Axis(ACM_Free,45,ACM_Limited,40,.5f,Motion,Limit);
    TestTrue(TEXT("Intermediate limited"),Motion==ACM_Limited);TestEqual(TEXT("180 to40 midpoint"),Limit,110.f);
    Axis(ACM_Free,45,ACM_Locked,23,.5f,Motion,Limit);
    TestTrue(TEXT("Locked target stays limited during blend"),Motion==ACM_Limited);TestEqual(TEXT("Locked midpoint"),Limit,90.f);
    Axis(ACM_Free,45,ACM_Locked,23,1,Motion,Limit);
    TestTrue(TEXT("Locked only at end"),Motion==ACM_Locked);TestEqual(TEXT("Exact authored field"),Limit,23.f);
    Axis(ACM_Free,45,ACM_Free,22,.5f,Motion,Limit);TestTrue(TEXT("Authored free remains free"),Motion==ACM_Free);
    Axis(ACM_Limited,80,ACM_Limited,40,.5f,Motion,Limit);TestEqual(TEXT("Retarget from current limit"),Limit,60.f);
    Axis(ACM_Free,45,ACM_Limited,40,.0001f,Motion,Limit);JoltRange(Motion,Limit);
    TestTrue(TEXT("Jolt free threshold does not abort the blend"),Motion==ACM_Free);TestEqual(TEXT("Canonical free bound"),Limit,180.f);
    Axis(ACM_Free,45,ACM_Locked,23,.9999f,Motion,Limit);JoltRange(Motion,Limit);
    TestTrue(TEXT("Jolt does not lock before completion"),Motion==ACM_Limited);TestEqual(TEXT("Smallest supported intermediate bound"),Limit,.5f);
    return true;
}
#endif
