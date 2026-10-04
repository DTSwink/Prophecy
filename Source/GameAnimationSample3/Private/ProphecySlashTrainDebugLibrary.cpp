#include "ProphecySlashTrainDebugLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
#include "ProphecyCustomAttack.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltStandardPhysicsLibrary.h"
#include "ProphecyPelvisInertiaMath.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/BodyInstance.h"
#include "HAL/IConsoleManager.h"

bool ProphecyCustomAttack::PlacePhysical(AProphecyAgent* Agent,TConstArrayView<FName> Names,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current,const FTransform& Carrier,FString& Error)
{
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Mesh || Agent->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic) return true;
    TArray<FTransform> Actual;Actual.SetNum(Names.Num());
    if (!Agent->SampleActualComponentPose(Names,Actual))
    { Error=TEXT("Cannot read the physical rig for the captured pose.");return false; }
    const auto Reference=Agent->GetAgentMesh()->GetComponentTransform();
    auto* Character=Agent->GetJoltCharacterComponent();
    auto* World=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    const bool Jolt=Agent->IsJoltPhysicalAnimationEnabled();
    for (int32 I=0;I<Names.Num();++I)
    {
        FTransform Body;FVector Linear,Angular;bool Dynamic;
        if (!Agent->GetPhysicalBodyState(Names[I],Body,Linear,Angular,Dynamic))continue;
        const auto Offset=Body.GetRelativeTransform(Actual[I]*Reference);
        const auto Now=Offset*Current[I]*Carrier,Before=Offset*Previous[I]*Carrier;
        const FVector W=ProphecyPelvisInertia::RotationVector(Now.GetRotation()*Before.GetRotation().Inverse())*30.;
        if (Jolt)
        {
            FProphecyJoltBodyHandle H;FProphecyJoltBodyState State;
            if (!Character || !World || !Character->GetBodyHandle(Names[I],H) || !World->ReadBody(H,State).IsSuccess())
            { Error=TEXT("Cannot read a captured Jolt body.");return false; }
            const FVector COM=Body.InverseTransformPosition(State.CenterOfMassPositionCm);
            const FVector V=(Now.TransformPosition(COM)-Before.TransformPosition(COM))*30.;
#if !UE_BUILD_SHIPPING
            FTransform RigidNow=Now;RigidNow.RemoveScaling();RigidNow.NormalizeRotation();
            auto* Permit=IConsoleManager::Get().FindConsoleVariable(TEXT("Prophecy.Jolt.DebugRigTeleport"));
            if (!Permit) { Error=TEXT("Load the captured-pose physics patch first.");return false; }
            const int32 SavedPermit=Permit->GetInt();Permit->Set(1,ECVF_SetByCode);
            const auto P=World->SetBodyPose(H,RigidNow);
            Permit->Set(SavedPermit,ECVF_SetByCode);
            if (!P.IsSuccess()) { Error=Names[I].ToString()+TEXT(": ")+P.Message;return false; }
            if (State.bDynamic)
            {
                const auto Velocity=World->SetBodyVelocity(H,V,W,true);
                if (!Velocity.IsSuccess()) { Error=Names[I].ToString()+TEXT(": ")+Velocity.Message;return false; }
            }
#else
            Error=TEXT("Captured physical pose restoration is development-only.");return false;
#endif
        }
        else if (auto* B=Mesh->GetBodyInstance(Names[I]))
        {
            const FVector COM=Body.InverseTransformPosition(B->GetCOMPosition());
            B->SetBodyTransform(Now,ETeleportType::TeleportPhysics,false);
            B->SetLinearVelocity((Now.TransformPosition(COM)-Before.TransformPosition(COM))*30.,false);
            B->SetAngularVelocityInRadians(W,false);
        }
    }
    // Move the existing held sword with the hand; retain its controller and grip.
    const int32 Hand=Names.IndexOfByKey(Agent->SwordHandSocket);
    if (Hand!=INDEX_NONE) if (auto* Sword=Agent->GetHeldSword())
        if (auto* Primitive=Sword->FindComponentByClass<UPrimitiveComponent>())
        {
            FTransform Now=Agent->SwordGripTransform*Current[Hand]*Carrier;
            const FTransform Before=Agent->SwordGripTransform*Previous[Hand]*Carrier;
            Now.SetScale3D(Primitive->GetComponentScale());FHitResult Hit;
            UProphecyJoltStandardPhysicsLibrary::K2_SetWorldTransform(Primitive,Now,false,Hit,true);
            UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsLinearVelocity(Primitive,(Now.GetLocation()-Before.GetLocation())*30.,false);
            UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsAngularVelocityInRadians(Primitive,
                ProphecyPelvisInertia::RotationVector(Now.GetRotation()*Before.GetRotation().Inverse())*30.,false);
        }
    return true;
}

bool UProphecySlashTrainDebugLibrary::PrepareProblemSlash(AProphecyAgent* Agent,FVector& TargetWorldLocation,FString& OutError)
{
    return PrepareGTAttackFromIdle(Agent,TEXT("CodexProblemSlashL"),TargetWorldLocation,OutError);
}

bool UProphecySlashTrainDebugLibrary::SetSlashTrainStartingPose(AProphecyAgent* Agent,FString& OutError)
{
    OutError=TEXT("Agent is not initialized.");
    if (IsInGameThread() && IsValid(Agent) && Agent->GetWorld() && Agent->HasValidAgentHandle())
        for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
            if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
                return It->SetSlashTrainStartingPose(Agent->GetAgentHandle(),OutError);
    return false;
}

bool UProphecySlashTrainDebugLibrary::PrepareGTAttackFromIdle(AProphecyAgent* Agent,FName Attack,
    FVector& TargetWorldLocation,FString& OutError)
{
    TargetWorldLocation=FVector::ZeroVector;
    OutError=TEXT("Select a supported attack on an initialized idle agent.");
    if (!Attack.IsNone() && IsInGameThread() && IsValid(Agent) && Agent->GetWorld() && Agent->HasValidAgentHandle())
        for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
            if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
                return It->SetSlashTrainStartingPose(Agent->GetAgentHandle(),OutError,Attack,&TargetWorldLocation);
    return false;
}
