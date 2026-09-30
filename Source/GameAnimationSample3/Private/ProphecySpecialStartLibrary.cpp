#include "ProphecySpecialStartLibrary.h"
#include "ProphecySpecialStart.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "PhysicsEngine/BodyInstance.h"

namespace ProphecySpecialStart
{
namespace
{
TSet<TWeakObjectPtr<const AProphecyAgent>> EnabledAgents;
FDelegateHandle Cleanup;
}
bool Enabled(const AProphecyAgent* Agent) { return !EnabledAgents.IsEmpty() && EnabledAgents.Contains(Agent); }
bool Sample(AProphecyAgent* Agent,TConstArrayView<FName> Names,
    const FTransform& PreviousCarrier,const FTransform& Carrier,float StepSeconds,FSeed& Out)
{
    if (!Enabled(Agent) || !IsValid(Agent)) return false;
    auto* Mesh=Agent->GetPoseReferenceMesh();
    const bool Jolt=Agent->IsJoltPhysicalAnimationEnabled();
    if (!Mesh || (!Jolt && !Mesh->IsAnySimulatingPhysics()) || !FMath::IsFinite(StepSeconds) || StepSeconds<=0) return false;
    Out.Current.SetNum(Names.Num());Out.Previous.SetNum(Names.Num());
    if (!Agent->SampleActualComponentPose(Names,MakeArrayView(Out.Current))) return false;
    const auto* Reference=Agent->GetAgentMesh();
    const auto ReferenceWorld=Reference && Reference->IsRegistered()?Reference->GetComponentTransform():Mesh->GetComponentTransform();
    auto* Character=Jolt?Agent->GetJoltCharacterComponent():nullptr;
    auto* World=Jolt?Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;
    for (int32 I=0;I<Names.Num();++I)
    {
        const FTransform Current=Out.Current[I]*ReferenceWorld;
        FTransform Previous=Current;
        // Bones without a body inherit the nearest physical ancestor's rigid motion.
        for (FName Bone=Names[I];!Bone.IsNone();Bone=Mesh->GetParentBone(Bone))
        {
            FVector Center,Velocity,Angular;bool Dynamic=false;
            if (Jolt)
            {
                FProphecyJoltBodyHandle Handle;FProphecyJoltBodyState State;
                if (!Character->GetBodyHandle(Bone,Handle) || !World->ReadBody(Handle,State).IsSuccess()) continue;
                Center=State.CenterOfMassPositionCm;Velocity=State.CenterOfMassVelocityCmPerSecond;
                Angular=State.AngularVelocityRadiansPerSecond;Dynamic=State.bDynamic;
            }
            else
            {
                auto* Body=Mesh->GetBodyInstance(Bone);if (!Body) continue;
                Center=Body->GetCOMPosition();Velocity=Body->GetUnrealWorldVelocity();
                Angular=Body->GetUnrealWorldAngularVelocityInRadians();Dynamic=Body->IsInstanceSimulatingPhysics();
            }
            if (Dynamic)
            {
                if (Center.ContainsNaN() || Velocity.ContainsNaN() || Angular.ContainsNaN()) return false;
                const double Speed=Angular.Size();
                const FQuat Back=Speed>SMALL_NUMBER?FQuat(Angular/Speed,-Speed*StepSeconds):FQuat::Identity;
                Previous.SetLocation(Center-Velocity*StepSeconds+Back.RotateVector(Current.GetLocation()-Center));
                Previous.SetRotation((Back*Current.GetRotation()).GetNormalized());
            }
            break;
        }
        Out.Current[I]=Current.GetRelativeTransform(Carrier);
        Out.Previous[I]=Previous.GetRelativeTransform(PreviousCarrier);
        if (Out.Current[I].ContainsNaN() || Out.Previous[I].ContainsNaN()) return false;
    }
    return true;
}
}

void UProphecySpecialStartLibrary::SetSpecialStartFromPhysical(AProphecyAgent* Agent,bool Enabled)
{
    using namespace ProphecySpecialStart;
    if (!IsValid(Agent) || Agent->IsActorBeingDestroyed()) return;
    if (Enabled) EnabledAgents.Add(Agent);else EnabledAgents.Remove(Agent);
    if (!EnabledAgents.IsEmpty() && !Cleanup.IsValid())
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=EnabledAgents.CreateIterator();It;++It)
                if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
        });
    if (EnabledAgents.IsEmpty() && Cleanup.IsValid())
    { FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset(); }
}
