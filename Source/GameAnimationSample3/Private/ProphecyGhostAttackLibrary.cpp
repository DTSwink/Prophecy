#include "ProphecyGhostAttackLibrary.h"
#include "ProphecyHalfAttackCompensation.h"
#include "ProphecyAttackControls.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyRootPhysicsLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
#include "DrawDebugHelpers.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Chaos/Convex.h"
#include "Engine/SkeletalMeshSocket.h"
#include "Engine/World.h"
#include "Components/LineBatchComponent.h"
#include "Misc/AutomationTest.h"
#include "ProphecyAttackControls.inl"

namespace ProphecyHalfAttackCompensation
{
// No ticking state, world delegates or retained object-layout changes. EndPlay
// removes the weak-key entries; disabling erases the agent's active entry.
static TSet<TWeakObjectPtr<const AProphecyAgent>> Active,ResetEnabled;
static TSet<TWeakObjectPtr<const AProphecyAgent>> DistributedAgents,ResetDistributed;
static TSet<TWeakObjectPtr<const AProphecyAgent>> PositionAgents,ResetPosition;
bool Enabled(const AProphecyAgent* A) { return !Active.IsEmpty() && Active.Contains(A); }
bool Distributed(const AProphecyAgent* A) { return !DistributedAgents.IsEmpty() && DistributedAgents.Contains(A); }
bool Position(const AProphecyAgent* A) { return !PositionAgents.IsEmpty() && PositionAgents.Contains(A); }
void Remove(const AProphecyAgent* A) { Active.Remove(A);ResetEnabled.Remove(A);DistributedAgents.Remove(A);ResetDistributed.Remove(A);PositionAgents.Remove(A);ResetPosition.Remove(A); }
void CaptureReset(const AProphecyAgent* A)
{
    if(Enabled(A)) ResetEnabled.Add(A);else ResetEnabled.Remove(A);
    if(Distributed(A)) ResetDistributed.Add(A);else ResetDistributed.Remove(A);
    if(Position(A)) ResetPosition.Add(A);else ResetPosition.Remove(A);
}
void RestoreReset(const AProphecyAgent* A)
{
    if(ResetEnabled.Contains(A)) Active.Add(A);else Active.Remove(A);
    if(ResetDistributed.Contains(A)) DistributedAgents.Add(A);else DistributedAgents.Remove(A);
    if(ResetPosition.Contains(A)) PositionAgents.Add(A);else PositionAgents.Remove(A);
}
void ForgetReset(const AProphecyAgent* A) { ResetEnabled.Remove(A);ResetDistributed.Remove(A);ResetPosition.Remove(A); }
}
bool UProphecyGhostAttackLibrary::EnableSpine01CompensationHalfAttack(AProphecyAgent* Agent,bool Enabled,bool DistributeAlongSpine01ToSpine05,bool CompensatePosition)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    if(Enabled) ProphecyHalfAttackCompensation::Active.Add(Agent);
    else ProphecyHalfAttackCompensation::Active.Remove(Agent);
    if(Enabled && DistributeAlongSpine01ToSpine05) ProphecyHalfAttackCompensation::DistributedAgents.Add(Agent);
    else ProphecyHalfAttackCompensation::DistributedAgents.Remove(Agent);
    if(Enabled && CompensatePosition) ProphecyHalfAttackCompensation::PositionAgents.Add(Agent);
    else ProphecyHalfAttackCompensation::PositionAgents.Remove(Agent);
    return true;
}

#if !UE_BUILD_SHIPPING
namespace
{
void DrawShapes(UWorld* World,const FKAggregateGeom& Geometry,const FTransform& Body,
    FColor Color,float Duration,float Thickness)
{
    for (const auto& Box:Geometry.BoxElems)
    {
        const FTransform T=Box.GetTransform()*Body;
        DrawDebugBox(World,T.GetLocation(),FVector(Box.X,Box.Y,Box.Z)*0.5*T.GetScale3D().GetAbs(),T.GetRotation(),Color,false,Duration,0,Thickness);
    }
    for (const auto& Sphere:Geometry.SphereElems)
        DrawDebugSphere(World,Body.TransformPosition(Sphere.Center),Sphere.Radius*Body.GetScale3D().GetAbsMax(),16,Color,false,Duration,0,Thickness);
    for (const auto& Capsule:Geometry.SphylElems)
    {
        const FTransform T=Capsule.GetTransform()*Body;
        const FVector Scale=T.GetScale3D().GetAbs();
        const float Radius=Capsule.Radius*FMath::Max(Scale.X,Scale.Y);
        DrawDebugCapsule(World,T.GetLocation(),0.5f*Capsule.Length*Scale.Z+Radius,Radius,T.GetRotation(),Color,false,Duration,0,Thickness);
    }
    for (const auto& Convex:Geometry.ConvexElems)
    {
        const FTransform T=Convex.GetTransform()*Body;
        if (const auto* Hull=Convex.GetChaosConvexMesh().GetReference())
        {
            // Cooked collision topology remains available even when editable triangle
            // indices were discarded (for example after rebuilding the sword hull).
            for (int32 Face=0;Face<Hull->NumPlanes();++Face)
            {
                const int32 Count=Hull->NumPlaneVertices(Face);
                for (int32 Edge=0;Edge<Count;++Edge)
                {
                    const FVector A(Hull->GetVertex(Hull->GetPlaneVertex(Face,Edge)));
                    const FVector B(Hull->GetVertex(Hull->GetPlaneVertex(Face,(Edge+1)%Count)));
                    DrawDebugLine(World,T.TransformPosition(A),T.TransformPosition(B),Color,false,Duration,0,Thickness);
                }
            }
            continue;
        }
        for (int32 I=0;I+2<Convex.IndexData.Num();I+=3) for (int32 Edge=0;Edge<3;++Edge)
        {
            const int32 A=Convex.IndexData[I+Edge],B=Convex.IndexData[I+(Edge+1)%3];
            if (Convex.VertexData.IsValidIndex(A) && Convex.VertexData.IsValidIndex(B))
                DrawDebugLine(World,T.TransformPosition(Convex.VertexData[A]),T.TransformPosition(Convex.VertexData[B]),Color,false,Duration,0,Thickness);
        }
    }
}
}
#endif
bool UProphecyGhostAttackLibrary::VisualizeGhostAttack(AProphecyAgent* Agent,bool Enabled,
    FVector WorldOffset,float Duration,float Thickness)
{
#if !UE_BUILD_SHIPPING
    if (!Enabled || !IsInGameThread() || !IsValid(Agent) || !Agent->GetWorld() || WorldOffset.ContainsNaN()
        || !FMath::IsFinite(Duration) || Duration<0 || !FMath::IsFinite(Thickness) || Thickness<0) return false;
    TArray<FName> Names; TArray<FTransform> Pose; FVector Target;
    bool Found=false;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
        { Found=It->ReadAgentAttackGhost(Agent->GetAgentHandle(),Names,Pose,Target); break; }
    if (!Found) return false;
    for (auto& T:Pose) T.AddToTranslation(WorldOffset);
    UWorld* World=Agent->GetWorld();
    const auto* Mesh=Agent->GetPoseReferenceMesh();
    const auto* Asset=Mesh ? Mesh->GetPhysicsAsset() : nullptr;
    if (Asset) for (const USkeletalBodySetup* Body:Asset->SkeletalBodySetups)
    {
        if (!Body) continue;
        const int32 Bone=Names.IndexOfByKey(Body->BoneName);
        if (Pose.IsValidIndex(Bone)) DrawShapes(World,Body->AggGeom,Pose[Bone],FColor::Cyan,Duration,Thickness);
    }
    // Explicit debug calls may load the fallback sword once; no gameplay tick does so.
    UStaticMesh* SwordMesh=Agent->SwordTrainingMesh.Get();
    if (AActor* Sword=Agent->GetHeldSword())
        if (const auto* Blade=Cast<UStaticMeshComponent>(Sword->GetRootComponent())) SwordMesh=Blade->GetStaticMesh();
    if (!SwordMesh) SwordMesh=Agent->SwordTrainingMesh.LoadSynchronous();
    FName HandBone=Agent->SwordHandSocket; FTransform Grip=Agent->SwordGripTransform;
    if (Mesh) if (const auto* Socket=Mesh->GetSocketByName(HandBone))
    { HandBone=Socket->BoneName; Grip=Grip*Socket->GetSocketLocalTransform(); }
    const int32 Hand=Names.IndexOfByKey(HandBone);
    if (SwordMesh && SwordMesh->GetBodySetup() && Pose.IsValidIndex(Hand))
        DrawShapes(World,SwordMesh->GetBodySetup()->AggGeom,Grip*Pose[Hand],FColor::Yellow,Duration,Thickness);
    Target+=WorldOffset;
    DrawDebugSphere(World,Target,5,16,FColor::Red,false,Duration,0,Thickness);
    const int32 Pelvis=Names.IndexOfByKey(FName(TEXT("pelvis")));
    if (Pose.IsValidIndex(Pelvis)) DrawDebugDirectionalArrow(World,Pose[Pelvis].GetLocation(),Target,8,FColor::Red,false,Duration,0,Thickness);
    return true;
#else
    return false;
#endif
}

#if WITH_DEV_AUTOMATION_TESTS && !UE_BUILD_SHIPPING
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGhostSwordDrawTest,"Prophecy.NN.HalfAttack.GhostSwordDrawing",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyGhostSwordDrawTest::RunTest(const FString& Parameters)
{
    UStaticMesh* Sword=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/_mygame/sword/geometry/Sword_GL01_Training.Sword_GL01_Training"));
    if (!TestNotNull(TEXT("Actual sword collision mesh"),Sword) || !TestNotNull(TEXT("Sword body setup"),Sword->GetBodySetup())) return false;
    auto Geometry=Sword->GetBodySetup()->AggGeom;
    // FKConvexElem copying intentionally omits its native cooked object.
    for (int32 I=0;I<Geometry.ConvexElems.Num();++I)
    {
        auto Cooked=Sword->GetBodySetup()->AggGeom.ConvexElems[I].GetChaosConvexMesh();
        if (!TestTrue(TEXT("Sword has cooked hull"),bool(Cooked))) return false;
        Geometry.ConvexElems[I].SetConvexMeshObject(MoveTemp(Cooked),FKConvexElem::EConvexDataUpdateMethod::UpdateConvexDataOnlyIfMissing);
        Geometry.ConvexElems[I].IndexData.Reset();
    }
    const UWorld::InitializationValues Values=UWorld::InitializationValues().AllowAudioPlayback(false)
        .RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false)
        .ShouldSimulatePhysics(false).EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!TestNotNull(TEXT("Debug fixture world"),World)) return false;
    World->UpdateWorldComponents(false,false);
    DrawShapes(World,Geometry,FTransform::Identity,FColor::Yellow,0.f,1.f);
    const auto* Batch=World->GetLineBatcher(UWorld::ELineBatcherType::World);
    TestTrue(TEXT("Actual cooked sword hull produces wire edges without editable indices"),Batch && Batch->BatchedLines.Num()>12);
    TestFalse(TEXT("Disabled visualization does nothing"),UProphecyGhostAttackLibrary::VisualizeGhostAttack(nullptr,false));
    World->DestroyWorld(false); World->MarkAsGarbage();
    return !HasAnyErrors();
}
#endif
