#pragma once
#include "CoreMinimal.h"
#include "ProphecyRobotProfile.h"
#include "ProphecyLocomotionTypeLibrary.h"
class AProphecyAgent;
class UWorld;
struct FProphecyJoltRigHandle;
class UProphecyJoltWorldSubsystem;
enum class EProphecyAgentSimulationMode : uint8;
namespace ProphecyRobot
{
bool IsActive(const AProphecyAgent* Agent);
bool HasRobot(const UWorld* World);
bool ExitToSimulationMode(AProphecyAgent* Agent,EProphecyAgentSimulationMode Mode,FString& Error);
void EntryHelpers(AProphecyAgent* Agent,TArray<FTransform>& Local);
void ForgetReturn(const AProphecyAgent* Agent);
bool OverrideSnapshot(AProphecyAgent* Agent,USkeletalMeshComponent& Mesh,FProphecyJoltRigSnapshot& Snapshot,FString& Error);
bool Configure(AProphecyAgent* Agent,UProphecyJoltWorldSubsystem& World,const FProphecyJoltRigHandle& Rig,FString& Error);
bool Prepare(AProphecyAgent* Agent,UProphecyJoltWorldSubsystem& World,const FProphecyJoltRigHandle& Rig,FString& Error);
void Forget(AProphecyAgent* Agent);
// Exact pose history lives in NN's published-bone order, in world space.
// Current Blueprint lower return and accepted slashLD upper return tuning.
struct FReturnSettings {float Lower=1.5f,Upper=.39f,Inertia=.18f,Easing=0,Hold=.17f,Coefficient=1,LowerHold=0;};
FReturnSettings ReturnSettings(const AProphecyAgent* Agent);
}
